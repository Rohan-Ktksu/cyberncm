"""Aggregate scoreboard JSON files into research/scoreboard.csv and the results tables of SCOREBOARD.md.

Usage: python scoreboard_table.py RESULTS_DIR OUT_CSV OUT_MD VERSION COMMIT
One CSV row per (version, dataset, model, split, metric): number of seeds, mean, min, max over seeds, and the 95%
bootstrap interval of seed 0 (resampling sources) where one exists. Models that do not depend on the seed (random forest,
isolation forest) have one seed. Every attempt gets rows; nothing is dropped.
"""
import csv, glob, json, os, sys
import numpy as np

METRICS = [("family_mean_auc", "family-mean AUC"), ("worst_family_auc", "worst family AUC"),
           ("false_per_host_day_at_80pct_5min", "false alerts per benign host-day at 80% in 5 min"),
           ("detect_1pct_cal", "attack windows flagged at the 1% calibration threshold"),
           ("false_window_rate_1pct_cal", "benign windows flagged at the 1% calibration threshold"),
           ("benign_source_hour_rate_1pct_cal", "benign source-hours with an alert at the 1% calibration threshold")]
CI_KEY = {"family_mean_auc": "family_mean_auc_ci95", "false_per_host_day_at_80pct_5min": "false_per_host_day_ci95"}
DATASETS = ["cic2017", "unsw", "d2018", "unraveled", "cicapt"]
NICE = {"cic2017": "CIC-IDS2017", "unsw": "UNSW-NB15", "d2018": "CSE-CIC-IDS2018", "unraveled": "Unraveled", "cicapt": "CICAPT-IIoT"}


def main(rdir, out_csv, out_md, version, commit):
    runs = {}
    for f in sorted(glob.glob(os.path.join(rdir, "*_s*.json"))):
        ds, s = os.path.basename(f)[:-5].rsplit("_s", 1); runs.setdefault(ds, {})[int(s)] = json.load(open(f))
    rows, fam_rows = [], []
    for ds, seeds in runs.items():
        for model in sorted({m for r in seeds.values() for m in r["models"]}):
            for split in ("dev", "final"):
                got = [(s, r["models"][model][split]) for s, r in sorted(seeds.items()) if model in r["models"] and split in r["models"][model]]
                if not got: continue
                for key, _ in METRICS + [("n_attacking_sources", ""), ("n_benign_sources", ""), ("n_families", "")]:
                    v = [g[key] for _, g in got if g.get(key) is not None]
                    if not v: continue
                    b = (seeds.get(0, {}).get("models", {}).get(model, {}).get(split, {}).get("bootstrap") or {}).get(CI_KEY.get(key, ""), None)
                    rows.append([version, ds, model, split, key, len(v), float(np.mean(v)), float(np.min(v)), float(np.max(v)),
                                 b[0] if b else "", b[1] if b else "", commit])
                fams = sorted({f for _, g in got for f in g.get("per_family_auc", {})})
                for fam in fams:
                    v = [g["per_family_auc"][fam] for _, g in got if fam in g.get("per_family_auc", {})]
                    fam_rows.append([version, ds, model, split, fam, len(v), float(np.mean(v)), float(np.min(v)), float(np.max(v)), commit])
    with open(out_csv, "w", newline="") as f:
        w = csv.writer(f); w.writerow(["version", "dataset", "model", "split", "metric", "n_seeds", "mean", "min", "max", "boot95_lo_seed0", "boot95_hi_seed0", "commit"]); w.writerows(rows)
    with open(out_csv.replace(".csv", "_families.csv"), "w", newline="") as f:
        w = csv.writer(f); w.writerow(["version", "dataset", "model", "split", "family", "n_seeds", "mean_auc", "min_auc", "max_auc", "commit"]); w.writerows(fam_rows)
    R = {(r[1], r[2], r[3], r[4]): r for r in rows}
    md = [f"## Results, {version} (commit `{commit}`)", "", "Mean over seeds with (min to max). The interval in square brackets is the 95% bootstrap over sources for seed 0's model. "
          "Random forest and isolation forest do not depend on the model seed (one run).", ""]
    for ds in DATASETS:
        if ds not in runs: continue
        md += [f"### {NICE[ds]} ({len(runs[ds])} seeds)", "", "| Model | Split | Family-mean AUC | Worst family | False alerts per benign host-day at 80% in 5 min | Attacking / benign sources |", "|---|---|---|---|---|---|"]
        for model in sorted({r[2] for r in rows if r[1] == ds}):
            for split in ("dev", "final"):
                def cell(k, fmt):
                    r = R.get((ds, model, split, k))
                    if not r: return "n/a"
                    s = f"{fmt % r[6]}" + (f" ({fmt % r[7]} to {fmt % r[8]})" if r[5] > 1 else "")
                    return s + (f" [{fmt % r[9]} to {fmt % r[10]}]" if r[9] != "" else "")
                a, b = R.get((ds, model, split, "n_attacking_sources")), R.get((ds, model, split, "n_benign_sources"))
                md.append(f"| {model} | {split} | {cell('family_mean_auc', '%.3f')} | {cell('worst_family_auc', '%.3f')} | {cell('false_per_host_day_at_80pct_5min', '%.2f')} | {int(a[6]) if a else 'n/a'} / {int(b[6]) if b else 'n/a'} |")
        md.append("")
    HARD = [("unraveled", "Lateral Movement"), ("unraveled", "Establish Foothold"), ("cic2017", "Botnet"), ("cic2017", "Infiltration"), ("d2018", "Web Attack - SQL")]
    hard = [r for r in fam_rows if r[2].startswith("v0") and r[3] == "final" and any(r[1] == d and h.lower() in r[4].lower() for d, h in HARD)]
    if hard:
        md += ["### Hard set, v0, final split (family-name match; mean AUC over seeds)", "", "| Dataset | Family | AUC | seeds |", "|---|---|---|---|"]
        md += [f"| {NICE[r[1]]} | {r[4]} | {r[6]:.3f} | {r[5]} |" for r in hard]
        md.append("")
    open(out_md, "w").write("\n".join(md) + "\n")
    print(f"{len(rows)} rows, {len(fam_rows)} family rows; datasets {sorted(runs)}")


if __name__ == "__main__":
    main(*sys.argv[1:6])
