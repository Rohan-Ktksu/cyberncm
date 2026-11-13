# Independent rerun kit (plan step 27)

**Who this is for:** someone who did not produce the results. The point of the step is that a second person, starting from a fresh session, gets the same numbers; if the author reruns their own work, the word "confirmed" would claim more than was done. The author's own rerun counts as "reproduced by the author", never "confirmed".

**What you need:** this repository, the datasets downloaded from their original sources (see the dataset table in the top-level README), and a Python 3.12 or 3.13 environment. Nothing here needs a GPU.

**Artifact access limitation:** the stored windows, v0 checkpoints and raw result files that Level 1 reads are kept in a private shared folder and are **not** published, because redistribution of the datasets and of models trained on them has not been cleared. Level 1 therefore cannot be run from this repository alone; a reader can rebuild windows with `ncm/prep*.py` and retrain (Level 2), and should expect small differences until an independent rerun has been done.

## Status of this kit (author's own test, 2026-11-12; not an independent rerun)

- Level 1: the checker was run by the author on CIC-IDS2017 (seeds 0 and 1), UNSW-NB15 and CSE-CIC-IDS2018 (seeds 0 to 2 each): every row matched the stored value to 3 decimals and fell inside the committed range. CICAPT-IIoT and Unraveled were not yet run through it.
- Level 3, R11: the command as written above, run from a fresh copy of `ncm/`, reproduced the stored seed-0 values (0.085, 0.894 and 0.943).
- Level 2 (fresh training) and the R7c command of level 3 have **not** been run through this guide by anyone yet. If a step fails because the guide is wrong, that is a bug in the guide: report it.

## Setup (10 minutes)

1. Clone the repository to local disk:
   `git clone https://github.com/Rohan-Ktksu/cyberncm cyberncm`
2. Install the pinned packages: `pip install -r ./cyberncm/requirements.txt` (restart the runtime if asked).
3. `DATA=/path/to/your/rebuilt/data`.

## Level 1, about 30 minutes: do the headline numbers recompute?

`python ./cyberncm/research/RERUN/check_headlines.py --repo ./cyberncm --data $DATA --datasets cic2017,unsw,d2018 --seeds 0,1,2`

The script is written without the scoreboard harness: it loads the shared v0 checkpoints and the windows, scores them, and computes the family-mean AUC itself. It prints PASS or FAIL for each row. **Expected:** every row `matches_stored True` (same value as the original run to 3 decimals) and `inside_range True` (inside the min to max over 5 seeds in `research/scoreboard.csv`). Add `--datasets unraveled,cicapt` for the other two (slower: Unraveled takes about 10 minutes per seed).

What this does and does not show: it shows the table in `research/SCOREBOARD.md` follows from the stored checkpoints and windows by code you can read. It does not show the checkpoints are the ones a fresh training would give (level 2) or that the windows follow from the raw datasets (level 4).

## Level 2, 1 to 2 hours: does a fresh training land in the same range?

Retrain v0 for one seed of one dataset and check it with the same script:

```
mkdir -p ./rr/ncm && cp -r ./cyberncm/ncm/* ./rr/ncm/ && cd ./rr/ncm
ln -s $DATA/cic2017 data && mkdir -p artifacts
OMP_NUM_THREADS=8 python train.py gru 64 7        # a seed the authors did not use
mkdir -p ./rr/ckpt && cp artifacts/ncm_gru64_s7.pt ./rr/ckpt/cic2017_s7.pt
python ./cyberncm/research/RERUN/check_headlines.py --repo ./cyberncm --data $DATA --datasets cic2017 --seeds 7 --ckpt-dir ./rr/ckpt
```

**Expected:** `inside_range True` (a new seed need not match any stored value; `matches_stored` has nothing to compare with and shows None). A final AUC inside 0.942 to 0.966 for CIC-IDS2017 is the pass; a value well outside is a finding to report.

## Level 3, about 1 hour: do the two findings that matter most hold?

**R11, refitting is enough** (CIC-IDS2017 model onto UNSW-NB15, seed 0). From `./rr/ncm` (the folder above, with `scoreboard.py`-era code importable):

`PYTHONPATH=./rr/ncm python ./cyberncm/research/R11/code/r11_adapt.py $DATA/scoreboard/ckpt/cic2017_s0.pt $DATA/unsw/windows.npz ./rr/r11.json 0`

