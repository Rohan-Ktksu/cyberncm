# Completed CPU follow-ups — 13 November 2026

Both processes exited 0. These are author-run single-seed follow-ups on public lab data, not independent human validation. Original datasets, checkpoints and historical multi-seed tables were not replaced. Exact commands, source/input hashes, environment, raw results and logs are in `results/cloud_followup/`. Input hashes were recorded after launch; no before/after hash invariance is asserted for these cloud jobs.

## CIC-IDS2017 to Unraveled adaptation (seed 0)

The source GRU is frozen. L3 refits target normalization, token/state centres and calibration. Final-split family-mean AUC and the retrospective FA80 metric are:

| Learning span | Fit windows | Calibration windows | L3 final AUC | FA80 per host-day |
|---|---:|---:|---:|---:|
| 10 min | 121 | 36 | 0.833501 | 14.406 |
| 60 min | 733 | 194 | 0.753704 | 13.827 |
| 360 min | 4443 | 1110 | 0.786268 | 12.792 |
| 1440 min | 21775 | 9077 | 0.853772 | 18.699 |
| 4320 min | 68709 | 15976 | 0.853156 | 16.372 |
| full | 168253 | 42070 | 0.886727 | 9.183 |

Matching target-trained seed-0 reference final AUC: 0.888941. Threshold-only transfer: 0.602594. Full target normalization alone: 0.607867.

The full day-0 benign span is about 144 hours, split 80/20 by time. The 1-day and 3-day fits remain about 0.035–0.036 AUC below the matching reference; full-span L3 is about 0.002 below. More minutes do not yield a monotonic curve in this seed. Do not infer a universal six-day learning requirement, a ten-minute readiness guarantee, or causation from this single run. The dev split contains dates before the day-0 learning span; only the final split is entirely later. Dev-based level selection therefore is not a clean prospective protocol. FA80 is a retrospective labelled evaluation metric, not the false-alert rate of a deployed fixed threshold; even full-span L3 remains above nine false alerts per host-day under this metric. No G1 approval follows.

## UNSW poisoning (seed 0)

All 9 families × 5 requested settings completed; all recorded dev/final thresholded detection fractions were 1.0. The script did not collect benign false-positive rates or AUCs, so this is not proof of robustness. Eight families have pool-capped doses. Worms reaches only 0.0254% effective day-0 contamination; the maximum across families is 4.7619%. Attack-labelled future windows are sampled, their originals excluded, and only normalization/centres/calibration are refit. This is an oracle frozen-backbone stress construction, with a recomputed time cutoff, not a prospective full-backbone poisoning experiment.

## Still open

Regenerate weighted bootstrap intervals; extend studies across seeds/directions; independently reproduce results; evaluate the unanswered-flow filter cost; validate any new nearest-token numerical convention with versioned models; run R12b only with complete data and matching original R12 references. No 72-run R12b sweep was started. Real-site G1 authorization and independent second-site sensing remain separate from this local demo.
