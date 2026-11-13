"""R6a: history-only score (no GRU) and v0 + history, evaluated like the scoreboard. Usage: python r6a_history.py CKPT OUT.json SEED"""
import json, os, sys
import numpy as np, torch
from scipy.signal import lfilter
from sklearn.cluster import MiniBatchKMeans
from ncm import NCM, ewma, score, sequences
import scoreboard as SB

CKPT, OUT, SEED = sys.argv[1], sys.argv[2], int(sys.argv[3])
torch.set_num_threads(int(os.environ.get("NCM_THREADS", 2)))
d = SB.load("data/windows.npz"); X, day, src, t = d["X"], d["day"], d["src"], d["t"]; names = d["names"]; d["fam"] = d["family"]
ck = torch.load(CKPT); model = NCM(h=ck["h"], arch=ck["arch"]); model.load_state_dict(ck["state"], strict=False)
seqs = sequences(day, src, t); cal = (day == 0) & (t >= ck["cut"]); train = (day == 0) & (t < ck["cut"])
Z = model.normalize(torch.from_numpy(X)).numpy().astype(np.float32)


def averages(Z, taus=(12, 120, 720)):
    out = [Z]
    for tau in taus:
        a = 1 - np.exp(-1 / tau); H = np.empty_like(Z)
        for idx in seqs:
            x = Z[idx]; H[idx] = lfilter([a], [1, -(1 - a)], x, axis=0, zi=((1 - a) * x[0])[None, :].astype(np.float64))[0]
        out.append(H)
    return np.concatenate(out, axis=1)


Zh = averages(Z)
rng = np.random.default_rng(SEED); tr = np.flatnonzero(train); tr = tr if len(tr) <= 300000 else rng.choice(tr, 300000, replace=False)
centres = torch.from_numpy(MiniBatchKMeans(512, n_init=3, random_state=SEED).fit(Zh[tr]).cluster_centers_.astype(np.float32))
dist = np.empty(len(Zh), np.float32); cc = (centres * centres).sum(-1)
for i in range(0, len(Zh), 100000):
    a = torch.from_numpy(Zh[i:i + 100000]); d2 = (a * a).sum(-1, keepdim=True) - 2 * a @ centres.T + cc
    dist[i:i + 100000] = d2.clamp_min(1e-6).min(-1).values.sqrt().numpy()
std = lambda v: (v - v[cal].mean()) / v[cal].std()
hist = ewma(std(dist), seqs)
comp, _ = score(model, X, seqs); c = (comp - comp[cal].mean(0)) / comp[cal].std(0)
v0 = ewma(c[:, 0] + c[:, 1] + 0.5 * (c[:, 2] + c[:, 3]), seqs)
MODELS = {"v0 NCM, smoothed": v0, "history only (no GRU): window + 1 min, 10 min, 1 h averages": hist, "v0 + history": std(v0) + std(hist)}
sps = {k: SB.Split(d, v) for k, v in d["splits"].items()}
res = {"seed": SEED, "splits": {k: [int(x) for x in v] for k, v in d["splits"].items()}, "models": {}}
for name, sc in MODELS.items():
    thr = float(np.quantile(sc[cal], 0.99)); res["models"][name] = {k: SB.report(sp, sc, names, thr) for k, sp in sps.items()}
    print(name, {k: round(res["models"][name][k]["family_mean_auc"], 3) for k in sps}, flush=True)
json.dump(res, open(OUT, "w"), indent=1); print("wrote", OUT)
