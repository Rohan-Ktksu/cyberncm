"""Apply the R3 rule. Usage: python r3_decide.py R3_DIR OUT.md   (files <dataset>_s<seed>.json)"""
import glob, json, os, re, sys
import numpy as np
rd, out = sys.argv[1:3]; NICE = {"cic2017": "CIC-IDS2017", "d2018": "CSE-CIC-IDS2018", "unraveled": "Unraveled"}
R = {}
for f in sorted(glob.glob(os.path.join(rd, "*_s?.json"))):
    ds = re.match(r"(\w+)_s\d\.json", os.path.basename(f)).group(1); R.setdefault(ds, []).append(json.load(open(f)))
fmt = lambda v: "-" if v is None else f"{v:.3f}"
mean = lambda xs: None if any(x is None for x in xs) else float(np.mean(xs))
L = ["### Final-split AUC of attackers against all benign windows, mean over seeds (min to max)", "",
     "| Dataset | Attackers | Attack sources / windows (final) | Full model | Without log_gap | Drop |", "|---|---|---|---|---|---|"]
drops = {}
for ds, rs in R.items():
    for key, label in (("auc_known_source_attackers", "with benign history"), ("auc_new_source_attackers", "no benign history (new)"), ("auc_all_attackers", "all")):
        a = [r["full"][key] for r in rs]; b = [r["no_log_gap"][key] for r in rs]
        if any(x is None for x in a + b): L.append(f"| {NICE[ds]} | {label} | none | - | - | - |"); continue
        dr = float(np.mean(a) - np.mean(b)); k = {"auc_known_source_attackers": "known", "auc_new_source_attackers": "new", "auc_all_attackers": "all"}[key]
        src_n = rs[0]["attack_sources"].get(k, sum(rs[0]["attack_sources"].values())); win_n = rs[0]["attack_windows"].get({"known": "known_source", "new": "new_source"}.get(k, ""), sum(rs[0]["attack_windows"].values()))
        L.append(f"| {NICE[ds]} | {label} | {src_n} / {win_n} | {np.mean(a):.3f} ({min(a):.3f} to {max(a):.3f}) | {np.mean(b):.3f} ({min(b):.3f} to {max(b):.3f}) | {dr:+.3f} |")
        if k == "known": drops[ds] = (dr, min(a) - max(b), max(a) - min(b))
L += ["", "### Alerts on benign windows (share above the 99% threshold of the day-0 calibration), final split, mean over seeds", "", "| Dataset | Benign windows | Full model | Without log_gap |", "|---|---|---|---|"]
for ds, rs in R.items():
    for key, label in (("benign_alert_known", "from sources with day-0 history"), ("benign_alert_new", "from new sources")):
        a = [r["full"][key] for r in rs]; b = [r["no_log_gap"][key] for r in rs]
        L.append(f"| {NICE[ds]} | {label} | {fmt(mean(a))} | {fmt(mean(b))} |")
big = [ds for ds, (d, lo, hi) in drops.items() if d > 0.05]
L += ["", f"Rule: detection of attackers with benign history 'leans on source novelty' when the mean AUC drop without log_gap exceeds 0.05 on at least 2 of the 3 datasets. Drops: " + ", ".join(f"{NICE[ds]} {d:+.3f}" for ds, (d, _, _) in drops.items()) + f". **Leans on novelty: {'yes' if len(big) >= 2 else 'no'}** ({len(big)} of {len(drops)} datasets over 0.05).", ""]
open(out, "w").write("\n".join(L) + "\n"); print("\n".join(L))
