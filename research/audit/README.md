# Research audit continuation — 13 November 2026

Working notes for the research audit of 13 November 2026. Reviewer notes and local checkout paths are not published.

## Recovered cloud results — latest update

Drive reauthorization succeeded. Both previously disconnected jobs completed and their output files survived. The all-family CIC-IDS2017 seed-0 poisoning run contains 15 families and 75 points; its log ends with the output-write message. Botnet detection: clean 0.79121, .005 poison 0.02568, .01 0.00141, .02 0.00375, .05 0.00084. This reproduces the broad collapse, not every rounded historical zero; small nonzero values and nonmonotonicity remain visible.

Stored R9 seed-2 exports were compared against their matching checkpoint and canonical windows. FP32 maximum raw-score error is 0.26897, yet test AUC is 0.971993691 versus PyTorch 0.971993693 and there are zero alert disagreements among 99,515 test windows at the reference threshold 3.46410. Its numerical outlier cause still needs isolation. INT8 test AUC is 0.976180205, but 41,403 decisions differ at that same reference threshold; it is not a drop-in replacement. Recalibration and a separate held-out evaluation would be required before deployment. These measurements do not constitute independent review or edge-hardware verification.

Compact results: results/recovered_cloud_summary.json. Full outputs and logs remain in Drive/cyberncm-data/audit_20261113. The earlier disconnection status below is historical; collecting these two results is now complete. Remaining UNSW, Unraveled, Portscan, scoreboard/bootstrap, R12b and independent-review work is still outstanding.

## Historical status at session close

Core reporting/AUC/checker fixes, deterministic timestamp recovery, and budget-aware R11 instrumentation are implemented and tested. Draft remains unmerged.


Still outstanding: finish/collect the two jobs; original-code rebuild under pinned pandas to isolate version effects; UNSW poisoning diagnosis; real Unraveled hourly/multi-day curve; spoof-mitigation Portscan cost; historical tie-aware scoreboard/bootstrap recomputation; all 72 R12b sensitivity runs with rule-0 comparison; independent human review. These are research validation work, not completed claims. No further cloud jobs were launched after the connection loss.

R11 chronology instrumentation passed a local end-to-end synthetic smoke run: final evaluation occurs after the train span, a sparse 10-minute budget is explicitly skipped, a 24-hour budget completes, and hourly counts sum to the actual fit plus calibration population. This verifies the instrumentation, not real-world adaptation performance. Log/results are outside Git at <local run directory>

## Verified corrections

1. R12b reporting failed open: an empty directory produced a negative mesh verdict. It now writes INCOMPLETE first and requires the declared 72-run grid, matching metadata, valid nonempty attacker populations, and defined rates before producing conditional results. The original post-R12 thresholds remain unchanged and explicitly exploratory.
2. Weighted AUC in ncm/scoreboard.py broke ties by row order. It now uses tie-aware weighted roc_auc_score. Historical weighted-bootstrap intervals using this function require recomputation; point estimates use roc_auc_score and are unaffected; this audit has not silently replaced them.
3. The headline rerun checker printed FAIL but exited successfully. It now exits nonzero on a failed check.
4. Poisoning diagnostics now record actual injected fit/calibration counts and effective fractions. They explicitly state that the backbone is frozen and the threshold is calculated from original calibration rows. Added an optional one-family poison run for diagnosis; default all-family behavior remains.

## Actual local checks and runs

