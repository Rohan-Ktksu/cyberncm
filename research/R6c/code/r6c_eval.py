"""R6c scoring: token distance on keyed windows, evaluated like the scoreboard. Usage: python r6c_eval.py WINDOWS.npz PAIR_MAP.npz OUT.json SEED [LABEL]
Run from a folder with ncm/ code (ncm.py, scoreboard.py, metrics.py) on the path."""
import json, os, sys, tempfile
import numpy as np, torch
from sklearn.cluster import MiniBatchKMeans
from ncm import ewma, sequences
import scoreboard as SB

WIN, PM, OUT, SEED = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4]); LABEL = sys.argv[5] if len(sys.argv) > 5 else "keyed"
torch.set_num_threads(int(os.environ.get("NCM_THREADS", 2)))
z = {k: v for k, v in np.load(WIN, allow_pickle=True).items()}; pm = np.load(PM)
key = z["src"].copy(); z["src"] = pm["source"][key]           # source view: attackers and hosts are sources
tmp = tempfile.mktemp(suffix=".npz"); np.savez(tmp, **z); d = SB.load(tmp); os.remove(tmp)
d["fam"] = d["family"]; X, day, t = d["X"], d["day"], d["t"]; names = d["names"]
seqs = sequences(day, key, t)                                   # smoothing per key and day
mon = day == 0; cut = np.quantile(t[mon], 0.8); train, cal = mon & (t < cut), mon & (t >= cut)
Z = np.clip((X - X[train].mean(0)) / (X[train].std(0) + 1e-3), -10, 10).astype(np.float32)
rng = np.random.default_rng(SEED); tr = np.flatnonzero(train); tr = tr if len(tr) <= 300000 else rng.choice(tr, 300000, replace=False)
cen = torch.from_numpy(MiniBatchKMeans(512, n_init=3, random_state=SEED).fit(Z[tr]).cluster_centers_.astype(np.float32)); cc = (cen * cen).sum(-1)
dist = np.empty(len(Z), np.float32)
for i in range(0, len(Z), 100000):
    q = torch.from_numpy(Z[i:i + 100000]); d2 = (q * q).sum(-1, keepdim=True) - 2 * q @ cen.T + cc; dist[i:i + 100000] = d2.clamp_min(1e-6).min(-1).values.sqrt().numpy()
sc = ewma((dist - dist[cal].mean()) / dist[cal].std(), seqs)
sps = {k: SB.Split(d, v) for k, v in d["splits"].items()}; thr = float(np.quantile(sc[cal], 0.99)); name = f"token distance, per {LABEL}"
res = {"seed": SEED, "windows": int(len(X)), "keys": int(len(np.unique(key))), "splits": {k: [int(x) for x in v] for k, v in d["splits"].items()}, "models": {name: {k: SB.report(sp, sc, names, thr) for k, sp in sps.items()}}}
print(name, {k: round(res["models"][name][k]["family_mean_auc"], 3) for k in sps}, "windows", len(X), flush=True)
json.dump(res, open(OUT, "w"), indent=1)
