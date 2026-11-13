# Model card: v0 (also v1)

Plan step 36. This card describes the detector as measured in `research/`. **v1 is v0**: no change tried in rounds R6a to R6f passed the improvement rule (`research/V1/README.md`). Every number below has a file and a commit behind it in `research/CLAIMS.md`. Nothing here has been reproduced by someone other than the author yet (plan step 27; the kit for it is `research/RERUN/`).

## What it is

An unsupervised detector of unusual behaviour per source address. Flow records are cut into 5-second windows per source; each window is 32 numbers (counts, timing, TCP flag ratios, packet and byte statistics, fan-out; no payload, no text). A 2-layer GRU (hidden size 64, 96,070 parameters, about 778 KB as FP32 ONNX; experimental INT8 export about 374 KB) summarises each source's recent windows. The score is the distance of the window to the nearest of 512 learned "normal behaviour" centres, plus the distance of the GRU state to the nearest of 512 learned normal states, plus half of two next-window surprise terms, each standardised on a calibration period and smoothed per source (`ncm/ncm.py`, `HANDOFF.md`). It is trained on a site's benign traffic only and has never seen an attack label.

## Deployment status after the 13 November audit

FP32 ONNX is the deployment candidate for shadow-mode evaluation; INT8 is experimental and must not inherit FP32/PyTorch thresholds. In the recovered CIC-IDS2017 seed-2 audit, FP32 preserved the tested alert decisions while INT8 changed 41,403 of 99,515 test decisions at the reference threshold. AUC alone does not establish deployment parity. The stage/hazard head and complete replay policy were not validated by that comparison. Automatic blocking remains out of scope.

The streaming replay uses frozen model parameters and calibration, with no automatic learning from incoming traffic. Offline retraining/refitting requires an owner-reviewed dataset and evaluation before model adoption; this operational procedure is not an experimentally proven poisoning mitigation. See `research/audit/README.md` for results and remaining checks.

## Intended use

- **Alerting and shadow mode:** show which sources look unusual compared with this site's own normal behaviour, and what would be blocked, without blocking.
- **Per-site setup:** the normalisation, both centre sets and the calibration are refitted on the site's own normal traffic (`research/R11/README.md`); a fixed threshold carried from another network or another period is not usable (`research/R2/README.md`).

## Out of scope: do not use or claim

- **Automatic blocking.** No alert policy tried reaches 80% of attacking sources caught within 5 minutes with fewer than one false alert per host-day on a five-week campaign (`research/R4/README.md`); false alarms are 3.5% of windows at best under daily recalibration (`research/R2/README.md`).
- **Prediction** of the next attack stage, or blocking "before the next stage" (`research/R2/README.md`: the attacker was flagged in the hour before 1, 1 and 2 of 6 testable stage onsets).
- **Sharing blocks between sites,** a mesh, consensus or federated learning: in simulation it speeds the first block but spreads false alerts to other sites and a lying site is not stopped (`research/R12/README.md`, merged).
- **Learning from traffic that may contain an attack:** a few percent of one attack family's windows in the first day makes that family undetected (`research/R7/README.md`, `research/R7m/README.md`).
- **A stated learning period.** 10 minutes of normal traffic was enough in lab data, but that is the lab minimum; the real shadow-mode duration is unmeasured (`research/R11/README.md`).

## Performance (final split of each dataset; mean over 5 seeds, range in brackets)

| Dataset | Family-mean AUC | Worst family AUC | False alerts per benign host-day at 80% of attackers caught in 5 min (a best case) |
|---|---|---|---|
| CIC-IDS2017 | 0.954 (0.942 to 0.966) | 0.861 | 12.1 |
| UNSW-NB15 | 0.942 (0.941 to 0.944) | 0.938 | 3.0 |
| CSE-CIC-IDS2018 (10% of sources) | 0.989 (0.988 to 0.991) | 0.982 | 0.24 |
| Unraveled (five-week campaign) | 0.894 (0.884 to 0.899) | 0.760 | 13.5 |
| CICAPT-IIoT (detection only) | 0.697 (0.637 to 0.756) | 0.654 | 8.7 |

