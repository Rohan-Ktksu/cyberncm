# R10: what is already published (first pass, 2026-11-11)

Plan step 15. Status: **first pass, not a literature review.** Six web searches; I read result snippets, not the papers. Every row below needs checking against the paper before any public sentence relies on it (claims ledger, step 36). Rows marked "unconfirmed" had a title or URL I could not match with certainty.

## Answer in five lines

1. Sharing alerts between sites, with trust scores for the sharers, is old (collaborative intrusion detection networks, from about 2008). Our mesh is not new as an idea.
2. A deployed system already does local detection, shared signals, consensus weighting by reporter trust and short expiry: CrowdSec. Its own materials describe it; its false-positive claims are marketing, not independent tests.
3. Federated learning for intrusion detection has several surveys and many papers on the same datasets we use. The ones found report supervised accuracy, not held-out attack families.
4. Unraveled's own authors report that common models hardly detect its APT activity, which matches our hard set (R2).
5. The searches did not find a measurement of what sharing blocks costs in blocks on normal traffic, or a cross-network failure report like R1. That is "not found here", not "does not exist".

## Related work

| Area | Work | What it does | Relation to ours | Source |
|---|---|---|---|---|
| Collaborative IDS | Fung, Zhang, Aib, Boutaba (CIDN, 2009-2011) | IDSes exchange alerts over an overlay; Bayesian and Dirichlet trust scores per peer; acquaintance management | Same shape as the mesh; trust is about peers that lie or are wrong | [paper](https://personal.ntu.edu.sg/zhangj/paper/tnsm10.pdf), [paper](https://rboutaba.cs.uwaterloo.ca/Papers/Conferences/2010/Carol10.pdf) |
| Collaborative IDS | RepCIDN, Gil Perez, Gomez Marmol, Martinez Perez | Reputation to limit damage from malicious alarms | Relevant to R7e (forged directives) | [page](https://webs.um.es/felixgm/pubs/improving-attack-detection-in-self-organizing-networks-a-trust-based-approach-toward-alert-satisfaction/) |
| Collaborative IDS | Decentralised trustworthy CIDS for IoT (2021) | Trust computation on a blockchain; shared detection rules in decentralised storage | Closest to our consensus and attestation plans | [arXiv 2110.11177](https://arxiv.org/pdf/2110.11177) |
| Collaborative IDS | TRIDEnT (2019, unconfirmed match for the URL) | Alert marketplace with rating and trust for competing parties | Incentive angle we do not cover | [arXiv 1905.03571](https://arxiv.org/pdf/1905.03571) |
| Deployed system | CrowdSec | Local alerts to decisions; offending IP, scenario and time sent to a central API; reporter trust rank; consensus before the community blocklist; 72 h expiry | The operational version of "share blocks with an expiry"; its own list of hard problems is confirming malice, false positives and poisoning, the same three R7 and R12 test | [vendor](https://crowdsec.net/our-data), [FAQ](https://crowdsec.net/faq-2) |
| Federated IDS surveys | ACM Computing Surveys vol. 57 (DOI 10.1145/3731596); IEEE TNSM survey | Taxonomies of FL-based IDS: aggregation, architecture, poisoning, privacy | Background for R8 | [ACM review](https://onofre4.tel.uva.es/publication/10-1145-3731596/), [TNSM](https://hal-imt-atlantique.archives-ouvertes.fr/hal-03831513) |
| Federated IDS, transfer | Transferability of federated IDS on CIC-IDS2017; block-level Bayesian aggregation (2025, aggregator page only, unverified) | Supervised; reports federated learning lowers transfer to unseen attacks and some fixes | Same question as R1/R8, supervised | [review](https://themoonlight.io/review/improving-transferability-of-network-intrusion-detection-in-a-federated-learning-setup), [page](https://newx.sg/paper/detail/b3ceca4e-f823-11f0-b84c-00163e10baa7) |
| Federated IDS, results | FedPrIDS (2025): CIC-IDS-2017, UNSW-NB15, Bot-IoT; AnomLocal (2026): UNSW-NB15 | Supervised accuracy 90 to 92%; anomaly detector 93.5% accuracy | Accuracy on mixed attack sets is not comparable to family-held-out AUC; protocols differ | [FedPrIDS and others](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12190250/), [AnomLocal](https://www.ncbi.nlm.nih.gov/pmc/articles/PMC12863697/) |
| Dataset | Unraveled / DAPT2021 | Semi-synthetic APT dataset, NFStream flows, public bucket; its authors found common ML models hardly detect the APT activity | Agrees with R2's hard stages | [COMIDDS](https://fkie-cad.github.io/COMIDDS/content/datasets/unraveled), [README](https://dapt2021.s3.amazonaws.com/README.txt) |
| Language-model detectors (for R14) | netFound; NetVAD; ET-BERT | netFound: hierarchical transformer on packet traces. NetVAD: variational autoencoder on frozen netFound features, benign-only training, tested on ToN-IoT and IoT-23. ET-BERT: pre-trained weights released | Candidates for the R14 comparison; NetVAD release status unconfirmed | [netFound](https://arxiv.org/html/2310.17025v4), [NetVAD](https://arxiv.org/pdf/2606.01452), [benchmark](https://arxiv.org/pdf/2403.10319) |

## What may be left to claim (to verify, not to assert)

- A benign-only model evaluated on **held-out attack families** across CIC-IDS2017, CSE-CIC-IDS2018 and UNSW-NB15, with **cross-network failure reported** (R1). The federated papers found report supervised accuracy.
- A **measured price of sharing**: share of benign windows blocked at a receiving site as the shared expiry grows (a first illustration is in `demo/README.md`; R12 is the real measurement). The collaborative-IDS literature found here is about trust in the reporter, and CrowdSec mitigates with trust, diversity and expiry, so the novelty would be the measurement, not the mechanism.
- Honest **negative results**: no next-stage prediction (R2); the sequence model adds little over a random forest.

## What this pass did not cover

- Threat-intelligence platforms and standards beyond CrowdSec (for example MISP, STIX/TAXII sharing), and commercial network detection with shared reputation.
- Published results per dataset with exact protocols; only titles and abstracts of a few were seen.
- Anything after the search snippets: no paper was opened.
- Searches were "standard" mode and US-only; a second pass in extended mode is cheap if this table is going into a paper.

## Method

Searches: collaborative IDS and cross-site sharing; federated IDS on the three datasets; Unraveled/DAPT2021; netFound, NetVAD and ET-BERT; CIDN trust and alert sharing; CrowdSec architecture.
