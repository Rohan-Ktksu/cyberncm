"""Error analysis on the hard set (PLAN.md step 16). Run from the ncm/ folder of a dataset run directory.

Usage: python errors.py CHECKPOINT OUT.json "FAMILY SUBSTRING" ...
For each named family on the final split: the 20 lowest-scoring attack windows under the alert threshold ("misses"),
and, once per dataset, the 20 highest-scoring windows of benign sources over it ("false alarms", at most 3 per source).
Threshold: 99th percentile of v0's smoothed score on the benign calibration span (set without labels).
"""
import json, sys
import numpy as np, torch
from ncm import NCM, ewma, score, sequences
import scoreboard as SB

ckpt, out, pats = sys.argv[1], sys.argv[2], sys.argv[3:]
d = SB.load("data/windows.npz"); X, day, src, t, fam = d["X"], d["day"], d["src"], d["t"], d["family"]
names, feats = d["names"], [str(f) for f in d["features"]]
ck = torch.load(ckpt); model = NCM(h=ck["h"], arch=ck["arch"]); model.load_state_dict(ck["state"], strict=False)
seqs = sequences(day, src, t); comp, _ = score(model, X, seqs)
cal = (day == 0) & (t >= ck["cut"]); c = (comp - comp[cal].mean(0)) / comp[cal].std(0)
sc = ewma(c[:, 0] + c[:, 1] + 0.5 * (c[:, 2] + c[:, 3]), seqs); thr = float(np.quantile(sc[cal], 0.99))
Z = model.normalize(torch.from_numpy(X)).numpy()
fin = np.isin(day, d["splits"]["final"]); attackers = np.unique(src[fam > 0]); COMP = ["token distance", "state distance", "gaussian surprise", "token surprise"]
ip = lambda x: ".".join(str((int(x) >> s) & 255) for s in (24, 16, 8, 0))


def row(i):
    o = np.argsort(-np.abs(Z[i]))[:5]
    return {"src": ip(src[i]), "day": int(day[i]), "t": float(t[i]), "score": float(sc[i]), "components_z": [float(x) for x in c[i]],
            "features_beyond_2sd": int((np.abs(Z[i]) > 2).sum()), "top_features": [[feats[j], float(Z[i, j])] for j in o]}


def contrast(a, b):  # features whose mean (in benign-training standard deviations) differs most between two groups
    if not a.any() or not b.any(): return []
    dz = Z[a].mean(0) - Z[b].mean(0); o = np.argsort(-np.abs(dz))[:6]
    return [[feats[j], float(Z[a][:, j].mean()), float(Z[b][:, j].mean())] for j in o]


res = {"checkpoint": ckpt, "threshold": thr, "final_days": [int(x) for x in d["splits"]["final"]], "families": {}}
ben = fin & (fam == 0) & ~np.isin(src, attackers)
for pat in pats:
    for f in [i for i, n in enumerate(names) if i > 0 and pat.lower() in n.lower()]:
        m = fin & (fam == f)
        if not m.any(): continue
        miss, hit = m & (sc <= thr), m & (sc > thr); idx = np.flatnonzero(miss); idx = idx[np.argsort(sc[idx])][:20]
        res["families"][names[f]] = {"windows": int(m.sum()), "sources": int(len(np.unique(src[m]))), "missed_share": float(miss.mean() if False else miss.sum() / m.sum()),
            "missed_median_features_beyond_2sd": float(np.median((np.abs(Z[miss]) > 2).sum(1))) if miss.any() else None,
            "caught_median_features_beyond_2sd": float(np.median((np.abs(Z[hit]) > 2).sum(1))) if hit.any() else None,
            "benign_median_features_beyond_2sd": float(np.median((np.abs(Z[ben]) > 2).sum(1))),
            "missed_vs_caught": contrast(miss, hit), "missed_vs_benign": contrast(miss, ben), "misses": [row(i) for i in idx]}
fa = ben & (sc > thr); idx = np.flatnonzero(fa); idx = idx[np.argsort(-sc[idx])]; keep, per = [], {}
for i in idx:
    if per.get(src[i], 0) < 3: keep.append(i); per[src[i]] = per.get(src[i], 0) + 1
    if len(keep) == 20: break
u, n = np.unique(src[fa], return_counts=True); o = np.argsort(-n)[:5]
res["false_alarms"] = {"benign_windows": int(ben.sum()), "benign_sources": int(len(np.unique(src[ben]))), "flagged_share": float(fa.sum() / max(ben.sum(), 1)),
    "sources_with_a_flag": int(len(u)), "top_sources_share_of_flags": [[ip(u[j]), float(n[j] / n.sum())] for j in o],
    "largest_component": {COMP[k]: float((c[fa].argmax(1) == k).mean()) for k in range(4)} if fa.any() else {},
    "flagged_vs_unflagged_benign": contrast(fa, ben & ~fa), "examples": [row(i) for i in keep]}
json.dump(res, open(out, "w"), indent=1); print("wrote", out, {k: round(v["missed_share"], 3) for k, v in res["families"].items()}, "FA share", round(res["false_alarms"]["flagged_share"], 4))
