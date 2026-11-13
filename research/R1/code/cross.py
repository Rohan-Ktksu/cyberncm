"""R1 cross-dataset test: train on dataset A, test on dataset B, no retuning.

Usage: python cross.py CKPT_A WINDOWS_A WINDOWS_B OUT_PREFIX

Everything comes from A: the backbone, its feature normalization, both codebooks, the component calibration,
the isolation forest, the stage head and the random forest. B is only scored.

Thresholds are reported two ways:
  source     quantiles of A's calibration windows (strict transfer, nothing seen from B)
  target-cal quantiles of B's day-0 calibration windows (last 20% of the benign day; no labels and no training,
             only the alarm threshold moves - HANDOFF finding 4 says thresholds must be recalibrated per network)

Part X1  unsupervised, every B attack unseen (same scores as evaluate.py Part 1).
Part X2  supervised transfer: stage head / random forest fitted on all of A's labelled windows, AUC of
         attack-vs-benign on B. Family sets differ between datasets, so this is attack-vs-benign, not per-stage.
"""
import json
import sys
import numpy as np
import pandas as pd
import torch
import torch.nn.functional as F
from sklearn.ensemble import IsolationForest, RandomForestClassifier
from sklearn.metrics import roc_auc_score
from ncm import NCM, STAGES, ewma, score, sequences, stage_of


def fit_head(feats, y, epochs=300):
    """Same stage head as evaluate.py (copied: importing evaluate.py runs the whole evaluation)."""
    head = torch.nn.Sequential(torch.nn.Linear(feats.shape[1], 64), torch.nn.GELU(), torch.nn.Linear(64, len(STAGES)))
    w = torch.tensor([len(y) / (len(STAGES) * max((y == k).sum(), 1)) for k in range(len(STAGES))], dtype=torch.float32)
    xb, yb = torch.from_numpy(feats), torch.from_numpy(y)
    opt = torch.optim.AdamW(head.parameters(), 3e-3, weight_decay=1e-2)
    for _ in range(epochs):
        opt.zero_grad()
        F.cross_entropy(head(xb), yb, weight=w).backward()
        opt.step()
    return head.eval()


def hazard(head, feats):
    with torch.no_grad():
        return 1 - F.softmax(head(torch.from_numpy(feats)), -1)[:, 0].numpy()


torch.manual_seed(0)
np.random.seed(0)
torch.set_num_threads(4)
CKPT, WA, WB, OUT = sys.argv[1:5]

ck = torch.load(CKPT)
model = NCM(h=ck["h"], arch=ck["arch"])
model.load_state_dict(ck["state"], strict=False)


def load(path):
    z = np.load(path)
    names = list(z["family_names"])
    d = {k: z[k] for k in ["X", "day", "src", "t", "family"]}
    d["names"], d["stage"] = names, np.array([stage_of(names[f]) for f in z["family"]])
    d["seqs"] = sequences(d["day"], d["src"], d["t"])
    d["comp"], d["S"] = score(model, d["X"], d["seqs"])
    d["Zn"] = model.normalize(torch.from_numpy(d["X"])).numpy()
    mon = d["day"] == 0
    d["cal"] = mon & (d["t"] >= np.quantile(d["t"][mon], 0.8))
    return d


A, B = load(WA), load(WB)
a_train = (A["day"] == 0) & ~A["cal"]
mu, sd = A["comp"][A["cal"]].mean(0), A["comp"][A["cal"]].std(0)
iforest = IsolationForest(n_estimators=200, random_state=0).fit(A["Zn"][a_train])


def scores(d):
    c = (d["comp"] - mu) / sd
    f = -iforest.score_samples(d["Zn"])
    return {"baseline: isolation forest, smoothed": ewma(f, d["seqs"]),
            "token distance only, smoothed": ewma(c[:, 0], d["seqs"]),
            "next-context surprise only, smoothed": ewma(0.5 * (c[:, 2] + c[:, 3]), d["seqs"]),
            "NCM (all three signals), smoothed": ewma(c[:, 0] + c[:, 1] + 0.5 * (c[:, 2] + c[:, 3]), d["seqs"])}


SA, SB = scores(A), scores(B)
SPLITS = {"dev": (1, 2), "final": (3, 4)}
day, fam = B["day"], B["family"]


def fams_in(days):
    return [f for f in range(1, len(B["names"])) if (np.isin(day, days) & (fam == f)).sum() >= 10]


def fam_auc(sc, f, days):
    m = np.isin(day, days) & ((fam == 0) | (fam == f))
    return roc_auc_score(fam[m] == f, sc[m])


