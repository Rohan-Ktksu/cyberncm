"""Summarise cross-dataset runs: mean and range over seeds, final split.
Usage: python summarize_cross.py RESULTS_DIR   (reads <a>_to_<b>_s<seed>_results.json)"""
import glob
import json
import os
import re
import sys
import numpy as np
import pandas as pd

runs = {}
for p in sorted(glob.glob(os.path.join(sys.argv[1], "*_to_*_s*_results.json"))):
    a, b, s = re.match(r"(.+)_to_(.+)_s(\d)_results\.json", os.path.basename(p)).groups()
    runs.setdefault((a, b), []).append(json.load(open(p)))

N, R = "NCM (all three signals), smoothed", "NCM risk R"
COLS = [("unsupervised", N, "final family-mean AUC"), ("unsupervised", N, "final worst family"),
        ("unsupervised", "token distance only, smoothed", "final family-mean AUC"),
        ("unsupervised", "baseline: isolation forest, smoothed", "final family-mean AUC"),
        ("unsupervised", N, "final false@1% source"), ("unsupervised", N, "final detect@1% target-cal"),
        ("unsupervised", N, "final false@1% target-cal"),
        ("supervised", R, "final family-mean AUC"), ("supervised", "RF single-window, smoothed", "final family-mean AUC")]
NAMES = ["NCM fam-mean", "NCM worst", "token dist", "iforest sm", "false@1% src-thr", "detect@1% tgt-cal",
         "false@1% tgt-cal", "sup. risk R", "sup. RF"]
rows = {}
for (a, b), rs in runs.items():
    row = {"seeds": len(rs)}
    for (part, model, metric), name in zip(COLS, NAMES):
        v = np.array([r[part][metric][model] for r in rs])
        row[name] = f"{v.mean():.3f} ({v.min():.3f}-{v.max():.3f})" if len(v) > 1 else f"{v[0]:.3f}"
    rows[f"{a} -> {b}"] = row
pd.set_option("display.width", 250)
print(pd.DataFrame(rows).T.to_string())
