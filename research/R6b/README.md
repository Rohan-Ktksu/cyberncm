# R6b: compare each host to itself

Plan step 21 (PLAN.md section 5, R6b). **Status: run complete on all five datasets at 5 seeds. No candidate passes the improvement rule. Method and rule unchanged from the commits before the run.**

## Question

Benign traffic drifts and differs by host role (research/features: between-network drift is several times the day-to-day drift, and R4 found that thresholds go stale). If every window is judged against its own source's recent behaviour and against the normal pattern of the hour, does the token-distance score improve?

## Candidates (all built on the token-distance score of the 32 window features, 512 centres, smoothed per source with the same EWMA 0.1)

Windows are the 32 features normalised by the checkpoint's training-span mean and standard deviation, clipped at +-10 (call this Z; global mean 0, standard deviation 1 on the training span).

1. **Token distance, global** (baseline already on the scoreboard).
2. **Self-centred.** Per source and day, the baseline of a window is the running average of that source's earlier windows of the day (time constant 720 windows, one hour), shrunk toward the global mean 0 by the weight n / (n + 30), n being the number of earlier windows. The feature vector is Z minus this baseline. For a source's first windows the baseline is about 0, so the vector is Z itself. Day 0 (training and calibration span) goes through the same transformation, so the codebook is fitted in the same space the test days are scored in.
3. **Self-centred and self-scaled.** As 2, and divided by the source's own running standard deviation (same time constant), shrunk toward 1 by the same weight n / (n + 30) and floored at 0.25.
4. **Hour-of-day centred.** Z minus the global benign mean of the same hour of day, estimated from the training span of day 0 only; an hour with fewer than 500 training windows uses the global mean 0. Windows carry a time of day (seconds since midnight for the three public sets; for Unraveled and CICAPT-IIoT the hour of `T` modulo a day).
5. **Self-centred and hour-of-day centred.**

For each candidate a codebook of 512 centres is fitted by MiniBatchKMeans (n_init 3, random state = seed) on the training span (at most 300,000 windows), the raw score is the distance to the nearest centre, standardised on the calibration span, then smoothed. Training span, calibration span, splits, datasets and the false-alert measure are those of `research/SCOREBOARD.md`. Seeds 0 to 4 (the seed sets the k-means start; v0 is the scoreboard checkpoint of that seed). No retuning on final.

## Decision rule (fixed now)

PLAN.md section 4 improvement rule, each candidate against **token distance, global** (the model the change modifies) and, for information, against v0: on a dataset a candidate is *better* when its seed minimum on dev is above the reference's seed maximum, *worse* when its seed maximum is below the reference's seed minimum (dev or final). It is an improvement when it is better on dev on at least 3 of 5 datasets, worse on none, and on the datasets where it is better on dev its final mean is not below the reference's. Four candidates are compared with one rule; a single pass is a lead needing the independent rerun (PLAN.md step 27). Differences inside the seed range are not wins.

## Known limits, stated now

- A source that attacks earlier in its own day has attack windows in its own baseline: self-centring can hide a campaign that starts early (the contamination problem R4 found for daily thresholds). The baseline is per day, so it never contains a previous day's attack.
- The hour profile comes from one day (the training day), so it is a weak estimate of a daily rhythm; Unraveled's training span is short.
- Windows of different sources are independent here; roles (server, client) are not modelled beyond the source's own history.
- The false-alert measure rests on 2 to 11 attacking sources per dataset and sets its threshold with the split's own labels (a best case).

## Results

Mean over 5 seeds, five datasets. Per-seed files are on Drive (`cyberncm-data/r6b/`). Dev numbers in brackets.

#### Family-mean AUC, mean over seeds (final split; dev in brackets)

| Model | CIC-IDS2017 | UNSW-NB15 | CSE-CIC-IDS2018 | Unraveled | CICAPT-IIoT |
|---|---|---|---|---|---|
| v0 NCM, smoothed | 0.954 (0.991) | 0.942 (0.949) | 0.989 (1.000) | 0.894 (0.906) | 0.697 (0.879) |
| token distance, global | 0.951 (0.995) | 0.940 (0.947) | 0.986 (0.999) | 0.857 (0.852) | 0.833 (0.936) |
| token distance, self-centred | 0.917 (0.845) | 0.969 (0.936) | 0.852 (0.965) | 0.758 (0.761) | 0.864 (0.901) |
| token distance, self-centred and self-scaled | 0.835 (0.878) | 0.890 (0.849) | 0.892 (0.984) | 0.766 (0.784) | 0.889 (0.890) |
| token distance, hour-of-day centred | 0.955 (0.995) | 0.940 (0.947) | 0.985 (0.999) | 0.855 (0.845) | 0.801 (0.916) |
| token distance, self-centred and hour-of-day centred | 0.919 (0.831) | 0.969 (0.935) | 0.848 (0.956) | 0.746 (0.768) | 0.862 (0.911) |

#### False alerts per benign host-day at 80% in 5 minutes (final; a best case)

