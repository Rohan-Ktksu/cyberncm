"""Apply the R7m rules. Usage: python r7m_decide.py R7M_DIR OUT.md   (files <dataset>_s<seed>.json)"""
import glob, json, os, re, sys
import numpy as np
rd, out = sys.argv[1:3]; NICE = {"cic2017": "CIC-IDS2017", "d2018": "CSE-CIC-IDS2018"}
C = {}   # clean[ds][trim] -> list of (auc, false share) per seed ; P[ds][(family, poison, trim)] -> list of detection
P = {}
for f in sorted(glob.glob(os.path.join(rd, "*_s?.json"))):
    ds = re.match(r"(\w+)_s\d\.json", os.path.basename(f)).group(1)
    for r in json.load(open(f))["runs"]:
        if r["family"] is None: C.setdefault(ds, {}).setdefault(r["trim"], []).append((r["final_family_mean_auc"], r["benign_false_share_final"]))
        else: P.setdefault(ds, {}).setdefault((r["family"], r["poison"], r["trim"]), []).append(r["detection"][r["family"]])
L = []; works = {}
L += ["### Clean cost of trimming (no poison): final family-mean AUC and share of benign final windows above the threshold, mean (min to max over seeds)", "",
      "| Dataset | Trim | AUC | False share | Within the clean rule |", "|---|---|---|---|---|"]
for ds in C:
    base = C[ds][0.0]; amin = min(a for a, _ in base); fmax = max(f for _, f in base)
    for q in sorted(C[ds]):
        v = C[ds][q]; a = np.mean([x[0] for x in v]); fs = np.mean([x[1] for x in v])
        ok = (a >= amin) and (fs <= fmax + 0.01); works[(ds, q)] = ok
        L.append(f"| {NICE[ds]} | {q:.0%} | {a:.3f} ({min(x[0] for x in v):.3f} to {max(x[0] for x in v):.3f}) | {fs:.4f} ({min(x[1] for x in v):.4f} to {max(x[1] for x in v):.4f}) | {'baseline' if q == 0 else ('yes' if ok else 'NO')} |")
L += ["", "### Detection of the poisoned family on the final split, mean over seeds", "", "| Dataset | Family | Poison | no trim | trim 1% | trim 2% | trim 5% | Fixed at (smallest trim with detection at least 0.5 at both poison levels and clean rule met) |", "|---|---|---|---|---|---|---|---|"]
fixed = []
for ds in P:
    for fam in sorted({k[0] for k in P[ds]}):
        for p in sorted({k[1] for k in P[ds] if k[0] == fam}):
            d = {q: float(np.mean(P[ds][(fam, p, q)])) for q in (0.0, 0.01, 0.02, 0.05) if (fam, p, q) in P[ds]}
            fx = ""
            if p == max(k[1] for k in P[ds] if k[0] == fam):
                lo = min(k[1] for k in P[ds] if k[0] == fam)
                ok_q = [q for q in (0.01, 0.02, 0.05) if all(np.mean(P[ds][(fam, pp, q)]) >= 0.5 for pp in (lo, p)) and works.get((ds, q))]
                fx = (f"{ok_q[0]:.0%}" if ok_q else "not fixed"); fixed.append((ds, fam, fx))
            L.append(f"| {NICE[ds]} | {fam} | {p:.1%} | " + " | ".join(f"{d[q]:.2f}" if q in d else "-" for q in (0.0, 0.01, 0.02, 0.05)) + f" | {fx} |")
L += ["", "Families fixed: " + (", ".join(f"{NICE[a]} {b} ({c})" for a, b, c in fixed if c != "not fixed") or "none"), "Families not fixed: " + (", ".join(f"{NICE[a]} {b}" for a, b, c in fixed if c == "not fixed") or "none"), ""]
open(out, "w").write("\n".join(L) + "\n"); print("\n".join(L))
