# QA Touch Integration Guide

> **Last Updated:** 2026-02-10

## Current State

| Metric | Value |
|--------|-------|
| **Total test cases in QA Touch** | 2,874 |
| **Imported from spreadsheet (v4)** | 2,868 |
| **Preserved (Audio)** | 6 |
| **Unique modules** | 468 |
| **Playwright tests mapped** | 132/152 (87%) |
| **Import status** | Complete (v4, 02/10/2026) |

## Result Upload Pipeline (Built)

### Automated (pytest plugin)
```bash
# Run tests with automatic QA Touch upload
pytest tests/ --qatouch-upload --qatouch-run <RUN_KEY> --json-report --json-report-file=report.json
```

### Manual (from JSON report)
```bash
# Upload results from a saved JSON report
python tools/qatouch_run_manager.py upload --run <RUN_KEY> --file report.json

# Dry-run (preview without uploading)
python tools/qatouch_run_manager.py upload --run <RUN_KEY> --file report.json --dry-run
```

### List test runs
```bash
python tools/qatouch_run_manager.py list
```

## Pipeline Components

| Tool | Location | Purpose |
|------|----------|---------|
| **QA Touch client** | `tools/qatouch_client.py` | API client with list/get/update endpoints + status constants |
| **Case mapper** | `tools/qatouch_mapper.py` | Builds `config/qatouch_case_mapping.json` (132/152 = 87% mapped) |
| **pytest reporter** | `plugins/qatouch_reporter.py` | Plugin: `--qatouch-upload --qatouch-run <KEY>` |
| **Run manager** | `tools/qatouch_run_manager.py` | List runs, upload from JSON report, dry-run mode |
| **AUTOMATED tags** | `tools/qatouch_automated_tags.csv` | 78 cases tagged for bulk import |
| **SMOKE tags** | `tools/qatouch_smoke_tags.csv` | 12 cases tagged for smoke runs |

## Workflow

1. **Create test run** in QA Touch UI (API not supported for run creation)
2. **Run tests** with `pytest --qatouch-upload --qatouch-run <KEY>` or run separately and upload JSON
3. **Results auto-uploaded** to the specified test run with pass/fail/skip status

## API Details

- **Base URL:** `https://api.qatouch.com` (NOT the subdomain URL)
- **Headers:** `api-token: <QATOUCH_API_KEY>`, `domain: <QATOUCH_DOMAIN>` (e.g. `soterixsystems`)
- **Project key:** `QATOUCH_PROJECT_ID` (e.g. `JlW1` for NexaiQ-Core)
- **Status codes:** passed=1, untested=2, blocked/skipped=3, retest=4, failed=5

## QA Touch Projects

| Project | Key | Jira Project |
|---------|-----|--------------|
| NexaiQ-Core | JlW1 | NC |
| NexaiQ-Private Cloud | P0BK | TBD |
| NexaiQ-Technician App | 60w8 | TBD |
| NexaiQ-Partner Admin Tool | 70l1 | TBD |

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

- Re-run `python tools/qatouch_mapper.py` to rebuild case mapping after v4 import
- Tag test cases with REGRESSION (~500-700) for release testing
- Set up test execution plans and run creation workflows
- See `docs/NC_JIRA_QA_REFERENCE.md` for Jira field mappings
- QA Touch import complete (2,969 cases) - see `config/qatouch_case_mapping.json` for automation mappings
