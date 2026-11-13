# Scoreboard (PLAN.md section 4)

**Status: results below for all five datasets at 5 seeds each (Unraveled on mixed hardware, see Deviations); the protocol and harness were committed before the run.** Rows are in `research/scoreboard.csv` and `research/scoreboard_families.csv`; the table at the bottom is regenerated whenever more runs are added. Anything changed after seeing results goes under "Deviations".

## What is fixed (PLAN.md section 4, unchanged)

Datasets CIC-IDS2017, CSE-CIC-IDS2018, UNSW-NB15 (in-domain), Unraveled (five-week campaign), CICAPT-IIoT (detection only). Seeds 0 to 4. Headline numbers: family-mean AUC, worst family, false alerts per benign host per day at 80% of attacking sources caught within 5 minutes. Baselines in every table: smoothed isolation forest, smoothed token distance, random forest on single windows, and the current model as "v0". A change is an improvement when it beats v0 by more than the seed range on the dev split of at least 3 of 5 datasets, is not worse on any, and the gain holds on the final split. Every attempt gets a row, failures included.

## How the plan's words are made operational (my choices, for review)

1. **Dev and final split.** Day 0 is the benign training span (as in every earlier round). The remaining days, in time order, are cut in two halves: the first half is dev, the second final. For the 5-day datasets this is days 1-2 and 3-4, as in `evaluate.py`. For Unraveled (36 test days) it is 18 and 18; the plan does not define a split there, so this is new. CICAPT-IIoT has 4 test days, so 2 and 2.
2. **Family-mean AUC and worst family.** For each attack family with at least 10 windows in the split, AUC of that family against the benign windows of the same split; mean and minimum over families. Same as `evaluate.py`. For Unraveled a family is a `signature:stage` pair.
3. **False alerts per benign host per day at the 80% / 5 minute point.** Per split, with the score fixed: an attacking source is caught if its score exceeds the threshold in a window within 5 minutes of its first attack-labelled window (alerts before that do not count). The threshold is the lowest one that catches at least 80% of the attacking sources in the split. The measure is then the number of false alert episodes (runs of alert windows with gaps of at most 60 s) per benign (source, day), over benign sources, using `ncm/metrics.py`. A benign source is one with no attack window in the split. One global threshold per split, no recalibration: threshold policies are R4's subject.
4. **Few attackers.** With few attacking sources the 80% rule is coarse (one source is 100%). The tables show the number of attacking and benign sources next to this measure; CIC-IDS2017 dev has one attacking source, so its value there rests on one address. Its final split has 7, so "80%" there means 6 of 7 and the smoke test's bootstrap interval ran from about 3.5 to 22 around a value of 12.7. On any dataset and split with fewer than 10 attacking sources, treat the false-alert value as a rough indication: a difference there may be one address behaving differently. Lean on the datasets with more attacking sources for this measure; the counts are in every results table.
5. **Baselines.** Token distance and isolation forest use the same smoothing as v0. The random forest follows `evaluate.py` Part 2 (leave one family out; benign windows of even 30-minute blocks plus attack windows of the other families; scored against benign windows of odd blocks) but with 100 trees instead of 200, to fit the time on a 2-CPU runtime. It is supervised, so it gets the AUC columns only. **It also trains on windows from the test days (see the reading of the table), so it is not a like-for-like baseline for the unsupervised rows; a fairer variant (day 0 benign plus attack windows of the dev split only) is planned, not run.** The benign training windows are capped at 200,000 (a fixed random subset); this only bites on CSE-CIC-IDS2018 and Unraveled.
   The random forest and the isolation forest are fitted on window features and a fixed random seed, not on the trained model, so their rows do not change with the model seed: they are computed once, with seed 0, and shown as identical across seeds (range zero) rather than recomputed five times.
6. **Uncertainty.** Range over seeds, plus a 95% bootstrap interval (200 resamples) that resamples sources, jointly attackers and benign hosts, for the family-mean AUC and the false-alert measure. The bootstrap is computed on seed 0's model only: it measures sampling of sources, not training variance, and is reported next to the seed range, not instead of it.
7. **Models.** All five seeds trained fresh, GRU-64, in the pinned environment of `requirements.txt` (`train.py gru 64 <seed>`), per dataset. CSE-CIC-IDS2018 is the fixed 10% source subsample used in R1. The shipped prototype checkpoints are not used.
8. **Files.** `ncm/scoreboard.py` writes one JSON per (dataset, seed); results are under `research/scoreboard/`.

