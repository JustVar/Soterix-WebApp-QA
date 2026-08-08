# QA Touch Integration Guide

> **Last Updated:** 2026-08-07 (counts checked against the live API)

## Current State

| Metric | Value |
|--------|-------|
| **Total test cases in QA Touch (NexaiQ-Core)** | 3,108 (live count 08/07/2026; cases are added continuously) |
| **Imported from spreadsheet (v4, 02/10/2026)** | 2,868 (+6 preserved Audio) |
| **Playwright tests mapped** | 378 mappings across 352 tests (see `config/qatouch_case_mapping.json`) |
| **Import status** | Complete (v4, 02/10/2026); later cases added directly in QA Touch |

The module count is not verifiable over the API (the modules count endpoint
returns 404), so this table no longer claims one.

## Result Upload Pipeline (Built)

### Automated (pytest plugin)
```bash
# Run tests with automatic QA Touch upload
pytest tests/ --qatouch-upload --qatouch-run <RUN_KEY>
```

To also write a JSON report for the manual path, install pytest-json-report
first (it is in requirements_legacy.txt, not the active requirements) and add
`--json-report --json-report-file=report.json`.

### Manual (from JSON report)
```bash
# Upload results from a saved JSON report (positional args)
python tools/qatouch_run_manager.py upload <RUN_KEY> report.json

# Preview without uploading
python tools/qatouch_run_manager.py dry-run report.json
```

### List test runs
```bash
python tools/qatouch_run_manager.py list
```

## Pipeline Components

| Tool | Location | Purpose |
|------|----------|---------|
| **QA Touch client** | `tools/qatouch_client.py` | API client with list/get/update endpoints + status constants |
| **Case mapper** | `tools/qatouch_mapper.py` | Builds `config/qatouch_case_mapping.json` (378 mappings) |
| **pytest reporter** | `plugins/qatouch_reporter.py` | Plugin: `--qatouch-upload --qatouch-run <KEY>` |
| **Run manager** | `tools/qatouch_run_manager.py` | List runs, upload from JSON report, dry-run mode |
| **AUTOMATED tags** | `tools/qatouch_automated_tags.csv` | 78 cases tagged for bulk import |
| **SMOKE tags** | `tools/qatouch_smoke_tags.csv` | 12 cases tagged for smoke runs |

## Workflow

1. **Create test run** in the QA Touch UI, or over the API:
   `python tools/qatouch_run_manager.py create-by-tag <NAME> <USER_KEY> <MILESTONE_KEY> <TAG>`
   (also `clone`, `milestone`, `release`; run the tool without args for usage)
2. **Run tests** with `pytest --qatouch-upload --qatouch-run <KEY>` or run separately and upload JSON
3. **Results auto-uploaded** to the specified test run with pass/fail/skip status

## API Details

- **Base URL:** `https://api.qatouch.com` (NOT the subdomain URL)
- **Headers:** `api-token: <QATOUCH_API_KEY>`, `domain: <QATOUCH_DOMAIN>` (e.g. `soterixsystems`)
- **Project key:** `QATOUCH_PROJECT_ID` (e.g. `JlW1` for NexaiQ-Core)
- **Status codes:** passed=1, untested=2, blocked/skipped=3, retest=4, failed=5

## QA Touch Projects

Live list as of 08/07/2026 (`P0BK` was renamed from NexaiQ-Private Cloud):

| Project | Key | Jira Project |
|---------|-----|--------------|
| NexaiQ-Core | JlW1 | NC |
| NexaiQ-Neurosen | P0BK | TBD |
| NexaiQ-Technician App | 60w8 | TBD |
| NexaiQ-Partner Admin Tool | 70l1 | TBD |
| NexiaQ-Mobile | K5kB | TBD |
| NexaiQ-Camera 2 Cloud | 60W5 | TBD |

## Environment Variables

```
QATOUCH_API_KEY=<your-api-key>
QATOUCH_DOMAIN=soterixsystems
QATOUCH_PROJECT_ID=JlW1
```

## Security

- Never store API keys in repo. Use CI secret storage and environment variables.
- See `.env.template` for all required variables.

## Import History

| Version | Date | Cases | Notes |
|---------|------|-------|-------|
| v2 | 02/02/2026 | 1,528 | Initial import with Login/Logout/Audio preserved |
| v3 | 02/04/2026 | 2,552 | Full steps, Admin-LPR excluded (duplicate) |
| v4 | 02/10/2026 | 2,868 (+6 Audio) = 2,874 | Login, Logout, Playback Auto-Timeout, Admin-LPR added; duplicate titles resolved |

## Next Steps

- Tag test cases with REGRESSION (~500-700) for release testing
- Set up test execution plans and run creation workflows
- See `docs/NC_JIRA_QA_REFERENCE.md` for Jira field mappings
