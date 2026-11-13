# Handoff — Decentralized Predictive Firewall Mesh / NCM model

Historical handoff written 2026-11-10. Current audit decisions supersede historical deployment recommendations below: FP32 is the shadow-mode candidate; INT8 is experimental; production blocking remains unsupported. Everything a new person needs to continue: what exists, what was measured, how to reproduce it, and the research and engineering still to do, in order.

## 1. Status in six lines

- **Project:** a mesh of firewalls that score traffic behaviour, block sources predicted to be attacking, and share alerts. Source design: the 20-page architecture report.
- **Plan:** `IMPLEMENTATION_PLAN.md` (23 sections): zero-cost stack, phases, API, console, security, data model.
- **Built:** only the NCM model prototype (`ncm-prototype/`, 865 lines of Python). Nothing else in the plan is built.
- **Measured:** detects attack families it never saw at 0.990 mean AUC, in historical prototype measurements; current candidate is FP32 and INT8 is experimental (see audit).
- **Main open question:** "predict the next attack stage" is untested. On the one dataset used, the sequence model adds nothing over a simpler score.
- **Main risk:** false alarms. A fixed threshold drifted from 1% to 5–9% within a week.

## 2. What exists

Everything is in the archive `mesh-handoff.tar.gz` (this file, the plan, the prototype, trained models, the prepared dataset).

| Path | What it is |
|---|---|
| `HANDOFF.md` | this file |
| `IMPLEMENTATION_PLAN.md` | full system plan |
| `ncm-prototype/README.md` | model design, result tables, limits |
| `ncm-prototype/prep.py` | raw flows → 5 s windows per source, 32 features, hour recovery |
| `ncm-prototype/ncm.py` | model, scoring, smoothing, kill-chain stage mapping |
| `ncm-prototype/train.py` | benign-only training, vocabularies, calibration |
| `ncm-prototype/evaluate.py` | baselines, unsupervised and leave-one-out evaluation, thresholds, stage head |
| `ncm-prototype/export.py` | streaming step → ONNX → INT8, parity check, timing |
| `ncm-prototype/stream.py` | live replay → signed directives and console demo events |
| `ncm-prototype/test_ncm.py` | self-checks (all pass) |
| `ncm-prototype/schemas/ncm-threat-directive.json` | directive contract, version 1.1.0 |
| `ncm-prototype/data/windows.npz` | prepared dataset: 125,674 windows × 32 features, with day, source, time, family |
| `ncm-prototype/artifacts/ncm_gru64_s0.pt` | **the chosen model** (with stage head and thresholds) |
| `ncm-prototype/artifacts/ncm_gru64_s0.int8.onnx` | experimental quantized export, 374 KB; requires separate calibration/validation |
| `ncm-prototype/artifacts/ncm_gru64_s0.onnx` | FP32 shadow-mode candidate |
| `ncm-prototype/artifacts/eval_gru64_s0.txt` | full evaluation output |
| `ncm-prototype/artifacts/*_results.json` | results per checkpoint (3 seeds of GRU-64, GRU-128, Transformer) |
| `ncm-prototype/artifacts/directives_<day>.jsonl` | signed directives from the replay, Tue–Fri |
| `ncm-prototype/artifacts/demo_events_<day>.json` | the same runs in the console's event format |

Not in the archive: the 1.1 GB of raw dataset files. `windows.npz` is enough to train, evaluate, export and replay; raw files are only needed to rerun `prep.py` (section 5).

## 3. What was measured

> **Superseded.** The headline numbers are now in `PLAN.md` §1 (where we are). The 0.970 below used a different scoring rule; under the common rule it is 0.954.

Dataset: CIC-IDS2017, corrected labels. Training: Monday only (benign). Dev: Tue–Wed. Final test: Thu–Fri.

| Measure | Value |
|---|---|
| Unseen family, risk score R (15 leave-one-out folds) | 0.990 mean AUC; 97% detected at 5.6% false alarms |
| Unseen whole kill-chain stage (5 folds) | 0.983 mean AUC; 95% detected at 5.5% false alarms |
| Unsupervised only, final days, family-mean AUC | full NCM 0.970; token distance alone 0.969; isolation forest smoothed 0.965; next-context surprise alone 0.837 |
| Random forest on single windows, same leave-one-out | 0.987 / 0.974 |
| Stage head without the sequence state | 0.986 / 0.955 (with state: 0.983 / 0.965) |
| Size and speed | 96,070 parameters; historical FP32 778 KB, 0.51 ms per 64 sources on one server thread. INT8 is experimental; no general 0.001 AUC-loss claim is supported |
| Live replay, Tue / Wed / Thu / Fri | 82 / 78 / 79 / 44% of attack windows under quarantine; 0.12 / 0.16 / 1.33 / 6.39% of benign |

