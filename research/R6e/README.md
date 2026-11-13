# R6e: training objective and backbone

Plan step 26 (PLAN.md section 5, R6e). The team deferred this round earlier (2026-11-12) and then asked for all steps to be finished, so it is run here, **in a reduced form**. **Status: run complete (30 trained models and the ensemble, all five datasets). No candidate passes the improvement rule; v0 stays. Contrastive objective and state-space backbone not tried. Method and rule unchanged from the commit before the run.**

## Question

Does a different backbone or training objective earn its place against v0 (a 2-layer GRU, hidden size 64, trained to predict the next window and its behaviour token from benign traffic)?

## Candidates

1. **Seed ensemble.** The scores of the five scoreboard v0 models (seeds 0 to 4) are averaged (each is already standardised on its own calibration span, smoothed per source). Its "seed range" is the min to max over the five leave-one-out ensembles of four models. No training.
2. **Transformer backbone at equal hidden size.** `train.py tf 64`: a causal Transformer over blocks of 32 windows, two layers, hidden size 64, in place of the GRU. Everything else unchanged. Seeds 0 to 2.
3. **GRU with a masked-history objective.** Same GRU and losses, but during training a random 20% of the input windows are replaced by the benign mean (zero after normalisation) while the targets stay clean, so the model must predict each next window and token from a corrupted history (`research/R6e/code/train_masked.py`). Seeds 0 to 2.

**Not tried:** a contrastive objective, and the state-space backbone (the plan lists both). The model is a causal streaming model, so a bidirectional masked-window objective is not usable; the masked-history objective above is the streaming-compatible form of masking, and it is my choice, not the plan's wording.

Datasets: all five of the scoreboard (CIC-IDS2017, UNSW-NB15, CSE-CIC-IDS2018, Unraveled, CICAPT-IIoT); each trained model is evaluated with the scoreboard harness (`scoreboard.py --no-rf`), so the measures and splits are the scoreboard's.

## Decision rule (fixed now)

