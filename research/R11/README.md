# R11: can a new site start without retraining?

Plan step 25 (PLAN.md section 5, R11). **Status: run complete (30 of 30). Refitting the codebooks and calibration on the target's own normal traffic matches full retraining in lab data; "10 minutes" is the lab minimum only, not a product setting (see line 4 of the answer and the limits). Method and rules unchanged from the commits before the run.**

## Question

R1 found that a model trained on one network does not carry over to another. The product plan lets a new site learn for a while before it enforces. How much of the model has to be refitted on the new site's own normal traffic, and how much traffic does that take, before the model is within 0.02 AUC of one fully retrained on that site?

## Method

The six transfer directions of R1 (train on A, test on B) between CIC-IDS2017, UNSW-NB15 and CSE-CIC-IDS2018 (the 10% source subsample), with A's v0 checkpoint of seed s (scoreboard seeds 0 to 4) scoring B's windows. Only the **non-gradient** parts of training are refitted, from B's normal traffic alone (its day-0 training and calibration span); no attack label of B is used for any adaptation.

Levels:
1. **Threshold only.** A's feature normalisation, both codebooks and calibration; the score is as in R1. (The alarm threshold of R1 moves to B's calibration span, but the AUC columns do not depend on a threshold, so this level's AUC equals R1's transfer AUC.)
2. **Plus feature normalisation.** The mean and standard deviation of the 32 features are refitted on B's fit span (clipped at +-10 as in training); the GRU, both codebooks and A's calibration statistics are A's.
3. **Plus both vocabularies and the calibration.** As level 2, and the 512-centre token codebook is refitted by MiniBatchKMeans (n_init 3, random state = s) on B's normalised fit windows, the 512-centre state codebook is refitted on the GRU states of those windows, and the four component means and standard deviations are recomputed on B's calibration span.
4. **Full retraining.** The in-domain v0 of B from the scoreboard (mean over its seeds), the reference.

Spans: B's day 0 is cut at its 80th percentile of time into a fit span and a calibration span, as in training. The score is v0's (token distance + state distance + half of the two surprise terms, each standardised on the calibration span, smoothed per source with EWMA 0.1). Evaluation is on B's dev and final days with the scoreboard measures (family-mean AUC, worst family, false alerts per benign host-day at 80% in 5 minutes). Datasets and splits as in `research/SCOREBOARD.md`.

**Learning curve.** For levels 2 and 3 the same procedure is repeated with only the first M minutes of B's day 0 (M = 10, 60, 360), the first 80% of that stretch as the fit span and the last 20% as the calibration span; "full" is the whole day-0 span above. With fewer than 1,024 fit windows a codebook has min(512, windows / 2) centres.

## Decision rules (fixed now)

