# Reproduction check (PLAN.md steps 11 and 12)

Run 2026-11-11 on a Colab CPU runtime. Python 3.13.18; torch 2.15.0+cpu, numpy 2.5.4, pandas 3.1.1, scikit-learn 1.9.1 (the pins in `requirements.txt`, installed into a separate folder). Code: `ncm/` from the Block B branch. Data: the prepared `windows.npz` files from `cyberncm-data/`.

## Result

| Check | Against | Result |
|---|---|---|
| UNSW-NB15 in-domain, GRU-64 seed 0: train, then `evaluate.py` | `research/R1/results/unsw_eval_seed0.txt` | 216 of 261 numbers identical. Headline NCM (smoothed) final family-mean AUC 0.9409 vs 0.9415, worst family 0.9364 vs 0.9368, false alarms at 1% 0.0779 vs 0.0771, detection 1.000 vs 1.000. 45 numbers differ by more than 0.0005, 5 by more than 0.001, 2 by more than 0.002; the largest gap is 0.017 on one tail statistic (I did not identify its column). |
| Cross run, CIC-IDS2017 to UNSW-NB15, seed 0 | `research/R1/results/cross/cic2017_to_unsw_s0.txt` | 124 of 124 numbers identical. |
| `ncm/metrics.py` on Unraveled, seed 0, ordered windows | `base_rate()` in `ncm/r2_lead.py`, and `research/R2` stored summary | Identical to `base_rate()` on all 18 values (3 score variants x 3 threshold policies x window and source-hour rate). Against the stored seed-0 summary: daily recalibration source-hours 0.1027 vs 0.1026, windows 0.0324 vs 0.0325; fixed threshold source-hours 0.2897 vs 0.2898, windows 0.2995 vs 0.3011. The R2 README's "10.8%" is the mean of the three stored seeds (0.1026, 0.1000, 0.1202). |

## Reading it

- The plan asks for a match to 0.001. The headline AUCs and the cross run meet that. The UNSW evaluation is not bit-exact: a handful of tail statistics move by 0.001 to 0.017. R1's README already records a one-window difference in UNSW windows between environments, so a library-version effect is the likely cause. I have not tested that.
- `metrics.py` reproduces R2's source-hour rate; the fixed-threshold window rate differs from the stored value by 0.0016, slightly over the 0.001 bar.

## Not done

UNSW seeds 1 and 2; the other five cross directions; CSE-CIC-IDS2018 and CICAPT-IIoT; Unraveled seeds 1 and 2. The step 12 text says "one cross run", which this covers.

## Data note

`cyberncm-data/unraveled/windows.npz` is the copy from R2's training step (`steps/unraveled_r2`). It has an extra `day_t0` key that `r2_lead.py` needs; the other copy on Drive (`steps/unraveled_prep`) lacks it and is otherwise identical. An earlier copy of the prep file placed in `cyberncm-data` was replaced.
