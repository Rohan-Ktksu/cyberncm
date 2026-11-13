### CIC-IDS2017, token distance score (5 seeds; final split: 7 attacking and 11 benign sources)

| Policy | Setting chosen on dev (per seed) | Attacking sources alerted within 5 min | False alerts per benign host-day | Benign source-hours with an alert | Seeds meeting the target |
|---|---|---|---|---|---|
| fixed threshold | none | 0.66 (0.57 to 0.71) | 2.95 (2.05 to 4.53) | 0.210 (0.172 to 0.248) | 0 of 5 |
| daily recalibration | none | 0.06 (0.00 to 0.14) | 1.03 (0.79 to 1.32) | 0.083 (0.069 to 0.110) | 0 of 5 |
| rolling quantile | 24 h, 6 h | 0.26 (0.14 to 0.29) | 1.17 (0.79 to 1.58) | 0.119 (0.076 to 0.145) | 0 of 5 |
| per-source threshold | previous day | 0.60 (0.57 to 0.71) | 3.71 (3.32 to 3.95) | 0.255 (0.248 to 0.262) | 0 of 5 |
| k of n on fixed | 6 of 12 | 0.54 (0.29 to 0.71) | 2.11 (1.63 to 2.74) | 0.108 (0.090 to 0.138) | 0 of 5 |
| k of n on daily | 6 of 12 | 0.00 (0.00 to 0.00) | 0.48 (0.26 to 0.68) | 0.022 (0.014 to 0.028) | 0 of 5 |
| two tiers | block above 99.9th percentile for 6 windows | 0.20 (0.00 to 0.43) | 1.15 (0.84 to 1.58) | 0.074 (0.055 to 0.110) | 0 of 5 |

### CIC-IDS2017, v0 score (5 seeds; final split: 7 attacking and 11 benign sources)

| Policy | Setting chosen on dev (per seed) | Attacking sources alerted within 5 min | False alerts per benign host-day | Benign source-hours with an alert | Seeds meeting the target |
|---|---|---|---|---|---|
| fixed threshold | none | 0.69 (0.57 to 0.71) | 2.97 (2.11 to 4.95) | 0.206 (0.179 to 0.228) | 0 of 5 |
| daily recalibration | none | 0.11 (0.00 to 0.14) | 0.89 (0.74 to 1.11) | 0.084 (0.062 to 0.097) | 0 of 5 |
| rolling quantile | 24 h, 6 h | 0.34 (0.29 to 0.43) | 1.28 (0.74 to 2.05) | 0.121 (0.090 to 0.152) | 0 of 5 |
| per-source threshold | previous day | 0.54 (0.43 to 0.71) | 3.87 (3.58 to 4.26) | 0.279 (0.255 to 0.297) | 0 of 5 |
| k of n on fixed | 6 of 12 | 0.66 (0.57 to 0.71) | 1.89 (1.47 to 2.53) | 0.101 (0.076 to 0.117) | 0 of 5 |
| k of n on daily | 6 of 12 | 0.00 (0.00 to 0.00) | 0.44 (0.37 to 0.58) | 0.023 (0.021 to 0.028) | 0 of 5 |
| two tiers | block above 99.9th percentile for 6 windows | 0.43 (0.29 to 0.57) | 1.05 (0.79 to 1.26) | 0.063 (0.048 to 0.083) | 0 of 5 |

### UNSW-NB15, token distance score (5 seeds; final split: 4 attacking and 37 benign sources)