Findings to carry forward:
1. The sequence model is not earning its place yet. The margin over a random forest and over the no-state head is within noise.
2. Next-step surprise fades during a sustained attack, because the model adapts to it. Distance-to-benign signals do not.
3. Smoothing a score over a source's recent windows is the single biggest improvement.
4. Thresholds must be recalibrated continuously, and one node must never enforce alone.
5. Architecture barely matters at this scale: GRU-64, GRU-128 and a Transformer are within seed noise.

## 4. What the evidence does not cover

- One lab network, five days, 14 hosts. Most attacks come from one address (172.16.0.1) that never appears in training, so part of the separation may be "new external source", not attack behaviour.
- Windows are 5 s from flow records. The report specifies 50 ms from packet counters, with TLS fingerprint, byte entropy and DNS failure features that flow records lack.
- No multi-stage chains from one source, so prediction of the next stage cannot be evaluated.
- Early exploration looked at all four attack days before the dev/final split existed. Numbers are optimistic.
- Some families are tiny: Heartbleed 11 windows, SQL injection 15.
- The report's own figures (14.8 Mpps, 2.4 ms, 92 ms finality, 93% F1 under poisoning) remain unverified.

## 5. Reproduce

Environment used: Python 3.13, torch 2.15 (CPU), pandas 3.0, scikit-learn 1.9, onnx 1.23, onnxruntime 1.29, numpy 2.5, pyarrow 26, jsonschema 4.26, cryptography 50. Four CPU cores, no GPU. Training takes about 25 s, full evaluation about 3 min.

```bash
pip install torch pandas pyarrow scikit-learn onnx onnxruntime jsonschema cryptography
```

From `ncm-prototype/`, with `data/windows.npz` present:

```bash
python train.py gru 64 0
```

```bash
python evaluate.py artifacts/ncm_gru64_s0.pt
```

```bash
python export.py artifacts/ncm_gru64_s0.pt
```

```bash
python stream.py artifacts/ncm_gru64_s0.pt 4
```

```bash
python test_ncm.py
```

`train.py` overwrites the checkpoint and drops its stage head; always run `evaluate.py` (without `--quick`) before `export.py` or `stream.py`.

To rebuild `windows.npz`, download the raw files then run `python prep.py`:

| Put in | Files | From |
|---|---|---|
| `data/` | `monday.csv` … `friday.csv` (811 MB) | Hugging Face dataset `bvk/CICIDS-2017` |
| `data/orig/` | 8 parquet files (306 MB) | Hugging Face dataset `bvsam/cic-ids-2017`, folder `traffic_labels` |

## 6. Things that will trip you up

| Issue | Detail |
|---|---|
| Lost hours in the corrected data | That copy's timestamps are `MM:SS.s` only. `prep.py` recovers the hour by matching each flow's 5-tuple and minute to the original copy (99.2–100% exact). Ports are reused, so match on every start minute, not the earliest. The authors' own files at `intrusion-detection.distrinet-research.be/CNS2022` should have full timestamps and would remove this step. |
| ONNX export leaves the model in training mode | Dropout then corrupts any comparison made afterwards. `score()` resets it. |
| INT8 quantizer breaks on `Gemm` | Linear layers are written as matmul + add (`ncm.Linear`) so quantization works. Do not replace with `nn.Linear`. |
| Signing is not RFC 8785 | `stream.py` signs sorted compact JSON. Switch to a real JCS library before the Rust agent has to verify these. |
| Schema differs from the report | Version 1.1.0 adds stage `IMPACT` and `horizon_ms` 5000. |
| Replay is not a zero-day test | In `stream.py` the stage head has seen those attack families. The zero-day evidence is the leave-one-out tables. |
| Demo events contain the answer | Each event's payload has a `truth` field from the labels. Fine for a demo, never in production. |
| Negative "first quarantine" times | Means that host was falsely quarantined earlier in the day, before its attack began. |
| Kill-chain mapping is a judgement call | `stage_of()` in `ncm.py`. No `EXFILTRATION` example exists in this data. |

## 7. Evaluation rules — keep these or the numbers stop meaning anything

