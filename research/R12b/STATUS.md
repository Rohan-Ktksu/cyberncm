# R12b status (as of 13 November 2026): incomplete, no verdict

This page records what happened when the R12b sweep was prepared. It is a reproducibility finding about data preparation. It is **not** a positive or negative result about block rules, sharing or a mesh, and it gives **no clearance at gate G1**.

## What was done

1. A corrected CPU environment was set up and the CIC-IDS2017 site populations for K=2 were rebuilt from the raw files.
2. Before any simulation, a guard compares the rebuilt site populations with the historical R12 populations.

## What the guard found

| | Site 0 windows | Site 1 windows | Day-0 fit windows (site 0 / site 1) |
|---|---|---|---|
| Rebuilt now | 83,558 | 77,938 | 14,348 / 13,832 |
| Historical R12 | 83,567 | 77,862 | 14,348 / 13,832 |

The day-0 fit counts match exactly; the totals do not. The guard therefore stopped the run **before any simulation**: no R12b result run was produced.

## Follow-up diagnostics

- All six orderings of the Friday input files were evaluated with the historical timestamp-recovery rule. **None** reproduced both historical site totals.
- A separate all-day diagnostic with the earliest-minute tie rule was launched for K=2 and K=4. Its output is not interpreted here and does not change the status below.

These are hypotheses about preprocessing (the timestamp tie handling that also explains the 125,577 against 125,674 window counts, see `research/RERUN/README.md`). They are not evidence for changing any threshold.

## Status

- The 72-run sweep is **incomplete**. The population and reference guards remain enabled.
- No positive or negative R12b verdict may be claimed, and no G1 clearance follows.
- Raw outputs of these diagnostics are withheld from this repository because they contain machine and session paths; the figures above are the ones recorded in the audit.
- Independent reproduction by another person has not been done.
