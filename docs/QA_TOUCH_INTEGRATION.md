# QA Touch Integration Guide

**This is the source of truth for how our code talks to QA Touch.** If another
document disagrees with this one, this one is right and the other is stale.

> **Last verified:** 2026-08-17 against the live API.

---

## Which document owns what

Four QA Touch documents exist. Each owns one subject. Nothing is duplicated on
purpose - if you find the same fact in two of them, the copy outside its owner
is stale.

| Document | Owns | Audience |
|---|---|---|
| **This file** | API contracts, endpoints, traps, project keys, env vars | Engineers |
| `QA_TOUCH_TEAM_GUIDE.md` | Day-to-day QA Touch use: suites, runs, tagging, holds | The QA team |
| `QATOUCH_NEW_CAPABILITIES.md` | Vendor features since 03/2026 and whether to adopt them | Engineers |
| `docs/local/qa_touch_integration.md` | Deep reverse-engineering notes, numbered sections (§7.A.1 etc.) | Maintainer only (gitignored) |

`docs/QA_Touch_Setup_Guide.md` is the original February setup walkthrough. It
is finished work, kept locally for history, and **must not be used for current
figures**. Same for `docs/local/qa_touch_import_capture_protocol.md`.

---

## Current state

Read live. Do not hand-maintain a copy of this table anywhere else.

| Metric | Value | Source |
|---|---|---|
| Test cases (NexaiQ-Core, `JlW1`) | 3,096 | live API, 08/17/2026 |
| Modules | 448 | live API, 08/17/2026 |
| Cases with steps | 3,096 (100%) | live API, 08/17/2026 |
| Playwright tests mapped | 378 mappings across 352 tests | `config/qatouch_case_mapping.json` |

```bash
python tools/qatouch_run_manager.py list                    # open test runs
python tools/qatouch_suite_hold.py status --modules PTZ     # tag state per module
```

