"""Feature drift and feature importance from the prepared windows (PLAN.md step 17). No trained model is used.

Usage: python features_drift.py DATA_DIR OUT.json     (DATA_DIR holds <dataset>/windows.npz)
"""
import itertools, json, sys
import numpy as np
from scipy.stats import ks_2samp
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import roc_auc_score

DD, OUT = sys.argv[1], sys.argv[2]
DS = ["cic2017", "unsw", "d2018", "unraveled", "cicapt"]
rng = np.random.default_rng(0)
sub = lambda a, n=50000: a if len(a) <= n else a[rng.choice(len(a), n, replace=False)]


def smd(a, b):
    s = np.sqrt((a.var(0) + b.var(0)) / 2)
    return np.abs(a.mean(0) - b.mean(0)) / np.where(s > 0, s, 1)


ks = lambda a, b: np.array([ks_2samp(a[:, j], b[:, j]).statistic for j in range(a.shape[1])])
res, base = {}, {}
for ds in DS:
    z = np.load(f"{DD}/{ds}/windows.npz", allow_pickle=True)
    X, day, fam = z["X"], z["day"], z["family"]; names = [str(n) for n in z["family_names"]]; feats = [str(f) for f in z["features"]]
    test_days = [int(d) for d in (np.argsort(z["day_t0"]) if "day_t0" in z.files else np.unique(day)) if d != 0 and (day == d).any()]
    final = test_days[len(test_days) // 2:]; dev = test_days[:len(test_days) // 2]
    ben = fam == 0; base[ds] = sub(X[ben & (day == 0)])
    r = {"features": feats, "days": {}}
    for d in test_days:  # drift of benign traffic against the training day
        b = X[ben & (day == d)]
        if len(b) >= 1000:
            b = sub(b); r["days"][str(d)] = {"ks": ks(base[ds], b).tolist(), "smd": smd(base[ds], b).tolist(), "n": int(len(b))}
    inf = np.isin(day, final); bf = sub(X[inf & ben], 100000); aucs = {}
    for f in np.unique(fam[inf & ~ben]):  # how well each single feature separates a family from benign, final split
        a = X[inf & (fam == f)]
        if len(a) >= 10:
            a = sub(a, 100000); y = np.r_[np.zeros(len(bf)), np.ones(len(a))]
            v = np.array([roc_auc_score(y, np.r_[bf[:, j], a[:, j]]) for j in range(X.shape[1])])
            aucs[names[f]] = np.maximum(v, 1 - v).tolist()
    r["single_feature_auc"] = aucs
    ind = np.isin(day, dev); bt, at = sub(X[ind & ben], 100000), sub(X[ind & ~ben], 100000)
    if len(at) >= 10:  # random forest, benign against any attack, dev split: impurity importance
        rf = RandomForestClassifier(n_estimators=50, n_jobs=1, class_weight="balanced", random_state=0)
        rf.fit(np.r_[bt, at], np.r_[np.zeros(len(bt)), np.ones(len(at))]); r["rf_importance_dev"] = rf.feature_importances_.tolist()
    res[ds] = r; print(ds, "done", flush=True)
res["between_networks"] = {f"{a}|{b}": {"ks": ks(base[a], base[b]).tolist(), "smd": smd(base[a], base[b]).tolist()} for a, b in itertools.combinations(DS, 2)}
json.dump(res, open(OUT, "w"))
print("wrote", OUT)
