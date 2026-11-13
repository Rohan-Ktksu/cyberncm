# Error analysis on the hard set (PLAN.md step 16)

**Status: all three datasets done (CIC-IDS2017, CSE-CIC-IDS2018, Unraveled). Method section unchanged from the commit before the run.**

## Question

On the families v0 handles worst, what do the missed attack windows and the false alarms look like, and does that point to a change worth trying in block D?

## Method

- **Model:** v0, GRU-64, seed 0 from the scoreboard run (`cyberncm-data/scoreboard/ckpt/`), smoothed full score. One seed: this is a qualitative look, not a measurement.
- **Threshold:** the 99th percentile of the score on the benign calibration span. It is set without labels, so the errors are the ones a deployed fixed threshold would make.
- **Split:** final split as in `research/SCOREBOARD.md`. This reads the final split; nothing is tuned on it here, but any model change motivated by this page must be judged on dev.
- **Hard set (PLAN.md section 4):** Unraveled Lateral Movement and Establish Foothold; CIC-IDS2017 Botnet and Infiltration; CSE-CIC-IDS2018 Web Attack - SQL. Matched by family name.
- **Misses:** per family, the 20 lowest-scoring attack windows under the threshold. **False alarms:** per dataset, the 20 highest-scoring windows over the threshold from sources that never attack, at most 3 per source.
- **For each window:** source, time, score, the four score components, the number of features more than 2 standard deviations from the benign training mean, and the five most unusual features.
- **Group contrasts:** features whose mean differs most between missed and caught windows of a family, between missed windows and benign windows, and between flagged and unflagged benign windows.
- "Inspected by hand" in the plan: the listed windows are in `results/*.json`; the write-up below states what I read from the tables and the contrasts. A person should still look at the examples.

## Known limits, stated now

One seed; 20 examples per group; window labels are the dataset's and a window labelled attack may hold mostly normal flows; features are per-source 5-second aggregates, so the raw flows behind a window are not shown.

## Results so far

Datasets done: CIC-IDS2017, CSE-CIC-IDS2018, Unraveled.

### CIC-IDS2017, final split (Thursday and Friday), seed 0, threshold 3.64

| Family | Attack windows | Sources | Missed | Features beyond 2 SD, median: missed / caught / benign |
|---|---|---|---|---|
| Botnet | 2,390 | 5 | 20.9% | 3 / 7 / 0 |
| Infiltration | 59 | 3 | 23.7% | 3.5 / 1 / 0 |
| Infiltration - Portscan | 296 | 2 | 0.3% | 7 / 6 / 0 |

- **Missed Botnet windows are weaker versions of the caught ones, not normal-looking traffic.** On average they still sit far from benign on `wellknown_frac` (-5.3 SD), `syn_ratio` (+3.5) and `rst_ratio` (+3.1); the caught ones are at -7.9, +5.9 and +5.7. The 20 lowest-scoring misses are quieter (1 to 2 unusual features, scores -0.1 to 1.2) and come from four of the five bot hosts.
- **Infiltration is small and borderline.** 59 windows from 3 hosts; 14 missed, with scores from 1.0 up to just under the threshold. With so few windows nothing firm can be said.
- **Infiltration - Portscan is not a hard case** (0.3% missed); the hard-set entry "Infiltration" means the non-scan windows.

**False alarms:** 1.97% of the 28,246 windows of the 11 never-attacking sources are flagged, and 10 of the 11 sources are flagged at least once. **67% of the flags fall on one host, 192.168.10.50**, the web server that the attacks target; 192.168.10.16 and 192.168.10.51 take 11% each. Flagged benign windows differ from unflagged ones mainly on `wellknown_frac` (-4.5 SD), `rst_ratio` (+1.7) and `syn_ratio` (+1.3). The largest score component is token distance in 57% of flags and state distance in 24%.

- **Hypothesis, not established:** many of these "false alarms" are the victim server answering attack traffic (resets and replies to unusual ports), which the per-source labelling counts as benign. The three example windows from 192.168.10.50 all fall on time steps where an attack is in progress, but attacks cover 24% of all time steps, so three windows prove nothing. Testing it needs the destination and the attack times per flow (the raw flow files), which the windows do not carry.

