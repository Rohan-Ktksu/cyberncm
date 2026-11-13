# Claims ledger

Plan step 36. Every sentence the project may say in public, with the file and commit that back it, and the sentences it must not say. A claim is only as strong as its row: every file cited here is on `main` except those marked open (R9) (the were merged; their branch commits are kept on `main`). **No row is confirmed by an independent rerun yet** (plan step 27; kit in `research/RERUN/`, 8ca52cb). When you add a sentence anywhere public, add its row here first.

Statuses: **May say** (with the qualifier in the row), **Must not say**, **Unmeasured** (no evidence either way; do not say it).

## May say

| # | Sentence (with its qualifier) | Evidence |
|---|---|---|
| S1 | A model trained only on one network's normal traffic flags attack families it never saw at family-mean AUC 0.954 (CIC-IDS2017), 0.942 (UNSW-NB15), 0.989 (CSE-CIC-IDS2018, 10% of sources) and 0.894 (Unraveled) on the later days of each dataset, mean of 5 seeds; 0.697 on CICAPT-IIoT. Public lab datasets with few attackers. | `research/SCOREBOARD.md`, `research/scoreboard.csv` |
| S2 | The GRU part is justified by one dataset: v0 beats its own token-distance score clearly only on Unraveled (0.894 against 0.857); on three datasets the gap is at most 0.003 and on CICAPT-IIoT v0 is 0.14 worse. | `research/SCOREBOARD.md`, `research/R6a/README.md` |
| S3 | A supervised random forest trained without the test period is ahead of v0 on CIC-IDS2017, UNSW-NB15 and CICAPT-IIoT and behind on CSE-CIC-IDS2018 and Unraveled; it needs labelled attacks. | `research/SCOREBOARD.md`, `research/R6f/README.md` |
| S4 | The model has 96,070 parameters. Historical server-thread measurements: FP32 778 KB / 0.51 ms per 64-source batch; experimental INT8 374 KB / 0.41 ms. FP32 is the shadow-mode candidate; INT8 requires separate calibration and validation. Not measured on edge hardware. | `HANDOFF.md` |
| S4c | The scoring step of the model (96,070 parameters, 374 KB as INT8, 512 bytes of state per tracked source) took 0.44 to 0.45 ms per batch of 64 sources on one pinned core of a cloud CPU (AMD EPYC 7B12), 99th percentile at most 0.79 ms, over four runs. This is a substitute measurement: not an edge board, and feature extraction is not included. | `research/R9/README.md` |
| S4b | INT8 and full-precision versions of the model do not give identical results: the test AUC differed by between -0.0003 and +0.0111 over four runs, and the correlation of their raw scores was 0.92 to 0.95. (The earlier 0.001 figure in `HANDOFF.md` is not reproduced and must not be quoted.) | `research/R9/README.md` |
| S5 | On a five-week multi-stage campaign (Unraveled) stages are detected while they happen at 0.79 to 0.999 AUC per stage. | `research/R2/README.md` |
| S6 | A fixed alarm threshold does not hold over weeks; per-network and per-period calibration is required; false alarms are 3.5% of windows at best under daily recalibration. | `research/R2/README.md`, `research/R4/README.md` |
| S7 | A new site needs no gradient training: refitting the normalisation, both centre sets and the calibration on its own normal traffic gives a final AUC within 0.021 of retraining the whole model in all six directions between CIC-IDS2017, UNSW-NB15 and CSE-CIC-IDS2018. Lab data only. | `research/R11/README.md` |
| S8 | No change tried to v0 (running averages, self-normalisation, other scoring functions, per-destination or per-service scoring, a supervised head) passed the pre-set improvement rule, so the shipping model is v0. Per-pair scoring is an open lead, not a result. | `research/V1/README.md`, `research/R6a` to `research/R6f` |
| S9 | The model reads no packet content or free text, and the code reviewed has no path from packet text to a decision or directive; the directive schema has no free-text field. | `research/R7/R7g.md` |
| S10 | Attackers that already have benign history on the network are detected at AUC 0.953, 0.993 and 0.830 (CIC-IDS2017, CSE-CIC-IDS2018, Unraveled; 6, 10 and 3 attacking sources) and this does not depend on the "gap since last window" feature. | `research/R3/README.md` |
| S11 | A brand-new benign source is likely to raise alerts: windows from sources unseen on the training day were above the threshold 92% and 94% of the time on CIC-IDS2017 and Unraveled. | `research/R3/README.md` |
| S12 | The product should alert and show what it would block, not block on its own: no alert policy tried reaches 80% of attackers in 5 minutes with fewer than one false alert per host-day on Unraveled in any of 5 seeds. | `research/R4/README.md` |
| S13 | In a simulation with the victim hosts split into 2 or 4 sites, sharing blocks between sites speeds up the first block (at 4 sites the share of attackers already blocked at their first window rises from 0.44 to 0.71, 0.21 to 0.48 and 0.28 to 0.45 on three datasets) but spreads false alerts to other sites and does not stop a lying site when false alerts are common. | `research/R12/README.md` |
| S14 | Mixing 0.5% to 2% of one attack family's windows into the first day of learning makes that family undetected for 6 of 20 testable families (CIC-IDS2017 and CSE-CIC-IDS2018); trimming the most unusual windows does not fix it under the pre-set rule. | `research/R7/README.md`, `research/R7m/README.md` |
| S15 | Windows shorter than 5 seconds built from flow records (CIC-IDS2017 only) alert sooner (median 20 to 25 s to the first alert against 81 s) but lose accuracy on the final days (family-mean AUC 0.917 at 1 s and 0.878 at 0.5 s against 0.954 at 5 s), so the 5-second window stays. Flow-level only: no packet captures, no 0.05 s window. | `research/R5/README.md` |
| S16 | A small open language model (Qwen2.5-0.5B, CPU) given our window features as text scores a family-mean AUC of 0.64 zero-shot and 0.64 with 6 examples, against 0.93 for v0 on the same 355 windows, and follows an instruction added to its input (all 24 flagged attack windows turned into normal). This says nothing about larger or fine-tuned models. | `research/R14/README.md` |
| S17 | Adding attack flows to a benign host (1% to 20% of its flows) or spoofing unanswered flows to an uninvolved host gets it blocked by the research block rule on every seed; that rule already blocks 29 to 42 of 48 benign host-days with nothing injected, so no blocking should rest on a score. Dropping unanswered flows removes the spoofed-source blocks (0 of 34), but its cost to scan detection was not measured. | `research/R7df/README.md` |
| S18 | No backbone or objective change tried (a seed ensemble, a Transformer with the same hidden size, a masked-history objective) beats v0 by the improvement rule; the Transformer is worse on two datasets and the ensemble gains about 0.005 AUC at best for five times the compute. | `research/R6e/README.md` |
| S19 | Following a campaign from the victim side (risk on the hosts it touches next, before their first attack window) showed no signal beyond the order-free control; only 2 victim hosts and 3 subnets were testable. | `research/R13/README.md` |
| S20 | A single-site console and agent exist (sign-up, add a site, enrol an agent with a signed key, a learning period, a shadow-mode would-block list); nothing in it blocks anything. On a 70-minute CIC-IDS2017 slice the would-block list held the attacker and one benign host. | `product/README.md` |

