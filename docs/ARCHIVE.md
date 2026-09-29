# What left the main branch

On 09/29/2026 the framework was cut down to 1 QA server, 1 account pair and
no scheduled run. Everything that served the old setup left the main branch.
Nothing was lost. Each of the 3 repos carries the git tag `pre-pivot` and
the branch `archive/pre-pivot`, both at the last commit before the cut:

- Soterix-WebApp-QA (this repo)
- Soterix-API-QA
- soterix-qa-shared

The archived files describe machines and tenants that no longer exist. Read
them for how a thing was done, not for what is true today.

## The restore command

To bring 1 file or folder back into the working tree:

```
git checkout pre-pivot -- <path>
```

Then read it against the current code before you commit it. A restored
file names variables and hosts that the current code does not read.

## What left, by area

| Area | What left | Where it was |
|---|---|---|
| The second tenant and the box layer | `BOX`, the `boxes` map with a per-box account pair (`QA_INDIA_*`, `QA_US_*`) and per-box test data, `get_active_box`, the `_pat` partner configs, the old per-box form of the stage, prod and Neurosen env files (the files remain, flattened), `config/environments.yaml`, `config/run_axis.py` | `config/base_config.py`, `config/env/`, `conftest.py`, `tests/shared/auth_state.py` |
| The nightly on the Linux machine | The cron nightly that ran every box in turn, the Weston service, the runner and prune scripts, the nginx site that served the archive | `deploy/spartan1/` |
| The served archive, publish and announce | The sftp publish of a run folder to the served archive, the Slack post of the expected runs, the `.evidence_scanned` marker mode of the evidence scan | `tools/publish_run.py`, `tools/announce_run.py`, `tools/evidence_scan.py --runs-dir` |
| The self-hosted CI | The runners on the Linux machine, the `CI_RUNNER` variable, the scheduled nightly workflow, the per-job venv and the deploy key for the shared package | `.github/workflows/qa-nightly.yml`, `deploy/spartan1/RUNNERS.md`, `docs/CI_ON_SPARTAN1.md` |
| The lab-camera suite | The Camera 2 Cloud tests against the web pages of the lab cameras, their page object, their camera and model data, the camera discovery tool, the c2c step files | `tests/c2c/`, `tests/shared/pages/camera_hardware_page.py`, `tests/data/c2c_*.yaml`, `tools/discover_c2c_cameras.py`, `tests/steps/c2c/` |
| Camera rotation over a measured pool | The per-box camera pool, the day index that rotated the camera, the bench that measured a pool | `tests/data/camera_pool_us.json`, `tests/shared/helpers/camera_pool.py` (the rotation half), `tools/livestream_bench.py` |
| The failure register and its audits | 135 numbered rows with owner and next action, the adversarial audit, the coverage assessment, the concurrency plan, the browser topology, the run workflows, the register rows cited from code | `docs/TEST_REPAIRS.md`, `docs/AUDIT_FINDINGS.md`, `docs/TEST_COVERAGE_ASSESSMENT.md`, `docs/CONCURRENCY_PLAN.md`, `docs/BROWSER_TOPOLOGY.md`, `docs/RUN_WORKFLOWS.md` |
| Jira and email tooling | The automatic bug filer and its field mapping, the Jira reference, the Graph mail sender and its OAuth secret reminders, the flaky-test ledger, the review queue | `tools/smart_jira_bug_creator.py`, `config/jira_field_mapping.*`, `docs/NC_JIRA_QA_REFERENCE.md`, `tools/email_client.py`, `tools/send_test_report.py`, `docs/EMAIL_REPORTS.md`, `MAINTENANCE_REMINDERS.md`, `flaky_tests.json` |
| The QA Touch migration tools | The xlsx import pipeline and its docs, the mapping regenerator, the mode sync, the suite builder and the suite hold, the run manager, the analytics snapshots and the case-count ledger, the contract canary, the full audit, the gap analysis and the sync check, the MCP launcher, the step editors (the step API and the step generator), the one-off scripts | `tools/qatouch_*.py` (the ones not listed below), `tools/qa_xlsx_*.py`, `tools/run_suite.py`, `tools/archive/`, `tools/templates/`, `docs/qa_import_pipeline.md`, `docs/qa_xlsx_import_template.md`, `docs/QATOUCH_NEW_CAPABILITIES.md`, `.mcp.json` |
| The verification review flow | The step-review sync to the QA Ops Hub and its doc | `tools/sync_verification_status.py`, `docs/VERIFICATION_WORKFLOW.md` |
| The two-remote review | The overlap report between the personal and the company remote | `tools/team_changes.py`, `docs/TEAM_CHANGES.md` |
| Old plans and records | The 19 session summaries and plans of `docs/archive/`, the hardware and methodology material of `docs/reference/`, the repo split record, the time tracking guide, the legacy Selenium tests and their pages | `docs/archive/`, `docs/reference/`, `docs/REPO_SPLIT_PLAN.md`, `docs/TIME_TRACKING_GUIDE.md`, `docs/TRIPLE_HELIX_METHODOLOGY.md`, `tests/legacy/`, `pages/`, `data/` |
| The credentials guide | The multi-environment credentials guide, written for the box accounts and a 1Password vault | `docs/CREDENTIALS_SETUP.md` |
| The tracked run ledger | The `history/` folder: the monthly run ledger, the test-count ledger and the QA Touch case-count ledger, with the tools that appended to the last two. A run with `--qatouch-upload` still appends the run ledger on the machine that ran it, and `.gitignore` now keeps `history/` out | `history/`, `tools/qatouch_ledger.py`, the ledger half of `tools/test_inventory.py` |
| The lint baseline gate | The per-file ruff baseline and the tool that failed a file that gained findings, with its pin. The baseline was 0, so `ruff check .` is the whole gate now | `config/lint_baseline.json`, `tools/lint_baseline.py`, `tests/tools/test_lint_baseline.py` |
| The lab cameras behind the suite | The Camera 2 Cloud suite drove lab cameras that are being removed. A restore of the suite also needs a new camera registry file, in the shape of `tests/data/c2c_cameras.yaml` | The lab. The file gives the shape |
| Data files nothing read (removed after the tag, restorable from it) | The outputs of the QA Touch migration tools: the affected-key, feature and repository inventories, the module navigation and generated-step files, the contract baseline, the dashboard metrics, the duplicate-module and rename plans, the sanity-run CSVs, the tag ids, the step sync checkpoints, the PTZ suite hold, the snapshots of the 3 QA Touch projects no test root reports to, and the Selenium-era pin file that nothing installed | Every `config/*.json` and `config/*.csv` except `config/collect_floor.json` and `config/qatouch_case_mapping.json`, `config/qatouch_suite_holds/`, `config/qatouch_snapshots/60w8/`, `config/qatouch_snapshots/70l1/`, `config/qatouch_snapshots/K5kB/`, `requirements_legacy.txt` |

