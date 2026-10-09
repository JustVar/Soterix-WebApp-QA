# QA Touch integration

How this repo talks to QA Touch. Read this page only if the team uploads
results to QA Touch or creates cases there. A plain run contacts nothing
but the QA server. The testers' page is
[QA_TOUCH_TEAM_GUIDE.md](QA_TOUCH_TEAM_GUIDE.md).

## Turn it on

Three lines in `.env`:

```
QATOUCH_API_KEY=<your API key>
QATOUCH_DOMAIN=<your domain, the part before .qatouch.com>
QATOUCH_PROJECT_ID=<the project key>
```

Never commit an API key. Then 1 upload:

```
venv\Scripts\python.exe -m pytest tests/ui/views --qatouch-upload --qatouch-run <run key>
```

The reporter (`plugins/qatouch_reporter.py`) maps each test to its case
through `config/qatouch_case_mapping.json`, uploads the results to the run
with that key, reads the run back, and fails loudly if a status did not
land. A skip uploads as Blocked, never Passed. Run uploads without `-n`.

Two tools check and repair an upload:

| Tool | Does |
|---|---|
| `tools/validate_run.py <run key>` | Reconciles the run against the last local results, case by case. This catches an upload the API accepted and discarded |
| `tools/retry_uploads.py` | Replays `logs/upload_failures.json`, verifies each retry, and quarantines the entries that can never land |

## The mapping and the reviewed gate

- **The mapping lives in `config/qatouch_case_mapping.json` only**, node
  id to case key. Never in a test file. The reporter honors a
  `@pytest.mark.qatouch("KEY")` marker, and the convention checker
  refuses one in a test file.
- **A mapping row is a proposal until a human reviews it.** The reporter
  uses only rows with `"reviewed": true`. Everything else is held back,
  and the skip is printed, never silent. Marking a row reviewed means you
  checked that the test really verifies that case.

```
venv\Scripts\python.exe tools/qatouch_mapping.py status            # reviewed / unreviewed / orphaned / shared
venv\Scripts\python.exe tools/qatouch_mapping.py check             # exit 1 when a mapped test no longer exists
venv\Scripts\python.exe tools/qatouch_mapping.py list-unreviewed
venv\Scripts\python.exe tools/qatouch_mapping.py mark-reviewed <node id>
```

`tools/qatouch_mapping_audit.py` reports rows whose test and case
disagree.

## Create cases in a new project

A test's case is written from its docstring (CONVENTIONS.md, "Adding a
test"). Three commands, from the repo root:

```
venv\Scripts\python.exe tools/qatouch_cases_from_tests.py --file tests/ui/views/test_views_basic.py
venv\Scripts\python.exe tools/qatouch_csv_import.py preview logs/qatouch_new_cases_<date>.csv --project <key>
venv\Scripts\python.exe tools/qatouch_csv_import.py import  logs/qatouch_new_cases_<date>.csv --project <key>
venv\Scripts\python.exe tools/qatouch_cases_from_tests.py --after-import logs/qatouch_new_cases_<date>.csv --project <key>
```

The first writes the case CSV and a Markdown preview under `logs/`.
`--unmapped` selects every test with no mapping row across the tree.
Preview first, every time: the import is create-only, there is no delete
API, and a case created by mistake goes through the manual DELETE-REQUEST
process. The last command reads the cases back, matches the CSV's
Reference column (the node id) to each new case, and writes the mapping
rows. `python tools/generate_step_stubs.py --from-docstrings <file>`
refreshes the JSON step sidecars under `tests/steps/ui/<module>/` from the
same docstrings and keeps each case key.

`config/qatouch_snapshots/` holds the newest JSON snapshot of the cases
for each project, the backup of the authored steps. `--after-import`,
`--dead-keys` and `tools/qatouch_mapping_audit.py` read the newest
snapshot, or the file you pass with `--cases`. The older snapshots are
under the git tag `pre-pivot` (docs/ARCHIVE.md). The tool that took a
snapshot left the main branch (docs/ARCHIVE.md). A snapshot is a JSON list
of cases as `getAllTestCases` returns them.

