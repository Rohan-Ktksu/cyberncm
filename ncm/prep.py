"""Build per-source 5-second behaviour windows (32 features) from CIC-IDS2017.

Inputs
  data/<day>.csv           corrected flows + labels (Liu/Engelen et al.), timestamps are MM:SS.s only
  data/orig/*.parquet      original flows, timestamps to the minute, used only to recover the hour
Output
  data/windows.npz         X [n,32], day, src, t (window start, s since midnight), family (0 = benign)
"""
import glob
import ipaddress
import numpy as np
import pandas as pd

W = 5.0  # window length in seconds
DAYS = ["monday", "tuesday", "wednesday", "thursday", "friday"]
KEY = ["src", "sport", "dst", "dport", "proto"]

FEATURES = [
    # temporal flow kinematics
    "log_flows", "log_gap", "iat_mean", "iat_std", "iat_min", "dur_mean", "dur_std", "pkt_iat_mean",
    # transport state and flags
    "syn_ratio", "fin_ratio", "rst_ratio", "psh_ratio", "ack_ratio", "tcp_frac", "unanswered_frac", "init_win",
    # payload kinematics (encryption-invariant)
    "log_fwd_bytes", "log_bwd_bytes", "dir_byte_ratio", "pkt_len_mean", "pkt_len_spread", "fwd_len_max",
    "log_fwd_pkts", "log_bwd_pkts",
    # fan-out
    "log_dst_ips", "log_dst_ports", "ports_per_flow", "ips_per_flow", "new_dst_frac", "wellknown_frac",
    "dns_frac", "port_entropy",
]

COLS = {
    "Src IP dec": "src", "Src Port": "sport", "Dst IP dec": "dst", "Dst Port": "dport", "Protocol": "proto",
    "Timestamp": "ts", "Flow Duration": "dur", "Total Fwd Packet": "fpk", "Total Bwd packets": "bpk",
    "Total Length of Fwd Packet": "fby", "Total Length of Bwd Packet": "bby", "Fwd Packet Length Max": "flmax",
    "Flow IAT Mean": "piat", "Packet Length Mean": "plmean", "FIN Flag Count": "fin", "SYN Flag Count": "syn",
    "RST Flag Count": "rst", "PSH Flag Count": "psh", "ACK Flag Count": "ack", "FWD Init Win Bytes": "iwin",
    "Label": "label",
}


def load_orig(day):
    """Original flows for one day: 5-tuple + start minute (seconds since midnight)."""
    parts = []
    for f in sorted(glob.glob(f"data/orig/{day.capitalize()}-*.parquet")):
        d = pd.read_parquet(f, columns=["Source IP", "Source Port", "Destination IP", "Destination Port",
                                        "Protocol", "Timestamp"]).dropna()
        parts.append(d)
    d = pd.concat(parts)
    ip2int = {ip: int(ipaddress.ip_address(ip)) for ip in pd.unique(d[["Source IP", "Destination IP"]].values.ravel())}
    out = pd.DataFrame({
        "src": d["Source IP"].map(ip2int).values, "sport": d["Source Port"].values.astype(np.int64),
        "dst": d["Destination IP"].map(ip2int).values, "dport": d["Destination Port"].values.astype(np.int64),
        "proto": d["Protocol"].values.astype(np.int64),
        "omin": (d["Timestamp"].dt.hour * 60 + d["Timestamp"].dt.minute).values,
    })
    return out.drop_duplicates()  # every start minute of each 5-tuple (ports get reused)


def recover_time(df, day):
    """The corrected CSVs lost the hour. Recover it from the original flows.

    Each original flow of the same 5-tuple is a candidate. It implies the first time with minute MM
    at or after its own start (1 min slack); the candidate needing the shortest wait wins. A wait of
    <= 1 min is an exact match; longer waits are continuation flows the corrected tool split off.
    Equal waits use the earliest implied start minute, independent of file/row order. This is a
    deterministic convention, not proof of the missing hour when the 5-tuple is ambiguous.
    """
    mm_ss = df["ts"].str.split(":", expand=True)
    df["mm"], df["ss"] = mm_ss[0].astype(int), mm_ss[1].astype(float)
    df["row"] = np.arange(len(df))
    c = df[KEY + ["row", "mm"]].merge(load_orig(day), on=KEY)
    c["tmin"] = np.ceil((c["omin"] - 1 - c["mm"]) / 60.0) * 60 + c["mm"]
    c["wait"] = c["tmin"] - c["omin"]
    best = c.sort_values(["row", "wait", "tmin"]).drop_duplicates("row")[["row", "tmin", "wait"]]
    df = df.merge(best, on="row")
    df["t"] = df["tmin"] * 60 + df["ss"]
    exact = (df["wait"] <= 1).mean()
    return df.drop(columns=["tmin", "wait", "row", "mm", "ss", "ts"]), exact


def entropy(codes, groups, n_groups):
    """Shannon entropy of `codes` within each group."""
    pair = pd.DataFrame({"g": groups, "c": codes}).value_counts().reset_index(name="n")
    tot = pair.groupby("g")["n"].transform("sum")
    p = pair["n"] / tot
    return (-(p * np.log2(p))).groupby(pair["g"]).sum().reindex(range(n_groups), fill_value=0).values


