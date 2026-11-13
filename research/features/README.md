# Feature importance and drift (PLAN.md step 17)

**Status: run once, results below. Method section unchanged from the commit before the run.**

## Question

Which of the 32 window features carry the detection signal, and which ones shift between days and between networks (and so may explain the false alarms over time and the cross-network failure in R1)?

## Method

Uses the prepared `windows.npz` of the five datasets. No trained model is involved, so nothing here depends on a seed other than the fixed subsampling seed.

- **Drift between days.** Per dataset and feature: benign windows of the training day (day 0) against the benign windows of each later day with at least 1,000 benign windows. Two numbers: the Kolmogorov-Smirnov statistic (0 = same distribution, 1 = disjoint) and the standardised mean difference. At most 50,000 windows per side, drawn with a fixed seed.
- **Drift between networks.** The same two numbers between the benign training-day windows of each pair of datasets (10 pairs), on the raw features.
- **Importance, model-free.** Final split (second half of the test days, as in `research/SCOREBOARD.md`): for each attack family with at least 10 windows, the AUC of each single feature against benign windows, folded so that 0.5 is useless and 1 is perfect in either direction; then the mean over families.
- **Importance, random forest.** Dev split: a 50-tree forest, benign against any attack (at most 100,000 windows per class), impurity importance. Impurity importance favours continuous features; it is shown as a second opinion, not as the answer.

## What will be reported

Per dataset: the features with the largest day-to-day drift, and the features with the highest importance; whether the important features are also the drifting ones. Across datasets: which features differ most between networks.

## Known limits, stated now

- "Benign" is the dataset label; an address that attacks later still contributes benign-labelled windows here.
- UNSW-NB15 flag and timing features are approximations (R1), so its between-network numbers partly measure that.
- Single-feature AUC ignores interactions; drift statistics on 50,000-window samples are precise to about 0.01.
- Unraveled is one campaign over five weeks; its day-to-day drift mixes weekday and weekend traffic.

## Results (run 2026-11-11, Colab CPU, pinned packages)

### Within one network: benign traffic against the training day

| Dataset | Later days | Median KS over the 32 features | Most drifting features (median KS over days) | Largest single-day KS |
|---|---|---|---|---|
| CIC-IDS2017 | 4 | 0.07 | `fwd_len_max` 0.11, `iat_std` 0.10, `pkt_len_spread` 0.10, `log_dst_ips` 0.09 | `fwd_len_max` 0.11 |
| UNSW-NB15 | 4 | 0.04 | `wellknown_frac` 0.06, `pkt_len_mean` 0.05, `log_bwd_bytes` 0.05, `ack_ratio` 0.05 | `wellknown_frac` 0.07 |
| CSE-CIC-IDS2018 | 4 | 0.06 | `dir_byte_ratio` 0.10, `dur_mean` 0.10, `psh_ratio` 0.09, `pkt_len_mean` 0.09 | `rst_ratio` 0.16 |
| Unraveled | 36 | 0.12 | `dns_frac` 0.28, `fwd_len_max` 0.25, `pkt_len_mean` 0.25, `dur_mean` 0.19 | `unanswered_frac` 0.38 |
| CICAPT-IIoT | 4 | 0.09 | `dur_mean` 0.18, `iat_mean` 0.17, `pkt_iat_mean` 0.16, `iat_std` 0.14 | `wellknown_frac` 0.29 |

### Between networks: benign training-day traffic, pair by pair

| Pair | Median KS over the 32 features | Features with KS above 0.5 (of 32) |
|---|---|---|
| CSE-CIC-IDS2018 and Unraveled | 0.20 | 6 |
| CIC-IDS2017 and CSE-CIC-IDS2018 | 0.25 | 1 |
| CIC-IDS2017 and Unraveled | 0.27 | 3 |
| CIC-IDS2017 and CICAPT-IIoT | 0.44 | 12 |
| Unraveled and CICAPT-IIoT | 0.45 | 13 |
| CSE-CIC-IDS2018 and CICAPT-IIoT | 0.45 | 10 |
| CIC-IDS2017 and UNSW-NB15 | 0.51 | 18 |
| UNSW-NB15 and Unraveled | 0.63 | 25 |
| UNSW-NB15 and CSE-CIC-IDS2018 | 0.66 | 25 |
| UNSW-NB15 and CICAPT-IIoT | 0.75 | 25 |

