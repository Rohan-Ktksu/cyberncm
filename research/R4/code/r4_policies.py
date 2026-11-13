"""R4 alert policies on v0 and token-distance scores (PLAN.md step 19). Run from a dataset run directory's ncm/ folder.

Usage: python r4_policies.py CHECKPOINT OUT.json
Per policy variant and split (dev, final): false alert episodes per benign host-day, share of attacking sources alerted within
5 minutes of their first attack window, benign source-hours with an alert, using ncm/metrics.py.
"""
import json, os, sys
import numpy as np, pandas as pd, torch
from ncm import NCM, ewma, score, sequences
import metrics as M
import scoreboard as SB

CKPT, OUT = sys.argv[1], sys.argv[2]
torch.set_num_threads(int(os.environ.get("NCM_THREADS", 2)))
d = SB.load("data/windows.npz"); X, day, src, t, fam, T = d["X"], d["day"], d["src"], d["t"], d["family"], d["T"]
ck = torch.load(CKPT); model = NCM(h=ck["h"], arch=ck["arch"]); model.load_state_dict(ck["state"], strict=False)
seqs = sequences(day, src, t); comp, _ = score(model, X, seqs)
cal = (day == 0) & (t >= ck["cut"]); c = (comp - comp[cal].mean(0)) / comp[cal].std(0)
SCORES = {"v0": ewma(c[:, 0] + c[:, 1] + 0.5 * (c[:, 2] + c[:, 3]), seqs), "token distance": ewma(c[:, 0], seqs)}
chrono = [int(x) for x in (np.argsort(d["day_t0"]) if "day_t0" in d else np.unique(day))]
hour = np.floor(T / 3600).astype(np.int64); atk = fam > 0
SP = {k: np.isin(day, v) for k, v in d["splits"].items()}


def fixed(sc, q=0.99):
    return np.full(len(sc), np.quantile(sc[cal], q))


def daily(sc):
    """Threshold of each test day = 99th percentile of ALL windows of the previous day (no labels); fixed when the previous day is the training day."""
    thr = fixed(sc)
    for i, dd in enumerate(chrono):
        if dd != 0 and i > 0 and chrono[i - 1] != 0: thr[day == dd] = np.quantile(sc[day == chrono[i - 1]], 0.99)
    return thr


def rolling(sc, hours):
    """Threshold of each hour = 99th percentile of all windows of the previous `hours` hours; fixed while fewer than 500 windows of history."""
    thr = fixed(sc); order = np.argsort(hour, kind="stable"); hs = hour[order]; ss = sc[order]
    for h in np.unique(hour):
        lo, hi = np.searchsorted(hs, h - hours), np.searchsorted(hs, h)
        if hi - lo >= 500: thr[hour == h] = np.quantile(ss[lo:hi], 0.99)
    return thr


def per_source(sc, min_n=30):
    """Threshold of a source on a day = 99th percentile of that source's own windows of the previous day; the day's global threshold when it had fewer than min_n."""
    base = daily(sc); df = pd.DataFrame({"s": src, "d": day, "x": sc})
    g = df.groupby(["s", "d"]).x.agg(q=lambda v: np.quantile(v, 0.99), n="size")
    prev = {chrono[i]: chrono[i - 1] for i in range(1, len(chrono))}; thr = base.copy()
    idx = pd.MultiIndex.from_arrays([src, [prev.get(int(x), -1) for x in day]])
    q = g.reindex(idx); ok = (q.n.values >= min_n) & np.isfinite(q.q.values); thr[ok] = q.q.values[ok]
    return thr


def k_of_n(exceed, k, n):
    out = np.zeros(len(exceed), bool)
    for idx in seqs:
        cs = np.cumsum(exceed[idx].astype(int)); r = cs.copy(); r[n:] = cs[n:] - cs[:-n]; out[idx] = r >= k
    return out


def sustained(exceed, n):
    out = np.zeros(len(exceed), bool)
    for idx in seqs:
        cs = np.cumsum(exceed[idx].astype(int)); r = cs.copy(); r[n:] = cs[n:] - cs[:-n]; out[idx] = (r >= n) & (np.arange(len(idx)) >= n - 1)
    return out


def variants(sc):
    f, dl = fixed(sc), daily(sc)
    yield "fixed threshold", "", sc > f
    yield "daily recalibration", "", sc > dl
    for h in (1, 6, 24): yield "rolling quantile", f"{h} h", sc > rolling(sc, h)
    yield "per-source threshold", "previous day", sc > per_source(sc)
    for base, thr in (("fixed", f), ("daily", dl)):
        for k, n in ((2, 3), (3, 6), (6, 12)): yield f"k of n on {base}", f"{k} of {n}", k_of_n(sc > thr, k, n)
    hi = fixed(sc, 0.999)
    for n in (2, 3, 6): yield "two tiers", f"block above 99.9th percentile for {n} windows", sustained(sc > hi, n)


res = {"checkpoint": CKPT, "splits": {k: [int(x) for x in v] for k, v in d["splits"].items()}, "rows": []}
for sname, sc in SCORES.items():
    for fam_name, param, al in variants(sc):
        for spn, m in SP.items():
            a, s_, T_, k_ = al[m], src[m], T[m], atk[m]
            det = M.detected_within(a, s_, T_, k_, minutes=(5,))[5]
            res["rows"].append({"score": sname, "policy": fam_name, "param": param, "split": spn, "detected_5min": det,
                                "false_per_host_day": M.false_alerts_per_host_day(a, s_, T_, k_, gap_s=60.0),
                                "benign_source_hour_rate": M.benign_source_hour_rate(a, s_, T_, k_), "benign_window_rate": M.benign_window_rate(a, s_, T_, k_),
                                "attacking_sources": int(len(np.unique(s_[k_]))), "benign_sources": int(len(np.unique(s_[~np.isin(s_, np.unique(s_[k_]))])))})
    print(sname, "done", flush=True)
json.dump(res, open(OUT, "w"))
print("wrote", OUT)
