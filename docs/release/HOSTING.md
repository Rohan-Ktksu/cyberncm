# Hosting plan for the public website

**Proposed provider: GitHub Pages**, published from a GitHub Actions workflow, free for public repositories. Nothing has been published; this page describes what would happen once the owner approves.

## What would be published

Only the contents of the `site/` folder: `index.html`, `assets/` (diagrams and screenshots) and `demo/` (the dashboard page plus its recording, `recorded_fallback.json`). It is a static page with no backend, no database, no cookies, no analytics and no external requests (verified by loading it and listing every request). It does not use Colab, private cloud-drive files, private GitHub access or any paid model API.

## What visitors can and cannot reach

- They can read the project overview, findings and research index, use the **in-browser simulation** (synthetic numbers, in their own browser, labelled as a simulation), and watch a **recorded playback** of a real sandbox run in the real dashboard (a static capture of synthetic data, controls disabled, labelled as a recording).
- They cannot reach the two-node demo's Node A or Node B services, operator endpoints, signing keys, arbitrary targets, live traffic or enforcement controls. Those run only on a user's own machine on `127.0.0.1` and are not part of the published folder. No tunnel is used.

## Configuration

`.github/workflows/pages.yml` is **manual only** (`workflow_dispatch`): it never runs on push. Steps for the owner after approval:

1. Create the public repository and push the reviewed release.
2. Repository *Settings → Pages → Build and deployment → Source: GitHub Actions*.
3. *Actions → Deploy site to GitHub Pages → Run workflow*.
4. Open the resulting URL, check the page loads and the simulation works, then add that URL to the README.

## Limits (from GitHub's Pages documentation, read 13 Nov 2026)

| Limit | Value stated by GitHub | Impact here |
|---|---|---|
| Published site size | no larger than 1 GB | The site is well under 1 MB. |
| Source repository | recommended limit 1 GB | The repository is a few MB. |
| Bandwidth | soft limit of 100 GB per month | Ample for a research page. |
| Builds | soft limit of 10 per hour (does not apply to custom Actions workflows) | We use a workflow. |
| Deployment timeout | 10 minutes | Not a concern. |
| Use | Not for running an online business, e-commerce or commercial SaaS; not for sensitive transactions | This is a non-commercial research page that collects nothing. |
| Plan | Free plans require the repository to be public | The release repository is public by design. |

Check the live documentation again before publishing; these figures were read from the provider's pages and can change.

## Why the real demo and the sandbox are not hosted

The two-node demo (and its synthetic-data sandbox) has operator controls (start, approve, unblock, reset) and holds a single shared state, so a public copy would let every visitor act on the same session; making it per-visitor would mean running a process pair per visitor on a free host. The public site therefore offers only static things (the in-browser simulation and a recorded playback of a sandbox run), and the sandbox itself is run locally (`demo/two_node/sandbox/README.md`). If a hosted per-visitor sandbox is wanted later it should get its own review: session isolation, rate limits, timeouts and abuse handling.

## Alternatives considered

Any other static host (for example a project page on a university server) works unchanged because the site is plain files. No paid service, billing enrolment or metered integration is required for the proposed plan.
