"""CSE-CIC-IDS-2018 (authors' corrected flows, CNS2022) -> data/windows.npz, same windows/features as prep.py.

Input  ../flows/d0..d4.parquet  (made by fetch_day.py run from the parent directory). Full timestamps and IPs, so no hour recovery.
Pseudo-days (fixed before any model ran). 2018 has no all-benign Monday, so day 0 is the benign stretch of one day:
  d0 Wed 14-02 from midnight up to the first attack chunk | d1 Thu 15-02 (dev) | d2 Wed 21-02 (dev)
  d3 Thu 22-02 (final) | d4 Fri 02-03 (final)
Flows are processed in source-hash shards (windows() is per source) to fit in memory.
"""
import ipaddress
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from prep import FEATURES, windows

REN = {"Src Port": "sport", "Dst Port": "dport", "Protocol": "proto", "t": "t", "Flow Duration": "dur",
       "Total Fwd Packet": "fpk", "Total Bwd packets": "bpk", "Total Length of Fwd Packet": "fby",
       "Total Length of Bwd Packet": "bby", "Fwd Packet Length Max": "flmax", "Flow IAT Mean": "piat",
       "Packet Length Mean": "plmean", "FIN Flag Count": "fin", "SYN Flag Count": "syn", "RST Flag Count": "rst",
       "PSH Flag Count": "psh", "ACK Flag Count": "ack", "FWD Init Win Bytes": "iwin"}
SHARD_FLOWS = 1_500_000
cache = {}


def ip_int(s):
    u = [x for x in pd.unique(s) if x not in cache]
    for x in u:
        try:
            cache[x] = int(ipaddress.ip_address(x))
        except ValueError:
            cache[x] = -1
    return s.map(cache).values


out = {k: [] for k in ["X", "day", "src", "t", "family"]}
for di in range(5):
    d = pq.ParquetFile(f"../flows/d{di}.parquet").read(use_threads=False).to_pandas()
    d["src"], d["dst"] = ip_int(d["Src IP"]), ip_int(d["Dst IP"])
    d = d[(d["src"] >= 0) & (d["dst"] >= 0)].rename(columns=REN)
    # "X - Attempted" = attacker flow with no payload; kept as attacker behaviour, as in the 2017 run
    d["family"] = d["Label"].str.replace(" - Attempted", "", regex=False)
    d = d.drop(columns=["Src IP", "Dst IP", "Label"])
    d["t"] = d["t"] - d["t"].min() + 3600 * 0  # seconds since the first flow of the day
    for c in ["sport", "dport", "proto", "fpk", "bpk", "fby", "bby", "fin", "syn", "rst", "psh", "ack", "iwin"]:
        d[c] = d[c].astype(np.int64)
    k = max(1, -(-len(d) // SHARD_FLOWS))
    shard = d["src"].values % k
    nf = len(d)
    for s in range(k):
        g = d[shard == s].copy()
        if not len(g):
            continue
        X, src, t, fam = windows(g)
        for key, v in zip(out, [X, np.full(len(X), di), src, t, fam]):
            out[key].append(v)
    nw = sum(len(x) for x, dd in zip(out["X"], out["day"]) if dd[0] == di)
    fm = np.concatenate([f for f, dd in zip(out["family"], out["day"]) if dd[0] == di])
    print(f"day {di}: {nf} flows, {nw} windows, {(fm != 'BENIGN').sum()} attack windows, {k} shards", flush=True)
    if di == 0:
        assert (fm == "BENIGN").all(), "attack window inside the benign training day"
    del d
X = np.concatenate(out["X"])
assert np.isfinite(X).all()
fam = np.concatenate(out["family"])
names = ["BENIGN"] + sorted(set(fam) - {"BENIGN"})
np.savez_compressed("data/windows.npz", X=X, day=np.concatenate(out["day"]), src=np.concatenate(out["src"]),
                    t=np.concatenate(out["t"]), family=np.array([names.index(x) for x in fam]),
                    family_names=np.array(names), features=np.array(FEATURES))
print(pd.Series(fam).value_counts().to_string())
