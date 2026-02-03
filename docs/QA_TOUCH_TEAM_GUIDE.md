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
| QA Engineer B | Tester | Same as above |
| QA Engineer A | Tester | Same as above |
| Nik Purohit | Tester | View, create, edit, execute test cases. Cannot delete or create test runs |

**Key restrictions for Testers:**
- Cannot delete test cases (use the DELETE-REQUEST tag process below)
- Cannot create test runs (Manager creates these)
- Cannot import data or manage integrations

---

## Module Structure

The modules mirror the NexaiQ web application:

| Module | Sub-Modules | Test Cases |
|--------|-------------|------------|
| **Authentication** | Login, Logout | 25 |
| **Global Features** | Chat, Notifications, Help Center, Profile, Audio | 39 |
| **Views** | -- | 186 |
| **Events** | -- | 0* |
| **Maps** | -- | 16 |
| **Insights** | -- | 36 |
| **Media** | -- | 42 |
| **Search** | -- | 167 |
| **LPR** | -- | 141 |
| **Admin** | Dashboard, Sites, Users, Maps, Integrations, Rules, General, LPR, Licenses | 876 |

*The rest of the modules are in the process of being migrated.
*Complete migration will take place when QA Team gives their updated spreadsheet

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

| Suite | Tag | Purpose | Size |
|-------|-----|---------|------|
| **Smoke** | `SMOKE` | Core functionality check after deployments | 50-75 tests |
| **Regression** | `REGRESSION` | Feature validation before releases | 200-400 tests |
| **Full** | (all test cases) | Complete inventory for major releases | 1,528+ tests |
| **Automated** | `AUTOMATED` | Has a corresponding Playwright test (future) | TBD |

### How to Tag a Test Case

1. Open the test case
2. Click the **Tags** field
3. Type the tag name (e.g., `SMOKE`) and press Enter
4. Click **Save**

**Bulk tagging:** Select multiple test cases with checkboxes, click **Bulk Edit**, add the tag, and apply.

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
- `Smoke - QA Env - v1.50 - 2026-02-03`
- `Release v1.50 - Regression - 2026-02-03`
- `Sprint 12 - New Features - 2026-02-03`

---

## Import Status

### Current State (as of 2026-02-02)

| Metric | Value |
|--------|-------|
| **Total test cases imported** | 1,528 |
| **With full steps** | 428 |
| **Title only (need steps)** | ~1,100 |
| **Source** | Bugasura extraction + testcases_export.json |
| **Import file** | `tests/data/qa_touch_import_v2.csv` |

### Module Breakdown

#### Full Steps Available (428 test cases)

| Module | Count |
|--------|-------|
| Core Features > Views | 186 |
| Core Features > Search | 167 |
| Core Features > Media | 42 |
| Core Features > Insights | 36 |
| Core Features > LPR | 26 |
| Core Features > Notifications | 21 |
| Admin > Dashboard | 18 |
| Core Features > Login | 17 |
| Core Features > Maps | 16 |
| Core Features > Chats | 12 |
| Core Features > Logout | 8 |
| Core Features > Audio | 6 |

#### Title Only (1,100 test cases -- steps pending)

| Module | Count |
|--------|-------|
| Admin > Rules | 204 |
| Admin > General | 200 |
| Admin > Licences | 187 |
| Admin > LPR | 115 |
| Admin > Maps | 100 |
| Admin > Sites | 68 |
| Admin > Users & Roles | 55 |
| Admin > Integrations | 44 |
| Core Features > Search | 49 |
| Core Features > Media | 14 |
| Admin > Dashboard | 1 |
| Various other | 63 |

### What Needs to Happen Next

1. **Fill in missing steps** for ~1,100 "Title Only" test cases (waiting on incoming spreadsheet)
2. **Tag test cases** for Smoke and Regression suites
3. **Set up test execution plans** for upcoming releases

---

## Need Help?

| Issue | Contact |
|-------|---------|
| Login/access problems | Justin Varughese |
| Test case questions | Post in #qa-team |
| Jira integration issues | Justin Varughese |
| Cannot delete a test case | Use DELETE-REQUEST tag |
| Need a test run created | Contact Justin with details |
