# NCM prototype — Next-Context Model for unseen-attack detection

A working, measured prototype of the report's "Next-Context Modeling" agent: trained on benign traffic only, tested on attacks it never saw, exported to FP32 ONNX (INT8 is experimental), and replayed as a live node that emits signed, schema-valid block directives.

## Headline results

All numbers are from real traffic (CIC-IDS2017, corrected labels), 5-second windows per source address. Training used Monday only, which contains no attacks, so every attack below is unseen by the unsupervised part.

| Question | Result |
|---|---|
| Does it detect attack types it never saw? | Yes. Risk score R reaches **0.990** mean AUC when each attack family is held out of training in turn, and **0.983** when a whole kill-chain stage is held out. |
| Does the "predict the next step" idea itself help? | **Not on this dataset.** Next-context surprise alone is the weakest signal (0.84 family-mean AUC, unstable across seeds). A sequence-free score matches the full model. |
| What does work? | Distance to a vocabulary of 512 benign behaviour tokens, smoothed over time per source (0.969 family-mean AUC on the final test days, fully unsupervised), plus a small supervised stage head. |
| Is it deployable at the edge? | 96,070 parameters; FP32 is the shadow-mode candidate. Historical single-server-core timing is not edge-hardware validation; INT8 requires separate calibration and validation. |
| How fast does it react? | One 5-second window for most attacks. Not the report's sub-250 ms: that needs packet-level features. |
| False alarms? | Thresholds set for 1% on Monday gave 5–9% on later days. In the live replay nearly every benign host was wrongly quarantined for 30 s at least once per day. Not safe to enforce without the safeguards below. |

## What the research found

"Next-Context Modeling" is the report's name for an existing idea: learn to predict the next event from benign history and flag what is surprising. Closely related published work:

