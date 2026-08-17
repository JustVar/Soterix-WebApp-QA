# QA Touch - New Capabilities and How We Could Use Them

QA Touch shipped seven releases between 2026-03-25 and 2026-07-29. Our tooling
was written before them. This page lists what is new, what we verified, and
what each one is worth to us.

> Contracts, endpoints and the measured API traps live in
> [QA_TOUCH_INTEGRATION.md](QA_TOUCH_INTEGRATION.md). This page is only about
> what the vendor added and whether we should adopt it.

Sources: `https://release.qatouch.com/` (release notes) and
`https://doc.qatouch.com/openapi.yaml` (the live OpenAPI spec, 4,477 lines).
Verified against the live API on 2026-08-17.

---

## Read this first: the docs do not describe the data

The OpenAPI spec documents **no test-case response fields at all**. Not one. A
grep for `module_name`, `Tags`, `case_title` across the whole spec returns
nothing.

That matters because QA Touch renamed those fields some time after 2026-03-27
(`module name` became `module_name`, the `NewTags` string became a `Tags`
list). Nothing announced it. Every tool of ours that read a case field went on
running and quietly reported "Unknown" instead of failing.

**Rule: never trust the docs for a response shape. Measure it.**
`tools/qatouch_client.py` now papers over that specific rename, but the next
one will need the same treatment. A weekly canary that asserts the field names
would catch it in a day instead of five months.

---

## The capabilities

### 1. Test Case Update API (2026-05-29) - useful, with one gap

`POST /api/v1/testcase/update?projectKey=...&caseKey=...`

Updates title, description, precondition, type, priority, mode, approval
status, steps and BDD script. Public API, so an API key is enough.

**Worth to us:** our current case-editing tools drive the *browser* internal
API (`/v1/case/update`) through a Playwright login that expires every few
weeks. Anything on that list could move to the public API and run headless -
in CI, on a schedule, with no browser.

**The gap: tags are not supported.** The only `tags` reference in the entire
public spec is an input filter when creating a run. So suite tagging - the
SMOKE/SANITY/REGRESSION work - still needs the browser path. That is why
`qatouch_suite_hold.py apply` still asks for a login.

### 2. Test-case-level and module-level bulk updates (2026-03-25) - already in use

`/api/v1/testRunResults/case/bulkupdate` and the module-level variant set
assignee and status in bulk on an existing run.

**Worth to us:** this is how the PTZ hold was applied to the open run. It is
also the tool for "assign this whole module to a tester" without clicking
through the UI.

**Two traps, both measured:**

- The endpoint answers `{"success": true, "msg": "Updated Test Run's status"}`
  **even when it changed nothing.** Always read the status back.
- It identifies a case by the case CODE with `TR` and leading zeros stripped.
  `TR0262` is sent as `262`. The case key (`B869bm`), the full code (`TR0262`)
  and the per-run result key (`w5BNkb`) are all accepted and all do nothing.

`case_code_to_ref()` in `tools/qatouch_client.py` builds the right form.

> **Open question worth chasing:** `plugins/qatouch_reporter.py` maps case keys
> to per-run result keys before uploading. In our test the result key was one
> of the forms that silently did nothing. Somebody should confirm that the
> Playwright result-upload pipeline is actually landing its results, because
> a silent no-op looks exactly like a successful upload.

### 3. `getTestRunlist/{caseKey}` - cheap run membership

Returns every run containing a case, with the `resultKey` and current status.

**Worth to us:** answering "which runs hold this case?" used to mean paging
every run's results - about 200 calls, which is how we hit HTTP 429 during
this work. Now it is one call per case. `qatouch_suite_hold.py runs-mark` uses
it.

### 4. Server-side filters on `getAllTestCases` - stops the rate limiting

`moduleKey`, `mode`, `approvalstatus`, `requirementKey`, `view=count|list`.

**Worth to us:** fetching one module went from paging 3,096 cases to a single
call returning 8. Wired up as `list_all_test_cases(project_key, module_key=...)`.
Use it any time the target is a module.

### 5. QA Touch MCP integration (2026-06-11) - evaluated: adopt alongside, do not replace

`qatouch-mcp-server` on npm. Official (`github.com/qatouch/qatouch-mcp-server`),
MIT, v1.1.6, 17 releases between 2026-06-03 and 2026-08-10, so it is actively
maintained. Node 18+, run through `npx -y qatouch-mcp-server`, authenticated
with the same `QATOUCH_DOMAIN` and API token we already hold. 45 tools.

**Verdict: use it for asking questions. Keep `tools/` for doing the work.**

What it covers well - reads and creates:

