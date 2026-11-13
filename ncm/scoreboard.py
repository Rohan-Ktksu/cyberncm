"""Scoreboard harness (PLAN.md section 4, step 14).

Usage, from the ncm/ folder with data/windows.npz in place:
    python scoreboard.py CHECKPOINT OUT.json [--seed N] [--boot B] [--no-rf]

Scores every window with v0 (NCM, all three signals, smoothed) and three baselines (token distance smoothed,
isolation forest smoothed, random forest on single windows trained without the held-out family), then reports per split:
  family-mean AUC and worst family   family vs the benign windows of the same split, families with >= 10 windows in it
  false alerts per benign host-day   at the lowest threshold that catches >= 80% of attacking sources within 5 minutes
                                     of their first attack window (metrics.py definitions; an episode is a run of alert
                                     windows with gaps <= 60 s)
  detect/false at the 1% threshold   threshold = 99th percentile of the benign calibration span (reference only)
Splits: day 0 is the benign training span; the remaining days, in time order, are cut in two halves: dev, then final.
(5-day datasets: dev = days 1-2, final = days 3-4, as in evaluate.py.) With --boot B, also a bootstrap that resamples
SOURCES (not windows) B times, for the family-mean AUC and for the false-alert metric.
"""
import argparse, json, os, sys, time
import numpy as np
import torch
from sklearn.ensemble import IsolationForest, RandomForestClassifier
from sklearn.metrics import roc_auc_score
from ncm import NCM, ewma, score, sequences
import metrics as M

DETECT_S, TARGET, GAP_S, MIN_WIN = 300.0, 0.8, 60.0, 10
NT = int(os.environ.get("NCM_THREADS", 2))  # CPU threads for torch and the forests; speed only


def load(path):
    z = np.load(path, allow_pickle=True)
    d = {k: z[k] for k in z.files}
    d["T"] = d["day_t0"][d["day"]] + d["t"] if "day_t0" in d else d["day"] * 86400.0 + d["t"]
    d["names"] = [str(n) for n in d["family_names"]]
    present = set(np.unique(d["day"]).tolist()) - {0}
    order = [int(x) for x in np.argsort(d["day_t0"]) if int(x) in present] if "day_t0" in d else sorted(present)
    h = len(order) // 2
    d["splits"] = {"dev": order[:h], "final": order[h:]}
    return d


def wauc(sc, pos, w):
    """Weighted AUC with half credit for ties, independent of row order."""
    if w[pos].sum() == 0 or w[~pos].sum() == 0:
        return np.nan
    return float(roc_auc_score(pos, sc, sample_weight=w))