1. **Best cheap level:** the one of levels 2 and 3 with the higher mean dev family-mean AUC over the six directions and five seeds at full data.
2. **Learning period:** for that level, the shortest M (10, 60, 360 minutes, or full) at which the mean over the six directions and five seeds of (final family-mean AUC minus level 4's final family-mean AUC of the target) is at least -0.02. If no budget reaches it, the finding is that cheap adaptation does not replace training. That M becomes the shadow-mode duration in the product plan, with the caveat below.
3. Differences are judged on means over seeds with their ranges shown; a difference inside the seed range is not a win.

## Known limits, stated now

- Only three networks, so six directions, and R1 found two of them near chance or inverted before any adaptation; a mean over directions can hide a mix of successes and failures, so the per-direction table is reported too.
- B's day 0 is one day (CIC-IDS2017 Monday, CSE-CIC-IDS2018 a benign stretch of one day, UNSW-NB15 a pseudo-day), so the learning curve runs from 10 minutes to a day of one particular network's traffic; a site's traffic changes over weeks, which this does not test.
- Level 4 uses the target's own seeds, not seed-matched to the source seed.
- UNSW-NB15's features are partly approximated (R1), so its directions measure that too.
- The false-alert measure rests on 2 to 11 attacking sources per dataset and sets its threshold with the split's own labels (a best case).

## Results

Six directions, 5 seeds each (30 runs), every number a mean over seeds. Per-seed files are on Drive (`cyberncm-data/r11/`). Level 4 is the target's own v0 from the scoreboard (mean over its 5 seeds).

Size of the target's training stretch (fit windows, number of sources), from day 0:

| Target | 10 min | 60 min | 360 min | whole day (about 8 to 12 h) |
|---|---|---|---|---|
| CIC-IDS2017 | 251 windows, 14 sources | 3,176, 20 | 17,468, 20 | 26,159 windows in the day |
| UNSW-NB15 | 1,021, 24 | 6,259, 25 | 37,481, 26 | 78,620 in the day |
| CSE-CIC-IDS2018 | 1,535, 199 | 10,028, 512 | 61,027, 1,359 | 110,803 in the day |

#### Final-split family-mean AUC per direction (mean over 5 seeds)

| Direction | L1 threshold only | L2 + target normalisation | L3 + target vocabularies and calibration | L4 full retraining (target's own v0) |
|---|---|---|---|---|
| CIC-IDS2017 to CSE-CIC-IDS2018 | 0.514 | 0.688 | 0.988 | 0.989 |
| CIC-IDS2017 to UNSW-NB15 | 0.103 | 0.895 | 0.943 | 0.942 |
| CSE-CIC-IDS2018 to CIC-IDS2017 | 0.922 | 0.865 | 0.933 | 0.954 |
| CSE-CIC-IDS2018 to UNSW-NB15 | 0.083 | 0.910 | 0.944 | 0.942 |
| UNSW-NB15 to CIC-IDS2017 | 0.891 | 0.778 | 0.939 | 0.954 |
| UNSW-NB15 to CSE-CIC-IDS2018 | 0.115 | 0.666 | 0.981 | 0.989 |

Mean dev family-mean AUC over the directions at full data: L2 0.813, L3 0.980. **Best cheap level: L3.**

#### Learning curve of L3 (final family-mean AUC, mean over 5 seeds)

| Direction | 10 min | 60 min | 360 min | full | L4 reference |
|---|---|---|---|---|---|
| CIC-IDS2017 to CSE-CIC-IDS2018 | 0.933 | 0.953 | 0.991 | 0.988 | 0.989 |
| CIC-IDS2017 to UNSW-NB15 | 0.945 | 0.945 | 0.943 | 0.943 | 0.942 |
| CSE-CIC-IDS2018 to CIC-IDS2017 | 0.956 | 0.947 | 0.941 | 0.933 | 0.954 |
| CSE-CIC-IDS2018 to UNSW-NB15 | 0.948 | 0.944 | 0.943 | 0.944 | 0.942 |
| UNSW-NB15 to CIC-IDS2017 | 0.964 | 0.952 | 0.938 | 0.939 | 0.954 |
| UNSW-NB15 to CSE-CIC-IDS2018 | 0.952 | 0.970 | 0.981 | 0.981 | 0.989 |

| Budget | 10 min | 60 min | 360 min | full |
|---|---|---|---|---|
| Mean over directions of (final AUC minus L4) | -0.012 | -0.010 | -0.005 | -0.007 |

**Learning period: 10 min** (the shortest budget with a mean gap of at most 0.02 to full retraining).

#### Dev family-mean AUC per direction (mean over 5 seeds)

| Direction | L1 | L2 @ full | L3 @ full | L4 |
|---|---|---|---|---|
| CIC-IDS2017 to CSE-CIC-IDS2018 | 0.600 | 0.925 | 1.000 | 1.000 |
| CIC-IDS2017 to UNSW-NB15 | 0.100 | 0.892 | 0.951 | 0.949 |
| CSE-CIC-IDS2018 to CIC-IDS2017 | 0.967 | 0.901 | 0.988 | 0.991 |
| CSE-CIC-IDS2018 to UNSW-NB15 | 0.086 | 0.909 | 0.952 | 0.949 |
| UNSW-NB15 to CIC-IDS2017 | 0.783 | 0.673 | 0.988 | 0.991 |
| UNSW-NB15 to CSE-CIC-IDS2018 | 0.704 | 0.578 | 0.998 | 1.000 |

## Answer in five lines

1. **Refitting only the feature normalisation is not enough.** Level 2 (mean dev 0.813) rescues the directions into UNSW-NB15 (0.083 to 0.910, 0.103 to 0.895) but is worse than no adaptation into CIC-IDS2017 (0.922 to 0.865, 0.891 to 0.778) and well below full retraining into CSE-CIC-IDS2018 (0.688, 0.666).
2. **Refitting the vocabularies and calibration is enough.** Level 3 (mean dev 0.980) is within 0.003 of full retraining on dev for all six directions and within 0.021 on final for all six (worst case: CSE-CIC-IDS2018 to CIC-IDS2017, 0.933 against 0.954). The GRU stays the one trained on the other network. Without any adaptation, into UNSW-NB15 the model scores 0.08 to 0.12 AUC, which is worse than chance (inverted), as R1 found.
3. **By the rule the lab learning period is 10 minutes.** The mean gap to full retraining on final is -0.012 at 10 minutes, -0.010 at 60, -0.005 at 360 and -0.007 on the whole day, so the shortest budget already satisfies the 0.02 rule. The curve is nearly flat, so more data barely helps on these datasets.
4. **"10 minutes" is the lab minimum, not the product setting.** The three datasets are clean lab captures whose normal day is one stable stretch, so ten minutes of it looks like the rest of the day; a real site has daily and weekly cycles that ten minutes would miss. UNSW-NB15's "day" is a pseudo-day built from the data, not real clock time. The first 10 minutes held only 251 (CIC-IDS2017), 1,021 (UNSW-NB15) and 1,535 (CSE-CIC-IDS2018) fit windows, from 14 to 199 sources, and the codebooks shrink to half the windows when there are fewer than 1,024. Per direction the final AUC at 10 minutes differs from full retraining by between +0.010 and -0.056 (-0.056 and -0.037 for the two directions into CSE-CIC-IDS2018), and the gap is not monotone: CSE-CIC-IDS2018 into CIC-IDS2017 is better at 10 minutes than on the whole day, which says noise, not learning.
5. **What it supports, and what it does not.** A new site needs no gradient training, only refitting two codebooks and the calibration on its own normal traffic; that is the finding. How long a site must run in shadow mode is **not** answered here and is not set to 10 minutes: the real duration is to be chosen after testing on a network with day and night cycles (a site log or a dataset with several real weeks, such as Unraveled's, used as the target of the learning curve), and until then the product plan should carry no number.

## Evidence limits

- **Three networks, six directions.** The mean can hide a direction that fails in a real deployment; the per-direction tables are above.
- **Lab traffic only.** The normal day of each dataset is a stable stretch, and UNSW-NB15's day is a pseudo-day, so no result here says anything about daily or weekly cycles.
- **One benign day, and no weekly rhythm.** The datasets' day 0 is 8 to 12 hours of lab or pseudo-day traffic; a real site's traffic changes by hour, day and week, which this does not test. Attacks in these datasets are also injected into otherwise regular lab traffic.
- **The 10-minute rows use very few windows** (as few as 251 for CIC-IDS2017, 14 sources). The codebook falls back to half the windows when there are fewer than 1,024.
- **Level 4 is not seed-matched** to the source seed.
- **The AUC does not use an alarm threshold.** The false-alert measure was recorded per run but is not part of the decision rules; the thresholds of levels 2 and 3 come from the target's own calibration span.
- UNSW-NB15's features are partly approximated (R1), so its directions measure that too.
- Two levels compared at one budget each against the same rule; no correction for multiple comparisons.

## Deviations

- The first runs of levels 3 failed for the directions into CIC-IDS2017 and UNSW-NB15 (a 512-centre codebook cannot hold fewer centres, which the 10-minute budget needs, as the protocol already specified). The script now replaces the codebook tensor with the smaller one. No method, rule or parameter changed; the failed jobs wrote no results and were rerun.

## Reproduce

From a folder with `ncm/` code: `python <repo>/research/R11/code/r11_adapt.py <A checkpoint> <B windows.npz> out.json <seed>`, then `python <repo>/research/R11/code/r11_decide.py <dir> <scoreboard dir> out.md`.


## Audit instrumentation — 13 November 2026

`r11_adapt.py` accepts an optional fifth argument containing positive budget minutes, such as `10,60,360,1440,4320`. Default budgets remain the original 360, 60, 10 minutes plus full. Outputs now include the requested budget, actual fit/calibration window and source counts, observed time span, and skipped-budget reasons. Day-0 contamination is rejected for this benign-adaptation protocol. Budgets describe elapsed observation time, not a guarantee of deployment readiness or concept-drift tolerance. Real multi-day Unraveled results are pending in the audit; earlier short-budget laboratory results do not settle that question.

Chronology metadata now records absolute training/evaluation intervals and whether each split is entirely after day 0; this exposes retrospective development splits rather than treating them as prospective evidence. Hourly UTC window counts show which observation hours each budget covers. Synthetic end-to-end smoke verification passed; real Unraveled curve remains pending after the Colab disconnection.
