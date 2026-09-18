# CI

The repo has 2 workflows.

| Workflow | When it runs | What it does |
|---|---|---|
| `.github/workflows/collect-gate.yml` | On each push to `main` and on each pull request | Checks the change. It does not open a browser and it sends no request to a tenant. |
| `.github/workflows/qa-nightly.yml` | By hand only | Holds the QA Touch canary and a smoke job. The nightly test run is not here. It is a cron job on spartan1. |

The collect gate runs on the company repo,
`Soterix-Systems/Soterix-WebApp-QA`. Its jobs skip themselves on the
personal mirror, which has no secrets. You can start the manual workflow
from the company repo or from the mirror. Only its schedule is limited to
the company repo.

## The collect gate

A push is not done until this gate is green. To see the result:

```
gh run list -R Soterix-Systems/Soterix-WebApp-QA --limit 3
gh run watch <run-id> -R Soterix-Systems/Soterix-WebApp-QA
```

The `collect` job does these steps in order. The first step that fails
stops the job.

| Step | What it proves | If it fails |
|---|---|---|
| Imports and fixture wiring | `pytest --collect-only` and `pytest --setup-plan` work for the whole repo. | Correct the import or the fixture that the error names. |
| Collected-test floor | The number of collected tests did not fall (`tools/collect_floor.py`). | If you removed tests on purpose, run `python tools/collect_floor.py --update` and commit the result alone. If you did not, a merge lost files: find them. |
| Offline suites | `pytest tests/plugins tests/tools tests/helpers` passes. | Run the same command on your machine. |
| Test inventory is current | `docs/TEST_INVENTORY.md` agrees with the tests. | Run `python tools/test_inventory.py` and commit the file. |
| Lint | `ruff` finds nothing (`tools/lint_baseline.py`). | Correct the finding that the message names. |
| House conventions on the added lines | `tools/convention_check.py` finds no HIGH item on the lines that the push adds. | Correct the line. The pre-commit hook does the same check. |
| Commit messages | No commit in the push names an AI tool, a model or a co-author (`tools/hooks/commit-msg`). | Write the commit message again. |
| Shim guards | `tests/plugins/test_shims.py` passes. | A shim is a module in this repo that points at the shared package. Read the docstring at the top of the test file. |

The `shim-matrix` job runs the shim guards on Python 3.11, 3.12, 3.13 and
3.14.

The pre-commit hook does most of these checks before the commit. To turn
the hooks on in a new clone, run `git config core.hooksPath tools/hooks`
one time. `secret_check` runs in the hook only, because it compares with
the values in your `.env`.

The gate needs 1 secret, `QA_SHARED_DEPLOY_KEY`. See "Secrets".

## The manual workflow

`.github/workflows/qa-nightly.yml` has 2 jobs:

**The GitHub side is manual (decided 2026-08-18); the live schedule is a
cron on spartan1** (since 2026-09-01, see `docs/RUN_WORKFLOWS.md` and
`deploy/spartan1/README.md`). The canary's cron here is commented out, and
neither job has ever been run from the Actions tab as of 2026-09-08 (zero
runs in either org), so the hosted-runner reachability question the smoke
job exists to answer is still open. The workflow stays in the repo so the run
button, the guards and the secrets story are ready the day GitHub-side
scheduling is wanted.

| Job | When | What |
|---|---|---|
| `canary` | Manual (schedule paused) | `tools/qatouch_contract_check.py` - fails the run the day QA Touch changes its API again. Run it by hand before any QA Touch session after a gap |
| `smoke` | Manual | Reachability probe + a pytest target. Exists to answer whether a hosted runner can reach the QA tenant and log in (reCAPTCHA from datacenter IPs is the risk) |

## The double-burn guard

This repo is pushed to two GitHub orgs (Soterix-Systems and JustVar), so the
workflow file exists in both. Scheduled runs are guarded to the company repo:

