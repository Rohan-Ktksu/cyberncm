"""R7 stress tests on v0 windows. Usage: python r7_stress.py MODE CKPT WINDOWS OUT.json SEED   (MODE: mimicry | poison)"""
import json, os, sys
import numpy as np, torch
from sklearn.cluster import MiniBatchKMeans
from ncm import NCM, ewma, score, sequences

MODE, CKPT, WIN, OUT, SEED = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], int(sys.argv[5])
torch.set_num_threads(int(os.environ.get("NCM_THREADS", 2))); MIN_WIN = 10
z = np.load(WIN, allow_pickle=True); X = z["X"].astype(np.float32); day, src, t, fam = z["day"], z["src"], z["t"], z["family"]
names = [str(n) for n in z["family_names"]]; FN = [str(n) for n in z["features"]]; ck = torch.load(CKPT)
if MODE not in ("poison", "mimicry", "mimicryall", "mimicrysample"):
    raise ValueError(f"Unknown stress mode: {MODE}")
ONLY_FAMILY = sys.argv[6] if len(sys.argv) > 6 else None
if ONLY_FAMILY is not None and (MODE != "poison" or ONLY_FAMILY not in names):
    raise ValueError("Optional family must name an existing family in poison mode")
present = sorted(set(np.unique(day).tolist()) - {0})
order = [int(x) for x in np.argsort(z["day_t0"]) if int(x) in present] if "day_t0" in z.files else present
h = len(order) // 2; SPLITS = {"dev": order[:h], "final": order[h:]}
# features whose value the sender cannot set: they depend on what the victim answers
VICTIM = {"log_bwd_bytes", "log_bwd_pkts", "dir_byte_ratio", "unanswered_frac", "rst_ratio", "fin_ratio"}
CTRL = np.array([f not in VICTIM or MODE == "mimicryall" for f in FN])   # mimicryall: exploratory worst case, every feature movable
ALPHAS = [0, 0.1, 0.2, 0.25, 0.3, 0.4, 0.5, 0.6, 0.7, 0.75, 0.8, 0.9, 1.0]
POISON = [0.005, 0.01, 0.02, 0.05]


def model_fresh():
    m = NCM(h=ck["h"], arch=ck["arch"]); m.load_state_dict(ck["state"], strict=False); m.eval(); return m


def v0(comp, mu, sd, seqs):
    c = (comp - mu) / sd; return ewma(c[:, 0] + c[:, 1] + 0.5 * (c[:, 2] + c[:, 3]), seqs)


@torch.no_grad()
def components(model, Xa, S, prev):
    zz = model.normalize(torch.from_numpy(Xa)); out = []
    for i in range(0, len(Xa), 200000):
        out.append(model.components(zz[i:i + 200000], torch.from_numpy(S[i:i + 200000]), torch.from_numpy(prev[i:i + 200000])).numpy())
    return np.concatenate(out)


def run(model, Xa, day_, src_, t_, mu, sd):
    seqs = sequences(day_, src_, t_); _, S = score(model, Xa, seqs); prev = np.zeros_like(S)
    for idx in seqs: prev[idx[1:]] = S[idx[:-1]]
    return v0(components(model, Xa, S, prev), mu, sd, seqs), S


def detection(sc, thr, mask_rows, fam_, famlist):
    out = {}
    for sp, days in SPLITS.items():
        out[sp] = {names[f]: float((sc[mask_rows & np.isin(day, days) & (fam_ == f)] > thr).mean()) for f in famlist[sp]}
    return out


fams = {sp: [f for f in range(1, len(names)) if (np.isin(day, d) & (fam == f)).sum() >= MIN_WIN] for sp, d in SPLITS.items()}
mon = day == 0; cal = mon & (t >= np.quantile(t[mon], 0.8)); fit = mon & ~cal
res = {"mode": MODE, "seed": SEED, "features_controlled": [f for f, c in zip(FN, CTRL) if c], "families": {k: [names[f] for f in v] for k, v in fams.items()}}

