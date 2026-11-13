"""Run one of the prep scripts with windows keyed by (source, destination) or (source, service).
Usage, from a folder `ncm/` that holds the prep scripts and the raw inputs they expect:
    python prep_keyed.py pair|service prep.py|prep_unsw.py|prep_2018.py|prep_unraveled.py|prep_cicapt.py [script args]
Writes data/windows.npz as the script does (its `src` array now holds a key id) and data/pair_map.npz (source address and second key of each id)."""
import atexit, runpy, sys
import numpy as np, pandas as pd
import prep

KEY, SCRIPT = sys.argv[1], sys.argv[2]; sys.argv = sys.argv[2:]
assert KEY in ("pair", "service")
reg, _orig = {}, prep.windows


def windows(df):
    df = df.copy()
    k2 = df["dst"].values.astype(np.int64) if KEY == "pair" else np.where(df["dport"].values < 1024, df["dport"].values, 0).astype(np.int64)
    codes, uniq = pd.factorize(pd.MultiIndex.from_arrays([df["src"].values.astype(np.int64), k2]))
    ids = np.array([reg.setdefault((int(a), int(b)), len(reg)) for a, b in uniq], dtype=np.int64)
    df["src"] = ids[codes]
    return _orig(df)


prep.windows = windows


def save():
    items = sorted(reg.items(), key=lambda kv: kv[1])
    np.savez("data/pair_map.npz", source=np.array([k[0] for k, _ in items], dtype=np.int64), key2=np.array([k[1] for k, _ in items], dtype=np.int64))
    print("keys:", len(items), flush=True)


atexit.register(save)
if SCRIPT == "prep.py": prep.main()
else: runpy.run_path(SCRIPT, run_name="__main__")