## Must not say

| # | Sentence | Why not | Evidence |
|---|---|---|---|
| N1 | "Predicts the next stage", "blocks before the next stage", "warns before an attack" | The attacker was flagged in the hour before 1, 1 and 2 of 6 testable stage onsets; the plan's prediction rounds are not done | `research/R2/README.md` |
| N2 | "Safe to block automatically" | No alert policy meets the target; false alarms 3.5% of windows at best | `research/R4/README.md`, `research/R2/README.md` |
| N3 | "Works on a new network without a learning period", or any specific shadow-mode duration (including "10 minutes") | Refitting on the site's own normal traffic is required; 10 minutes is the lab minimum on clean lab data; the real duration is unmeasured | `research/R11/README.md` |
| N4 | "Benefits from sharing between sites", "mesh", "consensus", "federated learning" as features that improve detection | Simulated sharing spreads false alerts and is not stopped by a lying site under the two-site rule; consensus and federated learning were never measured | `research/R12/README.md` |
| N5 | "Robust to poisoning" or "robust to an adversary", "cannot be evaded" | A poisoned learning period blinds the model for 6 of 20 testable families; mimicry tests are weak; targeted adversaries untested | `research/R7/README.md`, `research/R7m/README.md` |
| N6 | "Catches attackers that are already inside as reliably as new ones" | On Unraveled attackers with history score 0.83 against 0.998 for the new one | `research/R3/README.md` |
| N7 | "Beats supervised or simple baselines" | It does not beat token distance alone on four datasets, and the random forest trained without the test period beats it on three | `research/SCOREBOARD.md` |
| N8 | Any figure, comparison or result from the original architecture report | Not reproduced; the project's numbers come from `research/` only | `PLAN.md` section 10 |
| N9 | "Confirmed", "independently verified" or "reproduced" about any result | No independent rerun has been done | `research/RERUN/README.md` |
| N10 | "Production-ready" or "tested on a real network" | Only public lab datasets; no live deployment | `MODEL_CARD.md` |
| N11 | "Language models are worse (or better) detectors than v0" in general | One 0.5-billion-parameter model on CPU, zero-shot and 6-shot, on a sample of 355 windows; fine-tuned and larger models and published traffic models were not tried | `research/R14/README.md` |
| N12 | "Sub-second windows work" or "improve detection" | Flow-level only on one dataset: 1 s and 0.5 s windows lost accuracy; no packet-level features tested | `research/R5/README.md` |
| N13 | "The product blocks threats", "monitors live traffic", or "learns in N minutes" | The agent only replays flow files, never blocks anything, and its learning period is not validated | `product/README.md` |

