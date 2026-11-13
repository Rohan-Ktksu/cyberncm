"""Flow records to 5-second windows with the project's own feature code (ncm/prep.py)."""
import os, sys
import numpy as np, pandas as pd
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "ncm"))
import prep   # noqa: E402

# One row per flow. src and dst are IPv4 addresses as integers; t is the flow start in seconds (any fixed origin); dur is in microseconds.
COLUMNS = ["src", "sport", "dst", "dport", "proto", "dur", "fpk", "bpk", "fby", "bby", "flmax", "piat", "plmean", "fin", "syn", "rst", "psh", "ack", "iwin", "t"]
WINDOW_SECONDS = prep.W


def read_flows(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    missing = [c for c in COLUMNS if c not in df.columns]
    if missing: raise ValueError(f"flow file lacks columns: {missing}")
    df = df[COLUMNS + (["family"] if "family" in df.columns else [])].copy()
    df["family"] = "BENIGN"                      # the agent never sees a label (a ground-truth column, if present, is ignored)
    return df.sort_values("t", kind="stable").reset_index(drop=True)


def windows(df: pd.DataFrame):
    """-> X [n, 32], src [n], t [n] (window start, seconds), sorted by t."""
    X, src, t, _ = prep.windows(df)
    o = np.argsort(t, kind="stable"); return X[o], src[o], t[o]


def ip_str(n: int) -> str:
    return ".".join(str((int(n) >> s) & 255) for s in (24, 16, 8, 0))
