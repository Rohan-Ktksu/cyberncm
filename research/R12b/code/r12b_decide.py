"""Apply the R12b rules. Usage: python r12b_decide.py R12B_DIR OUT.md [R12_REFERENCE_DIR]   (files <dataset>_k<K>_r<rule>_s<seed>.json)"""
import glob, json, math, os, re, sys
from r12_reference import check_rule_zero
rd, out = sys.argv[1:3]; NICE = {"cic2017": "CIC-IDS2017", "d2018": "CSE-CIC-IDS2018", "unraveled": "Unraveled"}
RULES = {"0": "2 of 3 above 99.5% (R12's rule)", "1": "5 of 6 above 99.9%", "2": "12 of 12 above 99.9%", "3": "12 of 12 above 99.99%"}
# Clear stale reports before reading inputs: failed runs cannot leave an old verdict.
open(out, "w", encoding="utf-8").write("INCOMPLETE: R12b input validation has not completed; no verdict.\n")
expected = {f"{d}_k{k}_r{r}_s{s}.json" for d in NICE for k in (2, 4) for r in RULES for s in range(3)}
found = {os.path.basename(f) for f in glob.glob(os.path.join(rd, "*_k*_r*_s*.json"))}
missing, extra = expected - found, found - expected
if missing or extra:
    message = "INCOMPLETE: expected the full 72-run protocol; no verdict.\n"
    message += "Missing: " + ", ".join(sorted(missing)) + "\nUnexpected: " + ", ".join(sorted(extra)) + "\n"
    open(out, "w", encoding="utf-8").write(message)
    print(message)
    sys.exit(2)
R = {}
for f in sorted(glob.glob(os.path.join(rd, "*_k?_r?_s?.json"))):
    ds, k, r, s = re.fullmatch(r"(\w+)_k(\d)_r(\d)_s(\d)\.json", os.path.basename(f)).groups()
    with open(f) as stream:
        data = json.load(stream)
    expected_rule = {"0": (2, 3, .995), "1": (5, 6, .999), "2": (12, 12, .999), "3": (12, 12, .9999)}[r]
    rule = data["rule"]
    if data["seed"] != int(s) or data["K"] != int(k) or (rule["k_of"], rule["n_of"], rule["quantile"]) != expected_rule:
        raise ValueError(f"Result metadata contradicts filename/protocol: {f}")
    for pol in ("none", "share_all", "two_agree"):
        times = data["time_to_block"]["final"][pol]
        if not times or len(times) != data["attacker_site_pairs"]["final"] or any(x is not None and (not isinstance(x, (int, float)) or not math.isfinite(x)) for x in times):
            raise ValueError(f"Invalid or empty time-to-block population: {f}")
    R.setdefault((r, ds, int(k)), []).append(data)
# Rule 0 must reproduce the historical R12 populations and counts before interpretation.
reference_dir = sys.argv[3] if len(sys.argv) > 3 else None
if reference_dir is None:
    raise ValueError("INCOMPLETE: R12 reference directory required; no rule-0 reproduction check, no verdict")
for ds in NICE:
    for k in (2, 4):
        for seed in range(3):
            path = os.path.join(reference_dir, f"{ds}_k{k}_s{seed}.json")
            with open(path) as f:
                baseline = json.load(f)
            current = next(x for x in R[("0", ds, k)] if x["seed"] == seed)
            check_rule_zero(current, baseline)

def agg(rs, scen, pol, num, den, E="Einf"):
    v = [x["scenarios"][scen][f"{E}_{pol}"]["final"] for x in rs]; numerator, denominator = sum(a[num] for a in v), sum(a[den] for a in v)
    if not math.isfinite(numerator) or not math.isfinite(denominator) or denominator <= 0 or not 0 <= numerator <= denominator:
        raise ValueError(f"Undefined or invalid rate: {scen}/{pol} {num}/{den}")
    return float(numerator / denominator)
def ttb(rs, pol):
    xs = [x for r in rs for x in r["time_to_block"]["final"][pol]]; n = max(len(xs), 1)
    return sum(x is not None and x <= 0 for x in xs) / n, sum(x is None for x in xs) / n, len(xs)