## Known limits, stated now

- Lab datasets; one campaign in Unraveled; label errors in the CIC datasets.
- The final split is read once per model version; a second look needs a new held-out period.
- **The false-alert measure is a best case.** Its threshold is chosen with the attack labels of the same split (the lowest level that just reaches 80%). A real site has no labels and must set its level beforehand from past traffic, so a deployed alarm would likely do worse. Use the number to compare models with each other, never as what a customer would see. Alarm rules set without labels are R4's subject.

## Deviations

- **Random forest scoring fixed (2026-11-11, before any results table was built).** The first version of `scoreboard.py` scored the forest against all benign windows of the split, including the even-block windows it was trained on, which contradicts point 5 above and flatters it (CIC-IDS2017 seed 0 showed 1.000 dev and 0.974 final). The script now scores against benign windows of odd blocks only, and the random forest rows of the datasets already scored were recomputed with `--rf-only`. Found in review, not by me.
- **Random forest is not a fair baseline as built (2026-11-11, noted in review after the table was built).** It trains on test-period windows from the same hosts, so its rows are reported but must not be used to judge v0. The fair variant described under the table is the correction; it has not been run.
- **Unraveled completed with 5 seeds (2026-11-12), on mixed hardware.** Seed 0 trained on the 2-CPU runtime; seeds 1, 2 and 4 trained in parallel on an 8-CPU runtime (about 2.4 hours each, slowed by CPU oversubscription) and seed 3 was retrained alone after a runtime reset (14 minutes). Same pinned packages throughout, but thread counts differ, so the models are not bit-identical to a run on one machine; the seed range reflects that as well as the seed. The fair random forest for Unraveled ran afterwards.

## Results, v0, five datasets, 5 seeds each (commit `aec4298`)

Mean over seeds with (min to max). The interval in square brackets is the 95% bootstrap over sources for seed 0's model. Random forest and isolation forest do not depend on the model seed (one run).

### CIC-IDS2017 (5 seeds)

| Model | Split | Family-mean AUC | Worst family | False alerts per benign host-day at 80% in 5 min | Attacking / benign sources |
|---|---|---|---|---|---|
| isolation forest, smoothed | dev | 0.951 (0.951 to 0.951) [0.887 to 0.983] | 0.785 (0.785 to 0.785) | 21.39 (21.39 to 21.39) [6.83 to 43.77] | 1 / 19 |
| isolation forest, smoothed | final | 0.957 (0.957 to 0.957) [0.796 to 0.978] | 0.841 (0.841 to 0.841) | 40.63 (40.63 to 40.63) [16.49 to 54.51] | 7 / 11 |
| random forest, fair (day 0 benign + dev-split attacks of other families) | dev | n/a | n/a | n/a | n/a / n/a |
| random forest, fair (day 0 benign + dev-split attacks of other families) | final | 0.974 | 0.877 | n/a | n/a / n/a |
| random forest, single windows (leave-one-family-out) | dev | 1.000 | 1.000 | n/a | n/a / n/a |
| random forest, single windows (leave-one-family-out) | final | 0.971 | 0.866 | n/a | n/a / n/a |
| token distance, smoothed | dev | 0.995 (0.992 to 0.997) [0.991 to 0.998] | 0.982 (0.968 to 0.990) | 0.62 (0.55 to 0.70) [0.23 to 1.53] | 1 / 19 |
| token distance, smoothed | final | 0.951 (0.931 to 0.971) [0.891 to 0.974] | 0.866 (0.812 to 0.906) | 9.73 (9.11 to 10.11) [1.41 to 20.14] | 7 / 11 |
| v0 NCM, smoothed | dev | 0.991 (0.980 to 0.997) [0.948 to 0.994] | 0.971 (0.939 to 0.989) | 0.62 (0.52 to 0.70) [0.24 to 1.72] | 1 / 19 |
| v0 NCM, smoothed | final | 0.954 (0.942 to 0.966) [0.890 to 0.969] | 0.861 (0.822 to 0.912) | 12.06 (6.37 to 15.16) [1.39 to 21.12] | 7 / 11 |

