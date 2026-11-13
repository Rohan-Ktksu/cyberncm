"""R3: detection of attackers that have benign history, with and without the log_gap feature.
Usage: python r3_eval.py CKPT_FULL WINDOWS CKPT_NOGAP WINDOWS_NOGAP OUT.json SEED   (run where `ncm/` is importable)
WINDOWS_NOGAP is the same file with the log_gap column set to 0; CKPT_NOGAP was trained on it."""
import json, os, sys
import numpy as np, torch
from sklearn.metrics import roc_auc_score
from ncm import NCM, ewma, score, sequences

CK_A, W_A, CK_B, W_B, OUT, SEED = sys.argv[1:6] + [int(sys.argv[6])]
torch.set_num_threads(int(os.environ.get("NCM_THREADS", 2)))
z = np.load(W_A, allow_pickle=True); zb = np.load(W_B, allow_pickle=True)
day, src, t, fam = z["day"], z["src"], z["t"], z["family"]; names = [str(n) for n in z["family_names"]]
assert np.array_equal(day, zb["day"]) and np.array_equal(src, zb["src"]) and np.array_equal(fam, zb["family"])
FN = [str(n) for n in z["features"]]; ig = FN.index("log_gap"); assert (zb["X"][:, ig] == 0).all() and np.allclose(np.delete(z["X"], ig, 1), np.delete(zb["X"], ig, 1))
present = sorted(set(np.unique(day).tolist()) - {0})
order = [int(x) for x in np.argsort(z["day_t0"]) if int(x) in present] if "day_t0" in z.files else present
FINAL = order[len(order) // 2:]; fin = np.isin(day, FINAL)
known = np.isin(src, np.unique(src[(day == 0) & (fam == 0)]))          # source has benign windows in the training day
mon = day == 0; cal = mon & (t >= np.quantile(t[mon], 0.8))


def v0(ck, X):
    c = torch.load(ck); m = NCM(h=c["h"], arch=c["arch"]); m.load_state_dict(c["state"], strict=False); m.eval()
    seqs = sequences(day, src, t); _, S = score(m, X.astype(np.float32), seqs); prev = np.zeros_like(S)
    for idx in seqs: prev[idx[1:]] = S[idx[:-1]]
    with torch.no_grad():
        zz = m.normalize(torch.from_numpy(X.astype(np.float32))); comp = np.concatenate([m.components(zz[i:i + 200000], torch.from_numpy(S[i:i + 200000]), torch.from_numpy(prev[i:i + 200000])).numpy() for i in range(0, len(X), 200000)])
    cc = (comp - m.calib[:, 0].numpy()) / m.calib[:, 1].numpy(); return ewma(cc[:, 0] + cc[:, 1] + 0.5 * (cc[:, 2] + cc[:, 3]), seqs)


def auc(sc, atk_mask):
    m = fin & (atk_mask | (fam == 0)); return float(roc_auc_score(atk_mask[m], sc[m])) if atk_mask[m].any() and (~atk_mask[m]).any() else None


res = {"seed": SEED, "final_days": FINAL,
       "attack_windows": {"known_source": int((fin & (fam > 0) & known).sum()), "new_source": int((fin & (fam > 0) & ~known).sum())},
       "attack_sources": {"known": int(len(np.unique(src[fin & (fam > 0) & known]))), "new": int(len(np.unique(src[fin & (fam > 0) & ~known])))},
       "benign_windows_final": {"known_source": int((fin & (fam == 0) & known).sum()), "new_source": int((fin & (fam == 0) & ~known).sum())}}
for tag, ck, W in (("full", CK_A, z["X"]), ("no_log_gap", CK_B, zb["X"])):
    sc = v0(ck, W); thr = float(np.quantile(sc[cal], 0.99)); atk = fam > 0
    res[tag] = {"auc_all_attackers": auc(sc, atk), "auc_known_source_attackers": auc(sc, atk & known), "auc_new_source_attackers": auc(sc, atk & ~known),
                "detect_known": float((sc[fin & atk & known] > thr).mean()) if (fin & atk & known).any() else None,
                "detect_new": float((sc[fin & atk & ~known] > thr).mean()) if (fin & atk & ~known).any() else None,
                "benign_alert_known": float((sc[fin & (fam == 0) & known] > thr).mean()), "benign_alert_new": float((sc[fin & (fam == 0) & ~known] > thr).mean()) if (fin & (fam == 0) & ~known).any() else None}
    print(tag, {k: (round(v, 3) if v is not None else None) for k, v in res[tag].items()}, flush=True)
json.dump(res, open(OUT, "w"), indent=1); print(res["attack_windows"], res["attack_sources"], "wrote", OUT)
