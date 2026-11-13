# R12: what does sharing buy? (virtual sites)

Plan step 37 (PLAN.md section 5, R12; feeds gate G1: "does sharing help more than it harms?"). **Status: run complete (18 runs). By the rule fixed beforehand, sharing under the two-site rule does not help more than it harms; it does speed up the first block. Method and rule unchanged from the commit before the run.**

## Question

If a network is split into sites that each see only their own hosts' traffic, and sites tell each other which sources they have blocked, how much faster and wider are attackers stopped, and what does it cost in benign hosts wrongly blocked, and in damage from a site that lies?

## Setup

Datasets: CSE-CIC-IDS2018, CIC-IDS2017, Unraveled (raw flows, rewindowed). **Virtual sites:** the victim hosts (destination addresses) are split into K = 2 and K = 4 groups by a fixed hash of the destination address (`pandas.util.hash_array(dst) mod K`; one split, reproducible); each site sees only the flows towards its own hosts, windowed per (source, site) by the same `prep.windows` (5-second windows, 32 features). A source that attacks hosts in several sites appears as one window sequence at each.

**Per-site detector:** the scoreboard v0 checkpoint of the seed (GRU trained on the whole dataset), with the normalisation, both codebooks and the calibration refitted by each site on its own day-0 windows (R11 level 3, which R11 found enough for a new site). Seeds 0 to 2. Day 0 is the learning day; the dev and final days of the scoreboard are the test days, reported separately and decided on final.

**Block rule (fixed now, the same for every policy):** a source is blocked at a site when at least 2 of its last 3 windows there scored above the 99.5th percentile of that site's calibration windows (the last 20% of day 0); the block starts when that window ends. No alert policy meets R4's target, so this rule is not tuned or claimed to be tolerable; it is the common input to the comparison.