Source: `research/SCOREBOARD.md`, `research/scoreboard.csv`. The false-alert figure sets its threshold with the split's own labels (a best case) and rests on 2 to 11 attacking sources per dataset.

**Against simple baselines:** v0 beats token distance alone clearly only on Unraveled (0.894 against 0.857); on three datasets the gap is at most 0.003, and it loses 0.14 on CICAPT-IIoT (0.697 against 0.833). A random forest trained without the test period (benign day 0 plus other families' dev attacks, a supervised model that needs labels) is ahead on CIC-IDS2017 (0.974), UNSW-NB15 (0.961) and CICAPT-IIoT (0.891) and behind on CSE-CIC-IDS2018 (0.882) and Unraveled (0.647). Several changes were tried and none passed (`research/R6a` to `R6f`, `research/V1`); the GRU earns its place on one dataset, Unraveled.

**Cost (substitute measurement, one pinned core of a cloud CPU, not an edge board):** the scoring step takes 0.44 to 0.45 ms for a batch of 64 sources as INT8 (374 KB; 778 KB as full precision), with 512 bytes of state per tracked source, about 51 MB for 100,000 sources. Feature extraction from flow records is not included. INT8 and full precision differ slightly (test AUC between -0.0003 and +0.0111 on four runs) (`research/R9/README.md`).

**Campaign activity:** on Unraveled, stages are detected while they happen at 0.79 to 0.999 AUC per stage (`research/R2/README.md`).

## Behaviour on specific cases

- **Attackers already on the network (with benign history):** AUC 0.953, 0.993 and 0.830 on CIC-IDS2017, CSE-CIC-IDS2018 and Unraveled (6, 10 and 3 attacking sources); not dependent on the "gap since last window" feature (`research/R3/README.md`, merged). On Unraveled these are much harder than new sources (0.83 against 0.998).
- **New benign sources:** windows from sources never seen on the training day were above the alert threshold 92% (CIC-IDS2017) and 94% (Unraveled) of the time, so a new device is likely to raise alerts (same file).
- **Drift:** in the final weeks of Unraveled, 46% of windows from known benign sources exceed the day-0 threshold; a fixed threshold is unusable over weeks (`research/R3/README.md`, `research/R2/README.md`, `research/R4/README.md`).
- **Text and packet content:** the model reads no payload and no free text, and no path from packet text to a decision or directive exists in the code reviewed (`research/R7/R7g.md`).

## Known weaknesses (stress tests, `research/R7/README.md`)

- **Poisoned learning period (breach):** 6 of 20 testable families lose detection when 0.5% to 2% of their windows are in the first day. Trimming the most unusual windows before refitting does not fix it under the pre-set rule (`research/R7m/README.md`, merged). The practical defence is a process one (learn only from a period the owner has confirmed clean), which has not been measured.
- **Mimicry:** one of 27 families breaches under the simple test; the tests are weak and the model leans on features the attacker does not control (`research/R7/README.md`). Do not claim robustness to a determined imitator.
- **Low and slow:** none of the families on CIC-IDS2017 is missed when the attack is slowed 100 times; slower attacks look more unusual to this model (same file).

## Data and limits of the evidence

- Public lab datasets with injected attacks and few attacking sources (2 to 11); CIC-IDS2017, UNSW-NB15 (features partly approximated), CSE-CIC-IDS2018 (10% of sources), Unraveled (one multi-week campaign, mixed hardware for the training runs), CICAPT-IIoT.
- No real production network, no daily or weekly traffic cycle beyond Unraveled's five weeks, no live deployment.
- Results are from one author's runs; independent confirmation (plan step 27) is pending.
- Partly measured: language-model detectors (R14, one small model on CPU, far below v0 and injectable), campaign following (R13, no signal, tiny sample), windows shorter than 5 seconds (R5, flow level only: shorter windows alert sooner and lose accuracy), backbone and objective alternatives (R6e: none beats v0), edge cost (R9, a server core as a substitute for a board).
- Not measured: fine-tuned or larger language models and published traffic models, packet-level features, a contrastive objective and the state-space backbone, one shared model against one per site (R8, skipped), an actual edge board, the cost to scan detection of dropping unanswered flows.
- Single-site product: `product/` is a first slice in shadow mode only; see `product/README.md` for its limits.