## Unmeasured (say nothing)

| # | Topic | Status |
|---|---|---|
| U1 | Fine-tuned or larger language models, and published traffic models (ET-BERT, netFound, NetVAD) | R14 was a CPU-scale version with one small model; these were not tried |
| U2 | Campaign following with more than a handful of events, or with the full model | R13 ran on token distance with 2 testable hosts and 3 subnets |
| U3 | Packet-level features (byte entropy, TLS fingerprint, DNS failures) and windows shorter than 0.5 seconds | R5 was flow-level only |
| U4 | Timings and memory on an actual edge board (Raspberry Pi class) | R9 measured a substitute (one server core); no board has been tried; feature extraction from flow records is untimed |
| U5 | Contrastive objectives and the state-space backbone | R6e tried a seed ensemble, a Transformer and a masked-history objective only |
| U6 | One shared model against one per site | R8 skipped; moot if the mesh is dropped |
| U7 | Replayed and malformed directives, and targeted forged directives | R7e is covered only by R12's simulated lying site; R7d and R7f were run on one site (R7df) |
| U8 | Windows rebuilt from the raw data by someone else | Level 4 of the rerun kit not done by anyone |
| U9 | The cost to scan detection of dropping unanswered flows | Not measured (needs retraining on windows built without them) |
| U10 | A live flow follower, a real learning duration, and the product on a real network | Not built or measured (product/README.md) |

Audit qualification: the seed-2 ONNX diagnostic found 41,403 of 99,515 INT8 alert decisions differ from PyTorch at its frozen threshold. Its unchanged-threshold operating point is not deployable evidence. FP32 matched all decisions in that diagnostic but had a maximum score difference of 0.26897, so score equivalence is not claimed.
