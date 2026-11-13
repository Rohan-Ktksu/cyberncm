"""Build a synthetic dataset and a toy model so the real two-node demo runs with NO real data.

Everything is generated: traffic features, host addresses (documentation ranges only: 192.0.2.0/24,
198.51.100.0/24, 203.0.113.0/24) and labels. The synthetic windows are written in the same format as the
real prepared windows and pushed through the project's own steps (ncm/train.py, ncm/evaluate.py,
ncm/export.py), so the demo code (Node A, Node B, policy gate, enforcer) is the real code, unchanged.

The result is a toy: it shows how the pieces fit together. It says nothing about detection quality.

Usage:  python make_sandbox.py [OUT_DIR] [--force]
        OUT_DIR default: demo/two_node/sandbox/build   (git-ignored)
Outputs: OUT_DIR/data/windows.npz, OUT_DIR/artifacts/ncm_gru64_s0.pt and .onnx, OUT_DIR/logs/*.log
"""
import ipaddress
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent.parent
NCM = REPO / "ncm"

FAMILIES = ["BENIGN", "Portscan", "Infiltration", "Botnet", "DDoS"]
SUBJECT = "198.51.100.7"            # TEST-NET-2: the synthetic DDoS source that the demo maps to the lab client
PROTECTED = "203.0.113.250/32"      # a synthetic benign host the demo never alerts on
SEED = 7
DAY_END = 86000.0
DAYS = 5                            # day 0 = normal only (train + calibration); 1-2 dev; 3-4 final; replay uses day 4


def feature_names():
    """The 32 feature names, read from ncm/prep.py (names only; no data)."""
    src = (NCM / "prep.py").read_text(encoding="utf-8")
    block = re.search(r"FEATURES\s*=\s*\[(.*?)\]", src, re.S).group(1)
    names = re.findall(r"[\"']([a-z_0-9]+)[\"']", block)
    assert len(names) == 32, len(names)
    return names


def ip_int(s):
    return int(ipaddress.ip_address(s))


def generate(seed=SEED):
    rng = np.random.default_rng(seed)
    names = feature_names()
    d = len(names)
    mu = rng.uniform(1.0, 9.0, d)                       # feature means
    sd = rng.uniform(0.4, 1.4, d)                       # feature spreads
    X, DAY, SRC, T, FAM = [], [], [], [], []

    def session(host_ip, day, start, n, fam, host_off, shift=None, rho=0.5, noise=1.0, step=5.0):
        """One host's run of 5-second windows: AR(1) around the host's own level, optionally shifted."""
        x = mu + host_off + sd * rng.standard_normal(d)
        for i in range(n):
            e = sd * rng.standard_normal(d) * noise
            x = mu + host_off + rho * (x - mu - host_off) + np.sqrt(1 - rho ** 2) * e
            v = x + (shift if shift is not None else 0.0)
            if fam == 0 and rng.random() < 0.01:       # rare benign outliers, as in real traffic
                v = v + sd * rng.uniform(1.5, 3.0, d) * rng.choice([-1, 1], d)
            X.append(v); DAY.append(day); SRC.append(ip_int(host_ip)); T.append(start + i * step); FAM.append(fam)

    benign = [f"203.0.113.{i}" for i in range(1, 25)] + ["203.0.113.250"]
    anchor = "192.0.2.1"                                  # active around the replay window every day, and from t = 0
    for day in range(DAYS):
        session(anchor, day, 0.0, 3, 0, np.zeros(d))     # makes the day start at t = 0
        session(anchor, day, 24000.0, 700, 0, np.zeros(d))
        for h in benign:
            off = sd * rng.normal(0, 0.4, d)
            for _ in range(rng.integers(2, 5)):
                n = int(rng.integers(40, 90))
                start = float(rng.integers(0, int((DAY_END - n * 5) / 5))) * 5.0
                session(h, day, start, n, 0, off)
        if day >= 3:                                      # new benign devices appear late: they look a bit unusual
            for k in range(4):
                session(f"192.0.2.{100 + k}", day, float(rng.integers(0, 17000)) * 5.0, int(rng.integers(40, 80)), 0,
                        sd * rng.normal(0, 1.6, d))
    # attack families: each uses its own feature subset and shift; one event per family per attack day
    fam_shift = {}
    for f, scale in ((1, (3.0, 6.0)), (2, (3.0, 6.0)), (3, (3.0, 6.0)), (4, (6.0, 10.0))):
        idx = rng.choice(d, 8, replace=False)
        sh = np.zeros(d)
        sh[idx] = rng.choice([-1, 1], 8) * rng.uniform(*scale, 8) * sd[idx]
        fam_shift[f] = sh
    fixed = {4: {1: (25080.0, 30, "198.51.100.11"), 4: (25240.0, 60, SUBJECT), 3: (25500.0, 60, "198.51.100.13"),
                 2: (25900.0, 50, "198.51.100.14")}}
    for day in range(1, DAYS):
        for f in (1, 2, 3, 4):
            if day in (1, 2, 3):
                start, n, ip = float(rng.integers(2000, 80000 // 5)) * 5.0, 60, f"198.51.100.{20 + 10 * day + f}"
            else:
                start, n, ip = fixed[4][f]
            session(ip, day, start, n, f, np.zeros(d), shift=fam_shift[f], noise=0.6)
    X = np.asarray(X, np.float32)
    order = np.lexsort((np.asarray(T), np.asarray(SRC), np.asarray(DAY)))
    return dict(X=X[order], day=np.asarray(DAY, np.int64)[order], src=np.asarray(SRC, np.int64)[order],
                t=np.asarray(T, np.float64)[order], family=np.asarray(FAM, np.int64)[order],
                family_names=np.array(FAMILIES), features=np.array(names))


def run(cmd, cwd, log):
    env = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    with open(log, "w", encoding="utf-8") as f:
        r = subprocess.run([sys.executable, *cmd], cwd=cwd, env=env, stdout=f, stderr=subprocess.STDOUT)
    if r.returncode != 0:
        tail = Path(log).read_text(encoding="utf-8", errors="replace")[-1500:]
        raise SystemExit(f"step failed: {' '.join(cmd)}\n{tail}")


def build(out, force=False):
    out = Path(out)
    ck, onnx, win = out / "artifacts/ncm_gru64_s0.pt", out / "artifacts/ncm_gru64_s0.onnx", out / "data/windows.npz"
    if not force and ck.is_file() and onnx.is_file() and win.is_file():
        return ck, onnx, win
    for sub in ("data", "artifacts", "logs"):
        (out / sub).mkdir(parents=True, exist_ok=True)
    np.savez(win, **generate())
    run([str(NCM / "train.py"), "gru", "64", "0"], out, out / "logs/train.log")
    run([str(NCM / "evaluate.py"), "artifacts/ncm_gru64_s0.pt"], out, out / "logs/evaluate.log")
    run([str(NCM / "export.py"), "artifacts/ncm_gru64_s0.pt"], out, out / "logs/export.log")
    assert ck.is_file() and onnx.is_file(), "pipeline did not produce the expected files"
    return ck, onnx, win


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    out = Path(args[0]) if args else HERE / "build"
    ck, onnx, win = build(out, "--force" in sys.argv)
    print(json.dumps({"checkpoint": str(ck), "onnx": str(onnx), "windows": str(win), "subject": SUBJECT,
                      "protected": PROTECTED}, indent=1))