### UNSW-NB15 (5 seeds)

| Model | Split | Family-mean AUC | Worst family | False alerts per benign host-day at 80% in 5 min | Attacking / benign sources |
|---|---|---|---|---|---|
| isolation forest, smoothed | dev | 0.916 (0.916 to 0.916) [0.818 to 0.966] | 0.904 (0.904 to 0.904) | 4.77 (4.77 to 4.77) [0.34 to 6.91] | 4 / 38 |
| isolation forest, smoothed | final | 0.915 (0.915 to 0.915) [0.799 to 0.958] | 0.909 (0.909 to 0.909) | 6.06 (6.06 to 6.06) [0.21 to 10.44] | 4 / 37 |
| random forest, fair (day 0 benign + dev-split attacks of other families) | dev | n/a | n/a | n/a | n/a / n/a |
| random forest, fair (day 0 benign + dev-split attacks of other families) | final | 0.961 | 0.953 | n/a | n/a / n/a |
| random forest, single windows (leave-one-family-out) | dev | 0.996 | 0.993 | n/a | n/a / n/a |
| random forest, single windows (leave-one-family-out) | final | 0.992 | 0.987 | n/a | n/a / n/a |
| token distance, smoothed | dev | 0.947 (0.946 to 0.949) [0.880 to 0.989] | 0.944 (0.943 to 0.946) | 1.82 (1.67 to 1.91) [0.50 to 2.54] | 4 / 38 |
| token distance, smoothed | final | 0.940 (0.939 to 0.940) [0.848 to 0.979] | 0.937 (0.936 to 0.938) | 2.24 (1.51 to 2.71) [0.39 to 4.28] | 4 / 37 |
| v0 NCM, smoothed | dev | 0.949 (0.948 to 0.950) [0.858 to 0.987] | 0.944 (0.943 to 0.945) | 2.26 (1.20 to 2.99) [1.04 to 5.62] | 4 / 38 |
| v0 NCM, smoothed | final | 0.942 (0.941 to 0.944) [0.875 to 0.981] | 0.938 (0.936 to 0.939) | 3.01 (1.25 to 4.14) [0.27 to 6.71] | 4 / 37 |

### CSE-CIC-IDS2018 (5 seeds)

| Model | Split | Family-mean AUC | Worst family | False alerts per benign host-day at 80% in 5 min | Attacking / benign sources |
|---|---|---|---|---|---|
| isolation forest, smoothed | dev | 0.989 (0.989 to 0.989) [0.981 to 0.995] | 0.984 (0.984 to 0.984) | 0.25 (0.25 to 0.25) [0.06 to 0.41] | 13 / 3676 |
| isolation forest, smoothed | final | 0.807 (0.807 to 0.807) [0.743 to 0.835] | 0.559 (0.559 to 0.559) | 1.94 (1.94 to 1.94) [1.41 to 2.69] | 11 / 3794 |
| random forest, fair (day 0 benign + dev-split attacks of other families) | dev | n/a | n/a | n/a | n/a / n/a |
| random forest, fair (day 0 benign + dev-split attacks of other families) | final | 0.882 | 0.580 | n/a | n/a / n/a |
| random forest, single windows (leave-one-family-out) | dev | 1.000 | 0.999 | n/a | n/a / n/a |
| random forest, single windows (leave-one-family-out) | final | 1.000 | 1.000 | n/a | n/a / n/a |
| token distance, smoothed | dev | 0.999 (0.999 to 1.000) [0.998 to 1.000] | 0.999 (0.998 to 0.999) | 0.00 (0.00 to 0.01) [0.00 to 0.01] | 13 / 3676 |
| token distance, smoothed | final | 0.986 (0.984 to 0.986) [0.972 to 0.994] | 0.977 (0.973 to 0.978) | 0.34 (0.31 to 0.38) [0.19 to 0.58] | 11 / 3794 |
| v0 NCM, smoothed | dev | 1.000 (1.000 to 1.000) [0.999 to 1.000] | 1.000 (0.999 to 1.000) | 0.00 (0.00 to 0.00) [0.00 to 0.01] | 13 / 3676 |
| v0 NCM, smoothed | final | 0.989 (0.988 to 0.991) [0.981 to 0.996] | 0.982 (0.975 to 0.986) | 0.24 (0.20 to 0.28) [0.11 to 0.40] | 11 / 3794 |

