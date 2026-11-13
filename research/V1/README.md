# V1 decision (plan steps 28 and 29, round R6g): which detector ships

**Decision: v1 is v0.** No change tried in rounds R6a to R6f passed the improvement rule, so there is nothing to combine. The GRU stays, and the product keeps the rule it had in R4: it alerts and never blocks on its own.

This note is written from the committed results of the rounds below; it runs nothing new.

## The rule

PLAN.md section 4: a change is an improvement when it beats the reference by more than the seed range on dev on at least 3 of 5 datasets, is worse on none, and the gain holds on final. R6a also carried its own rule (the GRU is removed if history features without it are within 0.01 family-mean AUC of v0 on every dataset).

## Ablation table

| Round | Change tried | Result against v0 | Passes | Where |
|---|---|---|---|---|
| R6a | Running averages of the 32 features instead of, or beside, the GRU | History alone within 0.003 AUC on four datasets but far behind on Unraveled; v0 plus history not an improvement. The GRU-removal rule is not met | No | research/R6a |
| R6b | Self-normalisation by the source's own history; hour of day | Self-centring hurts on three datasets; helps UNSW-NB15 and CICAPT-IIoT on final but not on dev; hour of day adds nothing | No | research/R6b |
| R6c | Score per source-destination pair and per source-service | Pair scoring lifts final AUC on CICAPT-IIoT (0.833 to 0.965), UNSW-NB15 and CIC-IDS2017, but is worse on CSE-CIC-IDS2018 and Unraveled final; benign population changes with the unit; token distance only | No (a lead) | research/R6c |
| R6d | Other scoring functions, vocabulary sizes, mixture model, autoencoder, dropping the surprise terms | No candidate passes; the surprise terms add almost nothing; a 2,048-centre token distance is a close alternative | No | research/R6d |
| R6e | Training objectives, Transformer or state-space backbone, seed ensemble | Deferred by the team (2026-11-12) to keep to the mesh and stress-test questions | Not run | PLAN.md |
| R6f | Boosted trees on window plus history, with and without v0's score | Better on UNSW-NB15 only; much worse on Unraveled (0.461 against 0.894); unstable across seeds | No | research/R6f |

Related results that bear on what ships (not part of the R6 rule):

- **R4, alert policy:** no policy meets 80% of attackers caught within 5 minutes with fewer than one false alert per host-day on Unraveled in any of 5 seeds. The product alerts and never blocks on its own.
- **R11, new site:** refitting the codebooks and calibration on the new site's normal traffic matches full retraining within 0.021 on final in all six directions; the GRU does not need retraining. The 10 minutes seen in R11 is the lab minimum only; the shadow-mode duration is not set and must be chosen after testing on a network with day and night cycles.
- **Scoreboard:** v0 beats token distance alone clearly only on Unraveled (0.894 against 0.857); on the other four the gap is at most 0.003, and it loses 0.14 on CICAPT-IIoT. The fair random forest is ahead of v0 on three datasets and behind on two.

## What this means for v1

1. **v0 ships as the detector,** with calibration and codebooks refitted on the site's own normal traffic (R11).
2. **The GRU is not removed:** it earns its place only on Unraveled, the one dataset with a multi-week campaign, so the evidence for it is one dataset.
3. **One open lead:** per source-destination pair scoring on hosts that talk to many destinations (R6c). It would need a GRU trained on keyed windows and a unit-aware false-alert measure; it is the one candidate worth a follow-up if time allows.
4. **Nothing here is confirmed by an independent rerun** (plan step 27 needs a second person); every statement above is the authors' runs only.

## Step 29 (replay of v1 on the demo)

Because v1 is v0, the two-site replay and the evidence page already show v1. No replay needs to be redone.
