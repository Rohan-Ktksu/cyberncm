# R7d and R7f: induced false blocks and spoofed sources

Plan step 38 (PLAN.md section 5, R7d and R7f; R7e, forged and replayed directives, is covered at the end). **Status: run complete (3 seeds). R7d and R7f are both breached on every seed; dropping unanswered flows removes the induced blocks but its clean cost is unmeasured. Method and rules unchanged from the commit before the run.** Gate G1 recommends a single-site product (`research/G1.md`), so these two tests are run against **one site's own blocking**, which is where they still apply.

## Questions

- **R7d, induced false blocks:** can an attacker get a benign host blocked by adding attack traffic to its address, at 1, 5 or 20% of its flows?
- **R7f, spoofed sources:** can an attacker get an uninvolved host blocked by rewriting the source of its unanswered flows to that host's address?

## Method

Dataset: CIC-IDS2017, test days Tuesday to Friday, raw flow tables (`research/R7/code/r7b_slow.py` writes the cache of flow tables with recovered hours). v0 seeds 0 to 2 (scoreboard checkpoints). **Targets:** hosts with no attack flow that day ("pure benign") and at least 100 flows. **Block rule (the one of R12):** a host is blocked when at least 2 of its last 3 windows scored above the 99.5th percentile of the day-0 calibration windows. Only the targets' flows are rewindowed (windows are per source), scored with v0 per (day, source), and checked against the rule.

