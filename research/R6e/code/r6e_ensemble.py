"""R6e seed ensemble. Usage (cwd where ncm.py imports): python r6e_ensemble.py DATASET WINDOWS_NPZ CKPT_DIR OUT.json
Scores every window with the 5 scoreboard v0 checkpoints (seeds 0 to 4), averages the five smoothed scores (each is standardised on its own calibration span),
and reports family-mean AUC on dev and final for the full 5-model ensemble and for the 5 leave-one-out ensembles of 4 (their min to max is the ensemble's 'seed range')."""
import json, os, sys
import numpy as np, torch
from sklearn.metrics import roc_auc_score
from ncm import NCM, ewma, score, sequences

DS, WIN, CKD, OUT = sys.argv[1:5]; MIN_WIN = 10; torch.set_num_threads(int(os.environ.get("NCM_THREADS", 2)))
z = np.load(WIN, allow_pickle=True); X, day, src, t, fam = z["X"].astype(np.float32), z["day"], z["src"], z["t"], z["family"]
present = sorted(set(np.unique(day).tolist()) - {0}); order = [int(x) for x in np.argsort(z["day_t0"]) if int(x) in present] if "day_t0" in z.files else present
SPL = {"dev": order[:len(order) // 2], "final": order[len(order) // 2:]}; seqs = sequences(day, src, t)


def v0(ck):
    c = torch.load(ck); m = NCM(h=c["h"], arch=c["arch"]); m.load_state_dict(c["state"], strict=False); m.eval(); _, S = score(m, X, seqs); prev = np.zeros_like(S)
    for idx in seqs: prev[idx[1:]] = S[idx[:-1]]
    with torch.no_grad():
        zz = m.normalize(torch.from_numpy(X)); comp = np.concatenate([m.components(zz[i:i + 200000], torch.from_numpy(S[i:i + 200000]), torch.from_numpy(prev[i:i + 200000])).numpy() for i in range(0, len(X), 200000)])
    cc = (comp - m.calib[:, 0].numpy()) / m.calib[:, 1].numpy(); return ewma(cc[:, 0] + cc[:, 1] + 0.5 * (cc[:, 2] + cc[:, 3]), seqs)


def fam_auc(sc, days):
    te = np.isin(day, days); ben = te & (fam == 0); a = []
    for f in range(1, int(fam.max()) + 1):
        pos = te & (fam == f)
        if pos.sum() >= MIN_WIN: a.append(roc_auc_score(np.r_[np.ones(pos.sum()), np.zeros(ben.sum())], np.r_[sc[pos], sc[ben]]))
    return float(np.mean(a))


S5 = [v0(os.path.join(CKD, f"{DS}_s{s}.pt")) for s in range(5)]
res = {"dataset": DS, "single": {sp: [fam_auc(s, d) for s in S5] for sp, d in SPL.items()}, "ensemble5": {sp: fam_auc(np.mean(S5, 0), d) for sp, d in SPL.items()},
       "leave_one_out": {sp: [fam_auc(np.mean([S5[j] for j in range(5) if j != i], 0), d) for i in range(5)] for sp, d in SPL.items()}}
print(json.dumps(res)); json.dump(res, open(OUT, "w"), indent=1)
