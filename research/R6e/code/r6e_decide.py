"""Apply the R6e improvement rule against v0. Usage: python r6e_decide.py R6E_DIR SCOREBOARD_DIR OUT.md
R6E_DIR holds <candidate>/<dataset>_s<seed>.json (scoreboard format) for tf and gru_masked, and ensemble_<dataset>.json from r6e_ensemble.py."""
import glob, json, math, os, sys
import numpy as np
rd, sd, out = sys.argv[1:4]; V0 = "v0 NCM, smoothed"
NICE = {"cic2017": "CIC-IDS2017", "unsw": "UNSW-NB15", "d2018": "CSE-CIC-IDS2018", "unraveled": "Unraveled", "cicapt": "CICAPT-IIoT"}
# Fail closed: a partial experiment is not evidence that no candidate wins.
open(out,"w",encoding="utf-8").write("INCOMPLETE: R6e input validation pending; no conclusion.\n")
expected_ref={f"{ds}_s{seed}.json" for ds in NICE for seed in range(5)}
found_ref={os.path.basename(f) for f in glob.glob(os.path.join(sd,"*_s*.json")) if not os.path.basename(f).startswith(("fair_","rf_"))}
if found_ref!=expected_ref:raise ValueError("INCOMPLETE: expected all five datasets and five reference seeds")
expected_candidate={f"{ds}_s{seed}.json" for ds in NICE for seed in range(3)}
for name in ("tf","gru_masked"):
    found={os.path.basename(f) for f in glob.glob(os.path.join(rd,name,"*_s*.json"))}
    if found!=expected_candidate:raise ValueError(f"INCOMPLETE: missing or unexpected {name} dataset/seed files")
for folder,files in [(sd,expected_ref)]+[(os.path.join(rd,c),expected_candidate) for c in ("tf","gru_masked")]:
    for name in files:
        with open(os.path.join(folder,name)) as f:j=json.load(f)
        if j["seed"]!=int(name.rsplit("_s",1)[1][:-5]):raise ValueError("INCOMPLETE: contradictory seed metadata")
        for split in ("dev","final"):
            value=j["models"][V0][split]["family_mean_auc"]
            if not isinstance(value,(int,float)) or not math.isfinite(value) or not 0<=value<=1:
                raise ValueError("INCOMPLETE: invalid AUC")
ensembles={f"ensemble_{ds}.json" for ds in NICE}
if {os.path.basename(f) for f in glob.glob(os.path.join(rd,"ensemble_*.json"))}!=ensembles:
    raise ValueError("INCOMPLETE: expected all five ensemble results")
for ds in NICE:
    with open(os.path.join(rd,f"ensemble_{ds}.json")) as f:j=json.load(f)
    if j["dataset"]!=ds:raise ValueError("INCOMPLETE: ensemble dataset mismatch")
    for split in ("dev","final"):
        values=j["leave_one_out"][split]
        if len(values)!=5 or any(not isinstance(v,(int,float)) or not math.isfinite(v) or not 0<=v<=1 for v in values):
            raise ValueError("INCOMPLETE: invalid leave-one-out population")
mean = lambda v: float(np.mean(v)); rng_s = lambda v: f"{min(v):.3f} to {max(v):.3f}"
ref = {}                                     # ref[ds][split] -> list of v0 family-mean AUC per seed
for f in sorted(glob.glob(os.path.join(sd, "*_s?.json"))):
    if os.path.basename(f).startswith(("fair_", "rf_")): continue
    ds = os.path.basename(f)[:-5].rsplit("_s", 1)[0]
    for sp, x in json.load(open(f))["models"][V0].items(): ref.setdefault(ds, {}).setdefault(sp, []).append(x["family_mean_auc"])
cands = {}                                   # cands[name][ds][split] -> list
for name, label in (("tf", "Transformer backbone, same hidden size"), ("gru_masked", "GRU with masked-history objective")):
    for f in sorted(glob.glob(os.path.join(rd, name, "*_s?.json"))):
        ds = os.path.basename(f)[:-5].rsplit("_s", 1)[0]
        for sp, x in json.load(open(f))["models"][V0].items():       # the candidate is the "v0 NCM, smoothed" row of its own scoreboard file (the file also holds the baselines)
            cands.setdefault(label, {}).setdefault(ds, {}).setdefault(sp, []).append(x["family_mean_auc"])
for f in sorted(glob.glob(os.path.join(rd, "ensemble_*.json"))):
    j = json.load(open(f)); cands.setdefault("Seed ensemble (leave-one-out ensembles of 4 of the 5 v0 seeds)", {})[j["dataset"]] = {sp: j["leave_one_out"][sp] for sp in ("dev", "final")}
dss = [k for k in NICE if k in ref]
L = ["### Family-mean AUC per dataset: mean over seeds (min to max); v0 uses its 5 seeds", "", "| Model | Split | " + " | ".join(NICE[k] for k in dss) + " |", "|---|---|" + "---|" * len(dss)]
for sp in ("dev", "final"):
    L.append(f"| v0 (reference) | {sp} | " + " | ".join(f"{mean(ref[k][sp]):.3f} ({rng_s(ref[k][sp])})" for k in dss) + " |")
    for name, d in cands.items(): L.append(f"| {name} | {sp} | " + " | ".join((f"{mean(d[k][sp]):.3f} ({rng_s(d[k][sp])})" if k in d else "-") for k in dss) + " |")
L += ["", "### Improvement rule against v0", "", "| Candidate | Seeds per dataset | Better on dev | Worse (dev or final) | Final not below v0 where better | Improvement |", "|---|---|---|---|---|---|"]; winners = []
for name, d in cands.items():
    better, worse, hold = [], [], []
    for k in dss:
        if k not in d: continue
        if min(d[k]["dev"]) > max(ref[k]["dev"]): better.append(k); hold.append(mean(d[k]["final"]) >= mean(ref[k]["final"]))
        for sp in ("dev", "final"):
            if max(d[k][sp]) < min(ref[k][sp]): worse.append(f"{NICE[k]} {sp}")
    n = sorted({len(d[k]["dev"]) for k in d}); ok = len(better) >= 3 and not worse and all(hold) and len(d) == len(dss); winners += [name] if ok else []
    L.append(f"| {name} | {', '.join(map(str, n))} | {', '.join(NICE[x] for x in better) or 'none'} | {', '.join(worse) or 'none'} | {'yes' if all(hold) else 'no'} | {'**yes**' if ok else 'no'} |")
L += ["", "**Candidates that pass: " + (", ".join(winners) if winners else "none") + ".** A candidate missing a dataset cannot pass."]
open(out, "w").write("\n".join(L) + "\n"); print("\n".join(L))
