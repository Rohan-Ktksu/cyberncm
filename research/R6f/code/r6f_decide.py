"""Apply the R6f rule. Usage: python r6f_decide.py R6F_DIR SCOREBOARD_DIR OUT.md"""
import glob, json, os, sys
import numpy as np
rd, sd, out = sys.argv[1:4]; V0 = "v0 NCM, smoothed"
NICE = {"cic2017": "CIC-IDS2017", "unsw": "UNSW-NB15", "d2018": "CSE-CIC-IDS2018", "unraveled": "Unraveled", "cicapt": "CICAPT-IIoT"}
V = {}; C = {}
for f in sorted(glob.glob(os.path.join(sd, "*_s?.json"))):
    if os.path.basename(f).startswith(("fair_", "rf_")): continue  # other files sharing the name pattern
    ds, s = os.path.basename(f)[:-5].rsplit("_s", 1); V.setdefault(ds, []).append(json.load(open(f))["models"][V0]["final"]["family_mean_auc"])
for f in sorted(glob.glob(os.path.join(rd, "*_s?.json"))):
    ds, s = os.path.basename(f)[:-5].rsplit("_s", 1)
    for m, v in json.load(open(f))["models"].items():
        if v["final"].get("family_mean_auc") is not None: C.setdefault(m, {}).setdefault(ds, []).append(v["final"]["family_mean_auc"])
FAIR = {}
for ds in V:
    p = os.path.join(sd, f"fair_{ds}_s0.json")
    if os.path.exists(p): j = json.load(open(p))["models"]; FAIR[ds] = next(x["final"]["family_mean_auc"] for k, x in j.items() if "fair" in k)
dss = [k for k in NICE if k in V]; mean = lambda v: float(np.mean(v)); rng = lambda v: f"{np.mean(v):.3f} ({np.min(v):.3f} to {np.max(v):.3f})"
L = ["### Final-split family-mean AUC, mean over seeds (range)", "", "| Model | " + " | ".join(NICE[k] for k in dss) + " |", "|---|" + "---|" * len(dss)]
L.append("| v0 | " + " | ".join(rng(V[k]) for k in dss) + " |")
L.append("| fair random forest (one seed) | " + " | ".join(f"{FAIR[k]:.3f}" if k in FAIR else "n/a" for k in dss) + " |")
for m in C: L.append(f"| {m} | " + " | ".join(rng(C[m][k]) if k in C[m] else "n/a" for k in dss) + " |")
L += ["", "### Improvement rule against v0 (final split only)", "", "| Candidate | Better than v0 | Worse than v0 | Improvement |", "|---|---|---|---|"]
for m in C:
    better = [k for k in dss if k in C[m] and min(C[m][k]) > max(V[k])]; worse = [k for k in dss if k in C[m] and max(C[m][k]) < min(V[k])]
    ok = len(better) >= 3 and not worse
    L.append(f"| {m} | {', '.join(NICE[x] for x in better) or 'none'} | {', '.join(NICE[x] for x in worse) or 'none'} | {'**yes**' if ok else 'no'} |")
open(out, "w").write("\n".join(L) + "\n"); print("\n".join(L))
