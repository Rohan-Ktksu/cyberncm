"""R6f: supervised gradient-boosted head on window + history features, fair protocol, final split. Usage: python r6f_gbt.py CKPT OUT.json SEED"""
import json, os, sys
import numpy as np, torch
from scipy.signal import lfilter
from sklearn.ensemble import HistGradientBoostingClassifier
from sklearn.metrics import roc_auc_score
from ncm import NCM, ewma, score, sequences
import scoreboard as SB

CKPT, OUT, SEED = sys.argv[1], sys.argv[2], int(sys.argv[3])
torch.set_num_threads(int(os.environ.get("NCM_THREADS", 2)))
d = SB.load("data/windows.npz"); d["fam"] = d["family"]; X, day, src, t, fam = d["X"], d["day"], d["src"], d["t"], d["fam"]; names = d["names"]
ck = torch.load(CKPT); model = NCM(h=ck["h"], arch=ck["arch"]); model.load_state_dict(ck["state"], strict=False)
seqs = sequences(day, src, t); cal = (day == 0) & (t >= ck["cut"])
Z = model.normalize(torch.from_numpy(X)).numpy().astype(np.float32)


def averages(Z, taus=(12, 120, 720)):
    out = [Z]
    for tau in taus:
        a = 1 - np.exp(-1 / tau); H = np.empty_like(Z)
        for idx in seqs:
            x = Z[idx]; H[idx] = lfilter([a], [1, -(1 - a)], x, axis=0, zi=((1 - a) * x[0])[None, :].astype(np.float64))[0]
        out.append(H)
    return np.concatenate(out, axis=1)


F1 = averages(Z)
comp, _ = score(model, X, seqs); c = (comp - comp[cal].mean(0)) / comp[cal].std(0)
v0 = ewma(c[:, 0] + c[:, 1] + 0.5 * (c[:, 2] + c[:, 3]), seqs)
F2 = np.hstack([F1, v0[:, None].astype(np.float32)])
fin_days, dev_days = d["splits"]["final"], d["splits"]["dev"]
fin = np.isin(day, fin_days); seqs_f = [q for q in seqs if fin[q[0]]]; sp = SB.Split(d, fin_days); fi = np.flatnonzero(fin)
rng = np.random.default_rng(SEED); ben = np.flatnonzero(day == 0); ben = ben if len(ben) <= 100000 else rng.choice(ben, 100000, replace=False)
dev_atk = np.flatnonzero(np.isin(day, dev_days) & (fam > 0))
CAND = {"GBT on window + history": F1, "GBT on window + history + v0 score": F2}
res = {"seed": SEED, "models": {n: {"final": {"per_family_auc": {}}} for n in CAND}}
for f in sp.fams:
    pos = dev_atk[fam[dev_atk] != f]
    if len(pos) < 10:
        for n in CAND: res["models"][n]["final"]["per_family_auc"][names[f]] = None
        continue
    pos = pos if len(pos) <= 50000 else rng.choice(pos, 50000, replace=False); tr = np.r_[ben, pos]; y = np.r_[np.zeros(len(ben)), np.ones(len(pos))]
    for n, F in CAND.items():
        clf = HistGradientBoostingClassifier(max_iter=100, learning_rate=0.1, max_leaf_nodes=31, class_weight="balanced", random_state=SEED).fit(F[tr], y)
        P = np.zeros(len(X)); P[fi] = clf.predict_proba(F[fi])[:, 1]; s = ewma(P, seqs_f); m = (sp.fam == 0) | (sp.fam == f)
        res["models"][n]["final"]["per_family_auc"][names[f]] = float(roc_auc_score(sp.fam[m] == f, s[sp.idx][m]))
    print("held out", names[f], {n: round(res["models"][n]["final"]["per_family_auc"][names[f]], 3) for n in CAND}, flush=True)
for n in CAND:
    v = np.array([x for x in res["models"][n]["final"]["per_family_auc"].values() if x is not None])
    res["models"][n]["final"].update({"family_mean_auc": float(v.mean()) if len(v) else None, "worst_family_auc": float(v.min()) if len(v) else None, "n_families": int(len(v))})
    print(n, "family-mean AUC", None if not len(v) else round(float(v.mean()), 3), flush=True)
json.dump(res, open(OUT, "w"), indent=1)
