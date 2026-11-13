# R13: does risk rise on the hosts a campaign touches next?

Plan step 33 (PLAN.md section 5, R13: "Prediction, second attempt: follow the campaign, not the address"). **Status: run complete (3 seeds). The effect is absent on this evidence: the shuffled-order control flags the same onsets, and only 2 victim hosts and 3 subnets are testable. Method and rule unchanged from the commit before the run.**

## Question

R2 asked whether the *attacker's address* shows warning signs before a stage begins, and found almost none (`research/R2/README.md`). R13 asks it from the *victim's* side: after an attack has started somewhere, does the risk score on the hosts (and /24 subnets) the campaign touches next rise **before their first attack window**?

## Method

Dataset: Unraveled (the only multi-stage campaign), seeds 0 to 2. Windows keyed by (source, destination) from R6c (`cyberncm-data/r6c/windows/pair_unraveled`); each key's windows are scored with token distance (512 centres fitted on day-0 windows, standardised on the day-0 calibration span, smoothed per key and day, as in R6c). The **risk of a victim** at a time is the highest score of any window towards it, from any source; the risk of a subnet is the same over all hosts in the /24.

- **Onset:** the first attack-labelled window towards a victim (or subnet) in the test days. It is **testable** if the victim had traffic in the previous 24 hours.
- **Warning:** the victim's windows in the hour before the onset (none of them attack-labelled, by construction) include a score above the threshold. This is R2's `alert_1h`, from the victim's side.
- **Base rate:** the share of (victim, hour) blocks with traffic that contain an alert, excluding the two hours around a first attack window. A warning rate above the base rate is the only thing that would count as signal.
- **Thresholds:** the 99th percentile of the day-0 calibration windows (fixed), and recalibrated daily from the previous day's windows without labels (as in R2).
- **Shuffled control:** the same scoring with the order of windows shuffled inside each hour of a key's sequence before smoothing, as in R2.

## Decision rule (fixed now)

The effect is **present** when, with the daily threshold and the real order, the share of testable onsets with a warning exceeds the base rate by at least 0.25 for **both** hosts and subnets in at least 2 of the 3 seeds, **and** the shuffled control shows a smaller share than the real order. Otherwise it is **absent on this evidence**. With one campaign and a handful of onsets the result can show an effect is absent or worth pursuing, not prove one (PLAN.md).

## Known limits, stated now

- **One campaign, a handful of onsets:** the number of testable onsets (printed in the results) is small, so any rate is coarse; a difference of one onset is a large change.
- **Token distance only** (as R6c); the full v0 and its history were not used on pair windows.
- **The warning window is one hour,** the base rate is per (victim, hour) block; other windows would give other numbers.
- **Victims touched by many sources** have many windows, so their chance of an alert in any hour is high; the base rate is computed over all victim-hours, not matched per victim.
- Pair windows have a different benign population from per-source windows (R6c).
- The campaign order of victims is not modelled; this tests only the hour before the first attack window on each victim.

## Results

Seeds 0 to 2 (per-seed files: `cyberncm-data/r13/`). The three seeds agree exactly on every count; only the base rates move in the third decimal. The windows are the pair-keyed Unraveled windows (3,753,845 windows towards 16,583 destination addresses, 62,762 attack windows), token distance, as in R6c.

| Unit | First attack windows (onsets) | Testable (traffic in the prior 24 h) | With a warning in the prior hour, real order | With a warning, shuffled order | Base rate of an alert per unit-hour (daily threshold, real order) |
|---|---|---|---|---|---|
| Victim host | 5 | 2 | 1 of 2 | 1 of 2 | 0.060 to 0.063 |
| /24 subnet | 4 | 3 | 2 of 3 | 2 of 3 | 0.067 to 0.069 |

With the fixed day-0 threshold the warning counts are the same (1 of 2, 2 of 3) and the base rate is 0.26 to 0.34. The shuffled control (window order permuted inside each hour of a key before smoothing) gives the same counts in every seed.

## Answer in five lines

1. **By the rule fixed beforehand the effect is absent on this evidence.** It needs the warning share to exceed the base rate by 0.25 for both hosts and subnets in at least 2 of 3 seeds **and** the shuffled control to show a smaller share; the first part holds in every seed (1 of 2 hosts and 2 of 3 subnets against base rates of 0.06 to 0.07), the second part fails in every seed (the shuffled order flags exactly the same onsets).
2. **Why the shuffled control matters:** the same onsets are flagged whether or not the order of windows is real, so the "warning" is not a sign that the campaign's earlier activity builds up in time; it is that those victims already had unusual windows in the hour before, whatever the order. That matches R2, where order helped only on two stages.
3. **The sample is too small to say more:** only 2 of the 5 victim hosts and 3 of the 4 subnets had traffic in the prior 24 hours and so are testable. One flagged host out of two is one onset; it could be one busy host (R2 found the same kind of single case on 192.168.0.11, which was in the prior hour's traffic and already busy).
4. **No evidence that risk rises on the next victim before its first attack window.** The plan's claim ("follows the campaign, not the address") is not supported here and not refuted: the test cannot reach either conclusion with 2 to 3 events.
5. **For the claims ledger:** the "prediction" wording stays banned (N1); a campaign-following predictor was tried once, on one campaign, and showed nothing beyond the order-free control.

## Evidence limits

- **Two testable host onsets and three subnet onsets,** one campaign; every rate here is one event more or less.
- **Token distance on pair windows,** not the full v0 with history; the victim score is the highest score of any window towards it, so busy victims (many sources) have more chances to alert, and the base rate is pooled over all victim-hours, not matched per victim.
- **One-hour warning window; thresholds are the plan's two choices.**
- Pair windows have a different benign population from the per-source windows (R6c).
- The order in which the campaign touches victims is not modelled; only the hour before each victim's first attack window is examined.

## Deviations

None yet.

## Reproduce

`python research/R13/code/r13_victim.py <pair windows.npz> <pair_map.npz> out.json <seed>` from a folder with `ncm.py`.
