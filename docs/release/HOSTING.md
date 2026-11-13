# Hosting plan for the public website

**Proposed provider: GitHub Pages**, published from a GitHub Actions workflow, free for public repositories. Nothing has been published; this page describes what would happen once the owner approves.

## What would be published

Only the contents of the `site/` folder: `index.html` and `assets/*.svg`. It is a static page with no backend, no database, no cookies, no analytics and no external requests (verified by loading it and listing every request). It does not use Colab, private cloud-drive files, private GitHub access or any paid model API.

## What visitors can and cannot reach

- They can read the project overview, findings and research index, and use the **in-browser simulation**, which runs entirely in their own browser on synthetic numbers and is labelled as a simulation.
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

## Alternatives considered

Any other static host (for example a project page on a university server) works unchanged because the site is plain files. No paid service, billing enrolment or metered integration is required for the proposed plan.
