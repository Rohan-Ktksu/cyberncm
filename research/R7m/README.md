# R7m: does trimming the learning period fix poisoning?

Follow-up to R7c (plan step 31; PLAN.md section 5, R7 rule: every breach is logged with the mitigation tried and the curve after it; a mitigation counts only if the clean scoreboard numbers do not get worse beyond the seed range). **Status: run complete. Trimming is not adopted: it fails the clean rule at every level, helps only at low poison for three families, and not at all for the web attacks. Method and rules unchanged from the commit before the run.**

## The problem

R7c found that mixing 0.5 to 2% of one attack family's windows into the learning period (day 0) makes v0 miss that family after the in-domain refit of normalisation, codebooks and calibration (R11 level 3): 6 of 20 testable families breached, five on CIC-IDS2017 and one (Botnet Ares) on CSE-CIC-IDS2018.

## The mitigation tested

**Trimming.** Before the refit, the most unusual share q of the day-0 windows (fit and calibration spans alike) is dropped. Unusualness is the distance to the nearest of 32 centres (a coarse codebook by MiniBatchKMeans, n_init 3, random state = the seed, fitted on the poisoned fit span after refitting the feature normalisation): poisoned windows form their own small cluster far from the bulk, which a 512-centre codebook would absorb but a 32-centre one cannot. The refit (normalisation, 512-centre token codebook, 512-centre state codebook, calibration) then uses the trimmed windows only; the GRU is the scoreboard checkpoint as before. q = 1%, 2%, 5% against no trimming.

