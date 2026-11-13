"""Alert-quality measures shared by every experiment (PLAN.md step 11).

All functions take parallel arrays, one entry per window:
  alert      bool, the policy raised an alert (or a block) on this window
  src        source address (any hashable)
  t          window start, seconds
  is_attack  bool, ground-truth label of the window (dataset label, never a model output)
A "benign source" is one with no attack window anywhere in the data, as in R2: an address that attacks at some
point is excluded entirely, so its normal-looking traffic cannot count as a false alarm.
"""
import numpy as np
import pandas as pd


def _frame(alert, src, t, is_attack):
    d = pd.DataFrame({"a": np.asarray(alert, bool), "s": np.asarray(src), "t": np.asarray(t, float), "k": np.asarray(is_attack, bool)})
    d["attacker"] = d.s.isin(d.s[d.k].unique())
    return d


def benign_window_rate(alert, src, t, is_attack):
    """Share of windows of benign sources that carry an alert."""
    d = _frame(alert, src, t, is_attack); b = d[~d.attacker]
    return float(b.a.mean()) if len(b) else float("nan")


def benign_source_hour_rate(alert, src, t, is_attack):
    """Share of (benign source, hour) blocks that contain at least one alert (R2's 'benign source-hours')."""
    d = _frame(alert, src, t, is_attack); b = d[~d.attacker]
    return float(b.groupby([b.s, np.floor(b.t / 3600)]).a.any().mean()) if len(b) else float("nan")


def false_alerts_per_host_day(alert, src, t, is_attack, gap_s=60.0):
    """False-alert episodes per benign (source, day). An episode is a run of alert windows whose gaps are <= gap_s,
    so a source flagged on 40 consecutive windows counts once. The denominator is every (benign source, day) seen."""
    d = _frame(alert, src, t, is_attack); b = d[~d.attacker].copy()
    if b.empty:
        return float("nan")
    b["day"] = np.floor(b.t / 86400)
    episodes = 0
    for _, g in b[b.a].groupby(["s", "day"]):
        episodes += 1 + int((np.diff(np.sort(g.t.values)) > gap_s).sum())
    return episodes / b.groupby(["s", "day"]).ngroups


def detected_within(alert, src, t, is_attack, minutes=(1, 5, 60)):
    """Share of attacking sources with an alert from their first attack window up to N minutes later.
    Alerts before the first attack window do not count: that would reward flagging normal traffic."""
    d = _frame(alert, src, t, is_attack); out = {m: 0 for m in minutes}; n = 0
    for _, g in d[d.attacker].groupby("s"):
        first = g.t[g.k].min(); hit = g.t[g.a & (g.t >= first)]; n += 1
        for m in minutes:
            out[m] += int(len(hit) > 0 and hit.min() <= first + 60 * m)
    return {m: (v / n if n else float("nan")) for m, v in out.items()}


def attack_windows_blocked(blocked, is_attack):
    """Share of attack windows that fall under an active block."""
    k = np.asarray(is_attack, bool)
    return float(np.asarray(blocked, bool)[k].mean()) if k.any() else float("nan")
