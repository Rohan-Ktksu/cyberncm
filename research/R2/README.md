# R2 — Can it predict the next stage?

Question (HANDOFF §8, R2): on a multi-stage dataset, how long before a stage's first window does the score cross the
threshold, against token distance, the stage head without state, and the same sequences with window order shuffled?

**Status: done as a case study on one campaign. Answer so far: no.** GRU-64, seeds 0-2, no retuning.

## Answer in five lines

- **The model detects stages while they happen; it does not warn before them.** On Unraveled, with a threshold that holds
  false alarms near 3.5%, the attacker was flagged in the hour before 1, 1 and 2 of the 6 testable stage onsets (three seeds).
  Four of the 10 onsets cannot test early warning: three start on addresses with no traffic at all in the prior 24 h, and one
  (26 May) falls before the training period, where the fixed threshold applies. About 11% of benign source-hours contain an
  alert, so roughly 0.7 of 6 is expected by chance. Token distance alone flags 3 of 6 (see Lead time).
- **For the full model and the supervised heads, a warning appears only when the same address was already attacking.** A
  classifier trained on earlier stages flags an address before its next stage if that address was active in an earlier stage.
  The random forest and the head without sequence state do exactly the same. That is detection of the earlier stage, not
  prediction of the next one. The one possible exception is under Lead time.
- **Window order adds little.** Shuffling the windows inside each hour changes the unsupervised AUC by 0.01 or less on 4 of 6
  stages. Where the sequence state helps the supervised head (Data Exfiltration), the shuffled version helps as much.
- **A fixed threshold is unusable over weeks.** Calibrated for 1%, it flags 33% of benign windows over five test weeks.
- **Only one campaign could test this.** CICAPT-IIoT, the second dataset, cannot: its stages are indistinguishable on the network.

## Data

| Dataset | Access | Use here |
|---|---|---|
| Unraveled (called DAPT2021 by its authors) | Public bucket `dapt2021.s3.amazonaws.com`, no registration; labelled flows 3.47 GB | The R2 test. One APT campaign, 26 May - 6 July 2021, five labelled stages, plus one reconnaissance-only attacker (AA). |
| CICAPT-IIoT 2024 | Registration form at `unb.ca/cic/datasets/iiot-dataset-2024.html`; network CSVs 9.3 GB | Detection only (see below). One campaign, 1-4 Dec 2023, eight tactics. |
| DAPT 2020 | No public download found | Not used. Same team as Unraveled. |

Unraveled, after preparation: 1,640,208 windows. Training span 28 May - 2 June (the only multi-day stretch with no malicious label),
210,323 benign windows. Attack windows: Establish Foothold 26,750, Lateral Movement 25,707, Data Exfiltration 5,963,
AA Reconnaissance 1,847, APT Reconnaissance 677, Cover up 264.

The campaign as labelled, by first appearance (it moves across addresses, and the order is not the textbook one):

| Stage | First seen | Addresses |
|---|---|---|
| Lateral Movement | 26 May (a few flows), heavy from 21 June | 10.1.3.8, 192.168.0.11 |
| Reconnaissance | 3-10 June | 10.8.10.76, 10.8.10.70 |
| Data Exfiltration | 21 June | 10.1.3.8, then 10.1.3.17 |
| Establish Foothold | 22 June | 10.1.3.8 |
| Cover up | 2 July | 10.1.3.17 |

## Method

Everything from R1 is unchanged (model, features, training on benign data only). New for R2, in `code/r2_lead.py`:

- **Continuous sequences.** In the test period each source is one sequence across all days, so state and smoothing carry over
  (stages are days apart).
- **Lead time per onset.** An onset is the first window of a stage on one attacker address. For each: was that address above the
  threshold at any window in the hour before (`alert_1h`), and how many attack windows it already had in the prior 24 h.
- **Base rate.** The share of benign (source, hour) blocks containing an alert, which is what `alert_1h` gives by chance.
- **Three 1% thresholds.** Fixed from the training span; recalibrated daily from all of the previous day's windows (no labels);
  recalibrated daily from the previous day's benign-labelled windows only. The third is not deployable. It checks whether the
  previous day's attacks raise the second one and hide warnings.
- **Supervised, past only.** For each APT stage onset, a stage head is trained on benign windows and on attack windows that
  occurred before that onset, then scored on the new stage. With state, without state, and a random forest.
- **Shuffled control.** The same test data with window order shuffled inside each (source, hour) block.

## Unraveled results (3 seeds, mean and range)

### Detection per stage, unsupervised (AUC against all benign test windows)

