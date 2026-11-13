"""Apply the R6a decision rules to the per-seed JSON files. Usage: python r6a_decide.py R6A_DIR OUT.md"""
import glob, json, os, sys
import numpy as np
rd, out = sys.argv[1:3]
M0 = "v0 NCM, smoothed"; MH = "history only (no GRU): window + 1 min, 10 min, 1 h averages"; MB = "v0 + history"
NICE = {"cic2017": "CIC-IDS2017", "unsw": "UNSW-NB15", "d2018": "CSE-CIC-IDS2018", "unraveled": "Unraveled", "cicapt": "CICAPT-IIoT"}
D = {}
for f in sorted(glob.glob(os.path.join(rd, "*_s*.json"))):
    ds, s = os.path.basename(f)[:-5].rsplit("_s", 1)
    for m, v in json.load(open(f))["models"].items():
        for sp, x in v.items():
            e = D.setdefault(ds, {}).setdefault(m, {}).setdefault(sp, {"auc": [], "worst": [], "fa": []})
            e["auc"].append(x["family_mean_auc"]); e["worst"].append(x["worst_family_auc"]); e["fa"].append(x["false_per_host_day_at_80pct_5min"])
mean = lambda v: float(np.mean([a for a in v if a is not None])) if any(a is not None for a in v) else float("nan")
rng = lambda v, d=3: f"{np.mean(v):.{d}f} ({np.min(v):.{d}f} to {np.max(v):.{d}f})"
L = ["### Family-mean AUC and false alerts (mean over seeds, range)", "", "| Dataset | Split | Model | Family-mean AUC | Worst family | False alerts per benign host-day at 80% in 5 min |", "|---|---|---|---|---|---|"]
for ds in [k for k in NICE if k in D]:
    for sp in ("dev", "final"):
        for m in (M0, MH, MB):
            e = D[ds][m][sp]; L.append(f"| {NICE[ds]} | {sp} | {m.split(':')[0]} | {rng(e['auc'])} | {rng(e['worst'])} | {rng([a for a in e['fa'] if a is not None], 2)} |")
r1 = []; ok1 = True
for ds in [k for k in NICE if k in D]:
    for sp in ("dev", "final"):
        diff = mean(D[ds][MH][sp]["auc"]) - mean(D[ds][M0][sp]["auc"]); fa_h, fa_0 = mean(D[ds][MH][sp]["fa"]), mean(D[ds][M0][sp]["fa"])
        good = diff >= -0.01 and fa_h <= fa_0; ok1 &= good
        r1.append(f"| {NICE[ds]} | {sp} | {diff:+.3f} | {fa_h:.2f} vs {fa_0:.2f} | {'yes' if good else 'no'} |")
L += ["", "### Rule 1, GRU removal (history only against v0)", "", "| Dataset | Split | AUC difference (history minus v0) | False alerts, history vs v0 | Within 0.01 and no worse |", "|---|---|---|---|---|"] + r1
L += ["", f"**Rule 1 verdict: {'the GRU can be removed' if ok1 else 'the GRU stays (the rule is not met)'}.**"]
better, worse, hold = [], [], []
for ds in [k for k in NICE if k in D]:
    c, b = D[ds][MB], D[ds][M0]
    if min(c["dev"]["auc"]) > max(b["dev"]["auc"]): better.append(ds); hold.append(mean(c["final"]["auc"]) >= mean(b["final"]["auc"]))
    for sp in ("dev", "final"):
        if max(c[sp]["auc"]) < min(b[sp]["auc"]): worse.append((ds, sp))
ok2 = len(better) >= 3 and not worse and all(hold)
L += ["", "### Rule 2, improvement (v0 + history against v0)", "", f"- Better on dev (seed minimum above v0's seed maximum): {', '.join(NICE[x] for x in better) or 'none'} ({len(better)} of {len(D)} datasets).",
      f"- Worse (seed maximum below v0's seed minimum) on dev or final: {', '.join(f'{NICE[a]} {b}' for a, b in worse) or 'none'}.",
      f"- Final mean not below v0's on the datasets that are better on dev: {'yes' if all(hold) else 'no'}.", f"**Rule 2 verdict: {'an improvement' if ok2 else 'not an improvement'}.**", ""]
open(out, "w").write("\n".join(L) + "\n"); print("\n".join(L))