- R12b reporting: complete synthetic input passes; empty, missing run, unexpected seed, mismatched metadata, zero denominator, and empty attacker population cannot produce a verdict (two unittest methods, six invalid-input subcases).
- Weighted AUC: tied-row permutations, a hand-calculated weighted example, and an absent weighted class pass (three tests).
- Window comparison: shuffled matching rows compare equal; one changed feature row is detected (one test).
- Existing ncm/test_ncm.py: all checks passed.
- Fresh training through ncm/train.py: GRU-64, seed 7, 20,927 training windows, 653 chunks, 30 epochs, validation loss 4.9879. Separate disposable model directory; no historical checkpoint overwritten.
- Fresh headline check: dev family-mean AUC 0.985, final 0.957, both within the committed ranges; process exit 0. This uses the local 125,674-window dataset, not a verified raw rebuild. Not an independent reviewer confirmation.
- One-family frozen-backbone poison diagnostic, new seed 7 / Botnet: final detection 0.8515 at 0 poison; 0.0376 at requested .005; 0.1208 at .01; 0.0027 at .02; 0 at .05. Nonmonotonicity is reported, not smoothed away. Different seed/model run from the historical seed-0 claim; not evidence about UNSW immunity. Effective contamination and cap counts are in the JSON.
- Local original and upload-copy CIC-IDS2017 files are byte-identical, with 125,674 windows: day 0 26,159; day 1 26,523; day 2 25,179; day 3 23,361; day 4 24,452. Common keyed rows have no feature or label differences. The 125,577 and 125,909 rebuilt artifacts are not available locally; mismatch cause remains unresolved.
- GitHub PRs 4–34: 31 total, 23 merged, eight open, zero reviews/comments at inspection. The pasted handoff incorrectly said all 31 were merged. No review requests or messages sent.

Small outputs are in results/. Dataset/model blobs remain outside Git in <local run directory>. Environment used existing Python 3.12, NumPy 2.5.4, PyTorch 2.15.0+cpu, pandas 3.1.1 and scikit-learn 1.9.1.

## Remaining work, not claimed complete

| Item | Current status / input needed |
|---|---|
| Three CIC-IDS2017 counts | Need raw inputs and both rebuilt artifact variants; compare day/source/time keys with compare_windows.py |
| R11 real-day/night learning curve | Need Unraveled windows/checkpoint and fixed chronological budget protocol |
| R7c UNSW resistance | Instrumentation ready; need correct scoreboard UNSW checkpoint and stored reference outputs |
| Spoof mitigation versus Portscan | Need raw/cache flow files and original mitigation script from the appropriate branch |
| ONNX/INT8 discrepancy | Need R9 seed-2 export and matching checkpoint; local older seed-0 artifacts are not equivalent |
| Fresh training rerun kit | Completed locally, seed 7; exact cold cloud installation still untested |
| R7c rerun kit | One-family new-seed diagnostic completed; original all-family seed-0 command still needs exact scoreboard artifacts |
| R12b sensitivity reruns | Need per-site prepared windows, checkpoints and original R12 outputs. Rule-0 comparison and threshold review remain prerequisites for a gate interpretation |
| Independent review | Still requires another person; author-run reruns do not satisfy that requirement |

## Full-backbone poisoning follow-up — 13 November 2026

Completed the previously pending single-family full-backbone run locally. CIC-IDS2017, GRU-64 seed 7, requested poison 0.005 of original day-0 count: 131 injected windows, of which 99 fit and 32 calibration. Poisoned training completed 26 epochs; both models were scored on the same 2,259 remaining final Botnet windows after excluding original rows selected for injection.

| Measure | Clean full training | Poisoned full training |
|---|---|---|
| Botnet final detection at each model's 99th percentile calibration threshold | 0.84949 | 0.01239 |
| Benign-window false-alarm rate, final split | 0.09302 | 0.02382 |
| Botnet-versus-benign AUC, final split | 0.94601 | 0.82250 |

Both use complete respective calibration populations; the poisoned one includes injected calibration rows. Therefore this differs from the frozen-backbone R7c threshold convention (original calibration rows only). Do not treat the two as a controlled backbone-only ablation. This is one seed/family/rate sensitivity run, not evidence about UNSW, broad poisoning tolerance, or independent confirmation. Poison is sampled using known attack labels, including final days, then selected original rows are excluded: this is an oracle stress construction, not a clean prospective generalization experiment.

Preparation/evaluation scripts and small outputs are preserved alongside the audit. Scripts currently record the explicit D-drive paths used; adapt paths deliberately for a cloud rerun. Models remain outside Git.


## Live Drive audit: timestamp recovery depends on file order


Using unchanged historical `prep.py` in the current Colab environment reproduced **125,909** windows. Monday through Thursday match all canonical `(src,t)` keys and counts; Friday has 24,687 versus 24,452 canonical windows, with 999 canonical-only and 1,234 rebuilt-only keys.

