# R6c: unit of scoring, per source, per source-destination, per source-service

Plan step 22 (PLAN.md section 5, R6c). **Status: run complete on all five datasets at 5 seeds. Neither candidate passes the improvement rule. Method and rule unchanged from the commits before the run.**

## Question

Lateral movement is a per-destination pattern (plan, R6c). Does scoring the traffic of one source towards one destination, or towards one service, separately do better than scoring everything a source does together?

## Method

The five prep scripts all build their windows through one function, `prep.windows`, which groups flows by (source, 5-second window). `prep_keyed.py` wraps that function so the grouping key becomes **(source, destination)** or **(source, service)**, where service is the destination port if it is below 1,024 and 0 otherwise. The unchanged prep scripts then rerun on the raw flows (CIC-IDS2017 CSVs with the original-flow hour recovery, UNSW-NB15 parquet, CSE-CIC-IDS2018 day parquets, Unraveled CSVs, CICAPT-IIoT packet CSVs), each in its own folder so the canonical `windows.npz` files are never touched. Days, labels, families and features are those of the original prep; only the key changes. The mapping from a window's key to its source is saved next to the windows.

Scoring (`r6c_eval.py`) uses **token distance only**, with no GRU: the 32 features are normalised by the training-span mean and standard deviation of the keyed windows (clipped at +-10), a codebook of 512 centres is fitted by MiniBatchKMeans (n_init 3, random state = seed) on the training span (at most 300,000 windows), the raw score is the distance to the nearest centre, standardised on the calibration span and smoothed per key and day with the EWMA (0.1) of v0. Training span, calibration span (day 0, first 80% and last 20% of time), dev and final days, families and the false-alert measure are those of `research/SCOREBOARD.md`. Attackers and benign hosts are identified by their **source** address, so the host-day measure still counts hosts. Seeds 0 to 4 (the seed sets the k-means start). No retuning on final.

Candidates: **per source-destination pair** and **per source-service**. Reference: **token distance, 512 centres, per source** (the scoreboard row "token distance, smoothed", same seeds).

## Decision rule (fixed now)

PLAN.md section 4 improvement rule against the reference: on a dataset a candidate is *better* when its seed minimum on dev is above the reference's seed maximum, and *worse* when its seed maximum is below the reference's seed minimum (dev or final). It is an improvement when it is better on dev on at least 3 of 5 datasets, worse on none, and on the datasets where it is better on dev its final mean is not below the reference's. Two candidates, one rule; a pass is a lead needing the independent rerun (PLAN.md step 27). Differences inside the seed range are not wins.

## Known limits, stated now

- **The benign set changes with the unit.** Per-pair windows are far more numerous and sparser than per-source windows, so the AUC of a family against "the benign windows of the split" is computed against a different population. The rule is applied as written, but a difference may reflect that change as much as the scoring itself.
- **Several of the 32 features are degenerate per pair.** The fan-out features (distinct destinations, destination ports and their ratios) are almost constant when a window holds one destination; per-service windows keep them partly. This is inherent to the unit, not an oversight.
- The GRU (v0) is not retrained on keyed windows; only token distance is compared. If a keyed unit helped, a GRU on it would be a further step.
- Windows are cut per key, so a source that talks to many destinations in a window contributes many windows; host-day false-alert counts and the "alerted within 5 minutes" test are still per source.
- The false-alert measure rests on 2 to 11 attacking sources per dataset and sets its threshold with the split's own labels (a best case).
- UNSW-NB15 and CICAPT-IIoT inherit the approximations of their prep scripts (no TCP flags / initial window).

## Results

Mean over 5 seeds, five datasets. Per-seed files and the keyed windows are on Drive (`cyberncm-data/r6c/`). Dev numbers in brackets. The reference is token distance with 512 centres per source (the scoreboard row), same seeds.

Size of the keyed window sets (seed 0 run):

| Key | CIC-IDS2017 | UNSW-NB15 | CSE-CIC-IDS2018 | Unraveled | CICAPT-IIoT |
|---|---|---|---|---|---|
| pair | 396,606 windows, 61,926 keys | 1,046,166 windows, 311 keys | 14,217,940 windows, 1,394,633 keys | 3,753,845 windows, 54,084 keys | 321,353 windows, 137 keys |
| service | 205,796 windows, 482 keys | 750,801 windows, 406 keys | 7,030,658 windows, 85,444 keys | 2,317,785 windows, 3,197 keys | 315,198 windows, 52 keys |

#### Family-mean AUC, mean over seeds (final split; dev in brackets)

