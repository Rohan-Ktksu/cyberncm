"""R12: what does sharing blocks between sites buy? Usage: python r12_sim.py SITE_DIR CKPT OUT.json SEED [SCOREBOARD_WINDOWS_NPZ]
SITE_DIR holds windows.npz and pair_map.npz written by prep_site.py (windows keyed by (source, site)); CKPT is the scoreboard v0 checkpoint.
Each site refits normalisation, both codebooks and the calibration on its own day-0 windows (R11 level 3) and scores its own windows.
Block rule: a window completes a block when at least 2 of the source's last 3 windows at that site scored above the 99.5th percentile of the site's calibration windows.
Policies: none (own blocks only), share_all (a block anywhere applies at every site), two_agree (a shared block applies only if at least 2 OTHER sites have the source blocked; own blocks always apply).
Expiry: a block (own or shared) lasts E seconds after the window that triggered it, E = 30 or infinite."""
import json, os, sys
import numpy as np, torch
from sklearn.cluster import MiniBatchKMeans
from ncm import NCM, ewma, score, sequences

SD, CKPT, OUT, SEED = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4])
torch.set_num_threads(int(os.environ.get("NCM_THREADS", 2))); W = 5.0; INF = float("inf"); RATE_PER_HOUR = 5.0
z = np.load(os.path.join(SD, "windows.npz"), allow_pickle=True); pm = np.load(os.path.join(SD, "pair_map.npz"))
X = z["X"].astype(np.float32); day, idv, t, fam = z["day"], z["src"], z["t"], z["family"]
site_of = pm["site"][idv]; source_of = pm["source"][idv]; K = int(pm["site"].max()) + 1
if len(sys.argv) > 5:   # optional: keep only the sources of the scoreboard windows (CSE-CIC-IDS2018 uses a 10% source subsample)
    keep = np.isin(source_of, np.unique(np.load(sys.argv[5], allow_pickle=True)["src"]))
    X, day, idv, t, fam, site_of, source_of = X[keep], day[keep], idv[keep], t[keep], fam[keep], site_of[keep], source_of[keep]
