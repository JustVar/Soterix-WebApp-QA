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
| Playwright tests mapped | 378 rows, of which **134 reviewed** (usable) - the rest are held proposals | `config/qatouch_case_mapping.json` + `tools/qatouch_mapping.py status` |

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
- **Tags are browser-only for EXISTING cases.** The public API has no tag read
  or update endpoint. The one exception is creation: a `tags` column in the CSV
  import sets tags on a new case (see below). Changing the tags on a case that
  already exists needs this browser endpoint.

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
`requirementKey`, `view=count|list` - one at a time (`mode` may pair with
`view` or `page`). Filtering server-side turned a 3,096-case paginated pull
into one call returning 8. The API rate-limits bursts with HTTP 429, so
prefer the filter.

Three quirks of the `mode` filter, measured 2026-08-17: the value is
case-sensitive (`Automation` / `Manual`; the documented lowercase returns
"Provided Mode not found"); a filtered response reports `meta.last_page = 1`
whatever the total; and its `link.next` drops the filter. Page by computing
`total / per_page`. `tools/qatouch_mode.py` does this.

`GET /api/v1/getTestRunlist/{caseKey}` returns every run holding a case, with
its `resultKey` and current status.

---

## Updating an existing case

`POST /api/v1/testcase/update` via `QATouchClient.update_test_case()`.

**It is a partial update.** Send only the fields you want changed; the rest
keep their values. Measured 2026-08-17 - changing `precondition` left the
title, description, type, priority, module and tags untouched. That makes it
much safer than the browser endpoint, which needs the whole case echoed back
and silently drops whatever you forget.

| Field | Public API |
|---|---|
| title, description, precondition | yes |
| reference, estimate | yes |
| type, priority, mode | yes |
| **module (sectionKey)** | **no - accepted, answers success, does not move the case** |
| **tags** | **no - no parameter exists** |
| steps, BDD | separate endpoints, different semantics |

The `sectionKey` no-op is the same silent-success pattern as the other traps:
verified by moving a case between two PTZ modules and reading it back - it
never left. `update_test_case()` refuses the field rather than pretend.

### What this does and does not buy us

It removes the browser dependency for **plain metadata edits only**. The three
things our tooling actually does most still need a logged-in session:

| Tool | Writes | Can it move to the public API? |
|---|---|---|
| `qatouch_mode.py` (was `qatouch_api_mode_update.py` + `qatouch_set_mode.py`) | mode | **Done - on the public API, with read-back** |
| `backfill_qa_touch_metadata.py` | metadata + tags + steps | Partly - the metadata half |
| `qatouch_norun_update.py` | precondition + NO_RUN tag | Partly - the precondition half |
| `archive/reorganize_ldap_cases.py` (finished one-off) | module moves | No - browser only |
| `split_merged_steps.py`, `detect_merged_steps.py`, `qa_post_import_split_and_position.py` | surgical step edits | No |
| `qatouch_api_tag_update.py`, `qatouch_suite_hold.py` | tags | No |

So the QA Touch login is not going away. It gets needed less often.

---

## CSV import (public, create-only)

`POST /api/v1/testCase/import?projectKey={key}`, multipart body, field `file`,
up to 100 cases per request. Needs only the API key.

Every column below is mandatory - the controller indexes the row without
checking, so one missing column fails the row with `Undefined index: <column>`:

```
module_name, title, test_case_title, description, precondition, test_data,
steps, expected_result, tags, type, priority, mode, estimate, reference,
test_suite
```

These are NOT the column names our own converter emits. `tools/qa_xlsx_to_qatouch_csv.py`
targets the browser import wizard and uses `section_name` and `newtags`;
this endpoint wants `module_name` and `tags`.

The reply is honest, unlike the rest of this API:

```
{"success": true, "total": 34, "imported": 34, "failed": 0, "errors": []}
```

A rejected row creates nothing and names the column and row number, so probing
it is free.

**Create-only.** A `case_key` column is ignored - it creates a duplicate rather
than updating. Tags DO land on create, which is the only way to set a tag
through the public API.

**Multi-line steps split themselves.** Newline-separated `steps` and
`expected_result` cells arrive as separate step rows, each with its own
expected result. The browser pipeline needed a post-import step splitter for
this; the public endpoint does not.

Use `tools/qatouch_csv_import.py`. It takes our canonical CSV, translates the
column names, folds our one-step-per-row continuation rows into a single case,
and chunks at 100:

```bash
python tools/qatouch_csv_import.py preview cases.csv --project JlW1
python tools/qatouch_csv_import.py import  cases.csv --project JlW1
```

Preview first, every time. There is no delete API - a case created by mistake
has to go through the manual DELETE-REQUEST process.

---

## Result upload pipeline

One command runs a suite into a fresh QA Touch run and proves the results
landed:

```bash
python tools/run_suite.py tests/ui/views --env qa --version 1.8.0
python tools/run_suite.py tests/ui/admin/test_admin_general.py --dry-run   # plan only
```