| Policy | Setting chosen on dev (per seed) | Attacking sources alerted within 5 min | False alerts per benign host-day | Benign source-hours with an alert | Seeds meeting the target |
|---|---|---|---|---|---|
| fixed threshold | none | 1.00 (1.00 to 1.00) | 5.16 (5.12 to 5.20) | 0.520 (0.506 to 0.529) | 0 of 5 |
| daily recalibration | none | 0.00 (0.00 to 0.00) | 0.47 (0.43 to 0.52) | 0.055 (0.055 to 0.055) | 0 of 5 |
| rolling quantile | 1 h | 1.00 (1.00 to 1.00) | 1.85 (1.72 to 1.96) | 0.242 (0.227 to 0.251) | 0 of 5 |
| per-source threshold | previous day | 0.30 (0.25 to 0.50) | 1.66 (1.32 to 1.86) | 0.263 (0.239 to 0.275) | 0 of 5 |
| k of n on fixed | 6 of 12 | 1.00 (1.00 to 1.00) | 3.65 (3.59 to 3.77) | 0.261 (0.243 to 0.290) | 0 of 5 |
| k of n on daily | 6 of 12 | 0.00 (0.00 to 0.00) | 0.41 (0.38 to 0.45) | 0.047 (0.047 to 0.047) | 0 of 5 |
| two tiers | block above 99.9th percentile for 6 windows | 1.00 (1.00 to 1.00) | 3.43 (3.33 to 3.61) | 0.222 (0.196 to 0.271) | 0 of 5 |

### UNSW-NB15, v0 score (5 seeds; final split: 4 attacking and 37 benign sources)

| Policy | Setting chosen on dev (per seed) | Attacking sources alerted within 5 min | False alerts per benign host-day | Benign source-hours with an alert | Seeds meeting the target |
|---|---|---|---|---|---|
| fixed threshold | none | 1.00 (1.00 to 1.00) | 5.70 (5.46 to 5.96) | 0.627 (0.588 to 0.663) | 0 of 5 |
| daily recalibration | none | 0.00 (0.00 to 0.00) | 0.44 (0.39 to 0.51) | 0.040 (0.031 to 0.043) | 0 of 5 |
| rolling quantile | 1 h, 6 h | 1.00 (1.00 to 1.00) | 1.90 (1.80 to 1.99) | 0.239 (0.227 to 0.243) | 0 of 5 |
| per-source threshold | previous day | 0.15 (0.00 to 0.25) | 1.28 (1.19 to 1.42) | 0.226 (0.216 to 0.239) | 0 of 5 |
| k of n on fixed | 6 of 12 | 1.00 (1.00 to 1.00) | 3.98 (3.84 to 4.12) | 0.335 (0.302 to 0.365) | 0 of 5 |
| k of n on daily | 6 of 12 | 0.00 (0.00 to 0.00) | 0.35 (0.23 to 0.46) | 0.041 (0.031 to 0.047) | 0 of 5 |
| two tiers | block above 99.9th percentile for 6 windows | 1.00 (1.00 to 1.00) | 3.74 (3.70 to 3.77) | 0.297 (0.282 to 0.306) | 0 of 5 |

### CSE-CIC-IDS2018, token distance score (5 seeds; final split: 11 attacking and 3794 benign sources)

| Policy | Setting chosen on dev (per seed) | Attacking sources alerted within 5 min | False alerts per benign host-day | Benign source-hours with an alert | Seeds meeting the target |
|---|---|---|---|---|---|
| fixed threshold | none | 1.00 (1.00 to 1.00) | 0.88 (0.85 to 0.92) | 0.142 (0.129 to 0.155) | 5 of 5 (passes) |
| daily recalibration | none | 0.18 (0.18 to 0.18) | 0.12 (0.12 to 0.13) | 0.025 (0.024 to 0.026) | 0 of 5 |
| rolling quantile | 24 h, 6 h | 0.18 (0.18 to 0.18) | 0.29 (0.15 to 0.34) | 0.048 (0.028 to 0.059) | 0 of 5 |
| per-source threshold | previous day | 0.91 (0.91 to 0.91) | 0.36 (0.35 to 0.37) | 0.059 (0.058 to 0.060) | 5 of 5 (passes) |
| k of n on fixed | 6 of 12 | 1.00 (1.00 to 1.00) | 0.55 (0.52 to 0.57) | 0.053 (0.051 to 0.056) | 5 of 5 (passes) |
| k of n on daily | 6 of 12 | 0.18 (0.18 to 0.18) | 0.05 (0.05 to 0.06) | 0.003 (0.003 to 0.004) | 0 of 5 |
| two tiers | block above 99.9th percentile for 6 windows | 0.98 (0.91 to 1.00) | 0.23 (0.21 to 0.25) | 0.019 (0.017 to 0.021) | 5 of 5 (passes) |

