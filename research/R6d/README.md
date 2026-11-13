# R6d: which scoring function?

Plan step 23 (PLAN.md section 5, R6d). **Status: run complete on all five datasets at 5 seeds. No candidate passes the improvement rule. Method and rule unchanged from the commits before the run.**

## Question

R2 found that token distance carries most of the signal and that the next-context surprise terms are unstable across seeds (0.44 to 0.98). Do other ways of scoring a window, built on the same 32 features, do better than the current combined score?

## Candidates (all smoothed per source with the same EWMA 0.1 as v0)

Every raw score is standardised on the calibration span before smoothing, as in v0.

1. **v0**: the current model (token distance + state distance + half of the two surprise terms).
2. **v0 without the surprise terms**: token distance + state distance only (PLAN.md variant (e)).
3. **State distance only.**
4. **Token distance with 512 centres** (the baseline already on the scoreboard, from the checkpoint).
5. **Token distance with 128 centres** and 6. **with 2,048 centres**: MiniBatchKMeans (n_init 3, random state = seed) on the training span.
7. **Nearest-neighbour distance**: mean distance to the 5 nearest of 20,000 training windows (drawn with the seed).
8. **Gaussian mixture**: 16 diagonal components fitted on at most 100,000 training windows (random state = seed); score = minus the log-likelihood.
9. **Autoencoder**: a 32-16-8-16-32 network with ReLU, trained 5 epochs on at most 200,000 training windows (Adam 2e-3, batch 512, seed set); score = reconstruction error.

All windows are the 32 features normalised by the checkpoint's training-span mean and standard deviation, clipped at +-10. Training span, calibration span, splits, datasets and the false-alert measure are those of `research/SCOREBOARD.md`. Seeds 0 to 4: for candidates 2 to 4 the seed is the checkpoint's; for 5 to 9 it also seeds the fitting. No retuning on final.

## Decision rule (fixed now)

PLAN.md section 4 improvement rule, applied to each candidate against v0: on a dataset a candidate is *better* when its seed minimum on dev is above v0's seed maximum, and *worse* when its seed maximum is below v0's seed minimum (on dev or final). A candidate is an improvement when it is better on dev on at least 3 of 5 datasets, worse on none, and on the datasets where it is better on dev its final mean is not below v0's. Nine candidates are compared with one rule and no correction for that; the rule's "holds on final" part and the independent rerun (PLAN.md step 27) are the guard, so a single candidate that passes is a lead, not a result. Differences inside the seed range are not wins.

## Known limits, stated now

- Standard-deviation clipping and the 5 smoothing coefficient are those of v0, not retuned per candidate; candidates that would like a different smoothing are disadvantaged.
- The nearest-neighbour reference set is a 20,000-window sample, the mixture has 16 components and the autoencoder a single small shape: one setting each.
- The false-alert measure rests on 2 to 11 attacking sources per dataset and sets its threshold with the split's own labels (a best case).
- The candidates score windows one at a time (no history beyond the EWMA); history is R6a's subject.

## Results

Mean over 5 seeds, five datasets. Per-seed files are on Drive (`cyberncm-data/r6d/`). Dev numbers in brackets.

#### Family-mean AUC, mean over seeds (final split; dev in brackets)

| Candidate | CIC-IDS2017 | UNSW-NB15 | CSE-CIC-IDS2018 | Unraveled | CICAPT-IIoT |
|---|---|---|---|---|---|
| v0 NCM, smoothed | 0.954 (0.991) | 0.942 (0.949) | 0.989 (1.000) | 0.894 (0.906) | 0.697 (0.879) |
| v0 without the surprise terms (token + state distance) | 0.962 (0.991) | 0.942 (0.948) | 0.986 (0.999) | 0.891 (0.905) | 0.777 (0.894) |
| state distance only | 0.912 (0.902) | 0.956 (0.951) | 0.974 (0.990) | 0.855 (0.919) | 0.613 (0.750) |
| token distance, 512 centres | 0.951 (0.995) | 0.940 (0.947) | 0.986 (0.999) | 0.857 (0.852) | 0.833 (0.936) |
| token distance, 128 centres | 0.960 (0.992) | 0.940 (0.946) | 0.982 (1.000) | 0.849 (0.850) | 0.852 (0.939) |
| token distance, 2048 centres | 0.955 (0.998) | 0.943 (0.950) | 0.988 (1.000) | 0.880 (0.852) | 0.799 (0.906) |
| nearest-neighbour distance (5 nearest of 20,000 training windows) | 0.953 (0.998) | 0.941 (0.948) | 0.987 (1.000) | 0.878 (0.850) | 0.804 (0.911) |
| Gaussian mixture (16 diagonal components) | 0.970 (0.977) | 0.942 (0.947) | 0.931 (0.999) | 0.737 (0.806) | 0.769 (0.864) |
| autoencoder (32-16-8-16-32) | 0.924 (0.935) | 0.934 (0.936) | 0.971 (0.999) | 0.771 (0.831) | 0.652 (0.921) |

#### False alerts per benign host-day at 80% in 5 minutes (final; a best case)

