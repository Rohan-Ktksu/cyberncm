"""R7m: trimming as a mitigation for a poisoned learning period.
Usage: python r7m_trim.py CKPT WINDOWS OUT.json SEED FAMILIES(comma separated names or 'all-breached')"""
import json, os, sys
import numpy as np, torch
from sklearn.cluster import MiniBatchKMeans
from sklearn.metrics import roc_auc_score
from ncm import NCM, ewma, score, sequences

CKPT, WIN, OUT, SEED, FAMS = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4]), sys.argv[5].split(",")
torch.set_num_threads(int(os.environ.get("NCM_THREADS", 2))); MIN_WIN = 10
z = np.load(WIN, allow_pickle=True); X = z["X"].astype(np.float32); day, src, t, fam = z["day"], z["src"], z["t"], z["family"]
names = [str(n) for n in z["family_names"]]; ck = torch.load(CKPT)
present = sorted(set(np.unique(day).tolist()) - {0})
order = [int(x) for x in np.argsort(z["day_t0"]) if int(x) in present] if "day_t0" in z.files else present
FINAL = order[len(order) // 2:]; fin = np.isin(day, FINAL)
final_fams = [f for f in range(1, len(names)) if (fin & (fam == f)).sum() >= MIN_WIN]
test_fams = [names.index(n) for n in FAMS if n in names]
POISON = [0.0, 0.005, 0.02]; TRIM = [0.0, 0.01, 0.02, 0.05]; COARSE = 32
rng = np.random.default_rng(SEED); n0 = int((day == 0).sum())


def fresh():
    m = NCM(h=ck["h"], arch=ck["arch"]); m.load_state_dict(ck["state"], strict=False); m.eval(); return m


@torch.no_grad()
def comps(m, Xa, S, prev):
    zz = m.normalize(torch.from_numpy(Xa)); return np.concatenate([m.components(zz[i:i + 200000], torch.from_numpy(S[i:i + 200000]), torch.from_numpy(prev[i:i + 200000])).numpy() for i in range(0, len(Xa), 200000)])


def km(a, k):
    return torch.from_numpy(MiniBatchKMeans(int(min(k, max(2, len(a) // 2))), n_init=3, random_state=SEED).fit(a).cluster_centers_.astype(np.float32))


def refit_score(Xa, day_, src_, t_, q):
    """In-domain refit as in R11 level 3, optionally after trimming the most unusual q share of the day-0 windows."""
    mon = day_ == 0; cut = np.quantile(t_[mon], 0.8); cal = mon & (t_ >= cut); fit = mon & ~cal
    keep = np.ones(len(Xa), bool)
    if q > 0:
        mu0, sd0 = Xa[fit].mean(0), Xa[fit].std(0) + 1e-3
        a = ((Xa - mu0) / sd0).clip(-10, 10)
        c = km(a[fit], COARSE).numpy(); am = a[mon]
        d = np.concatenate([np.sqrt(np.maximum(((am[k:k + 20000, None, :] - c[None]) ** 2).sum(-1), 0).min(1)) for k in range(0, len(am), 20000)])
        idx = np.flatnonzero(mon); drop = idx[d >= np.quantile(d, 1 - q)]; keep[drop] = False
    fit_k, cal_k = fit & keep, cal & keep
    m = fresh(); m.mean.copy_(torch.from_numpy(Xa[fit_k].mean(0))); m.std.copy_(torch.from_numpy(Xa[fit_k].std(0) + 1e-3))
    seqs = sequences(day_, src_, t_); _, S = score(m, Xa, seqs); prev = np.zeros_like(S)
    for idx in seqs: prev[idx[1:]] = S[idx[:-1]]
    m.codebook.data = km(m.normalize(torch.from_numpy(Xa[fit_k])).numpy(), 512); m.state_codebook.data = km(S[fit_k], 512)
    c = comps(m, Xa, S, prev); cc = (c - c[cal_k].mean(0)) / c[cal_k].std(0)
    return ewma(cc[:, 0] + cc[:, 1] + 0.5 * (cc[:, 2] + cc[:, 3]), seqs), cal_k, int((~keep & mon).sum())


def measures(sc, thr, poisoned_rows, fam_):
    ok = np.ones(len(X), bool); ok[poisoned_rows] = False
    aucs = [roc_auc_score((fam_[fin & ok & ((fam_ == 0) | (fam_ == f))] == f), sc[fin & ok & ((fam_ == 0) | (fam_ == f))]) for f in final_fams]
    ben = fin & ok & (fam_ == 0)
    return {"final_family_mean_auc": float(np.mean(aucs)), "benign_false_share_final": float((sc[ben] > thr).mean()),
            "detection": {names[f]: float((sc[fin & ok & (fam_ == f)] > thr).mean()) for f in final_fams}}


res = {"seed": SEED, "runs": []}
jobs = [(None, 0.0)] + [(f, p) for f in test_fams for p in POISON if p > 0]
for f, p in jobs:
    npz = 0 if f is None else min(int(np.ceil(p * n0)), int(((day > 0) & (fam == f)).sum()) // 2)
    pick = rng.choice(np.flatnonzero((day > 0) & (fam == f)), npz, replace=False) if npz else np.array([], int)
    tp = rng.uniform(t[day == 0].min(), t[day == 0].max(), npz)
    Xa = np.concatenate([X, X[pick]]); day_ = np.concatenate([day, np.zeros(npz, day.dtype)]); src_ = np.concatenate([src, src[pick]]); t_ = np.concatenate([t, tp])
    for q in TRIM:
        sc, cal_k, ndrop = refit_score(Xa, day_, src_, t_, q); sc = sc[:len(X)]
        thr = float(np.quantile(sc[cal_k[:len(X)]], 0.99)); mm = measures(sc, thr, pick, fam)
        res["runs"].append({"family": None if f is None else names[f], "poison": p, "trim": q, "poison_windows": int(npz), "trimmed_windows": ndrop, **mm})
        print(names[f] if f is not None else "clean", p, q, ndrop, round(mm["final_family_mean_auc"], 3), round(mm["benign_false_share_final"], 4), None if f is None else round(mm["detection"][names[f]], 3), flush=True)
json.dump(res, open(OUT, "w"), indent=1); print("wrote", OUT)
