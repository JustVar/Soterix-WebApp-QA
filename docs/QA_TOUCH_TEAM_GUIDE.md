# QA Touch - Team Guide

## Overview

QA Touch is the centralized test case management platform for Soterix Systems. All test cases, test execution tracking, and QA reporting live here.

**URL:** `https://soterixsystems.qatouch.com/v2#/`

**Active Project:** NexaiQ-Core

---

## Getting Started

### Login

1. Navigate to `https://soterixsystems.qatouch.com/v2#/`
2. Enter your email and password
3. First-time users: check your email for an invitation link to set your password

### Navigation

1. Click **Project List** in the left sidebar
2. Select **NexaiQ-Core**
3. Use the **Modules** tab to browse test cases by area
4. Use the **Search** icon to find test cases by keyword

---

## Team & Roles

| Name | Role | Permissions |
|------|------|-------------|
| Justin Varughese | Manager (Admin) | Full access: create/delete test cases, create test runs, manage integrations |
| QA Engineer B | Tester | Execute test cases, add comments, update results |
| Nik Purohit | Tester | Execute test cases, add comments, update results |
| QA Engineer A | Tester (pending invite) | Will be added when onboarded |

**Key restrictions for Testers:**
- Cannot delete test cases (use the DELETE-REQUEST tag process below)
- Cannot create test runs (Manager creates these)
- Cannot import data or manage integrations
- **Any tester can execute tests in any run** regardless of assignee - assignee is ownership only

---

## Module Structure

The modules mirror the NexaiQ web application:

| Module | Sub-Modules | Test Cases |
|--------|-------------|------------|
| **Authentication** | Login (39), Logout (26) | 65 |
| **Global Features** | Chat (58), Notifications (40), Audio (6) | 104 |
| **Views** | Camera Grid, Devices Tab, Layouts, My Views, PTZ, etc. | 343 |
| **Events** | Landing Page, Filters, Search Results, Pinned Clips, etc. | 182 |
| **Maps** | Landing, Static Maps, Google Maps, Camera Preview, etc. | 80 |
| **Insights** | Dashboards, Widgets, Graph Types, Reports, etc. | 302 |
| **Media** | Listing, Vault, Filters, Bulk Actions, etc. | 114 |
| **Search** | Categories (Event/Person/Vehicle), Zone/Line, Results | 286 |
| **LPR** | Landing, Events Panel, Camera Search, Notifications, etc. | 153 |
| **Admin** | Dashboard (80), Sites (118), Users (90), Maps (115), Integrations (46), Rules (188), General (200), LPR (200), Licenses (187) | 1,224 |
| **TOTAL** | | **2,874** |

---

## Test Case Expectations

### What a Complete Test Case Looks Like

| Field | Required | Description |
|-------|----------|-------------|
| **Module** | Yes | Where the test case belongs |
| **Title** | Yes | Specific, descriptive name |
| **Precondition** | If applicable | Setup required before testing |
| **Steps** | Yes* | Numbered steps, one action per step |
| **Expected Result** | Yes* | What should happen when steps are followed |
| **Tags** | If applicable | SMOKE, REGRESSION, etc. |

*Test cases without steps are not executable. As of the 2026-08-17 live read every
case in the project has steps. If you create a case, give it steps in the same sitting.

### Naming Conventions

**Good:**
- `Validate login with valid credentials`
- `Verify camera feed loads within 5 seconds on Views page`
- `Validate Sites dropdown filters correctly by Enterprise`

