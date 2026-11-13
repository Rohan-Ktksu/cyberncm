"""R6d: alternative scoring functions on the 32 window features. Usage: python r6d_scores.py CKPT OUT.json SEED"""
import json, os, sys
import numpy as np, torch
from sklearn.cluster import MiniBatchKMeans
from sklearn.mixture import GaussianMixture
from ncm import NCM, ewma, score, sequences
import scoreboard as SB

CKPT, OUT, SEED = sys.argv[1], sys.argv[2], int(sys.argv[3])
torch.set_num_threads(int(os.environ.get("NCM_THREADS", 2))); torch.manual_seed(SEED)
d = SB.load("data/windows.npz"); d["fam"] = d["family"]; X, day, src, t = d["X"], d["day"], d["src"], d["t"]; names = d["names"]
ck = torch.load(CKPT); model = NCM(h=ck["h"], arch=ck["arch"]); model.load_state_dict(ck["state"], strict=False)
seqs = sequences(day, src, t); cal = (day == 0) & (t >= ck["cut"]); train = (day == 0) & (t < ck["cut"])
Z = model.normalize(torch.from_numpy(X)).numpy().astype(np.float32); Zt = torch.from_numpy(Z)
std = lambda v: (v - v[cal].mean()) / v[cal].std(); sm = lambda raw: ewma(std(raw), seqs)
rng = np.random.default_rng(SEED); tr = np.flatnonzero(train)
sub = lambda n: tr if len(tr) <= n else rng.choice(tr, n, replace=False)


def nearest(A, B, k=1, chunk=5000):
    out = np.empty(len(A), np.float32); bb = (B * B).sum(-1)
    for i in range(0, len(A), chunk):
        a = A[i:i + chunk]; d2 = ((a * a).sum(-1, keepdim=True) - 2 * a @ B.T + bb).clamp_min(1e-6)
        out[i:i + chunk] = d2.topk(k, dim=-1, largest=False).values.sqrt().mean(-1).numpy()
    return out


def centres(v):
    return torch.from_numpy(MiniBatchKMeans(v, n_init=3, random_state=SEED).fit(Z[sub(300000)]).cluster_centers_.astype(np.float32))


comp, _ = score(model, X, seqs); c = (comp - comp[cal].mean(0)) / comp[cal].std(0)
M = {"v0 NCM, smoothed": ewma(c[:, 0] + c[:, 1] + 0.5 * (c[:, 2] + c[:, 3]), seqs),
     "v0 without the surprise terms (token + state distance)": ewma(c[:, 0] + c[:, 1], seqs),
     "state distance only": ewma(c[:, 1], seqs), "token distance, 512 centres": ewma(c[:, 0], seqs)}
for v in (128, 2048): M[f"token distance, {v} centres"] = sm(nearest(Zt, centres(v)))
M["nearest-neighbour distance (5 nearest of 20,000 training windows)"] = sm(nearest(Zt, Zt[torch.from_numpy(sub(20000))], k=5))
gmm = GaussianMixture(16, covariance_type="diag", reg_covar=1e-3, random_state=SEED).fit(Z[sub(100000)].astype(np.float64)); M["Gaussian mixture (16 diagonal components)"] = sm(-gmm.score_samples(Z.astype(np.float64)))
ae = torch.nn.Sequential(torch.nn.Linear(32, 16), torch.nn.ReLU(), torch.nn.Linear(16, 8), torch.nn.ReLU(), torch.nn.Linear(8, 16), torch.nn.ReLU(), torch.nn.Linear(16, 32))
opt = torch.optim.Adam(ae.parameters(), 2e-3); xt = Zt[torch.from_numpy(sub(200000))]
for _ in range(5):
    for b in torch.randperm(len(xt)).split(512):
        opt.zero_grad(); ((ae(xt[b]) - xt[b]) ** 2).mean().backward(); opt.step()
with torch.no_grad(): err = np.concatenate([((ae(Zt[i:i + 200000]) - Zt[i:i + 200000]) ** 2).mean(-1).numpy() for i in range(0, len(Zt), 200000)])
M["autoencoder (32-16-8-16-32)"] = sm(err)
sps = {k: SB.Split(d, v) for k, v in d["splits"].items()}
res = {"seed": SEED, "splits": {k: [int(x) for x in v] for k, v in d["splits"].items()}, "models": {}}
for name, sc in M.items():
    thr = float(np.quantile(sc[cal], 0.99)); res["models"][name] = {k: SB.report(sp, sc, names, thr) for k, sp in sps.items()}
    print(name, {k: round(res["models"][name][k]["family_mean_auc"], 3) for k in sps}, flush=True)
json.dump(res, open(OUT, "w"), indent=1); print("wrote", OUT)