Poison levels: 0.5% and 2% of the day-0 window count (the two levels around the R7c breach line), the same procedure as R7c (windows of one family from the days after day 0, drawn with the seed, placed at random times in day 0, never more than half the family's windows, the windows used left out of the test). Datasets: CIC-IDS2017 and CSE-CIC-IDS2018 (the two with breaches). Families: the six breached ones (CIC-IDS2017 Botnet, DDoS, Infiltration, Web Attack - Brute Force, Web Attack - XSS; CSE-CIC-IDS2018 Botnet Ares). Seeds 0 to 2.

**Not tested here** (they are process steps, not model changes): learning only from an owner-confirmed clean period (it assumes no poison, so a rerun would be vacuous) and comparing the old and new model for a day before switching (needs a live deployment).

## Decision rules (fixed now)

1. **Clean rule.** For a trim level q on a dataset, with no poison: the mean over seeds of the final family-mean AUC must be at least the lowest seed value of the untrimmed model, and the share of benign final windows above the threshold (set at the 99th percentile of the trimmed calibration windows) must not exceed the highest untrimmed seed value by more than 0.01. A trim level that fails is not usable on that dataset.
2. **A family is fixed at q** when its detection on the final split, mean over seeds, is at least 0.5 at both poison levels (0.5% and 2%) and the clean rule holds for q on that dataset. The smallest such q is reported.
3. Mitigation is **adopted** only if it fixes at least the five CIC-IDS2017 families or all six, and the clean rule holds; otherwise the remaining breaches go into the model card as stated limits.

## Known limits, stated now

- Trimming removes legitimately rare normal behaviour as well; the clean rule measures that cost on these datasets only, whose normal traffic is lab traffic.
- A poisoner who also makes the attack windows look usual (mimicry, R7a) or who poisons more than q of the windows would defeat it; poison above 2% was not tested here.
- The coarse score assumes poisoned windows are unusual relative to the bulk; a family whose windows resemble normal traffic (R7c: Infiltration, Portscan) may not be separable.
- Three seeds, two datasets, six families; 2 to 11 attacking sources per dataset.
- The refit is in-domain and does not retrain the GRU.

## Results

3 seeds on two datasets, six families, poison at 0.5% and 2% of day 0, trim 0, 1, 2 and 5%. Per-seed files are on Drive (`cyberncm-data/r7m/`).

#### Clean cost of trimming (no poison): final family-mean AUC and share of benign final windows above the threshold, mean (min to max over seeds)

| Dataset | Trim | AUC | False share | Within the clean rule |
|---|---|---|---|---|
| CIC-IDS2017 | 0% | 0.951 (0.942 to 0.966) | 0.0813 (0.0745 to 0.0936) | baseline |
| CIC-IDS2017 | 1% | 0.958 (0.936 to 0.970) | 0.1156 (0.1107 to 0.1229) | NO |
| CIC-IDS2017 | 2% | 0.968 (0.967 to 0.969) | 0.1124 (0.1114 to 0.1140) | NO |
| CIC-IDS2017 | 5% | 0.965 (0.963 to 0.966) | 0.1318 (0.1165 to 0.1449) | NO |
| CSE-CIC-IDS2018 | 0% | 0.989 (0.988 to 0.991) | 0.0611 (0.0513 to 0.0716) | baseline |
| CSE-CIC-IDS2018 | 1% | 0.984 (0.978 to 0.986) | 0.0698 (0.0586 to 0.0785) | NO |
| CSE-CIC-IDS2018 | 2% | 0.984 (0.983 to 0.987) | 0.0744 (0.0681 to 0.0844) | NO |
| CSE-CIC-IDS2018 | 5% | 0.979 (0.975 to 0.983) | 0.0837 (0.0666 to 0.0997) | NO |

#### Detection of the poisoned family on the final split, mean over seeds

| Dataset | Family | Poison | no trim | trim 1% | trim 2% | trim 5% | Fixed at (smallest trim with detection at least 0.5 at both poison levels and clean rule met) |
|---|---|---|---|---|---|---|---|
| CIC-IDS2017 | Botnet | 0.5% | 0.13 | 0.45 | 0.52 | 0.90 |  |
| CIC-IDS2017 | Botnet | 2.0% | 0.01 | 0.04 | 0.06 | 0.05 | not fixed |
| CIC-IDS2017 | DDoS | 0.5% | 0.08 | 0.08 | 0.40 | 0.70 |  |
| CIC-IDS2017 | DDoS | 2.0% | 0.11 | 0.11 | 0.40 | 0.70 | not fixed |
| CIC-IDS2017 | Infiltration | 0.5% | 0.56 | 0.52 | 0.58 | 0.50 |  |
| CIC-IDS2017 | Infiltration | 2.0% | 0.56 | 0.48 | 0.67 | 0.52 | not fixed |
| CIC-IDS2017 | Web Attack - Brute Force | 0.5% | 0.04 | 0.04 | 0.04 | 0.06 |  |
| CIC-IDS2017 | Web Attack - Brute Force | 2.0% | 0.03 | 0.03 | 0.03 | 0.03 | not fixed |
| CIC-IDS2017 | Web Attack - XSS | 0.5% | 0.00 | 0.00 | 0.00 | 0.00 |  |
| CIC-IDS2017 | Web Attack - XSS | 2.0% | 0.00 | 0.00 | 0.00 | 0.33 | not fixed |
| CSE-CIC-IDS2018 | Botnet Ares | 0.5% | 0.79 | 0.98 | 0.75 | 0.74 |  |
| CSE-CIC-IDS2018 | Botnet Ares | 2.0% | 0.43 | 0.59 | 0.55 | 0.50 | not fixed |

Families fixed: none
Families not fixed: CIC-IDS2017 Botnet, CIC-IDS2017 DDoS, CIC-IDS2017 Infiltration, CIC-IDS2017 Web Attack - Brute Force, CIC-IDS2017 Web Attack - XSS, CSE-CIC-IDS2018 Botnet Ares


## Answer in five lines

1. **Trimming is not adopted: no family is fixed under the rules as fixed.** Every trim level fails the clean rule on both datasets, so the "fixed at" column is empty by rule. On CIC-IDS2017 trimming lifts the clean AUC (0.951 to 0.958, 0.968 and 0.965) but raises the share of benign windows above the threshold from 0.081 to 0.112 to 0.132; on CSE-CIC-IDS2018 it lowers the clean AUC from 0.989 to 0.984 and below (just outside the seed range 0.988 to 0.991) and raises the false share from 0.061 to 0.070 to 0.084.
2. **Where trimming does help, it helps only at the lower poison level.** At 0.5% poison, a 5% trim lifts CIC-IDS2017 Botnet from 0.13 to 0.90 and DDoS from 0.08 to 0.70, and a 1% trim lifts CSE-CIC-IDS2018 Botnet Ares from 0.79 to 0.98. At 2% poison, Botnet stays at 0.05 to 0.06, DDoS only reaches 0.40 to 0.70, and Ares rises to 0.59 at 1% and 0.50 at 5%.
3. **It does nothing for the web attacks.** CIC-IDS2017 Web Attack - Brute Force (0.03 to 0.06) and XSS (0.00, 0.33 only at 5% trim and 2% poison) stay undetected at every trim level, which fits the idea that their windows look like the bulk of normal web traffic and are therefore not "unusual" and cannot be trimmed. Infiltration was already around 0.5 here (0.56 untrimmed at both levels) and trimming neither clearly helps nor hurts.
4. **The poisoning breach stays, as a stated limit.** The six breached families of R7c remain breached under the rule; the model card says v0 can be blinded by a poisoned learning period and that trimming only partly reduces this at the cost of more false alerts.
5. **The practical mitigation is a process one:** learn only from a period the owner has confirmed clean (not testable here, since it assumes no poison) and compare the old and new model for a day before switching (needs a live deployment). The ledger entry "must not claim robust to a poisoned learning period" stands.

## Evidence limits

- **Run-to-run noise:** the untrimmed rows here differ from R7c's for the same families (Infiltration 0.56 here against 0.38 and 0.53 in R7c) because each run draws its poison windows from a different random stream; so family numbers near 0.5 should be read as roughly 0.5 plus or minus 0.15, and only the large moves (Botnet and DDoS with a 5% trim, Brute Force and XSS unmoved) are firm.
- **Two datasets, six families, three seeds**; the clean rule uses the three untrimmed seeds' range, which is narrow, so it is a strict test (a 0.005 AUC drop on CSE-CIC-IDS2018 is outside it).
- **One trim score** (distance to 32 coarse centres) and one set of trim levels; other robust refits (trimmed means, median-based calibration, a leave-out check of the refit against the old model) were not tried.
- **Poison above 2% and attacks that also mimic normal traffic** were not tested.
- The benign false share is measured at the threshold set on the trimmed calibration windows, as the protocol states; its baseline (6 to 8%) is far above the nominal 1%, because normal traffic in the final days differs from day 0 (the same drift behind R4).

## Deviations

None yet.

## Reproduce

`python research/R7m/code/r7m_trim.py <checkpoint> <windows.npz> out.json <seed> <family names, comma separated>` from a folder with `ncm/`, then `python research/R7m/code/r7m_decide.py <results dir> out.md`.
