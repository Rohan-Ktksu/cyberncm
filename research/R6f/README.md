# R6f: a supervised head on history features

Plan step 24 (PLAN.md section 5, R6f). **Status: run complete on all five datasets at 5 seeds. Neither candidate passes the improvement rule. Method and rule unchanged from the commits before the run.**

## Question

The random forest on single windows already matched or beat v0 in R1 and in the scoreboard, and the fair forest (trained without the test period) beats v0 on three datasets but collapses on two (research/SCOREBOARD.md). Does a gradient-boosted classifier on window plus history features, with known attack families as negatives, do better than v0 on unseen families, and does adding v0's anomaly score as a feature fix the collapse?

## Candidates

All follow the fair-forest protocol: for each attack family with at least 10 windows in the final split, that family is held out (all its windows); the classifier is trained on the day-0 benign windows plus the attack windows of the dev split that belong to other families; it is scored on the final split against all its benign windows. The dev split is used for training, so dev is not available for these rows: **final split only**.

1. **GBT on window + history:** the 128 numbers of R6a (the 32 normalised features and their running averages over 1 minute, 10 minutes and 1 hour, per source and day).
2. **GBT on window + history + v0 score:** the same 128 numbers plus v0's smoothed anomaly score for the window (v0 never saw an attack label).

Classifier: scikit-learn HistGradientBoostingClassifier (100 iterations, learning rate 0.1, 31 leaves, balanced class weights, random state = the seed). Training windows: at most 100,000 benign (a random subset of day 0, drawn with the seed) and at most 50,000 attack windows of the dev split (random subset). The predicted attack probability is smoothed per source and day with the v0 EWMA (0.1) before scoring. Seeds 0 to 4 (the seed sets the sampling and the classifier; v0 is the scoreboard checkpoint of that seed). Datasets: all five.

## Decision rule (fixed now)

PLAN.md section 4 improvement rule, with dev dropped because supervised models train on dev attacks: on a dataset a candidate is *better* than v0 when its seed minimum on final is above v0's seed maximum on final, and *worse* when its seed maximum is below v0's seed minimum. It is an improvement when it is better on at least 3 of 5 datasets and worse on none. Two candidates, one rule; a pass is a lead needing the independent rerun (PLAN.md step 27), and a supervised model that passes is not a replacement for an unsupervised detector (it needs labelled attacks), only evidence on how far supervision helps. Differences inside the seed range are not wins.

## Known limits, stated now

- The training attacks still include the same attacking machines as the test days, which flatters supervised models (stated for the fair forest too).
- A dataset where the final families have no counterpart among the dev attacks (Botnet Ares in CSE-CIC-IDS2018, the APT stages in Unraveled) will show the supervised weakness; that is the point of the test, not a bug.
- Training windows are subsampled to bound time; a larger sample could change the numbers.
- One setting of the classifier; no tuning on final.
- UNSW-NB15 and CICAPT-IIoT inherit the approximations of their prep scripts.

## Results

5 seeds on five datasets, final split only, supervised head trained as in the fair random forest (day-0 benign plus the development days' attacks, never the test period). Per-seed files are on Drive (`cyberncm-data/r6f/`). "Better" means the lowest seed of the candidate is above the highest seed of v0.

#### Final-split family-mean AUC, mean over seeds (range)

| Model | CIC-IDS2017 | UNSW-NB15 | CSE-CIC-IDS2018 | Unraveled | CICAPT-IIoT |
|---|---|---|---|---|---|
| v0 | 0.954 (0.942 to 0.966) | 0.942 (0.941 to 0.944) | 0.989 (0.988 to 0.991) | 0.894 (0.884 to 0.899) | 0.697 (0.637 to 0.756) |
| fair random forest (one seed) | 0.974 | 0.961 | 0.882 | 0.647 | 0.891 |
| GBT on window + history | 0.889 (0.853 to 0.901) | 0.992 (0.992 to 0.992) | 0.847 (0.804 to 0.904) | 0.461 (0.352 to 0.580) | 0.661 (0.436 to 0.757) |
| GBT on window + history + v0 score | 0.889 (0.853 to 0.901) | 0.987 (0.969 to 0.992) | 0.989 (0.972 to 0.995) | 0.602 (0.559 to 0.653) | 0.556 (0.321 to 0.753) |

#### Improvement rule against v0 (final split only)

| Candidate | Better than v0 | Worse than v0 | Improvement |
|---|---|---|---|
| GBT on window + history | UNSW-NB15 | CIC-IDS2017, CSE-CIC-IDS2018, Unraveled | no |
| GBT on window + history + v0 score | UNSW-NB15 | CIC-IDS2017, Unraveled | no |

## Answer in five lines

1. **No supervised head passes the rule.** Window plus history is better than v0 on UNSW-NB15 only (0.992 against 0.942) and worse on CIC-IDS2017 (0.889 against 0.954), CSE-CIC-IDS2018 (0.847 against 0.989) and Unraveled (0.461 against 0.894). Adding v0's score makes it better only on UNSW-NB15 (0.987) and worse on CIC-IDS2017 and Unraveled (0.602 against 0.894).
2. **With each final attack family held out, supervision helps on one dataset and hurts on the others.** UNSW-NB15 rises by about 0.05 (0.942 to 0.992); on Unraveled a trained head falls to 0.46 (0.60 with v0's score), with single seeds as low as 0.35, below chance. A likely reason, not tested here, is that on UNSW-NB15 the held-out families resemble the other families and the same attacking machines remain in training.
3. **Giving the head v0's score rescues the dataset where the head alone failed most outright** (CSE-CIC-IDS2018, 0.847 to 0.989, equal to v0), but never beats v0 there and adds nothing on the others.
4. **The result is unstable across seeds** on the large datasets (CICAPT-IIoT 0.32 to 0.76, Unraveled 0.35 to 0.65), so any single-seed supervised number, including the one-seed fair forest in the first rows, should be read with that spread in mind.
5. **Decision: v0 stays unsupervised.** A supervised head is a possible add-on for a site that has labelled attacks of its own kinds, not a replacement, and not a basis for any claim about unseen attacks.

## Evidence limits

- **Final split only,** as the protocol fixed; dev attacks are training data here. One fixed classifier setting (100 iterations, 31 leaves), no tuning on final.
- **The training attacks include the same attacking machines as the test days,** which flatters supervision (the protocol's stated limit); UNSW-NB15 also has partly approximated features and a pseudo-day structure, so its high score is the least trustworthy of the five.
- **Training windows are subsampled** (at most 100,000 benign, 50,000 attack); a larger sample could change the numbers.
- **2 to 11 attacking sources per dataset** in the final split; seed ranges are shown, but source-level sampling noise is not.
- The fair random forest row is a single seed and a different learner, shown for context only.
- One candidate learner (histogram gradient boosting); other supervised learners were not tried.

## Deviations

- The decision script first failed on the scoreboard folder's fair-forest files, which share its filename pattern; it was fixed to skip them before any result was read. No method, rule or parameter changed.
- The UNSW-NB15 seeds 2 to 4 were run as separate processes in parallel to save time; same script and seeds.

## Reproduce

From a dataset run directory's `ncm/` folder: `python <repo>/research/R6f/code/r6f_gbt.py artifacts/ncm_gru64_s0.pt out.json 0`; then `python <repo>/research/R6f/code/r6f_decide.py <dir with the 25 json files> <scoreboard dir> results.md`.