## Four traps that will waste your day

All 4 were measured. The first 3 fail **silently**: the API returns
success and changes nothing. **Never trust an HTTP 200 from QA Touch. Read
the value back.**

### 1. Response field names changed and nothing announced it

The public API renamed test-case fields once:

| Old | New |
|---|---|
| `module name` | `module_name` |
| `NewTags` (comma string) | `Tags` (list) |
| `created by` / `created date` / `updated date` | `created_by` / `created_date` / `updated_date` |

Every tool that read the old names kept running and silently reported
`"Unknown"`. The OpenAPI spec at `doc.qatouch.com/openapi.yaml` documents
no test-case response fields at all, so no document could have warned us.
`QATouchClient.list_test_cases()` attaches both spellings to every case
(`add_legacy_case_aliases`), so old and new readers both work.

### 2. Clearing tags needs `[""]`, not `[]`

Internal endpoint `POST /v1/case/update/p/{project}/cid/{case}`:

| `newtags` sent | Result |
|---|---|
| `["99GQ"]` (non-empty) | applied |
| `[]` | **ignored**. Answers `{"status": true, "msg": "Case Updated Successfully"}` |
| `null` | ignored, same false success |
| `""` | ignored, same false success |
| `[""]` | **all tags cleared** |

QA Touch reads `[]`, `null` and `""` as "field not supplied". A list
holding 1 empty string is the explicit "no tags" signal.

### 3. Test-run results identify a case by stripped case CODE

Public endpoint `PATCH /api/v1/testRunResults/status/multiple`:

| `case` value sent | Result |
|---|---|
| `B869bm` (case key) | ignored, false success |
| `TR0262` (full code) | ignored, false success |
| `w5BNkb` (per-run result key) | ignored, false success |
| **`262`** (code, no `TR`, no leading zeros) | applied |

The reporter once sent the per-run result key, so every automated upload
silently did nothing. Uploads now go through
`POST /api/v1/testRunResults/testrun/code`, which takes the **full** case
code (`TR0263`, prefix included) and names the case it changed in its
reply: `{"success": true, "msg": "TR0263 - Updated Successfully"}`. That
makes a no-op visible. It also accepts file attachments (png, pdf, jpg,
csv, log, 2 MB) for screenshots.
`QATouchClient.update_test_run_results_by_code()` implements it, and the
reporter reads the run back after every upload.

### 4. The same status has 2 spellings

| Endpoint | Code 6 | Code 7 |
|---|---|---|
| `getAvailableStatuses` | `Not-Applicable` | `In-Progress` |
| test run result reads | `Not Applicable` | `In Progress` |

An `==` comparison between the 2 is wrong, and wrong quietly. Compare
through `normalize_status_name()` in `tools/qatouch_client.py`, which
folds hyphens, spaces and case to 1 form. `STATUS_NAMES` there is the
single definition of the status names.

## API details

**Public API.** Needs only the API key, works headless.

- Base URL `https://api.qatouch.com` (NOT the subdomain URL)
- Headers: `api-token: <QATOUCH_API_KEY>`, `domain: <QATOUCH_DOMAIN>`
- Spec: `https://doc.qatouch.com/openapi.yaml` (endpoints only, no
  response schemas)

**Internal browser API.** Needs a logged-in browser session, which
expires every few weeks. The tools that used it left the main branch. The
facts, for whoever brings one back:

- `POST /v1/case/edit/p/{project}/cid/{case}` reads a full case, and
  `POST /v1/case/update/p/{project}/cid/{case}` writes one.
- Tags are browser-only for EXISTING cases. The public API has no tag read
  or update endpoint. The 1 exception is creation: a `tags` column in the
  CSV import sets tags on a new case.
