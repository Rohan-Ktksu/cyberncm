"""R7d (induced false blocks) and R7f (spoofed sources) on CIC-IDS2017 flows.
Usage (cwd = a folder where ncm.py and prep.py import): python r7df_inject.py CKPT CANONICAL_WINDOWS OUT.json SEED CACHE_DIR
CACHE_DIR holds cache_<day>.pkl (flow tables after hour recovery, as written by r7b_slow.py).
Targets are 'pure benign' hosts (no attack flow that day). Block rule (as R12): at least 2 of the host's last 3 windows above the 99.5th percentile of the day-0 calibration windows."""
import json, os, pickle, sys
import numpy as np, pandas as pd, torch
import prep
from ncm import NCM, ewma, score, sequences

CK, WIN, OUT, SEED, CACHE = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4]), sys.argv[5]
torch.set_num_threads(int(os.environ.get("NCM_THREADS", 4))); prep.W = 5.0; rng = np.random.default_rng(SEED)
c = torch.load(CK); m = NCM(h=c["h"], arch=c["arch"]); m.load_state_dict(c["state"], strict=False); m.eval()


def v0(X, day, src, t):
    seqs = sequences(day, src, t); _, S = score(m, X.astype(np.float32), seqs); prev = np.zeros_like(S)
    for idx in seqs: prev[idx[1:]] = S[idx[:-1]]
    with torch.no_grad():
        zz = m.normalize(torch.from_numpy(X.astype(np.float32))); comp = np.concatenate([m.components(zz[i:i + 200000], torch.from_numpy(S[i:i + 200000]), torch.from_numpy(prev[i:i + 200000])).numpy() for i in range(0, len(X), 200000)])
    cc = (comp - m.calib[:, 0].numpy()) / m.calib[:, 1].numpy(); return ewma(cc[:, 0] + cc[:, 1] + 0.5 * (cc[:, 2] + cc[:, 3]), seqs)


z = np.load(WIN, allow_pickle=True); sc0 = v0(z["X"], z["day"], z["src"], z["t"]); mon = z["day"] == 0; cal = mon & (z["t"] >= np.quantile(z["t"][mon], 0.8)); THR = float(np.quantile(sc0[cal], 0.995))


def blocked_hosts(df, targets, day):
    """Window the flows of the target hosts, score with v0, return {host: blocked?} and window counts."""
    sub = df[df["src"].isin(targets)].copy(); X, src, t, fam = prep.windows(sub)
    sc = v0(X, np.full(len(X), day), src, t); out = {}
    for s in targets:
        r = np.flatnonzero(src == s); r = r[np.argsort(t[r])]; a = (sc[r] > THR).astype(int)
        a1 = np.zeros_like(a); a1[1:] = a[:-1]; a2 = np.zeros_like(a); a2[2:] = a[:-2]       # a host with no windows (all flows dropped) is not blocked
        out[int(s)] = bool(len(a) and ((a + a1 + a2) >= 2).any())
    return out, int(len(X))


res = {"seed": SEED, "threshold": THR, "r7d": [], "r7f": []}
DAYS = ["tuesday", "wednesday", "thursday", "friday"]
for di, d in enumerate(DAYS, 1):
    df = pickle.load(open(os.path.join(CACHE, f"cache_{d}.pkl"), "rb")); atk = df["family"] != "BENIGN"
    pure = np.array(sorted(set(df.loc[~atk, "src"]) - set(df.loc[atk, "src"]))); n_flows = df.groupby("src").size()
    targets = np.array([s for s in pure if n_flows[s] >= 100]); pool = df[atk]
    if len(targets) == 0 or len(pool) == 0: continue
    base, nwin = blocked_hosts(df, targets, di)
    res["r7d"].append({"day": d, "p": 0.0, "targets": int(len(targets)), "blocked": int(sum(base.values())), "induced": 0, "windows": nwin})
    for p in (0.01, 0.05, 0.2):
        rows = []
        for s in targets:
            mine = df[df["src"] == s]; k = int(np.ceil(p * len(mine))); add = pool.sample(k, replace=len(pool) < k, random_state=int(rng.integers(1 << 30))).copy()
            add["src"] = s; add["t"] = rng.uniform(mine["t"].min(), mine["t"].max(), k); rows.append(add)
        inj = pd.concat([df, *rows], ignore_index=True); bl, nwin = blocked_hosts(inj, targets, di)
        res["r7d"].append({"day": d, "p": p, "targets": int(len(targets)), "blocked": int(sum(bl.values())), "induced": int(sum(bl[int(s)] and not base[int(s)] for s in targets)), "windows": nwin})
    # R7f: all unanswered attack flows of the attacker with most of them are re-sourced to each target in turn
    un = pool[(pool["bpk"] == 0) & pool["proto"].isin([6, 17])]
    if len(un) > 0:
        att = un["src"].value_counts().index[0]; spoof = un[un["src"] == att].head(3000)
        for mit in (False, True):
            rows = []
            for s in targets:
                add = spoof.copy(); add["src"] = s; rows.append(add)
            inj = pd.concat([df, *rows], ignore_index=True)
            if mit: inj = inj[inj["bpk"] > 0]                                   # mitigation: count only flows with an answer
            base_m = blocked_hosts(df[df["bpk"] > 0] if mit else df, targets, di)[0]
            bl, nwin = blocked_hosts(inj, targets, di)
            res["r7f"].append({"day": d, "mitigation_drop_unanswered": mit, "spoofed_flows_per_target": int(len(spoof)), "targets": int(len(targets)), "blocked_without_spoof": int(sum(base_m.values())), "blocked_with_spoof": int(sum(bl.values())), "induced": int(sum(bl[int(s)] and not base_m[int(s)] for s in targets))})
    print(d, [r for r in res["r7d"] if r["day"] == d], [r for r in res["r7f"] if r["day"] == d], flush=True)
json.dump(res, open(OUT, "w"), indent=1); print("wrote", OUT)