- Surprisal-based unsupervised intrusion detection: X-SPUR ([arXiv 2609.21217](https://arxiv.org/pdf/2609.21217)).
- Benign-only self-supervised NIDS: CLAN ([2509.06550](https://arxiv.org/pdf/2509.06550)), Anomal-E ([2207.06819](https://arxiv.org/pdf/2207.06819)), NetVAD ([2606.01452](https://arxiv.org/pdf/2606.01452)); survey of sequence- and context-based NetFlow detection ([2602.05594](https://arxiv.org/html/2602.05594v1)).
- From memory, not re-checked: DeepLog (next-log-event prediction, CCS 2017), Radford et al. 2018 (an LSTM language model over flow sequences), Kitsune (NDSS 2018).
- Dataset quality: the original CIC-IDS2017 has labelling and flow-construction errors ([Engelen et al. 2021](https://lirias.kuleuven.be/retrieve/713070), [Liu et al. 2022](https://archive.cps-vo.org/node/97449), [Lanvin et al. 2022](https://hal.archives-ouvertes.fr/hal-03775466)). This prototype uses the corrected labels.
- Model size: no published head-to-head of GRU, Transformer and state-space models under INT8 for edge intrusion detection turned up; one study found quantization gives little on already-compact models ([A-THENA, 2604.21623](https://arxiv.org/pdf/2604.21623)). So the choice here was made by measurement.

So the novelty claim cannot rest on the model. See "What this means for the project" below.

## The model

```
flows â”€â–¶ 5 s window per source â”€â–¶ 32 features â”€â–¶ normalize â”€â–¶ embed â”€â–¶ GRU (2 layers, 64) â”€â–¶ state s_t
                                                    â”‚                         â”‚
                         dx: distance to nearest of 512 benign tokens         â”œâ”€ ds: distance to nearest of 512 benign states
                                                                              â”œâ”€ g, k: how badly s_(t-1) predicted this window
                                                                              â””â”€ stage head on [s_t, window] → 6 kill-chain classes

surprise S = z(dx) + z(ds) + (z(g) + z(k)) / 2        each z-scored on benign calibration data
hazard   H = 1 âˆ’ P(benign)                             from the stage head
risk     R = 0.5 · clip(S) + 0.5 · H                   S and H smoothed per source (EWMA, Î± = 0.1)
R > 99th benign percentile → rate-limit;  R > 99.9th → quarantine, TTL 30 s
```

The 32 features follow the report's four groups (timing, transport flags, payload sizes, fan-out), eight each. They are numbers only; no packet text reaches the model.

Why each choice:
- **Three unsupervised signals, not one.** Next-step surprise only fires at a change. A sustained attack becomes predictable within a few windows and its surprise drops; the model "gets used to it". Distance-to-benign signals do not adapt, so they keep firing.
- **Smoothing.** Benign oddities are isolated; attacks persist. Smoothing lifted unsupervised family-mean AUC from 0.93 to 0.97 on the final days.
- **Confidence floor.** The predicted variance is clamped so one over-confident miss cannot produce a huge score.
- **GRU-64.** Constant work per window with a small state per source, which suits streaming. GRU-128 and a Transformer were within seed noise of it.

## Results in detail

**Unsupervised, every attack unseen.** Family-mean AUC; design choices were made on Tue–Wed (dev), Thu–Fri is the final test. NCM rows are means over three training seeds.

| Score | Dev | Final | Worst family (final) |
|---|---|---|---|
| Isolation forest on single windows | 0.896 | 0.924 | 0.790 |
| Isolation forest, smoothed | 0.946 | 0.965 | 0.874 |
| Token distance only, smoothed (no sequence model) | 0.994 | 0.969 | 0.924 |
| Next-context surprise only, smoothed | 0.853 | 0.837 | 0.31 – 0.75 |
| **NCM, all three signals, smoothed** | 0.991 | 0.970 | 0.918 |

At the 1% calibrated threshold on the final days the full NCM detected 85–92% of attack windows, but with 7–10% false alarms instead of 1%: benign behaviour on Thursday and Friday differs from Monday.

**Leave-one-out: the supervised head never saw the tested attack.** Mean AUC, seed 0.

| | Random forest, single window | Stage head without state | Stage head with state (H) | Surprise (S) | **Risk R** |
|---|---|---|---|---|---|
| One family held out (15 folds) | 0.987 | 0.986 | 0.983 | 0.968 | **0.990** |
| One whole stage held out (5 folds) | 0.974 | 0.955 | 0.965 | 0.978 | **0.983** |

R detected 97% (family) and 95% (stage) of held-out attack windows at about 5.5% false alarms. Hardest cases: botnet traffic (0.96) and the infiltration download (0.94), both quiet and close to normal browsing.

**Historical server-core cost:** FP32 778 KB, INT8 374 KB; 0.51 ms vs 0.41 ms per batch of 64 in the original measurement. Its AUC pair (0.9673/0.9663) is not a general quantization-loss bound. The later seed-2 audit found 41,403/99,515 INT8 decisions changed at the PyTorch threshold (INT8 not recalibrated), and FP32 maximum raw-score error 0.269 despite no threshold-decision differences.

**Historical INT8 recorded replay** (original runs; not the current FP32 default):

| Day | Attack windows under quarantine | Benign windows under quarantine | Directives |
|---|---|---|---|
| Tue (FTP, SSH brute force) | 82% | 0.12% | 456 |
| Wed (four DoS types, Heartbleed) | 78% | 0.16% | 265 |
| Thu (web attacks, infiltration) | 79% | 1.33% | 436 |
| Fri (botnet, port scan, DDoS) | 44% | 6.39% | 2,217 |

**Separate FP32 Friday verification:** 2,201 directives; coverage is recomputed from window labels and generated events by `research/audit/verify_replay.py`. See its result JSON for exact counts. Tuesday–Thursday FP32 replay has not been run.

In the historical INT8 runs, the external attacker was quarantined in its first window every day. Botnet hosts were caught 50–95 s in and only 22–49% covered. In this replay the stage head had seen these families; the zero-day evidence is the leave-one-out table.

## What this means for the project

1. **Keep NCM, but describe it accurately.** What is supported: an unsupervised behaviour-vocabulary detector plus a stage classifier, combined as the report's R = Î±S + (1âˆ’Î±)H, catches unseen attack families at about 0.98–0.99 AUC on this data, with a compact FP32 deployment candidate; INT8 is experimental.
2. **The prediction claim is untested, not disproven.** CIC-IDS2017 attacks are loud and each source does one thing; there are no reconnaissance → access → lateral chains from one source. Stopping an attack before its next stage can only be shown on a multi-stage dataset.
3. **Do not enforce on one node's opinion.** The false-quarantine rate is the strongest argument for the report's safeguards: shadow mode first, two-peer corroboration, 30 s expiry, protected prefixes.
4. **Evaluate recalibration offline with reviewed clean data.** A threshold fixed on one day drifted 5–9× within the week.
5. **The schema needs two additions**, made here as version 1.1.0: an `IMPACT` stage (denial of service fits none of the report's five) and a longer `horizon_ms`. No `EXFILTRATION` example exists in this dataset, so the head can never output it.

## Limits of this evidence

- One lab network, five days, 14 hosts. Most attacks come from a single address that never appears in training, so some of the separation may be "new external source" rather than attack behaviour. A feature that would have exposed this directly (share of internal destinations) was left out on purpose.
- Windows are built from flow records, not packets: 5 s instead of the report's 50 ms, and no TLS fingerprint, byte entropy or DNS failure features.
- The dev/final split was introduced partway through; the first exploratory runs looked at all four attack days. Treat the numbers as optimistic until repeated on another dataset.
- Small evaluation sets for some families (Heartbleed 11 windows, SQL injection 15).
- The dataset copies are third-party Hugging Face mirrors. The corrected copy had lost the hour from its timestamps; it was recovered by matching flows to the original copy (99.2–100% exact matches). Check the dataset's terms of use before publishing results.

## Next steps, in order

1. Repeat on a second dataset without retuning (CSE-CIC-IDS2018 or UNSW-NB15).
2. Find or build a multi-stage dataset and test whether hazard rises before the next stage. This is the experiment the novelty claim depends on.
3. Extract packet-level features from the pcaps to get sub-second windows.
4. Add rolling per-site calibration and measure false quarantines per host per day.
5. Port `Step` to the Rust agent: it is the same ONNX file through the `ort` crate, with one state vector per source.

## Run it

```bash
pip install torch pandas pyarrow scikit-learn onnx onnxruntime jsonschema cryptography
```

Data: put the five corrected day files (`monday.csv` … `friday.csv`, Hugging Face `bvk/CICIDS-2017`) in `data/` and the original labelled-flow parquet files (`bvsam/cic-ids-2017`, folder `traffic_labels`) in `data/orig/`.

```bash
python prep.py
```

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

| File | Purpose |
|---|---|
| `prep.py` | flows → per-source 5 s windows, 32 features, hour recovery |
| `ncm.py` | the model and scoring |
| `train.py` | benign-only training, vocabularies, calibration |
| `evaluate.py` | baselines, unsupervised and leave-one-out evaluation, thresholds |
| `export.py` | streaming step → ONNX → INT8, parity and timing |
| `stream.py` | live replay → signed `NCMThreatDirective`s and console demo events |
| `schemas/ncm-threat-directive.json` | the directive contract (report schema, v1.1.0) |
| `test_ncm.py` | self-checks: streaming equals batch, signatures, hostile directive fields rejected |
| `artifacts/` | trained models, ONNX files, full evaluation output, directives and demo event files |

`artifacts/demo_events_<day>.json` is in the console's event format, so these recorded runs can drive the replay demo directly.


## Deployment decision after the audit

`stream.py` now requires the FP32 `.onnx` export produced by `export.py` for its checkpoint. It fails if that file is missing and never falls back to `.int8.onnx`. INT8 export remains available for offline experiments; it is not the deployment candidate. The recovered seed-2 audit found zero FP32 threshold-decision disagreements but 41,403 INT8 disagreements on 99,515 test windows, using the PyTorch threshold. This does not validate every checkpoint, the stage/hazard head, batch size, network, or blocking policy.

Replay performs inference with fixed model weights, normalization, codebooks and calibration. Per-source hidden-state/EWMA updates are inference state, not training. There is no automatic traffic-to-training/refitting path in this replay. Keep training and R11 refitting as deliberate offline research commands. Before adopting any new model, the owner must review a separately saved traffic dataset, its provenance and clean-period assessment, then review held-out detection and false-alarm results. Do not feed the live stream into training or replace an active checkpoint automatically. Owner review reduces exposure; it is not a measured poisoning defense or a guarantee that traffic is clean.