- A tag the project has never seen fails the whole import row with the
  server's own error, and nothing is created. Create a new label once in
  the QA Touch UI before the API will accept it. The Mode column, not a
  tag, marks a case as automation.

### Result status codes

Verified against `GET /api/v1/testRuns/getAvailableStatuses`.

| Code | Status | | Code | Status |
|---|---|---|---|---|
| 1 | Passed | | 5 | Failed |
| 2 | Untested | | 6 | Not Applicable |
| 3 | Blocked (also used for skipped) | | 7 | In Progress |
| 4 | Retest | | 8 | Hold |

### Useful filters

`getAllTestCases` accepts `moduleKey`, `mode`, `approvalstatus`,
`requirementKey`, `view=count|list`, 1 at a time (`mode` may pair with
`view` or `page`). A server-side filter turns a paginated pull of every
case into 1 call. The API rate-limits bursts with HTTP 429, so prefer the
filter.

Three quirks of the `mode` filter: the value is case-sensitive
(`Automation` / `Manual`, the documented lowercase returns "Provided Mode
not found"). A filtered response reports `meta.last_page = 1` whatever the
total. Its `link.next` drops the filter. Page by computing
`total / per_page`.

`GET /api/v1/getTestRunlist/{caseKey}` returns every run holding a case,
with its `resultKey` and current status.

### Updating an existing case

`POST /api/v1/testcase/update` via `QATouchClient.update_test_case()`. It
is a partial update: send only the fields you want changed, and the rest
keep their values.

| Field | Public API |
|---|---|
| title, description, precondition | yes |
| reference, estimate | yes |
| type, priority, mode | yes |
| **module (sectionKey)** | **no. Accepted, answers success, does not move the case** |
| **tags** | **no. No parameter exists** |
| steps, BDD | separate endpoints, different semantics |

`update_test_case()` refuses the `sectionKey` field rather than pretend.

### CSV import (public, create-only)

`POST /api/v1/testCase/import?projectKey={key}`, multipart body, field
`file`, up to 100 cases per request. Needs only the API key. Every column
below is mandatory. A missing column fails the row with
`Undefined index: <column>`:

```
module_name, title, test_case_title, description, precondition, test_data,
steps, expected_result, tags, type, priority, mode, estimate, reference,
test_suite
```

The reply is honest: `{"success": true, "total": 34, "imported": 34,
"failed": 0, "errors": []}`. A rejected row creates nothing and names the
column and row number. **Create-only.** A `case_key` column is ignored, and
the row creates a duplicate. Newline-separated `steps` and
`expected_result` cells arrive as separate step rows.
`tools/qatouch_csv_import.py` writes this shape from the CSV that
`qatouch_cases_from_tests.py` makes, and chunks at 100.

### Attachments on result uploads

`POST /api/v1/testRunResults/testrun/code` also accepts multipart `file[]`
parts (png, pdf, jpg, csv, log, 2 MB per file) beside the `comments`
field. `QATouchClient.update_test_run_results_by_code()` takes an optional
`attachments` list of `(filename, bytes, content_type)`.

The reporter uses this when `QATOUCH_USE_PLAYWRIGHT_ENDPOINT=1` is set:
a failed case with a captured screenshot uploads it as
`<case code>-failure.png`. A screenshot over the 2 MB cap is skipped whole,
with a warning in the log. A failed multipart request does not fail the
upload: the reporter logs the error and sends the plain status upload
again, then reads back again. The multipart path has not run against the
live API. The next upload with a failure is the check: open the run and
confirm the file landed.

## Contract drift

QA Touch changes its API without telling anyone. The field rename above
went unnoticed for months because the tools kept answering with
`"Unknown"`. When an upload's read-back fails, or a listing shows
`"Unknown"` in every row, suspect a rename first. Compare a raw response
with the field names in `tools/qatouch_client.py` before you change any
other code.
