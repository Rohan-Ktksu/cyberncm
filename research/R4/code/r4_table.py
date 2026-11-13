"""Aggregate R4 JSON files into results tables. Usage: python r4_table.py R4_DIR OUT.md OUT.csv

Per dataset, score source and policy family, per seed: the parameter is chosen on dev (the setting with the fewest false alert
episodes per benign host-day among those catching >= 80% of attacking sources within 5 minutes; if none does, the one catching
most, ties by fewest false alerts), then read on final. Reported: mean and range over seeds of the final numbers.
A policy family "meets the target" on a seed when its dev-chosen setting has final detection >= 0.8 and < 1 false alert episode
per benign host-day; it passes on a dataset when it meets the target on a majority of that dataset's seeds.
"""
import csv, glob, json, os, sys
import numpy as np, pandas as pd
rd, out_md, out_csv = sys.argv[1:4]
NICE = {"cic2017": "CIC-IDS2017", "unsw": "UNSW-NB15", "d2018": "CSE-CIC-IDS2018", "unraveled": "Unraveled", "cicapt": "CICAPT-IIoT"}
FAM = ["fixed threshold", "daily recalibration", "rolling quantile", "per-source threshold", "k of n on fixed", "k of n on daily", "two tiers"]
rows = []
for f in sorted(glob.glob(os.path.join(rd, "*_s*.json"))):
    ds, s = os.path.basename(f)[:-5].rsplit("_s", 1)
    for r in json.load(open(f))["rows"]: rows.append({**r, "dataset": ds, "seed": int(s)})
df = pd.DataFrame(rows); res = []
for (ds, sc, seed, pol), g in df.groupby(["dataset", "score", "seed", "policy"]):
    dev, fin = g[g.split == "dev"].set_index("param"), g[g.split == "final"].set_index("param")
    ok = dev[dev.detected_5min >= 0.8]
    pick = ok.false_per_host_day.idxmin() if len(ok) else dev.sort_values(["detected_5min", "false_per_host_day"], ascending=[False, True]).index[0]
    r = fin.loc[pick]; res.append({"dataset": ds, "score": sc, "seed": seed, "policy": pol, "param": pick, "dev_reached_80": bool(len(ok)),
        "final_detected_5min": r.detected_5min, "final_false_per_host_day": r.false_per_host_day, "final_benign_source_hour_rate": r.benign_source_hour_rate,
        "attacking_sources": int(r.attacking_sources), "benign_sources": int(r.benign_sources),
        "meets": bool(r.detected_5min >= 0.8 and r.false_per_host_day < 1)})
R = pd.DataFrame(res); R.to_csv(out_csv, index=False)
md = []; rng = lambda v, d=2: f"{np.mean(v):.{d}f}" + (f" ({np.min(v):.{d}f} to {np.max(v):.{d}f})" if len(v) > 1 else "")
for ds in [k for k in NICE if k in set(R.dataset)]:
    for sc in sorted(set(R[R.dataset == ds].score)):
        g = R[(R.dataset == ds) & (R.score == sc)]; n = g.seed.nunique(); a = g.attacking_sources.iloc[0]; b = g.benign_sources.iloc[0]
        md += [f"### {NICE[ds]}, {sc} score ({n} seed{'s' if n > 1 else ''}; final split: {a} attacking and {b} benign sources)", "",
               "| Policy | Setting chosen on dev (per seed) | Attacking sources alerted within 5 min | False alerts per benign host-day | Benign source-hours with an alert | Seeds meeting the target |", "|---|---|---|---|---|---|"]
        for pol in FAM:
            h = g[g.policy == pol]
            if h.empty: continue
            params = ", ".join(sorted(set(h.param))) or "none"; met = int(h.meets.sum())
            md.append(f"| {pol} | {params} | {rng(h.final_detected_5min.values)} | {rng(h.final_false_per_host_day.values)} | {rng(h.final_benign_source_hour_rate.values, 3)} | {met} of {len(h)}{' (passes)' if met * 2 > len(h) else ''} |")
        md.append("")
open(out_md, "w").write("\n".join(md) + "\n"); print(len(R), "rows;", sorted(set(R.dataset)))
