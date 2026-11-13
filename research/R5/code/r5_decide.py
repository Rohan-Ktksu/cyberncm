"""Apply the R5 rule. Usage: python r5_decide.py R5_DIR OUT.md   (files w<seconds>_s<seed>.json)"""
import glob, json, os, re, sys
import numpy as np
rd, out = sys.argv[1:3]; R = {}
for f in sorted(glob.glob(os.path.join(rd, "w*_s?.json"))):
    w = float(re.match(r"w([\d.]+)_s\d\.json", os.path.basename(f)).group(1)); R.setdefault(w, []).append(json.load(open(f)))
ws = sorted(R); ref = R[5.0]; ref_final = np.mean([r["final"]["family_mean_auc"] for r in ref]); ref_dev = np.mean([r["dev"]["family_mean_auc"] for r in ref])
L = ["### v0 by window length, CIC-IDS2017, mean over seeds (min to max)", "", "| Window | Windows | Dev AUC | Final AUC | Worst family (final) | Median s to first alert (final) | 90th percentile s | Never alerted (attacker-days, final) |", "|---|---|---|---|---|---|---|---|"]
keep = []
for w in ws:
    rs = R[w]; fa = [r["final"]["family_mean_auc"] for r in rs]; da = [r["dev"]["family_mean_auc"] for r in rs]
    md = [r["final"]["median_seconds_to_first_alert"] for r in rs]; p9 = [r["final"]["p90_seconds_to_first_alert"] for r in rs]; nv = [(r["final"]["never_alerted"], r["final"]["attacker_days"]) for r in rs]
    L.append(f"| {w:g} s | {rs[0]['windows']:,} | {np.mean(da):.3f} ({min(da):.3f} to {max(da):.3f}) | {np.mean(fa):.3f} ({min(fa):.3f} to {max(fa):.3f}) | {np.mean([r['final']['worst_family_auc'] for r in rs]):.3f} | {np.mean([x for x in md if x is not None]):.1f} | {np.mean([x for x in p9 if x is not None]):.1f} | {sum(a for a, _ in nv)} of {sum(b for _, b in nv)} |")
    if np.mean(fa) >= ref_final - 0.01 and np.mean(da) >= ref_dev - 0.01: keep.append(w)
L += ["", f"Rule: the fastest window length whose mean final AND dev family-mean AUC are both within 0.01 of the 5-second window (final {ref_final:.3f}, dev {ref_dev:.3f}) keeps accuracy. Lengths that keep it: {', '.join(f'{w:g} s' for w in keep) or 'none'}. **Fastest window that keeps accuracy: {min(keep):g} s.**", ""]
open(out, "w").write("\n".join(L) + "\n"); print("\n".join(L))
