# R7: can v0 be fooled? (mimicry, poisoned learning period, text path)

Plan step 31 (PLAN.md section 5, R7a, R7c, R7g). **Status: run complete (R7a, R7b, R7c, R7g). One mimicry family and six poisoning families are breached; the learning period is the weak point. Protocol and rules were committed before the runs; three exploratory variants were added after seeing results and are reported separately.** R7b (low and slow) was added after a feasibility check and runs on CIC-IDS2017 only (see its section). R7d to R7f (the mesh) wait for R12.

## What is tested

The detector is v0 (the scoreboard checkpoint of each seed), unchanged. Datasets: CIC-IDS2017, UNSW-NB15, CSE-CIC-IDS2018, Unraveled, CICAPT-IIoT, seeds 0 to 2 (three seeds for time; the scoreboard used five). Scores are v0's smoothed anomaly score with the alarm threshold at the 99th percentile of the benign calibration span of day 0 (the last 20% of day 0), as in R11.

### R7a mimicry

Every attack window (any family) has its features moved toward the benign mean by a fraction a, for the features the sender controls only: x' = x + a (mean_benign - x), with the benign mean taken over day-0 fit-span benign windows. a runs over 0, 0.1, 0.2, 0.25, 0.3, 0.4, 0.5, 0.6, 0.7, 0.75, 0.8, 0.9, 1.0. Features the victim decides are left alone: log_bwd_bytes, log_bwd_pkts, dir_byte_ratio, unanswered_frac, rst_ratio, fin_ratio (what the target answers, not what the sender sends). The others (timing, flag ratios other than the two above, packet sizes, forward bytes and packets, fan-out, new-destination share, port entropy) count as attacker-controlled. Modified windows are rescored through the GRU in their source's sequence. The measure is detection: the share of a family's windows (dev and final days) whose score exceeds the threshold, per family with at least 10 windows in the split.

**Breach rule (fixed now):** a family is breached when its detection falls below 0.5 at a <= 0.5, provided its detection at a = 0 was at least 0.5. A family below 0.5 at a = 0 is reported as "not detected at baseline", not as a breach. The smallest grid value of a with detection below 0.5 is reported per family. Only the final split enters the breach decision.

**Exploratory addendum (added after the mimicry results, outside the rule).** The first mimicry results showed almost no breach, which may be because the six victim-side features stay unmoved and still give attacks away. `mimicryall` repeats R7a with all 32 features movable (a worst case that no real attacker can reach, since the victim decides some of them). It is reported separately and does not change the breach rule or its count.

**Second exploratory addendum (after the worst-case mimicry results).** Moving all features to the benign *mean* left detection at 1.00 on CSE-CIC-IDS2018, Unraveled and CICAPT-IIoT, which probably says that the mean of heterogeneous normal traffic is itself an unusual point (far from every codebook centre), not that those datasets are robust. `mimicrysample` repeats R7a (controlled features only, as in the rule) but moves each attack window toward one randomly drawn real benign window of the day-0 fit span (the same target for every a, drawn with the seed), which at a = 1 gives the controlled features of a real benign window. It is a more realistic attacker than moving to the mean, reported separately, and does not change the breach rule or its count.

### R7c poisoned learning period

**Datasets: CIC-IDS2017, UNSW-NB15 and CSE-CIC-IDS2018 only** (the three where R11 tested adaptation; the five-fold refit per family and poison level would be too slow on the others in this round; this narrowing was decided before any poisoning result existed). The in-domain adaptation of R11 (level 3, full day-0 span): the target refits feature normalisation, both codebooks and the calibration on its own day 0, with the GRU from the scoreboard checkpoint. Attack windows of one family are mixed into day 0 at 0.5%, 1%, 2% and 5% of the day-0 window count (times drawn uniformly over day 0, the attacker's own source kept, drawn without replacement from that family's windows on the days after day 0, never more than half of them), treated as benign for fitting and calibration. The windows used are left out of the test windows; the threshold is the 99th percentile of the original day-0 calibration windows under the poisoned fit. Detection of that family on the dev and final days is measured as in R7a, one family at a time, with 0% as the baseline.