present = sorted(set(np.unique(day).tolist()) - {0})
order = [int(x) for x in np.argsort(z["day_t0"]) if int(x) in present] if "day_t0" in z.files else present
SPLIT = {d: ("dev" if i < len(order) // 2 else "final") for i, d in enumerate(order)}
ck = torch.load(CKPT)


def fresh():
    m = NCM(h=ck["h"], arch=ck["arch"]); m.load_state_dict(ck["state"], strict=False); m.eval(); return m


def refit_score(rows):
    Xa, d_, i_, t_ = X[rows], day[rows], idv[rows], t[rows]
    mon = d_ == 0; cal = mon & (t_ >= np.quantile(t_[mon], 0.8)); fit = mon & ~cal
    m = fresh(); m.mean.copy_(torch.from_numpy(Xa[fit].mean(0))); m.std.copy_(torch.from_numpy(Xa[fit].std(0) + 1e-3))
    seqs = sequences(d_, i_, t_); _, S = score(m, Xa, seqs); prev = np.zeros_like(S)
    for idx in seqs: prev[idx[1:]] = S[idx[:-1]]
    km = lambda a: torch.from_numpy(MiniBatchKMeans(int(min(512, max(2, len(a) // 2))), n_init=3, random_state=SEED).fit(a).cluster_centers_.astype(np.float32))
    m.codebook.data = km(m.normalize(torch.from_numpy(Xa[fit])).numpy()); m.state_codebook.data = km(S[fit])
    with torch.no_grad():
        zz = m.normalize(torch.from_numpy(Xa)); c = np.concatenate([m.components(zz[i:i + 200000], torch.from_numpy(S[i:i + 200000]), torch.from_numpy(prev[i:i + 200000])).numpy() for i in range(0, len(Xa), 200000)])
    cc = (c - c[cal].mean(0)) / c[cal].std(0); sc = ewma(cc[:, 0] + cc[:, 1] + 0.5 * (cc[:, 2] + cc[:, 3]), seqs)
    return sc, float(np.quantile(sc[cal], 0.995)), int(fit.sum())


alert = np.zeros(len(X), bool); info = {}
for j in range(K):
    rows = np.flatnonzero(site_of == j); sc, thr, nfit = refit_score(rows); alert[rows] = sc > thr; info[j] = {"windows": int(len(rows)), "day0_fit_windows": nfit, "threshold": thr}
    print("site", j, info[j], flush=True)
# rule times: >= 2 of the last 3 windows (same source at the same site, same day) above the threshold
o = np.lexsort((t, idv, day)); a = alert[o].astype(int); g = (day[o].astype(np.int64) << 40) + idv[o]
same1 = np.r_[False, g[1:] == g[:-1]]; same2 = np.r_[False, False, g[2:] == g[:-2]]
a1 = np.r_[0, a[:-1]] * same1; a2 = np.r_[0, 0, a[:-2]] * same2
rule = np.zeros(len(X), bool); rule[o] = (a + a1 + a2) >= 2
tau = {}   # (day, source, site) -> sorted completion times of rule windows
for i in np.flatnonzero(rule & (day > 0)): tau.setdefault((int(day[i]), int(source_of[i]), int(site_of[i])), []).append(float(t[i] + W))
tau = {k: np.array(sorted(v)) for k, v in tau.items()}
atk = (fam > 0) & (day > 0); atk_sources = {(int(d), int(s)) for d, s in zip(day[atk], source_of[atk])}
rows_by = {}
for i in np.flatnonzero(day > 0): rows_by.setdefault((int(day[i]), int(source_of[i])), []).append(i)
rows_by = {k: np.array(v) for k, v in rows_by.items()}


def active(T, tt, E):
    idx = np.searchsorted(T, tt, "right") - 1; ok = idx >= 0
    return ok if E == INF else ok & (tt < T[np.clip(idx, 0, None)] + E)


def evaluate(forged):
    """forged: {(day, source): times of forged blocks issued by site 0}."""
    T = {k: v.copy() for k, v in tau.items()}
    for (d, s), ts in forged.items(): T[(d, s, 0)] = np.sort(np.r_[T.get((d, s, 0), np.array([])), ts])
    keys = {(d, s) for (d, s, _) in T}
    out = {}
    for E in (30.0, INF):
        for pol, m in (("none", None), ("share_all", 1), ("two_agree", 2)):
            out[(E, pol)] = {sp: {"att_windows": 0, "att_prevented": 0, "benign_windows_nosite": 0, "benign_blocked_windows": 0, "benign_combos_nosite": 0, "benign_combos_blocked": 0,
                                  "benign_windows_honest": 0, "benign_blocked_honest": 0} for sp in ("dev", "final")}
    ttb = {sp: {pol: [] for pol in ("none", "share_all", "two_agree")} for sp in ("dev", "final")}; n_pairs = {"dev": 0, "final": 0}
    for (d, s), R in rows_by.items():
        sp = SPLIT[d]; is_atk = (d, s) in atk_sources; isb = ~is_atk
        fam_r, site_r, t_r = fam[R], site_of[R], t[R]
        own_has = {j: (d, s, j) in T for j in range(K)}
        for E in (30.0, INF):
            if (d, s) in keys:
                A = np.zeros((K, len(R)), bool)
                for j in range(K):
                    if (d, s, j) in T: A[j] = active(T[(d, s, j)], t_r, E)
                own = A[site_r, np.arange(len(R))]; oth = A.sum(0) - own
            else: own = np.zeros(len(R), bool); oth = np.zeros(len(R), int)
            for pol, m in (("none", None), ("share_all", 1), ("two_agree", 2)):
                blocked = own if m is None else own | (oth >= m); c = out[(E, pol)][sp]
                if is_atk:
                    ma = fam_r > 0; c["att_windows"] += int(ma.sum()); c["att_prevented"] += int((blocked & ma).sum())
                else:
                    nos = np.array([not own_has[j] for j in site_r]); c["benign_windows_nosite"] += int(nos.sum()); c["benign_blocked_windows"] += int((blocked & nos).sum())
                    for j in range(K):
                        sel = (site_r == j) & nos
                        if sel.any(): c["benign_combos_nosite"] += 1; c["benign_combos_blocked"] += int(blocked[sel].any())
                    hs = site_r != 0; c["benign_windows_honest"] += int(hs.sum()); c["benign_blocked_honest"] += int((blocked & hs).sum())
        if is_atk:
            for j in range(K):
                sel = (site_r == j) & (fam_r > 0)
                if not sel.any(): continue
                n_pairs[sp] += 1; first_pkt = float(t_r[sel].min()); firsts = {jj: T[(d, s, jj)][0] for jj in range(K) if (d, s, jj) in T}
                others = sorted(v for jj, v in firsts.items() if jj != j); own_first = firsts.get(j, INF)
                for pol, m in (("none", None), ("share_all", 1), ("two_agree", 2)):
                    b = own_first if m is None else min(own_first, others[m - 1] if len(others) >= m else INF)
                    ttb[sp][pol].append(b - first_pkt)
    return out, ttb, n_pairs


rng = np.random.default_rng(SEED); forged = {}
benign_pure = sorted({k for k in rows_by if k not in atk_sources})
for d in order:
    dd = [k for k in benign_pure if k[0] == d]; hours = (t[day == d].max() - t[day == d].min()) / 3600
    n = int(round(RATE_PER_HOUR * hours))
    if dd and n:
        pick = rng.choice(len(dd), n, replace=True)
        for pi in pick: forged.setdefault(dd[pi], []).append(float(rng.uniform(t[day == d].min(), t[day == d].max())))
honest, ttb, n_pairs = evaluate({}); lying, _, _ = evaluate({k: np.array(v) for k, v in forged.items()})
res = {"seed": SEED, "K": K, "sites": info, "forged_blocks_per_hour": RATE_PER_HOUR, "forged_total": int(sum(len(v) for v in forged.values())), "attacker_site_pairs": n_pairs, "scenarios": {}}
for scen, o_ in (("honest", honest), ("lying_site0", lying)):
    res["scenarios"][scen] = {("E30" if E == 30.0 else "Einf") + "_" + pol: v for (E, pol), v in o_.items()}
res["time_to_block"] = {sp: {pol: [None if not np.isfinite(x) else float(x) for x in v] for pol, v in d_.items()} for sp, d_ in ttb.items()}
json.dump(res, open(OUT, "w"), indent=1)
f = res["scenarios"]["honest"]; print({k: round(v["final"]["att_prevented"] / max(v["final"]["att_windows"], 1), 3) for k, v in f.items()}); print("wrote", OUT)