**Expected** (seed 0, final family-mean AUC, stored in `$DATA/r11/cic2017_to_unsw_s0.json`; the five-seed means are in `research/R11/README.md`): threshold only 0.085 (below chance, the model is inverted on this direction), plus normalisation 0.894, plus vocabularies and calibration (the line "L3 + target vocabularies and calibration @ full") 0.943, against the target's own full retraining at 0.942 (mean over its seeds). Differences of up to about 0.005 from run to run are normal (clustering is seeded but threads vary); a value outside that is a finding.

**R7c, a poisoned learning period blinds the model** (CIC-IDS2017 Botnet, seed 0):

`PYTHONPATH=./rr/ncm python ./cyberncm/research/R7/code/r7_stress.py poison $DATA/scoreboard/ckpt/cic2017_s0.pt $DATA/cic2017/windows.npz ./rr/r7_poison.json 0`

**Expected:** in the output, the lines for `Botnet` show final detection 0.79 at poison 0.0 and 0.03 at 0.005, 0.00 at 0.01 and above (seed 0, stored in `$DATA/r7/poison_cic2017_s0.json`; the three-seed means in `research/R7/README.md` are 0.83 and 0.13). Allow about 0.1 either way on the poisoned values, since the draw of poison windows is seeded but small changes move a family near the detection threshold. The run takes 15 to 25 minutes (it covers every family; read the Botnet lines).

## Level 4 (optional, hours): do the windows follow from the raw data?

`ncm/README.md` and the `ncm/prep*.py` scripts rebuild `windows.npz` from the public datasets. This needs the raw downloads (hundreds of MB to tens of GB) and is the longest step; the author has not yet had it reproduced either.

## Sign-off sheet

Copy this table into your report, fill the last three columns, and put your name and the date.

| Claim | Level | Expected | Observed | Pass? | Notes |
|---|---|---|---|---|---|
| v0 family-mean AUC, CIC-IDS2017, UNSW-NB15, CSE-CIC-IDS2018, seeds 0 to 2, dev and final | 1 | matches stored, inside committed range | | | |
| Fresh v0 training for CIC-IDS2017 (new seed) | 2 | final AUC inside 0.942 to 0.966 | | | |
| R11: level 3 within 0.02 of full retraining, CIC-IDS2017 to UNSW-NB15 (seed 0) | 3 | 0.943 against 0.942 | | | |
| R7c: Botnet detection falls from 0.79 to about 0.03 at 0.5% poison (seed 0) | 3 | see above | | | |

Anything that does not match is the useful result: write down exactly what you ran, what you saw and which expected value it breaks, and send it to the authors rather than adjusting the setup until it passes.

## Known limits of this kit

- Levels 1 to 3 use the shared windows and checkpoints, so they cannot catch an error in how the windows were built (level 4) or in the raw data.
- The checker shares the library code in `ncm/ncm.py` (the model and `score`, `ewma`) with the author's runs; reading that file is part of the check.
- The scoreboard's other models (random forests, isolation forest), R4, R6, the stress tests other than R7c and R3 are not covered here; extend the kit before claiming them as confirmed.

## Audit correction — 13 November 2026

The checker now returns a nonzero process exit status when headline checks fail. Previously it printed FAIL but exited successfully, which could mislead automated runners. A successful author-run rerun still is not independent confirmation.

Weighted AUC in `ncm/scoreboard.py` now uses scikit-learn's tie-aware weighted ROC AUC. The prior implementation broke ties by row position, so tied scores could change AUC under row permutations. Only seed-0 weighted-bootstrap intervals using this function require recomputation; point estimates already use tie-aware roc_auc_score. Regression check: `python research/RERUN/test_auc.py`.


### Raw-rebuild dataset versions

Historical headline results use canonical CIC-IDS2017 windows: 125,674 rows, SHA-256 `0f8a383e5b19c05123d23f89f7dbc526a00f15e54afbe9bc5292685f8bc2bea5`. The corrected deterministic earliest-minute timestamp tie convention produces a different dataset: 125,577 rows (Thursday -91, Friday -6). Label it `cic2017-earliest-minute-v1`; do not replace canonical windows under historical checkpoints or expect Level 1 headline equality. New-version model results require fresh training and evaluation. Missing-hour ambiguity remains; the new convention is reproducible, not proof of timestamp truth. Exact artifact hash/provenance collection is pending; do not treat row count as an identity hash.
