# CI - scheduled automation

One workflow: `.github/workflows/qa-nightly.yml`. It is the scheduler for
everything that must not depend on one laptop. Two jobs:

**Everything is manual for now (decided 2026-08-18).** Tests run by hand, and
the canary's nightly cron is commented out in the workflow - automations are
not fully built or in use yet, so a schedule would watch an API nobody is
writing to. The workflow stays in the repo so the run button, the guards and
the secrets story are ready the day scheduling starts.

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
2. Add the five secrets.
3. Actions > QA nightly > Run workflow (the `smoke` job) - read the
   reachability probe line and the login result. That answers the open
   hosted-runner question from the 2026-08-18 grounding research.
4. If green: nothing further until scheduled automation is real - then
   uncomment the canary's cron in the workflow and decide smoke cadence.
   If blocked: register a self-hosted runner (above) and re-run.