**Breach rule (fixed now):** detection of the family on the final split falls below 0.5 at 2% or less, provided it was at least 0.5 at 0%.

### R7g text path (a review, no run)

Every component that reads packet content or free text is listed in `R7g.md`. Today the answer must be none.

## R7b low and slow (added to this round after checking feasibility; protocol fixed before it runs)

Feasible for **CIC-IDS2017 only**: it is the one dataset whose raw flows (with recovered timestamps) are on Drive. For Tuesday to Friday, each attacking source's attack flows (every flow labelled with an attack family) are re-spaced by a factor k from that source's first attack flow of the day: t' = t0 + k (t - t0), with k = 1 (control), 10, 100, 1,000; benign flows (including the attackers' own) are unchanged. The day is then windowed again by the same `prep.windows` (5-second windows), Monday is the original benign day, and v0 (seeds 0 to 2) scores everything with the threshold from the benign calibration span of Monday as in R7a. Detection per attack family is the share of its windows above the threshold, on the dev and final days.

**Breach rule (fixed now):** a family caught at k = 1 (detection at least 0.5 on final) is breached when its detection on final is below 0.5 at k = 100. k = 1 must reproduce the original windows closely (window counts are printed and compared); a large mismatch is reported as a limit.

Limits: stretching times beyond the capture's end puts windows outside the day's hours, and the model has no clock feature, so this is a test of the model's rate sensitivity, not of a real slow attack's side effects; flows that depend on timing (a brute-force that needs many attempts in a window) change meaning; only one dataset; the detection of a re-windowed family uses new window counts, so numbers are shares of different windows.

## Rules for every test (PLAN.md)

Each breach is logged with the mitigation tried and the curve after it; a mitigation counts only if the clean scoreboard numbers do not get worse beyond the seed range; breaches that remain become stated limits in the model card and "must not claim" entries in the ledger. This round measures the curves and the breaches; mitigations go in a follow-up so each can be rerun against the same curves.

## Known limits, stated now

- Mimicry moves all controlled features by the same fraction toward the benign mean, a simple attacker; a smarter one picks the cheapest features. The "smallest change" search is over the grid only (steps of 0.05 to 0.1), not an optimisation.
- Features are partly interdependent in real traffic (bytes and packets, timing and duration); the transformation can produce windows no real flow set would give, so a breach is an upper bound on how easy fooling is, and a non-breach is not safe.
- Poisoning windows are placed at random times in day 0 with the attacker's own source, so the attacker's GRU sequence on day 0 is not the real one.
- Three seeds, five datasets, 2 to 11 attacking sources each; per-family numbers can rest on a handful of sources.
- The poisoned set is one family at a time; combinations were not tried.

## Results