def windows(df):
    """Aggregate one day's flows into per-source windows."""
    df = df.sort_values(["src", "t"]).reset_index(drop=True)
    df["w"] = np.floor(df["t"] / W).astype(np.int64)
    gid = df.groupby(["src", "w"], sort=False).ngroup().values
    n = gid.max() + 1
    g = df.groupby(gid)

    df["iat"] = df.groupby(gid)["t"].diff()  # gap between flow starts inside the window
    df["ldur"] = np.log1p(df["dur"].clip(lower=0))
    pk = (df["fpk"] + df["bpk"]).clip(lower=1)
    # destination not contacted by this source in its previous window
    pair = df[["src", "w", "dst"]].drop_duplicates()
    prev_w = pair[["src", "w"]].drop_duplicates().sort_values(["src", "w"])
    prev_w["pw"] = prev_w.groupby("src")["w"].shift()
    pair = pair.merge(prev_w, on=["src", "w"]).merge(
        pair.rename(columns={"w": "pw"}).assign(seen=1), on=["src", "pw", "dst"], how="left")
    df = df.merge(pair[["src", "w", "dst", "seen"]], on=["src", "w", "dst"], how="left")

    first = g[["src", "w"]].first()
    nf = g.size().values.astype(float)
    tot_pk = pk.groupby(gid).sum().values
    f = {}
    f["log_flows"] = np.log1p(nf)
    gap = first.groupby("src")["w"].diff().fillna(3600 / W).values * W  # first window of a source: treat as 1 h idle
    f["log_gap"] = np.log1p(gap)
    f["iat_mean"] = np.log1p(g["iat"].mean().fillna(W).values)
    f["iat_std"] = np.log1p(g["iat"].std().fillna(0).values)
    f["iat_min"] = np.log1p(g["iat"].min().fillna(W).values)
    f["dur_mean"] = g["ldur"].mean().values
    f["dur_std"] = g["ldur"].std().fillna(0).values
    f["pkt_iat_mean"] = np.log1p(g["piat"].mean().clip(lower=0).values)
    for flag in ["syn", "fin", "rst", "psh", "ack"]:
        f[f"{flag}_ratio"] = g[flag].sum().values / tot_pk
    f["tcp_frac"] = (df["proto"] == 6).groupby(gid).mean().values
    f["unanswered_frac"] = (df["bpk"] == 0).groupby(gid).mean().values
    f["init_win"] = np.log1p(g["iwin"].mean().clip(lower=0).values)
    fby, bby = g["fby"].sum().values, g["bby"].sum().values
    f["log_fwd_bytes"], f["log_bwd_bytes"] = np.log1p(fby), np.log1p(bby)
    f["dir_byte_ratio"] = fby / np.maximum(fby + bby, 1)
    f["pkt_len_mean"] = np.log1p(g["plmean"].mean().values)
    f["pkt_len_spread"] = np.log1p(g["plmean"].std().fillna(0).values)
    f["fwd_len_max"] = np.log1p(g["flmax"].max().values)
    f["log_fwd_pkts"], f["log_bwd_pkts"] = np.log1p(g["fpk"].sum().values), np.log1p(g["bpk"].sum().values)
    n_ip, n_port = g["dst"].nunique().values, g["dport"].nunique().values
    f["log_dst_ips"], f["log_dst_ports"] = np.log1p(n_ip), np.log1p(n_port)
    f["ports_per_flow"], f["ips_per_flow"] = n_port / nf, n_ip / nf
    f["new_dst_frac"] = df["seen"].isna().groupby(gid).mean().values
    f["wellknown_frac"] = (df["dport"] < 1024).groupby(gid).mean().values
    f["dns_frac"] = (df["dport"] == 53).groupby(gid).mean().values
    f["port_entropy"] = entropy(df["dport"].values, gid, n)

    X = np.stack([f[k] for k in FEATURES], axis=1).astype(np.float32)
    # window label: the most common attack family among its flows, benign if none
    fam = df["family"].where(df["family"] != "BENIGN")
    label = fam.groupby(gid).agg(lambda s: s.mode().iat[0] if s.notna().any() else "BENIGN")
    return X, first["src"].values, first["w"].values * W, label.values


def main():
    out = {k: [] for k in ["X", "day", "src", "t", "family"]}
    for di, day in enumerate(DAYS):
        df = pd.read_csv(f"data/{day}.csv", usecols=list(COLS)).rename(columns=COLS)
        n0 = len(df)
        df, rate = recover_time(df, day)
        # "X - Attempted" = attacker flow that carried no payload; still attacker behaviour
        df["family"] = df["label"].str.replace(" - Attempted", "", regex=False)
        X, src, t, fam = windows(df)
        print(f"{day}: {n0} flows, hour matched exactly for {rate:.1%} of {len(df)} kept, {len(X)} windows, "
              f"{(fam != 'BENIGN').sum()} attack windows, hours {t.min()/3600:.1f}-{t.max()/3600:.1f}")
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


if __name__ == "__main__":
    main()
