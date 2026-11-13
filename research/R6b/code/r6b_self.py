"""R6b: token distance on self-centred / self-scaled / hour-centred features. Usage: python r6b_self.py CKPT OUT.json SEED"""
import json, os, sys
import numpy as np, torch
from scipy.signal import lfilter
from sklearn.cluster import MiniBatchKMeans
from ncm import NCM, ewma, score, sequences
import scoreboard as SB

CKPT, OUT, SEED = sys.argv[1], sys.argv[2], int(sys.argv[3])
torch.set_num_threads(int(os.environ.get("NCM_THREADS", 2)))
d = SB.load("data/windows.npz"); d["fam"] = d["family"]; X, day, src, t, T = d["X"], d["day"], d["src"], d["t"], d["T"]; names = d["names"]
ck = torch.load(CKPT); model = NCM(h=ck["h"], arch=ck["arch"]); model.load_state_dict(ck["state"], strict=False)
seqs = sequences(day, src, t); cal = (day == 0) & (t >= ck["cut"]); train = (day == 0) & (t < ck["cut"])
Z = model.normalize(torch.from_numpy(X)).numpy().astype(np.float32)
std = lambda v: (v - v[cal].mean()) / v[cal].std(); sm = lambda raw: ewma(std(raw), seqs)
TAU, K0 = 720.0, 30.0; a = 1 - np.exp(-1 / TAU)


def self_baseline(Z):
    """Per source and day: causal running mean and variance of the source's earlier windows, shrunk toward (0, 1)."""
    M = np.zeros_like(Z); S = np.ones_like(Z)
    for idx in seqs:
        x = Z[idx].astype(np.float64); n = np.arange(len(idx))[:, None].astype(np.float64)  # earlier windows before each one
        m = lfilter([a], [1, -(1 - a)], x, axis=0, zi=((1 - a) * x[0])[None, :])[0]; v = lfilter([a], [1, -(1 - a)], (x - m) ** 2, axis=0, zi=np.ones((1, x.shape[1])) * 0)[0]
        mp = np.vstack([np.zeros((1, x.shape[1])), m[:-1]]); vp = np.vstack([np.ones((1, x.shape[1])), v[:-1]]); w = n / (n + K0)
        M[idx] = (w * mp).astype(np.float32); S[idx] = np.sqrt(np.maximum(w * vp + (1 - w), 0.25 ** 2)).astype(np.float32)
    return M, S


M_, S_ = self_baseline(Z)
tod = (T % 86400) // 3600 if "day_t0" in d else (t % 86400) // 3600
H = np.zeros((24, Z.shape[1]), np.float32)
for h in range(24):
    m = train & (tod == h)
    if m.sum() >= 500: H[h] = Z[m].mean(0)
hour = H[tod.astype(int)]
CAND = {"token distance, self-centred": Z - M_, "token distance, self-centred and self-scaled": (Z - M_) / S_,
        "token distance, hour-of-day centred": Z - hour, "token distance, self-centred and hour-of-day centred": Z - M_ - hour}
comp, _ = score(model, X, seqs); c = (comp - comp[cal].mean(0)) / comp[cal].std(0)
MOD = {"v0 NCM, smoothed": ewma(c[:, 0] + c[:, 1] + 0.5 * (c[:, 2] + c[:, 3]), seqs), "token distance, global": ewma(c[:, 0], seqs)}
rng = np.random.default_rng(SEED); tr = np.flatnonzero(train); tr = tr if len(tr) <= 300000 else rng.choice(tr, 300000, replace=False)
for name, F in CAND.items():
    F = np.clip(F, -10, 10).astype(np.float32); cen = torch.from_numpy(MiniBatchKMeans(512, n_init=3, random_state=SEED).fit(F[tr]).cluster_centers_.astype(np.float32))
    dist = np.empty(len(F), np.float32); cc = (cen * cen).sum(-1)
    for i in range(0, len(F), 100000):
        q = torch.from_numpy(F[i:i + 100000]); d2 = (q * q).sum(-1, keepdim=True) - 2 * q @ cen.T + cc; dist[i:i + 100000] = d2.clamp_min(1e-6).min(-1).values.sqrt().numpy()
    MOD[name] = sm(dist)
sps = {k: SB.Split(d, v) for k, v in d["splits"].items()}
res = {"seed": SEED, "splits": {k: [int(x) for x in v] for k, v in d["splits"].items()}, "models": {}}
for name, sc in MOD.items():
    thr = float(np.quantile(sc[cal], 0.99)); res["models"][name] = {k: SB.report(sp, sc, names, thr) for k, sp in sps.items()}
    print(name, {k: round(res["models"][name][k]["family_mean_auc"], 3) for k in sps}, flush=True)
json.dump(res, open(OUT, "w"), indent=1); print("wrote", OUT)