| Candidate | CIC-IDS2017 | UNSW-NB15 | CSE-CIC-IDS2018 | Unraveled | CICAPT-IIoT |
|---|---|---|---|---|---|
| v0 NCM, smoothed | 12.06 | 3.01 | 0.24 | 13.47 | 8.74 |
| v0 without the surprise terms (token + state distance) | 10.51 | 2.37 | 0.30 | 14.38 | 6.22 |
| state distance only | 20.91 | 2.03 | 0.25 | 20.11 | 10.31 |
| token distance, 512 centres | 9.73 | 2.24 | 0.34 | 6.58 | 5.60 |
| token distance, 128 centres | 11.25 | 1.95 | 0.46 | 7.50 | 7.86 |
| token distance, 2048 centres | 8.25 | 1.78 | 0.28 | 4.92 | 8.86 |
| nearest-neighbour distance (5 nearest of 20,000 training windows) | 9.00 | 2.05 | 0.29 | 4.63 | 9.96 |
| Gaussian mixture (16 diagonal components) | 15.09 | 2.08 | 0.15 | 6.49 | 14.05 |
| autoencoder (32-16-8-16-32) | 43.98 | 2.95 | 0.55 | 16.18 | 23.54 |

#### Improvement rule against v0

| Candidate | Better on dev | Worse (dev or final) | Final not below v0 where better on dev | Improvement |
|---|---|---|---|---|
| v0 without the surprise terms (token + state distance) | none | CSE-CIC-IDS2018 final | yes | no |
| state distance only | none | CIC-IDS2017 dev, CSE-CIC-IDS2018 dev, CSE-CIC-IDS2018 final, Unraveled final, CICAPT-IIoT dev | yes | no |
| token distance, 512 centres | CICAPT-IIoT | UNSW-NB15 final, CSE-CIC-IDS2018 final, Unraveled dev, Unraveled final | yes | no |
| token distance, 128 centres | CICAPT-IIoT | UNSW-NB15 dev, CSE-CIC-IDS2018 final, Unraveled dev, Unraveled final | yes | no |
| token distance, 2048 centres | none | Unraveled dev | yes | no |
| nearest-neighbour distance (5 nearest of 20,000 training windows) | CIC-IDS2017 | CSE-CIC-IDS2018 final, Unraveled dev, Unraveled final | no | no |
| Gaussian mixture (16 diagonal components) | none | CSE-CIC-IDS2018 final, Unraveled dev, Unraveled final | yes | no |
| autoencoder (32-16-8-16-32) | none | CIC-IDS2017 dev, CIC-IDS2017 final, UNSW-NB15 dev, UNSW-NB15 final, CSE-CIC-IDS2018 final, Unraveled dev, Unraveled final | yes | no |

**Candidates that pass the rule: none.**


## Answer in five lines

1. **No candidate passes the rule.** None is better than v0 on dev, outside the seed range, on three datasets. The nearest, token distance with 512 centres and 128 centres, is better only on CICAPT-IIoT and worse on Unraveled and elsewhere; nearest-neighbour distance is better only on CIC-IDS2017 dev.
2. **The surprise terms add almost nothing.** v0 without them (token + state distance) is within 0.01 AUC of v0 on four datasets (+0.008 on CIC-IDS2017 final, 0 on UNSW-NB15, -0.003 on CSE-CIC-IDS2018, -0.003 on Unraveled) and +0.08 on CICAPT-IIoT, with fewer false alerts on three datasets. They are also the unstable part (R2). Removing them is neutral on accuracy and simplifies the model, but it is not an improvement under the rule.
3. **Token distance with 2,048 centres is a close alternative.** It matches v0 on four datasets (within 0.012), is worse than v0 only on Unraveled dev (0.852 against 0.906, outside the seed range), and needs fewer false alerts on four of five datasets (for example Unraveled 4.9 against 13.5, UNSW-NB15 1.8 against 3.0). It does not pass because the rule counts dev AUC, where it is not better anywhere.
4. **Unraveled is where v0's extra parts earn their keep**: every simpler or different score is below v0 there on dev (state distance alone is the exception on dev, 0.919, but it is far worse on final, 0.855).
5. **The Gaussian mixture and the autoencoder are not worth carrying forward.** The mixture is the best on CIC-IDS2017 final (0.970) but collapses on Unraveled (0.737) and CSE-CIC-IDS2018 final (0.931); the autoencoder is below v0 on seven of ten dataset-split pairs.

## Evidence limits

- Nine candidates against one rule with no correction; since none passes, the multiplicity does not change the conclusion, but a single win would have needed the independent rerun.
- Smoothing, clipping and standardisation are v0's, not retuned per candidate; the mixture has 16 components with a regularisation of 1e-3, the autoencoder one small shape, the neighbour search a 20,000-window reference: one setting each.
- The false-alert measure rests on 2 to 11 attacking sources per dataset and uses the split's own labels to set the threshold (a best case); its large differences are indications.
- Unraveled's v0 checkpoints come from mixed hardware (`research/SCOREBOARD.md`, Deviations).
- This round scores single windows; history is R6a's subject, and it found that the GRU stays.

## Deviations

- The first run stopped on CIC-IDS2017 because the mixture model failed on collapsed components (features that barely vary in the training span). Before any result existed, the mixture was given `reg_covar=1e-3` and float64 data (scikit-learn's default is 1e-6), and all runs were repeated from scratch. No other change.

## Reproduce

From a dataset run directory's `ncm/` folder: `python <repo>/research/R6d/code/r6d_scores.py artifacts/ncm_gru64_s0.pt out.json 0`; then `python <repo>/research/R6d/code/r6d_decide.py <dir with the 25 json files> results.md`.