if MODE in ("mimicry", "mimicryall", "mimicrysample"):
    m = model_fresh(); mu_c, sd_c = m.calib[:, 0].numpy(), m.calib[:, 1].numpy()
    seqs0 = sequences(day, src, t); _, S0 = score(m, X, seqs0); P0 = np.zeros_like(S0)
    for idx in seqs0: P0[idx[1:]] = S0[idx[:-1]]
    s0 = v0(components(m, X, S0, P0), mu_c, sd_c, seqs0); thr = float(np.quantile(s0[cal], 0.99))   # threshold from the benign calibration span
    benign_mu = X[fit & (fam == 0)].mean(0); atk_src = np.unique(src[fam > 0]); rows = np.isin(src, atk_src)   # only sources with attack windows can change
    res["threshold"] = thr; res["curve"] = {}
    pool_b = X[fit & (fam == 0)]; TGT = pool_b[np.random.default_rng(SEED).integers(len(pool_b), size=int((fam > 0).sum()))]   # mimicrysample: each attack window moves toward one random real benign window
    for a in ALPHAS:
        Xa = X.copy(); am = fam > 0; Xa[np.ix_(am, CTRL)] = X[np.ix_(am, CTRL)] + a * (TGT[:, CTRL] - X[np.ix_(am, CTRL)]) if MODE == "mimicrysample" else X[np.ix_(am, CTRL)] + a * (benign_mu[CTRL] - X[np.ix_(am, CTRL)])
        sub = np.flatnonzero(rows); sc_sub, _ = run(m, Xa[sub], day[sub], src[sub], t[sub], mu_c, sd_c)
        sc = s0.copy(); sc[sub] = sc_sub
        res["curve"][str(a)] = detection(sc, thr, np.ones(len(X), bool), fam, fams)
        print("alpha", a, {sp: round(float(np.mean(list(v.values()))), 3) for sp, v in res["curve"][str(a)].items()}, flush=True)
else:
    rng = np.random.default_rng(SEED); res["curve"] = {}; n0 = int(mon.sum())
    def refit(Xa, day_, src_, t_, fit_, cal_):
        m = model_fresh(); m.mean.copy_(torch.from_numpy(Xa[fit_].mean(0))); m.std.copy_(torch.from_numpy(Xa[fit_].std(0) + 1e-3))
        seqs = sequences(day_, src_, t_); _, S = score(m, Xa, seqs); prev = np.zeros_like(S)
        for idx in seqs: prev[idx[1:]] = S[idx[:-1]]
        km = lambda a: torch.from_numpy(MiniBatchKMeans(int(min(512, max(2, len(a) // 2))), n_init=3, random_state=SEED).fit(a).cluster_centers_.astype(np.float32))
        m.codebook.data = km(m.normalize(torch.from_numpy(Xa[fit_])).numpy()); m.state_codebook.data = km(S[fit_])
        c = components(m, Xa, S, prev); return v0(c, c[cal_].mean(0), c[cal_].std(0), seqs)
    selected = sorted(set(fams["dev"]) | set(fams["final"]))
    if ONLY_FAMILY is not None:
        selected = [f for f in selected if names[f] == ONLY_FAMILY]
        if not selected:
            raise ValueError("Requested family has insufficient evaluation windows")
    for fname_i in selected:
        pool = np.flatnonzero((day > 0) & (fam == fname_i))
        for p in [0.0] + POISON:
            npz = min(int(np.ceil(p * n0)), len(pool) // 2)
            if p > 0 and npz == 0: continue
            pick = rng.choice(pool, npz, replace=False) if npz else np.array([], int)
            span_t = t[mon]; tp = rng.uniform(span_t.min(), span_t.max(), npz)
            Xa = np.concatenate([X, X[pick]]); day_ = np.concatenate([day, np.zeros(npz, day.dtype)]); src_ = np.concatenate([src, src[pick]]); t_ = np.concatenate([t, tp])
            cutoff = np.quantile(t_[day_ == 0], 0.8); mon_ = day_ == 0; cal_ = mon_ & (t_ >= cutoff); fit_ = mon_ & ~cal_
            sc = refit(Xa, day_, src_, t_, fit_, cal_)[:len(X)]
            thr = float(np.quantile(sc[cal_[:len(X)]], 0.99))   # threshold from the (poisoned) calibration span's original windows
            keep = np.ones(len(X), bool); keep[pick] = False   # the windows used for poisoning are not scored as test windows
            d = detection(sc, thr, keep, fam, fams)
            injected = np.arange(len(Xa)) >= len(X)
            if not np.array_equal(fit_ | cal_, mon_) or np.any(fit_ & cal_):
                raise ValueError("Poison fit/calibration partition is invalid")
            res["curve"].setdefault(names[fname_i], {})[str(p)] = {
                "poison_windows": int(npz),
                "poison_fit_windows": int((injected & fit_).sum()),
                "poison_calibration_windows": int((injected & cal_).sum()),
                "total_fit_windows": int(fit_.sum()),
                "total_calibration_windows": int(cal_.sum()),
                "effective_day0_poison_fraction": float(npz / mon_.sum()),
                "effective_fit_poison_fraction": float((injected & fit_).sum() / fit_.sum()),
                "requested_poison_relative_to_original_day0": p,
                "pool_capped": bool(npz < int(np.ceil(p * n0))),
                "calibration_threshold_original_rows_only": True,
                "backbone_retrained": False,
                "detection": {sp: d[sp].get(names[fname_i]) for sp in d}}
            print(names[fname_i], p, npz, res["curve"][names[fname_i]][str(p)]["detection"], flush=True)
json.dump(res, open(OUT, "w"), indent=1); print("wrote", OUT)
