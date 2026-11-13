"""Evaluate NCM on Tue-Fri. Usage: python evaluate.py CHECKPOINT [--quick]

Design choices were made on the dev days (Tue, Wed). Thu and Fri are the final test.

Part 1  Unsupervised. The model never saw any attack, so every family is a zero-day.
Part 2  Stage head, leave-one-out: trained without one family (or one whole kill-chain stage), tested
        on it, against a random forest on single-window features under the same split. (--quick skips)
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

torch.manual_seed(0)
np.random.seed(0)
torch.set_num_threads(4)
CKPT = sys.argv[1]
QUICK = "--quick" in sys.argv

z = np.load("data/windows.npz")
X, day, src, t, fam = z["X"], z["day"], z["src"], z["t"], z["family"]
names = list(z["family_names"])
stage = np.array([stage_of(names[f]) for f in fam])
ck = torch.load(CKPT)
model = NCM(h=ck["h"], arch=ck["arch"])
model.load_state_dict(ck["state"], strict=False)  # stage head may be absent before first evaluation

seqs = sequences(day, src, t)
comp, S = score(model, X, seqs)
mon = day == 0
train, cal = mon & (t < ck["cut"]), mon & (t >= ck["cut"])
Zn = model.normalize(torch.from_numpy(X)).numpy()
c = (comp - comp[cal].mean(0)) / comp[cal].std(0)
iforest = -IsolationForest(n_estimators=200, random_state=0).fit(Zn[train]).score_samples(Zn)
surp = ewma(c[:, 0] + c[:, 1] + 0.5 * (c[:, 2] + c[:, 3]), seqs)
scores = {
    "baseline: isolation forest": iforest,
    "baseline: isolation forest, smoothed": ewma(iforest, seqs),
    "token distance only, smoothed": ewma(c[:, 0], seqs),
    "next-context surprise only, smoothed": ewma(0.5 * (c[:, 2] + c[:, 3]), seqs),
    "NCM (all three signals), raw": c[:, 0] + c[:, 1] + 0.5 * (c[:, 2] + c[:, 3]),
    "NCM (all three signals), smoothed": surp,
}
SPLITS = {"dev": (1, 2), "final": (3, 4)}
fams = [f for f in range(1, len(names)) if (fam == f).any()]


def fam_auc(sc, f, days):
    m = np.isin(day, days) & ((fam == 0) | (fam == f))  # the family vs benign windows of the same split
    return roc_auc_score(fam[m] == f, sc[m])


def fams_in(days):
    # R1: UNSW families span several days, so a family counts in every split where it has >= 10 windows
    return [f for f in fams if (np.isin(day, days) & (fam == f)).sum() >= 10]


def report(sc):
    out = {}
    for sp, days in SPLITS.items():
        te = np.isin(day, days)
        ben, atk = te & (fam == 0), te & (fam > 0)
        aucs = [fam_auc(sc, f, days) for f in fams_in(days)]
        out[f"{sp} AUC"] = roc_auc_score(atk[te], sc[te])
        out[f"{sp} family-mean AUC"] = np.mean(aucs)
        out[f"{sp} worst family"] = np.min(aucs)
        for q, tag in ((0.99, "1%"), (0.999, "0.1%")):
            thr = np.quantile(sc[cal], q)
            out[f"{sp} detect@{tag}"] = (sc[atk] > thr).mean()
            out[f"{sp} false@{tag}"] = (sc[ben] > thr).mean()
    return out


pd.set_option("display.width", 250)
print(f"{CKPT}: {(fam[day > 0] == 0).sum()} benign and {(fam > 0).sum()} attack test windows\n")
print("PART 1 - unsupervised, every attack unseen. Thresholds set on Monday benign calibration data.")
overall = pd.DataFrame({n: report(s) for n, s in scores.items()}).T
print(overall.round(3).to_string(), "\n")

cols = ["baseline: isolation forest, smoothed", "token distance only, smoothed", "NCM (all three signals), smoothed"]
ff = fams_in(SPLITS["final"])
per_fam = pd.DataFrame({n: {names[f]: fam_auc(scores[n], f, SPLITS["final"]) for f in ff} for n in cols})
per_fam.insert(0, "windows", [(np.isin(day, SPLITS["final"]) & (fam == f)).sum() for f in ff])
print("AUC per attack family, final split (days 3-4)")
print(per_fam.round(3).to_string(), "\n")

thr = np.quantile(surp[cal], 0.99)
rows = []
for idx in seqs:
    for f in np.unique(fam[idx][fam[idx] > 0]):
        run = idx[fam[idx] == f]
        hit = np.flatnonzero(surp[run] > thr)
        rows.append({"family": names[f], "first_alert": hit[0] + 1 if len(hit) else np.nan})
ttd = pd.DataFrame(rows).groupby("family").agg(
    sources=("first_alert", "size"), detected=("first_alert", lambda s: s.notna().mean()),
    median_windows_to_alert=("first_alert", "median"))
print("Windows (5 s each) from an attacking source's first attack window to its first alert, 1% threshold")
print(ttd.round(2).to_string(), "\n")
results = {"overall": overall.to_dict(), "per_family": per_fam.to_dict(), "time_to_alert": ttd.to_dict()}


# ---------- Part 2: stage head, leave-one-out ----------
def fit_head(feats, y, epochs=300):
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


test = day > 0
ben, atk = test & (fam == 0), test & (fam > 0)
block = (t // 1800).astype(int) % 2  # alternate 30-minute blocks: benign train / benign test
ben_tr, ben_te = ben & (block == 0), ben & (block == 1)
feats = np.hstack([S, Zn]).astype(np.float32)
q50, q999 = np.quantile(surp[cal], [0.5, 0.999])
surp01 = np.clip((surp - q50) / (q999 - q50), 0, 1)


def leave_out(groups):
    rows = {}
    for name, held in groups.items():
        tr, te = ben_tr | (atk & ~held), ben_te | held
        H = ewma(hazard(fit_head(feats[tr], stage[tr]), feats), seqs)
        rf = RandomForestClassifier(n_estimators=200, n_jobs=2, class_weight="balanced", random_state=0)
        P = ewma(rf.fit(X[tr], stage[tr] > 0).predict_proba(X)[:, 1], seqs)
        H0 = ewma(hazard(fit_head(Zn[tr], stage[tr]), Zn), seqs)  # ablation: same head without the state
        R = 0.5 * surp01 + 0.5 * H
        thr = np.quantile(R[cal], 0.99)
        rows[name] = {"windows": held.sum(), "RF single-window, smoothed": roc_auc_score(held[te], P[te]),
                      "head without state": roc_auc_score(held[te], H0[te]),
                      "NCM hazard H": roc_auc_score(held[te], H[te]), "NCM surprise S": roc_auc_score(held[te], surp[te]),
                      "NCM risk R": roc_auc_score(held[te], R[te]),
                      "R detect@1%": (R[held] > thr).mean(), "R false@1%": (R[ben_te] > thr).mean()}
    df = pd.DataFrame(rows).T
    df.loc["MEAN"] = df.mean()
    return df


if not QUICK:
    print("PART 2 - stage head trained WITHOUT the listed family, AUC on that family")
    lofo = leave_out({names[f]: fam == f for f in fams})
    print(lofo.round(3).to_string(), "\n")
    print("PART 2b - stage head trained WITHOUT a whole kill-chain stage")
    loso = leave_out({STAGES[s]: atk & (stage == s) for s in range(1, len(STAGES)) if (atk & (stage == s)).any()})
    print(loso.round(3).to_string(), "\n")
    results |= {"leave_family_out": lofo.to_dict(), "leave_stage_out": loso.to_dict()}

    # final head on every family; thresholds for the streaming prototype
    model.stage.load_state_dict(fit_head(feats[ben_tr | atk], stage[ben_tr | atk]).state_dict())
    R = 0.5 * surp01 + 0.5 * ewma(hazard(model.stage, feats), seqs)
    ck["state"] = model.state_dict()
    ck["thresholds"] = {"q50": float(q50), "q999": float(q999), "r_limit": float(np.quantile(R[cal], 0.99)),
                        "r_block": float(np.quantile(R[cal], 0.999))}
    torch.save(ck, CKPT)
json.dump(results, open(CKPT.replace(".pt", "_results.json"), "w"), indent=1, default=float)