**What this suggests for block D, to be judged on dev, not here:** (a) Botnet misses are graded, so a longer memory or a k-of-n rule (R4, R6a) may recover them; (b) if the victim-reply hypothesis holds, scoring per source-destination pair (R6c) or excluding replies would cut the largest block of false alarms on this dataset, and the false-alert numbers on the scoreboard for CIC-IDS2017 would partly measure a labelling artefact.

Examples (20 per group): `results/cic2017.json`.

### CSE-CIC-IDS2018, final split (days 3 and 4), seed 0, threshold 3.40

| Family | Attack windows | Sources | Missed |
|---|---|---|---|
| Web Attack - SQL | 18 | 1 | 0% |

- **Web Attack - SQL is not a hard case at this threshold:** all 18 windows, from one source, score above it. The hard-set entry in the plan came from a lower AUC in the earlier R1 work; with one source and 18 windows neither number says much.
- **False alarms are the issue here:** 6.75% of the 239,805 benign windows are flagged, and 620 of the 3,793 benign sources are flagged at least once. One external source, 193.111.198.65, accounts for 47.7% of all flags; the next source for 3.0%. The 20 example windows come from 10 different sources.
- **What drives them:** state distance is the largest score component in 52% of flags and token distance in 37%. Flagged benign windows differ from unflagged ones mainly on `wellknown_frac` (-1.0 SD), `iat_std`, `log_fwd_pkts` and `dur_mean` (+0.7 to +0.8 SD each): a shift of 1 SD or less, much smaller than CIC-IDS2017's 4.5 SD on `wellknown_frac`. The top examples are single sources with unusual FIN or RST handling (`fin_ratio` +9 SD, `rst_ratio` +6.6 SD).
- **Not checked:** whether those flagged sources are benign scanners or odd clients that the 2018 labels simply do not mark as attacks. The raw flows are needed for that. The benign set is the 10% source subsample (8,009 sources in total), so source counts are not the full network's.

Examples (20): `results/d2018.json`.

### Unraveled, final split (the second half of the test days, 18 days), seed 0, fixed threshold 3.53

| Family | Attack windows | Sources | Missed |
|---|---|---|---|
| APT: Lateral Movement | 25,636 | 2 | 2.0% |
| APT: Establish Foothold | 26,750 | 1 | 0.0% |

- **At this fixed threshold almost nothing is missed, and almost everything benign is flagged.** 31.4% of the 456,132 benign windows are flagged and every one of the 457 benign sources is flagged at least once. R2 measured 32.6% of benign windows over the five weeks for the same fixed threshold, so this is the known drift problem (a threshold set on one benign day goes stale over weeks), not a new finding. It is also why the AUC of the hard families (0.78 and 0.83) is low although few attack windows are missed: benign windows score high too.
- **The few Lateral Movement misses** (20 of the 25,636 windows, all from 192.168.0.11) sit between 1.95 and 2.33, well under the threshold but not unusual by the feature test (no feature more than 2 SD from normal). They are quiet windows of a source that is otherwise caught; nothing here suggests a different kind of attack.
- **False alarms are spread across many sources:** the largest source (10.1.1.15) accounts for 19% of the flags, the next four for 12%, 11%, 8% and 7%. The 20 example windows come from 16 sources and include external cloud addresses and the multicast address 239.255.255.250. State distance is the largest score component in 59% of flags, token distance in 17%. Flagged benign windows differ from unflagged ones by 0.5 to 0.75 SD on backward packets and bytes, packet-length spread and the direction ratio: a gradual shift of traffic volume, which fits drift.
- **What this suggests for block D, to be judged on dev:** the policy matters more than the model here. Daily recalibration or per-source baselines (R4, R6b) address the 31% directly, and R4's results already show that, with them, the 80% / 5 minute target is not met on this dataset. A different score could not fix a threshold that has gone stale.
- **Not checked:** which of the flagged benign sources are real nuisance traffic (scanners, discovery protocols) and which are normal hosts that changed behaviour; that needs the raw flows.

Examples (20 per group): `results/unraveled.json`.

## Deviations

None.

## Reproduce

From a dataset run directory's `ncm/` folder: `python <repo>/research/errors/code/errors.py artifacts/ncm_gru64_s0.pt out.json "Botnet" "Infiltration"`
