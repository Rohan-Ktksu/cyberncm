# R9: what does v0 cost on an edge-class CPU?

Plan step 35 (PLAN.md section 5, R9). **Status: run complete (4 runs, substitute core). Latency passes the pre-set rule; INT8 parity does not (one of four runs differs by 0.011). Method and rule unchanged from the commit before the run.** There is no Raspberry Pi class board in this project yet, so this round measures a **substitute** and says so everywhere: one thread pinned to one core of a cloud CPU. It is not a measurement of any edge board.

## Question

How big is v0 as INT8, how long does one scoring step take for a batch of sources on one core, how much memory per tracked source does it need, and does INT8 give the same answers as the full-precision model?

## Method

The scoreboard v0 checkpoint of seed 0 (CIC-IDS2017, UNSW-NB15) and seed 1 and 2 (CIC-IDS2017). The streaming step (`ncm/export.py`: normalise, embed, GRU, distances; stateless, the caller keeps one hidden state per source) is exported to ONNX (FP32, opset 17), quantised to INT8 by dynamic quantisation, and run with onnxruntime with 1 intra-op and 1 inter-op thread, the process pinned to one core (`taskset -c 0`), on an otherwise idle machine.

Measured: file size; latency for batches of 1, 8, 64 and 512 sources (200 warm-up runs, then 2,000 timed runs; median, 95th and 99th percentile); hidden-state bytes per source (layers x hidden size x 4); peak resident memory of the process (this includes the loaded dataset, so it is an upper bound, and the per-source state is the figure to use); parity: ONNX FP32 against PyTorch (maximum absolute difference in the surprise), INT8 against FP32 (correlation of the raw surprise over every window of the dataset, and the difference in the AUC of the smoothed surprise, attack against benign on the test days).

## Pass rule (fixed now)

The substitute result **supports a deployment claim** when, on the pinned core, (a) the INT8 median latency for a batch of 64 sources is at most 5 ms (a thousandth of the 5-second window a source produces), and (b) INT8 changes the test AUC by at most 0.005 compared with FP32 on every checked dataset and seed. If either fails, the model card says so. A pass is a claim about the substitute only; it does not cover feature extraction from flow records, the network, or any real board.

## Known limits, stated now

- **Substitute, not a board.** The CPU is a cloud server core (the model name is recorded in the result); a Raspberry Pi class core is several times slower, by an amount this round does not measure.
- **Only the scoring step is timed.** Building the 32 features from flow records and the smoothing step are not in it, and they may dominate in practice.
- **Process memory includes the dataset** held for the parity check; the per-source state figure is the number to use for sizing.
- A shared cloud machine has noisy neighbours; percentiles are reported so the spread is visible.
- Only the INT8 route of `export.py` was tried (dynamic quantisation), not static quantisation or other runtimes.

## Results

Four runs: CIC-IDS2017 seeds 0, 1, 2 and UNSW-NB15 seed 0 (per-run files, with the ONNX models, are on Drive: `cyberncm-data/r9/`). Machine: AMD EPYC 7B12, one thread pinned to core 0 of an otherwise idle 8-core cloud VM. **This is the substitute, not an edge board.**

| Measure | FP32 | INT8 |
|---|---|---|
| File size | 778 KB | 374 KB |
| Parameters | 96,070 | 96,070 |
| Latency, batch of 1 source (median over the 4 runs, range) | 0.105 to 0.109 ms | 0.112 to 0.119 ms |
| Latency, batch of 8 | 0.168 to 0.175 ms | 0.161 to 0.167 ms |
| Latency, batch of 64 | 0.518 to 0.535 ms | **0.444 to 0.451 ms** |
| Latency, batch of 512 | 3.86 to 4.02 ms | 2.98 to 3.06 ms |
| 99th percentile, batch of 64 (worst of the 4 runs) | 1.24 ms | 0.79 ms |
| Hidden state kept per source | 512 bytes | 512 bytes |

