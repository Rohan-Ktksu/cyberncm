"""R7b low and slow on CIC-IDS2017. Usage (from a folder whose data/ holds <day>.csv and orig/*.parquet): python r7b_slow.py CKPT WINDOWS_NPZ OUT.json SEED NCM_DIR
Attacker flows are re-spaced by a factor k from each attacking source's first attack flow of the day, then the day is windowed again."""
import json, os, pickle, sys
import numpy as np, pandas as pd, torch
CKPT, WIN, OUT, SEED, NCM_DIR = sys.argv[1], sys.argv[2], sys.argv[3], int(sys.argv[4]), sys.argv[5]
sys.path.insert(0, NCM_DIR)
import prep
from ncm import NCM, ewma, score, sequences
torch.set_num_threads(int(os.environ.get("NCM_THREADS", 2)))
KS = [1, 10, 100, 1000]; MIN_WIN = 10
z = np.load(WIN, allow_pickle=True); names = [str(n) for n in z["family_names"]]
base = {k: z[k] for k in ["X", "day", "src", "t", "family"]}; day0 = base["day"] == 0
SPLITS = {"dev": [1, 2], "final": [3, 4]}
cache = {}
for di, d in enumerate(prep.DAYS):
    if di == 0: continue
    f = f"cache_{d}.pkl"
    if os.path.exists(f): cache[di] = pickle.load(open(f, "rb")); continue
    df = pd.read_csv(f"data/{d}.csv", usecols=list(prep.COLS)).rename(columns=prep.COLS)
    df, _ = prep.recover_time(df, d); df["family"] = df["label"].str.replace(" - Attempted", "", regex=False)
    pickle.dump(df, open(f, "wb")); cache[di] = df
ck = torch.load(CKPT); m = NCM(h=ck["h"], arch=ck["arch"]); m.load_state_dict(ck["state"], strict=False); m.eval()
mu, sd = m.calib[:, 0].numpy(), m.calib[:, 1].numpy()


@torch.no_grad()
def v0(X, day, src, t):
    seqs = sequences(day, src, t); _, S = score(m, X, seqs); prev = np.zeros_like(S)
    for idx in seqs: prev[idx[1:]] = S[idx[:-1]]
    zz = m.normalize(torch.from_numpy(X)); comp = np.concatenate([m.components(zz[i:i + 200000], torch.from_numpy(S[i:i + 200000]), torch.from_numpy(prev[i:i + 200000])).numpy() for i in range(0, len(X), 200000)])
    c = (comp - mu) / sd; return ewma(c[:, 0] + c[:, 1] + 0.5 * (c[:, 2] + c[:, 3]), seqs)


res = {"seed": SEED, "factors": {}}
for k in KS:
    parts = {"X": [base["X"][day0]], "day": [base["day"][day0]], "src": [base["src"][day0]], "t": [base["t"][day0]], "family": [base["family"][day0]]}
    for di, df in cache.items():
        d = df.copy(); atk = d["family"] != "BENIGN"
        t0 = d.loc[atk].groupby("src")["t"].transform("min"); d.loc[atk, "t"] = t0 + k * (d.loc[atk, "t"] - t0)
        X, src, t, fam = prep.windows(d)
        for key, v in zip(parts, [X, np.full(len(X), di), src, t, np.array([names.index(x) for x in fam])]): parts[key].append(v)
    X, day, src, t, fam = (np.concatenate(parts[x]) for x in ["X", "day", "src", "t", "family"])
    sc = v0(X.astype(np.float32), day, src, t); mon = day == 0; cal = mon & (t >= np.quantile(t[mon], 0.8)); thr = float(np.quantile(sc[cal], 0.99))
    out = {"windows": int(len(X)), "attack_windows": int((fam > 0).sum()), "threshold": thr, "detection": {}}
    for sp, days in SPLITS.items():
        out["detection"][sp] = {names[f]: float((sc[np.isin(day, days) & (fam == f)] > thr).mean()) for f in range(1, len(names)) if (np.isin(day, days) & (fam == f)).sum() >= MIN_WIN}
        out["detection"][sp + "_windows"] = {names[f]: int((np.isin(day, days) & (fam == f)).sum()) for f in range(1, len(names)) if (np.isin(day, days) & (fam == f)).sum() >= 1}
    res["factors"][str(k)] = out; print("k", k, out["windows"], out["attack_windows"], {sp: round(float(np.mean(list(out["detection"][sp].values()))), 3) for sp in SPLITS}, flush=True)
json.dump(res, open(OUT, "w"), indent=1); print("wrote", OUT)