It collects the tests, maps them to cases through
`config/qatouch_case_mapping.json`, creates a run holding exactly those
cases (so nothing sits Untested for want of a test), runs pytest with
`--qatouch-upload`, then reads the run back and reconciles it case by case
against `logs/last_run_results.json`. Needs `QATOUCH_ASSIGN_TO` and
`QATOUCH_MILESTONE_KEY` in `.env` (see `qatouch_run_manager.py users` /
`milestone`).

The pieces, each usable on its own:

| Tool | Does |
|---|---|
| `plugins/qatouch_reporter.py` | pytest plugin. Resolves case codes from the run, uploads via the code endpoint, reads back and fails loudly if a status did not land |
| `tools/validate_run.py <RUN_KEY>` | Reconciles the run against the last local results, case by case. This is what catches an upload the API accepted and discarded |
| `tools/retry_uploads.py` | Replays `logs/upload_failures.json`, verifies each retry, quarantines entries that can never land |
| `tools/qatouch_mode.py sync` | Compares the Playwright mapping with the cases marked Mode=Automation and reports both mismatch directions; `--apply` fixes the safe one |
| `tools/qatouch_run_manager.py` | Runs, milestones, users, manual JSON upload |
| `tools/qatouch_mapper.py` | Rebuilds the test-to-case mapping. New matches enter as **unreviewed proposals** (floor 0.75, already-claimed cases refused) |
| `tools/qatouch_mapping.py` | The review gate and rename guard. `status`, `check` (exit 1 on renamed/deleted mapped tests), `list-unreviewed`, `mark-reviewed` |

**A mapping row is a proposal until a human reviews it.** 330 of the 378
rows were auto-matched by word overlap - guesses. The reporter, run_suite
and mode sync use only rows with `"reviewed": true`; everything else is
held back and the skip is printed, never silent. Bootstrap (2026-08-20)
marked the 48 manual rows and 86 clean score-1.0 rows reviewed; 244 await
review via `python tools/qatouch_mapping.py list-unreviewed`, and marking a
row reviewed means you checked the test really verifies that case. Renamed
tests are caught by `python tools/qatouch_mapping.py check`.

**Mode=Automation is the source of truth for "this case is automated".** The
mapping is the link between a test and a case; the case's Mode is the
status the whole team can see. `qatouch_mode.py sync` is what keeps them
aligned. As of 2026-08-17: 275 mapped, 271 Automation, 264 aligned, 11
mapped-but-Manual, 7 Automation-but-unmapped.

The `smoke` / `sanity` pytest markers are **not** the same thing as the QA
Touch SMOKE / SANITY suites. `-m smoke` collects the 132 C2C hardware tests,
none of which map to a case. Target directories or files, not markers, until
that is redesigned.

Bug filing to Jira happens only when `--file-bugs` is passed AND
`BUG_CREATION_ENABLED=true` - failures going straight to Jira is not the
intended end state.

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

## MCP server (for asking questions, not for automation)

The official `qatouch-mcp-server` is wired into this repo. Your MCP client
starts it automatically from `.mcp.json` - nothing to configure if your `.env`
already works for the other QA Touch tools.

```
.mcp.json  ->  python tools/qatouch_mcp_launch.py  ->  npx -y qatouch-mcp-server
```

`tools/qatouch_mcp_launch.py` exists because the server wants
`QATOUCH_API_TOKEN` in its environment while our credentials sit in the
gitignored `.env` under `QATOUCH_API_KEY`. The launcher bridges the two so
`.mcp.json` never holds a token and can be committed safely. It is stdlib-only
on purpose - the MCP client may not use the repo venv - so do not add imports
that need installing.

To check it starts:

```bash
python tools/qatouch_mcp_launch.py     # waits on stdin = healthy, Ctrl+C to stop
```

Needs Node.js 18 or newer on PATH.

**Use it for** asking what a module covers, searching cases and defects,
checking run results without writing a script. 49 tools, all reads and creates.

**Do not use it for** suite tagging, holds, or CI result uploads. It has no tag
tools at all, cannot update an existing case, and is a stdio server that a
pytest plugin cannot call. Those stay in `tools/`. Full reasoning in
`QATOUCH_NEW_CAPABILITIES.md`.

**Two things to know:**

- **It sends usage analytics to QA Touch.** Every tool call posts to
  `api.qatouch.com/api/v1/mcp/usage` with the tool name, status, duration,
  your domain and a masked token. Nothing secret leaves, but the vendor sees
  which tools you use and when.
- **Its count disagrees with pagination.** `count_test_cases` reported 3,108
  for `JlW1` on 2026-08-17 while paging every case yielded 3,096. Twelve cases
  of difference, unexplained. Trust the paginated list when the number matters.
- Arguments are camelCase (`projectKey`), not snake_case.

---

## Contract canary

QA Touch changes its API without telling anyone. The March 2026 field rename
went unnoticed for five months. This guards against the next one:

```bash
python tools/qatouch_contract_check.py            # exits 1 on drift
python tools/qatouch_contract_check.py --verbose  # show every check
python tools/qatouch_contract_check.py --update   # re-record after an intended change
```

It runs nightly in CI - `.github/workflows/qa-nightly.yml`, see `docs/CI.md`
for the schedule, the double-burn guard and the secrets it needs.

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
