# Security policy

CyberNCM is a **research prototype**, not a production security product. It is published so that its methods and negative results can be examined. Please read the threat model in the [README](README.md#threat-model-and-security-boundaries) before reporting.

## Reporting a vulnerability

**Please do not open a public issue for a security problem.**

Report privately through one of these routes:

1. **GitHub private vulnerability reporting**: the "Report a vulnerability" button under this repository's *Security* tab (when enabled in the repository settings).
2. **Email**: rohanktksu@gmail.com


Please include what you found, the steps to reproduce it, the version or commit, and its impact. We will acknowledge a report as soon as we can; as a small research team we cannot promise a fixed response time.

## What is in scope

- The signing and verification code, the policy gate, the userspace gate and the operator endpoints in `demo/two_node/`.
- The single-site console and agent in `product/` (authentication, sessions, enrolment, request signing).
- Anything that would let a visitor of the public website reach operator or enforcement functionality. The public site in `site/` is static and has none by design.

## What is out of scope

- Detection quality (missed attacks, false alerts, evasion of the research model). These are documented research limitations, not vulnerabilities; evidence is in `research/`.
- The demonstration's own scope limits: it binds to `127.0.0.1`, does not change the Windows firewall and does not block campus or internet traffic.
- Findings that require running the demo against a network or host you do not own. Test only on systems you own or have written permission to test.

## Supported versions

Only the current `main` branch. There are no releases and no security backports.

## Responsible use

Use this code for research, teaching and evaluation in shadow mode. Do not deploy automatic blocking on a network on the strength of these results; the evidence does not support it (see `research/G1.md` and `research/CLAIMS.md`).