class Split:
    """Everything about one split that does not depend on the score."""
    def __init__(self, d, days):
        sp = np.isin(d["day"], days); self.idx = np.flatnonzero(sp)
        self.src, self.T, self.fam = d["src"][sp], d["T"][sp], d["fam"][sp]
        self.atk = self.fam > 0
        self.ids, self.sid = np.unique(self.src, return_inverse=True)
        n = len(self.ids)
        self.att_src = np.zeros(n, bool); self.att_src[self.sid[self.atk]] = True
        first = np.full(n, np.inf); np.minimum.at(first, self.sid[self.atk], self.T[self.atk])
        self.in_win = self.att_src[self.sid] & (self.T >= first[self.sid]) & (self.T <= first[self.sid] + DETECT_S)
        ben = ~self.att_src[self.sid]
        self.b_idx = np.flatnonzero(ben)  # windows of benign sources, sorted by (host-day, time)
        day = np.floor(self.T[self.b_idx] / 86400)
        key = self.sid[self.b_idx].astype(np.int64) * 100000 + day.astype(np.int64)
        o = np.lexsort((self.T[self.b_idx], key)); self.b_idx = self.b_idx[o]; key = key[o]
        self.g_key, self.g = np.unique(key, return_inverse=True)
        self.g_src = (self.g_key // 100000).astype(int)  # source of each benign host-day
        self.fams = [f for f in np.unique(self.fam[self.atk]) if (self.fam == f).sum() >= MIN_WIN]

    def catch_thr(self, sc, cnt):
        """Lowest threshold that catches >= TARGET of the (weighted) attacking sources within DETECT_S."""
        m = np.full(len(self.ids), -np.inf)
        np.maximum.at(m, self.sid[self.in_win], sc[self.in_win])
        a = np.repeat(m[self.att_src], cnt[self.att_src].astype(int))
        if len(a) == 0: return np.nan
        a.sort(); k = int(np.floor((1 - TARGET) * len(a)))
        return a[k - 1] if k >= 1 else a[0] - 1e-9

    def false_per_host_day(self, sc, thr, cnt):
        al = sc[self.b_idx] > thr
        ga, ta = self.g[al], self.T[self.b_idx][al]
        if len(ga) == 0: return 0.0
        start = np.r_[True, (ga[1:] != ga[:-1]) | (ta[1:] - ta[:-1] > GAP_S)]
        ep = np.bincount(ga[start], minlength=len(self.g_key))
        w = cnt[self.g_src]
        return float((ep * w).sum() / w.sum())


def report(sp, sc, names, cal_thr, cnt=None):
    ones = np.ones(len(sp.ids))
    fa_thr = sp.catch_thr(sc[sp.idx], ones)
    fam_auc = {names[f]: float(roc_auc_score(sp.fam[(sp.fam == 0) | (sp.fam == f)] == f, sc[sp.idx][(sp.fam == 0) | (sp.fam == f)])) for f in sp.fams}
    a = np.array(list(fam_auc.values())); s = sc[sp.idx]
    al1 = s > cal_thr
    out = {"family_mean_auc": float(a.mean()) if len(a) else None, "worst_family_auc": float(a.min()) if len(a) else None,
           "n_families": len(a), "n_attacking_sources": int(sp.att_src.sum()), "n_benign_sources": int((~sp.att_src).sum()),
           "fa_threshold": float(fa_thr), "false_per_host_day_at_80pct_5min": sp.false_per_host_day(sc[sp.idx], fa_thr, ones) if np.isfinite(fa_thr) else None,
           "detect_within_5min_check": M.detected_within(s > fa_thr, sp.src, sp.T, sp.atk, minutes=(5,))[5] if np.isfinite(fa_thr) else None,
           "metrics_py_false_per_host_day": M.false_alerts_per_host_day(s > fa_thr, sp.src, sp.T, sp.atk, gap_s=GAP_S) if np.isfinite(fa_thr) else None,
           "detect_1pct_cal": float(al1[sp.atk].mean()) if sp.atk.any() else None, "false_window_rate_1pct_cal": M.benign_window_rate(al1, sp.src, sp.T, sp.atk),
           "benign_source_hour_rate_1pct_cal": M.benign_source_hour_rate(al1, sp.src, sp.T, sp.atk), "per_family_auc": fam_auc}
    return out


def bootstrap(sp, sc, B, rng):
    auc, fa = [], []
    s = sc[sp.idx]
    for _ in range(B):
        cnt = rng.multinomial(len(sp.ids), np.ones(len(sp.ids)) / len(sp.ids)).astype(float); w = cnt[sp.sid]
        vals = [wauc(s[(sp.fam == 0) | (sp.fam == f)], (sp.fam == f)[(sp.fam == 0) | (sp.fam == f)], w[(sp.fam == 0) | (sp.fam == f)]) for f in sp.fams]
        auc.append(np.nanmean(vals) if np.isfinite(vals).any() else np.nan)
        thr = sp.catch_thr(s, cnt)
        fa.append(sp.false_per_host_day(s, thr, cnt) if np.isfinite(thr) else np.nan)
    q = lambda v: [float(x) for x in np.nanpercentile(v, [2.5, 97.5])] if np.isfinite(v).any() else None
    return {"family_mean_auc_ci95": q(auc), "false_per_host_day_ci95": q(fa), "B": B}


def rf_scores(d, X, seqs, fam, day, T, sp_all, cap=0):
    """Random forest on single windows, trained without the held-out family (evaluate.py Part 2): benign windows of
    even 30-minute blocks plus attack windows of the other families; scored against benign windows of odd blocks.
    Returns {family: smoothed attack probability for every window}."""
    test = day > 0
    block = (T // 1800).astype(int) % 2
    ben_tr = test & (fam == 0) & (block == 0)
    if cap and ben_tr.sum() > cap:  # time guard on the big datasets: a fixed random subset of the benign training windows
        keep = np.random.default_rng(0).choice(np.flatnonzero(ben_tr), cap, replace=False); ben_tr = np.zeros(len(fam), bool); ben_tr[keep] = True
    out = {}
    for f in sorted({int(x) for sp in sp_all for x in sp.fams}):
        tr = ben_tr | (test & (fam > 0) & (fam != f))
        rf = RandomForestClassifier(n_estimators=100, n_jobs=NT, class_weight="balanced", random_state=0)
        out[f] = ewma(rf.fit(X[tr], fam[tr] > 0).predict_proba(X)[:, 1], seqs)
        print(f"  rf without family {d['names'][f]}: done", flush=True)
    return out, block


def rf_fair(d, X, seqs, fam, day, sp_final, cap=0):
    """Fair supervised baseline: trained only on day 0 benign windows plus attack windows of the dev split, never on the
    test period it is scored on. For each family with enough final windows: that family is held out (all its windows),
    the rest of the dev attacks are positives, the forest is scored on the final split against ALL its benign windows."""
    names = d["names"]; fin_days = d["splits"]["final"]; dev_days = d["splits"]["dev"]
    fin = np.isin(day, fin_days); seqs_f = [q for q in seqs if fin[q[0]]]
    ben_tr = np.flatnonzero(day == 0)
    if cap and len(ben_tr) > cap: ben_tr = np.random.default_rng(0).choice(ben_tr, cap, replace=False)
    out = {}
    for f in sp_final.fams:
        pos = np.flatnonzero(np.isin(day, dev_days) & (fam > 0) & (fam != f))
        if len(pos) < MIN_WIN: out[names[f]] = None; continue
        tr = np.r_[ben_tr, pos]
        rf = RandomForestClassifier(n_estimators=100, n_jobs=NT, class_weight="balanced", random_state=0).fit(X[tr], fam[tr] > 0)
        P = np.zeros(len(X)); fi = np.flatnonzero(fin); P[fi] = rf.predict_proba(X[fi])[:, 1]
        sc = ewma(P, seqs_f); m = (sp_final.fam == 0) | (sp_final.fam == f)
        out[names[f]] = float(roc_auc_score(sp_final.fam[m] == f, sc[sp_final.idx][m]))
        print(f"  fair rf without family {names[f]}: {out[names[f]]:.3f}", flush=True)
    return out


def main(ckpt, outp, seed, B, use_rf, cap, rf_only=False, fair=False):
    t0 = time.time()
    d = load("data/windows.npz"); X, day, src, t, fam, T = d["X"], d["day"], d["src"], d["t"], d["fam"] if "fam" in d else d["family"], d["T"]
    d["fam"] = fam; names = d["names"]
    ck = torch.load(ckpt); model = NCM(h=ck["h"], arch=ck["arch"]); model.load_state_dict(ck["state"], strict=False)
    seqs = sequences(day, src, t); comp, _ = score(model, X, seqs)
    cal, train = (day == 0) & (t >= ck["cut"]), (day == 0) & (t < ck["cut"])
    c = (comp - comp[cal].mean(0)) / comp[cal].std(0)
    Zn = model.normalize(torch.from_numpy(X)).numpy()
    iso = -IsolationForest(n_estimators=200, random_state=0).fit(Zn[train]).score_samples(Zn)
    models = {"v0 NCM, smoothed": ewma(c[:, 0] + c[:, 1] + 0.5 * (c[:, 2] + c[:, 3]), seqs),
              "token distance, smoothed": ewma(c[:, 0], seqs), "isolation forest, smoothed": ewma(iso, seqs)}
    sps = {k: Split(d, v) for k, v in d["splits"].items()}
    if rf_only or fair == "only": models = {}
    if fair == "only": use_rf = False
    rng = np.random.default_rng(seed)
    res = {"dataset_windows": int(len(X)), "seed": seed, "splits": {k: [int(x) for x in v] for k, v in d["splits"].items()}, "models": {}}
    for name, sc in models.items():
        thr = float(np.quantile(sc[cal], 0.99)); res["models"][name] = {}
        for k, sp in sps.items():
            res["models"][name][k] = report(sp, sc, names, thr)
            if B: res["models"][name][k]["bootstrap"] = bootstrap(sp, sc, B, rng)
        print(name, {k: round(res["models"][name][k]["family_mean_auc"] or 0, 3) for k in sps}, f"{time.time() - t0:.0f}s", flush=True)
    if use_rf:
        rfs, _ = rf_scores(d, X, seqs, fam, day, T, list(sps.values()), cap)
        name = "random forest, single windows (leave-one-family-out)"; res["models"][name] = {}
        for k, sp in sps.items():
            a = {}
            for f in sp.fams:
                held_out = (sp.T // 1800).astype(int) % 2 == 1  # benign windows of odd blocks: never used to train the forest
                m = ((sp.fam == 0) & held_out) | (sp.fam == f); a[names[f]] = float(roc_auc_score(sp.fam[m] == f, rfs[f][sp.idx][m]))
            v = np.array(list(a.values()))
            res["models"][name][k] = {"family_mean_auc": float(v.mean()) if len(v) else None, "worst_family_auc": float(v.min()) if len(v) else None,
                                      "n_families": len(v), "per_family_auc": a, "note": "supervised; no false-alert metric (a score per held-out family)"}
        print(name, {k: round(res["models"][name][k]["family_mean_auc"] or 0, 3) for k in sps}, f"{time.time() - t0:.0f}s", flush=True)
    if fair:
        a = rf_fair(d, X, seqs, fam, day, sps["final"], cap); v = np.array([x for x in a.values() if x is not None])
        res["models"]["random forest, fair (day 0 benign + dev-split attacks of other families)"] = {"final": {
            "family_mean_auc": float(v.mean()) if len(v) else None, "worst_family_auc": float(v.min()) if len(v) else None, "n_families": len(v),
            "per_family_auc": {k: x for k, x in a.items() if x is not None}, "note": "supervised, never trained on the test period; final split only"}}
        print("fair rf", {k: round(x, 3) for k, x in a.items() if x is not None}, "mean", round(float(v.mean()), 3) if len(v) else None, flush=True)
    json.dump(res, open(outp, "w"), indent=1)
    print("wrote", outp, f"{time.time() - t0:.0f}s")


if __name__ == "__main__":
    ap = argparse.ArgumentParser(); ap.add_argument("ckpt"); ap.add_argument("out")
    ap.add_argument("--seed", type=int, default=0); ap.add_argument("--boot", type=int, default=0); ap.add_argument("--no-rf", action="store_true"); ap.add_argument("--rf-cap", type=int, default=200000); ap.add_argument("--rf-only", action="store_true"); ap.add_argument("--fair-rf", choices=["also", "only"], default=None)
    a = ap.parse_args(); torch.set_num_threads(NT)
    main(a.ckpt, a.out, a.seed, a.boot, not a.no_rf, a.rf_cap, a.rf_only, ("only" if a.fair_rf == "only" else bool(a.fair_rf)))