The count grows continuously as cases are authored. A number written into a
document is wrong the week after. The February import totals are in
[Import history](#import-history) and are history, not current state.

---

## Four traps that will waste your day

All four were measured on 2026-08-17. The first three fail **silently** - the
API returns success and changes nothing. **Never trust an HTTP 200 from QA
Touch. Read the value back.**

`tools/qatouch_contract_check.py` is the canary that watches for the next one.
Run it on a schedule; it exits non-zero the moment the API drifts.

### 1. Response field names changed and nothing announced it

Some time after 2026-03-27 the public API renamed test-case fields:

| Old | New |
|---|---|
| `module name` | `module_name` |
| `NewTags` (comma string) | `Tags` (list) |
| `created by` / `created date` / `updated date` | `created_by` / `created_date` / `updated_date` |

Every tool that read the old names kept running and silently reported
`"Unknown"`. It went unnoticed for five months. The OpenAPI spec at
`doc.qatouch.com/openapi.yaml` documents **no test-case response fields at
all**, so no document could have warned us.

`QATouchClient.list_test_cases()` now attaches both spellings to every case
(`add_legacy_case_aliases`), so old and new readers both work.

### 2. Clearing tags needs `[""]`, not `[]`

Internal endpoint `POST /v1/case/update/p/{project}/cid/{case}`:

| `newtags` sent | Result |
|---|---|
| `["99GQ"]` (non-empty) | applied |
| `[]` | **ignored** - answers `{"status": true, "msg": "Case Updated Successfully"}` |
| `null` | ignored, same false success |
| `""` | ignored, same false success |
| `[""]` | **all tags cleared** |

QA Touch reads `[]`, `null` and `""` as "field not supplied". A list holding
one empty string is the explicit "no tags" signal.

### 3. Test-run results identify a case by stripped case CODE

Public endpoint `PATCH /api/v1/testRunResults/status/multiple`:

| `case` value sent | Result |
|---|---|
| `B869bm` (case key) | ignored, false success |
| `TR0262` (full code) | ignored, false success |
| `w5BNkb` (per-run result key) | ignored, false success |
| **`262`** (code, no `TR`, no leading zeros) | applied |

Use `case_code_to_ref()` in `tools/qatouch_client.py`.

> **This was not hypothetical. Confirmed 2026-08-17 and fixed.**
> `plugins/qatouch_reporter.py` sent the per-run result key, so **every
> automated result upload silently did nothing**. Both of its fallback forms
> (result key and case key) are ignored by the API. Uploads now go through
> `update_test_run_results_by_code()` and the reporter reads the run back
> after every upload, failing loudly if the statuses did not land.

### Use the case-code endpoint for results

`POST /api/v1/testRunResults/testrun/code` is the endpoint to use. It takes
the **full** case code (`TR0263`, prefix included) and its reply names the case
it changed:

```
{"success": true, "msg": "TR0263 - Updated Successfully"}
```

That makes a no-op visible, which `status/multiple` does not. It also accepts
file attachments (png/pdf/jpg/csv/log, 2 MB) for screenshots - not wired up yet.

`QATouchClient.update_test_run_results_by_code()` implements it.

### 4. The same status has two spellings

QA Touch spells statuses differently depending on which endpoint you ask:

| Endpoint | Code 6 | Code 7 |
|---|---|---|
| `getAvailableStatuses` | `Not-Applicable` | `In-Progress` |
| test run result reads | `Not Applicable` | `In Progress` |

An `==` comparison between the two is wrong, and wrong quietly - it reports
"status did not change" for a status that did. Compare through
`normalize_status_name()` in `tools/qatouch_client.py`, which folds hyphens,
spaces and case to one form. `STATUS_NAMES` there is the single definition of
the status names; do not re-declare them per tool.

---

## API details

**Public API** - needs only the API key, works headless and in CI.

- Base URL `https://api.qatouch.com` (NOT the subdomain URL)
- Headers: `api-token: <QATOUCH_API_KEY>`, `domain: <QATOUCH_DOMAIN>`
- Spec: `https://doc.qatouch.com/openapi.yaml` (endpoints only - no response schemas)

**Internal browser API** - needs a logged-in browser session, expires every few
weeks. Used only for what the public API cannot do.

- `POST /v1/case/edit/p/{project}/cid/{case}` - read a full case
- `POST /v1/case/update/p/{project}/cid/{case}` - write a full case
- **Tags are browser-only.** The public API has no tag read or write. Its only
  `tags` reference is an input filter when creating a run.

### Result status codes

Verified against `GET /api/v1/testRuns/getAvailableStatuses`.

| Code | Status | | Code | Status |
|---|---|---|---|---|
| 1 | Passed | | 5 | Failed |
| 2 | Untested | | 6 | Not Applicable |
| 3 | Blocked (also used for skipped) | | 7 | In Progress |
| 4 | Retest | | 8 | Hold |

### Suite tag IDs

Config: `config/qatouch_tag_ids.json`

| Tag | Hash ID |
|---|---|
| `smoke` | `99GQ` |
| `sanity` | `X1zZ` |
| `regression` | `MW0N` |

### Useful filters

`getAllTestCases` accepts `moduleKey`, `mode`, `approvalstatus`,
`requirementKey`, `view=count|list` - one at a time. Filtering server-side
turned a 3,096-case paginated pull into one call returning 8. The API
rate-limits bursts with HTTP 429, so prefer the filter.

`GET /api/v1/getTestRunlist/{caseKey}` returns every run holding a case, with
its `resultKey` and current status.

---

## Result upload pipeline

```bash
# Automatic upload from a pytest run
pytest tests/ --qatouch-upload --qatouch-run <RUN_KEY>

# From a saved JSON report
python tools/qatouch_run_manager.py upload <RUN_KEY> report.json
python tools/qatouch_run_manager.py dry-run report.json     # preview
python tools/qatouch_run_manager.py list                    # list runs
```

For the JSON path install `pytest-json-report` (it sits in
`requirements_legacy.txt`, not the active requirements) and add
`--json-report --json-report-file=report.json`.

Components: `plugins/qatouch_reporter.py` (pytest plugin),
`tools/qatouch_client.py` (API client), `config/qatouch_case_mapping.json`
(test to case mapping), `tools/qatouch_mapper.py` (rebuilds the mapping).

---

## QA Touch projects

| Project | Key | Jira Project |
|---|---|---|
| NexaiQ-Core | `JlW1` | NC |
| NexaiQ-Neurosen | `P0BK` | TBD |
| NexaiQ-Technician App | `60w8` | TBD |
| NexaiQ-Partner Admin Tool | `70l1` | TBD |
| NexiaQ-Mobile | `K5kB` | TBD |
| NexaiQ-Camera 2 Cloud | `60W5` | TBD |

## Environment variables

```
QATOUCH_API_KEY=<your-api-key>
QATOUCH_DOMAIN=soterixsystems
QATOUCH_PROJECT_ID=JlW1
```

Never commit API keys. Use CI secret storage. See `.env.template`.

---

## Import history

Finished work. Kept to explain where the case base came from. **Do not quote
these as current counts** - several older documents do, which is why they
disagree with each other.

| Version | Date | Cases | Notes |
|---|---|---|---|
| v2 | 02/02/2026 | 1,528 | Initial import, Login/Logout/Audio preserved |
| v3 | 02/04/2026 | 2,552 | Full steps, Admin-LPR excluded as duplicate |
| v4 | 02/10/2026 | 2,868 (+6 Audio) = 2,874 | Login, Logout, Playback Auto-Timeout, Admin-LPR added; duplicate titles resolved |

Everything above 2,874 was authored or scaffolded directly in QA Touch after
the import. The live runbook for new imports is `docs/qa_import_pipeline.md`.

---

## Contract canary

QA Touch changes its API without telling anyone. The March 2026 field rename
went unnoticed for five months. This guards against the next one:

```bash
python tools/qatouch_contract_check.py            # exits 1 on drift
python tools/qatouch_contract_check.py --verbose  # show every check
python tools/qatouch_contract_check.py --update   # re-record after an intended change
```

It checks the case response fields, our legacy aliases, the status codes, the
tag IDs and the endpoints we depend on, all against
`config/qatouch_contract_baseline.json`.

**When it fails, work out which side is wrong first.** If QA Touch changed
something we must follow, fix our code, then `--update`. Never `--update` to
silence a failure you have not understood - that is how the last drift stayed
invisible.

It found trap 4 on its first run.

---

## Related

- `docs/QA_TOUCH_TEAM_GUIDE.md` - how the QA team uses QA Touch
- `docs/QATOUCH_NEW_CAPABILITIES.md` - vendor features since 03/2026
- `docs/qa_import_pipeline.md` - xlsx to QA Touch import runbook
- `docs/NC_JIRA_QA_REFERENCE.md` - Jira field mappings
