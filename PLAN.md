# cyberncm — plan after R1 and R2

Written 2026-11-11. One ordered list of steps, from the two-day demonstration to engineering. This replaces the research list (§8), the claims table (§10) and the headline numbers (§3) in `HANDOFF.md`. The evaluation rules in `HANDOFF.md` §7 still apply.

## 1. Where we are

| Round | Question | Answer |
|---|---|---|
| Prototype | Does a benign-trained model flag unseen attack families? | Yes inside one network: 0.954 family-mean AUC on CIC-IDS2017 under the common scoring rule (the handoff's 0.970 used a different rule). |
| R1 | Does it hold on other networks? | Inside each network yes (0.94–0.99). Across networks no: near chance or inverted in 4 of 6 directions. Thresholds never transfer. |
| R2 | Does it warn before the next attack stage? | No. It detects stages as they happen. Early alerts come from addresses already attacking, and simpler models give the same alerts. |
| Both | Does the sequence model earn its place? | Not yet. Window order adds almost nothing; a random forest on single windows matches it on unseen families. |
| Both | False alarms | Fixed threshold: 33% of benign windows over five weeks. Daily recalibration: 3.5% of windows, about 11% of benign source-hours. |

## 2. Direction

1. **The claim is detection and sharing, not prediction.** Each site learns its own normal traffic and detects deviations; the mesh shares confirmed detections so other sites block sooner.
2. **The model comes first.** Find out how good it can get and collect evidence strong enough to publish. False alarms are the first target.
3. **The mesh has never been measured.** It gets its own rounds after the model rounds, then a decision gate.
4. **Every round is kept**, R3 to R14. Nothing is dropped; the order below puts each where its inputs exist.
5. **Engineering is staged**, so there is always something to show. Full product engineering waits for the gate.

## 3. The order

Do the steps in this order. Steps in the same block can run in parallel between two people; a step never starts before its "needs" are done. Durations are estimates.

### Block A — demonstration (2 days)

| # | Step | Needs | Done when |
|---|---|---|---|
| 1 | Confirm the single-site replay runs from the tarball (Colab cell in §7) | — | `stream.py` writes `demo_events_fri.json` |
| 2 | Agree the event fields: `seq`, `t_ms`, `site`, `type` (`alert`, `block`, `shared_block`, `counter`), `src`, `phase`, `risk`, `truth` | — | Written in `demo/README.md` |
| 3 | Count, per attack day, which victim hosts each attacker hits and when; pick the day where one attacker hits two hosts at different times | 1 | Day chosen, or fallback chosen (see cut lines) |
| 4 | Replay page from `demo/template.html`: load a real event file in place of the example data | 2 | Friday's single-site file plays end to end |
| 5 | `demo/sim_sites.py`: split victim hosts into two sites, windows per site (filter on destination before `prep.windows`), existing model on each, one event file with a `site` field; runs with sharing on and off | 3 | Two event files |
| 6 | Load both files in the page; comparison numbers: seconds to block at site B with and without sharing, attack windows stopped, benign hosts wrongly blocked | 4, 5 | Numbers on the page |
| 7 | Results slide (what was and was not measured), backup video, two rehearsals; freeze at the first clean run | 6 | Rehearsed |

What the demonstration shows: a site's detector, trained only on normal traffic, flags an attacker it never saw and issues a signed block; a second site receives that block; the same replay with sharing off; one honest slide.

Cut lines:
- No day has an attacker hitting two hosts at different times: show two sites that both see the attacker and report how many seconds earlier the slower site blocks. Say it is the same attack seen from two places.
- Step 5 not working by the end of day 1: demonstrate one site, present sharing as the next step.
- No sign-up, database, live traffic, kernel code or deployment.

What to say: recorded lab traffic (CIC-IDS2017), replayed; the detector never saw these attacks in training; blocks are signed and schema-checked; 0.94–0.99 AUC on unseen families inside one network across three datasets. What not to say: predicts, zero-day protection, works on any network, safe to block automatically. The `truth` field is dataset labels: show it as ground truth, never as model output.

### Block B — foundations (2–3 days)

| # | Step | Needs | Done when |
|---|---|---|---|
| 8 | One code folder: unpack `ncm-prototype/` from `mesh-handoff.tar.gz` into `ncm/`, overwrite with `research/R1/code/*.py`, add `research/R2/code/*.py`; extract `IMPLEMENTATION_PLAN.md` to the repo root | — | `python ncm/test_ncm.py` passes from a fresh clone |
| 9 | `requirements.txt`: `torch==2.15.0` (CPU), `numpy==2.5.4`, `pandas==3.1.1`, `scikit-learn==1.9.1`, plus `pyarrow onnx onnxruntime jsonschema cryptography` | 8 | Installs in Colab |
| 10 | Shared Drive folder `cyberncm-data/`, one subfolder per dataset with its `windows.npz`: `cic2017`, `unsw`, `d2018`, `unraveled`, `cicapt`; regenerate any not kept | 8 | All five load from Colab |
| 11 | `ncm/metrics.py`: false alerts per benign host per day; share of benign source-hours with an alert; share of attacking sources alerted within 1, 5 and 60 minutes; attack windows under an active block | 8 | Unit test passes; reproduces R2's 11% of source-hours |
| 12 | Reproduction check: rerun the UNSW in-domain table and one cross run | 9, 10 | Match the READMEs to 0.001 |
| 13 | Point `HANDOFF.md` §3, §8, §10 to this file | — | Merged |

### Block C — baseline evidence (about 1 week)

| # | Step | Needs | Done when |
|---|---|---|---|
| 14 | Scoreboard harness (§4) with v0 and the three baselines on all five datasets, 5 seeds, bootstrap intervals over sources | 11, 12 | `research/SCOREBOARD.md` and `scoreboard.csv` hold the v0 rows |
| 15 | **R10** prior art | — | Related-work table and one paragraph on what is left to claim |
| 16 | Error analysis on the hard set: 20 misses and 20 false alarms per family, inspected by hand | 14 | `research/errors/` |
| 17 | Feature importance, and per-feature drift between days and between networks | 14 | `research/features/` |
| 18 | Evidence pages (stage F2): scoreboard and results on the static site | 14 | Page reads `scoreboard.csv` |

### Block D — improve the model (about 4 weeks)

One change at a time against v0. Order is by expected gain; each later step may use earlier winners.

| # | Step | Needs | Done when |
|---|---|---|---|
| 19 | **R4** alert policy | 14 | Policy table; a winning policy or a statement that none exists |
| 20 | **R6a** history features | 14 | Scoreboard row |
| 21 | **R6b** compare each host to itself | 14, 16 | Scoreboard row |
| 22 | **R6c** unit of scoring | 14 | Scoreboard row |
| 23 | **R6d** scoring function | 20 | Scoreboard rows |
| 24 | **R6f** supervised head | 20 | Scoreboard row |
| 25 | **R11** robust scaling and onboarding without retraining | 19 | Table per adaptation level; shortest learning period |
| 26 | **R6e** training objective and backbone | 20–23 | Scoreboard rows |
| 27 | Independent rerun of every winner from a fresh Colab session, by someone who did not run it | each winner | "Confirmed" in the scoreboard |
| 28 | **R6g** combine the confirmed winners into v1; full scoreboard once on the final splits; ablation table | 19–27 | v1 row and ablations |
| 29 | Replay of v1 against v0 on the same traffic (stage F3) | 28 | Page shows both |

### Block E — stress v1 (about 2 weeks)

| # | Step | Needs | Done when |
|---|---|---|---|
| 30 | **R3** new-source check | 28 | AUC drop on known-source attackers stated |
| 31 | **R7a–c, R7g** mimicry, low and slow, poisoned learning period, text-path review | 28 | Curves; breach log; mitigations rerun |
| 32 | **R14** comparison with language-model approaches | 28, 15 | Comparison table |
| 33 | **R13** prediction by campaign | 28 | Lead-time table at host and subnet level |
| 34 | **R5** sub-second windows from packet captures | 28 | Fastest window that keeps accuracy; v2 row if it wins |
| 35 | **R9** edge hardware | 28 | Timings on a board, or the labelled substitute |
| 36 | Model card and claims ledger | 30–35 | `MODEL_CARD.md`, `research/CLAIMS.md` |

### Block F — the mesh (about 2 weeks)

| # | Step | Needs | Done when |
|---|---|---|---|
| 37 | **R12** what sharing buys | 28, 19, step 5's simulation | Table for 2 and 4 sites |
| 38 | **R7d–f** induced false blocks, forged and replayed directives, spoofed sources | 37 | Curves; breach log |
| 39 | **R8** one shared model or one per site | 37 | Per-site, pooled, federated in one table |
| 40 | **Gate G1** (§6) | 36–39 | `research/G1.md` |

### Block G — engineering

| # | Step | Needs | Done when |
|---|---|---|---|
| 41 | F4: Python agent (flow records → detector → signed directives, shadow mode by default); API; database; console with sign-up, add a site, install command, site dashboard, blocklist | 40 | A stranger can sign up, add a site and see it connect |
| 42 | F5: two agents exchanging directives over HTTP, then gossip; live demo mode, mesh view, admin and audit pages | 41 | Two-node run recorded |
| 43 | F6: Rust agent and kernel filter, consensus, attestation, federated learning | 42, and only if G1 says the mesh is worth building | — |

> **Progress note (2026-11-13, for 14 November 2026 demo):** A minimal two-node cooperative prototype was built under `demo/two_node/` (`node_a.py`, `node_b.py`, `protocol.py`, `policy.py`, `enforcer.py`, `dashboard.html`, `DEMO_RUNBOOK.md`, `WALKTHROUGH_5MIN.md`). Node A replays recorded CIC-IDS2017 Friday windows through the frozen FP32 ONNX model (`ncm_gru64_s0.onnx`) and sends Ed25519-signed v1.2.0 alerts to Node B over localhost HTTP; Node B verifies signatures, schema, freshness, expiry, scope, and replay state, holds mapped alerts (`172.16.0.1 -> 127.0.0.2`) for explicit `human-approved` operator consent (never auto-blocking on remote alerts alone), and enforces a max 30 s userspace TCP connection gate on `127.0.0.1:18080` with real before/during/after HTTP probes. This is a bounded two-process prototype for demonstration; it does not change Gate G1's research verdict (`research/G1.md`), nor does it implement gossip, consensus, federated learning, or kernel filtering.

## 4. The scoreboard and the evidence

Every model change goes through one table.

| Fixed | Value |
|---|---|
| Datasets | CIC-IDS2017, CSE-CIC-IDS2018, UNSW-NB15 (in-domain); Unraveled (five-week campaign); CICAPT-IIoT (detection only) |
| Splits | As in R1 and R2. Dev for every choice; final touched once per reported model |
| Seeds | 5 (0–4) |
| Headline numbers | Family-mean AUC; worst family; false alerts per benign host per day at 80% of attacking sources caught within 5 minutes |
| Hard set, reported separately | Unraveled Lateral Movement (0.79 today) and Establish Foothold (0.90); CIC-IDS2017 Botnet and Infiltration; CSE-CIC-IDS2018 Web Attack - SQL |
| Baselines in every table | Smoothed isolation forest, smoothed token distance, random forest on single windows, and the current model as "v0" |
| Uncertainty | Range over seeds, plus a bootstrap interval that resamples sources, not windows |
| A change is an improvement when | It beats v0 by more than the seed range on the dev split of at least 3 of 5 datasets, is not worse on any, and the gain holds on the final split |

Files: `research/SCOREBOARD.md` (one row per model version, with commit hash) and `research/scoreboard.csv`. Every attempt gets a row, including failures.

Evidence beyond the scoreboard:

| Evidence | Where |
|---|---|
| Protocol written before each run, deviations listed after | `research/<round>/README.md` |
| Ablation table for v1 | `research/R6g/` |
| Error analysis on the hard set | `research/errors/` |
| Feature importance and drift | `research/features/` |
| Related work and comparison with published results | `research/R10/` |
| Breach log from the adversarial rounds | `research/R7/BREACHES.md` |
| Model card for v1 | `MODEL_CARD.md` |
| Claims ledger: every public sentence with the file and commit behind it | `research/CLAIMS.md` |
| Independent rerun of each winner and of v1's headline row | note in `SCOREBOARD.md` |

## 5. The rounds in detail

Every round: seeds 0–4, no retuning on final splits, protocol committed before the first run.

**R3. Is detection just "a new source"?**
- Score only attackers that also have benign history (CSE-CIC-IDS2018 botnet hosts, Unraveled internal hosts, CIC-IDS2017 Friday bots), and rerun with `log_gap` removed.

**R4. How low can false alarms go?**
- Data: Unraveled (five test weeks), then CSE-CIC-IDS2018 and CIC-IDS2017.
- Policies on the same scores: fixed threshold (reference); daily recalibration (reference, 3.5%); rolling quantile over the last 1, 6 and 24 hours; per-source threshold from that source's own history; k of n windows (2 of 3, 3 of 6, 6 of 12); two tiers, alert at the 99th percentile and block only at a higher level sustained for n windows.
- Also run each policy on token distance alone, to see whether the policy or the model matters more.
- Target: under 1 false block per benign host per day while blocking at least 80% of attacking sources within 5 minutes.

**R5. Do sub-second windows work?**
- Features from packet captures (CIC-IDS2017 pcaps, about 52 GB; start with one attack day), adding byte entropy, TLS fingerprint and DNS failures.
- Window sweep: 0.05, 0.5, 1 and 5 s. Report AUC, the false-alarm metric and time to first alert.
- One day's pcap is 8–13 GB: stream it from Drive and keep only the feature windows.

**R6. Which model?** One change each against v0.

| Round | Change | Why a gain is expected |
|---|---|---|
| R6a | Running averages of the 32 features over 1 min, 10 min, 1 h, in place of or beside the GRU | R2: history helps (+0.12 to +0.17 on two stages), order does not |
| R6b | Normalise features by the source's own recent history and by hour of day | Benign traffic drifts and differs by host role |
| R6c | Score per source-destination pair and per source-service, beside source alone | Lateral movement is a per-destination pattern |
| R6d | Vocabulary 128 / 512 / 2,048; nearest-neighbour distance; Gaussian mixture; autoencoder; drop or stabilise the next-context surprise (0.44–0.98 across seeds today) | Token distance carries most of the signal |
| R6e | Masked-window and contrastive objectives; GRU against Transformer and state-space model at equal size; seed ensemble | Tests whether the neural part can earn its place |
| R6f | Gradient-boosted trees on window plus history features; known attack families as negatives for the anomaly score | The random forest already ties the full model |
| R6g | Combine the winners into v1 | — |

Rule fixed now: if history features without the GRU are within 0.01 family-mean AUC of v0 on every dataset and no worse on the false-alarm metric, the GRU is removed.

**R7. Can it be fooled, and what do we do when it is?**

Prompt injection does not apply: the model reads 32 numbers, never text, and its output is a schema-checked structure. Attackers can still manipulate the numbers, the learning period and the sharing. Run on v1 and v0, on CIC-IDS2017 and Unraveled.

| Test | How to run it | Breached when | If breached |
|---|---|---|---|
| R7a Mimicry | Move attack windows' features 25, 50, 75 and 100% toward the benign mean, only for features an attacker controls. Then search for the smallest change that drops the score under the threshold. | Detection of a family falls below half at a change of 50% or less | History and per-host features; train the supervised head on mimicked examples; ensemble with a plain statistical score; weight features an attacker cannot cheaply change |
| R7b Low and slow | Re-space an attacker's flows 10×, 100× and 1,000× slower before windowing. | A family caught at normal speed is missed at 100× | Longer history (6 h, 24 h); a per-source cumulative score that does not decay; state the slowest attack still caught |
| R7c Poisoned learning period | Mix 0.5, 1, 2 and 5% attack windows of one family into the benign training span. | Detection of that family falls below half at 2% or less | Learn only from an owner-confirmed clean period; trim the most unusual 1–5% of training windows; alarm on sharp shifts at refit; compare old and new model for a day before switching |
| R7d Induced false blocks | Add attack flows to a benign source's windows at 1, 5 and 20% of its traffic. | A benign host is blocked at 5% or less | Block the source-destination pair, not the source; require a completed handshake; protected prefixes; rate-limit first; require a second site to agree |
| R7e Forged and replayed directives | In the R12 simulation one site issues signed blocks for random benign addresses; replay old directives; send malformed ones. | Any is applied at an honest site under the two-site rule | Timestamp window and sequence numbers; lower the site's weight per uncorroborated block; cap blocks per site per hour; evict |
| R7f Spoofed sources | Rewrite the source of attack flows to an uninvolved host (UDP and unanswered TCP only). | The uninvolved host is blocked | Count only flows with a completed handshake; never share a block based on unanswered traffic alone |
| R7g Text reaches a decision | Review: list every component that reads packet content or free text. Today the answer must be none. | Any path from packet text to a directive exists | Remove it. A future language model gets feature numbers only, and its output passes the same schema check |

Rules: each test runs at increasing strength until it breaks the model or reaches the top level, giving a curve. Every breach is logged with the mitigation tried and the curve after it. A mitigation counts only if the clean scoreboard numbers do not get worse beyond the seed range. Breaches that remain become stated limits in the model card and "must not claim" entries in the ledger.

**R8. One shared model, or one per site?**
- R12's virtual sites and the three R1 networks as sites: per-site model; one model on pooled benign data; federated averaging with each site keeping its own normalisation, vocabularies and thresholds.
- If R6 removes the GRU, this becomes "does pooling vocabularies help", a one-day test.

**R9. What does it cost on real edge hardware?**
- v1 as INT8 on a Raspberry Pi class board: latency per batch, memory, output parity. Without a board, a throttled single-core container, labelled as a substitute.

**R10. What is already published?**
- Systems that combine shared alerts, consensus on block rules and attested federated learning; per-network anomaly detectors with cross-site sharing; published results on our datasets, noting where protocols differ.

**R11. Can a new site start without retraining?**
- For each of the 6 train → test directions from R1, four levels using the target's benign data only: threshold only; plus refit feature normalisation (also try quantile scaling); plus refit both vocabularies and the calibration; full retraining.
- Learning curve for the best cheap level: 10 minutes, 1 hour, 6 hours, a full day of target benign data.
- The shortest period within 0.02 of full retraining becomes the shadow-mode duration in the product.

**R12. What does sharing buy?**
- Virtual sites: split victim hosts into 2 and 4 groups; each site sees only its own hosts' flows and runs its own detector.
- Data: CSE-CIC-IDS2018, CIC-IDS2017, Unraveled.
- Compare: no sharing; share every block at once; act only when 2 sites agree; 30-second expiry against no expiry. Then add one lying site.
- Report: time from an attacker's first packet at a site to its block there; attack windows prevented; benign hosts wrongly blocked at sites that detected nothing themselves; damage from the lying site.

**R13. Prediction, second attempt: follow the campaign, not the address.**
- Score by victim host and by subnet: after a stage is detected anywhere, does risk rise on the hosts the campaign touches next, before their first attack window?
- Same controls as R2. One campaign and a handful of onsets: this can show an effect is absent or worth pursuing, not prove one.

**R14. How does it compare with language-model approaches?**
- Measure, on the scoreboard datasets: a small open LLM given each window as text, zero-shot and few-shot; the same LLM fine-tuned on the leave-one-family-out split if Colab's free GPU allows; one published traffic model with released weights if one runs (candidates to check in R10: ET-BERT, netFound, NetVAD).
- Report beside v0 and v1: family-mean AUC, worst family, the false-alarm metric, model size, time per window, hardware needed.
- Put instruction text into the fields an LLM detector reads and record whether its verdict changes.
- Same windows, splits and threshold procedure; state that the LLMs see features as text, not raw packets.

## 6. Gate G1

| Question | Evidence | If no |
|---|---|---|
| Is there an alert policy a real network could tolerate? | R4 on v1 | The product alerts and never blocks on its own |
| Does sharing help more than it harms? | R12, R7d–f | Single-site detector; drop the mesh, consensus and federation |
| How long must a site learn before enforcing? | R11 | — |
| Which detector ships? | R6g, R7 | — |
| Shared model or per-site? | R8 | — |

## 7. Working on Colab (removed from the public copy: private working instructions)
## 8. Front end

`demo/template.html` is the design template: one static file with the colour and type tokens for light and dark, the components, and a working replay player on example data. Build every stage from it.

| Stage | Pages | Data source |
|---|---|---|
| F1 (steps 4–6) | Replay: two site panels, shared-block link, sharing on / off, event table | Event files from `stream.py` and `sim_sites.py` |
| F2 (step 18) | Evidence: scoreboard, per-dataset results, hard set, claims | `research/scoreboard.csv` |
| F3 (step 29) | v1 against v0 replay; false alarms per host per day | Event files from v1 |
| F4 (step 41) | Console: sign-up, add a site, install command, site dashboard, blocklist | API |
| F5 (step 42) | Live demo, mesh view, admin and audit | API |

To use the template: replace the two `EXAMPLE_*` arrays with `fetch()` of real event files; keep the tokens and component classes; move to Next.js at F4 by lifting the `:root` token blocks into the global stylesheet unchanged.

Requirements from F1 on: works by keyboard; status shown by text and shape, never colour alone; animation respects reduced-motion; layout works at 360 px; ground truth is always labelled as ground truth.

The rest of the engineering design (API routes, data model, enrolment, blocklist distribution, security) is in `IMPLEMENTATION_PLAN.md` §3–§22. Read it with two corrections: the claim is detection and sharing, and every site has a learning period before it may enforce.

## 9. How we work

- **Branches:** `<yourname>/<round>-<name>`. Someone else reviews every pull request. Nothing goes to `main` unreviewed.
- **Shared files** (`ncm/metrics.py`, `ncm/evaluate.py`, the scoreboard harness) change only in a small pull request of their own.
- **One folder per round:** `research/<ID>/` with `README.md`, `code/`, `results/`.
- **README shape, as in R1 and R2:** answer in five lines; method; results with ranges; evidence limits; reproduce.
- **Protocol first:** commit the method and decision rule before running. Later changes go under "deviations".
- **Negative results are results.** R1 and R2 were both negative and both moved the project.
- **A winner is confirmed only after someone else reruns it.**

## 10. What we can say now

| Supported | Not supported |
|---|---|
| A model trained on one network's benign traffic flags unseen attack families on that network at 0.94–0.99 AUC, on three public datasets | Any form of "predicts" or "blocks before the next stage" |
| It fits in 374 KB and runs in under a millisecond per batch on one CPU core | "Works on a new network without a learning period" |
| It detects multi-stage campaign activity while it happens (Unraveled, 0.79–0.999 per stage) | "Safe to block automatically" — false alarms are 3.5% of windows at best so far |
| A fixed threshold is unusable over weeks; per-network calibration is required | Any benefit from the mesh, consensus or federated learning — unmeasured |
| It cannot be steered by text in packets, by design | Any comparison with language-model detectors — unmeasured until R14 |
| | Any figure from the original architecture report |

## 11. Risks

1. R4 may find no tolerable policy. Then the product alerts and never blocks, and R12 measures shared alerts.
2. R12 uses lab datasets where one attacker hits several victims; real cross-organisation attacks may overlap far less. State this beside every R12 number.
3. Unraveled is one campaign. Use it for the long-duration false-alarm test, not for detection-rate claims.
4. Many rounds against five small datasets invite overfitting to them. The final-split rule and the independent rerun are the guard; do not relax them.
5. Shared Drive folder: keep to the output-folder rule or checkpoints will be overwritten.