1. Train the backbone on benign data only.
2. Make every design choice on dev data. Touch the final split once per reported configuration.
3. Report family-mean AUC and the worst family, not only pooled AUC.
4. Always report the false-alarm rate actually observed on test benign traffic at the calibrated threshold.
5. Zero-day claims come only from leave-one-family-out and leave-one-stage-out.
6. At least 3 seeds; report the spread. Differences under about 0.01 AUC are noise here.
7. Every new idea is compared against the three cheap baselines: smoothed isolation forest, smoothed token distance, random forest on single windows.

## 8. Research still to do, in order

> **Superseded.** The ordered list of steps is `PLAN.md` §3; the rounds are described in `PLAN.md` §5. R1 and R2 are done (`research/R1`, `research/R2`).

Each item lists the comparison to run and when it counts as done.

| # | Question | Do | Compare | Done when |
|---|---|---|---|---|
| R1 | Do the results hold on other networks? | Run the unchanged pipeline on CSE-CIC-IDS2018 and UNSW-NB15. Only `prep.py` needs a new loader. | Same tables as section 3, no retuning. Also train on one dataset, test on the other. | Family-mean AUC and false-alarm rates reported for both. |
| R2 | **Can it predict the next stage?** The novelty claim depends on this. | Use a multi-stage dataset: DAPT 2020, Unraveled, CICAPT-IIoT. Label each source's stage over time. | Lead time: how many seconds before a stage's first window does R cross the threshold? Against token distance, against the stage head without state, and against the same sequences with window order shuffled. | A number for median lead time per stage transition, and whether the sequence model beats the shuffled control. |
| R3 | Is the separation just "new external source"? | Evaluate only internal attackers (botnet, infiltration). Remove `log_gap` and first-window effects. Add benign external sources to training if any dataset has them. | Per-family AUC before and after. | The drop is known and stated. |
| R4 | How low can false alarms go? | Rolling calibration (recalibrate hourly on the last N hours), per-host thresholds, require k of n windows, and simulated two-node corroboration (split hosts across virtual nodes). | False quarantines per host per day at a fixed 90% attack-window detection. | A configuration under one false quarantine per host per day, or a statement that it is not reachable. |
| R5 | Do sub-second windows work? | Extract the report's features from the pcaps (same Hugging Face repo, about 52 GB), including byte entropy, TLS fingerprint, DNS failures. | Window sweep 0.05 / 0.5 / 1 / 5 s: AUC, false alarms, time to first alert. | The fastest window that keeps accuracy is identified. |
| R6 | Which model and settings? | Sweep on dev only. | Backbone: GRU vs Transformer vs state-space at equal parameter count. Vocabulary 128 / 512 / 2,048. Smoothing 0.05–0.5. Mix α 0–1. Add published baselines: an autoencoder, Kitsune, a DeepLog-style next-token model. 5 seeds. | One table; choice justified or "no difference" stated. |
| R7 | How does it fail under evasion? | Low and slow: stretch attack timing 10× and 100×. Mimicry: move attack features toward benign means. Baseline poisoning: mix 1–5% attack windows into training. | Detection rate versus evasion strength. | Break points documented. |
| R8 | Does federated learning work for this model? | Split hosts into clients, train with Flower. The behaviour vocabulary is k-means, which plain weight averaging cannot merge — decide how to federate it. | Central vs federated accuracy; then 10–30% poisoning clients with and without robust aggregation. | Accuracy gap and poisoning tolerance measured. |
| R9 | Real edge cost | Run the INT8 model on an ARM board (Raspberry Pi class) through the Rust `ort` crate. | Latency, memory, parity with Python outputs. | Numbers on real hardware. |
| R10 | Prior art | Literature search for systems that combine gossip alerts, consensus and attested federated learning. | — | A related-work paragraph with what is and is not new. |

Results table to fill in for every experiment:

| Dataset | Model / setting | Seeds | Family-mean AUC | Worst family | Detect @1% | False @1% (observed) | Median time to alert | Notes |
|---|---|---|---|---|---|---|---|---|

## 9. Engineering still to do

Follows the phases in `IMPLEMENTATION_PLAN.md` §9. None of it is started.

| Step | Work | Depends on |
|---|---|---|
| E1 | Freeze the directive schema (1.1.0) and the event format; build the 1,000-payload rejection suite | — |
| E2 | XDP collector that emits the same 32 features `prep.py` computes, checked value-for-value against it on a replayed pcap | R5 for the window size |
| E3 | Rust agent: load the ONNX file, one state vector per source, smoothing, thresholds, sign, write the block map; shadow mode default | E1, E2, R9 |
| E4 | Rolling calibration in the agent | R4 |
| E5 | Gossip mesh with validation, two-peer corroboration, TTL, protected prefixes | E3 |
| E6 | Web app: accounts, add-a-site, replay demo. The demo event files already exist | E1 |
| E7 | Lite enforcer and live demo | E5, E6 |
| E8 | Consensus, federated learning, attestation | E5, R8 |

