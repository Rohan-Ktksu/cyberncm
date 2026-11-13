"""Apply the R7a and R7c breach rules. Usage: python r7_decide.py R7_RESULTS_DIR OUT.md   (files: mimicry_<ds>_s<seed>.json, poison_<ds>_s<seed>.json)"""
import glob, json, os, re, sys
import numpy as np
rd, out = sys.argv[1:3]
NICE = {"cic2017": "CIC-IDS2017", "unsw": "UNSW-NB15", "d2018": "CSE-CIC-IDS2018", "unraveled": "Unraveled", "cicapt": "CICAPT-IIoT"}
M, MA, MS, P = {}, {}, {}, {}   # M[ds][split][family][alpha] -> list over seeds ; P[ds][split][family][p]
for f in sorted(glob.glob(os.path.join(rd, "*_s?.json"))):
    mode, ds, s = re.match(r"(mimicrysample|mimicryall|mimicry|poison)_(\w+)_s(\d)\.json", os.path.basename(f)).groups(); j = json.load(open(f))
    for k, v in j["curve"].items():
        if mode in ("mimicry", "mimicryall", "mimicrysample"):
            for sp, fd in v.items():
                for fam, x in fd.items(): {"mimicryall": MA, "mimicrysample": MS}.get(mode, M).setdefault(ds, {}).setdefault(sp, {}).setdefault(fam, {}).setdefault(float(k), []).append(x)
        else:
            for p, e in v.items():
                for sp, x in e["detection"].items():
                    if x is not None: P.setdefault(ds, {}).setdefault(sp, {}).setdefault(k, {}).setdefault(float(p), []).append(x)
mean = lambda v: float(np.mean(v)); L = []
L += ["### R7a mimicry: detection (share of the family's windows above the 99% threshold), mean over seeds, final split", "",
      "| Dataset | Family | a=0 | a=0.25 | a=0.5 | a=0.75 | a=1.0 | smallest a with detection below half | Breach (below half at a<=0.5) |", "|---|---|---|---|---|---|---|---|---|"]
breaches = []
for ds in M:
    for fam, cur in sorted(M[ds].get("final", {}).items()):
        d = {a: mean(v) for a, v in cur.items()}; al = sorted(d); base = d[0.0]
        first = next((a for a in al if d[a] < 0.5), None)
        if base < 0.5: status = "not detected at a=0"
        elif d[0.5] < 0.5: status = "BREACH"; breaches.append((ds, fam, first))
        else: status = "no"
        L.append(f"| {NICE[ds]} | {fam} | {d[0.0]:.2f} | {d[0.25]:.2f} | {d[0.5]:.2f} | {d[0.75]:.2f} | {d[1.0]:.2f} | {first if first is not None else 'none up to 1.0'} | {status} |")
L += ["", f"Families breached at a<=0.5: {len(breaches)}: " + (", ".join(f"{NICE[a]} {b} (first below half at a={c})" for a, b, c in breaches) or "none"), ""]
if MA:
    L += ["### R7a-all (exploratory, outside the rule): every feature movable, final split", "", "| Dataset | Family | a=0 | a=0.25 | a=0.5 | a=0.75 | a=1.0 | smallest a with detection below half |", "|---|---|---|---|---|---|---|---|"]
    nb = 0
    for ds in MA:
        for fam, cur in sorted(MA[ds].get("final", {}).items()):
            d = {a: mean(v) for a, v in cur.items()}; first = next((a for a in sorted(d) if d[a] < 0.5), None); nb += d[0.0] >= 0.5 and d[0.5] < 0.5
            L.append(f"| {NICE[ds]} | {fam} | {d[0.0]:.2f} | {d[0.25]:.2f} | {d[0.5]:.2f} | {d[0.75]:.2f} | {d[1.0]:.2f} | {first if first is not None else 'none up to 1.0'} |")
    L += ["", f"Families that would be breached at a<=0.5 if every feature were movable: {nb}", ""]
if MS:
    L += ["### R7a-sample (exploratory, outside the rule): controlled features move toward one random real benign window, final split", "", "| Dataset | Family | a=0 | a=0.25 | a=0.5 | a=0.75 | a=1.0 | smallest a with detection below half | Would breach (below half at a<=0.5) |", "|---|---|---|---|---|---|---|---|---|"]
    nb = 0
    for ds in MS:
        for fam, cur in sorted(MS[ds].get("final", {}).items()):
            d = {a: mean(v) for a, v in cur.items()}; first = next((a for a in sorted(d) if d[a] < 0.5), None); br = d[0.0] >= 0.5 and d[0.5] < 0.5; nb += br
            L.append(f"| {NICE[ds]} | {fam} | {d[0.0]:.2f} | {d[0.25]:.2f} | {d[0.5]:.2f} | {d[0.75]:.2f} | {d[1.0]:.2f} | {first if first is not None else 'none up to 1.0'} | {'yes' if br else ('not detected at a=0' if d[0.0] < 0.5 else 'no')} |")
    L += ["", f"Families that would be breached at a<=0.5 under the sampled-window attacker: {nb}", ""]
L += ["### R7c poisoned learning period: detection of the poisoned family on the final split (windows left out of the poisoning), mean over seeds", "",
      "| Dataset | Family | 0% | 0.5% | 1% | 2% | 5% | Breach (below half at 2% or less) |", "|---|---|---|---|---|---|---|---|"]
pb = []
for ds in P:
    for fam, cur in sorted(P[ds].get("final", {}).items()):
        d = {p: mean(v) for p, v in cur.items()}; g = lambda p: f"{d[p]:.2f}" if p in d else "-"
        base = d.get(0.0, float("nan"))
        if base < 0.5: status = "not detected at 0%"
        elif any(d[p] < 0.5 for p in (0.005, 0.01, 0.02) if p in d): status = "BREACH"; pb.append((ds, fam))
        else: status = "no"
        L.append(f"| {NICE[ds]} | {fam} | {g(0.0)} | {g(0.005)} | {g(0.01)} | {g(0.02)} | {g(0.05)} | {status} |")
L += ["", f"Families breached at 2% or less: {len(pb)}: " + (", ".join(f"{NICE[a]} {b}" for a, b in pb) or "none"), ""]
open(out, "w").write("\n".join(L) + "\n"); print("\n".join(L))
