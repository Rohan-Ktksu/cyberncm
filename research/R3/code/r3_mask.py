"""Write a copy of a windows.npz with the log_gap column set to 0. Usage: python r3_mask.py IN_WINDOWS OUT_WINDOWS"""
import sys, numpy as np
z = np.load(sys.argv[1], allow_pickle=True); d = {k: z[k] for k in z.files}
i = [str(n) for n in d["features"]].index("log_gap"); d["X"] = d["X"].copy(); d["X"][:, i] = 0
np.savez_compressed(sys.argv[2], **d); print("wrote", sys.argv[2], "log_gap column", i)