## 10. What can be claimed today

> **Superseded.** The current claims table is `PLAN.md` §10.

| Safe to say | Not yet |
|---|---|
| A 374 KB benign-trained model flags attack families it never saw at about 0.98–0.99 AUC on CIC-IDS2017 | "Detects zero-days" in general |
| The model sees only numbers and emits a schema-locked, signed directive | "Blocks attacks before the next stage" |
| It runs in well under a millisecond per batch on one CPU core | Any of the report's throughput, latency or poisoning figures |
| Single-node enforcement produces daily false quarantines, which is why the mesh safeguards exist | "Safe to run in enforce mode" |

## 11. Decisions the team has to make

1. If R2 shows no prediction benefit, is the project's contribution the mesh coordination and trust design instead of the model?
2. Keep the sequence model if it stays tied with simpler scores? Dropping it would halve the model and remove per-source state.
3. Source address as the unit of scoring, or source–destination pair? Pairs separate mixed behaviour but multiply state.
4. Acceptable false-quarantine budget per host per day.
5. Research project or public service? The free hosting chosen in the plan forbids commercial use.

## 12. Datasets

| Dataset | Use | Status | Where | Cautions |
|---|---|---|---|---|
| CIC-IDS2017, corrected labels | everything so far | used; prepared as `windows.npz` | Hugging Face `bvk/CICIDS-2017`; authors' page `intrusion-detection.distrinet-research.be/CNS2022` (not reachable from the build machine) | mirror lost the hour in timestamps |
| CIC-IDS2017, original flows | hour recovery only | used | Hugging Face `bvsam/cic-ids-2017` (`traffic_labels`); official `unb.ca/cic/datasets/ids-2017.html` | known label errors — do not evaluate on these labels |
| CIC-IDS2017 pcaps | R5 | to get, about 52 GB | same Hugging Face repo, folder `pcap` | large |
| CSE-CIC-IDS2018 | R1 | to get | `unb.ca/cic/datasets/ids-2018.html` | same error types as 2017; prefer the corrected version from the CNS2022 page |
| UNSW-NB15 | R1 | to get | `research.unsw.edu.au/projects/unsw-nb15-dataset` | a few attacker addresses emit all attack types at once, so per-source windows mix families; consider source–destination pairs |
| DAPT 2020 | R2 | to get; download page not checked | via its paper | small (about 87k flows) |
| Unraveled | R2 | to get; download page not checked | via its paper | semi-synthetic, about 6.9M flows |
| CICAPT-IIoT | R2 | to get; download page not checked | paper: arXiv 2407.11278 | provenance and network logs, industrial setting |

Check each dataset's terms of use and citation requirements before publishing.

## 13. References

- Architecture report: *Decentralized Predictive Firewall Mesh* (20 pages) — the design source; its numbers are targets.
- Surprisal-based intrusion detection: [X-SPUR](https://arxiv.org/pdf/2609.21217)
- Survey, contextual NetFlow detection: [arXiv 2602.05594](https://arxiv.org/html/2602.05594v1)
- Benign-only self-supervised detection: [CLAN](https://arxiv.org/pdf/2509.06550), [Anomal-E](https://arxiv.org/pdf/2207.06819), [NetVAD](https://arxiv.org/pdf/2606.01452)
- Dataset errors: [Engelen et al. 2021](https://lirias.kuleuven.be/retrieve/713070), [Liu et al. 2022](https://archive.cps-vo.org/node/97449), [Lanvin et al. 2022](https://hal.archives-ouvertes.fr/hal-03775466)
- Multi-stage datasets: [CICAPT-IIoT](https://arxiv.org/abs/2407.11278), [Network Intrusion Datasets survey](https://arxiv.org/pdf/2502.06688)
- Quantization on compact models: [A-THENA](https://arxiv.org/pdf/2604.21623)
- From memory, not re-checked: DeepLog (CCS 2017), Radford et al. 2018 (LSTM over flow sequences), Kitsune (NDSS 2018).

## Audit continuation — 13 November 2026

See research/audit/README.md for code corrections, actual local fresh-training/poison diagnostic results, and the remaining artifact-dependent reruns. R12b cannot decide from missing data; tied-score weighted AUC was corrected; the headline checker now fails its process on failed checks. No mesh gate, independent confirmation, or original raw-data discrepancy resolution is claimed.
