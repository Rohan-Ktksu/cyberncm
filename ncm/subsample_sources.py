"""Keep every source that is ever an attacker, plus a fixed fraction of the other sources, so the unchanged pipeline
fits in memory. Usage: python subsample_sources.py [percent]   (default 10; rewrites data/windows.npz, keeps a backup)

Used for CSE-CIC-IDS2018, which has about 5.85M benign windows (47x CIC-IDS2017). Fixed before any 2018 model ran.
Selection is by a hash of the source address, so the same hosts are kept on every day and no window inside a kept
source is dropped: per-source sequences stay intact. Attacker sources are always kept in full, including their
benign windows, so the test still contains benign traffic from the attacking hosts.
"""
import os
import sys
import numpy as np

PCT = int(sys.argv[1]) if len(sys.argv) > 1 else 10
z = dict(np.load("data/windows.npz"))
src = z["src"].astype(np.int64)
attackers = np.unique(src[z["family"] > 0])
h = (src * 2654435761) % (1 << 32) % 100  # Knuth multiplicative hash of the address
keep = np.isin(src, attackers) | (h < PCT)
os.replace("data/windows.npz", "data/windows_full.npz")
np.savez_compressed("data/windows.npz", **{k: (v[keep] if v.shape[:1] == src.shape else v) for k, v in z.items()})
print(f"kept {keep.sum()} of {len(keep)} windows; {len(attackers)} attacker sources in full, "
      f"{len(np.unique(src[keep]))} of {len(np.unique(src))} sources")
for d in np.unique(z["day"]):
    m = keep & (z["day"] == d)
    print(f"day {d}: {m.sum()} windows, {(z['family'][m] > 0).sum()} attack windows")