Features that differ most between networks (mean KS over the 10 pairs): `init_win` 0.61, `log_bwd_pkts` 0.61, `pkt_len_mean` 0.59, `log_fwd_pkts` 0.57. Least: `unanswered_frac` 0.25, `rst_ratio` 0.26, `ips_per_flow` 0.31, `ports_per_flow` 0.32.

### Which features carry the signal

| Dataset | Families | Best single features (family-mean AUC, final split) | Random forest importance (dev split) | Rank correlation, drift against importance |
|---|---|---|---|---|
| CIC-IDS2017 | 8 | `syn_ratio` 0.92, `pkt_len_mean` 0.87, `tcp_frac` 0.84, `init_win` 0.82 | `init_win` 0.24, `new_dst_frac` 0.10, `dur_mean` 0.09, `tcp_frac` 0.09 | -0.12 |
| UNSW-NB15 | 9 | `port_entropy` 0.89, `log_dst_ports` 0.89, `log_dst_ips` 0.88, `log_bwd_pkts` 0.87 | `log_dst_ports` 0.12, `log_bwd_pkts` 0.08, `port_entropy` 0.08, `log_dst_ips` 0.07 | 0.27 |
| CSE-CIC-IDS2018 | 4 | `pkt_len_mean` 0.88, `new_dst_frac` 0.82, `log_bwd_pkts` 0.82, `log_fwd_bytes` 0.81 | `log_fwd_pkts` 0.21, `init_win` 0.16, `log_fwd_bytes` 0.13, `ips_per_flow` 0.12 | 0.54 |
| Unraveled | 5 | `tcp_frac` 0.89, `rst_ratio` 0.87, `ack_ratio` 0.84, `dur_mean` 0.84 | `pkt_len_mean` 0.16, `syn_ratio` 0.15, `fwd_len_max` 0.11, `log_gap` 0.11 | -0.07 |
| CICAPT-IIoT | 2 | `log_fwd_bytes` 0.90, `log_fwd_pkts` 0.89, `wellknown_frac` 0.84, `pkt_len_mean` 0.84 | `pkt_len_mean` 0.11, `ack_ratio` 0.10, `fwd_len_max` 0.09, `wellknown_frac` 0.08 | 0.56 |

Mean single-feature AUC over the five datasets: `log_fwd_pkts` 0.81, `log_fwd_bytes` 0.80, `dur_mean` 0.79, `pkt_len_mean` 0.78.

## Answer in five lines

1. **Inside one network, benign traffic drifts little from day to day**: the median feature moves by a KS of 0.04 to 0.12. Unraveled drifts most (five weeks; `dns_frac`, `fwd_len_max` and `pkt_len_mean` at 0.25 to 0.28).
2. **Between networks the drift is several times larger**: median KS 0.20 to 0.75 per pair. UNSW-NB15 is far from every other dataset (0.51 to 0.75, with 18 to 25 of 32 features above 0.5); part of that is its approximated features (R1).
3. **The features that carry most signal are among those that differ most between networks**: packet and byte counts, `pkt_len_mean`, `init_win`. This fits the cross-network failure in R1, but it is a correlation between two rankings, not a tested cause.
4. **The useful features are different in each dataset** (`syn_ratio` in CIC-IDS2017, port and address fan-out in UNSW-NB15, `tcp_frac` and `rst_ratio` in Unraveled), so no small common feature set stands out.
5. **Within a network, drift and importance are not consistently linked** (rank correlation -0.12 to 0.56), so dropping drifting features is not an obvious fix for false alarms.

## Evidence limits

- Marginal, one feature at a time. CIC-IDS2017 and CSE-CIC-IDS2018 look close here (median KS 0.25), yet R1 found transfer from CIC-IDS2017 to CSE-CIC-IDS2018 near chance, so per-feature drift does not by itself predict transfer.
- CSE-CIC-IDS2018 is the 10% source subsample; CICAPT-IIoT has two families with enough windows; the five datasets have 4, 4, 4, 36 and 4 later days.
- No test of whether removing or rescaling any feature changes detection or false alarms. That is R6b and R11.
- I have not checked the day-level pattern in Unraveled (weekday against weekend); the per-day values are in the JSON.

Full numbers: `results/features_drift.json`.

## Deviations

None.

## Reproduce

`python research/features/code/features_drift.py <cyberncm-data> out.json`