**Policies:** (1) *no sharing*, own blocks only; (2) *share every block*: a block at any site applies at every site at once; (3) *act when 2 other sites agree*: a shared block applies at a site only if at least 2 other sites have the source blocked (the site's own blocks always apply; with K = 2 this is the same as no sharing and is reported as such). **Expiry:** a block, own or shared, lasts 30 seconds after the window that triggered it, or never expires; a source whose windows keep alerting is blocked again.

**Lying site:** one site (site 0) also issues forged blocks for random benign sources, 5 per hour of test day, at uniform times, as a signed and accepted directive; the damage is measured at the other sites.

## Measures (final split)

1. **Time to block:** per attacker-site pair with at least one attack window, the time from the first attack window at that site to the first moment the source is blocked there (negative or zero if the block comes first). Median over pairs, share never blocked, share blocked at or before the first window.
2. **Attack windows prevented:** the share of attack windows whose start falls inside an active block at their site.
3. **Benign sources wrongly blocked at sites that detected nothing themselves:** over benign source-site-days with no own block, the share with at least one window inside an active block.
4. **Damage from the lying site:** the extra share of benign windows at the honest sites that fall inside a block, compared with the honest run.

## Decision rule (fixed now)

Sharing under the two-site rule (policy 3, no expiry) **helps more than it harms** when, at K = 4, against no sharing: (a) the share of attack windows prevented rises by at least 0.05 on at least 2 of the 3 datasets; (b) the share of wrongly blocked benign source-site-days (measure 3) rises by at most 0.02 on every dataset; (c) the lying site adds at most 0.001 to the share of benign windows blocked at honest sites (measure 4). If not, the finding is that sharing does not clearly pay on this evidence, and gate G1 says single-site detector (drop the mesh, consensus and federation). "Share every block" and the 30-second expiry are reported for comparison and do not enter the rule.

## Known limits, stated now

- **Sites are an artefact of the datasets:** hosts are split at random, so each site sees a random share of each attacker's traffic. Real sites differ in population, hours and software; sharing between very different sites may behave unlike this.
- **One host split, three seeds, three datasets** (lab data, injected attacks, 2 to 11 attackers per dataset); a source count this small makes per-dataset shares jumpy.
- **No communication delay, loss or clock skew:** a shared block applies at the instant it is issued. Real latency would reduce the gain.
- **The block rule is a fixed choice** (2 of 3 windows above the 99.5th percentile); other rules change the false-block numbers a lot (R4 found no tolerable policy).
- **Windows at a site contain only that site's flows,** so a source's features there differ from the whole-dataset windows the GRU was trained on; the per-site refit of R11 compensates only partly.
- **The lying site is a simple one:** random benign targets at a fixed rate; a targeted liar (protected servers, a rate high enough to trigger two-site agreement with a second liar) was not simulated here, and R7d to R7f stay open for that.
- Attackers that never alert anywhere cannot be helped by sharing; that share is reported as "never blocked".

## Results

3 seeds on each of three datasets and two site counts (18 runs); per-seed files are on Drive (`cyberncm-data/r12/`). Every number is pooled over seeds (summed counts). Final split.

#### Share of attack windows prevented (blocked when the window starts), final split, no expiry

| Dataset | Sites | no sharing | share every block | act when 2 other sites agree |
|---|---|---|---|---|
| CIC-IDS2017 | 2 | 0.901 | 0.985 | 0.901 |
| CIC-IDS2017 | 4 | 0.975 | 0.990 | 0.986 |
| CSE-CIC-IDS2018 | 2 | 0.999 | 1.000 | 0.999 |
| CSE-CIC-IDS2018 | 4 | 0.999 | 1.000 | 0.999 |
| Unraveled | 2 | 0.990 | 0.999 | 0.990 |
| Unraveled | 4 | 0.997 | 0.999 | 0.999 |

#### Share of attack windows prevented (blocked when the window starts), final split, 30-second expiry

| Dataset | Sites | no sharing | share every block | act when 2 other sites agree |
|---|---|---|---|---|
| CIC-IDS2017 | 2 | 0.513 | 0.525 | 0.513 |
| CIC-IDS2017 | 4 | 0.649 | 0.668 | 0.657 |
| CSE-CIC-IDS2018 | 2 | 0.995 | 0.995 | 0.995 |
| CSE-CIC-IDS2018 | 4 | 0.995 | 0.995 | 0.995 |
| Unraveled | 2 | 0.783 | 0.786 | 0.783 |
| Unraveled | 4 | 0.771 | 0.795 | 0.772 |

#### Time from an attacker's first window at a site to its block there (seconds; median of attacker-site pairs, share never blocked, share blocked before or at the first window), final split

| Dataset | Sites | Policy | Median | Never blocked | Blocked at or before first window | Pairs |
|---|---|---|---|---|---|---|
| CIC-IDS2017 | 2 | no sharing | 420 | 0.00 | 0.36 | 33 |
| CIC-IDS2017 | 2 | share every block | -4990 | 0.00 | 0.70 | 33 |
| CIC-IDS2017 | 2 | act when 2 other sites agree | 420 | 0.00 | 0.36 | 33 |
| CIC-IDS2017 | 4 | no sharing | 22 | 0.08 | 0.44 | 39 |
| CIC-IDS2017 | 4 | share every block | -5665 | 0.00 | 0.79 | 39 |
| CIC-IDS2017 | 4 | act when 2 other sites agree | -5090 | 0.03 | 0.71 | 39 |
| CSE-CIC-IDS2018 | 2 | no sharing | 20 | 0.00 | 0.30 | 33 |
| CSE-CIC-IDS2018 | 2 | share every block | -2305 | 0.00 | 0.82 | 33 |
| CSE-CIC-IDS2018 | 2 | act when 2 other sites agree | 20 | 0.00 | 0.30 | 33 |
| CSE-CIC-IDS2018 | 4 | no sharing | 30 | 0.00 | 0.21 | 33 |
| CSE-CIC-IDS2018 | 4 | share every block | -5325 | 0.00 | 0.88 | 33 |
| CSE-CIC-IDS2018 | 4 | act when 2 other sites agree | 10 | 0.00 | 0.48 | 33 |
| Unraveled | 2 | no sharing | 10 | 0.25 | 0.27 | 162 |
| Unraveled | 2 | share every block | 5 | 0.00 | 0.46 | 162 |
| Unraveled | 2 | act when 2 other sites agree | 10 | 0.25 | 0.27 | 162 |
| Unraveled | 4 | no sharing | 10 | 0.17 | 0.28 | 168 |
| Unraveled | 4 | share every block | 5 | 0.00 | 0.48 | 168 |
| Unraveled | 4 | act when 2 other sites agree | 5 | 0.00 | 0.45 | 168 |

#### Benign sources wrongly blocked at sites that did not alert on them themselves (share of such source-site-days with a blocked window), final split, no expiry

| Dataset | Sites | no sharing | share every block | act when 2 other sites agree |
|---|---|---|---|---|
| CIC-IDS2017 | 2 | 0.000 | 0.373 | 0.000 |
| CIC-IDS2017 | 4 | 0.000 | 0.715 | 0.438 |
| CSE-CIC-IDS2018 | 2 | 0.000 | 0.020 | 0.000 |
| CSE-CIC-IDS2018 | 4 | 0.000 | 0.055 | 0.017 |
| Unraveled | 2 | 0.000 | 0.394 | 0.000 |
| Unraveled | 4 | 0.000 | 0.508 | 0.364 |

#### Damage from one lying site (forged blocks for random benign sources, 5 per hour from site 0): extra share of benign windows blocked at the other sites, final split, no expiry

| Dataset | Sites | no sharing | share every block | act when 2 other sites agree |
|---|---|---|---|---|
| CIC-IDS2017 | 2 | +0.0000 | +0.1702 | +0.0000 |
| CIC-IDS2017 | 4 | +0.0000 | +0.1021 | +0.1081 |
| CSE-CIC-IDS2018 | 2 | +0.0000 | +0.0118 | +0.0000 |
| CSE-CIC-IDS2018 | 4 | +0.0000 | +0.0070 | +0.0030 |
| Unraveled | 2 | +0.0000 | +0.0031 | +0.0000 |
| Unraveled | 4 | +0.0000 | +0.0021 | +0.0049 |

#### Benign sources wrongly blocked at sites that did not alert on them themselves (share of such source-site-days with a blocked window), final split, 30-second expiry

| Dataset | Sites | no sharing | share every block | act when 2 other sites agree |
|---|---|---|---|---|
| CIC-IDS2017 | 2 | 0.000 | 0.305 | 0.000 |
| CIC-IDS2017 | 4 | 0.000 | 0.623 | 0.054 |
| CSE-CIC-IDS2018 | 2 | 0.000 | 0.008 | 0.000 |
| CSE-CIC-IDS2018 | 4 | 0.000 | 0.026 | 0.006 |
| Unraveled | 2 | 0.000 | 0.242 | 0.000 |
| Unraveled | 4 | 0.000 | 0.362 | 0.239 |

#### Damage from one lying site (forged blocks for random benign sources, 5 per hour from site 0): extra share of benign windows blocked at the other sites, final split, 30-second expiry

| Dataset | Sites | no sharing | share every block | act when 2 other sites agree |
|---|---|---|---|---|
| CIC-IDS2017 | 2 | +0.0000 | +0.0042 | +0.0000 |
| CIC-IDS2017 | 4 | +0.0000 | +0.0041 | +0.0000 |
| CSE-CIC-IDS2018 | 2 | +0.0000 | +0.0000 | +0.0000 |
| CSE-CIC-IDS2018 | 4 | +0.0000 | +0.0000 | +0.0000 |
| Unraveled | 2 | +0.0000 | +0.0005 | +0.0000 |
| Unraveled | 4 | +0.0000 | +0.0004 | +0.0000 |

#### Rule (4 sites, policy 'act when 2 other sites agree', no expiry, against no sharing)

- Gain in attack windows prevented, per dataset: CIC-IDS2017 +0.011, CSE-CIC-IDS2018 +0.001, Unraveled +0.002 (0 of 3 at or above +0.05; need at least 2).
- Added share of wrongly blocked benign source-site-days: CIC-IDS2017 +0.438, CSE-CIC-IDS2018 +0.017, Unraveled +0.364 (all at most +0.02: False).
- Extra benign windows blocked by the lying site: CIC-IDS2017 +0.1081, CSE-CIC-IDS2018 +0.0030, Unraveled +0.0049 (all at most +0.001: False).
- **Sharing under the two-site rule helps more than it harms: no.**


## Answer in five lines

1. **By the rule fixed beforehand: sharing under the two-site rule does not help more than it harms.** At 4 sites it raises the share of attack windows prevented by only +0.011 (CIC-IDS2017), +0.001 (CSE-CIC-IDS2018) and +0.002 (Unraveled) against the 0.05 needed, adds wrongly blocked benign source-site-days of +0.44 (CIC-IDS2017) and +0.36 (Unraveled) against the 0.02 allowed, and one lying site adds +0.108 (CIC-IDS2017) and +0.005 (Unraveled) of benign windows blocked against the 0.001 allowed. The harm criteria fail on their own, whatever the gain.
2. **The window-share measure hides a real speed gain.** With no expiry and no sharing, 4 sites already prevent 97.5% to 99.9% of attack windows because attacks are long and most windows come after the first block. What sharing changes is the start: the share of attacker-site pairs blocked at or before their first window rises from 0.44 to 0.71 (CIC-IDS2017), 0.21 to 0.48 (CSE-CIC-IDS2018) and 0.28 to 0.45 (Unraveled) with the two-site rule at 4 sites (to 0.79, 0.88 and 0.48 sharing every block), and the median time to block falls from 22 seconds to a block that already stands when the attacker arrives on CIC-IDS2017 (4 sites), and by only a few seconds on the other two (30 to 10 seconds, 10 to 5). Sharing does speed up the first-window defence, mostly on the dataset with the slowest own detection; the rule's measure did not capture it.
3. **The harm is the false alerts spreading.** The block rule is not tolerable on benign traffic (R4 found no tolerable policy), so a benign source wrongly blocked at one site is, with several sites, blocked at others: at 4 sites with the two-site rule and no expiry, 44% (CIC-IDS2017) and 36% (Unraveled) of benign source-site-days that had no alert of their own end up with a blocked window; sharing every block is worse (72% and 51%). A 30-second expiry cuts the two-site harm to 5% and 0.6% (CIC-IDS2017, CSE-CIC-IDS2018) but only to 24% for Unraveled, and costs the protection: windows prevented under the two-site rule fall from 0.986 to 0.657 (CIC-IDS2017, 4 sites) and from 0.999 to 0.772 (Unraveled).
4. **The two-site rule does not stop a lying site when false alerts are common:** forged blocks need only one honest site's own false alert to reach "two sites agree", which is why the damage is +0.108 on CIC-IDS2017 at 4 sites with no expiry (sharing every block: +0.102 to +0.170); with a 30-second expiry the damage is zero under the two-site rule but only because blocks do not last.
5. **For gate G1:** on this evidence, with the alert rule we have, sharing does not pay: the mesh, consensus and federation are not justified, and the single-site detector is the supported product. The result would be worth reopening if the alert policy got far cleaner (R4's gap) or if the lab sites turn out to be unlike real ones; R7d to R7f (induced false blocks, forged and replayed directives, spoofed sources) are not needed to reach this answer, since the harm shows without any attacker on the mesh.

## Evidence limits

- **The harm figures come from the block rule I fixed** (2 of the last 3 windows above the 99.5th percentile), which is not tolerable on benign traffic; a much stricter rule would shrink both the harm and the speed gain. The rule decides the "no" on harm only for this rule; I did not search for a rule that would pass.
- **The windows-prevented measure is saturated** (0.97 to 0.999 without sharing at 4 sites with no expiry), so a gain threshold of +0.05 could not be met on these long attacks; the speed-of-first-block result in line 2 is the informative gain measure and it is positive.
- **Sites are random host groups,** so each site sees a random share of each attacker's traffic and its benign traffic looks like the others'; real sites differ, so sharing between very different sites may do better or worse.
- **Few attackers:** 33 to 39 attacker-site pairs for the two lab datasets, 162 to 168 for Unraveled; one host split, three seeds, per-dataset shares are jumpy.
- **No latency, loss or clock skew:** a shared block applies the instant it is issued, which flatters sharing.
- **The lying site is a simple one** (random benign targets, 5 per hour); a targeted liar was not simulated.
- **CSE-CIC-IDS2018 is the scoreboard's 10% source subsample;** CIC-IDS2017 at 2 sites under the two-site rule is the same as no sharing by construction.
- The simulation assumes one detector checkpoint per site refitted on its own day 0 (R11 level 3), not a retrained model.

## Deviations

- The first version of `r12_decide.py` printed the harm and lying-site tables for no expiry only; the protocol said the 30-second expiry would be reported too, so the script was extended to print both (no change to the rule, which uses no expiry).
- The CSE-CIC-IDS2018 site windows were first built from all 80,919 sources (8.6 million windows); the scoreboard uses a 10% source subsample (8,021 sources). The first two jobs were stopped before producing anything and the simulation now keeps only the scoreboard's sources (`r12_sim.py` takes the scoreboard windows file as an optional fifth argument). CIC-IDS2017 and Unraveled have identical source sets in both, so they are unaffected.

## Reproduce

`python research/R12/code/prep_site.py <K> <prep script> [args]` from a folder with `ncm/` and the raw inputs, then `python research/R12/code/r12_sim.py <site dir> <ckpt> out.json <seed>` (with `ncm/` importable) and `python research/R12/code/r12_decide.py <dir> out.md`.
