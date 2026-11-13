"""Independent check of the headline v0 numbers, written without the scoreboard harness.

For each dataset and seed it loads the shared v0 checkpoint and windows, scores every window with v0 (token distance + state distance
+ half of the two surprise terms, each standardised with the checkpoint's own calibration, smoothed per source with the EWMA from ncm.py),
and computes the family-mean AUC on the dev and final days: for every attack family with at least 10 windows in the split, the AUC of that
family's windows against all benign windows of the split, averaged over families. It compares the result with
  1. the per-seed value the scoreboard run stored (<data>/scoreboard/<dataset>_s<seed>.json), expected to match to 3 decimals, and
  2. the committed range in research/scoreboard.csv (min to max over 5 seeds), which a rerun from scratch must fall inside.
Usage: python check_headlines.py --repo <repo root> --data <cyberncm-data folder> [--datasets cic2017,unsw,d2018] [--seeds 0,1,2]
"""
import argparse, json, os, sys
import numpy as np
import pandas as pd
import torch
from sklearn.metrics import roc_auc_score

ap = argparse.ArgumentParser()
ap.add_argument("--repo", required=True); ap.add_argument("--data", required=True)
ap.add_argument("--datasets", default="cic2017,unsw,d2018"); ap.add_argument("--seeds", default="0,1,2")
ap.add_argument("--ckpt-dir", default=None, help="folder with <dataset>_s<seed>.pt (default <data>/scoreboard/ckpt); use it to check checkpoints you retrained yourself")
a = ap.parse_args()
sys.path.insert(0, os.path.join(a.repo, "ncm"))
from ncm import NCM, ewma, score, sequences   # noqa: E402

torch.set_num_threads(int(os.environ.get("NCM_THREADS", 4))); MIN_WIN = 10
csv = pd.read_csv(os.path.join(a.repo, "research", "scoreboard.csv"))
ckdir = a.ckpt_dir or os.path.join(a.data, "scoreboard", "ckpt")


def v0_scores(ckpt, z):
    c = torch.load(ckpt); m = NCM(h=c["h"], arch=c["arch"]); m.load_state_dict(c["state"], strict=False); m.eval()
    X = z["X"].astype(np.float32); seqs = sequences(z["day"], z["src"], z["t"]); _, S = score(m, X, seqs)
    prev = np.zeros_like(S)
    for idx in seqs: prev[idx[1:]] = S[idx[:-1]]
    with torch.no_grad():
        zz = m.normalize(torch.from_numpy(X))
        comp = np.concatenate([m.components(zz[i:i + 200000], torch.from_numpy(S[i:i + 200000]), torch.from_numpy(prev[i:i + 200000])).numpy() for i in range(0, len(X), 200000)])
    cc = (comp - m.calib[:, 0].numpy()) / m.calib[:, 1].numpy()
    return ewma(cc[:, 0] + cc[:, 1] + 0.5 * (cc[:, 2] + cc[:, 3]), seqs)


def family_mean_auc(sc, day, fam, days):
    te = np.isin(day, days); ben = te & (fam == 0); out = []
    for f in range(1, int(fam.max()) + 1):
        pos = te & (fam == f)
        if pos.sum() >= MIN_WIN:
            m = pos | ben; out.append(roc_auc_score(fam[m] == f, sc[m]))
    return float(np.mean(out))


rows, ok_all = [], True
for ds in a.datasets.split(","):
    z = np.load(os.path.join(a.data, ds, "windows.npz"), allow_pickle=True); day, fam = z["day"], z["family"]
    present = sorted(set(np.unique(day).tolist()) - {0})
    order = [int(x) for x in np.argsort(z["day_t0"]) if int(x) in present] if "day_t0" in z.files else present
    splits = {"dev": order[:len(order) // 2], "final": order[len(order) // 2:]}
    for s in [int(x) for x in a.seeds.split(",")]:
        sc = v0_scores(os.path.join(ckdir, f"{ds}_s{s}.pt"), z)
        stored = json.load(open(os.path.join(a.data, "scoreboard", f"{ds}_s{s}.json")))["models"]["v0 NCM, smoothed"] if os.path.exists(os.path.join(a.data, "scoreboard", f"{ds}_s{s}.json")) else None
        for sp, days in splits.items():
            mine = family_mean_auc(sc, day, fam, days)
            r = csv[(csv.version == "v0") & (csv.dataset == ds) & (csv.model == "v0 NCM, smoothed") & (csv.split == sp) & (csv.metric == "family_mean_auc")].iloc[0]
            same = None if stored is None else abs(mine - stored[sp]["family_mean_auc"]) < 0.0015
            inside = r["min"] - 0.002 <= mine <= r["max"] + 0.002
            ok_all &= bool(inside) and (same is not False)
            rows.append({"dataset": ds, "seed": s, "split": sp, "this_check": round(mine, 3), "stored_run": None if stored is None else round(stored[sp]["family_mean_auc"], 3),
                         "matches_stored": same, "committed_range": f"{r['min']:.3f} to {r['max']:.3f}", "inside_range": bool(inside)})
            print(rows[-1], flush=True)
print("\n" + pd.DataFrame(rows).to_string(index=False)); print("\nOVERALL:", "PASS" if ok_all else "FAIL (see rows with False)")

sys.exit(0 if ok_all else 1)