### Unraveled (5 seeds)

| Model | Split | Family-mean AUC | Worst family | False alerts per benign host-day at 80% in 5 min | Attacking / benign sources |
|---|---|---|---|---|---|
| isolation forest, smoothed | dev | 0.834 (0.834 to 0.834) [0.681 to 0.987] | 0.690 (0.690 to 0.690) | 14.62 (14.62 to 14.62) [6.90 to 22.60] | 3 / 1790 |
| isolation forest, smoothed | final | 0.799 (0.799 to 0.799) [0.680 to 0.981] | 0.640 (0.640 to 0.640) | 15.77 (15.77 to 15.77) [3.91 to 20.41] | 4 / 457 |
| random forest, fair (day 0 benign + dev-split attacks of other families) | dev | n/a | n/a | n/a | n/a / n/a |
| random forest, fair (day 0 benign + dev-split attacks of other families) | final | 0.647 | 0.481 | n/a | n/a / n/a |
| random forest, single windows (leave-one-family-out) | dev | 0.882 | 0.873 | n/a | n/a / n/a |
| random forest, single windows (leave-one-family-out) | final | 0.922 | 0.779 | n/a | n/a / n/a |
| token distance, smoothed | dev | 0.852 (0.844 to 0.858) [0.707 to 0.999] | 0.705 (0.689 to 0.718) | 4.81 (3.95 to 5.93) [0.70 to 5.75] | 3 / 1790 |
| token distance, smoothed | final | 0.857 (0.849 to 0.863) [0.730 to 0.952] | 0.729 (0.713 to 0.737) | 6.58 (5.40 to 8.34) [1.70 to 7.18] | 4 / 457 |
| v0 NCM, smoothed | dev | 0.906 (0.901 to 0.917) [0.762 to 0.999] | 0.814 (0.803 to 0.835) | 5.87 (5.10 to 6.62) [1.00 to 7.66] | 3 / 1790 |
| v0 NCM, smoothed | final | 0.894 (0.884 to 0.899) [0.809 to 0.998] | 0.760 (0.733 to 0.782) | 13.47 (10.95 to 15.91) [0.07 to 17.42] | 4 / 457 |

### CICAPT-IIoT (5 seeds)

| Model | Split | Family-mean AUC | Worst family | False alerts per benign host-day at 80% in 5 min | Attacking / benign sources |
|---|---|---|---|---|---|
| isolation forest, smoothed | dev | 0.899 (0.899 to 0.899) [0.494 to 0.977] | 0.899 (0.899 to 0.899) | 3.00 (3.00 to 3.00) [1.62 to 4.64] | 2 / 16 |
| isolation forest, smoothed | final | 0.806 (0.806 to 0.806) [0.389 to 0.921] | 0.797 (0.797 to 0.797) | 22.46 (22.46 to 22.46) [3.20 to 40.47] | 2 / 17 |
| random forest, fair (day 0 benign + dev-split attacks of other families) | dev | n/a | n/a | n/a | n/a / n/a |
| random forest, fair (day 0 benign + dev-split attacks of other families) | final | 0.891 | 0.887 | n/a | n/a / n/a |
| random forest, single windows (leave-one-family-out) | dev | 0.983 | 0.983 | n/a | n/a / n/a |
| random forest, single windows (leave-one-family-out) | final | 0.961 | 0.959 | n/a | n/a / n/a |
| token distance, smoothed | dev | 0.936 (0.927 to 0.945) [0.685 to 0.990] | 0.936 (0.927 to 0.945) | 4.14 (3.40 to 5.48) [1.02 to 5.08] | 2 / 16 |
| token distance, smoothed | final | 0.833 (0.818 to 0.848) [0.314 to 0.947] | 0.822 (0.800 to 0.847) | 5.60 (5.36 to 5.93) [3.25 to 8.44] | 2 / 17 |
| v0 NCM, smoothed | dev | 0.879 (0.853 to 0.908) [0.574 to 0.989] | 0.879 (0.853 to 0.908) | 3.00 (2.60 to 3.96) [0.92 to 3.56] | 2 / 16 |
| v0 NCM, smoothed | final | 0.697 (0.637 to 0.756) [0.284 to 0.962] | 0.654 (0.594 to 0.723) | 8.74 (5.18 to 18.93) [2.08 to 7.93] | 2 / 17 |

