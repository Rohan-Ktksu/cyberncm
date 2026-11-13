# R5: do shorter windows work? (flow-level version)

Plan step 34 (PLAN.md section 5, R5). **Status: flow-level run complete (3 window lengths, 3 seeds). 5 seconds is the shortest window that keeps accuracy; shorter windows alert sooner but lose accuracy on the final days. The packet-level part of R5 is not done. Method and rule unchanged from the commit before the run.**

## What this round is, and is not

The plan's R5 builds features from **packet captures** (CIC-IDS2017 pcaps, about 52 GB, with byte entropy, TLS fingerprints and DNS failures) and sweeps windows of 0.05, 0.5, 1 and 5 seconds. The pcaps are not available here and extracting those features from tens of gigabytes was not attempted. **This round answers only the part that flow records can answer:** how the window length affects v0 when the same 32 flow-level features are built from the corrected CIC-IDS2017 flows, whose start times have a resolution of 0.1 second. A 0.05-second window is below that resolution and is not tested. Byte entropy, TLS fingerprint and DNS failure features are **not** tested; whether they would help is unanswered.

## Method

Dataset: CIC-IDS2017 (the only one with start times fine enough; the others carry second-resolution or coarser times). The same prep script is run with the window length set to 0.5, 1 and 5 seconds (5 seconds reproduces the existing windows; the new run is repeated so the three lengths share one code path). v0 is **retrained from scratch** on each window set (`train.py gru 64 <seed>`, seeds 0 to 2), the day-0 benign training day and the dev and final days exactly as in the scoreboard.

Measures: family-mean AUC on dev and final (as in the scoreboard); the 99.5th-percentile alert threshold of the day-0 calibration windows; **time to first alert**: for each attacking source and test day, the time from its first attack window to its first window above that threshold (median and 90th percentile, and the number of attacker-days never alerted).

## Decision rule (fixed now)

The **fastest window that keeps accuracy** is the shortest length whose mean family-mean AUC is within 0.01 of the 5-second window's, on both dev and final. A shorter window that keeps accuracy and alerts sooner is a candidate "v2 row" in the plan's sense, but with one dataset it cannot satisfy the scoreboard's improvement rule (3 of 5 datasets), so it can only be a lead.

## Known limits, stated now

- **One dataset, three seeds, one attack campaign day structure;** the numbers rest on the same few attacking sources as the scoreboard (CIC-IDS2017 final has 7).
- **Flow records are aggregated by the capture tool before we see them:** a flow that spans several windows is attributed to its start; shorter windows therefore see fewer, more bursty flow starts, and any difference may reflect that attribution as much as the windowing.
- **Smoothing is per window** (an exponential average with factor 0.1 per window), so its time horizon shrinks with the window length; no retuning was done.
- **The time-to-first-alert threshold is one fixed choice** (the 99.5th percentile) and the benign false-alert rate at that threshold is not matched across window lengths.
- **Not the plan's R5:** no packet-level features, no 0.05-second window.

## Results

CIC-IDS2017 only, flow-level windows of 0.5, 1 and 5 seconds, v0 retrained from scratch for each (seeds 0 to 2; per-seed files and checkpoints are on Drive, `cyberncm-data/r5/`). The same 7 dev and 8 final attack families (with at least 10 windows) are scored at every window length, so the family-mean AUCs are comparable. The 5-second run has 125,577 windows against 125,674 in the canonical file (a small difference in the rebuilt windows); its final AUC, 0.954, equals the scoreboard's.

#### v0 by window length, CIC-IDS2017, mean over seeds (min to max)

| Window | Windows | Dev AUC | Final AUC | Worst family (final) | Median s to first alert (final) | 90th percentile s | Never alerted (attacker-days, final) |
|---|---|---|---|---|---|---|---|
| 0.5 s | 335,806 | 0.987 (0.983 to 0.990) | 0.878 (0.834 to 0.906) | 0.726 | 24.8 | 202.7 | 0 of 30 |
| 1 s | 258,716 | 0.990 (0.986 to 0.994) | 0.917 (0.914 to 0.921) | 0.811 | 20.3 | 398.4 | 0 of 30 |
| 5 s | 125,577 | 0.991 (0.982 to 0.997) | 0.954 (0.945 to 0.966) | 0.877 | 80.8 | 1319.5 | 0 of 30 |