```yaml
if: github.event_name != 'schedule' || github.repository == 'Soterix-Systems/Soterix-WebApp-QA'
```

Without it every schedule fires twice - two quota draws, two QA Touch writes.
Manual runs work from either org on purpose. Do not remove the guard.

## Minutes budget (hosted runners)

The Soterix-Systems org is on the free plan: **2,000 Linux minutes and 500 MB
of artifact storage per month, shared across every repo in the org**, reset
monthly. When they run out, jobs are blocked (no surprise bill). The canary
would cost about 30 minutes/month once its schedule is re-enabled. A
nightly full suite would not fit
(~2,700-4,500 min/month estimated); nightly smoke + weekly full (~1,350)
would. Check usage: org Settings > Billing.

Every job carries `timeout-minutes` as a hard cap, and artifacts expire after
7 days to protect the 500 MB store.

## Secrets

Set in Settings > Secrets and variables > Actions on the COMPANY repo:

| Secret | Used by | Same value as local `.env` key |
|---|---|---|
| `QATOUCH_API_KEY` | canary, uploads | `QATOUCH_API_KEY` |
| `QATOUCH_DOMAIN` | canary, uploads | `QATOUCH_DOMAIN` (e.g. `soterixsystems`) |
| `QATOUCH_PROJECT_ID` | canary, uploads | `QATOUCH_PROJECT_ID` (e.g. `JlW1`) |
| `QA_USER`, `QA_PASSWORD` | smoke login | `QA_USER`, `QA_PASSWORD` |
| `QA_SHARED_DEPLOY_KEY` | collect gate | None. It is the private half of a read-only deploy key on `Soterix-Systems/SOTERIX-QA-SHARED`. The gate uses it to install the shared package. |

If `QA_SHARED_DEPLOY_KEY` is lost, make a new key pair. Add the public half
to the shared repo as a read-only deploy key, and put the private half in
this secret. The key cannot push, and it cannot read this repo.

Never set `BUG_CREATION_ENABLED` in CI - Jira filing stays a deliberate,
local, human-triggered act.

## Self-hosted option (free minutes, lab network)

GitHub Actions separates the orchestrator (this YAML, the schedule, the run
button, the logs) from the machine. Self-hosted runners use the same YAML
and cost zero minutes, private repos included. Worth switching if the smoke
probe shows the QA tenant unreachable or reCAPTCHA blocking datacenter IPs,
or when full-suite cadence outgrows 2,000 minutes.

What it takes:

1. An always-on box with network reach to the QA tenant. Candidates today:
   spartan1 (already hosts the asset tracker) or a new small box. Not the
   laptop - removing the laptop dependency is the point.
2. Register: company repo (or org) Settings > Actions > Runners > New
   self-hosted runner, follow the three commands, give it the label
   `qa-lab`, install as a service. The runner polls GitHub outbound over
   443 - no inbound ports, and it auto-updates.
3. On the box: Python 3.14, `pip install -r requirements.txt`,
   `python -m playwright install --with-deps chrome`, ~2 GB free disk.
4. In the workflow, change `runs-on: ubuntu-latest` to
   `runs-on: [self-hosted, qa-lab]`. Nothing else changes.
5. Secrets can stay in GitHub as above, or live in a local `.env` on the
   box (the tools load it themselves) so credentials never leave the lab.

Trade-off to know: the box is a single point of failure. The YAML in the
repo is what makes that acceptable - if the box dies, register a new runner
and re-run; nothing else to rebuild.

## First-run checklist

1. Push this branch to the company repo.
2. Add the secrets in the table.
3. Actions > QA nightly > Run workflow (the `smoke` job) - read the
   reachability probe line and the login result. That answers the open
   hosted-runner question from the 2026-08-18 grounding research.
4. If green: nothing further until scheduled automation is real - then
   uncomment the canary's cron in the workflow and decide smoke cadence.
   If blocked: register a self-hosted runner (above) and re-run.