| Model | CIC-IDS2017 | UNSW-NB15 | CSE-CIC-IDS2018 | Unraveled | CICAPT-IIoT |
|---|---|---|---|---|---|
| v0 NCM, smoothed | 12.06 | 3.01 | 0.24 | 13.47 | 8.74 |
| token distance, global | 9.73 | 2.24 | 0.34 | 6.58 | 5.60 |
| token distance, self-centred | 28.13 | 2.17 | 0.31 | 26.75 | 4.32 |
| token distance, self-centred and self-scaled | 28.95 | 1.83 | 0.07 | 18.34 | 3.09 |
| token distance, hour-of-day centred | 10.12 | 2.20 | 0.39 | 8.60 | 10.96 |
| token distance, self-centred and hour-of-day centred | 26.03 | 2.13 | 0.32 | 26.88 | 4.65 |

#### Improvement rule against token distance, global (the rule's reference)

| Candidate | Better on dev | Worse (dev or final) | Final not below reference where better on dev | Improvement |
|---|---|---|---|---|
| token distance, self-centred | none | CIC-IDS2017 dev, CIC-IDS2017 final, UNSW-NB15 dev, CSE-CIC-IDS2018 dev, CSE-CIC-IDS2018 final, Unraveled dev, Unraveled final, CICAPT-IIoT dev | yes | no |
| token distance, self-centred and self-scaled | none | CIC-IDS2017 dev, CIC-IDS2017 final, UNSW-NB15 dev, UNSW-NB15 final, CSE-CIC-IDS2018 dev, CSE-CIC-IDS2018 final, Unraveled dev, Unraveled final, CICAPT-IIoT dev | yes | no |
| token distance, hour-of-day centred | none | CICAPT-IIoT final | yes | no |
| token distance, self-centred and hour-of-day centred | none | CIC-IDS2017 dev, CIC-IDS2017 final, UNSW-NB15 dev, CSE-CIC-IDS2018 dev, CSE-CIC-IDS2018 final, Unraveled dev, Unraveled final, CICAPT-IIoT dev | yes | no |

**Candidates that pass: none.**

#### Improvement rule against v0 (for information)

| Candidate | Better on dev | Worse (dev or final) | Final not below reference where better on dev | Improvement |
|---|---|---|---|---|
| token distance, self-centred | none | CIC-IDS2017 dev, CIC-IDS2017 final, UNSW-NB15 dev, CSE-CIC-IDS2018 dev, CSE-CIC-IDS2018 final, Unraveled dev, Unraveled final | yes | no |
| token distance, self-centred and self-scaled | none | CIC-IDS2017 dev, CIC-IDS2017 final, UNSW-NB15 dev, UNSW-NB15 final, CSE-CIC-IDS2018 dev, CSE-CIC-IDS2018 final, Unraveled dev, Unraveled final | yes | no |
| token distance, hour-of-day centred | none | UNSW-NB15 final, CSE-CIC-IDS2018 final, Unraveled dev, Unraveled final | yes | no |
| token distance, self-centred and hour-of-day centred | none | CIC-IDS2017 dev, CIC-IDS2017 final, UNSW-NB15 dev, CSE-CIC-IDS2018 dev, CSE-CIC-IDS2018 final, Unraveled dev, Unraveled final | yes | no |

**Candidates that pass: none.**

## Answer in five lines

1. **No candidate passes the rule**, against global token distance (the rule's reference) or against v0. None is better on dev, outside the seed range, on even one dataset.
2. **Comparing a host to itself hurts on three of five datasets.** Self-centred token distance falls from 0.951 to 0.917 on CIC-IDS2017 final (dev 0.995 to 0.845), from 0.986 to 0.852 on CSE-CIC-IDS2018 final, and from 0.857 to 0.758 on Unraveled final, and needs more false alerts there (CIC-IDS2017 28 against 10, Unraveled 27 against 7).
3. **On two datasets it helps on final but not on dev.** UNSW-NB15 final rises from 0.940 to 0.969 and CICAPT-IIoT final from 0.833 to 0.864 (0.889 with self-scaling), while their dev scores fall (UNSW-NB15 0.936 against 0.947, CICAPT-IIoT 0.901 against 0.936). The rule needs dev, so this is a lead for datasets with a stable host population, not a result; with only 2 and 4 attacking sources in those final splits it may also be luck.
4. **Hour-of-day centring does nothing measurable**: within 0.004 AUC of the reference on four datasets and 0.032 worse on CICAPT-IIoT final. A profile from a single training day is a weak estimate, and the data may simply have little daily rhythm at this granularity.
5. **A plausible reason for the losses (not tested):** a source that starts attacking has its attack windows folded into its own baseline within the same day, so self-centring hides exactly the change it should reveal, the contamination problem R4 found for daily thresholds.

## Evidence limits

- Four candidates against one rule with no correction; none passes, so multiplicity does not matter for the conclusion.
- One setting each (one-hour time constant, shrinkage weight n / (n + 30), a 0.25 floor on the scale, 512 centres); a longer baseline, or one that excludes flagged windows, is not tried here.
- The hour profile comes from one training day, and Unraveled's training span is short.
- The false-alert measure rests on 2 to 11 attacking sources per dataset and uses the split's own labels (a best case).
- Unraveled's v0 checkpoints come from mixed hardware (`research/SCOREBOARD.md`, Deviations).

## Deviations

None yet.

## Reproduce

From a dataset run directory's `ncm/` folder: `python <repo>/research/R6b/code/r6b_self.py artifacts/ncm_gru64_s0.pt out.json 0`; then `python <repo>/research/R6b/code/r6b_decide.py <dir with the 25 json files> results.md`.
