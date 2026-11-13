# R1 — Do the results hold on other networks?

Question (HANDOFF §8, R1): run the unchanged pipeline on CSE-CIC-IDS2018 and UNSW-NB15 with no retuning, and also train on
one dataset and test on another.

**Status: done.** All three parts are run with 3 seeds each (GRU-64, seeds 0-2). Results are in `results/`; the 2018 seed 0
re-evaluation with the Botnet Ares stage fix is included (`results/d2018_eval_seed0.txt`, committed after the fix).

| Part | Status |
|---|---|
| UNSW-NB15, same tables as HANDOFF §3 | Done, 3 seeds, rerun in one environment. |
| CSE-CIC-IDS2018, same tables | Done, 3 seeds, on a fixed 10% source subsample (below). |
| Train on one dataset, test on another | Done: all 6 directions between CIC-IDS2017, UNSW-NB15 and CSE-CIC-IDS2018, 3 seeds each (18 runs). |

## Answer in four lines

- **Within one network, yes.** Unsupervised family-mean AUC is 0.942 on UNSW-NB15, 0.954 on CIC-IDS2017 and 0.988 on
  CSE-CIC-IDS2018, all scored with the same rule (see "Scoring rule" below; the handoff's 0.970 for CIC-IDS2017 used a different one).
- **Across networks, no.** A model trained on one network and run on another is near chance or inverted in 4 of 6 directions.
  Only transfer *into* CIC-IDS2017 works (0.89-0.92 from CSE-CIC-IDS2018 and UNSW-NB15).
- **Thresholds never transfer.** With the source network's threshold, 57-100% of the target's benign windows alarm. Recalibrating
  on the target's benign traffic brings false alarms to 1-5% but then catches 0-28% of attack windows.
- **The sequence model still does not beat a random forest.** On unseen families the random forest on single windows is within
  0.003 AUC of the full model, or ahead of it, on all three datasets. On unseen stages the full model leads by 0.009 on CIC-IDS2017
  only. On CIC-IDS2017 even the smoothed isolation forest (0.957) ties the full unsupervised model (0.954).

## Method changes (what differs from the original pipeline)

Everything else is the original pipeline. Model, normalisation, codebooks, calibration and training are unchanged.

**UNSW-NB15**
- `code/prep_unsw.py`: loader. Flow records (Hugging Face `rdpahalavan/UNSW-NB15`, `Network-Flows/UNSW_Flow.parquet`) become the same
  5 s per-source windows and 32 features by reusing `prep.windows`.
- Pseudo-days, fixed before any model ran: day 0 = Jan 22 14:00 to Jan 23 01:00 (no attacks; benign train and calibration);
  day 1 = Jan 22 attack hours; days 2-4 = Feb 18 in three equal blocks. Dev = days 1-2, final = days 3-4.
- Approximated features: UNSW has no TCP flag counts, packet-length max or packet inter-arrival time. Flags are guessed from the
  connection `state`, `flmax` from `smeansz`, `piat` from `sintpkt`. The five flag ratios are therefore near-constant.

**CSE-CIC-IDS2018**
- Source: the authors' corrected flows, `intrusion-detection.distrinet-research.be/CNS2022/Datasets/CSECICIDS2018_improved.zip`
  (10.4 GB). Only five day files are needed. Common Hugging Face mirrors drop the source IP and cannot be used.
- `code/fetch_day.py` extracts one day to parquet, streamed over HTTP or from a local copy (`--zip PATH`).
  **Bug fixed:** under pandas 3, `to_datetime` returns microseconds, and the original divided by 1e9, squeezing each day into
  about 46 seconds. Seconds are now computed with a `Timedelta`.
- `code/prep_2018.py`: loader. Pseudo-days: day 0 = Wed 14-02 from the start of the file up to the first chunk containing an attack
  (5.5M benign flows); dev = Thu 15-02 (DoS GoldenEye, Slowloris) and Wed 21-02 (DDoS HOIC, LOIC-UDP); final = Thu 22-02
  (web brute force, XSS, SQL injection) and Fri 02-03 (Botnet Ares). "X - Attempted" labels are merged into X.
- `code/subsample_sources.py`: 2018 has 5.89M windows (47× CIC-IDS2017), which does not fit the pipeline in 16 GB. Every source that
  is ever an attacker is kept in full (23 sources, with their benign windows); other sources are kept if a hash of the address falls
  in 10%. Result: 656k windows, 8,021 of 80,919 sources. Fixed before any 2018 model ran. False-alarm rates are per window, so the
  sample changes their precision, not their expected value.
- Small families: Web Attack - SQL has 18 windows, XSS 40, Brute Force 73, DoS GoldenEye 165.

**Shared**
- `code/evaluate.py`: families are scored inside each split's days (the original assumed one family per day). Families with under
  10 windows in a split are skipped. Random forest `n_jobs` lowered from 4 to 2 for memory; results do not depend on it.
- `code/ncm.py`, `stage_of()` (judgement calls): UNSW Reconnaissance and Analysis = RECONNAISSANCE, Worms = LATERAL_MOVEMENT,
  Backdoor = COMMAND_AND_CONTROL, other UNSW families default to INITIAL_ACCESS except DoS = IMPACT. 2018: any `DDoS*` = IMPACT
  (previously only `DDoS` matched), any `Botnet*` = COMMAND_AND_CONTROL (previously `Botnet Ares` fell through to INITIAL_ACCESS;
  commit `49ce1d2`). Neither change alters the CIC-IDS2017 mapping.
- `code/cross.py`: cross-dataset evaluation. Checked: with A = B it reproduces `evaluate.py` Part 1 exactly.
- `code/summarize_cross.py`: builds `results/cross/summary.txt`.

## In-domain results (final split, mean of 3 seeds, range in brackets)

Format follows HANDOFF §3 and the results table in §8. "Median time to alert" is in windows of 5 s, from a source's first attack
window to its first alert at the 1% threshold, median over sources.

All three columns use the same scoring rule and 3 seeds. CIC-IDS2017 uses the three handoff checkpoints, rescored with the R1
`evaluate.py` (see "Scoring rule" below).

| Measure | CIC-IDS2017 | UNSW-NB15 | CSE-CIC-IDS2018 |
|---|---|---|---|
| Unsupervised NCM (smoothed), family-mean AUC | 0.954 (0.944-0.966) | 0.942 (0.942-0.944) | 0.988 (0.986-0.990) |
| Unsupervised NCM, worst family | 0.875 (0.832-0.912) | 0.938 (0.937-0.939) | 0.978 (0.968-0.985), Web Attack - SQL in 2018 |
| Token distance only, smoothed, family-mean AUC | 0.951 (0.944-0.963) | 0.940 (0.940-0.940) | 0.985 (0.984-0.986) |
| Smoothed isolation forest, family-mean AUC | 0.957 | 0.915 | 0.807 (worst family 0.559) |
| Detected at the 1% threshold (unsupervised NCM) | 88% (85-92) | 100% | 100% |
| False alarms at the 1% threshold (observed on test benign) | 8.1% (7.3-9.5) | 7.8% (7.7-7.9) | 6.6% (5.1-8.8) |
| Median time to alert, 1% threshold | — | 1.0 window (5 s) for every family | 1.0 window (5 s) for every family |
| Unseen family (leave-one-out), risk score R, mean AUC | 0.990 (0.989-0.991) | 0.995 | 0.998 (0.998-0.999) |
| Random forest on single windows, leave-one-out | 0.987 | 0.994 | 1.000 |
| Stage head without sequence state, leave-one-out | 0.986 | 0.993 | 0.972 |
| Unseen whole stage (leave-one-stage-out), R | 0.983 (0.980-0.985) | 0.996 | 0.997 (0.995-0.999) |
| Random forest, leave-one-stage-out | 0.974 | 0.995 | 0.997 |

Per-seed tables: `results/unsw_eval_seed*.txt`, `results/d2018_eval_seed*.txt`, `results/cic2017_rescored/summary.json`;
JSON in `results/*_results.json`. The 2018 seed 0 file is the re-evaluation with the Botnet Ares stage fix.
UNSW-NB15 family-mean AUC: the unrounded seed values are 0.9415, 0.9419 and 0.9439, mean 0.9424, so 0.942
(averaging the rounded values 0.942, 0.942, 0.944 gives 0.943).

### Scoring rule (why the CIC-IDS2017 column differs from HANDOFF §3)

Family-mean AUC averages, over attack families, the AUC of one family's windows against benign windows. The two versions differ
only in *which* benign windows:

- **Handoff (original `evaluate.py`):** benign windows of the family's own day. Possible only when each family occurs on one day.
- **R1 (`code/evaluate.py`):** benign windows of the whole split (both final days); families with under 10 windows in a split skipped.
  Required for UNSW-NB15 and CSE-CIC-IDS2018, whose families span several days, so it is the only rule usable on all three.

Same three CIC-IDS2017 checkpoints, both rules (final split, unsupervised, mean of 3 seeds):

| Score | Handoff rule | R1 rule |
|---|---|---|
| NCM (smoothed), family-mean AUC | 0.970 (0.965-0.975) | 0.954 (0.944-0.966) |
| NCM, worst family | 0.918 | 0.875 |
| Token distance, family-mean AUC | 0.969 | 0.951 |
| Smoothed isolation forest, family-mean AUC | 0.965 | 0.957 |

The gap (0.016) is larger than the 0.01 treated as noise, so comparing CIC-IDS2017 at 0.970 with the other datasets overstated it.
Pooled AUC, detection and false-alarm rates and all leave-one-out numbers do not depend on the rule and are unchanged. The handoff's
"97% detected at 5.6% false alarms" is the leave-one-out risk score R, not the unsupervised score; the comparable unsupervised
figures are 88% at 8.1%. Rescoring was run on Colab with the pinned R1 package versions; the handoff had leave-one-out results for
seed 0 only, so seeds 1 and 2 were evaluated in full there. Per-seed values for both rules and the leave-one-out means are in
`results/cic2017_rescored/summary.json`.

Smoothed isolation forest and token distance are the baselines the HANDOFF §7 rule requires. UNSW token distance spans 0.940
across the three seeds, which the file rounds to the same value.

## Cross-dataset results (final split of the target, mean of 3 seeds, range in brackets)

Everything comes from the source network A: the backbone, normalisation, codebooks, calibration, isolation forest, stage head and
random forest. "Target-cal" moves only the alarm threshold, to the 99th percentile of the target's benign calibration windows
(no labels, no training). AUC below 0.5 means the ranking is inverted: the target's benign traffic looks *more* abnormal than its attacks.
Time to alert is not measured in the cross runs, so those cells are blank.

| Train → test | NCM family-mean AUC | NCM worst family | Token distance | Isolation forest | False @1%, source threshold | Detect / false @1%, target-cal | Supervised R | Supervised RF |
|---|---|---|---|---|---|---|---|---|
| CIC-IDS2017 → UNSW-NB15 | 0.092 (0.085-0.099) | 0.066 | 0.064 | 0.064 | 95% | 0.8% / 1.3% | 0.218 | 0.111 |
| CIC-IDS2017 → CSE-CIC-IDS2018 | 0.529 (0.487-0.554) | 0.360 | 0.523 | 0.632 | 57% | 5.8% / 1.5% | 0.672 | 0.795 |
| UNSW-NB15 → CIC-IDS2017 | 0.889 (0.813-0.926) | 0.628 | 0.912 | 0.873 | 100% | 23.3% / 1.0% | 0.766 | 0.254 |
| UNSW-NB15 → CSE-CIC-IDS2018 | 0.138 (0.043-0.193) | 0.004 | 0.291 | 0.486 | 100% | 0.0% / 1.0% | 0.636 | 0.668 |
| CSE-CIC-IDS2018 → CIC-IDS2017 | 0.922 (0.920-0.922) | 0.786 | 0.928 | 0.793 | 93% | 27.6% / 2.6% | 0.906 | 0.889 |
| CSE-CIC-IDS2018 → UNSW-NB15 | 0.082 (0.063-0.096) | 0.050 | 0.074 | 0.055 | 100% | 0.9% / 5.4% | 0.735 | 0.143 |

Full tables per run: `results/cross/<a>_to_<b>_s<seed>.txt` (18 runs) and `_results.json`; summary: `results/cross/summary.txt`.

## Findings

- **The in-domain numbers do not show the method generalises; the cross-dataset numbers show it does not.** What the model learns is
  "this network's benign traffic", and the score is distance from that. A new network's benign traffic is itself far from it.
- **Transfer into CIC-IDS2017 works because its attacks are extreme, not because the model transfers.** Most CIC-IDS2017 attack windows
  come from one source (172.16.0.1) doing high-rate DoS, brute force and scans, which look abnormal to any benign model. Even there the
  worst family drops to 0.63-0.79 and the source threshold flags 93-100% of benign traffic.
- **UNSW-NB15 inverts in every direction.** Its benign traffic is unlike both CIC datasets, and its features are partly approximated
  (no TCP flag counts; see limits), so its benign windows look abnormal to models trained elsewhere and its attack windows do not.
  UNSW numbers should be weighed less than the 2018 numbers.
- **Per-network calibration is required, and not sufficient.** HANDOFF finding 4 holds in a stronger form: without retraining, a
  recalibrated threshold either over-alarms or misses almost everything. A new site needs its own benign training period.
- **On CSE-CIC-IDS2018 the sequence state helps the stage head (0.998 vs 0.972) but not over the random forest (1.000).** On the other two
  datasets the state adds nothing. The finding "the sequence model is not earning its place yet" stands.
- **The isolation forest baseline is weak on 2018 (0.807, worst family 0.559)**, so the NCM's advantage there is over isolation forest
  only, not over token distance (0.985) or the random forest.

**Partial evidence on R3 ("is it just a new source?")**: In CSE-CIC-IDS2018 the 10 Botnet Ares sources are internal hosts (172.31.69.x)
that each have about 1,300 benign windows in the training day, and Botnet still scores 0.99 AUC unsupervised. So at least one family
is detected by behaviour on a source the model already knows. Every other 2018 attacker is a new external address (18.21x.x.x), and on
UNSW-NB15 four addresses (175.45.176.0-3) emit every attack, so R3 still needs its own run.

## Evidence limits

- Environment: Python 3.12, torch 2.15 (CPU), pandas 3.1, scikit-learn 1.9, numpy 2.5; 8 logical cores, 16 GB RAM.
  UNSW windows differ from the earlier build by one attack window (30,750 vs 30,749), probably a library version difference.
- The cross-dataset feature spaces are not identical: UNSW's flag and timing features are approximations.
- CIC-IDS2017 cross runs use the three checkpoints from `mesh-handoff.tar.gz`.
- 2018 day 0 is a benign stretch of an attack day, not an all-benign day, and the zip's row order decides where it ends.
- The 2018 stage labels for Botnet, DDoS and DoS are judgement calls (see `stage_of()`); a different mapping changes the stage-head rows.
- Small families (Web Attack - SQL 18 windows, XSS 40) make their per-family AUC noisy.
- Results are from one dataset of each kind and one model size (GRU-64). They say nothing about other architectures.

## Reproduce

Copy `code/*.py` over the `ncm-prototype/` scripts in a fresh directory per dataset.

UNSW-NB15: put `unsw_flow.parquet` one directory above, then

```bash
python prep_unsw.py
python train.py gru 64 0
python evaluate.py artifacts/ncm_gru64_s0.pt
```

CSE-CIC-IDS2018: from the parent of the run directory, for each of d0..d4 (d0 with `--until-attack`):

```bash
python run/fetch_day.py Wednesday-14-02-2018.csv d0 --until-attack --zip CSECICIDS2018_improved.zip
```

Then, in the run directory, prep, train with seeds 0-2, and evaluate each checkpoint with `evaluate.py`.

Cross-dataset: `python cross.py CKPT WINDOWS_A WINDOWS_B OUT_PREFIX`, where `CKPT` is the source network's checkpoint
(`artifacts/ncm_gru64_s<seed>.pt`), `WINDOWS_A` and `WINDOWS_B` are the two `data/windows.npz` files (source, target), and
`OUT_PREFIX` names the output (`results/cross/<a>_to_<b>_s<seed>`). Run it for each of the 6 directions and 3 seeds, then
`python summarize_cross.py results/cross`.