| Stage | Windows | Full model | Full model, shuffled | Token distance only |
|---|---|---|---|---|
| APT Reconnaissance | 677 | 0.999 (0.999-0.999) | 0.999 | 0.999 |
| AA Reconnaissance | 1,847 | 0.998 (0.997-0.998) | 0.998 | 0.997 |
| APT Data Exfiltration | 5,963 | 0.958 (0.944-0.978) | 0.955 | 0.836 |
| APT Cover up | 264 | 0.928 (0.912-0.938) | 0.898 | 0.935 |
| APT Establish Foothold | 26,750 | 0.899 (0.890-0.906) | 0.891 | 0.729 |
| APT Lateral Movement | 25,707 | 0.790 (0.780-0.799) | 0.716 | 0.793 |

The full model beats token distance on Establish Foothold (+0.17) and Data Exfiltration (+0.12), which it did not on the R1
datasets. Real order beats shuffled order on Lateral Movement (+0.07) and Cover up (+0.03) only.

### Lead time, unsupervised full model

An onset is testable if its address had traffic in the prior 24 h and it falls after the training period: 6 of the 10 onsets
(10.1.3.8 Data Exfiltration and Establish Foothold, 192.168.0.11 Lateral Movement and Establish Foothold, 10.1.3.17 Data
Exfiltration and Cover up). Counts over all 10 onsets are in `results/unraveled/summary.json`.

| Threshold | Benign windows flagged | Benign source-hours with an alert | Testable onsets (of 6) flagged in the prior hour, per seed |
|---|---|---|---|
| Fixed | 32.6% | 31.6% | 6, 6, 6 |
| Recalibrated daily | 3.5% | 10.8% | 1, 1, 2 |
| Recalibrated daily, benign-only (uses labels) | 3.7% | 11.2% | 1, 1, 2 |
| Shuffled order, recalibrated daily | 4.6% | 11.3% | 2, 2, 2 |
| Token distance only, recalibrated daily | 2.5% | 11.8% | 3, 3, 3 |

- The benign-only threshold flags the same onsets as the label-free one, so the previous day's attacks are not hiding warnings.
- The full model flags Cover up (10.1.3.17, 131 attack windows in the prior 24 h) in every seed, and in one seed Establish
  Foothold on 10.1.3.8 (447 attack windows in the prior 24 h). Both addresses were already attacking.
- **Token distance flags more than the full model** (the same 3 of 6 in every seed): Data Exfiltration on 10.1.3.8 (5 attack
  windows in the prior 24 h), Establish Foothold on 192.168.0.11 (2,759), and Lateral Movement on 192.168.0.11, which had 8,216
  windows in the prior 24 h and none labelled as attack. The last is the one case that could be a real early signal. It is
  one address, and 192.168.0.11 is a busy host (it also carries 5,122 benign-labelled flows), so this does not settle it. The
  full model misses all three in every seed.
- New attacker addresses (10.8.10.76, 10.8.10.70, 10.8.10.87) have no traffic before their first attack window, so nothing can
  precede them. They are detected within the first window to 3 minutes.

### Supervised, trained on the past only (AUC on the new stage)

| New stage | Earlier attack windows | Head with state | Head with state, shuffled | Head without state | Random forest | Unsupervised score |
|---|---|---|---|---|---|---|
| Data Exfiltration | 753 | 0.732 (0.592-0.869) | 0.761 (0.638-0.828) | 0.578 | 0.530 | 0.949 (0.930-0.974) |
| Establish Foothold | 1,635 | 0.982 | 0.980 | 0.985 | 0.988 | 0.872 |
| Cover up | 59,951 | 0.986 | 0.982 | 0.988 | 0.996 | 0.939 |

- Lateral Movement and Reconnaissance are not in the table: fewer than 20 attack windows existed before their onsets.
- Lead time: every head, the head without state and the random forest flag the same onsets in the prior hour, in all seeds:
  10.1.3.8 before Data Exfiltration and before Establish Foothold (it already had attack windows), not 10.1.3.17 before Data
  Exfiltration (it had none), and not Cover up.

## CICAPT-IIoT: detection only

Phase 1 (27 Nov - 1 Dec 2023, 12.06M packets, no attack label) is the training span; phase 2 (1-4 Dec, 9.54M packets) holds
1,004 attack packets between two internal hosts, 172.16.63.128 and 172.16.65.128. Both hosts have benign traffic in training.
After preparation: 195,259 windows, 154 of them attack windows (collection 79, discovery 28, credential access 12, command and
control 11, exfiltration 9, cleanup 8, persistence 4, lateral movement 3).

