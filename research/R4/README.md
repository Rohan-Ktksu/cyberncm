# R4: how low can false alarms go?

Plan step 19 (PLAN.md section 5, R4). **Status: run complete on all five datasets at 5 seeds each; verdict: the pass rule is not met. Method sections unchanged from the commits before the run.** This file is committed before the first run; anything changed afterwards goes under "Deviations" at the bottom, with the reason.

## Question

Can an alert policy on top of the existing scores keep false blocks under 1 per benign host per day while blocking at least 80% of attacking sources within 5 minutes?

## Fixed inputs

- **Model:** v0, GRU-64, seeds 0 to 4 (the scoreboard seeds), no retuning. Scores come from the unsupervised full model (`ncm/evaluate.py`, "NCM (all three signals), smoothed") and, separately, from token distance alone.
- **Data, in this order:** Unraveled (five labelled test weeks, the long-duration test), then CSE-CIC-IDS2018, then CIC-IDS2017. Splits as in R1 and R2. Policies and their parameters are chosen on the dev split; the final split is read once per policy.
- **Benign source:** an address with no attack window anywhere in the data (as in R2). Attacking sources are excluded from false-alarm counts.
- **Metrics:** `ncm/metrics.py` only. False blocks per benign host per day = false alert episodes per benign (source, day), gap 60 s. Attack side = share of attacking sources with an alert from their first attack window up to 5 minutes later; alerts before the first attack window do not count. Also reported: share of benign source-hours with an alert, and share of attack windows under an active block.

## Policies (same scores for all)

1. Fixed threshold from calibration data (reference).
2. Daily recalibration at the 1% quantile (reference; 3.5% of windows, about 11% of benign source-hours in R2).
3. Rolling quantile over the last 1, 6 and 24 hours.
4. Per-source threshold from that source's own history.
5. k of n windows above threshold: 2 of 3, 3 of 6, 6 of 12.
6. Two tiers: alert at the 99th percentile; block only at a higher level sustained for n windows (n and the higher level are chosen on dev).

Each policy is also run on token distance alone, to separate the effect of the policy from the effect of the model.

## Output

One table per dataset and per score source: false blocks per benign host per day against share of attacking sources blocked within 5 minutes, per policy, mean and range over seeds. Results in `research/R4/results/`.

## Operational choices (fixed before the run)

- **Scores and seeds:** v0 smoothed and token distance alone, models from the scoreboard run (`cyberncm-data/scoreboard/ckpt/`), seeds 0 to 4 where trained. Unraveled has seed 0 only so far.
- **Splits:** dev and final exactly as in `research/SCOREBOARD.md`. **Parameter choice** (rolling window, k and n, tier length) uses dev only: the setting with the fewest false alert episodes per benign host-day among those catching at least 80% of attacking sources within 5 minutes on dev; if none reaches 80%, the one that catches most (ties: fewest false alerts). The chosen setting is then read once on final.
- **Policy 2, daily recalibration:** threshold of a day = 99th percentile of all windows of the previous day, labels not used; the fixed calibration threshold when the previous day is the training day. (As in R2.)
- **Policy 3, rolling quantile:** threshold of an hour = 99th percentile of all windows of the previous 1, 6 or 24 hours; the fixed threshold while fewer than 500 windows of history exist.
- **Policy 4, per-source threshold:** a source's threshold on a day = 99th percentile of its own windows of the previous day when it had at least 30; otherwise the daily-recalibration threshold.
- **Policy 5, k of n:** an alert when at least k of the source's last n windows exceed the base threshold; base is the fixed threshold and, separately, the daily one. "Windows" are the source's own consecutive windows, not wall-clock time.
- **Policy 6, two tiers:** the alert tier is the 99th-percentile policy; a block needs the score above the 99.9th percentile of the calibration span in n consecutive windows (n = 2, 3, 6; chosen on dev). Only the block tier is scored for false blocks.
- **Metrics:** `ncm/metrics.py`; false blocks = false alert episodes (gap 60 s) per benign host-day; caught = alerted within 5 minutes of the first attack window; a benign source has no attack window in the split.
- **Pass rule as committed**, applied to the dev-chosen setting on final, per score source. With several seeds, a policy meets the target on a seed when its dev-chosen setting has final detection of at least 80% and fewer than 1 false alert episode per benign host-day, and passes on a dataset when it meets the target on a majority of that dataset's seeds (Unraveled has one seed, so 1 of 1). The overall pass needs this on Unraveled and on at least one other dataset (the 'at least one other' rule is my reading of the committed text).