Permuting only the three Friday original parquet files produced totals **125,909; 125,780; 125,911; 125,810; 125,674; 125,668**. Morning then DDoS then PortScan matches every canonical Friday key. This establishes that ambiguous equal-wait matches in `recover_time` were resolved by input order. It explains the 125,909 versus 125,674 count difference without invoking a model change. It does not yet explain R5's 125,577 or prove feature/label equality from matching keys.

Fix: choose shortest wait, then earliest implied start minute, explicitly and deterministically; also sort input filenames. The tie rule is a convention, not evidence of the true missing hour. Opposite Friday file orders both yield 24,446 windows under this policy (199 canonical-only and 193 rebuilt-only keys); other days need the same policy audit before declaring a new total. Historical datasets, metrics, and checkpoints are preserved. Any newly versioned dataset requires retraining and downstream reruns, rather than substituting it into old tables.

Regression: `python research/audit/test_time_recovery.py` passes all 24 candidate-row permutations, preserving shortest-wait precedence and unmatched-row exclusion. Small measured results are in `results/friday_order_audit.json`; detailed cloud outputs remain in the new Drive `audit_20261113` folder. Rebuild scripts are saved here; cloud notebook paths must be prepared as described in their inputs.

### Pinned-environment follow-up


A complete raw rebuild with the explicit earliest-minute tie convention finished successfully under the pinned core packages: Monday 26,159; Tuesday 26,523; Wednesday 25,179; Thursday 23,270; Friday 24,446, total **125,577**. This equals R5's reported count, but equality of counts alone does not prove that its features or rows were identical. The historical implementation under these same package versions still needs comparison to separate pandas-version effects from the explicit tie rule. The new artifact is saved separately as `audit_20261113/fixed_policy_windows.npz`; the canonical file is untouched.

The original all-family CIC-IDS2017 seed-0 R7c command is running against its scoreboard checkpoint. Partial Botnet output: clean 0.79121; requested .005 0.02568; .01 0.00141. Completion and full JSON are required before calling the whole command reproduced. A stored-export parity runner is ready for the exact R9 seed-2 artifacts. R11 now accepts explicit additional budget minutes and records fit/calibration windows, sources, observed elapsed span and skipped budgets, preserving the original default budgets.

Standalone diagnostic commands (use a disposable work directory on Colab/Linux for the symlinks):

```bash
python research/audit/rebuild_count_audit.py /absolute/path/prep.py "$DATA" /content/count-audit /content/count-output
cd /content/count-audit
python /absolute/path/friday_order_audit.py /absolute/path/prep.py "$DATA" /content/friday-orders.json
```

The specified preprocessing source hash is recorded by the count runner. To reproduce the historical bug, supply the old `prep.py` revision deliberately; running the corrected source demonstrates the corrected policy instead. `onnx_parity_audit.py` needs `ncm.py` and `export.py` importable (for example, `PYTHONPATH=ncm`), then accepts windows, matching checkpoint, stored FP32, stored INT8, and new JSON output paths in that order. It reports both numerical errors and operational/AUC disagreement, without retroactively choosing a pass threshold.


## Deployment follow-through

Replay now requires the checkpoint's FP32 `.onnx` export and refuses an INT8-only directory. INT8 generation remains an offline experiment. Verified Python compilation and a focused path-selection smoke check: missing FP32 fails before checkpoint loading; when both exports exist, session creation receives FP32. Session creation was mocked, so this check is not a full replay or a hazard-head parity test.

The inspected `ncm/stream.py` has no training/refitting path; weights, codebooks, normalization and calibration remain fixed during replay. Documentation now explicitly requires owner review of offline learning data and evaluation before adopting model changes. This is an operating requirement, not a newly implemented approval service or proven poisoning defense. No training job or deployment was started, and no main merge performed.


## Full FP32 replay validation

