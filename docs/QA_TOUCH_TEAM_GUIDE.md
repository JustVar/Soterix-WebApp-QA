# QA Touch: team guide

QA Touch is the test case management platform. Test cases, test runs and
manual results live there. This page is for the testers who execute runs.
The engineers' page, for the API and the automated upload, is
[QA_TOUCH_INTEGRATION.md](QA_TOUCH_INTEGRATION.md). The whole integration
is optional: nothing in this repo contacts QA Touch unless you turn it on.

## Getting started

1. Open your QA Touch domain (`https://<domain>.qatouch.com/v2#/`).
2. Enter your email and password. A first-time user gets an invitation
   email with a link to set the password.
3. Click **Project List** in the left sidebar and choose the project.
4. Use the **Modules** tab to browse test cases by area, and the **Search**
   icon to find a case by keyword.

## Roles

| Role | Can do |
|------|--------|
| Manager | Create and delete test cases, create test runs, import data, manage integrations |
| Tester | Execute test cases in any run, add comments, update results |

A tester cannot delete a test case (use the DELETE-REQUEST tag below) and
cannot create a test run. Any tester can execute tests in any run. The
assignee is ownership only.

## What a complete test case looks like

| Field | Required | Description |
|-------|----------|-------------|
| **Module** | Yes | Where the test case belongs |
| **Title** | Yes | Specific, descriptive name |
| **Precondition** | If applicable | Setup needed before testing |
| **Steps** | Yes | Numbered steps, 1 action per step |
| **Expected Result** | Yes | What happens when the steps are followed |
| **Tags** | If applicable | SMOKE, REGRESSION, and the rest |

A test case without steps is not executable. If you create a case, give
it steps in the same sitting.

Good titles: `Validate login with valid credentials`, `Verify camera feed
loads within 5 seconds on Views page`. Bad titles: `Test login`, `Check
stuff works`, `Bug fix verification`.

The automated tests write their case from the test's docstring
(CONVENTIONS.md, "Adding a test"). Those cases carry the node id in the
Reference field. Do not edit their steps in QA Touch. Edit the docstring.

## Suites and tags

Test cases are organized into suites with **tags**:

| Suite | Tag | Purpose | Gate |
|-------|-----|---------|------|
| Smoke | `SMOKE` | Core functionality check. Run first after a deployment | 100% pass |
| Sanity | `SANITY` | Broader validation. Run after Smoke passes | 95% pass |
| Regression | `REGRESSION` | Full feature validation before release sign-off | 90% pass |
| Full | (all test cases) | Complete inventory for major releases | none |

### How to tag a test case

1. Open the test case.
2. Click the **New Tags** field (not the "Tags" field).
3. Choose the tag from the dropdown (`SMOKE`, `SANITY`, and the rest).
4. Click **Save**.

If the tag does not exist in the dropdown, click **Add New** next to the
New Tags field to create it first. Typing a tag name does not create it.

**Bulk tagging:** select several test cases with the checkboxes, click
**Bulk Edit**, choose the tag from the **New Tags** dropdown, and click
**Save**. The "Others remain unchanged" option keeps the existing tags.

### Suite holds

A suite hold takes a group of test cases out of a suite for a while. The
cases stay in QA Touch. Only the suite tag comes off, so the cases drop out
of the next Sanity or Regression run. Remove the tags by bulk edit, and
write down which cases carried which tag, because that record is the only
way back. A hold does not change runs that already exist: QA Touch copies
the case list into a run when the run is created. For a run that is
already open, set the held cases to **Not Applicable** instead. The PTZ
modules were on hold this way on the QA Touch side when the framework was
handed over.

## Executing test runs

### Finding your assignment

1. Open the project, then the **Test Runs** tab.
2. Find the test run with your name in the Assignee column.
3. Click the test run to open it.

### Execution process

For each assigned test case:

1. Read the **Preconditions** and set up the environment.
2. Follow the **Steps** one by one in the application.
3. Compare the actual behavior against the **Expected Result**.
4. Set the result.

| Status | When to use | Action |
|--------|-------------|--------|
| **Passed** | All steps match the expected results | None. Move to the next test |
| **Failed** | A step did not give the expected result | Add a comment and create a Jira bug |
| **Blocked** | Cannot execute (environment issue, dependency, existing bug) | Add a comment with the blocker |
| **Skipped** | Not applicable for this run | Add a comment that says why |

### When a test fails

1. Set the status to **Failed**.
2. Add a comment: which step failed, what you expected, what happened.
3. Attach a screenshot if possible.
4. Create a Jira bug with the integration icon in QA Touch.

Bug description template (Chrome only):

```
Environment: QA
Chrome Version: (for example 122.0.6261.94)
User Account: (the test account used)

Steps to Reproduce:
1. Log in as [role]
2. Go to [page]
3. Do [action]
4. See [result]

Expected Result:
[What should have happened]

Actual Result:
[What happened]

QA Touch Test Case: [case id]

Screenshots/Evidence:
[Attached]
```

## Jira from QA Touch

| QA Touch result | Jira transition |
|-----------------|-----------------|
| Test Passed | QA IN PROGRESS to **COMPLETE** |
| Test Failed | QA IN PROGRESS to **QA NOT PASSED** |
| Test Blocked | QA IN PROGRESS to **BLOCKED** |

To create a bug from a failed case: open the case in the run, click the
Jira integration icon, fill Issue Type (Bug), Summary, Description and
Priority, and click **Create**. The bug is linked to the case. To link a
case to a story: open the case, click **Link Issue**, search the story by
key, and link it.

## Delete request process

Testers cannot delete test cases. To request a deletion:

1. Open the test case.
2. Add the tag `DELETE-REQUEST`.
3. Add a comment that says why ("Duplicate of TC-0045", "Created by
   mistake").
4. The Manager reviews the requests.

## Tags reference

| Tag | Purpose |
|-----|---------|
| **SMOKE** | Part of the Smoke suite |
| **SANITY** | Part of the Sanity suite |
| **REGRESSION** | Part of the Regression suite |
| **AUTOMATED** | Has an automated test |
| **NO_RUN** | Cannot be run. The reason is in the precondition |
| **DELETE-REQUEST** | Requesting deletion |

## Test run naming

```
[Type] - [Environment] - [Version] - [Date YYYY-MM-DD]
```

Examples: `Smoke - QA - v1.6.0 - 2026-02-17`,
`Regression - QA - v1.6.0 - 2026-02-17`.

Execution order: Smoke first (100% pass before the next), then Sanity
(95%), then Regression (90% for release sign-off). Close a run when its
release ships.
