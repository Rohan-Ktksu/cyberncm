"""UNSW-NB15 -> data/windows.npz, same 5 s per-source windows and 32 features as prep.py (reuses prep.windows).

Input  ../unsw_flow.parquet  (HF rdpahalavan/UNSW-NB15, Network-Flows): 2.06M flows with IPs, epoch start time, labels.
Pseudo-days (fixed before any model was run), because the pipeline expects Mon = benign train, Tue/Wed dev, Thu/Fri final:
  day 0  Jan 22 14:00 -> Jan 23 01:00   no attacks occur in this span (benign train + calibration)
  day 1  Jan 22 attack hours (11:49-14:00)
  day 2-4  Feb 18 00:00-12:21 in three equal-duration blocks
shortcut: UNSW has no TCP flag counts, packet-length max or packet IAT; flags are guessed from `state`, flmax from smeansz,
piat from sintpkt. syn/fin/rst/psh/ack ratios are therefore near-constant here. Upgrade: rebuild from the pcaps.
"""
import ipaddress
import numpy as np
import pandas as pd
import pyarrow.parquet as pq
from prep import FEATURES, windows

COLS = ["source_ip", "source_port", "destination_ip", "destination_port", "protocol", "state", "dur", "sbytes", "dbytes",
        "spkts", "dpkts", "swin", "smeansz", "sintpkt", "stime", "attack_label"]
# single-threaded read: the threaded reader crashed on this machine (about 0.4 GB free RAM)
d = pq.ParquetFile("../unsw_flow.parquet").read(columns=COLS, use_threads=False).to_pandas()
d["family"] = d["attack_label"].map(lambda s: "BENIGN" if s == "normal" else {"dos": "DoS"}.get(s, s.capitalize()))
ts = pd.to_datetime(d["stime"], unit="s")
feb = ts >= "2015-02-01"
t0 = ts[feb].min().floor("D")
span = (ts[feb].max() - t0) / 3
day = np.full(len(d), -1)
day[(ts >= "2015-01-22 14:00") & (ts < "2015-01-23 01:00")] = 0
day[(ts >= "2015-01-22 11:00") & (ts < "2015-01-22 14:00")] = 1
day[feb] = 2 + np.minimum(((ts[feb] - t0) / span).astype(int), 2)
assert (day[d["family"] != "BENIGN"] > 0).all(), "attack flow inside the benign training day"
assert (day >= 0).all()

ips = pd.unique(d[["source_ip", "destination_ip"]].values.ravel())
ip2int = {ip: int(ipaddress.ip_address(ip)) for ip in ips}
tcp = (d["protocol"] == "tcp").values
st = d["state"].values
f = pd.DataFrame({
    "src": d["source_ip"].map(ip2int).values, "sport": d["source_port"].values,
    "dst": d["destination_ip"].map(ip2int).values, "dport": d["destination_port"].values,
    "proto": np.where(tcp, 6, np.where(d["protocol"] == "udp", 17, 1)),
    "t": d["stime"].values.astype(float), "dur": d["dur"].values * 1e6,  # CIC durations are microseconds
    "fpk": d["spkts"].values, "bpk": d["dpkts"].values, "fby": d["sbytes"].values, "bby": d["dbytes"].values,
    "flmax": d["smeansz"].values, "piat": d["sintpkt"].values * 1e3,
    "plmean": (d["sbytes"] + d["dbytes"]).values / np.maximum(d["spkts"] + d["dpkts"], 1).values,
    "fin": (tcp & np.isin(st, ["FIN", "CLO"])).astype(int), "syn": tcp.astype(int),
    "rst": (tcp & (st == "RST")).astype(int), "psh": (tcp & (d["sbytes"].values > 0)).astype(int),
    "ack": (tcp & ~np.isin(st, ["REQ", "INT"])).astype(int), "iwin": d["swin"].values,
    "family": d["family"].values, "day": day,
})
print(f.groupby("day").size().to_dict(), "flows per pseudo-day")

out = {k: [] for k in ["X", "day", "src", "t", "family"]}
for di in range(5):
    g = f[f["day"] == di].drop(columns="day")
    X, src, t, fam = windows(g)
    print(f"day {di}: {len(g)} flows, {len(X)} windows, {(fam != 'BENIGN').sum()} attack windows")
    for k, v in zip(out, [X, np.full(len(X), di), src, t, fam]):
        out[k].append(v)
X = np.concatenate(out["X"])
assert np.isfinite(X).all()
fam = np.concatenate(out["family"])
names = ["BENIGN"] + sorted(set(fam) - {"BENIGN"})
np.savez_compressed("data/windows.npz", X=X, day=np.concatenate(out["day"]), src=np.concatenate(out["src"]),
                    t=np.concatenate(out["t"]), family=np.array([names.index(x) for x in fam]),
                    family_names=np.array(names), features=np.array(FEATURES))
print(pd.Series(fam).value_counts().to_string())