| Unit | CIC-IDS2017 | UNSW-NB15 | CSE-CIC-IDS2018 | Unraveled | CICAPT-IIoT |
|---|---|---|---|---|---|
| per source (reference: token distance, 512 centres) | 0.951 (0.995) | 0.940 (0.947) | 0.986 (0.999) | 0.857 (0.852) | 0.833 (0.936) |
| per source-destination pair | 0.970 (0.990) | 0.977 (0.974) | 0.980 (1.000) | 0.835 (0.977) | 0.965 (0.989) |
| per source-service | 0.977 (0.997) | 0.970 (0.971) | 0.988 (0.999) | 0.906 (0.843) | 0.728 (0.894) |

#### False alerts per benign host-day at 80% in 5 minutes (final; a best case)

| Unit | CIC-IDS2017 | UNSW-NB15 | CSE-CIC-IDS2018 | Unraveled | CICAPT-IIoT |
|---|---|---|---|---|---|
| per source | 9.73 | 2.24 | 0.34 | 6.58 | 5.60 |
| per source-destination pair | 84.19 | 1.03 | 0.75 | 6.51 | 1.45 |
| per source-service | 32.23 | 0.42 | 0.29 | 12.53 | 28.26 |

#### Improvement rule against per-source token distance

| Candidate | Better on dev | Worse (dev or final) | Final not below reference where better on dev | Improvement |
|---|---|---|---|---|
| per source-destination pair | UNSW-NB15, Unraveled, CICAPT-IIoT | CIC-IDS2017 dev, CSE-CIC-IDS2018 final, Unraveled final | no | no |
| per source-service | UNSW-NB15 | CSE-CIC-IDS2018 dev, CICAPT-IIoT dev, CICAPT-IIoT final | yes | no |

## Answer in five lines

1. **No candidate passes the rule.** Per source-destination pair is better than the per-source reference on dev on three datasets (UNSW-NB15 0.974 against 0.947, Unraveled 0.977 against 0.852, CICAPT-IIoT 0.989 against 0.936), but it is worse on CIC-IDS2017 dev (0.990 against 0.995), CSE-CIC-IDS2018 final (0.980 against 0.986) and Unraveled final (0.835 against 0.857), and on Unraveled its final mean is below the reference. Per source-service is better on dev only on UNSW-NB15 and worse on CSE-CIC-IDS2018 dev and CICAPT-IIoT.
2. **The unit changes the answer a great deal.** On final, per pair lifts CICAPT-IIoT from 0.833 to 0.965, UNSW-NB15 from 0.940 to 0.977 and CIC-IDS2017 from 0.951 to 0.970; per service lifts Unraveled from 0.857 to 0.906 and CIC-IDS2017 to 0.977. These are large effects, bigger than anything in R6a, R6b or R6d.
3. **But the gains are not consistent.** Per pair on Unraveled scores 0.977 on dev and 0.835 on final, a gap of 0.14, so it does not hold across the five-week campaign; per service is much worse on CICAPT-IIoT (0.728 against 0.833). Which unit helps depends on the network.
4. **False alerts move the other way on CIC-IDS2017.** At the 80% / 5 minute point, per pair needs 84 false alerts per benign host-day there against 10 per source (per service 32); on UNSW-NB15 and CICAPT-IIoT per pair needs fewer (1.0 and 1.5 against 2.2 and 5.6). This measure is a best case and rests on 2 to 11 attacking sources per dataset.
5. **A lead, not a result.** Pair-level scoring looks most useful where a few hosts talk to many destinations (UNSW-NB15, CICAPT-IIoT), which fits the plan's reasoning about lateral movement. It would need the GRU retrained on keyed windows and a unit-aware false-alert measure before it could be a v1 candidate.

## Evidence limits

- **The benign population changes with the unit.** Keyed windows are much more numerous and sparser than per-source windows, so the AUC against "the benign windows of the split" is computed against a different set; part of any difference may come from that and not from the scoring. The rule was applied as written.
- Several of the 32 features are near-constant per pair (the fan-out features), by construction of the unit.
- Only token distance was compared; a GRU on keyed windows was not trained.
- The false-alert measure counts episodes per source, with windows of all of a source's keys together, but a source with many keys has many more windows that can alert.
- Two candidates against one rule; no correction. The final-versus-dev gaps on Unraveled and CICAPT-IIoT show how unstable the split-level comparison is with 2 to 4 attacking sources.
- UNSW-NB15 and CICAPT-IIoT inherit the approximations of their prep scripts, and Unraveled's v0 checkpoints (not used here) come from mixed hardware.

## Deviations

- The decision script first failed on the scoreboard folder's fair-forest files, which share its filename pattern; it was fixed to skip them before any result was read. No method, rule or parameter changed.

## Reproduce

For each dataset, in a folder holding the raw inputs as the prep script expects: `python research/R6c/code/prep_keyed.py pair|service <prep script> [args]`, then `python research/R6c/code/r6c_eval.py <windows.npz> <pair_map.npz> <out.json> <seed>`; then `python research/R6c/code/r6c_decide.py ...`.
