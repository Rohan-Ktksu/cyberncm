"""Apply the R6b improvement rule. Usage: python r6b_decide.py R6B_DIR OUT.md  (reference: token distance, global; also shown against v0)"""
import glob, json, os, sys
import numpy as np
rd, out = sys.argv[1:3]; REF = "token distance, global"; V0 = "v0 NCM, smoothed"
NICE = {"cic2017": "CIC-IDS2017", "unsw": "UNSW-NB15", "d2018": "CSE-CIC-IDS2018", "unraveled": "Unraveled", "cicapt": "CICAPT-IIoT"}
D = {}
for f in sorted(glob.glob(os.path.join(rd, "*_s*.json"))):
    ds, s = os.path.basename(f)[:-5].rsplit("_s", 1)
    for m, v in json.load(open(f))["models"].items():
        for sp, x in v.items():
            e = D.setdefault(m, {}).setdefault(ds, {}).setdefault(sp, {"auc": [], "fa": []}); e["auc"].append(x["family_mean_auc"]); e["fa"].append(x["false_per_host_day_at_80pct_5min"])
dss = [k for k in NICE if k in D[REF]]; mean = lambda v: float(np.mean([a for a in v if a is not None]))
L = ["### Family-mean AUC, mean over seeds (final split; dev in brackets)", "", "| Model | " + " | ".join(NICE[k] for k in dss) + " |", "|---|" + "---|" * len(dss)]
for m in D: L.append(f"| {m} | " + " | ".join(f"{mean(D[m][k]['final']['auc']):.3f} ({mean(D[m][k]['dev']['auc']):.3f})" for k in dss) + " |")
L += ["", "### False alerts per benign host-day at 80% in 5 minutes (final; a best case)", "", "| Model | " + " | ".join(NICE[k] for k in dss) + " |", "|---|" + "---|" * len(dss)]
for m in D: L.append(f"| {m} | " + " | ".join(f"{mean(D[m][k]['final']['fa']):.2f}" for k in dss) + " |")
def verdict(ref):
    rows, winners = [], []
    for m in D:
        if m in (REF, V0): continue
        better, worse, hold = [], [], []
        for k in dss:
            c, b = D[m][k], D[ref][k]
            if min(c["dev"]["auc"]) > max(b["dev"]["auc"]): better.append(k); hold.append(mean(c["final"]["auc"]) >= mean(b["final"]["auc"]))
            for sp in ("dev", "final"):
                if max(c[sp]["auc"]) < min(b[sp]["auc"]): worse.append(f"{NICE[k]} {sp}")
        ok = len(better) >= 3 and not worse and all(hold); winners += [m] if ok else []
        rows.append(f"| {m} | {', '.join(NICE[x] for x in better) or 'none'} | {', '.join(worse) or 'none'} | {'yes' if all(hold) else 'no'} | {'**yes**' if ok else 'no'} |")
    return rows, winners
for ref, title in ((REF, "against token distance, global (the rule's reference)"), (V0, "against v0 (for information)")):
    rows, w = verdict(ref)
    L += ["", f"### Improvement rule {title}", "", "| Candidate | Better on dev | Worse (dev or final) | Final not below reference where better on dev | Improvement |", "|---|---|---|---|---|"] + rows
    L += ["", "**Candidates that pass: " + (", ".join(w) if w else "none") + ".**"]
open(out, "w").write("\n".join(L) + "\n"); print("\n".join(L))
