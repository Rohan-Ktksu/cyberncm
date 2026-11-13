"""Export the streaming step to ONNX, quantize to INT8, check it against PyTorch and time it.

Usage: python export.py CHECKPOINT
The step is stateless: the caller keeps one hidden state per source and passes it back in.
  inputs   x [B, 32] raw window features, h [layers, B, H] state from the previous window
  outputs  surprise [B] (before smoothing), stage_probs [B, 6], token [B], next_token [B], h_out
"""
import os
import sys
import time
import numpy as np
import onnxruntime as ort
import torch
from onnxruntime.quantization import QuantType, quantize_dynamic
from sklearn.metrics import roc_auc_score
from ncm import NCM, ewma, nearest, score, sequences


class Step(torch.nn.Module):
    """One window for a batch of sources. The GRU is written as plain matmuls so INT8 quantization applies."""

    def __init__(self, m):
        super().__init__()
        self.m = m

    def forward(self, x, h):
        m = self.m
        z = m.normalize(x)
        prev, inp, hs = h[-1], m.emb(z), []
        for l in range(m.layers):
            gi = inp @ getattr(m.rnn, f"weight_ih_l{l}").T + getattr(m.rnn, f"bias_ih_l{l}")
            gh = h[l] @ getattr(m.rnn, f"weight_hh_l{l}").T + getattr(m.rnn, f"bias_hh_l{l}")
            (ir, iz, i_n), (hr, hz, hn) = gi.chunk(3, -1), gh.chunk(3, -1)
            r, u = torch.sigmoid(ir + hr), torch.sigmoid(iz + hz)
            inp = (1 - u) * torch.tanh(i_n + r * hn) + u * h[l]
            hs.append(inp)
        probs = torch.softmax(m.stage(torch.cat([inp, z], -1)), -1)
        return (m.surprise(m.components(z, inp, prev)), probs, nearest(z, m.codebook)[1],
                m.tok(inp).argmax(-1), torch.stack(hs))


def load(ckpt):
    ck = torch.load(ckpt)
    m = NCM(h=ck["h"], arch=ck["arch"])
    m.load_state_dict(ck["state"])
    return m.eval(), ck


def stream(sess, m, X, seqs):
    """Replay every source window by window through an ONNX session. Returns raw surprise per window."""
    out = np.zeros(len(X), np.float32)
    for idx in seqs:
        h = np.zeros((m.layers, 1, m.h), np.float32)
        for i in idx:
            s, _, _, _, h = sess.run(None, {"x": X[i:i + 1], "h": h})
            out[i] = s[0]
    return out


if __name__ == "__main__":
    ckpt = sys.argv[1]
    m, ck = load(ckpt)
    fp32, int8 = ckpt.replace(".pt", ".onnx"), ckpt.replace(".pt", ".int8.onnx")
    args = (torch.zeros(2, m.d), torch.zeros(m.layers, 2, m.h))
    torch.onnx.export(Step(m), args, fp32, input_names=["x", "h"], dynamo=False, opset_version=17,
                      output_names=["surprise", "stage_probs", "token", "next_token", "h_out"],
                      dynamic_axes={"x": {0: "B"}, "h": {1: "B"}})
    quantize_dynamic(fp32, int8, weight_type=QuantType.QInt8)

    z = np.load("data/windows.npz")
    X, day, src, t, fam = z["X"], z["day"], z["src"], z["t"], z["family"]
    seqs = sequences(day, src, t)
    opts = ort.SessionOptions()
    opts.intra_op_num_threads = 1  # single core, as on an edge box
    res = {}
    for name, path in (("FP32", fp32), ("INT8", int8)):
        sess = ort.InferenceSession(path, opts)
        raw = stream(sess, m, X, seqs)
        sm = ewma(raw, seqs)
        te = day > 0
        xb, hb = X[:64], np.zeros((m.layers, 64, m.h), np.float32)
        t0 = time.perf_counter()
        for _ in range(2000):
            sess.run(None, {"x": xb, "h": hb})
        res[name] = (raw, os.path.getsize(path) / 1024, roc_auc_score(fam[te] > 0, sm[te]),
                     (time.perf_counter() - t0) / 2000 * 1e3)
    with torch.no_grad():  # score() puts the model back in eval mode; ONNX export leaves it in train mode
        ref = m.surprise(torch.from_numpy(score(m, X, seqs)[0])).numpy()
    got = res["FP32"][0]
    print(f"ONNX FP32 vs PyTorch, max abs difference in surprise: {np.abs(ref - got).max():.5f}")
    print(f"parameters: {sum(p.numel() for p in m.parameters()):,}")
    for name, (raw, kb, auc, ms) in res.items():
        print(f"{name}: {kb:7.0f} KB   test AUC (smoothed surprise) {auc:.4f}   {ms:.3f} ms per batch of 64 windows, 1 thread")
    print(f"INT8 vs FP32 surprise correlation: {np.corrcoef(res['FP32'][0], res['INT8'][0])[0, 1]:.4f}")