def report(name):
    sb, out = SB[name], {}
    for sp, days in SPLITS.items():
        te = np.isin(day, days)
        ben, atk = te & (fam == 0), te & (fam > 0)
        aucs = [fam_auc(sb, f, days) for f in fams_in(days)]
        out[f"{sp} AUC"] = roc_auc_score(atk[te], sb[te])
        out[f"{sp} family-mean AUC"] = np.mean(aucs)
        out[f"{sp} worst family"] = np.min(aucs)
        for tag, thr in (("source", np.quantile(SA[name][A["cal"]], 0.99)), ("target-cal", np.quantile(sb[B["cal"]], 0.99))):
            out[f"{sp} detect@1% {tag}"] = (sb[atk] > thr).mean()
            out[f"{sp} false@1% {tag}"] = (sb[ben] > thr).mean()
    return out


pd.set_option("display.width", 250)
print(f"train {WA} ({CKPT}) -> test {WB}: {(fam[day > 0] == 0).sum()} benign, {(fam > 0).sum()} attack test windows\n")
print("PART X1 - unsupervised transfer. Thresholds at 1%: 'source' from A's calibration, 'target-cal' from B's benign day 0.")
x1 = pd.DataFrame({n: report(n) for n in SB}).T
print(x1.round(3).to_string(), "\n")

ff = fams_in(SPLITS["final"])
per_fam = pd.DataFrame({n: {B["names"][f]: fam_auc(SB[n], f, SPLITS["final"]) for f in ff} for n in SB})
per_fam.insert(0, "windows", [(np.isin(day, SPLITS["final"]) & (fam == f)).sum() for f in ff])
print("AUC per attack family on B, final split (days 3-4)")
print(per_fam.round(3).to_string(), "\n")

# ---------- Part X2: supervised transfer ----------
a_test = A["day"] > 0
a_ben_tr = a_test & (A["family"] == 0) & ((A["t"] // 1800).astype(int) % 2 == 0)
a_fit = a_ben_tr | (a_test & (A["family"] > 0))
featsA, featsB = np.hstack([A["S"], A["Zn"]]).astype(np.float32), np.hstack([B["S"], B["Zn"]]).astype(np.float32)
head = fit_head(featsA[a_fit], A["stage"][a_fit])
head0 = fit_head(A["Zn"][a_fit], A["stage"][a_fit])
rf = RandomForestClassifier(n_estimators=200, n_jobs=2, class_weight="balanced", random_state=0)
rf.fit(A["X"][a_fit], A["stage"][a_fit] > 0)
sA = SA["NCM (all three signals), smoothed"]
q50, q999 = np.quantile(sA[A["cal"]], [0.5, 0.999])


def risk(d, s, feats):
    H = ewma(hazard(head, feats), d["seqs"])
    return H, 0.5 * np.clip((s - q50) / (q999 - q50), 0, 1) + 0.5 * H


HA, RA = risk(A, sA, featsA)
HB, RB = risk(B, SB["NCM (all three signals), smoothed"], featsB)
sup = {"RF single-window, smoothed": (None, ewma(rf.predict_proba(B["X"])[:, 1], B["seqs"])),
       "head without state": (None, ewma(hazard(head0, B["Zn"]), B["seqs"])),
       "NCM hazard H": (None, HB), "NCM risk R": (RA, RB)}
rows = {}
for name, (sa, sb) in sup.items():
    r = {}
    for sp, days in SPLITS.items():
        te = np.isin(day, days)
        aucs = [fam_auc(sb, f, days) for f in fams_in(days)]
        r[f"{sp} AUC"] = roc_auc_score(fam[te] > 0, sb[te])
        r[f"{sp} family-mean AUC"] = np.mean(aucs)
        r[f"{sp} worst family"] = np.min(aucs)
        if sa is not None:
            for tag, thr in (("source", np.quantile(sa[A["cal"]], 0.99)), ("target-cal", np.quantile(sb[B["cal"]], 0.99))):
                r[f"{sp} detect@1% {tag}"] = (sb[te & (fam > 0)] > thr).mean()
                r[f"{sp} false@1% {tag}"] = (sb[te & (fam == 0)] > thr).mean()
    rows[name] = r
x2 = pd.DataFrame(rows).T
print("PART X2 - supervised transfer: fitted on all of A's labelled windows, attack-vs-benign on B")
print(x2.round(3).to_string(), "\n")
json.dump({"unsupervised": x1.to_dict(), "per_family_final": per_fam.to_dict(), "supervised": x2.to_dict()},
          open(OUT + "_results.json", "w"), indent=1, default=float)