| Area | Tools |
|---|---|
| Read | `list_projects`, `list_test_cases`, `search_test_cases`, `list_modules`, `list_test_runs`, `list_test_run_results`, `list_test_run_result_history`, `list_requirements`, `list_defects`, all the `count_*` |
| Create | `create_test_case`, `create_bulk_test_cases`, `create_module`, `create_project`, `create_release`, `create_requirement`, `create_defect`, `create_test_run_with_modules`, `import_test_cases` (the CSV import from item 6) |
| Results | `update_test_run_result_status`, `update_test_run_results_by_code` |

Worth noting: it uses **`update_test_run_results_by_code`** - the same endpoint
we independently moved the reporter onto. Independent confirmation that the
code-based endpoint is the right one.

**Why it cannot replace `tools/`:**

1. **No tag tools. None.** The word "tag" does not appear in its tool list. Our
   main QA Touch workflow - SMOKE/SANITY/REGRESSION suite membership and the
   suite holds - is entirely tag work, and tags are browser-only anyway.
2. **No case update.** It creates cases but cannot edit an existing one.
3. **No run-membership lookup.** Nothing equivalent to
   `getTestRunlist/{caseKey}`, which is how we find a case inside existing runs.
4. **Wrong shape for automation.** It is a stdio server for an MCP client. Our
   reporter is a pytest plugin and our tools are scripts; neither can call it.
5. **It inherits the traps.** It talks to the same API that reports success for
   writes it discards. Our tools read values back afterwards. Assume it does
   not.

**Adopt it for:** interactive work - asking what a module covers, searching
cases and defects in natural language, checking run results without writing a
script. That is real value and it costs nothing to add.

**Do not:** rewrite any of `tools/` around it, or use it for suite tagging,
holds, or result uploads from CI.

### 6. CSV Test Case Import API (2026-07-12) - replaces a manual step

`POST /api/v1/testCase/import?projectKey=...`, up to 100 cases per request.

**Worth to us:** `docs/qa_import_pipeline.md` currently drives the browser's
internal import endpoints, reverse-engineered by live probe. A supported
public endpoint is a straight upgrade: no browser, no session, no probing.
Chunk our CSVs at 100 rows and the import becomes a scriptable step.

### 7. Playwright integration 2.0 (2026-03-25) - check our reporter

"Upgraded to Playwright 2.0 with enhanced support for screenshots and time
spent tracking."

**Worth to us:** confirmed and partly done. The reporter path it fed called a
client method that never existed, so it raised on every attempt; uploads now
run through `update_test_run_results_by_code()`.

**TODO - screenshots and timing attachments.** `POST
/api/v1/testRunResults/testrun/code` accepts multipart `file[]` attachments
(png/pdf/jpg/jpeg/gif/xls/xlsx/doc/docx/csv/log, 2 MB each) plus `comments`.
The reporter already captures failure screenshots (`self.screenshots`) and
per-test durations (`self.durations`) and currently drops both. Work needed:
extend the client method to post multipart when files are given, and pass
`execution_time` per result. Marked with a TODO in
`plugins/qatouch_reporter.py`.

### 8. Smaller items

| Item | Released | Note |
|---|---|---|
| Insights Dashboard | 2026-07-12 | Coverage, automation progress, defect trends. May overlap our QA Ops Hub reporting - look before building more. |
| Report Heatmap Summary | 2026-07-12 | Execution patterns and high-risk areas. |
| Burndown / velocity | 2026-06-29 | Release view and custom dashboards. |
| Test Plans resource | - | `getAllTestPlan` is live; we return "Test Plan not found". Unused. |
| Bulk GitLab issue mapping + RTM | 2026-07-12 | We use Jira, not GitLab. Ignore. |
| Linear integration | 2026-07-29 | We use Jira. Ignore. |
| Save filters / closed-issues tab | 2026-03-25 | UI only. |
| AI Test Parameters | 2026-04-29 | Data-driven parameterisation. Worth a look for repetitive matrix cases. |
| Step position reorder | 2026-04-29 | UI convenience. |

---

## Suggested order

1. **Confirm the result-upload pipeline is not silently failing.** Highest
   stakes: if uploads no-op, our automated results never reached QA Touch.
2. **Add a field-name canary.** One scheduled check that asserts the case
   response still carries `module_name`, `Tags`, `case_key`. Cheap insurance
   against the next undocumented rename.
3. ~~Evaluate the MCP server~~ - done. Adopt for interactive use only; it
   has no tag tools, so it cannot take over the suite work.
4. **Move the CSV import onto the public endpoint.**
5. **Move non-tag case edits onto the public update API**, leaving only tag
   work on the browser path.

---

*Written 2026-08-17. Every API claim here was checked against the live API or
quoted from the spec on that date. Re-verify before relying on any of it - the
vendor changes response shapes without documenting them.*
