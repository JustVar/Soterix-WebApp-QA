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

*Test cases without steps are not executable. Over 1,100 test cases currently need steps written.

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
| **REGRESSION** | Part of the Regression Suite |
| **AUTOMATED** | Has a Playwright test (future) |
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

## Import Status

### Current State (as of 2026-02-17)

| Metric | Value |
|--------|-------|
| **Total test cases** | 2,874 |
| **Imported from spreadsheet (v4)** | 2,868 |
| **Preserved (Audio)** | 6 |
| **With full steps** | 2,868 (100% of imported) |
| **Unique modules (incl. sub-modules)** | 468 |
| **Parent modules** | 10 |
| **Source** | Soterix_Testcases (1).xlsx |
| **Import file** | `tests/data/qa_touch_import_v4.csv` |

### Test Suites Status

| Suite | Tagged | Target |
|-------|--------|--------|
| SMOKE | 60 | 60 (complete) |
| SANITY | 0 | ~221 (tagging pending) |
| REGRESSION | 0 | 500-700 (planned) |
| AUTOMATED | 78 | ongoing |

### Active Test Runs

| Run | Key | Release | Cases | Status |
|-----|-----|---------|-------|--------|
| Smoke - Stage - v1.6.0 - 2026-02-20 | vaKhn | v1.6.0 - Stage (Dmn7) | 60 | Open |

---

## Need Help?

| Issue | Contact |
|-------|---------|
| Login/access problems | Justin Varughese |
| Test case questions | Post in #qa-team |
| Jira integration issues | Justin Varughese |
| Cannot delete a test case | Use DELETE-REQUEST tag |
| Need a test run created | Contact Justin with details |