L = ["# R12b exploratory sensitivity report", "", "Thresholds are author-chosen after R12. These conditional results do not constitute owner approval or an independent confirmation of gate G1.", ""]; verdicts = {}
for r, name in RULES.items():
    dss = [d for d in NICE if (r, d, 4) in R]
    if not dss: continue
    L += [f"### Rule {r}: {name}", "", "| Dataset | Sites | Benign source-site-days blocked by the site's own rule | Attacker-site pairs never blocked (no sharing) | Blocked at or before first window: no sharing / share all / two-site rule | Attack windows prevented: no sharing / share all / two-site rule | Benign wrongly blocked by sharing (added): share all / two-site rule | Lying site, extra benign windows blocked: share all / two-site rule |", "|---|---|---|---|---|---|---|---|"]
    own, never, gain, harm, lie = {}, {}, {}, {}, {}
    for ds in dss:
        for k in (2, 4):
            if (r, ds, k) not in R: continue
            rs = R[(r, ds, k)]; o = agg(rs, "honest", "none", "benign_combos_own", "benign_combos_total")
            f0 = {p: ttb(rs, p) for p in ("none", "share_all", "two_agree")}; pv = {p: agg(rs, "honest", p, "att_prevented", "att_windows") for p in f0}
            hm = {p: agg(rs, "honest", p, "benign_combos_blocked", "benign_combos_nosite") for p in ("share_all", "two_agree")}
            ly = {p: agg(rs, "lying_site0", p, "benign_blocked_honest", "benign_windows_honest") - agg(rs, "honest", p, "benign_blocked_honest", "benign_windows_honest") for p in ("share_all", "two_agree")}
            L.append(f"| {NICE[ds]} | {k} | {o:.3f} | {f0['none'][1]:.2f} | {f0['none'][0]:.2f} / {f0['share_all'][0]:.2f} / {f0['two_agree'][0]:.2f} | {pv['none']:.3f} / {pv['share_all']:.3f} / {pv['two_agree']:.3f} | {hm['share_all']:.3f} / {hm['two_agree']:.3f} | {ly['share_all']:+.4f} / {ly['two_agree']:+.4f} |")
            if k == 4: own[ds], never[ds], gain[ds], harm[ds], lie[ds] = o, f0["none"][1], f0["two_agree"][0] - f0["none"][0], hm["two_agree"], ly["two_agree"]
    usable = all(v <= 0.05 for v in own.values()) and sum(v <= 0.5 for v in never.values()) >= 2
    pays = sum(g >= 0.10 for g in gain.values()) >= 2 and all(h <= 0.02 for h in harm.values()) and all(x <= 0.001 for x in lie.values())
    verdicts[r] = (usable, pays)
    L += ["", f"At 4 sites: own false blocks " + ", ".join(f"{NICE[d]} {v:.3f}" for d, v in own.items()) + "; never blocked " + ", ".join(f"{NICE[d]} {v:.2f}" for d, v in never.items()) + f". **Usable rule: {'yes' if usable else 'no'}.**",
          "Two-site rule against no sharing: gain in pairs blocked at or before the first window " + ", ".join(f"{NICE[d]} {v:+.2f}" for d, v in gain.items()) + "; benign wrongly blocked by sharing " + ", ".join(f"{NICE[d]} {v:.3f}" for d, v in harm.items()) + "; lying-site damage " + ", ".join(f"{NICE[d]} {v:+.4f}" for d, v in lie.items()) + f". **Sharing pays under this rule: {'yes' if pays else 'no'}.**", ""]
up = [RULES[r] for r, (u, p) in verdicts.items() if u and p]; anyp = [RULES[r] for r, (u, p) in verdicts.items() if p]
L += ["### Threshold sensitivity (4 sites, two-site sharing)", "",
      "These are author-chosen operating points, not new acceptance criteria. No G1 approval follows from them.", "",
      "| Level | Own false-block cap | Never-blocked cap (at least 2 datasets) | Gain (at least 2) | Added harm cap | Lying damage cap | Rules meeting all |",
      "|---|---|---|---|---|---|---|"]
for label, own_cap, never_cap, gain_min, harm_cap, lie_cap in (
    ("strict", .025, .25, .15, .01, .0005),
    ("original", .05, .5, .10, .02, .001),
    ("lenient", .10, .75, .05, .04, .002)):
    passed=[]
    for r in RULES:
        rates=[]
        for ds in NICE:
            rs=R[(r, ds, 4)]
            own_rate=agg(rs,"honest","none","benign_combos_own","benign_combos_total")
            f0=ttb(rs,"none"); f2=ttb(rs,"two_agree")
            hm=agg(rs,"honest","two_agree","benign_combos_blocked","benign_combos_nosite")
            ly=agg(rs,"lying_site0","two_agree","benign_blocked_honest","benign_windows_honest")-agg(rs,"honest","two_agree","benign_blocked_honest","benign_windows_honest")
            rates.append((own_rate,f0[1],f2[0]-f0[0],hm,ly))
        if (all(v[0]<=own_cap and v[3]<=harm_cap and v[4]<=lie_cap for v in rates)
                and sum(v[1]<=never_cap for v in rates)>=2 and sum(v[2]>=gain_min for v in rates)>=2):
            passed.append(r)
    L.append(f"| {label} | {own_cap} | {never_cap} | {gain_min} | {harm_cap} | {lie_cap} | {', '.join(passed) or 'none'} |")
L += ["", "Rule-0 scenario counts and populations match all 18 supplied historical R12 reference files.", ""]
L += ["### Verdict", "", ("**Sharing pays under a usable rule: " + "; ".join(up) + ". R12's 'no' was specific to its block rule.**") if up else (("**Sharing pays only under rules that are not usable (" + "; ".join(anyp) + "); no usable rule makes it pay.**") if anyp else "**Sharing does not pay under any of the four rules; R12's 'no' holds across them.**"), ""]
open(out, "w", encoding="utf-8").write("\n".join(L) + "\n"); print("\n".join(L))
