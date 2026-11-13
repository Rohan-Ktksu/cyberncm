"""Apply the R12 rule. Usage: python r12_decide.py R12_DIR OUT.md   (files <dataset>_k<K>_s<seed>.json)"""
import glob, json, os, re, sys
import numpy as np
rd, out = sys.argv[1:3]; NICE = {"cic2017": "CIC-IDS2017", "d2018": "CSE-CIC-IDS2018", "unraveled": "Unraveled"}
R = {}
for f in sorted(glob.glob(os.path.join(rd, "*_k?_s?.json"))):
    ds, k, s = re.match(r"(\w+)_k(\d)_s(\d)\.json", os.path.basename(f)).groups(); R.setdefault((ds, int(k)), []).append(json.load(open(f)))
POL = ("none", "share_all", "two_agree"); pol_name = {"none": "no sharing", "share_all": "share every block", "two_agree": "act when 2 other sites agree"}
def agg(rs, scen, E, pol, key, den):
    v = [r["scenarios"][scen][f"{E}_{pol}"]["final"] for r in rs]; return float(sum(x[key] for x in v) / max(sum(x[den] for x in v), 1))
def med(rs, pol):
    xs = [x for r in rs for x in r["time_to_block"]["final"][pol]]; fin = [x for x in xs if x is not None]
    return (float(np.median(fin)) if fin else None, 1 - len(fin) / max(len(xs), 1), float(np.mean([x <= 0 for x in fin])) if fin else 0.0, len(xs))
L = []
for E, lab in (("Einf", "no expiry"), ("E30", "30-second expiry")):
    L += [f"### Share of attack windows prevented (blocked when the window starts), final split, {lab}", "", "| Dataset | Sites | " + " | ".join(pol_name[p] for p in POL) + " |", "|---|---|---|---|---|"]
    for (ds, k), rs in sorted(R.items()): L.append(f"| {NICE[ds]} | {k} | " + " | ".join(f"{agg(rs, 'honest', E, p, 'att_prevented', 'att_windows'):.3f}" for p in POL) + " |")
    L.append("")
L += ["### Time from an attacker's first window at a site to its block there (seconds; median of attacker-site pairs, share never blocked, share blocked before or at the first window), final split", "",
      "| Dataset | Sites | Policy | Median | Never blocked | Blocked at or before first window | Pairs |", "|---|---|---|---|---|---|---|"]
for (ds, k), rs in sorted(R.items()):
    for p in POL:
        m, nv, z0, n = med(rs, p); L.append(f"| {NICE[ds]} | {k} | {pol_name[p]} | {'-' if m is None else f'{m:.0f}'} | {nv:.2f} | {z0:.2f} | {n} |")
dmg = {}
for E, lab in (("Einf", "no expiry"), ("E30", "30-second expiry")):
    L += ["", f"### Benign sources wrongly blocked at sites that did not alert on them themselves (share of such source-site-days with a blocked window), final split, {lab}", "", "| Dataset | Sites | " + " | ".join(pol_name[p] for p in POL) + " |", "|---|---|---|---|---|"]
    for (ds, k), rs in sorted(R.items()): L.append(f"| {NICE[ds]} | {k} | " + " | ".join(f"{agg(rs, 'honest', E, p, 'benign_combos_blocked', 'benign_combos_nosite'):.3f}" for p in POL) + " |")
    L += ["", f"### Damage from one lying site (forged blocks for random benign sources, 5 per hour from site 0): extra share of benign windows blocked at the other sites, final split, {lab}", "", "| Dataset | Sites | " + " | ".join(pol_name[p] for p in POL) + " |", "|---|---|---|---|---|"]
    for (ds, k), rs in sorted(R.items()):
        row = []
        for p in POL:
            d = agg(rs, "lying_site0", E, p, "benign_blocked_honest", "benign_windows_honest") - agg(rs, "honest", E, p, "benign_blocked_honest", "benign_windows_honest"); dmg[(E, ds, k, p)] = d; row.append(f"{d:+.4f}")
        L.append(f"| {NICE[ds]} | {k} | " + " | ".join(row) + " |")
gain = {}; harm = {}
for (ds, k), rs in R.items():
    if k < 3: continue
    gain[ds] = agg(rs, "honest", "Einf", "two_agree", "att_prevented", "att_windows") - agg(rs, "honest", "Einf", "none", "att_prevented", "att_windows")
    harm[ds] = agg(rs, "honest", "Einf", "two_agree", "benign_combos_blocked", "benign_combos_nosite") - agg(rs, "honest", "Einf", "none", "benign_combos_blocked", "benign_combos_nosite")
n_gain = sum(g >= 0.05 for g in gain.values()); ok_harm = all(h <= 0.02 for h in harm.values()); ok_lie = all(dmg[("Einf", ds, 4, "two_agree")] <= 0.001 for ds in gain if ("Einf", ds, 4, "two_agree") in dmg)
L += ["", "### Rule (4 sites, policy 'act when 2 other sites agree', no expiry, against no sharing)", "",
      f"- Gain in attack windows prevented, per dataset: " + ", ".join(f"{NICE[d]} {g:+.3f}" for d, g in gain.items()) + f" ({n_gain} of {len(gain)} at or above +0.05; need at least 2).",
      f"- Added share of wrongly blocked benign source-site-days: " + ", ".join(f"{NICE[d]} {h:+.3f}" for d, h in harm.items()) + f" (all at most +0.02: {ok_harm}).",
      f"- Extra benign windows blocked by the lying site: " + ", ".join(f"{NICE[ds]} {dmg[("Einf", ds, 4, 'two_agree')]:+.4f}" for ds in gain if ("Einf", ds, 4, 'two_agree') in dmg) + f" (all at most +0.001: {ok_lie}).",
      f"- **Sharing under the two-site rule helps more than it harms: {'yes' if (n_gain >= 2 and ok_harm and ok_lie) else 'no'}.**", ""]
open(out, "w").write("\n".join(L) + "\n"); print("\n".join(L))