### CSE-CIC-IDS2018, v0 score (5 seeds; final split: 11 attacking and 3794 benign sources)

| Policy | Setting chosen on dev (per seed) | Attacking sources alerted within 5 min | False alerts per benign host-day | Benign source-hours with an alert | Seeds meeting the target |
|---|---|---|---|---|---|
| fixed threshold | none | 1.00 (1.00 to 1.00) | 0.79 (0.76 to 0.82) | 0.129 (0.119 to 0.137) | 5 of 5 (passes) |
| daily recalibration | none | 0.62 (0.18 to 0.91) | 0.12 (0.11 to 0.13) | 0.024 (0.022 to 0.027) | 3 of 5 (passes) |
| rolling quantile | 6 h | 0.76 (0.27 to 0.91) | 0.27 (0.25 to 0.30) | 0.044 (0.039 to 0.048) | 4 of 5 (passes) |
| per-source threshold | previous day | 0.91 (0.91 to 0.91) | 0.34 (0.33 to 0.37) | 0.058 (0.055 to 0.062) | 5 of 5 (passes) |
| k of n on fixed | 6 of 12 | 1.00 (1.00 to 1.00) | 0.49 (0.48 to 0.51) | 0.051 (0.050 to 0.054) | 5 of 5 (passes) |
| k of n on daily | 6 of 12 | 0.58 (0.18 to 0.91) | 0.06 (0.05 to 0.06) | 0.003 (0.002 to 0.004) | 2 of 5 |
| two tiers | block above 99.9th percentile for 6 windows | 1.00 (1.00 to 1.00) | 0.22 (0.19 to 0.24) | 0.021 (0.018 to 0.024) | 5 of 5 (passes) |

### Unraveled, token distance score (5 seeds; final split: 4 attacking and 457 benign sources)

| Policy | Setting chosen on dev (per seed) | Attacking sources alerted within 5 min | False alerts per benign host-day | Benign source-hours with an alert | Seeds meeting the target |
|---|---|---|---|---|---|
| fixed threshold | none | 0.70 (0.50 to 0.75) | 3.65 (2.55 to 4.33) | 0.129 (0.114 to 0.138) | 0 of 5 |
| daily recalibration | none | 0.95 (0.75 to 1.00) | 2.45 (2.09 to 2.77) | 0.096 (0.090 to 0.101) | 0 of 5 |
| rolling quantile | 24 h | 0.25 (0.25 to 0.25) | 1.79 (1.39 to 2.24) | 0.084 (0.075 to 0.090) | 0 of 5 |
| per-source threshold | previous day | 0.75 (0.75 to 0.75) | 4.52 (4.39 to 4.63) | 0.141 (0.139 to 0.144) | 0 of 5 |
| k of n on fixed | 3 of 6 | 0.55 (0.25 to 0.75) | 2.87 (1.86 to 3.49) | 0.082 (0.069 to 0.090) | 0 of 5 |
| k of n on daily | 3 of 6 | 0.45 (0.25 to 0.50) | 1.83 (1.51 to 2.12) | 0.054 (0.050 to 0.058) | 0 of 5 |
| two tiers | block above 99.9th percentile for 3 windows | 0.15 (0.00 to 0.25) | 2.03 (1.17 to 2.89) | 0.065 (0.048 to 0.077) | 0 of 5 |

### Unraveled, v0 score (5 seeds; final split: 4 attacking and 457 benign sources)

