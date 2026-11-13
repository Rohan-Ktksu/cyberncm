"""Apply the R7b breach rule. Usage: python r7b_decide.py R7B_DIR OUT.md  (files cic2017_s<seed>.json)"""
import glob, json, os, sys
import numpy as np
rd, out = sys.argv[1:3]; D = {}
for f in sorted(glob.glob(os.path.join(rd, "cic2017_s?.json"))):
    for k, v in json.load(open(f))["factors"].items():
        for fam, x in v["detection"]["final"].items(): D.setdefault(fam, {}).setdefault(int(k), []).append(x)
L = ["### R7b low and slow (CIC-IDS2017, final split): detection at k times slower, mean over seeds", "", "| Family | k=1 | k=10 | k=100 | k=1000 | Breach (caught at k=1 and missed at k=100) |", "|---|---|---|---|---|---|"]
n = 0
for fam in sorted(D):
    d = {k: float(np.mean(v)) for k, v in D[fam].items()}
    if 1 not in d or 100 not in d: continue
    st = "not detected at k=1" if d[1] < 0.5 else ("BREACH" if d[100] < 0.5 else "no"); n += st == "BREACH"
    L.append(f"| {fam} | " + " | ".join(f"{d[k]:.2f}" if k in d else "-" for k in (1, 10, 100, 1000)) + f" | {st} |")
L += ["", f"Families breached at k=100: {n}", ""]
open(out, "w").write("\n".join(L) + "\n"); print("\n".join(L))
