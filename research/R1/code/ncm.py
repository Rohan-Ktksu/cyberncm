"""Next-Context Model (NCM): scores how abnormal a source's behaviour is, window by window.

The backbone is trained on benign traffic only, to predict a source's next 5-second window from its
history. Three unsupervised signals come out of it, each standardized against benign calibration data:

  dx  distance from this window to the nearest of 512 known benign behaviour tokens   (odd window)
  ds  distance from the hidden state to the nearest of 512 known benign states        (odd history)
  g,k how badly the model predicted this window (Gaussian and token surprise)         (odd transition)

surprise = z(dx) + z(ds) + (z(g) + z(k)) / 2, then smoothed per source with an EWMA.
A supervised stage head on [state, window] gives the kill-chain stage and the hazard 1 - P(benign).
"""
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

STAGES = ["BENIGN", "RECONNAISSANCE", "INITIAL_ACCESS", "LATERAL_MOVEMENT", "COMMAND_AND_CONTROL", "IMPACT"]
EWMA = 0.1  # smoothing factor per window; one isolated odd window does not raise an alert


def stage_of(family: str) -> int:
    """Kill-chain stage of a CIC-IDS2017 attack family."""
    if family == "BENIGN":
        return 0
    if family in ("Portscan", "Reconnaissance", "Analysis"):  # last two: UNSW-NB15 (R1 judgement call)
        return 1
    if family.startswith("Infiltration"):
        return 3
    if family.startswith("Botnet") or family == "Backdoor":  # 2018: "Botnet Ares"
        return 4
    if family == "Worms":
        return 3
    if family.startswith("DoS") or family.startswith("DDoS"):  # 2018: DDoS-HOIC, DDoS-LOIC-UDP
        return 5
    return 2  # brute force, web attacks, Heartbleed


def nearest(a, book):
    """Distance to, and index of, the nearest codebook row. Plain matmul so it exports and quantizes."""
    d2 = (a * a).sum(-1, keepdim=True) - 2 * a @ book.T + (book * book).sum(-1)
    return d2.clamp_min(1e-6).min(-1).values.sqrt(), d2.argmin(-1)


class Linear(nn.Linear):
    """nn.Linear written as matmul + add: ONNX Runtime's INT8 quantizer mishandles the Gemm op it exports to."""

    def forward(self, x):
        return x @ self.weight.T + self.bias


class NCM(nn.Module):
    def __init__(self, d=32, h=64, layers=2, vocab=512, arch="gru", ctx=32):
        super().__init__()
        self.d, self.h, self.layers, self.arch, self.ctx = d, h, layers, arch, ctx
        self.register_buffer("mean", torch.zeros(d))
        self.register_buffer("std", torch.ones(d))
        self.register_buffer("codebook", torch.zeros(vocab, d))        # benign behaviour tokens
        self.register_buffer("state_codebook", torch.zeros(vocab, h))  # benign hidden states
        self.register_buffer("calib", torch.tensor([[0.0, 1.0]] * 4))  # benign mean, std of dx, ds, g, k
        self.emb = nn.Sequential(Linear(d, h), nn.GELU())
        if arch == "gru":
            self.rnn = nn.GRU(h, h, layers, batch_first=True, dropout=0.1)
        else:  # causal Transformer over blocks of `ctx` windows (ablation only, not exported)
            self.pos = nn.Parameter(torch.zeros(ctx, h))
            layer = nn.TransformerEncoderLayer(h, 4, 2 * h, dropout=0.1, batch_first=True)
            self.rnn = nn.TransformerEncoder(layer, layers)
        self.mu = Linear(h, d)        # predicted next window
        self.logvar = Linear(h, d)    # and the model's confidence, per feature
        self.tok = Linear(h, vocab)   # predicted next behaviour token
        self.stage = nn.Sequential(Linear(h + d, 64), nn.GELU(), Linear(64, len(STAGES)))

    def normalize(self, x):
        return ((x - self.mean) / self.std).clamp(-10, 10)

    def states(self, z):
        """Hidden state after each window. z: [B, T, d] normalized."""
        e = self.emb(z)
        if self.arch == "gru":
            return self.rnn(e)[0]
        out = torch.zeros_like(e)
        for i in range(0, e.shape[1], self.ctx):
            blk = e[:, i:i + self.ctx]
            n = blk.shape[1]
            mask = torch.triu(torch.full((n, n), float("-inf")), 1)
            out[:, i:i + n] = self.rnn(blk + self.pos[:n], mask=mask)
        return out

    def components(self, z, s, prev):
        """dx, ds, g, k for windows z with states s; `prev` is the state before each window."""
        dx, token = nearest(z, self.codebook)
        ds, _ = nearest(s, self.state_codebook)
        logvar = self.logvar(prev).clamp(-3, 3)  # floor on confidence keeps benign surprise light-tailed
        g = 0.5 * (logvar + (z - self.mu(prev)) ** 2 / logvar.exp()).sum(-1)
        k = -F.log_softmax(self.tok(prev), -1).gather(-1, token.unsqueeze(-1)).squeeze(-1)
        return torch.stack([dx, ds, g, k], -1)

    def surprise(self, comp):
        c = (comp - self.calib[:, 0]) / self.calib[:, 1]
        return c[..., 0] + c[..., 1] + 0.5 * (c[..., 2] + c[..., 3])

    def forward(self, x):
        """x: [B, T, d] raw windows of one source in time order -> components [B, T, 4], states."""
        z = self.normalize(x)
        s = self.states(z)
        prev = torch.cat([torch.zeros_like(s[:, :1]), s[:, :-1]], 1)
        return self.components(z, s, prev), s


def sequences(day, src, t):
    """Index arrays, one per (day, source), in time order."""
    order = np.lexsort((t, src, day))
    key = day[order].astype(np.int64) * (1 << 40) + src[order].astype(np.int64)
    return np.split(order, np.flatnonzero(np.diff(key)) + 1)


@torch.no_grad()
def score(model, X, seqs):
    """Run every sequence from a zero state. Returns components [n, 4] and states [n, h]."""
    model.eval()
    comp = np.zeros((len(X), 4), np.float32)
    S = np.zeros((len(X), model.h), np.float32)
    for idx in seqs:
        c, s = model(torch.from_numpy(X[idx])[None])
        comp[idx], S[idx] = c[0].numpy(), s[0].numpy()
    return comp, S


def ewma(v, seqs, a=EWMA):
    """Per-source exponential moving average of a score."""
    out = v.astype(np.float64).copy()
    for idx in seqs:
        acc = out[idx[0]]
        for i in idx:
            acc = a * out[i] + (1 - a) * acc
            out[i] = acc
    return out
