"""R11: adaptation levels for a new site. Usage: python r11_adapt.py CKPT_A WINDOWS_B OUT.json SEED [BUDGET_MINUTES_COMMA_SEPARATED]"""
import json, os, sys
import numpy as np, torch
from sklearn.cluster import MiniBatchKMeans
from ncm import NCM, ewma, score, sequences
import scoreboard as SB

CKPT, WB, OUT, SEED = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4])
torch.set_num_threads(int(os.environ.get("NCM_THREADS", 2)))
BUDGETS = [float(x) for x in sys.argv[5].split(",")] if len(sys.argv) > 5 else [360.0, 60.0, 10.0]
if not BUDGETS or any(not np.isfinite(x) or x <= 0 for x in BUDGETS):
    raise ValueError("Adaptation budgets must be positive finite minutes")
d = SB.load(WB); d["fam"] = d["family"]; X, day, src, t = d["X"], d["day"], d["src"], d["t"]; names = d["names"]
seqs = sequences(day, src, t); mon = day == 0
ck = torch.load(CKPT)


def fresh():
    m = NCM(h=ck["h"], arch=ck["arch"]); m.load_state_dict(ck["state"], strict=False); m.eval(); return m


def spans(minutes):
    t0 = t[mon].min()
    if minutes is None:
        cut = np.quantile(t[mon], 0.8); return mon & (t < cut), mon & (t >= cut)
    end = t0 + minutes * 60; cut = t0 + 0.8 * minutes * 60
    return mon & (t < cut), mon & (t >= cut) & (t < end)


def states(model):
    """One GRU pass: states of every window, and the state before each window."""
    _, S = score(model, X, seqs); prev = np.zeros_like(S)
    for idx in seqs: prev[idx[1:]] = S[idx[:-1]]
    return S, prev


@torch.no_grad()
def components(model, S, prev):
    z = model.normalize(torch.from_numpy(X)); out = []
    for i in range(0, len(X), 200000):
        out.append(model.components(z[i:i + 200000], torch.from_numpy(S[i:i + 200000]), torch.from_numpy(prev[i:i + 200000])).numpy())
    return np.concatenate(out)


def km(a, k):
    k = int(min(k, max(2, len(a) // 2))); return torch.from_numpy(MiniBatchKMeans(k, n_init=3, random_state=SEED).fit(a).cluster_centers_.astype(np.float32))


def v0_score(comp, mu, sd):
    c = (comp - mu) / sd; return ewma(c[:, 0] + c[:, 1] + 0.5 * (c[:, 2] + c[:, 3]), seqs)


sps = {k: SB.Split(d, v) for k, v in d["splits"].items()}
res = {"seed": SEED, "models": {}, "budgets": {},
       "protocol": {"target": WB, "checkpoint": CKPT, "backbone_retrained": False,
                    "train_span_seconds": float(np.ptp(t[mon])), "day0_windows": int(mon.sum()),
                    "day0_attack_windows": int((mon & (d["family"] > 0)).sum()),
                    "splits": d["splits"], "requested_budget_minutes": BUDGETS}}
res["protocol"]["train_absolute_start"] = float(d["T"][mon].min())
res["protocol"]["train_absolute_end"] = float(d["T"][mon].max())
res["protocol"]["evaluation_chronology"] = {
    name: {"start": float(d["T"][np.isin(day, days)].min()),
           "end": float(d["T"][np.isin(day, days)].max()),
           "entirely_after_day0": bool((d["T"][np.isin(day, days)] > d["T"][mon].max()).all())}
    for name, days in d["splits"].items()}
if res["protocol"]["day0_attack_windows"]:
    raise ValueError("This learning-curve protocol requires an attack-free day-0 span")


def record(name, sc, cal):
    if not np.isfinite(sc).all():
        raise ValueError(f"Nonfinite scores for {name}")
    thr = float(np.quantile(sc[cal], 0.99)); res["models"][name] = {k: SB.report(sp, sc, names, thr) for k, sp in sps.items()}
    print(name, {k: round(res["models"][name][k]["family_mean_auc"], 3) for k in sps}, flush=True)


# level 1: A's everything
m1 = fresh(); S1, P1 = states(m1); c1 = components(m1, S1, P1); mu_a, sd_a = m1.calib[:, 0].numpy(), m1.calib[:, 1].numpy()
fit, cal = spans(None); record("L1 threshold only", v0_score(c1, mu_a, sd_a), cal)
for label, minutes in [("full", None)] + [(f"{x:g} min", x) for x in BUDGETS]:
    fit, cal = spans(minutes)
    res["budgets"][label] = {"requested_minutes": minutes, "fit_windows": int(fit.sum()),
                              "calibration_windows": int(cal.sum()),
                              "fit_sources": int(len(np.unique(src[fit]))),
                              "calibration_sources": int(len(np.unique(src[cal]))),
                              "observed_span_seconds": float(np.ptp(t[fit | cal])) if (fit | cal).any() else None,
                              "status": "pending",
                              "hourly_windows_utc": np.bincount(((d["T"][fit | cal] % 86400) // 3600).astype(int), minlength=24).tolist()}
    if fit.sum() < 50 or cal.sum() < 20:
        res["budgets"][label]["status"] = "skipped: too few windows"
        print("skip", label, "too few windows"); continue
    m = fresh(); m.mean.copy_(torch.from_numpy(X[fit].mean(0))); m.std.copy_(torch.from_numpy(X[fit].std(0) + 1e-3))
    S, P = states(m); c2 = components(m, S, P); record(f"L2 + target normalisation @ {label}", v0_score(c2, mu_a, sd_a), cal)
    m.codebook.data = km(m.normalize(torch.from_numpy(X[fit])).numpy(), 512); m.state_codebook.data = km(S[fit], 512)  # .data: fewer than 512 centres when fit windows are few
    c3 = components(m, S, P); record(f"L3 + target vocabularies and calibration @ {label}", v0_score(c3, c3[cal].mean(0), c3[cal].std(0)), cal)
    res["budgets"][label]["status"] = "complete"
    json.dump(res, open(OUT, "w"), indent=1)
json.dump(res, open(OUT, "w"), indent=1); print("wrote", OUT)