Completed offline Friday replay with the matching historical prototype seed-0 checkpoint/export and canonical windows, in <local run directory> Process exit 0: 24,452 windows, 2,201 directives/events (678 rate-limit, 1,523 quarantine), 7 protected-prefix suppressions. A verification rerun validated every directive schema and Ed25519 signature, contiguous sequence numbers, event count, and unchanged checkpoint/export SHA-256 hashes. Small evidence: results/fp32_replay_verification.json. Reproduction helper: verify_replay.py, run from the disposable replay directory with stream.py/ncm.py, schemas/, data/windows.npz and artifacts/ncm_gru64_s0.pt plus .onnx present; it writes only replay outputs and verification.json. It captures the ephemeral public key in memory; no private key is saved.

This closes the full-replay execution check, not the deployment-safety question. Simulated active-quarantine coverage was 43.5% of attack windows and 6.33% of benign windows. First quarantines before attack onset are false/early alerts, not prediction evidence. The historical prototype checkpoint differs from the scoreboard seed-2 parity experiment. No live firewall rule was applied, no online learning occurred, and no production deployment is approved by this run.


## Review corrections

Findings from an internal review of the audit branch were addressed as listed below. This was an internal review, not the independent-human reproduction required by the research plan.

- B1/B2: restored explicit historical INT8 replay table labels, separated the FP32 Friday result, and removed general deployable-INT8/0.001-AUC claims from the touched handoff, model card, README and claims ledger. Historical server timings are not an edge-board benchmark.
- B3: stream.main now returns computed coverage counts; verify_replay.py independently reconstructs coverage from generated events/directives and source/window labels, with assertions against replay accounting. Actual Friday result: 1,210/2,784 attack windows (43.4626%) and 1,372/21,668 benign windows (6.3319%); 24,452 total, 2,201 directives. Full signature/schema verification passes again.
- S2: explicitly versioned the corrected tie-policy dataset as cic2017-earliest-minute-v1, distinct from the canonical 125,674-window artifact. The 125,668 figure is now labelled a Friday-only counterfactual; the complete corrected rebuild is 125,577. New-version hash/provenance collection remains open. Do not replace canonical data under old results.
- S3: only weighted-bootstrap intervals use wauc; point estimates already use roc_auc_score and are unaffected.
- S5: full-poison preparation now takes SOURCE_NPZ RUN_ROOT; evaluation takes RUN_ROOT and resolves ncm relative to the repository. Parameterized evaluation reproduced the existing results.
- S6: prefer the threshold-free Botnet AUC change 0.9460 to 0.8225 when summarizing the one-seed, one-family, oracle-poison full-backbone experiment. Detection 0.8495 to 0.0124 uses different thresholds (3.2765 to 3.9419), with benign false-alarm rates 0.0930 to 0.0238. Both measures must retain these qualifiers.
- S8: R11 decision tables discover computed budgets, support Unraveled names, and say available seeds rather than assuming five. A synthetic end-to-end report-generation test verifies 1,440/4,320-minute columns appear.


## Recovered raw evidence and follow-up status — 13 November

Nine original JSON/log files from the Drive audit folder are preserved byte-for-byte under `results/cloud_raw`, with SHA-256 manifest. The separately stored corrected windows artifact has SHA-256 `034fb41a424635e1827e672e6378991c2307e120c12b4d8f7b4a441a5dd24ca4`; its bytes remain on Drive rather than Git. Counts in the earlier transcribed summary can now be checked against the raw rebuild log. Canonical windows remain unchanged.


Current follow-ups: R11 seed-0 multi-day adaptation (10, 60, 360, 1440 and 4320 minutes) and R7 UNSW seed-0 all-family poisoning are running in a separate Colab child environment. They are not completed results and are not part of the frozen demo claims. Exact reviewed source hashes, commands and environment are retained in Drive `followup_20261113_01`. No R12b sweep is running.

## Focused FP32 outlier diagnosis

