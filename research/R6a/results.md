### Family-mean AUC and false alerts (mean over seeds, range)

| Dataset | Split | Model | Family-mean AUC | Worst family | False alerts per benign host-day at 80% in 5 min |
|---|---|---|---|---|---|
| CIC-IDS2017 | dev | v0 NCM, smoothed | 0.991 (0.980 to 0.997) | 0.971 (0.939 to 0.989) | 0.62 (0.52 to 0.70) |
| CIC-IDS2017 | dev | history only (no GRU) | 0.989 (0.989 to 0.989) | 0.978 (0.977 to 0.979) | 0.75 (0.70 to 0.82) |
| CIC-IDS2017 | dev | v0 + history | 0.995 (0.994 to 0.996) | 0.990 (0.988 to 0.993) | 0.68 (0.61 to 0.76) |
| CIC-IDS2017 | final | v0 NCM, smoothed | 0.954 (0.942 to 0.966) | 0.861 (0.822 to 0.912) | 12.06 (6.37 to 15.16) |
| CIC-IDS2017 | final | history only (no GRU) | 0.952 (0.951 to 0.953) | 0.766 (0.760 to 0.773) | 36.41 (35.32 to 36.89) |
| CIC-IDS2017 | final | v0 + history | 0.965 (0.963 to 0.966) | 0.860 (0.853 to 0.872) | 26.84 (23.37 to 28.53) |
| UNSW-NB15 | dev | v0 NCM, smoothed | 0.949 (0.948 to 0.950) | 0.944 (0.943 to 0.945) | 2.26 (1.20 to 2.99) |
| UNSW-NB15 | dev | history only (no GRU) | 0.951 (0.950 to 0.951) | 0.949 (0.948 to 0.949) | 2.66 (2.23 to 3.09) |
| UNSW-NB15 | dev | v0 + history | 0.949 (0.948 to 0.950) | 0.946 (0.945 to 0.946) | 2.34 (1.83 to 2.58) |
| UNSW-NB15 | final | v0 NCM, smoothed | 0.942 (0.941 to 0.944) | 0.938 (0.936 to 0.939) | 3.01 (1.25 to 4.14) |
| UNSW-NB15 | final | history only (no GRU) | 0.945 (0.945 to 0.946) | 0.942 (0.941 to 0.943) | 2.05 (1.91 to 2.26) |
| UNSW-NB15 | final | v0 + history | 0.943 (0.942 to 0.944) | 0.940 (0.939 to 0.941) | 2.52 (1.54 to 3.54) |
| CSE-CIC-IDS2018 | dev | v0 NCM, smoothed | 1.000 (1.000 to 1.000) | 1.000 (0.999 to 1.000) | 0.00 (0.00 to 0.00) |
| CSE-CIC-IDS2018 | dev | history only (no GRU) | 1.000 (1.000 to 1.000) | 1.000 (0.999 to 1.000) | 0.01 (0.00 to 0.01) |
| CSE-CIC-IDS2018 | dev | v0 + history | 1.000 (1.000 to 1.000) | 1.000 (1.000 to 1.000) | 0.00 (0.00 to 0.01) |
| CSE-CIC-IDS2018 | final | v0 NCM, smoothed | 0.989 (0.988 to 0.991) | 0.982 (0.975 to 0.986) | 0.24 (0.20 to 0.28) |
| CSE-CIC-IDS2018 | final | history only (no GRU) | 0.986 (0.986 to 0.987) | 0.985 (0.984 to 0.985) | 0.52 (0.48 to 0.56) |
| CSE-CIC-IDS2018 | final | v0 + history | 0.989 (0.989 to 0.990) | 0.986 (0.985 to 0.986) | 0.37 (0.35 to 0.40) |
| Unraveled | dev | v0 NCM, smoothed | 0.906 (0.901 to 0.917) | 0.814 (0.803 to 0.835) | 5.87 (5.10 to 6.62) |
| Unraveled | dev | history only (no GRU) | 0.765 (0.762 to 0.767) | 0.533 (0.527 to 0.537) | 10.28 (8.06 to 11.30) |
| Unraveled | dev | v0 + history | 0.835 (0.831 to 0.838) | 0.671 (0.663 to 0.678) | 6.02 (5.57 to 6.73) |
| Unraveled | final | v0 NCM, smoothed | 0.894 (0.884 to 0.899) | 0.760 (0.733 to 0.782) | 13.47 (10.95 to 15.91) |
| Unraveled | final | history only (no GRU) | 0.841 (0.838 to 0.846) | 0.719 (0.715 to 0.722) | 33.91 (32.39 to 35.84) |
| Unraveled | final | v0 + history | 0.878 (0.871 to 0.885) | 0.744 (0.727 to 0.756) | 23.60 (21.40 to 25.22) |
| CICAPT-IIoT | dev | v0 NCM, smoothed | 0.879 (0.853 to 0.908) | 0.879 (0.853 to 0.908) | 3.00 (2.60 to 3.96) |
| CICAPT-IIoT | dev | history only (no GRU) | 0.882 (0.879 to 0.885) | 0.882 (0.879 to 0.885) | 2.12 (0.84 to 3.68) |
| CICAPT-IIoT | dev | v0 + history | 0.888 (0.871 to 0.901) | 0.888 (0.871 to 0.901) | 2.39 (1.60 to 3.72) |
| CICAPT-IIoT | final | v0 NCM, smoothed | 0.697 (0.637 to 0.756) | 0.654 (0.594 to 0.723) | 8.74 (5.18 to 18.93) |
| CICAPT-IIoT | final | history only (no GRU) | 0.820 (0.817 to 0.826) | 0.782 (0.776 to 0.788) | 5.45 (3.68 to 6.54) |
| CICAPT-IIoT | final | v0 + history | 0.796 (0.775 to 0.814) | 0.786 (0.763 to 0.810) | 3.26 (2.61 to 4.00) |

### Rule 1, GRU removal (history only against v0)

| Dataset | Split | AUC difference (history minus v0) | False alerts, history vs v0 | Within 0.01 and no worse |
|---|---|---|---|---|
| CIC-IDS2017 | dev | -0.003 | 0.75 vs 0.62 | no |
| CIC-IDS2017 | final | -0.002 | 36.41 vs 12.06 | no |
| UNSW-NB15 | dev | +0.002 | 2.66 vs 2.26 | no |
| UNSW-NB15 | final | +0.003 | 2.05 vs 3.01 | yes |
| CSE-CIC-IDS2018 | dev | -0.000 | 0.01 vs 0.00 | no |
| CSE-CIC-IDS2018 | final | -0.003 | 0.52 vs 0.24 | no |
| Unraveled | dev | -0.141 | 10.28 vs 5.87 | no |
| Unraveled | final | -0.053 | 33.91 vs 13.47 | no |
| CICAPT-IIoT | dev | +0.003 | 2.12 vs 3.00 | yes |
| CICAPT-IIoT | final | +0.123 | 5.45 vs 8.74 | yes |

**Rule 1 verdict: the GRU stays (the rule is not met).**

### Rule 2, improvement (v0 + history against v0)

- Better on dev (seed minimum above v0's seed maximum): none (0 of 5 datasets).
- Worse (seed maximum below v0's seed minimum) on dev or final: Unraveled dev.
- Final mean not below v0's on the datasets that are better on dev: yes.
**Rule 2 verdict: not an improvement.**

