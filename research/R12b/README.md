# R12b: does R12's "sharing does not pay" depend on the block rule?

Follow-up to R12 (plan step 37; evidence for gate G1). **Status: protocol and code committed before the run. No results yet.**

## Why this rerun

R12 concluded that sharing blocks between sites does not help more than it harms. That conclusion used **one block rule that the author chose** (2 of a source's last 3 windows above the 99.5th percentile of the site's calibration windows) and did not try others. R7d later showed that this rule alone blocks 29 to 42 of 48 benign host-days on CIC-IDS2017 with no attack added. R12's harm (false blocks spreading between sites) may therefore reflect that rule and not sharing itself. This rerun repeats R12 with much stricter rules. It was requested in review before the gate decision.

## Method

Everything as in R12 (`research/R12/README.md`): the same virtual sites (K = 2 and 4, the same host split), the same per-site refit of v0, seeds 0 to 2, the same three datasets (CSE-CIC-IDS2018 restricted to the scoreboard's sources), the same policies (no sharing, share every block, act when 2 other sites agree), expiry (none, 30 seconds) and lying site. Only the block rule changes; `r12b_sim.py` is `r12_sim.py` with the rule as a parameter.

Four rules, fixed now:

| Rule | A source is blocked at a site when | 
|---|---|
| 0 | 2 of its last 3 windows are above the 99.5th percentile (R12's rule; must reproduce R12's numbers) |
| 1 | 5 of its last 6 windows are above the 99.9th percentile |
| 2 | 12 of its last 12 windows (a full minute of activity) are above the 99.9th percentile |
| 3 | 12 of its last 12 windows are above the 99.99th percentile |

## Measures (final split, 4 sites unless stated)

As R12, plus two that R12 did not report: the share of **benign source-site-days blocked by the site's own rule** (how harsh the rule is on its own), and the share of attacker-site pairs **blocked at or before their first attack window** computed over all pairs (pairs never blocked count as not blocked). R12's line 2 found that the share of attack windows prevented is saturated, so the first-window measure is the gain measure here; windows prevented is still reported.

## Decision rules (fixed now)

1. **A rule is usable** when the site's own rule blocks at most 5% of benign source-site-days on every dataset, and at most half of the attacker-site pairs are never blocked (without sharing) on at least 2 of the 3 datasets. A rule that blocks most benign hosts, or catches almost nobody, is not a basis for judging sharing.
2. **Sharing pays under a rule** when, for the two-site policy with no expiry against no sharing: the share of attacker-site pairs blocked at or before their first window rises by at least 0.10 on at least 2 of the 3 datasets; the share of benign source-site-days wrongly blocked through sharing is at most 0.02 on every dataset; and the lying site adds at most 0.001 to the share of benign windows blocked at honest sites on every dataset.
3. **Verdict for G1:** if sharing pays under at least one usable rule, R12's "no" was specific to its block rule and the gate question is reopened. If it pays only under rules that are not usable, or under none, R12's "no" holds across the rules tried.

Sanity check: rule 0 must give the same counts as the committed R12 results; a mismatch is reported before anything else.

## Known limits, stated now

- **Four rules are not all rules.** A different family (per-source thresholds, a rate limit before a block, scores from another detector) could behave differently.
- **Changing the gain measure after R12** is a choice made with R12's results in view; windows prevented, R12's original measure, is reported beside it.
- **Stricter rules catch fewer attackers and later,** so the comparison is between sharing regimes at a given rule, not between rules.
- The rest of R12's limits apply unchanged: random host split, few attackers, no latency, lab data, a simple lying site.

## Deviations

None yet.

## Reproduce

Site windows as in R12 (`research/R12/code/prep_site.py`), then `python research/R12b/code/r12b_sim.py <site dir> <checkpoint> out.json <seed> <scoreboard windows.npz or -> <k> <n> <quantile>` and `python research/R12b/code/r12b_decide.py <dir> out.md <original-R12-results-dir>`.

## Audit corrections — 13 November 2026

The decision script now refuses to publish a verdict unless all 72 declared dataset/site/rule/seed results exist, metadata agrees with filenames and rules, time-to-block populations are nonempty and valid, and reported rates have positive denominators. Before validation it replaces any stale report with an INCOMPLETE notice. Empty or missing data cannot mean zero harm or a negative mesh verdict.

Thresholds and the four block rules above remain author-chosen, post-R12 sensitivity assumptions, not independently chosen operating requirements or owner approval of G1. This audit does not silently change them. Even complete conditional results do not settle the general question of whether sharing is useful. The baseline rule-0 reproduction must still be compared with original R12 artifacts before interpreting a rerun.

Checks: `python research/R12b/code/test_r12b_decide.py`. Synthetic fixtures exercise complete input, no files, missing seed, unexpected seed, mismatched metadata, empty attacker populations, and zero denominator. Fixtures are test data, not research results.

### Additional verdict guards and sensitivity (13 November)

The original R12 reference directory is required for a verdict. After all 72 runs validate, every rule-0 dataset/K/seed must match its corresponding original R12 seed, K, attacker-site pairs and scenario counts exactly. Missing references or differences fail closed with INCOMPLETE. Exploratory strict/original/lenient threshold tables expose sensitivity; they do not change the original rule or grant G1 approval. No 72-run rerun was started during this review.

`python research/R12b/code/test_r12b_decide.py` also covers missing references and rule-0 baseline mismatches.

## Executable validation pipeline — 13 November

`code/run_r12b_batch.py DATA_ROOT OUTPUT_ROOT SOURCE_DIR` prepares all six destination-hashed site datasets from raw flows, checks each site's total/day-0 fit population against historical R12, runs all 18 rule-0 controls with original count/timing/forgery comparisons, then runs the remaining 54 settings and the 72-file decision guard. Any failed population, execution or reference check writes INCOMPLETE and stops without a verdict. Run it after other memory-heavy jobs finish.

Recovered inputs: CIC-IDS2017 raw/original flows in private data storage; CSE-CIC-IDS2018 d0..d4 parquets in <local copy> and private data storage; all 173 Unraveled CSVs in private data storage. Existing R6c pair maps are source/destination or service pairs, not valid R12 site inputs.

The staged source directory uses historical preprocessing from commit `3cbdcba`, current model/scoring code, and an explicitly recorded Friday original-file order (morning, DDoS, PortScan) that matched canonical source-window keys in the earlier audit. This is a reconstruction candidate, not proof of the original R12 input identity. Population and rule-0 outcome gates decide whether it is compatible. It does not substitute the new earliest-minute dataset under old results.

The reference guard now permits only the two additional R12b leaf counters absent from historical R12 (`benign_combos_total`, `benign_combos_own`). Every original counter, time-to-block array, forged-message total/rate and site population must still match exactly. Regression fixtures use the real older schema; changed outcomes and unknown/missing counters fail closed.

An optional `NCM_SCORE_CACHE_DIR` saves exact per-site score/calibration arrays because all four rules share the same refit. Keys include input/checkpoint/model/code hashes, seed/site, package/Python versions and thread settings; rule-specific quantiles are always recomputed. Cached arrays are finite-validated, atomically written and loaded without pickle; corruption fails closed. `python research/R12b/code/test_r12_score_cache.py` checks exact reuse, separate keys, nonfinite rejection and corruption. No rule or acceptance threshold was relaxed.