**Bad:**
- `Test login` (too vague)
- `Check stuff works` (not descriptive)
- `Bug fix verification` (doesn't describe what is being tested)

---

## Test Suites

Test cases are organized into suites using **tags**:

| Suite | Tag | Purpose | Size | Gate |
|-------|-----|---------|------|------|
| **Smoke** | `SMOKE` | Core functionality check - run first after deployment | 60 tests | 100% pass required |
| **Sanity** | `SANITY` | Broader validation - run after Smoke passes | ~221 tests | 95%+ pass required |
| **Regression** | `REGRESSION` | Full feature validation before release sign-off | 500-700 tests | 90%+ pass required |
| **Full** | (all test cases) | Complete inventory for major releases | 2,874 tests | - |
| **Automated** | `AUTOMATED` | Has a corresponding Playwright test | 78 tests | - |

### How to Tag a Test Case

1. Open the test case
2. Click the **New Tags** field (not the "Tags" field)
3. Select the tag from the dropdown (e.g., `SMOKE`, `SANITY`)
4. Click **Save**

**Important:** If the tag does not exist in the dropdown, click the **"Add New"** button next to the New Tags field to create it first. Simply typing a tag name will not create it - you must use "Add New".

**Bulk tagging:** Select multiple test cases with checkboxes, click **Bulk Edit**, select the tag from the **New Tags** dropdown, and click **Save**. The "Others remain unchanged" option preserves existing tags.

#> New QA Touch features since March 2026, and the API traps we measured, are in
> [QATOUCH_NEW_CAPABILITIES.md](QATOUCH_NEW_CAPABILITIES.md).

## Suite Holds

A suite hold takes a group of test cases out of a suite for a while. The cases
stay in QA Touch. Only the suite tag comes off, so the cases drop out of the
next Sanity or Regression run. The hold is reversible.

**Current holds:**

| Group | Out of | Since | Reason |
|-------|--------|-------|--------|
| PTZ modules (PTZ Controls, PTZ Digital Controls, PTZ Presets, PTZ Tours, PTZ Tours & Presets) | Sanity, Regression | 2026-08-17 | On hold until further notice |

Run a hold with `tools/qatouch_suite_hold.py`. The tool writes a restore file
to `config/qatouch_suite_holds/` that records every tag it removed. Keep that
file. It is the only record of the original tags.

```bash
# See where the cases stand today (read only)
python tools/qatouch_suite_hold.py status --modules PTZ

# See which existing runs already contain them (read only)
python tools/qatouch_suite_hold.py runs --modules PTZ

# Preview the change (read only)
python tools/qatouch_suite_hold.py preview --modules PTZ --suites sanity,regression

# Apply the hold - opens a browser, log in to QA Touch when asked
python tools/qatouch_suite_hold.py apply --modules PTZ --suites sanity,regression     --label ptz --reason "PTZ on hold until further notice"

# Lift the hold later
python tools/qatouch_suite_hold.py restore --backup config/qatouch_suite_holds/hold_ptz_STAMP.json
```

**A hold does not change runs that already exist.** QA Touch copies the case
list into a run when the run is created. A test run created before the hold
keeps its PTZ cases.

For a run that is already open, set the held cases to **Not Applicable**
instead. The cases stay in the run, they drop out of the pass-rate maths, and
nobody wastes time executing them.

```bash
# Preview first - always
python tools/qatouch_suite_hold.py runs-mark --modules PTZ --run "1.7.9" \
    --status not-applicable --dry-run

# Apply
python tools/qatouch_suite_hold.py runs-mark --modules PTZ --run "1.7.9" \
    --status not-applicable --label ptz --reason "PTZ on hold"

# Undo
python tools/qatouch_suite_hold.py runs-restore --backup config/qatouch_suite_holds/runstatus_ptz_STAMP.json
```

**The tool refuses to overwrite an executed result by default.** A row that
already reads Passed, Failed or Blocked is a record that somebody ran the
test. Only rows still sitting at Untested are changed. `--include-executed`
overrides this - do not use it on a run whose results anyone still needs.

**Two warnings about the results API.** It answers
`{"success": true}` even when it changed nothing, so the tool always reads the
status back to confirm. And it identifies a case by its case CODE with the
`TR` prefix and leading zeros stripped - `TR0262` is sent as `262`. The case
key and the full code are both accepted and both silently do nothing.

**Status of the PTZ hold (applied 2026-08-17):**

| Step | State |
|---|---|
| Suite tags removed | Done - 20 PTZ cases carried `regression`; all 52 now carry no tags |
| Sanity-QA-1.7.9 (current run) | Done - all 52 set to Not Applicable (all were Untested, nothing lost) |
| Older runs (v1.6.0, v1.7.2, v1.7.6, 1.7.8, Regression-QA-V1.7.0) | Left alone on purpose - they hold real Passed/Failed records |

Restore files for both steps are in `config/qatouch_suite_holds/`. To lift the
hold, run `restore` for the tag file and `runs-restore` for the status file.

**Clearing the last tag needs `newtags: [""]`, not `[]`.** QA Touch reads an
empty list as "field not supplied", answers "Case Updated Successfully" and
changes nothing. The tools handle this - see `docs/QA_TOUCH_INTEGRATION.md`.

---

## Executing Test Runs

### Finding Your Assignment

1. Open **NexaiQ-Core** > **Test Runs** tab
2. Find the test run with your name in the Assignee column
3. Click the test run to open it

### Execution Process

For each assigned test case:

1. Read the **Preconditions** and set up the environment
2. Follow the **Steps** one by one in the NexaiQ application
3. Compare actual behavior against the **Expected Result**
4. Set the result:

| Status | When to Use | Action Required |
|--------|-------------|-----------------|
| **Passed** | All steps match expected results | None -- move to next test |
| **Failed** | Any step did not produce expected result | Add comment + create Jira bug |
| **Blocked** | Cannot execute (environment issue, dependency, existing bug) | Add comment with blocker details |
| **Skipped** | Not applicable for this run | Add comment explaining why |

### When a Test Fails

1. Set status to **Failed**
2. Add a comment describing: which step failed, what you expected, what actually happened
3. Attach a screenshot if possible
4. Create a Jira bug (use the integration icon in QA Touch)

**Bug description template (NexaiQ-Core -- Chrome only):**

```
Environment: QA / Staging / Production
Chrome Version: (e.g., 122.0.6261.94)
User Account: (test account used)

Steps to Reproduce:
1. Log in to NexaiQ as [role]
2. Navigate to [page]
3. Perform [action]
4. Observe [result]

Expected Result:
[What should have happened]

Actual Result:
[What actually happened]

QA Touch Test Case: [TC ID]

Screenshots/Evidence:
[Attached]
```

**Note:** NexaiQ-Core is tested on Chrome only. When mobile projects (NexaiQ-iOS, NexaiQ-Android) are active, those will use a separate template with device model, OS version, and app version fields.

---

## Jira Integration

### QA-Relevant Workflow

```
READY FOR QA BUILD
    | (Code added to QA build)
READY FOR QA
    | (Start testing)
QA IN PROGRESS
    | (Passed) --> COMPLETE
    | (Failed) --> QA NOT PASSED --> DEV IN PROGRESS (loop)
    | (Blocked) --> BLOCKED
```

### QA Touch to Jira Status Mapping

| QA Touch Result | Jira Transition |
|-----------------|-----------------|
| Test Passed | QA IN PROGRESS --> **COMPLETE** |
| Test Failed | QA IN PROGRESS --> **QA NOT PASSED** |
| Test Blocked | QA IN PROGRESS --> **BLOCKED** |

### Creating a Bug from QA Touch

1. In the test run, click on the failed test case
2. Click the **Create Issue** or Jira integration icon
3. Fill in: Issue Type (Bug), Summary, Description, Priority
4. Click **Create**
5. The bug appears in Jira under the NC project (e.g., NC-45) and is auto-linked

### Linking Test Cases to Jira Stories

1. Open the test case in QA Touch
2. Click **Link Issue** (chain-link icon)
3. Search for the Jira story by key (e.g., `NC-12`)
4. Select and link

---

## Delete Request Process

Testers cannot delete test cases. To request deletion:

1. Open the test case
2. Add the tag: `DELETE-REQUEST`
3. Add a comment explaining why (e.g., "Duplicate of TC-0045", "Created by mistake")
4. The Manager reviews and processes requests weekly

---

## Slack Channels

| Channel | Purpose |
|---------|---------|
| **#qa-automation** | Playwright automation results |
| **#qa-execution** | Test run assignments and completion updates |
| **#qa-team** | Day-to-day team discussion |
| **#QA-Daily-Standup** | Daily standup updates |

---

## Daily Workflow

1. Check **#qa-automation** for overnight automation results
2. Check **#qa-execution** for test run assignments
3. Open QA Touch > NexaiQ-Core > Test Runs > find your assigned run
4. Execute assigned test cases
5. For failures: add comment + create Jira bug
6. For blockers: add comment with blocker details
7. Update standup in **#QA-Daily-Standup**

---

## Tags Reference

| Tag | Purpose |
|-----|---------|
| **SMOKE** | Part of the Smoke Suite |
| **SANITY** | Part of the Sanity Suite |
| **REGRESSION** | Part of the Regression Suite |
| **AUTOMATED** | Has a Playwright test (future) |
| **NO_RUN** | Cannot be run - reason is in the precondition |
| **DELETE-REQUEST** | Requesting deletion |

---

## Test Run Naming Convention

```
[Type] - [Environment] - [Version/Sprint] - [Date YYYY-MM-DD]
```

Examples:
- `Smoke - Stage - v1.6.0 - 2026-02-17`
- `Sanity - Stage - v1.6.0 - 2026-02-17`
- `Regression - Stage - v1.6.0 - 2026-02-17`

### Execution Order

1. **SMOKE first** (gate) - must be 100% pass before proceeding
2. **SANITY second** - 95%+ pass to proceed
3. **REGRESSION third** - 90%+ pass for release sign-off

---

## Project Status

These numbers come from the live QA Touch API, not from the import files. Do
not hand-edit them. Re-read them at any time with:

```bash
python tools/qatouch_suite_hold.py status --modules ""   # per-module tag state
```

### Current State (live read 2026-08-17)

| Metric | Value |
|--------|-------|
| **Total test cases** | 3,096 |
| **Cases with steps** | 3,096 (100%) |
| **Unique modules (incl. sub-modules)** | 448 |
| **Original import (v4, 02/2026)** | 2,868 imported + 6 Audio preserved |

The original spreadsheet import is finished. The case count has grown past it
through scaffolding and authoring, so the old import totals are history, not a
current figure. The import runbook is `docs/qa_import_pipeline.md`.

### Test Suites Status (live read 2026-08-17)

| Suite | Tag | Tagged cases |
|-------|-----|--------------|
| SMOKE | `smoke` | 64 |
| SANITY | `sanity` | 16 |
| REGRESSION | `regression` | 584 |
| (other) | `future` | 1 |

Tag counts and run membership are NOT the same thing. A test run copies its
case list in when the run is created, so a run can hold cases that carry no
suite tag at all. Check run membership with the `runs` command, not the tags.

### Active Test Runs

Read the live list instead of trusting a table here:

```bash
python tools/qatouch_run_manager.py list
```

As of 2026-08-17 there are 10 open runs. Several date back to v1.6.0 and are
open only because nobody closed them. Close a run when its release ships.

---

## Need Help?

| Issue | Contact |
|-------|---------|
| Login/access problems | Justin Varughese |
| Test case questions | Post in #qa-team |
| Jira integration issues | Justin Varughese |
| Cannot delete a test case | Use DELETE-REQUEST tag |
| Need a test run created | Contact Justin with details |
