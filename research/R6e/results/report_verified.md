### Family-mean AUC per dataset: mean over seeds (min to max); v0 uses its 5 seeds

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

### Improvement rule against v0

| Candidate | Seeds per dataset | Better on dev | Worse (dev or final) | Final not below v0 where better | Improvement |
|---|---|---|---|---|---|
| Transformer backbone, same hidden size | 3 | none | Unraveled dev, CICAPT-IIoT final | yes | no |
| GRU with masked-history objective | 3 | none | none | yes | no |
| Seed ensemble (leave-one-out ensembles of 4 of the 5 v0 seeds) | 5 | none | none | yes | no |

**Candidates that pass: none.** A candidate missing a dataset cannot pass.