- **R7d:** for each target, k = ceil(p x its flows) attack flows (drawn from that day's attack flows of any family) get the target's address as source and uniformly random times inside the target's active period; p = 1%, 5%, 20%. A host-day is **induced-blocked** at p when it is blocked at p and was not blocked at p = 0 (the same day and seed).
- **R7f:** the unanswered (no reply) TCP and UDP attack flows of the attacker with the most of them that day (at most 3,000) are re-sourced to each target in turn, keeping their original times (the real attack period). Run twice: as is, and with the **mitigation** "count only flows with an answer" (flows with no reply are dropped before windowing, for the target and its baseline). A target is induced-blocked when it is blocked with the spoofed flows and was not blocked without them.

## Breach rules (fixed now)

- **R7d** is breached when at least one benign host-day is induced-blocked at p of 5% or less (the plan's wording: "a benign host is blocked at 5% or less").
- **R7f** is breached when at least one uninvolved host-day is induced-blocked by the spoofed flows without the mitigation. The mitigation **counts only if** it removes the induced blocks **and** does not damage detection of the families that rely on unanswered flows (port scans): a retraining on windows built without unanswered flows, scored on the final days against the scoreboard's range, is the check that decides that; **it is not run in this round**, so any mitigation here is reported as "removes the induced blocks, clean cost unmeasured".

## Known limits, stated now

- **One dataset, a handful of benign hosts per day (about 15), three seeds,** so a "host-day" count is small and one host is a large share.
- **The injected flows are real attack flows moved to another address,** at random times in the target's active period; an attacker who shapes the timing could do better, and one who cannot send as the target at all (no spoofing ability) could not do this.
- **Spoofed TCP flows that go unanswered** are exactly what port scans look like; the mitigation of dropping them may blind the detector to scans (not measured here).
- The block rule is a fixed choice and not tolerable on benign traffic (R4), so some hosts are already blocked at p = 0; only the **induced** blocks count as breaches.
- **R7e (forged and replayed directives, malformed messages):** R12's lying-site simulation measures forged blocks (`research/R12/README.md`); replay and malformed directives need a directive protocol that does not exist yet (Block G) and are **not tested**.

## Results

CIC-IDS2017, Tuesday to Friday, v0 seeds 0 to 2 (per-seed files: `cyberncm-data/r7df/`). Targets are hosts with no attack flow that day and at least 100 flows: 14, 11, 12 and 11 hosts on the four days (48 host-days, the same on every seed; the day with no unanswered attack flows, Tuesday, has no R7f run, so R7f has 34 host-days).

### R7d: attack flows added to benign hosts

| Seed | Injected share p | Benign host-days | Blocked | Induced blocks (blocked at p, not at 0%) |
|---|---|---|---|---|
| 0 | 0% | 48 | 42 | 0 |
| 0 | 1% | 48 | 45 | 3 |
| 0 | 5% | 48 | 46 | 5 |
| 0 | 20% | 48 | 48 | 6 |
| 1 | 0% | 48 | 29 | 0 |
| 1 | 1% | 48 | 38 | 9 |
| 1 | 5% | 48 | 42 | 14 |
| 1 | 20% | 48 | 47 | 19 |
| 2 | 0% | 48 | 35 | 0 |
| 2 | 1% | 48 | 45 | 10 |
| 2 | 5% | 48 | 47 | 12 |
| 2 | 20% | 48 | 48 | 13 |

### R7f: unanswered attack flows re-sourced to uninvolved hosts

The spoofed flows are those of the attacker with the most unanswered TCP and UDP flows of the day, up to 3,000 per target (3,000 on Wednesday and Thursday, 46 on Friday).

| Seed | Mitigation (drop unanswered flows) | Uninvolved host-days | Blocked without the spoofed flows | Blocked with them | Induced blocks |
|---|---|---|---|---|---|
| 0 | no | 34 | 30 | 34 | 4 |
| 0 | yes | 34 | 25 | 25 | 0 |
| 1 | no | 34 | 21 | 34 | 13 |
| 1 | yes | 34 | 16 | 16 | 0 |
| 2 | no | 34 | 23 | 34 | 11 |
| 2 | yes | 34 | 16 | 16 | 0 |

## Answer in five lines

1. **R7d is breached on every seed.** Adding attack flows to a benign host makes it blocked when it was not blocked before: 3, 9 and 10 induced blocks of 48 host-days at 1% injected, 5, 14 and 12 at 5%, 6, 19 and 13 at 20%. The breach rule needs one at 5% or less.
2. **The block rule is the weak link, not only the injection:** with the same fixed rule (2 of 3 windows above the 99.5th percentile) 42, 29 and 35 of the 48 benign host-days are blocked already with nothing injected, and 47 or 48 are blocked at 20%. The induced numbers are therefore limited by how few hosts were left unblocked (6, 19, 13); a rule this false-block-heavy cannot be used to block automatically (R4), and this test shows that an attacker adds to it cheaply.
3. **R7f is breached on every seed:** with spoofed unanswered flows, all 34 uninvolved host-days are blocked on each seed, 4, 13 and 11 of them newly (the others were already blocked).
4. **The mitigation "count only flows with an answer" removes every induced block** (0 of 34 on each seed), but its **clean cost was not measured** and is the point of doubt: port scans consist of unanswered flows, so dropping them probably blinds the detector to scans. By the rule fixed in the protocol the mitigation therefore does not count as adopted; it is a lead, to be checked by retraining on windows built without unanswered flows.
5. **For the product:** do not block on the strength of a score; if blocking is ever added, block the source-destination pair and not the source, require an answered flow, protect critical prefixes and rate-limit first, as the plan lists (none of these was tested). R7e (forged directives): R12's lying site is the only evidence; replay and malformed directives are untested.

## Evidence limits

- **One dataset, about 12 benign hosts a day, three seeds:** a host-day is a large share; the baseline block counts differ a lot between seeds (29 to 42 of 48), which shows how much the rule depends on the model.
- **The injected flows are real attack flows moved to another address** at random times inside the target's active period; a cleverer attacker (or one unable to send as the target) would give other numbers.
- **The induced count cannot exceed the hosts left unblocked,** so at high injection levels it saturates.
- **Dropping unanswered flows changes the windows of every host,** so the "blocked without the spoofed flows" baseline for the mitigation runs differs from the unmitigated one (25, 16 and 16 against 30, 21 and 23).
- **The mitigation's effect on detection of scans and other unanswered-flow families was not measured.**
- R7e: only the simulated lying site (R12); replay and malformed directives are not tested because the directive protocol is not built.

## Deviations

- The first launch crashed in the mitigation run of R7f on a target whose flows were all unanswered (no windows left, an array-shape error in the block rule). The block rule now treats a host with no windows as not blocked; everything was rerun from the start, no result had been written up.

## Reproduce

`python research/R7df/code/r7df_inject.py <checkpoint> <canonical windows.npz> out.json <seed> <folder with cache_<day>.pkl>` from a folder where `ncm.py` and `prep.py` import.