## Decision rule (fixed now)

- **Pass:** at least one policy at under 1 false block per benign host per day and at least 80% of attacking sources blocked within 5 minutes, on the final split of Unraveled and on at least one of the other two datasets, using parameters chosen on dev only.
- **Fail:** no policy meets both. Then the product alerts and never blocks on its own (PLAN.md section 6), and R12 measures shared alerts.
- Differences smaller than the range over seeds are not wins.

## Known limits, stated now

- Unraveled is one campaign: it tests false alarms over weeks, not detection rates; the attack-side number there rests on few attacking sources and carries wide uncertainty.
- Daily recalibration and rolling quantiles use benign-looking history; a patient attacker can shift them (R7b/R7c test this later).
- The final split is read once per policy; a second look would need a new held-out period.

## Results

Final split, parameters chosen on dev only, mean and range over 5 seeds for every dataset (Unraveled's seeds ran on mixed hardware, see `research/SCOREBOARD.md`). "Meets the target" = at least 80% of attacking sources alerted within 5 minutes and under 1 false alert episode per benign host-day. The same tables as a CSV: `results/r4_final_split.csv`.

#### CIC-IDS2017, token distance score (5 seeds; final split: 7 attacking and 11 benign sources)

| Policy | Setting chosen on dev (per seed) | Attacking sources alerted within 5 min | False alerts per benign host-day | Benign source-hours with an alert | Seeds meeting the target |
|---|---|---|---|---|---|
| fixed threshold | none | 0.66 (0.57 to 0.71) | 2.95 (2.05 to 4.53) | 0.210 (0.172 to 0.248) | 0 of 5 |
| daily recalibration | none | 0.06 (0.00 to 0.14) | 1.03 (0.79 to 1.32) | 0.083 (0.069 to 0.110) | 0 of 5 |
| rolling quantile | 24 h, 6 h | 0.26 (0.14 to 0.29) | 1.17 (0.79 to 1.58) | 0.119 (0.076 to 0.145) | 0 of 5 |
| per-source threshold | previous day | 0.60 (0.57 to 0.71) | 3.71 (3.32 to 3.95) | 0.255 (0.248 to 0.262) | 0 of 5 |
| k of n on fixed | 6 of 12 | 0.54 (0.29 to 0.71) | 2.11 (1.63 to 2.74) | 0.108 (0.090 to 0.138) | 0 of 5 |
| k of n on daily | 6 of 12 | 0.00 (0.00 to 0.00) | 0.48 (0.26 to 0.68) | 0.022 (0.014 to 0.028) | 0 of 5 |
| two tiers | block above 99.9th percentile for 6 windows | 0.20 (0.00 to 0.43) | 1.15 (0.84 to 1.58) | 0.074 (0.055 to 0.110) | 0 of 5 |

#### CIC-IDS2017, v0 score (5 seeds; final split: 7 attacking and 11 benign sources)

| Policy | Setting chosen on dev (per seed) | Attacking sources alerted within 5 min | False alerts per benign host-day | Benign source-hours with an alert | Seeds meeting the target |
|---|---|---|---|---|---|
| fixed threshold | none | 0.69 (0.57 to 0.71) | 2.97 (2.11 to 4.95) | 0.206 (0.179 to 0.228) | 0 of 5 |
| daily recalibration | none | 0.11 (0.00 to 0.14) | 0.89 (0.74 to 1.11) | 0.084 (0.062 to 0.097) | 0 of 5 |
| rolling quantile | 24 h, 6 h | 0.34 (0.29 to 0.43) | 1.28 (0.74 to 2.05) | 0.121 (0.090 to 0.152) | 0 of 5 |
| per-source threshold | previous day | 0.54 (0.43 to 0.71) | 3.87 (3.58 to 4.26) | 0.279 (0.255 to 0.297) | 0 of 5 |
| k of n on fixed | 6 of 12 | 0.66 (0.57 to 0.71) | 1.89 (1.47 to 2.53) | 0.101 (0.076 to 0.117) | 0 of 5 |
| k of n on daily | 6 of 12 | 0.00 (0.00 to 0.00) | 0.44 (0.37 to 0.58) | 0.023 (0.021 to 0.028) | 0 of 5 |
| two tiers | block above 99.9th percentile for 6 windows | 0.43 (0.29 to 0.57) | 1.05 (0.79 to 1.26) | 0.063 (0.048 to 0.083) | 0 of 5 |

#### UNSW-NB15, token distance score (5 seeds; final split: 4 attacking and 37 benign sources)

| Policy | Setting chosen on dev (per seed) | Attacking sources alerted within 5 min | False alerts per benign host-day | Benign source-hours with an alert | Seeds meeting the target |
|---|---|---|---|---|---|
| fixed threshold | none | 1.00 (1.00 to 1.00) | 5.16 (5.12 to 5.20) | 0.520 (0.506 to 0.529) | 0 of 5 |
| daily recalibration | none | 0.00 (0.00 to 0.00) | 0.47 (0.43 to 0.52) | 0.055 (0.055 to 0.055) | 0 of 5 |
| rolling quantile | 1 h | 1.00 (1.00 to 1.00) | 1.85 (1.72 to 1.96) | 0.242 (0.227 to 0.251) | 0 of 5 |
| per-source threshold | previous day | 0.30 (0.25 to 0.50) | 1.66 (1.32 to 1.86) | 0.263 (0.239 to 0.275) | 0 of 5 |
| k of n on fixed | 6 of 12 | 1.00 (1.00 to 1.00) | 3.65 (3.59 to 3.77) | 0.261 (0.243 to 0.290) | 0 of 5 |
| k of n on daily | 6 of 12 | 0.00 (0.00 to 0.00) | 0.41 (0.38 to 0.45) | 0.047 (0.047 to 0.047) | 0 of 5 |
| two tiers | block above 99.9th percentile for 6 windows | 1.00 (1.00 to 1.00) | 3.43 (3.33 to 3.61) | 0.222 (0.196 to 0.271) | 0 of 5 |

#### UNSW-NB15, v0 score (5 seeds; final split: 4 attacking and 37 benign sources)

| Policy | Setting chosen on dev (per seed) | Attacking sources alerted within 5 min | False alerts per benign host-day | Benign source-hours with an alert | Seeds meeting the target |
|---|---|---|---|---|---|
| fixed threshold | none | 1.00 (1.00 to 1.00) | 5.70 (5.46 to 5.96) | 0.627 (0.588 to 0.663) | 0 of 5 |
| daily recalibration | none | 0.00 (0.00 to 0.00) | 0.44 (0.39 to 0.51) | 0.040 (0.031 to 0.043) | 0 of 5 |
| rolling quantile | 1 h, 6 h | 1.00 (1.00 to 1.00) | 1.90 (1.80 to 1.99) | 0.239 (0.227 to 0.243) | 0 of 5 |
| per-source threshold | previous day | 0.15 (0.00 to 0.25) | 1.28 (1.19 to 1.42) | 0.226 (0.216 to 0.239) | 0 of 5 |
| k of n on fixed | 6 of 12 | 1.00 (1.00 to 1.00) | 3.98 (3.84 to 4.12) | 0.335 (0.302 to 0.365) | 0 of 5 |
| k of n on daily | 6 of 12 | 0.00 (0.00 to 0.00) | 0.35 (0.23 to 0.46) | 0.041 (0.031 to 0.047) | 0 of 5 |
| two tiers | block above 99.9th percentile for 6 windows | 1.00 (1.00 to 1.00) | 3.74 (3.70 to 3.77) | 0.297 (0.282 to 0.306) | 0 of 5 |

#### CSE-CIC-IDS2018, token distance score (5 seeds; final split: 11 attacking and 3794 benign sources)

| Policy | Setting chosen on dev (per seed) | Attacking sources alerted within 5 min | False alerts per benign host-day | Benign source-hours with an alert | Seeds meeting the target |
|---|---|---|---|---|---|
| fixed threshold | none | 1.00 (1.00 to 1.00) | 0.88 (0.85 to 0.92) | 0.142 (0.129 to 0.155) | 5 of 5 (passes) |
| daily recalibration | none | 0.18 (0.18 to 0.18) | 0.12 (0.12 to 0.13) | 0.025 (0.024 to 0.026) | 0 of 5 |
| rolling quantile | 24 h, 6 h | 0.18 (0.18 to 0.18) | 0.29 (0.15 to 0.34) | 0.048 (0.028 to 0.059) | 0 of 5 |
| per-source threshold | previous day | 0.91 (0.91 to 0.91) | 0.36 (0.35 to 0.37) | 0.059 (0.058 to 0.060) | 5 of 5 (passes) |
| k of n on fixed | 6 of 12 | 1.00 (1.00 to 1.00) | 0.55 (0.52 to 0.57) | 0.053 (0.051 to 0.056) | 5 of 5 (passes) |
| k of n on daily | 6 of 12 | 0.18 (0.18 to 0.18) | 0.05 (0.05 to 0.06) | 0.003 (0.003 to 0.004) | 0 of 5 |
| two tiers | block above 99.9th percentile for 6 windows | 0.98 (0.91 to 1.00) | 0.23 (0.21 to 0.25) | 0.019 (0.017 to 0.021) | 5 of 5 (passes) |

#### CSE-CIC-IDS2018, v0 score (5 seeds; final split: 11 attacking and 3794 benign sources)

| Policy | Setting chosen on dev (per seed) | Attacking sources alerted within 5 min | False alerts per benign host-day | Benign source-hours with an alert | Seeds meeting the target |
|---|---|---|---|---|---|
| fixed threshold | none | 1.00 (1.00 to 1.00) | 0.79 (0.76 to 0.82) | 0.129 (0.119 to 0.137) | 5 of 5 (passes) |
| daily recalibration | none | 0.62 (0.18 to 0.91) | 0.12 (0.11 to 0.13) | 0.024 (0.022 to 0.027) | 3 of 5 (passes) |
| rolling quantile | 6 h | 0.76 (0.27 to 0.91) | 0.27 (0.25 to 0.30) | 0.044 (0.039 to 0.048) | 4 of 5 (passes) |
| per-source threshold | previous day | 0.91 (0.91 to 0.91) | 0.34 (0.33 to 0.37) | 0.058 (0.055 to 0.062) | 5 of 5 (passes) |
| k of n on fixed | 6 of 12 | 1.00 (1.00 to 1.00) | 0.49 (0.48 to 0.51) | 0.051 (0.050 to 0.054) | 5 of 5 (passes) |
| k of n on daily | 6 of 12 | 0.58 (0.18 to 0.91) | 0.06 (0.05 to 0.06) | 0.003 (0.002 to 0.004) | 2 of 5 |
| two tiers | block above 99.9th percentile for 6 windows | 1.00 (1.00 to 1.00) | 0.22 (0.19 to 0.24) | 0.021 (0.018 to 0.024) | 5 of 5 (passes) |

#### Unraveled, token distance score (5 seeds; final split: 4 attacking and 457 benign sources)

| Policy | Setting chosen on dev (per seed) | Attacking sources alerted within 5 min | False alerts per benign host-day | Benign source-hours with an alert | Seeds meeting the target |
|---|---|---|---|---|---|
| fixed threshold | none | 0.70 (0.50 to 0.75) | 3.65 (2.55 to 4.33) | 0.129 (0.114 to 0.138) | 0 of 5 |
| daily recalibration | none | 0.95 (0.75 to 1.00) | 2.45 (2.09 to 2.77) | 0.096 (0.090 to 0.101) | 0 of 5 |
| rolling quantile | 24 h | 0.25 (0.25 to 0.25) | 1.79 (1.39 to 2.24) | 0.084 (0.075 to 0.090) | 0 of 5 |
| per-source threshold | previous day | 0.75 (0.75 to 0.75) | 4.52 (4.39 to 4.63) | 0.141 (0.139 to 0.144) | 0 of 5 |
| k of n on fixed | 3 of 6 | 0.55 (0.25 to 0.75) | 2.87 (1.86 to 3.49) | 0.082 (0.069 to 0.090) | 0 of 5 |
| k of n on daily | 3 of 6 | 0.45 (0.25 to 0.50) | 1.83 (1.51 to 2.12) | 0.054 (0.050 to 0.058) | 0 of 5 |
| two tiers | block above 99.9th percentile for 3 windows | 0.15 (0.00 to 0.25) | 2.03 (1.17 to 2.89) | 0.065 (0.048 to 0.077) | 0 of 5 |

#### Unraveled, v0 score (5 seeds; final split: 4 attacking and 457 benign sources)

| Policy | Setting chosen on dev (per seed) | Attacking sources alerted within 5 min | False alerts per benign host-day | Benign source-hours with an alert | Seeds meeting the target |
|---|---|---|---|---|---|
| fixed threshold | none | 1.00 (1.00 to 1.00) | 23.83 (20.72 to 26.09) | 0.361 (0.315 to 0.399) | 0 of 5 |
| daily recalibration | none | 0.35 (0.25 to 0.50) | 1.44 (1.14 to 1.65) | 0.060 (0.047 to 0.072) | 0 of 5 |
| rolling quantile | 24 h | 0.25 (0.25 to 0.25) | 1.27 (1.03 to 1.41) | 0.056 (0.042 to 0.069) | 0 of 5 |
| per-source threshold | previous day | 0.55 (0.50 to 0.75) | 3.61 (3.40 to 3.92) | 0.101 (0.090 to 0.110) | 0 of 5 |
| k of n on fixed | 2 of 3 | 1.00 (1.00 to 1.00) | 23.33 (20.23 to 25.53) | 0.324 (0.278 to 0.361) | 0 of 5 |
| k of n on daily | 3 of 6 | 0.05 (0.00 to 0.25) | 1.10 (0.88 to 1.31) | 0.033 (0.025 to 0.040) | 0 of 5 |
| two tiers | block above 99.9th percentile for 3 windows | 1.00 (1.00 to 1.00) | 16.44 (14.22 to 18.42) | 0.227 (0.197 to 0.251) | 0 of 5 |

#### CICAPT-IIoT, token distance score (5 seeds; final split: 2 attacking and 17 benign sources)

| Policy | Setting chosen on dev (per seed) | Attacking sources alerted within 5 min | False alerts per benign host-day | Benign source-hours with an alert | Seeds meeting the target |
|---|---|---|---|---|---|
| fixed threshold | none | 1.00 (1.00 to 1.00) | 12.24 (10.46 to 14.07) | 0.568 (0.538 to 0.626) | 0 of 5 |
| daily recalibration | none | 0.00 (0.00 to 0.00) | 3.00 (2.54 to 3.43) | 0.185 (0.158 to 0.216) | 0 of 5 |
| rolling quantile | 6 h | 0.00 (0.00 to 0.00) | 2.31 (1.86 to 2.82) | 0.154 (0.129 to 0.196) | 0 of 5 |
| per-source threshold | previous day | 0.00 (0.00 to 0.00) | 14.05 (13.46 to 14.93) | 0.295 (0.269 to 0.327) | 0 of 5 |
| k of n on fixed | 6 of 12 | 1.00 (1.00 to 1.00) | 15.02 (9.64 to 18.29) | 0.432 (0.401 to 0.474) | 0 of 5 |
| k of n on daily | 6 of 12 | 0.00 (0.00 to 0.00) | 2.32 (1.93 to 2.79) | 0.123 (0.102 to 0.149) | 0 of 5 |
| two tiers | block above 99.9th percentile for 6 windows | 0.00 (0.00 to 0.00) | 1.09 (0.71 to 1.57) | 0.068 (0.041 to 0.102) | 0 of 5 |

#### CICAPT-IIoT, v0 score (5 seeds; final split: 2 attacking and 17 benign sources)

| Policy | Setting chosen on dev (per seed) | Attacking sources alerted within 5 min | False alerts per benign host-day | Benign source-hours with an alert | Seeds meeting the target |
|---|---|---|---|---|---|
| fixed threshold | none | 1.00 (1.00 to 1.00) | 13.12 (10.07 to 16.21) | 0.522 (0.468 to 0.570) | 0 of 5 |
| daily recalibration | none | 0.40 (0.00 to 0.50) | 1.81 (1.57 to 1.96) | 0.119 (0.096 to 0.135) | 0 of 5 |
| rolling quantile | 6 h | 0.00 (0.00 to 0.00) | 1.48 (1.14 to 1.71) | 0.098 (0.067 to 0.111) | 0 of 5 |
| per-source threshold | previous day | 0.30 (0.00 to 0.50) | 14.05 (10.32 to 16.54) | 0.236 (0.222 to 0.251) | 0 of 5 |
| k of n on fixed | 6 of 12 | 1.00 (1.00 to 1.00) | 10.77 (7.96 to 13.11) | 0.412 (0.365 to 0.444) | 0 of 5 |
| k of n on daily | 6 of 12 | 0.00 (0.00 to 0.00) | 1.06 (0.50 to 1.43) | 0.063 (0.026 to 0.091) | 0 of 5 |
| two tiers | block above 99.9th percentile for 6 windows | 0.10 (0.00 to 0.50) | 1.11 (0.71 to 1.82) | 0.066 (0.041 to 0.117) | 0 of 5 |


## Answer in five lines

1. **The pass rule is not met.** On Unraveled, no policy meets the target in any of the 5 seeds, with either score. The closest on detection is daily recalibration on token distance, which catches 95% of the attacking sources at 2.45 false alert episodes per benign host-day; v0 with a fixed threshold catches all of them at 24.
2. **The target is met on CSE-CIC-IDS2018** (11 attacking sources) by several policies, even the plain fixed threshold (all attackers caught at 0.79 to 0.88 false alerts per host-day). That dataset has 3,794 benign sources, most of them sparse, which makes per-host-day figures look better; it is not met on CIC-IDS2017, UNSW-NB15, CICAPT-IIoT or Unraveled.
3. **The policies that cut false alerts most also miss attackers.** Daily recalibration and k-of-n on it flag few benign hosts but catch 0 to 11% of attackers within 5 minutes on CIC-IDS2017, 0% on UNSW-NB15, 0 to 40% on CICAPT-IIoT, and 5 to 35% on Unraveled with v0: yesterday's attacks raise today's threshold (R2 saw the same).
4. **Fixed thresholds catch the attackers at a high price:** about 3 false alert episodes per benign host-day on CIC-IDS2017, 5 to 6 on UNSW-NB15, 12 to 13 on CICAPT-IIoT, and on Unraveled 3.7 with token distance against 24 with v0.
5. **The score matters on Unraveled.** With daily recalibration, token distance catches 95% of attackers (2.45 false alerts) while v0 catches 35% (1.44); with a fixed threshold, v0 needs 24 false alerts against 3.7. On the other datasets v0 and token distance behave alike within the seed ranges.

**What the rule says to do:** no policy passes, so the product alerts and never blocks on its own, and the mesh round (R12) measures shared alerts rather than shared blocks. A better score or a policy that is robust to attacks in its own history (R6) is the open route; none of the policies tried here gets there.

## Evidence limits

- Attacking sources in the final split: CIC-IDS2017 7, UNSW-NB15 4, CICAPT-IIoT 2, CSE-CIC-IDS2018 11, Unraveled 4. The "80% caught" test moves in large steps with so few attackers, and the false-alert rates for the small datasets rest on a handful of addresses.
- Unraveled is one campaign, and its 5 seeds ran on mixed hardware (thread counts differ), so the seed range includes that.
- The threshold-based policies use the 99th percentile, and the k of n, rolling and tier settings come from small grids chosen on dev. A different grid could move the numbers; none was tuned on final.
- Benign hosts here include very sparse ones, so false alerts per host-day depends on how many such hosts a dataset has (3,794 in CSE-CIC-IDS2018 against 11 to 37 elsewhere).
- Lab data, labels with known errors; a host the labels call benign but that behaves oddly counts as a false alert (the error analysis in `research/errors` suggests this matters on CIC-IDS2017).

## Deviations

None.

## Reproduce

Filled in after the run (Colab cells as in PLAN.md section 7, data from `cyberncm-data/`).
