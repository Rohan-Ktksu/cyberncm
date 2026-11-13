"""R5: v0 trained on windows of one length. Usage (where `ncm.py` imports): python r5_eval.py CKPT WINDOWS OUT.json SEED WSEC
Measures family-mean AUC (dev and final, as the scoreboard) and time to first alert: the threshold is the 99.5th percentile of the day-0 calibration
windows (last 20% of day 0); for each attacking source (dev and final days separately), the time from its first attack window to its first window above the threshold."""
import json, os, sys
import numpy as np, torch
from sklearn.metrics import roc_auc_score
from ncm import NCM, ewma, score, sequences

CK, WIN, OUT, SEED, WSEC = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4]), float(sys.argv[5])
torch.set_num_threads(int(os.environ.get("NCM_THREADS", 2))); MIN_WIN = 10
z = np.load(WIN, allow_pickle=True); X, day, src, t, fam = z["X"].astype(np.float32), z["day"], z["src"], z["t"], z["family"]
c = torch.load(CK); m = NCM(h=c["h"], arch=c["arch"]); m.load_state_dict(c["state"], strict=False); m.eval()
seqs = sequences(day, src, t); _, S = score(m, X, seqs); prev = np.zeros_like(S)
for idx in seqs: prev[idx[1:]] = S[idx[:-1]]
with torch.no_grad():
    zz = m.normalize(torch.from_numpy(X)); comp = np.concatenate([m.components(zz[i:i + 200000], torch.from_numpy(S[i:i + 200000]), torch.from_numpy(prev[i:i + 200000])).numpy() for i in range(0, len(X), 200000)])
cc = (comp - m.calib[:, 0].numpy()) / m.calib[:, 1].numpy(); sc = ewma(cc[:, 0] + cc[:, 1] + 0.5 * (cc[:, 2] + cc[:, 3]), seqs)
present = sorted(set(np.unique(day).tolist()) - {0}); SPLITS = {"dev": present[:len(present) // 2], "final": present[len(present) // 2:]}
mon = day == 0; cal = mon & (t >= np.quantile(t[mon], 0.8)); thr = float(np.quantile(sc[cal], 0.995))
res = {"seed": SEED, "window_seconds": WSEC, "windows": int(len(X)), "attack_windows": int((fam > 0).sum()), "threshold": thr}
for sp, days in SPLITS.items():
    te = np.isin(day, days); ben = te & (fam == 0); aucs = []
    for f in range(1, int(fam.max()) + 1):
        pos = te & (fam == f)
        if pos.sum() >= MIN_WIN: aucs.append(roc_auc_score(np.r_[np.ones(pos.sum()), np.zeros(ben.sum())], np.r_[sc[pos], sc[ben]]))
    delays, never = [], 0
    for s in np.unique(src[te & (fam > 0)]):
        for d in days:
            rows = np.flatnonzero((src == s) & (day == d)); rows = rows[np.argsort(t[rows])]
            at = rows[fam[rows] > 0]
            if len(at) == 0: continue
            t0 = t[at[0]]; hit = rows[(t[rows] >= t0) & (sc[rows] > thr)]
            if len(hit): delays.append(float(t[hit[0]] - t0))
            else: never += 1
    res[sp] = {"family_mean_auc": float(np.mean(aucs)), "worst_family_auc": float(np.min(aucs)), "families": len(aucs), "attacker_days": len(delays) + never, "never_alerted": never,
               "median_seconds_to_first_alert": float(np.median(delays)) if delays else None, "p90_seconds_to_first_alert": float(np.percentile(delays, 90)) if delays else None}
    print(sp, res[sp], flush=True)
json.dump(res, open(OUT, "w"), indent=1)