PLAN.md section 4 improvement rule against **v0** (the reference for a change to the model itself; v0 uses its 5 seeds' range): a candidate is **better** on a dataset when its lowest dev family-mean AUC is above v0's highest, **worse** when its highest on dev or final is below v0's lowest. It is an **improvement** when better on at least 3 of 5 datasets, worse on none, and the mean final AUC is not below v0's on the datasets where it is better on dev. A candidate with a dataset missing cannot pass. Differences inside the seed range are not wins.

## Known limits, stated now

- **Three seeds for the trained candidates** against v0's five; the rule compares ranges, so fewer seeds make a narrower range for the candidate than it should have.
- **One masking rate (20%) and one Transformer configuration;** no tuning.
- **The ensemble costs five times the compute** at deployment; a gain would have to be weighed against that and against the 374 KB model size.
- **The Transformer is described in the code as an ablation that is not exported:** it processes blocks of 32 windows, so a deployed version would need a different streaming step.
- Contrastive objectives and the state-space backbone are not tried.

## Results

Three seeds for each trained candidate on all five datasets (30 trained models, evaluated with the scoreboard harness; checkpoints and per-seed files on Drive, `cyberncm-data/r6e/`), the seed ensemble from the five existing v0 checkpoints. Reference: v0 with its five seeds.

#### Family-mean AUC per dataset: mean over seeds (min to max); v0 uses its 5 seeds

| Model | Split | CIC-IDS2017 | UNSW-NB15 | CSE-CIC-IDS2018 | Unraveled | CICAPT-IIoT |
|---|---|---|---|---|---|---|
| v0 (reference) | dev | 0.991 (0.980 to 0.997) | 0.949 (0.948 to 0.950) | 1.000 (1.000 to 1.000) | 0.906 (0.901 to 0.917) | 0.879 (0.853 to 0.908) |
| Transformer backbone, same hidden size | dev | 0.998 (0.997 to 0.998) | 0.951 (0.948 to 0.956) | 1.000 (1.000 to 1.000) | 0.884 (0.874 to 0.890) | 0.860 (0.851 to 0.866) |
| GRU with masked-history objective | dev | 0.992 (0.991 to 0.992) | 0.950 (0.947 to 0.952) | 1.000 (1.000 to 1.000) | 0.910 (0.908 to 0.915) | 0.881 (0.863 to 0.908) |
| Seed ensemble (leave-one-out ensembles of 4 of the 5 v0 seeds) | dev | 0.995 (0.994 to 0.996) | 0.948 (0.948 to 0.948) | 1.000 (1.000 to 1.000) | 0.910 (0.907 to 0.911) | 0.877 (0.869 to 0.886) |
| v0 (reference) | final | 0.954 (0.942 to 0.966) | 0.942 (0.941 to 0.944) | 0.989 (0.988 to 0.991) | 0.894 (0.884 to 0.899) | 0.697 (0.637 to 0.756) |
| Transformer backbone, same hidden size | final | 0.954 (0.944 to 0.960) | 0.943 (0.941 to 0.948) | 0.990 (0.990 to 0.991) | 0.889 (0.883 to 0.892) | 0.525 (0.489 to 0.561) |
| GRU with masked-history objective | final | 0.958 (0.949 to 0.964) | 0.943 (0.941 to 0.944) | 0.992 (0.989 to 0.996) | 0.894 (0.884 to 0.901) | 0.645 (0.633 to 0.666) |
| Seed ensemble (leave-one-out ensembles of 4 of the 5 v0 seeds) | final | 0.958 (0.955 to 0.961) | 0.942 (0.941 to 0.942) | 0.990 (0.989 to 0.990) | 0.898 (0.896 to 0.900) | 0.702 (0.685 to 0.718) |

#### Improvement rule against v0

| Candidate | Seeds per dataset | Better on dev | Worse (dev or final) | Final not below v0 where better | Improvement |
|---|---|---|---|---|---|
| Transformer backbone, same hidden size | 3 | none | Unraveled dev, CICAPT-IIoT final | yes | no |
| GRU with masked-history objective | 3 | none | none | yes | no |
| Seed ensemble (leave-one-out ensembles of 4 of the 5 v0 seeds) | 5 | none | none | yes | no |

**Candidates that pass: none.** A candidate missing a dataset cannot pass.

## Answer in five lines

1. **No candidate passes the improvement rule.** None is better than v0 on dev on any dataset (the rule needs 3 of 5): every candidate's dev range overlaps v0's on every dataset, so no difference counts.
2. **The Transformer backbone is worse, not better:** below v0's range on Unraveled dev (0.884 against 0.901 to 0.917) and on CICAPT-IIoT final (0.525 against 0.637 to 0.756), with CICAPT-IIoT the most unstable (0.489 to 0.561). Elsewhere it matches v0 (CIC-IDS2017 0.954, CSE-CIC-IDS2018 0.990, UNSW-NB15 0.943 on final).
3. **The masked-history objective changes almost nothing:** candidate seed ranges overlap v0 everywhere (0.958, 0.943, 0.992, 0.894, 0.645 against 0.954, 0.942, 0.989, 0.894, 0.697); the lower CICAPT-IIoT mean (0.645, 0.633 to 0.666) is inside v0's wide range. It is not worse by the rule and not better.
4. **A seed ensemble gains about 0.005 AUC at most in the rounded table** (CIC-IDS2017 final 0.958 against 0.954, Unraveled final 0.898 against 0.894, CICAPT-IIoT 0.702 against 0.697), inside the single-model seed range everywhere, for five times the compute at deployment. Its narrow range (0.955 to 0.961 on CIC-IDS2017) is partly because the five leave-one-out ensembles share most of their members.
5. **Decision:** v0 stays as it is (consistent with R6g). The neural part is not made better by these backbone or objective changes at this size; that leaves the question of whether it earns its place at all, which R6a answered for one dataset only (Unraveled). A contrastive objective and the state-space backbone were not tried.

## Evidence limits

- **Three seeds against v0's five:** the candidate ranges are narrower than they would be with five seeds, which makes the "worse" test easier to trigger and the "better" test easier to pass; with this data neither was close except where stated.
- **One masking rate (20%), one Transformer configuration, no tuning;** a differently tuned objective could do better.
- **Contrastive objectives and the state-space backbone were not tried,** so R6e is only partly done.
- **The ensemble's range is not a real seed range** (leave-one-out subsets overlap).
- **The Transformer here processes blocks of 32 windows** and is not exportable as the streaming step; a gain would not have been deployable as is.
- Datasets with few attacking sources (CICAPT-IIoT, Unraveled) have wide seed ranges for every model, so small differences there are unreadable.

## Deviations

- The first version of `r6e_decide.py` read every model row of each scoreboard file (the files also hold the isolation-forest and token-distance baselines), so its first tables mixed three models per candidate ("9 seeds per dataset" for 3 seeds); the script now reads only the candidate's own row. The bug was seen in the script's own output before anything was written up; no method, rule or run changed.
- The run was started as two parallel workers with 4 threads each; the notebook connection dropped while they ran and the jobs finished unattended; their output files were read afterwards.

## Reproduce

`python research/R6e/code/r6e_run.py "[('tf','cic2017',0), ...]" TAG` (needs `train_masked.py` copied next to `r6e_run.py`'s `/content/r6ecode/`), `python research/R6e/code/r6e_ensemble.py <dataset> <windows.npz> <checkpoint dir> out.json` and `python research/R6e/code/r6e_decide.py <dir> <scoreboard dir> out.md`.


## Verification follow-up, 13 November 2026

The decision script now refuses incomplete grids, missing reference seeds, malformed AUCs, contradictory seed metadata and invalid ensemble populations. It writes INCOMPLETE before reading inputs. The runner parses job data with ast.literal_eval instead of executing it and accepts only declared candidates, datasets and seeds. Synthetic report tests verify complete input and fail-closed missing inputs; the full 30-model result grid has not been independently recomputed in this review. Same hidden width is not a parameter-matched backbone comparison. Leave-one-out ensemble subsets overlap and are not independent seed replicates. Rounded table means do not support an exact universal 0.004 bound. Original experimental results and pass thresholds were not changed.


The report was subsequently reproduced from all 60 stored input records: 25 reference point-estimate files, 30 trained-candidate point-estimate files, and five ensemble files. The complete decision table matches the reported no-passing-candidate result. `results/report_inputs.json` contains extracted point estimates and SHA-256 hashes of the original complete Drive files; `results/report_verified.md` is the computed report. This reproduces report calculation, not the 30 model-training runs or independent human confirmation.
