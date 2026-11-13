"""R13: does risk rise on the hosts a campaign touches next, before their first attack window?
Usage (from a folder where ncm.py imports): python r13_victim.py WINDOWS_PAIR.npz PAIR_MAP.npz OUT.json SEED
WINDOWS_PAIR holds windows keyed by (source, destination); PAIR_MAP maps a key to the source address and the destination address (key2).
Scores are token distance (512 centres from day-0 windows, smoothed per key and day, as R6c), the score of a victim (or /24 subnet) at a time is the highest score of any window to it."""
import json, os, sys
import numpy as np, torch
from sklearn.cluster import MiniBatchKMeans
from ncm import ewma, sequences

WIN, PM, OUT, SEED = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4]); HOUR = 3600.0; DAY = 86400.0
torch.set_num_threads(int(os.environ.get("NCM_THREADS", 4)))
z = np.load(WIN, allow_pickle=True); pm = np.load(PM); X, day, t, fam, key = z["X"], z["day"], z["t"], z["family"], z["src"]
T = z["day_t0"][day] + t if "day_t0" in z.files else day * DAY + t
dst = pm["key2"][key].astype(np.int64); subnet = dst >> 8; names = [str(n) for n in z["family_names"]]
mon = day == 0; cut = np.quantile(t[mon], 0.8); train, cal = mon & (t < cut), mon & (t >= cut)
Zn = np.clip((X - X[train].mean(0)) / (X[train].std(0) + 1e-3), -10, 10).astype(np.float32)
rng = np.random.default_rng(SEED); tr = np.flatnonzero(train); tr = tr if len(tr) <= 300000 else rng.choice(tr, 300000, replace=False)
cen = torch.from_numpy(MiniBatchKMeans(512, n_init=3, random_state=SEED).fit(Zn[tr]).cluster_centers_.astype(np.float32)); cc = (cen * cen).sum(-1)
dist = np.empty(len(Zn), np.float32)
for i in range(0, len(Zn), 100000):
    q = torch.from_numpy(Zn[i:i + 100000]); d2 = (q * q).sum(-1, keepdim=True) - 2 * q @ cen.T + cc; dist[i:i + 100000] = d2.clamp_min(1e-6).min(-1).values.sqrt().numpy()
dz = (dist - dist[cal].mean()) / dist[cal].std()
seqs = sequences(day, key, t)
shuf = []
for idx in seqs:                                    # shuffled control: permute the order of windows inside each hour of one key's sequence
    idx = idx[np.argsort(T[idx])]; hr = np.floor(T[idx] / HOUR).astype(np.int64); out = []
    for h in np.unique(hr): out.append(rng.permutation(idx[hr == h]))
    shuf.append(np.concatenate(out))
SC = {"real": ewma(dz, seqs), "shuffled": ewma(dz, shuf)}
test = day > 0; days = sorted(np.unique(day[test]).tolist())
res = {"seed": SEED, "windows": int(len(X)), "victims": int(len(np.unique(dst))), "attack_windows": int(((fam > 0) & test).sum())}


def thresholds(sc):
    fixed = float(np.quantile(sc[cal], 0.99)); daily = {}
    prev = cal
    for d in days:
        daily[d] = float(np.quantile(sc[prev], 0.99)) if prev.sum() > 100 else fixed; prev = day == d
    return fixed, daily


def analyse(sc, unit, label):
    fixed, daily = thresholds(sc); thr_of = {"fixed": np.full(len(sc), fixed), "daily": np.array([daily.get(int(d), fixed) for d in day])}
    out = {}
    uniq = np.unique(unit[test]); firstatk = {}
    a = np.flatnonzero(test & (fam > 0))
    for i in a[np.argsort(T[a])]: firstatk.setdefault(int(unit[i]), float(T[i]))
    order = np.argsort(T); tsorted = T[order]
    for tname, thr in thr_of.items():
        al = sc > thr
        hits, tested = [], 0
        for u, t0 in firstatk.items():
            ru = np.flatnonzero((unit == u) & test)
            prior24 = ru[(T[ru] < t0) & (T[ru] >= t0 - DAY)]
            if len(prior24) == 0: continue
            tested += 1; hits.append(bool(al[prior24][T[prior24] >= t0 - HOUR].any()))
        # base rate: share of (unit, hour) blocks, among units with traffic in the block, that contain an alert; blocks within 1 h before a first attack window excluded
        blk = (unit * 100000 + np.floor(T / HOUR).astype(np.int64))[test]; alt = al[test]; ut = unit[test]; hh = np.floor(T[test] / HOUR)
        excl = np.zeros(len(blk), bool)
        for u, t0 in firstatk.items(): excl |= (ut == u) & (hh >= np.floor(t0 / HOUR) - 1) & (hh <= np.floor(t0 / HOUR))
        ub, inv = np.unique(blk[~excl], return_inverse=True); anyalert = np.zeros(len(ub), bool); np.logical_or.at(anyalert, inv, alt[~excl])
        out[tname] = {"onsets": int(len(firstatk)), "testable_onsets": tested, "flagged_prior_hour": int(sum(hits)), "base_rate_unit_hours": float(anyalert.mean()), "unit_hours": int(len(ub))}
    return out


for sname, sc in SC.items():
    res[sname] = {"host": analyse(sc, dst, "host"), "subnet24": analyse(sc, subnet, "subnet")}
    print(sname, json.dumps({u: {t_: (v["flagged_prior_hour"], v["testable_onsets"], round(v["base_rate_unit_hours"], 3)) for t_, v in d.items()} for u, d in res[sname].items()}), flush=True)
json.dump(res, open(OUT, "w"), indent=1)