**Why it cannot test next-stage prediction.** The tactics are actions on the host; the network shows only the control channel.
A random forest asked to tell six tactics apart from the window features scores 0.24 balanced accuracy, against 0.17 with
shuffled labels (maximum 0.29 over 20 shuffles) and 0.17 by chance. Collection against all other tactics gives AUC 0.52.
So "flagged before the next stage" here means "spotted the channel earlier".

What it does show (3 seeds):

| Measure | Result |
|---|---|
| Unsupervised AUC per tactic, token distance only | 0.86-0.97 |
| Unsupervised AUC per tactic, full model | 0.69-0.94, lower than token distance on every tactic |
| Supervised, attack against the same hosts' benign windows (random forest, cross-validated) | 0.90 |
| Past-only heads on each new tactic: with state / without state / random forest | 0.84-0.90 / 0.79-0.91 / 0.84-0.90 |
| Daily recalibration: benign windows flagged | 0.4%; identical with the benign-only threshold |

Shuffling lowers the full model's AUC here (for example collection 0.749 to 0.607), but token distance, which has no sequence
model, drops too (0.880 to 0.804). The attack comes in short contiguous bursts and the per-source smoothing rewards that.

## Evidence limits

- **One campaign.** Ten onsets on Unraveled, of which three are new addresses with no prior traffic. This is a case study.
- **Stage labels are the dataset's.** The labelled order (lateral movement before reconnaissance, foothold after exfiltration)
  is not a clean kill chain; "next stage" means "next labelled stage".
- **False alarms are 3.5%, not 1%,** under daily recalibration. No setting reached 1% over the five weeks (that is R4).
- **Lead time is measured per source address.** The campaign moves between addresses; following it by victim host or by
  campaign was not done.
- **Windows are 5 s from flow records,** and stages here are hours to weeks apart. Sub-second prediction (R5) is untested.
- **Unraveled rows dropped:** 13,169 malformed rows (0.19%, unquoted commas), rows with an invalid stage label, non-IPv4 rows and
  exact duplicates (the gateway capture repeats subnet flows): 6,877,157 read, 6,847,981 kept.
- **CICAPT-IIoT flows are 5 s slices** of connections, because the attack runs over long-lived connections; its features are
  therefore not identical in meaning to the flow features of the other datasets.
- **Environments.** Unraveled ran on Colab (Python 3.13), CICAPT-IIoT on the R1 machine (Python 3.12), both with the R1 package
  versions (torch 2.15.0, numpy 2.5.4, pandas 3.1.1, scikit-learn 1.9.1).
- Cite Myneni et al., *Computer Networks* 2023 (Unraveled) and Ghiasvand et al. 2024 (CICAPT-IIoT) if these results are published.

## What this means for the project (HANDOFF §11, decision 1)

R2 was the test of the novelty claim. On the one campaign available, the evidence is against "blocks attacks before the next
stage": warnings come from detecting an address that is already attacking, and simpler models give the same warnings. Together
with R1 (no sequence-model advantage, no transfer across networks), the supportable claim is anomaly detection per network.
Whether the project's contribution is the mesh coordination and trust design instead is a decision for the team.

## Files

- `code/prep_unraveled.py`, `code/prep_cicapt.py`: loaders. `code/r2_lead.py`: the evaluation.
- `results/unraveled/summary.json`: per-seed AUCs and lead-time counts (the full per-seed outputs are about 1 MB and are kept
  outside the repo).
- `results/cicapt/`: per-seed evaluation output (`cicapt_lead_seed*.txt`, `r2_lead_s*_results.json`), training and preparation logs.
- Not committed: raw data, `windows.npz`, checkpoints.

## Reproduce

Copy the `ncm-prototype/` scripts, then `research/R1/code/*.py`, then `research/R2/code/*.py` into a run directory per dataset.

Unraveled: download the 173 files under `processed/network-flows/` of the bucket to `/content/data/unraveled/flows/`, then

```bash
python prep_unraveled.py
```

CICAPT-IIoT:

```bash
python prep_cicapt.py phase1_NetworkData.csv phase2_NetworkData.csv
```

Then, for each seed 0-2:

```bash
python train.py gru 64 0
```

```bash
python r2_lead.py artifacts/ncm_gru64_s0.pt artifacts/r2_lead_s0
```

For CICAPT-IIoT add `3` as a last argument to `r2_lead.py` (tactics with at least 3 windows are reported). Per seed: Unraveled
trains in about 12 min and evaluates in about 10 min on 4 threads; CICAPT-IIoT about 6 and 2 min.