Parity (test days, attack against benign, smoothed surprise; the AUC here is not the scoreboard's family-mean AUC):

| Run | FP32 AUC | INT8 AUC | INT8 minus FP32 | INT8 against FP32 surprise correlation | ONNX FP32 against PyTorch, largest difference in any window's surprise |
|---|---|---|---|---|---|
| CIC-IDS2017 seed 0 | 0.9658 | 0.9769 | **+0.0111** | 0.949 | 0.0011 |
| CIC-IDS2017 seed 1 | 0.9799 | 0.9805 | +0.0006 | 0.930 | 0.0008 |
| CIC-IDS2017 seed 2 | 0.9720 | 0.9762 | +0.0042 | 0.924 | 0.269 |
| UNSW-NB15 seed 0 | 0.9443 | 0.9441 | -0.0003 | 0.947 | 0.0078 |

Peak resident memory of the benchmark process was 550 to 620 MB, but that includes the dataset held for the parity check; the sizing figure is the model (374 KB) plus 512 bytes per tracked source, about 51 MB for 100,000 sources.

## Answer in five lines

1. **Latency passes the pre-set rule:** the INT8 scoring step takes 0.44 to 0.45 ms for a batch of 64 sources on one pinned core (99th percentile at most 0.79 ms), against the 5 ms limit, which is a thousandth of the 5-second window a source produces. A batch of 512 takes about 3 ms. On this core that is roughly 145,000 source-windows per second, or about 700,000 sources each producing a window every 5 seconds, for the scoring step alone.
2. **Parity does not pass the pre-set rule:** INT8 changed the test AUC by more than 0.005 on one of the four runs (CIC-IDS2017 seed 0: +0.0111, INT8 higher), and by +0.0006, +0.0042 and -0.0003 on the others. The earlier statement that INT8 "costs 0.001 AUC" (`HANDOFF.md`) is not reproduced here: the difference is small but not 0.001 and can go either way. The surprise correlation between INT8 and FP32 is only 0.92 to 0.95.
3. **The ONNX FP32 export is not an exact copy on every window:** its largest difference from PyTorch in a single window's surprise is 0.001 to 0.008 on three runs and 0.27 on CIC-IDS2017 seed 2. I did not find the cause (the difference is in a few windows, since the AUC is unaffected).
4. **What this supports:** a claim about the scoring step on one server core (sub-millisecond per batch, 374 KB, 512 bytes per source). It does not support a claim about a Raspberry Pi class board, about feature extraction from flow records (not timed, and likely the larger cost), or that INT8 and FP32 give the same alerts.
5. **For the model card:** quote 0.44 ms per batch of 64 on one core of a cloud CPU as the substitute figure, drop "INT8 costs 0.001 AUC", and say INT8 changed the AUC by between -0.0003 and +0.011 on four runs.

## Evidence limits

- **Substitute, not a board.** A Pi core is slower by an amount this round does not measure. The figures are for a server-class core.
- **Only the scoring step is timed.** Building the 32 features from flow records, the smoothing and any network I/O are not in it.
- **Four runs, two datasets,** one seed on UNSW-NB15; the INT8 parity spread (-0.0003 to +0.0111) is wide for so few runs.
- **The parity AUC is a different measure** from the scoreboard's family-mean AUC, so it must not be compared with the scoreboard figures.
- A shared cloud machine has neighbours; the 99th percentiles are shown so the spread is visible. Dynamic quantisation was the only INT8 route tried.

## Deviations

- The first launch of the benchmark chain was interrupted by a lost connection to the notebook; the four runs had finished on the machine and their output files were read afterwards. No rerun, no change to the method.
- The ONNX packages were installed into a separate folder (`onnx`, `onnxruntime`) and placed last on the import path so the pinned versions stay in force.

## Reproduce

From a copy of `ncm/` with `onnx` and `onnxruntime` installed: `taskset -c 0 python research/R9/code/r9_bench.py <checkpoint> <windows.npz> out.json`.
