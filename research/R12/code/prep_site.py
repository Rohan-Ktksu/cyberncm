"""Run one of the prep scripts with windows keyed by (source, site), where a site is a fixed random group of victim hosts.
Usage, from a folder `ncm/` that holds the prep scripts and the raw inputs they expect:
    python prep_site.py K prep.py|prep_unsw.py|prep_2018.py|prep_unraveled.py|prep_cicapt.py [script args]
A flow belongs to site hash(destination address) mod K (pandas.util.hash_array, fixed key, so the split is reproducible).
Writes data/windows.npz as the script does (its `src` array holds a (source, site) id) and data/pair_map.npz (source address and site of each id)."""
import atexit, runpy, sys
import numpy as np, pandas as pd
import prep

K, SCRIPT = int(sys.argv[1]), sys.argv[2]; sys.argv = sys.argv[2:]
reg, _orig = {}, prep.windows


def windows(df):
    df = df.copy()
    site = (pd.util.hash_array(df["dst"].values.astype(np.int64)) % K).astype(np.int64)
    codes, uniq = pd.factorize(pd.MultiIndex.from_arrays([df["src"].values.astype(np.int64), site]))
    ids = np.array([reg.setdefault((int(a), int(b)), len(reg)) for a, b in uniq], dtype=np.int64)
    df["src"] = ids[codes]
    return _orig(df)


prep.windows = windows


def save():
    items = sorted(reg.items(), key=lambda kv: kv[1])
    np.savez("data/pair_map.npz", source=np.array([k[0] for k, _ in items], dtype=np.int64), site=np.array([k[1] for k, _ in items], dtype=np.int64))
    print("ids:", len(items), flush=True)


atexit.register(save)
if SCRIPT == "prep.py": prep.main()
else: runpy.run_path(SCRIPT, run_name="__main__")
