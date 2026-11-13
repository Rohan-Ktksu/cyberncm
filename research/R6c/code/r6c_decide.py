"""Apply the R6c improvement rule. Usage: python r6c_decide.py R6C_DIR SCOREBOARD_DIR OUT.md   (R6C_DIR holds pair/ and service/ subfolders of <ds>_s<seed>.json)"""
import glob, json, os, sys
import numpy as np
rd, sd, out = sys.argv[1:4]; REF = "token distance, smoothed"
NICE = {"cic2017": "CIC-IDS2017", "unsw": "UNSW-NB15", "d2018": "CSE-CIC-IDS2018", "unraveled": "Unraveled", "cicapt": "CICAPT-IIoT"}
def load(pattern, model):
    D = {}
    for f in sorted(glob.glob(pattern)):
        if os.path.basename(f).startswith(('fair_', 'rf_')): continue  # other files that share the name pattern
        ds, s = os.path.basename(f)[:-5].rsplit("_s", 1); j = json.load(open(f))["models"]; m = model if model in j else next(iter(j))
        for sp, x in j[m].items():
            e = D.setdefault(ds, {}).setdefault(sp, {"auc": [], "fa": []}); e["auc"].append(x["family_mean_auc"]); e["fa"].append(x["false_per_host_day_at_80pct_5min"])
    return D
R = load(os.path.join(sd, "*_s?.json"), REF); C = {"per source-destination pair": load(os.path.join(rd, "pair", "*_s?.json"), None), "per source-service": load(os.path.join(rd, "service", "*_s?.json"), None)}
dss = [k for k in NICE if k in R]; mean = lambda v: float(np.mean([a for a in v if a is not None]))
L = ["### Family-mean AUC, mean over seeds (final split; dev in brackets)", "", "| Unit | " + " | ".join(NICE[k] for k in dss) + " |", "|---|" + "---|" * len(dss)]
L.append("| per source (reference: token distance, 512 centres) | " + " | ".join(f"{mean(R[k]['final']['auc']):.3f} ({mean(R[k]['dev']['auc']):.3f})" for k in dss) + " |")
for name, D in C.items(): L.append(f"| {name} | " + " | ".join(f"{mean(D[k]['final']['auc']):.3f} ({mean(D[k]['dev']['auc']):.3f})" if k in D else "n/a" for k in dss) + " |")
L += ["", "### False alerts per benign host-day at 80% in 5 minutes (final; a best case)", "", "| Unit | " + " | ".join(NICE[k] for k in dss) + " |", "|---|" + "---|" * len(dss)]
L.append("| per source | " + " | ".join(f"{mean(R[k]['final']['fa']):.2f}" for k in dss) + " |")
for name, D in C.items(): L.append(f"| {name} | " + " | ".join(f"{mean(D[k]['final']['fa']):.2f}" if k in D else "n/a" for k in dss) + " |")
L += ["", "### Improvement rule against per-source token distance", "", "| Candidate | Better on dev | Worse (dev or final) | Final not below reference where better on dev | Improvement |", "|---|---|---|---|---|"]
for name, D in C.items():
    better, worse, hold = [], [], []
    for k in dss:
        if k not in D: continue
        c, b = D[k], R[k]
        if min(c["dev"]["auc"]) > max(b["dev"]["auc"]): better.append(k); hold.append(mean(c["final"]["auc"]) >= mean(b["final"]["auc"]))
        for sp in ("dev", "final"):
            if max(c[sp]["auc"]) < min(b[sp]["auc"]): worse.append(f"{NICE[k]} {sp}")
    ok = len(better) >= 3 and not worse and all(hold)
    L.append(f"| {name} | {', '.join(NICE[x] for x in better) or 'none'} | {', '.join(worse) or 'none'} | {'yes' if all(hold) else 'no'} | {'**yes**' if ok else 'no'} |")
open(out, "w").write("\n".join(L) + "\n"); print("\n".join(L))
