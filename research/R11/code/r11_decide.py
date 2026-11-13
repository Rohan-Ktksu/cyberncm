"""Apply the R11 decision rules. Usage: python r11_decide.py R11_DIR SCOREBOARD_DIR OUT.md"""
import glob, json, os, re, sys
import numpy as np
rd, sd, out = sys.argv[1:4]; V0 = "v0 NCM, smoothed"
NICE = {"cic2017": "CIC-IDS2017", "unsw": "UNSW-NB15", "d2018": "CSE-CIC-IDS2018"}
BUD = ["10 min", "60 min", "360 min", "full"]
R = {}   # R[(A,B)][model][seed] = (dev, final, fa_final)
for f in sorted(glob.glob(os.path.join(rd, "*_to_*_s?.json"))):
    a, b, s = re.match(r"(\w+)_to_(\w+)_s(\d)\.json", os.path.basename(f)).groups()
    for m, v in json.load(open(f))["models"].items():
        R.setdefault((a, b), {}).setdefault(m, {})[int(s)] = (v["dev"]["family_mean_auc"], v["final"]["family_mean_auc"], v["final"]["false_per_host_day_at_80pct_5min"])
# Include every computed budget, including multi-day curves.
BUD = sorted({m.rsplit(" @ ", 1)[1] for models in R.values() for m in models
              if " @ " in m and m.rsplit(" @ ", 1)[1] != "full"},
             key=lambda x: float(x.removesuffix(" min"))) + ["full"]
REF = {}
for f in sorted(glob.glob(os.path.join(sd, "*_s?.json"))):
    if os.path.basename(f).startswith(("fair_", "rf_")): continue
    ds = os.path.basename(f)[:-5].rsplit("_s", 1)[0]; v = json.load(open(f))["models"][V0]
    REF.setdefault(ds, []).append((v["dev"]["family_mean_auc"], v["final"]["family_mean_auc"]))
ref = {k: (np.mean([x[0] for x in v]), np.mean([x[1] for x in v])) for k, v in REF.items()}
mean = lambda v: float(np.mean(v)); dirs = sorted(R)
def level(a, b, name, i): return mean([x[i] for x in R[(a, b)][name].values()]) if name in R[(a, b)] else float("nan")
L = ["### Final-split family-mean AUC per direction (mean over available seeds)", "", "| Direction | L1 threshold only | L2 + target normalisation | L3 + target vocabularies and calibration | L4 full retraining (target's own v0) |", "|---|---|---|---|---|"]
for a, b in dirs:
    L.append(f"| {NICE.get(a,a)} to {NICE.get(b,b)} | {level(a,b,'L1 threshold only',1):.3f} | {level(a,b,'L2 + target normalisation @ full',1):.3f} | {level(a,b,'L3 + target vocabularies and calibration @ full',1):.3f} | {ref[b][1]:.3f} |")
def over_dirs(name, i): return mean([level(a, b, name, i) for a, b in dirs if name in R[(a, b)]])
L2d, L3d = over_dirs("L2 + target normalisation @ full", 0), over_dirs("L3 + target vocabularies and calibration @ full", 0)
best = "L2 + target normalisation" if L2d >= L3d else "L3 + target vocabularies and calibration"
L += ["", f"Mean dev family-mean AUC over the directions at full data: L2 {L2d:.3f}, L3 {L3d:.3f}. **Best cheap level: {best.split(' ')[0]}.**", "",
      f"### Learning curve of {best.split(' ')[0]} (final family-mean AUC, mean over available seeds)", "", "| Direction | " + " | ".join(BUD) + " | L4 reference |", "|---|" + "---|" * (len(BUD) + 1)]
for a, b in dirs: L.append(f"| {NICE.get(a,a)} to {NICE.get(b,b)} | " + " | ".join(f"{level(a,b,best+' @ '+m,1):.3f}" for m in BUD) + f" | {ref[b][1]:.3f} |")
diff = {m: mean([level(a, b, f"{best} @ {m}", 1) - ref[b][1] for a, b in dirs if f"{best} @ {m}" in R[(a, b)]]) for m in BUD}
L += ["", "| Budget | " + " | ".join(BUD) + " |", "|---|" + "---|" * len(BUD), "| Mean over directions of (final AUC minus L4) | " + " | ".join(f"{diff[m]:+.3f}" for m in BUD) + " |", ""]
ok = [m for m in BUD if diff[m] >= -0.02]
L.append("**Learning period: " + (f"{ok[0]}** (the shortest budget with a mean gap of at most 0.02 to full retraining)." if ok else "none of the budgets reaches a mean gap of 0.02: cheap adaptation does not replace training.**"))
L += ["", "### Dev family-mean AUC per direction (mean over available seeds)", "", "| Direction | L1 | L2 @ full | L3 @ full | L4 |", "|---|---|---|---|---|"]
for a, b in dirs: L.append(f"| {NICE.get(a,a)} to {NICE.get(b,b)} | {level(a,b,'L1 threshold only',0):.3f} | {level(a,b,'L2 + target normalisation @ full',0):.3f} | {level(a,b,'L3 + target vocabularies and calibration @ full',0):.3f} | {ref[b][0]:.3f} |")
open(out, "w").write("\n".join(L) + "\n"); print("\n".join(L))