Rule: the fastest window length whose mean final AND dev family-mean AUC are both within 0.01 of the 5-second window (final 0.954, dev 0.991) keeps accuracy. Lengths that keep it: 5 s. **Fastest window that keeps accuracy: 5 s.**


Per-seed final AUC: 0.5 s: 0.906, 0.894, 0.834; 1 s: 0.914, 0.917, 0.921; 5 s: 0.951, 0.966, 0.945. Per-seed median seconds to first alert (final): 0.5 s: 20.2, 28.5, 25.5; 1 s: 10.5, 40.5, 10.0; 5 s: 80.0, 92.5, 70.0. No attacker-day (30 per length, over three seeds) was missed at the 99.5% threshold at any length.

## Answer in five lines

1. **By the rule fixed beforehand, 5 seconds is the shortest window that keeps accuracy** on CIC-IDS2017: on dev all three lengths are within 0.01 (0.987, 0.990, 0.991) but on the final days 1 second loses 0.037 (0.917) and 0.5 second loses 0.076 (0.878), and the 5-second seeds (0.945 to 0.966) do not overlap the 1-second ones (0.914 to 0.921). The final-day difference is larger than the seed spread for 1 second; for 0.5 second the spread is wide (0.834 to 0.906).
2. **Shorter windows alert sooner:** the median time from an attacker's first attack window to its first alert on the final days is 20 s with 1-second windows and 25 s with 0.5-second windows, against 81 s with 5-second windows, and the 90th percentile falls from about 1,320 s to 400 s and 200 s. The per-seed medians for 1 second range from 10 to 40 s, so the size of the gain is rough.
3. **The speed comes at a cost in accuracy** that shows on the final days (worst family 0.73 and 0.81 against 0.88), not on dev; the alert threshold is the same percentile of each model's own calibration windows, so the benign false-alert rates are not matched across lengths and the faster alerts may partly be more false alerts.
4. **No "v2" row:** one dataset cannot meet the scoreboard rule (3 of 5 datasets), and the shorter windows do not hold their accuracy here; the 5-second window stays.
5. **What is not answered:** packet-level features (byte entropy, TLS fingerprint, DNS failures) and a 0.05-second window were not tested (no packet captures here and the flow start times are 0.1 s). The plan's R5 is only partly done: a flow-level window sweep.

## Evidence limits

- **One dataset, three seeds, 7 attacking sources in the final split;** time to first alert rests on 10 attacker-days per seed, so its seed medians vary a lot (10 to 40 s for 1 second).
- **Flow records are aggregated before we see them:** a flow is attributed to the window of its start, so shorter windows see burstier flow starts; some of the differences may be this attribution and not the window length.
- **Smoothing is per window** (factor 0.1 per window), so its time horizon shrinks with the window length; it was not retuned.
- **False alerts are not matched** across lengths (see line 3), and the time to first alert uses one threshold (99.5th percentile of the calibration windows).
- The rebuilt 5-second windows differ slightly from the canonical file (97 fewer windows), which does not change the final AUC.

## Deviations

- The first launch was started as two parallel workers with 4 threads each while a language-model smoke test (R14) also ran, which slowed the training but changed nothing in the commands, seeds or data.
- The 5-second windows were rebuilt (125,577 windows) rather than reused (125,674), so all three lengths share one code path, as the protocol says.

## Reproduce

From a folder with `ncm/`, the raw CSVs and the original flows (see R6c's run directories): `python research/R5/code/prep_win.py <seconds>`, `python train.py gru 64 <seed>` on the result, `python research/R5/code/r5_eval.py <checkpoint> <windows.npz> out.json <seed> <seconds>`, then `python research/R5/code/r5_decide.py <dir> out.md`.
