# R3: is detection just "a new source"?

Plan step 30 (PLAN.md section 5, R3). **Status: run complete (9 runs). Detection of attackers with benign history does not depend on `log_gap`; benign new sources are heavily alerted. Method and rule unchanged from the commit before the run.**

## Question

A source that has never been seen before is unusual in itself. If v0 mostly flags "this address is new", then an attacker who is already on the network (an infected internal host with normal history) would be much harder to catch than the scoreboard suggests. Does detection of attackers that have benign history hold up, and does it depend on the `log_gap` feature (the gap since the source's previous window, which is largest for a source's first appearance)?

## Method

Datasets: CIC-IDS2017 (Friday bots among the attackers), CSE-CIC-IDS2018 (the botnet hosts) and Unraveled (internal hosts). Seeds 0 to 2.

- **Known-source attackers:** attack windows of sources that have at least one benign window on day 0 (the training day). **New-source attackers:** attack windows of sources with none. Sources are counted once on each side.
- **Full model:** the scoreboard v0 checkpoint of each seed.
- **No-`log_gap` model:** `log_gap` is set to 0 in every window of the dataset (train, calibration and test) and v0 is **retrained** from scratch on that file with the scoreboard's training command (`train.py gru 64 <seed>`), same seeds, same splits. Everything else is unchanged.
- **Measures (final split only, as the scoreboard's headline):** the AUC of the group's attack windows against all benign windows of the final days, for the known-source attackers, the new-source attackers and all attackers; the share of attack windows above the 99% threshold of the day-0 calibration windows; and the share of benign final windows above that threshold, split by whether their source has day-0 history, which shows whether novelty itself raises alerts.

## Decision rule (fixed now)

Detection of known-source attackers **leans on source novelty** when the mean (over seeds) AUC drop from the full model to the no-`log_gap` model exceeds 0.05 on at least 2 of the 3 datasets. A dataset with no known-source attackers in the final split is reported as "none" and does not count. The finding to state in the model card is the AUC of known-source attackers, with and without `log_gap`, whichever way the rule falls. Differences inside the seed range are not drops.

## Known limits, stated now

- The number of known-source attackers can be small (a handful of hosts), so a group's AUC rests on few sources; counts are printed.
- "Has benign history" is "has a benign window on day 0", not "was seen in the days just before the attack"; an attacker active only on the final days is counted as known if it was benign on day 0.
- Zeroing `log_gap` is one way to remove novelty; other features (new destination share, window counts) can carry the same information.
- The retrained models have the scoreboard's usual seed noise, so a drop smaller than the seed range is not a finding.
- Three datasets, three seeds; UNSW-NB15 and CICAPT-IIoT are left out because their attackers are few or have no benign history.

## Results

3 seeds on three datasets; each no-`log_gap` model is a fresh training of v0 on the masked windows (per-seed files and checkpoints are on Drive, `cyberncm-data/r3/`). Final split.

#### Final-split AUC of attackers against all benign windows, mean over seeds (min to max)

| Dataset | Attackers | Attack sources / windows (final) | Full model | Without log_gap | Drop |
|---|---|---|---|---|---|
| CIC-IDS2017 | with benign history | 6 / 2741 | 0.953 (0.950 to 0.956) | 0.953 (0.949 to 0.958) | +0.001 |
| CIC-IDS2017 | no benign history (new) | 1 / 1115 | 0.963 (0.951 to 0.983) | 0.969 (0.956 to 0.981) | -0.006 |
| CIC-IDS2017 | all | 7 / 3856 | 0.956 (0.950 to 0.963) | 0.957 (0.957 to 0.958) | -0.001 |
| CSE-CIC-IDS2018 | with benign history | 10 / 35599 | 0.993 (0.992 to 0.994) | 0.993 (0.992 to 0.996) | -0.000 |
| CSE-CIC-IDS2018 | no benign history (new) | 1 / 131 | 0.990 (0.989 to 0.991) | 0.987 (0.983 to 0.990) | +0.003 |
| CSE-CIC-IDS2018 | all | 11 / 35730 | 0.993 (0.992 to 0.994) | 0.993 (0.992 to 0.996) | -0.000 |
| Unraveled | with benign history | 3 / 58616 | 0.830 (0.821 to 0.835) | 0.819 (0.776 to 0.850) | +0.011 |
| Unraveled | no benign history (new) | 1 / 1847 | 0.998 (0.998 to 0.999) | 0.996 (0.989 to 1.000) | +0.002 |
| Unraveled | all | 4 / 60463 | 0.835 (0.826 to 0.840) | 0.824 (0.783 to 0.855) | +0.011 |

#### Alerts on benign windows (share above the 99% threshold of the day-0 calibration), final split, mean over seeds

| Dataset | Benign windows | Full model | Without log_gap |
|---|---|---|---|
| CIC-IDS2017 | from sources with day-0 history | 0.080 | 0.061 |
| CIC-IDS2017 | from new sources | 0.924 | 0.550 |
| CSE-CIC-IDS2018 | from sources with day-0 history | 0.047 | 0.045 |
| CSE-CIC-IDS2018 | from new sources | 0.083 | 0.093 |
| Unraveled | from sources with day-0 history | 0.461 | 0.398 |
| Unraveled | from new sources | 0.936 | 0.904 |

Rule: detection of attackers with benign history 'leans on source novelty' when the mean AUC drop without log_gap exceeds 0.05 on at least 2 of the 3 datasets. Drops: CIC-IDS2017 +0.001, CSE-CIC-IDS2018 -0.000, Unraveled +0.011. **Leans on novelty: no** (0 of 3 datasets over 0.05).


## Answer in five lines

1. **Detection of attackers that have benign history does not lean on source novelty: the rule is not met.** Without `log_gap` the AUC of known-source attackers changes by +0.001 (CIC-IDS2017, 6 sources), -0.000 (CSE-CIC-IDS2018, 10 sources) and +0.011 (Unraveled, 3 sources), all within the seed range, against the 0.05 drop that would count.
2. **On Unraveled attackers with history are much harder than new ones, with or without `log_gap`:** 0.83 (0.82 to 0.84) for the 3 known sources against 0.998 for the one new source; on CIC-IDS2017 the two are alike (0.953 and 0.963) and on CSE-CIC-IDS2018 both are high (0.993 and 0.990). The hard cases of the scoreboard are the hosts that were already on the network, which is the dangerous kind (an infected internal machine), and the model is no better there without `log_gap` than with it.
3. **Novelty does raise alerts on benign traffic:** benign windows from sources never seen on day 0 are above the 99% threshold 92% of the time on CIC-IDS2017 and 94% on Unraveled with `log_gap`, against 8% and 5% of windows from known sources on the two lab datasets (CSE-CIC-IDS2018: 8% new, 5% known, no effect). Without `log_gap` the CIC-IDS2017 figure falls to 55% and Unraveled stays at 90%, so the feature is not the only cause. A new device joining a network is, here, flagged almost every time it appears.
4. **The Unraveled numbers show the drift problem too:** 46% of windows from known benign sources are above the day-0 threshold in the final weeks (40% without `log_gap`), the same drift R4 found.
5. **For the model card:** v0 can be stated to catch attackers already on the network at about the AUC above (0.95, 0.99 and 0.83 on the three datasets) and does not owe that to the novelty of the source; it must also state that a brand-new benign source is likely to raise alerts, which matters for onboarding new devices.

## Evidence limits

- **Very few attackers in each group:** 6, 10 and 3 known-source attacking sources and 1 new-source attacker per dataset; the new-source figures rest on one host each, and the CIC-IDS2017 benign "new source" figure on 57 windows. AUC for a group is the AUC of those windows against all benign windows, so a few hosts decide it.
- **"Has benign history" means a benign window on day 0.** A host benign on day 0 and attacking only in the final days counts as known; hosts that turned up after day 0 but before their attack are counted as new.
- **`log_gap` is one way to remove novelty:** other features (new-destination share, window counts) carry related information, and zeroing `log_gap` changes the whole feature set the model trains on (the new models are retrained, so the comparison includes seed noise: the Unraveled range for the no-`log_gap` model is 0.78 to 0.85).
- **Three datasets, three seeds.** UNSW-NB15 and CICAPT-IIoT were left out.

## Deviations

- The first training runs were started five at once and were far too slow (thread oversubscription); they were stopped and restarted as two workers with limited threads. Same commands, seeds and data.
- The evaluation step first failed for most runs (the script could not import the model code because of the folder it was run from); the runner was fixed and the evaluations rerun on the saved checkpoints. No change to the method.
- The first version of `r3_decide.py` chose its group by matching the word "history" in the row label, which matched both known and new rows, so the printed source counts and the rule's drops used the wrong row; it was fixed before any result was written up (the rule is evaluated on the known-source rows as the protocol says).

## Reproduce

`python research/R3/code/r3_mask.py <windows.npz> <windows_nogap.npz>`; retrain v0 on the masked file (`train.py gru 64 <seed>` with `data/` pointing at it); `python research/R3/code/r3_eval.py <ckpt_full> <windows> <ckpt_nogap> <windows_nogap> out.json <seed>` from a folder with `ncm/`; `python research/R3/code/r3_decide.py <dir> out.md`.