## What stayed, and why

- `tools/qatouch_cases_from_tests.py`, `tools/qatouch_csv_import.py`,
  `tools/qatouch_mapping.py`, `tools/qatouch_mapping_audit.py`,
  `tools/qatouch_client.py`, `tools/retry_uploads.py`,
  `tools/validate_run.py` and `plugins/qatouch_reporter.py`. They are the
  way to upload results and to create cases in a new QA Touch project.
  Nothing runs without `--qatouch-upload`.
- `deploy/windows-runner/`. The scripts for a scheduled run on a Windows
  machine, with the box loop removed. Nothing is registered.
- `docs/LINUX_H265.md`. The 1 lesson from the Linux machine that any future
  Linux runner needs.
- `config/known_defects.yaml`. Empty, with its shape in the header.
- The single-run guard, the preflight, the stream guard, the evidence scan
  and the 6 pre-commit checks. They are what makes a run readable, safe to
  share and safe to change on any machine.

## Two things worth reading later

- The served-archive recipe: `deploy/spartan1/nginx-qa-runs.conf`,
  `deploy/spartan1/setup-publish-user.sh` and `tools/publish_run.py`, for
  the day a host exists again.
- The rule in `docs/CI_ON_SPARTAN1.md` that a self-hosted runner never runs
  a pull request, if self-hosting is ever reconsidered.