### Hard set, v0, final split (family-name match; mean AUC over seeds)

| Dataset | Family | AUC | seeds |
|---|---|---|---|
| CIC-IDS2017 | Botnet | 0.950 | 5 |
| CIC-IDS2017 | Infiltration | 0.925 | 5 |
| CIC-IDS2017 | Infiltration - Portscan | 0.992 | 5 |
| CSE-CIC-IDS2018 | Web Attack - SQL | 0.982 | 5 |
| Unraveled | APT:Establish Foothold | 0.867 | 5 |
| Unraveled | APT:Lateral Movement | 0.760 | 5 |

### Reading the table

1. **The full model beats token distance alone clearly on one dataset, barely on three, and loses on one.** Final-split family-mean AUC, v0 against token distance: Unraveled 0.894 and 0.857 (seed ranges 0.884 to 0.899 and 0.849 to 0.863: no overlap, a gap of 0.037), CIC-IDS2017 0.954 and 0.951, UNSW-NB15 0.942 and 0.940, CSE-CIC-IDS2018 0.989 and 0.986 (gaps of at most 0.003), and CICAPT-IIoT 0.697 and 0.833 (v0 behind by 0.14). Unraveled, the long five-week campaign, is where the sequence and surprise parts earn something; on CICAPT-IIoT they hurt, as R2 found they could be unstable.
2. **The random forest comes in two versions and only one is fair.** The first (rows "random forest, single windows") trains on windows of the test days and must not be used to judge v0 (see Deviations). The fair version (day 0 benign plus attack windows of the dev split only, final split only) is ahead of v0 on three datasets: CIC-IDS2017 0.974 against 0.954, UNSW-NB15 0.961 against 0.942, CICAPT-IIoT 0.891 against 0.697. It is **behind on two: CSE-CIC-IDS2018 0.882 against 0.989 and Unraveled 0.647 against 0.894** (worst family 0.481). In both, the test attack families have no counterpart among the dev attacks (Botnet Ares in 2018; the APT stages in Unraveled), so the forest has nothing to match, while v0 flags them unseen. So a supervised model wins when test attacks resemble the ones it was shown and loses badly when they do not, which is the situation an unsupervised detector is built for. Caveat: the fair forest's training attacks still include the same attacking machines as the test days.
3. **The isolation forest** is competitive on CIC-IDS2017 (0.957) but much worse on CSE-CIC-IDS2018 final (0.807), Unraveled (0.799) and CICAPT-IIoT (0.806), and needs the most false alerts in the 80% / 5 minute measure on CIC-IDS2017 (40.6).
4. **The false-alert measure is thin.** Attacking sources in the final split: CIC-IDS2017 7, UNSW-NB15 4, CICAPT-IIoT 2, Unraveled 4, CSE-CIC-IDS2018 11. Only CSE-CIC-IDS2018 has more than 10, where v0 needs 0.24 false alerts per benign host-day against 0.34 for token distance (bootstrap interval 0.11 to 0.40 for v0). On Unraveled v0 needs more false alerts than token distance at the 80% point (13.5 against 6.6, ranges 10.9 to 15.9 and 5.4 to 8.3) despite its higher AUC. The measure sets its threshold with the split's own labels (a best case, see Known limits).
5. **Hard set** (v0, final, 5 seeds where seeds are given): CIC-IDS2017 Botnet 0.950 and Infiltration 0.925, CSE-CIC-IDS2018 Web Attack - SQL 0.982, Unraveled Establish Foothold 0.867 and Lateral Movement 0.760 (the plan's earlier single-seed figures were 0.90 and 0.79).
6. **Decision-rule status.** There is no candidate model yet, so this is the v0 baseline on all five datasets. The rule's "3 of 5 datasets" count now stands on five.

### Bootstrap correction — 13 November 2026

All 30 seed-0 family-mean AUC interval pairs were regenerated with tie-aware weighted AUC and the original 200 source resamples. Point estimates, seed ranges, counts, false-alert intervals and family tables are unchanged. The commit column still identifies historical point results; corrected interval provenance is in research/audit/results/bootstrap_corrected/interval_changes.json. These are author reruns, not independent human validation.
