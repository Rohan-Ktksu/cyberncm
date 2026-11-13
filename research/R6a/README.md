# R6a: do running averages of the features replace the GRU?

Plan step 20 (PLAN.md section 5, R6a). **Status: run complete on all five datasets at 5 seeds. Rule 1 (GRU removal): not met. Rule 2 (improvement): not met. Method and rules unchanged from the commits before the run.**

## Question

R2 found that history helps and order does not (+0.12 to +0.17 on two stages). Can a plain per-source running average of the 32 features, over about 1 minute, 10 minutes and 1 hour, stand in for the GRU's hidden state, either replacing it or beside it?

## Candidates (everything else as in v0)

- **v0:** the current model, smoothed score (scoreboard row "v0 NCM, smoothed").
- **History only (no GRU):** each window is described by 128 numbers: the 32 normalised features (training-span mean and standard deviation, clipped at +-10, from the checkpoint) and, per source and day, their running averages with time constants of 12, 120 and 720 windows (1 minute, 10 minutes, 1 hour at 5 s per window; coefficient 1 - exp(-1/tau); each average starts at the source's first window of the day). A codebook of 512 centres is fitted by MiniBatchKMeans (n_init 3, random state = the seed) on the training span (at most 300,000 windows). The raw score is the distance to the nearest centre, standardised on the calibration span and smoothed per source with the same EWMA (0.1) as v0. The GRU, the surprise terms and the state codebook are not used.
- **v0 + history:** the sum of the standardised v0 score and the standardised history-only score, standardised on the calibration span.

Training span, calibration span, dev and final splits and the false-alert measure are exactly those of `research/SCOREBOARD.md`. Datasets: all five. Seeds 0 to 4 (for the history-only score the seed changes only the k-means start; v0 and v0 + history use the scoreboard's checkpoint of that seed). No retuning on final.

## Decision rules (fixed now)

1. **GRU removal rule (from PLAN.md section 5):** the GRU is removed if the history-only score is within 0.01 family-mean AUC of v0 on every dataset and no worse on the false-alert measure. Operationalised: for each of the five datasets and both splits, mean over seeds of (history-only AUC minus v0 AUC) is at least -0.01, and the history-only mean false alerts per benign host-day at 80% in 5 minutes (scoreboard measure, a best case) is not above v0's mean. PLAN.md names "the A1 metric" (the R4 policy numbers); R4 found no passing policy, so the scoreboard's measure is used and said so here. The PLAN.md variants (d) random forest on history features and (e) v0 without the surprise term are not part of this round (R6f and R6d).
2. **Improvement rule for "v0 + history" (PLAN.md section 4):** on a dataset the candidate is *better* when its seed minimum on dev is above v0's seed maximum (outside the seed range), and *worse* when its seed maximum is below v0's seed minimum. It is an improvement when it is better on dev on at least 3 of 5 datasets, worse on none (dev or final), and on the datasets where it is better on dev its final mean is not below v0's final mean.
3. Differences inside the seed range are not wins.

## Known limits, stated now

- Averages restart each day for each source (the scoring sequences are per source and day, as in v0), so the 1-hour average is cold early in a day.
- The false-alert measure rests on 2 to 11 attacking sources per dataset and sets its threshold with the split's own labels.
- Unraveled's seeds run on mixed hardware (SCOREBOARD.md, Deviations); the history-only score is deterministic given the seed so it is not affected.
- One architecture choice (three time constants, 512 centres) is tried; a different grid is not explored here.

## Results

Mean over 5 seeds with (min to max), final and dev splits, all five datasets. "v0 + history" and v0 use the scoreboard checkpoint of each seed; the history-only score is deterministic given the seed, so its ranges are narrow. The per-seed files are on Drive (`cyberncm-data/r6a/`).

#### Family-mean AUC and false alerts (mean over seeds, range)

| Dataset | Split | Model | Family-mean AUC | Worst family | False alerts per benign host-day at 80% in 5 min |
|---|---|---|---|---|---|
| CIC-IDS2017 | dev | v0 NCM, smoothed | 0.991 (0.980 to 0.997) | 0.971 (0.939 to 0.989) | 0.62 (0.52 to 0.70) |
| CIC-IDS2017 | dev | history only (no GRU) | 0.989 (0.989 to 0.989) | 0.978 (0.977 to 0.979) | 0.75 (0.70 to 0.82) |
| CIC-IDS2017 | dev | v0 + history | 0.995 (0.994 to 0.996) | 0.990 (0.988 to 0.993) | 0.68 (0.61 to 0.76) |
| CIC-IDS2017 | final | v0 NCM, smoothed | 0.954 (0.942 to 0.966) | 0.861 (0.822 to 0.912) | 12.06 (6.37 to 15.16) |
| CIC-IDS2017 | final | history only (no GRU) | 0.952 (0.951 to 0.953) | 0.766 (0.760 to 0.773) | 36.41 (35.32 to 36.89) |
| CIC-IDS2017 | final | v0 + history | 0.965 (0.963 to 0.966) | 0.860 (0.853 to 0.872) | 26.84 (23.37 to 28.53) |
| UNSW-NB15 | dev | v0 NCM, smoothed | 0.949 (0.948 to 0.950) | 0.944 (0.943 to 0.945) | 2.26 (1.20 to 2.99) |
| UNSW-NB15 | dev | history only (no GRU) | 0.951 (0.950 to 0.951) | 0.949 (0.948 to 0.949) | 2.66 (2.23 to 3.09) |
| UNSW-NB15 | dev | v0 + history | 0.949 (0.948 to 0.950) | 0.946 (0.945 to 0.946) | 2.34 (1.83 to 2.58) |
| UNSW-NB15 | final | v0 NCM, smoothed | 0.942 (0.941 to 0.944) | 0.938 (0.936 to 0.939) | 3.01 (1.25 to 4.14) |
| UNSW-NB15 | final | history only (no GRU) | 0.945 (0.945 to 0.946) | 0.942 (0.941 to 0.943) | 2.05 (1.91 to 2.26) |
| UNSW-NB15 | final | v0 + history | 0.943 (0.942 to 0.944) | 0.940 (0.939 to 0.941) | 2.52 (1.54 to 3.54) |
| CSE-CIC-IDS2018 | dev | v0 NCM, smoothed | 1.000 (1.000 to 1.000) | 1.000 (0.999 to 1.000) | 0.00 (0.00 to 0.00) |
| CSE-CIC-IDS2018 | dev | history only (no GRU) | 1.000 (1.000 to 1.000) | 1.000 (0.999 to 1.000) | 0.01 (0.00 to 0.01) |
| CSE-CIC-IDS2018 | dev | v0 + history | 1.000 (1.000 to 1.000) | 1.000 (1.000 to 1.000) | 0.00 (0.00 to 0.01) |
| CSE-CIC-IDS2018 | final | v0 NCM, smoothed | 0.989 (0.988 to 0.991) | 0.982 (0.975 to 0.986) | 0.24 (0.20 to 0.28) |
| CSE-CIC-IDS2018 | final | history only (no GRU) | 0.986 (0.986 to 0.987) | 0.985 (0.984 to 0.985) | 0.52 (0.48 to 0.56) |
| CSE-CIC-IDS2018 | final | v0 + history | 0.989 (0.989 to 0.990) | 0.986 (0.985 to 0.986) | 0.37 (0.35 to 0.40) |
| Unraveled | dev | v0 NCM, smoothed | 0.906 (0.901 to 0.917) | 0.814 (0.803 to 0.835) | 5.87 (5.10 to 6.62) |
| Unraveled | dev | history only (no GRU) | 0.765 (0.762 to 0.767) | 0.533 (0.527 to 0.537) | 10.28 (8.06 to 11.30) |
| Unraveled | dev | v0 + history | 0.835 (0.831 to 0.838) | 0.671 (0.663 to 0.678) | 6.02 (5.57 to 6.73) |
| Unraveled | final | v0 NCM, smoothed | 0.894 (0.884 to 0.899) | 0.760 (0.733 to 0.782) | 13.47 (10.95 to 15.91) |
| Unraveled | final | history only (no GRU) | 0.841 (0.838 to 0.846) | 0.719 (0.715 to 0.722) | 33.91 (32.39 to 35.84) |
| Unraveled | final | v0 + history | 0.878 (0.871 to 0.885) | 0.744 (0.727 to 0.756) | 23.60 (21.40 to 25.22) |
| CICAPT-IIoT | dev | v0 NCM, smoothed | 0.879 (0.853 to 0.908) | 0.879 (0.853 to 0.908) | 3.00 (2.60 to 3.96) |
| CICAPT-IIoT | dev | history only (no GRU) | 0.882 (0.879 to 0.885) | 0.882 (0.879 to 0.885) | 2.12 (0.84 to 3.68) |
| CICAPT-IIoT | dev | v0 + history | 0.888 (0.871 to 0.901) | 0.888 (0.871 to 0.901) | 2.39 (1.60 to 3.72) |
| CICAPT-IIoT | final | v0 NCM, smoothed | 0.697 (0.637 to 0.756) | 0.654 (0.594 to 0.723) | 8.74 (5.18 to 18.93) |
| CICAPT-IIoT | final | history only (no GRU) | 0.820 (0.817 to 0.826) | 0.782 (0.776 to 0.788) | 5.45 (3.68 to 6.54) |
| CICAPT-IIoT | final | v0 + history | 0.796 (0.775 to 0.814) | 0.786 (0.763 to 0.810) | 3.26 (2.61 to 4.00) |

#### Rule 1, GRU removal (history only against v0)

| Dataset | Split | AUC difference (history minus v0) | False alerts, history vs v0 | Within 0.01 and no worse |
|---|---|---|---|---|
| CIC-IDS2017 | dev | -0.003 | 0.75 vs 0.62 | no |
| CIC-IDS2017 | final | -0.002 | 36.41 vs 12.06 | no |
| UNSW-NB15 | dev | +0.002 | 2.66 vs 2.26 | no |
| UNSW-NB15 | final | +0.003 | 2.05 vs 3.01 | yes |
| CSE-CIC-IDS2018 | dev | -0.000 | 0.01 vs 0.00 | no |
| CSE-CIC-IDS2018 | final | -0.003 | 0.52 vs 0.24 | no |
| Unraveled | dev | -0.141 | 10.28 vs 5.87 | no |
| Unraveled | final | -0.053 | 33.91 vs 13.47 | no |
| CICAPT-IIoT | dev | +0.003 | 2.12 vs 3.00 | yes |
| CICAPT-IIoT | final | +0.123 | 5.45 vs 8.74 | yes |

**Rule 1 verdict: the GRU stays (the rule is not met).**

#### Rule 2, improvement (v0 + history against v0)

- Better on dev (seed minimum above v0's seed maximum): none (0 of 5 datasets).
- Worse (seed maximum below v0's seed minimum) on dev or final: Unraveled dev.
- Final mean not below v0's on the datasets that are better on dev: yes.
**Rule 2 verdict: not an improvement.**


## Answer in five lines

1. **The GRU-removal rule is not met.** History only is within 0.01 AUC of v0 on four of the five datasets (differences of -0.003 to +0.003 on CIC-IDS2017, UNSW-NB15 and CSE-CIC-IDS2018, and +0.123 on CICAPT-IIoT final), but on Unraveled it is far behind (0.841 against 0.894 on final, 0.765 against 0.906 on dev), and it needs more false alerts than v0 on CIC-IDS2017 (36 against 12 on final), CSE-CIC-IDS2018 (0.52 against 0.24) and Unraveled (34 against 13). So the GRU stays.
2. **Where the GRU matters and where it does not.** On CIC-IDS2017, UNSW-NB15 and CSE-CIC-IDS2018 the learned state adds at most 0.003 AUC over plain running averages, which fits R2's finding that order adds little. On Unraveled, the five-week campaign, it adds 0.05 to 0.14, and a 1-hour average does not replace it.
3. **On CICAPT-IIoT the GRU hurts.** History only reaches 0.820 on final against 0.697 for v0 (seed ranges do not overlap), with fewer false alerts (5.5 against 8.7).
4. **"v0 + history" is not an improvement.** It is better than v0 on dev on none of the five datasets (outside the seed range), and worse on Unraveled dev (0.835 against 0.906). On CICAPT-IIoT final it is better (0.796 against 0.697) but the rule needs dev.
5. **No new candidate for v1 from this round**; the CICAPT-IIoT result says v0's state can be the weak part on some data, which R6d and R6e should keep in mind.

## Evidence limits

- One design only (three time constants, 512 centres, one smoothing). A different set could change the Unraveled gap; none was tuned here.
- The false-alert measure rests on 2 to 11 attacking sources per dataset and sets its threshold with the split's own labels (a best case), so its large differences (CIC-IDS2017 final 36 against 12 on 7 attackers) are indications, not measurements.
- The averages restart each day per source, so the 1-hour average is cold early in a day; on Unraveled, where sources are active for long periods, a persistent average might do better.
- Unraveled's v0 models come from mixed hardware (see `research/SCOREBOARD.md`).
- Variants (d) and (e) from the plan are not part of this round.

## Deviations

- The first run of the script stopped at once with a missing-key error (the label array name differs between the data loader and the report code). It was fixed before any result existed, and the runs were repeated from scratch. No decision rule or parameter changed.

## Reproduce

From a dataset run directory's `ncm/` folder (with `scoreboard.py`): `python <repo>/research/R6a/code/r6a_history.py artifacts/ncm_gru64_s0.pt out.json 0`.