Per-seed files are on Drive (`cyberncm-data/r7/` and `r7b/`). Three seeds (0 to 2), v0 only, numbers are mean detection over seeds on the final split (the share of a family's windows above the 99% benign threshold). Breach rules are the ones fixed above.

#### R7a mimicry: detection (share of the family's windows above the 99% threshold), mean over seeds, final split

| Dataset | Family | a=0 | a=0.25 | a=0.5 | a=0.75 | a=1.0 | smallest a with detection below half | Breach (below half at a<=0.5) |
|---|---|---|---|---|---|---|---|---|
| CIC-IDS2017 | Botnet | 0.83 | 0.67 | 0.46 | 0.29 | 0.31 | 0.5 | BREACH |
| CIC-IDS2017 | DDoS | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | none up to 1.0 | no |
| CIC-IDS2017 | Infiltration | 0.76 | 0.73 | 0.63 | 0.68 | 0.74 | none up to 1.0 | no |
| CIC-IDS2017 | Infiltration - Portscan | 1.00 | 0.99 | 0.98 | 0.92 | 0.92 | none up to 1.0 | no |
| CIC-IDS2017 | Portscan | 1.00 | 1.00 | 0.99 | 1.00 | 1.00 | none up to 1.0 | no |
| CIC-IDS2017 | Web Attack - Brute Force | 0.99 | 0.82 | 0.99 | 0.99 | 0.85 | none up to 1.0 | no |
| CIC-IDS2017 | Web Attack - SQL Injection | 0.29 | 0.22 | 0.51 | 0.71 | 0.44 | 0.0 | not detected at a=0 |
| CIC-IDS2017 | Web Attack - XSS | 1.00 | 1.00 | 1.00 | 1.00 | 0.99 | none up to 1.0 | no |
| CICAPT-IIoT | APT:credential access | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | none up to 1.0 | no |
| CICAPT-IIoT | APT:discovery | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | none up to 1.0 | no |
| CSE-CIC-IDS2018 | Botnet Ares | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | none up to 1.0 | no |
| CSE-CIC-IDS2018 | Web Attack - Brute Force | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | none up to 1.0 | no |
| CSE-CIC-IDS2018 | Web Attack - SQL | 1.00 | 0.91 | 0.91 | 1.00 | 1.00 | none up to 1.0 | no |
| CSE-CIC-IDS2018 | Web Attack - XSS | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | none up to 1.0 | no |
| Unraveled | AA:Reconnaissance | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | none up to 1.0 | no |
| Unraveled | APT:Cover up | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | none up to 1.0 | no |
| Unraveled | APT:Data Exfiltration | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | none up to 1.0 | no |
| Unraveled | APT:Establish Foothold | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | none up to 1.0 | no |
| Unraveled | APT:Lateral Movement | 0.97 | 0.97 | 0.98 | 0.99 | 1.00 | none up to 1.0 | no |
| UNSW-NB15 | Analysis | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | none up to 1.0 | no |
| UNSW-NB15 | Backdoor | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | none up to 1.0 | no |
| UNSW-NB15 | DoS | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | none up to 1.0 | no |
| UNSW-NB15 | Exploits | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | none up to 1.0 | no |
| UNSW-NB15 | Fuzzers | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | none up to 1.0 | no |
| UNSW-NB15 | Generic | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | none up to 1.0 | no |
| UNSW-NB15 | Reconnaissance | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | none up to 1.0 | no |
| UNSW-NB15 | Shellcode | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | none up to 1.0 | no |
| UNSW-NB15 | Worms | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | none up to 1.0 | no |

Families breached at a<=0.5: 1: CIC-IDS2017 Botnet (first below half at a=0.5)


#### R7c poisoned learning period: detection of the poisoned family on the final split (windows left out of the poisoning), mean over seeds

| Dataset | Family | 0% | 0.5% | 1% | 2% | 5% | Breach (below half at 2% or less) |
|---|---|---|---|---|---|---|---|
| CIC-IDS2017 | Botnet | 0.83 | 0.13 | 0.09 | 0.01 | 0.00 | BREACH |
| CIC-IDS2017 | DDoS | 1.00 | 0.09 | 0.09 | 0.11 | 0.12 | BREACH |
| CIC-IDS2017 | Infiltration | 0.76 | 0.38 | 0.34 | 0.53 | 0.56 | BREACH |
| CIC-IDS2017 | Infiltration - Portscan | 1.00 | 0.93 | 0.92 | 0.95 | 0.83 | no |
| CIC-IDS2017 | Portscan | 1.00 | 1.00 | 1.00 | 0.92 | 0.93 | no |
| CIC-IDS2017 | Web Attack - Brute Force | 0.99 | 0.03 | 0.03 | 0.03 | 0.03 | BREACH |
| CIC-IDS2017 | Web Attack - SQL Injection | 0.29 | 0.25 | 0.21 | 0.62 | 0.54 | not detected at 0% |
| CIC-IDS2017 | Web Attack - XSS | 1.00 | 0.00 | 0.00 | 0.00 | 0.00 | BREACH |
| CSE-CIC-IDS2018 | Botnet Ares | 1.00 | 0.79 | 0.52 | 0.43 | 0.28 | BREACH |
| CSE-CIC-IDS2018 | Web Attack - Brute Force | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | no |
| CSE-CIC-IDS2018 | Web Attack - SQL | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | no |
| CSE-CIC-IDS2018 | Web Attack - XSS | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | no |
| UNSW-NB15 | Analysis | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | no |
| UNSW-NB15 | Backdoor | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | no |
| UNSW-NB15 | DoS | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | no |
| UNSW-NB15 | Exploits | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | no |
| UNSW-NB15 | Fuzzers | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | no |
| UNSW-NB15 | Generic | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | no |
| UNSW-NB15 | Reconnaissance | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | no |
| UNSW-NB15 | Shellcode | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | no |
| UNSW-NB15 | Worms | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | no |

Families breached at 2% or less: 6: CIC-IDS2017 Botnet, CIC-IDS2017 DDoS, CIC-IDS2017 Infiltration, CIC-IDS2017 Web Attack - Brute Force, CIC-IDS2017 Web Attack - XSS, CSE-CIC-IDS2018 Botnet Ares


#### R7b low and slow (CIC-IDS2017, final split): detection at k times slower, mean over seeds

| Family | k=1 | k=10 | k=100 | k=1000 | Breach (caught at k=1 and missed at k=100) |
|---|---|---|---|---|---|
| Botnet | 0.82 | 0.89 | 0.97 | 0.99 | no |
| DDoS | 1.00 | 1.00 | 1.00 | 1.00 | no |
| Infiltration | 0.76 | 0.40 | 0.88 | 0.91 | no |
| Infiltration - Portscan | 1.00 | 1.00 | 1.00 | 1.00 | no |
| Portscan | 1.00 | 1.00 | 1.00 | 1.00 | no |
| Web Attack - Brute Force | 0.99 | 0.68 | 1.00 | 1.00 | no |
| Web Attack - SQL Injection | 0.29 | 0.47 | 1.00 | 1.00 | not detected at k=1 |
| Web Attack - XSS | 1.00 | 0.72 | 1.00 | 1.00 | no |

Families breached at k=100: 0


Exploratory variants added after seeing results, reported separately and outside the breach rules:

#### R7a-all (exploratory, outside the rule): every feature movable, final split

| Dataset | Family | a=0 | a=0.25 | a=0.5 | a=0.75 | a=1.0 | smallest a with detection below half |
|---|---|---|---|---|---|---|---|
| CIC-IDS2017 | Botnet | 0.83 | 0.64 | 0.29 | 0.04 | 0.00 | 0.4 |
| CIC-IDS2017 | DDoS | 1.00 | 0.73 | 0.42 | 0.13 | 0.00 | 0.4 |
| CIC-IDS2017 | Infiltration | 0.76 | 0.63 | 0.56 | 0.53 | 0.46 | 0.9 |
| CIC-IDS2017 | Infiltration - Portscan | 1.00 | 0.99 | 0.95 | 0.75 | 0.02 | 0.9 |
| CIC-IDS2017 | Portscan | 1.00 | 1.00 | 0.87 | 0.81 | 0.13 | 0.9 |
| CIC-IDS2017 | Web Attack - Brute Force | 0.99 | 0.81 | 0.98 | 0.69 | 0.01 | 0.8 |
| CIC-IDS2017 | Web Attack - SQL Injection | 0.29 | 0.22 | 0.42 | 0.31 | 0.00 | 0.0 |
| CIC-IDS2017 | Web Attack - XSS | 1.00 | 1.00 | 1.00 | 0.87 | 0.00 | 0.9 |
| CICAPT-IIoT | APT:credential access | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | none up to 1.0 |
| CICAPT-IIoT | APT:discovery | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | none up to 1.0 |
| CSE-CIC-IDS2018 | Botnet Ares | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | none up to 1.0 |
| CSE-CIC-IDS2018 | Web Attack - Brute Force | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | none up to 1.0 |
| CSE-CIC-IDS2018 | Web Attack - SQL | 1.00 | 0.89 | 0.93 | 1.00 | 1.00 | none up to 1.0 |
| CSE-CIC-IDS2018 | Web Attack - XSS | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | none up to 1.0 |
| Unraveled | AA:Reconnaissance | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | none up to 1.0 |
| Unraveled | APT:Cover up | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | none up to 1.0 |
| Unraveled | APT:Data Exfiltration | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | none up to 1.0 |
| Unraveled | APT:Establish Foothold | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | none up to 1.0 |
| Unraveled | APT:Lateral Movement | 0.97 | 0.96 | 0.98 | 0.99 | 0.99 | none up to 1.0 |
| UNSW-NB15 | Analysis | 1.00 | 1.00 | 1.00 | 1.00 | 0.68 | none up to 1.0 |
| UNSW-NB15 | Backdoor | 1.00 | 1.00 | 1.00 | 1.00 | 0.32 | 1.0 |
| UNSW-NB15 | DoS | 1.00 | 1.00 | 1.00 | 1.00 | 0.29 | 1.0 |
| UNSW-NB15 | Exploits | 1.00 | 1.00 | 1.00 | 1.00 | 0.31 | 1.0 |
| UNSW-NB15 | Fuzzers | 1.00 | 1.00 | 1.00 | 1.00 | 0.37 | 1.0 |
| UNSW-NB15 | Generic | 1.00 | 1.00 | 1.00 | 1.00 | 0.12 | 1.0 |
| UNSW-NB15 | Reconnaissance | 1.00 | 1.00 | 1.00 | 1.00 | 0.30 | 1.0 |
| UNSW-NB15 | Shellcode | 1.00 | 1.00 | 1.00 | 1.00 | 0.33 | 1.0 |
| UNSW-NB15 | Worms | 1.00 | 1.00 | 1.00 | 1.00 | 0.32 | 1.0 |

Families that would be breached at a<=0.5 if every feature were movable: 2


#### R7a-sample (exploratory, outside the rule): controlled features move toward one random real benign window, final split

| Dataset | Family | a=0 | a=0.25 | a=0.5 | a=0.75 | a=1.0 | smallest a with detection below half | Would breach (below half at a<=0.5) |
|---|---|---|---|---|---|---|---|---|
| CIC-IDS2017 | Botnet | 0.83 | 0.69 | 0.55 | 0.48 | 0.58 | 0.7 | no |
| CIC-IDS2017 | DDoS | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | none up to 1.0 | no |
| CIC-IDS2017 | Infiltration | 0.76 | 0.73 | 0.71 | 0.77 | 0.80 | none up to 1.0 | no |
| CIC-IDS2017 | Infiltration - Portscan | 1.00 | 0.99 | 0.99 | 0.97 | 0.96 | none up to 1.0 | no |
| CIC-IDS2017 | Portscan | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | none up to 1.0 | no |
| CIC-IDS2017 | Web Attack - Brute Force | 0.99 | 0.94 | 1.00 | 0.99 | 0.99 | none up to 1.0 | no |
| CIC-IDS2017 | Web Attack - SQL Injection | 0.29 | 0.38 | 0.96 | 1.00 | 1.00 | 0.0 | not detected at a=0 |
| CIC-IDS2017 | Web Attack - XSS | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | none up to 1.0 | no |
| CICAPT-IIoT | APT:credential access | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | none up to 1.0 | no |
| CICAPT-IIoT | APT:discovery | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | none up to 1.0 | no |
| CSE-CIC-IDS2018 | Botnet Ares | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | none up to 1.0 | no |
| CSE-CIC-IDS2018 | Web Attack - Brute Force | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | none up to 1.0 | no |
| CSE-CIC-IDS2018 | Web Attack - SQL | 1.00 | 0.98 | 1.00 | 1.00 | 1.00 | none up to 1.0 | no |
| CSE-CIC-IDS2018 | Web Attack - XSS | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | none up to 1.0 | no |
| Unraveled | AA:Reconnaissance | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | none up to 1.0 | no |
| Unraveled | APT:Cover up | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | none up to 1.0 | no |
| Unraveled | APT:Data Exfiltration | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | none up to 1.0 | no |
| Unraveled | APT:Establish Foothold | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | none up to 1.0 | no |
| Unraveled | APT:Lateral Movement | 0.97 | 0.98 | 0.99 | 1.00 | 1.00 | none up to 1.0 | no |
| UNSW-NB15 | Analysis | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | none up to 1.0 | no |
| UNSW-NB15 | Backdoor | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | none up to 1.0 | no |
| UNSW-NB15 | DoS | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | none up to 1.0 | no |
| UNSW-NB15 | Exploits | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | none up to 1.0 | no |
| UNSW-NB15 | Fuzzers | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | none up to 1.0 | no |
| UNSW-NB15 | Generic | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | none up to 1.0 | no |
| UNSW-NB15 | Reconnaissance | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | none up to 1.0 | no |
| UNSW-NB15 | Shellcode | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | none up to 1.0 | no |
| UNSW-NB15 | Worms | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | none up to 1.0 | no |

Families that would be breached at a<=0.5 under the sampled-window attacker: 0


## Answer in five lines

1. **R7c, poisoned learning period, is the real weakness: 6 of 20 testable families are breached.** On CIC-IDS2017 mixing in 0.5% of one family's attack windows into day 0 drops detection of that family from 0.83 to 0.13 (Botnet), 1.00 to 0.09 (DDoS), 0.99 to 0.03 (Web Brute Force), 1.00 to 0.00 (XSS), 0.76 to 0.38 (Infiltration); on CSE-CIC-IDS2018 Botnet Ares falls from 1.00 to 0.43 at 2%. Port scans, the CSE-CIC-IDS2018 web attacks and all of UNSW-NB15 do not fall (UNSW-NB15 stays at 1.00 even at 5%, which I cannot explain; its approximated features and very separable attacks are the first suspects).
2. **R7a, mimicry, breaches one family of 27 (CIC-IDS2017 Botnet, below half at a = 0.5), but this is a weak test.** Attacker-controlled features were moved toward the benign mean and six victim-side features (bytes back, unanswered share, RST, FIN) were left alone; detection stays at 1.00 on three datasets even with all 32 features at the benign mean, most likely because the mean of heterogeneous traffic is itself an odd point. Moving toward one real benign window (controlled features only) breaches nothing. Read together this says the model leans on the victim-side features and on being far from normal, not that it cannot be imitated: a copy of a real benign window on every feature would presumably not be flagged (not tested), and the all-feature run already shows two CIC-IDS2017 families breached at a <= 0.5 and UNSW-NB15 falling to about 0.3 at a = 1.
3. **R7b, low and slow, breaches nothing on CIC-IDS2017, and slowing the attack makes it more visible, not less** (mean detection on final 0.85 at k = 1, 0.98 at k = 100). A plausible reason, not tested here, is that the model sees the long gaps between windows and sparse windows themselves as unusual; there is a dip at k = 10 for Infiltration (0.40), Brute Force (0.68) and XSS (0.72). A model that flags slowness is not safe from an attacker who also keeps the gap pattern normal.
4. **R7g, the text path: none.** No component reads packet content or free text; the directive schema has no free-text field (see `R7g.md`).
5. **Decision:** the model card must state that v0 can be blinded by a poisoned learning period (poison 0.5% of a family's windows into the first day and that family goes undetected), and the ledger gets a "must not claim robust to poisoning or to mimicry" entry. Mitigations (learn only from an owner-confirmed clean period, trim the most unusual 1 to 5% of training windows, compare old and new model for a day before switching) are the next round, each rerun against these curves.

## Breach log

| Test | Breach | Mitigation tried | Curve after |
|---|---|---|---|
| R7a mimicry | CIC-IDS2017 Botnet | none yet | not run |
| R7c poisoning | CIC-IDS2017 Botnet, DDoS, Infiltration, Web Brute Force, XSS; CSE-CIC-IDS2018 Botnet Ares | none yet (planned: owner-confirmed clean period, trim the most unusual windows) | not run |
| R7b low and slow | none | not needed | |
| R7g text path | none | not needed | |

## Evidence limits

- **Three seeds**, five datasets (R7a), three datasets (R7c), one dataset (R7b); 2 to 11 attacking sources per dataset, so a family's number can rest on a handful of sources.
- **The mimicry attacker is simple** (the same fraction for every controlled feature, toward a mean or a random window); a smarter one that chooses the cheapest features, or keeps the victim-side features normal too, was not tried. The split of features into attacker-controlled and victim-decided is a judgement (an attacker can influence what the victim answers by choosing which targets to hit).
- **The all-features and sampled-window variants were added after the first mimicry result,** which is a forking path; they are outside the rule and reported as exploration.
- **Poisoning windows are placed at random times in day 0** with the attacker's own source, so the attacker's sequence on day 0 is not the real one; detection is measured after an in-domain refit of normalisation, codebooks and calibration (the R11 procedure), not after a full retraining of the GRU.
- **R7b stretches times beyond the capture's end**; the model has no clock feature, so this tests rate sensitivity, not a real slow attack's side effects (an attack that needs many attempts in a window changes meaning when stretched).
- UNSW-NB15's result of no effect under poisoning is unexplained and should not be read as robustness.
- R7d to R7f (forged and replayed directives, induced false blocks, spoofed sources) need the R12 simulation and are not in this round.

## Deviations

- Three exploratory mimicry variants / checks were added after seeing results (`mimicryall`, `mimicrysample`) and the R7b section was added after a feasibility check; all are labelled, each was committed before it ran, and none changes a rule or its count.
- Poisoning was run on the three R11 datasets only (stated before the poisoning results). The CSE-CIC-IDS2018 poisoning jobs for seeds 1 and 2 were also started in parallel extra workers; same script and seeds.
- R7b seeds 1 and 2 reused the cache of seed 0; no other change.

## Reproduce

`python research/R7/code/r7_stress.py mimicry|poison <checkpoint> <windows.npz> out.json <seed>` from a folder with `ncm/`, then `python research/R7/code/r7_decide.py <results dir> out.md`.

## Audit instrumentation — 13 November 2026

Poison-mode JSON now records injected rows that actually enter fit and calibration, effective contamination fractions, pool-capping, and the threshold population. The original method is preserved: frozen backbone, refit normalization/codebooks/calibration, threshold from original calibration rows only. This is not a full-backbone poisoning experiment. Requested poison relative to original day-0 size differs from the resulting fraction of augmented rows.

For a bounded diagnostic, optionally append one exact family name to the existing poison command. Original all-family invocations are unchanged. Unsupported modes and nonexistent/insufficient families now fail explicitly. Example family: `Botnet` for CIC-IDS2017. A new-seed diagnostic is not a reproduction of the old seed-0 result.

UNSW's reported resistance is not explained merely by this instrumentation. Inspect actual fit counts, family sample limits, score changes, threshold shifts, and detection in a rerun with the correct checkpoint before claiming immunity or a bug.