The original seed-2 checkpoint and stored FP32 export were downloaded in bounded chunks and their SHA-256 hashes match the earlier full parity audit. A local Python 3.12 diagnostic replayed only the 5,365-window sequence containing row 57,227. PyTorch chose token 438; ONNX chose token 94. Their float64 direct squared distances from the normalized input are 0.464505859995 and 0.464506583953 (margin about 7.24e-7). The previous-state token negative log probabilities differ by about 0.8038, producing an approximately -0.269 score shift after calibration. The observed score change agrees to about 1e-5; ONNX versus PyTorch streaming hidden-state difference at that row is only 2.68e-7. This supports a numerically sensitive nearest-token boundary as the cause of this outlier, rather than substantial recurrent-state drift.

Evidence: `results/fp32_outlier_diagnostic.json`; reproducer: `diagnose_fp32_outlier.py WINDOWS CHECKPOINT STORED_FP32_ONNX OUT`. The local reference score differs slightly from the earlier cloud result; input/model hashes are identical, Python/platform differ. This is one targeted sequence, not a new full parity run, a fix, or proof that every outlier has the same cause. No model/export was changed. Any tie-tolerance or distance-kernel change requires versioning, recalibration and downstream validation before adoption.

## Completed UNSW poisoning follow-up (one seed)

The frozen-backbone UNSW seed-0 run exited successfully and saved all 9 families x 5 requested dose settings (including clean). All recorded dev/final thresholded family detection fractions are 1.0 in this particular run. This is not AUC and does not establish poisoning robustness: no benign false-positive rates or AUCs were collected by this script; eight families have at least one pool-capped dose; rare Worms reaches only 0.0254% effective day-0 contamination despite a requested 5%. The largest effective day-0 contamination across families is 4.7619% (requested 5% relative to the original population), not 5% of the augmented population. The code refits normalization, centre sets and calibration with a frozen backbone; its 80/20 time boundary is recomputed after injection. It samples attack-labelled future windows and excludes originals selected for injection, so this remains an oracle stress construction, not a prospective adversary trial.

Raw result, log, command, environment, source hashes, input hashes and evidence SHA-256 manifest are in `results/cloud_followup/`. Input hashes were collected after these read-only jobs were launched, not asserted as before/after invariance checks. Source archive is retained on Drive. This author-run follow-up is not an independent-human reproduction. It does not alter historical multi-seed tables. R11 multi-day adaptation is still running separately and will be recorded only after completion.

## Final follow-up completion

Both free CPU follow-ups have now exited successfully. All six R11 spans and thirteen model evaluations are present; the earlier running notices are historical. See `FOLLOWUP_REPORT.md` for measured results and limits, and `results/cloud_followup/completion.json` for observed exit status. The generic R11 reporting script generated all multi-day columns against the matching seed-0 target reference; its single-run learning-period wording must retain the report's chronology and generalization caveats.

## Bootstrap regeneration in progress

The five original seed-0 scoreboard runs use 200 source resamples for each of three unsupervised models, in model/split order. `recompute_bootstrap.py` uses the corrected scoreboard functions and identical RNG order, checks each point AUC against the original to three decimals, saves split checkpoints, and checks input hashes before/after. It never overwrites old results. `run_bootstrap_batch.py` limits execution to two child jobs with one CPU thread each. Cloud output folder: `cyberncm-data/validation_20261113_02`. Local command needs `ncm/` on PYTHONPATH; the cloud archive places its library files alongside the runner. Published intervals will be patched only after validating the completed grid; point estimates and seed ranges will stay unchanged.

## Bootstrap regeneration completed

All five datasets exited 0; all 30 model/split point checks match the original seed-0 AUCs to three decimals and all input hashes remain unchanged. The table updater refused a real incomplete checkpoint, then accepted the complete grid. Only 30 AUC interval pairs were updated; every historical point/range/count and false-alert interval was preserved. Raw outputs, logs and the exact changes receipt are in results/bootstrap_corrected. R12b preparation failed before simulation because Drive rejects symlinks; the runner now stages preparation on /content and persists finished files to Drive. Original failed-run evidence is preserved.

## R12b population-control finding

See results/r12b_reconstruction/README.md. Local scratch fixed the Drive symlink error, but the historical site-population check correctly stopped the run before any simulation. Six Friday file orders failed to reproduce the counts; an all-day deterministic tie-policy diagnostic is pending retrieval. This is an unresolved reproducibility finding, not a negative or positive mesh result.