| Policy | Setting chosen on dev (per seed) | Attacking sources alerted within 5 min | False alerts per benign host-day | Benign source-hours with an alert | Seeds meeting the target |
|---|---|---|---|---|---|
| fixed threshold | none | 1.00 (1.00 to 1.00) | 23.83 (20.72 to 26.09) | 0.361 (0.315 to 0.399) | 0 of 5 |
| daily recalibration | none | 0.35 (0.25 to 0.50) | 1.44 (1.14 to 1.65) | 0.060 (0.047 to 0.072) | 0 of 5 |
| rolling quantile | 24 h | 0.25 (0.25 to 0.25) | 1.27 (1.03 to 1.41) | 0.056 (0.042 to 0.069) | 0 of 5 |
| per-source threshold | previous day | 0.55 (0.50 to 0.75) | 3.61 (3.40 to 3.92) | 0.101 (0.090 to 0.110) | 0 of 5 |
| k of n on fixed | 2 of 3 | 1.00 (1.00 to 1.00) | 23.33 (20.23 to 25.53) | 0.324 (0.278 to 0.361) | 0 of 5 |
| k of n on daily | 3 of 6 | 0.05 (0.00 to 0.25) | 1.10 (0.88 to 1.31) | 0.033 (0.025 to 0.040) | 0 of 5 |
| two tiers | block above 99.9th percentile for 3 windows | 1.00 (1.00 to 1.00) | 16.44 (14.22 to 18.42) | 0.227 (0.197 to 0.251) | 0 of 5 |

### CICAPT-IIoT, token distance score (5 seeds; final split: 2 attacking and 17 benign sources)

| Policy | Setting chosen on dev (per seed) | Attacking sources alerted within 5 min | False alerts per benign host-day | Benign source-hours with an alert | Seeds meeting the target |
|---|---|---|---|---|---|
| fixed threshold | none | 1.00 (1.00 to 1.00) | 12.24 (10.46 to 14.07) | 0.568 (0.538 to 0.626) | 0 of 5 |
| daily recalibration | none | 0.00 (0.00 to 0.00) | 3.00 (2.54 to 3.43) | 0.185 (0.158 to 0.216) | 0 of 5 |
| rolling quantile | 6 h | 0.00 (0.00 to 0.00) | 2.31 (1.86 to 2.82) | 0.154 (0.129 to 0.196) | 0 of 5 |
| per-source threshold | previous day | 0.00 (0.00 to 0.00) | 14.05 (13.46 to 14.93) | 0.295 (0.269 to 0.327) | 0 of 5 |
| k of n on fixed | 6 of 12 | 1.00 (1.00 to 1.00) | 15.02 (9.64 to 18.29) | 0.432 (0.401 to 0.474) | 0 of 5 |
| k of n on daily | 6 of 12 | 0.00 (0.00 to 0.00) | 2.32 (1.93 to 2.79) | 0.123 (0.102 to 0.149) | 0 of 5 |
| two tiers | block above 99.9th percentile for 6 windows | 0.00 (0.00 to 0.00) | 1.09 (0.71 to 1.57) | 0.068 (0.041 to 0.102) | 0 of 5 |

### CICAPT-IIoT, v0 score (5 seeds; final split: 2 attacking and 17 benign sources)

| Policy | Setting chosen on dev (per seed) | Attacking sources alerted within 5 min | False alerts per benign host-day | Benign source-hours with an alert | Seeds meeting the target |
|---|---|---|---|---|---|
| fixed threshold | none | 1.00 (1.00 to 1.00) | 13.12 (10.07 to 16.21) | 0.522 (0.468 to 0.570) | 0 of 5 |
| daily recalibration | none | 0.40 (0.00 to 0.50) | 1.81 (1.57 to 1.96) | 0.119 (0.096 to 0.135) | 0 of 5 |
| rolling quantile | 6 h | 0.00 (0.00 to 0.00) | 1.48 (1.14 to 1.71) | 0.098 (0.067 to 0.111) | 0 of 5 |
| per-source threshold | previous day | 0.30 (0.00 to 0.50) | 14.05 (10.32 to 16.54) | 0.236 (0.222 to 0.251) | 0 of 5 |
| k of n on fixed | 6 of 12 | 1.00 (1.00 to 1.00) | 10.77 (7.96 to 13.11) | 0.412 (0.365 to 0.444) | 0 of 5 |
| k of n on daily | 6 of 12 | 0.00 (0.00 to 0.00) | 1.06 (0.50 to 1.43) | 0.063 (0.026 to 0.091) | 0 of 5 |
| two tiers | block above 99.9th percentile for 6 windows | 0.10 (0.00 to 0.50) | 1.11 (0.71 to 1.82) | 0.066 (0.041 to 0.117) | 0 of 5 |

