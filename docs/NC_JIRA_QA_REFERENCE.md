# NexaiQ-Core (NC) - Jira QA Reference

> **Version:** 1.0
> **Created:** February 7, 2026
> **Author:** Justin Varughese, QA Lead
> **Last Updated:** February 8, 2026
> **Jira Project Key:** NC
> **Jira URL:** https://soterixsystems.atlassian.net

This document is the **tool-agnostic** Jira reference for QA. It covers the NC project configuration that QA needs to know - field IDs, workflows, required fields, status mappings, and permissions. This information applies regardless of which test management tool is in use (QA Touch, TestRail, Zephyr, etc.).

---

## Table of Contents

1. [Project Overview](#1-project-overview)
2. [Issue Types](#2-issue-types)
3. [Workflows](#3-workflows)
4. [QA-Relevant Statuses & Transitions](#4-qa-relevant-statuses--transitions)
5. [Bug Creation - Required Fields](#5-bug-creation--required-fields)
6. [Custom Field Reference](#6-custom-field-reference)
7. [Test Result -> Jira Status Mapping](#7-test-result--jira-status-mapping)
8. [Groups & Permissions](#8-groups--permissions)
9. [Known Gaps & Blockers](#9-known-gaps--blockers)
10. [Automation Integration Points](#10-automation-integration-points)

---

## 1. Project Overview

| Field | Value |
|-------|-------|
| **Project Name** | NexaiQ-Core |
| **Project Key** | NC |
| **Project Type** | Company-managed (Jira Software) |
| **Board** | Board 34 |
| **Workflow Scheme** | NexaiQ Core Scheme (shared with NexaiQ-iOS) |
| **Permission Scheme** | NC software permission scheme (shared with NexaiQ-iOS) |
| **Notification Scheme** | Default Notification Scheme (shared with 3 projects) |

**Important:** Changes to workflow or permission schemes affect both NexaiQ-Core AND NexaiQ-iOS.

---

## 2. Issue Types

| Issue Type | QA Creates? | QA Tests? | Starting Status | Notes |
|------------|-------------|-----------|-----------------|-------|
| **Story** | No | Yes | UNSCHEDULED | Full lifecycle: analysis -> dev -> peer review -> QA -> complete |
| **Bug** | Yes | Yes | READY FOR DEV | 8 mandatory fields at creation |
| **Child Bug** | Yes | Yes | READY FOR DEV | Bug under a parent Story |
| **Task** | No | Yes | READY FOR DEV | Same workflow structure as Bug |
| **Hotfix** | No | No | READY FOR DEV | Support verifies; QA only tests if converted to Story |
| **Spike** | No | No | UNSCHEDULED | Research/investigation; no QA phase |
| **Epic** | No | No | NEW | Approval is automation-only |
| **Sub-task** | No | Yes | TBD | Not yet tested |

---

## 3. Workflows

### 3.1 Story Workflow

```
UNSCHEDULED
    ↓ Begin analysis (Product Management; PRD Link required)
ANALYSIS IN PROGRESS
    ↓ Complete analysis (Product Management; Story Points screen)
READY FOR DEV
    ↓ Start dev work (Developers)
DEV IN PROGRESS
    ↓ Start Peer Review (Developers; Release Notes required)
PEER REVIEW
    ↓ Peer Review passed (Developers; anti-self-approval - Reporter cannot approve)
    ↓ Detect a bug -> PEER REVIEW NOT PASSED -> DEV IN PROGRESS
READY FOR QA BUILD
    ↓ Add code to build for QA
READY FOR QA
    ↓ Start QA test (QA/QC System Testing)
QA IN PROGRESS
    ↓ QA passed (QA/QC System Testing) -> COMPLETE
    ↓ Detect a bug -> QA NOT PASSED -> DEV IN PROGRESS
```

**Global transitions (available from most statuses):**
- Encounter impediment -> BLOCKED (Impediment Screen)
- Dev Override (Scrum Masters)
- QA Override (Scrum Masters)
- Transition to Unscheduled (Product Management or Scrum Masters)
- Transition to Cancelled (Product Management or Scrum Masters)

### 3.2 Bug Workflow

```
READY FOR DEV
    ↓ Start dev work (Developers)
DEV IN PROGRESS
    ↓ Start Peer Review (Developers; Release Notes required)
PEER REVIEW
    ↓ Peer Review passed (Developers; anti-self-approval)
    ↓ Detect a bug -> PEER REVIEW NOT PASSED -> DEV IN PROGRESS
READY FOR QA BUILD
    ↓ Add code to build for QA
READY FOR QA
    ↓ Start QA test (QA/QC System Testing)
QA IN PROGRESS
    ↓ QA passed -> COMPLETE
    ↓ Detect a bug -> QA NOT PASSED -> DEV IN PROGRESS
```

**Global transitions:** Cancelled, Closed by Support, Dev Override, QA Override

**Key differences from Story:** No Unscheduled/Analysis phase. 8 mandatory fields at creation. No Story Points screen.

### 3.3 Task Workflow

Same structure as Bug workflow. Release Notes required for Peer Review.

### 3.4 Hotfix Workflow

```
READY FOR DEV
    ↓ Start dev work (Developers)
DEV IN PROGRESS
    ↓ Apply hotfix (Root Cause Analysis required)
SUPPORT REVIEW
    ↓ Verify with customer (Product Support group) -> COMPLETE
    ↓ Critical defect present (Product Support group) -> SUPPORT REVIEW FAILED -> DEV IN PROGRESS
```

**Global transitions:** Closed by Support, Dev Override, Blocker/impediment flow

**Blocker:** Product Support group does not exist yet - blocks Support Review transitions.

### 3.5 Spike Workflow

```
UNSCHEDULED
    ↓ Begin analysis
ANALYSIS IN PROGRESS
    ↓ Grooming rework loop (if needed) -> back to ANALYSIS IN PROGRESS
READY FOR DEV
    ↓ Start dev work
DEV IN PROGRESS
    ↓ Complete -> COMPLETE
```

No QA phase. No Blocked/impediment status. No Cancelled transition.

### 3.6 Epic Workflow

```
NEW
    ↓ Start work
DEFINING REQUIREMENTS
    ↓ Complete PRD
REQUIREMENTS REVIEW
    ↓ Design completed and estimated (Story Points required + child issues must exist)
AWAITING APPROVAL
    ↓ Epic approved -> READY FOR DEV (automation-only)
    ↓ Approval rejected -> NEEDS REVISION (automation-only)
```

**Blocker:** "Epic approved" and "Approval rejected" transitions are restricted from all users - automation-only. No Cancelled transition exists.

---

## 4. QA-Relevant Statuses & Transitions

### Statuses QA Interacts With

| Status | QA Action | Group Required |
|--------|-----------|----------------|
| READY FOR QA | Start testing | QA/QC System Testing |
| QA IN PROGRESS | Execute tests, record results | QA/QC System Testing |
| COMPLETE | QA passed - done | QA/QC System Testing (triggers transition) |
| QA NOT PASSED | QA failed - returns to dev | QA/QC System Testing (triggers transition) |
| BLOCKED | Impediment encountered | Various (Impediment Screen) |

### QA Override

Scrum Masters can override QA transitions (move issues through QA statuses without being in the QA group). This is for emergency situations only.

### Blocked/Impediment Flow

```
DEV IN PROGRESS -> BLOCKED
READY FOR QA -> BLOCKED
QA IN PROGRESS -> BLOCKED
BLOCKED -> QA IN PROGRESS (impediment cleared)
BLOCKED -> DEV IN PROGRESS (impediment cleared)
```

---

## 5. Bug Creation - Required Fields

When creating a Bug in the NC project, **8 mandatory fields** must be populated in addition to the standard fields (Project, Issue Type, Summary).

| # | Field Name | Custom Field ID | Type | Allowed Values | Source |
|---|------------|-----------------|------|----------------|--------|
| 1 | **Module** | `customfield_10135` | option-with-child | Views, Events, Maps, Insights, Media, Search, LPR, Admin, Partner Admin Tool, Event Wall, + more | Test case module |
| 2 | **Steps to Reproduce** | `customfield_10139` | text | (free text) | Test case steps |
| 3 | **Bug Overview** | `customfield_10140` | text | (free text) | Test case title + failure context |
| 4 | **Expected Behavior** | `customfield_10141` | text | (free text) | Test case expected result |
| 5 | **Actual Behavior** | `customfield_10142` | text | (free text) | Tester observation |
| 6 | **Environment Found** | `customfield_10098` | select | Dev, QA, Staging, Production | Test run environment |
| 7 | **Severity** | `customfield_10099` | select | Critical, High, Medium, Low | Priority mapping |
| 8 | **Affected Build Number** | `customfield_10138` | select | 1.4.10, 1.4.10h, 1.5, 1.5.1, 1.5.2, 1.5.3, 1.5.4, 1.5.5, 1.5.6 | Test run version |

> **Field IDs auto-discovered** on 2026-02-07 via `python tools/discover_jira_fields.py`. Full data in `config/jira_field_mapping.json`.

### Bug Description Template

```
**Environment:** [QA / Staging / Production]
**Browser:** [Chrome/Firefox/Edge] (version)
**User Account:** [test account used]

**Steps to Reproduce:**
1. Log in to NexaiQ as [role]
2. Navigate to [page]
3. Perform [action]
4. Observe [result]

**Expected Result:**
[What should have happened]

**Actual Result:**
[What actually happened]

**Test Case Reference:** [QA Touch TC ID or link]

**Screenshots/Evidence:**
[Attached]
```

---

## 6. Custom Field Reference

### Custom Fields - Complete Reference (Auto-Discovered 2026-02-07)

**Bug/Child Bug Required Fields:**

| Field Name | Custom Field ID | Type | Required By |
|------------|-----------------|------|-------------|
| Module | `customfield_10135` | option-with-child | Bug, Hotfix, Child Bug |
| Steps to Reproduce | `customfield_10139` | text | Bug, Hotfix, Child Bug |
| Bug Overview | `customfield_10140` | text | Bug, Hotfix, Child Bug |
| Expected Behavior | `customfield_10141` | text | Bug, Hotfix, Child Bug |
| Actual Behavior | `customfield_10142` | text | Bug, Hotfix, Child Bug |
| Environment Found | `customfield_10098` | select | Bug, Child Bug |
| Severity | `customfield_10099` | select | Bug, Child Bug |
| Affected Build Number | `customfield_10138` | select | Bug, Child Bug |

**Workflow Validator Fields:**

| Field Name | Custom Field ID | Used By | Notes |
|------------|-----------------|---------|-------|
| Story Points | `customfield_10097` | Story (validators) | NOT the built-in "Story point estimate" (customfield_10016) |
| Story point estimate | `customfield_10016` | (built-in agile) | Jira built-in - NOT used by workflow validators |
| Release Notes | `customfield_10134` | Story, Bug, Task | Required for Peer Review transition |
| Root Cause Analysis | `customfield_10209` | Hotfix | Required for "apply hotfix" transition |

> **Full field data:** `config/jira_field_mapping.json` - regenerate with `python tools/discover_jira_fields.py`

### Dual Story Points Warning

Two Story Points fields exist:
- `customfield_10016` - "Story point estimate" (Jira built-in agile field)
- `customfield_10097` - "Story Points" (custom field)

**Workflow validators check `customfield_10097`.** Recommend aligning on a single field to avoid confusion.

---

## 7. Test Result -> Jira Status Mapping

> **Note:** Status names in this doc use ALL CAPS for visual clarity. The actual Jira API status names are title-case (e.g., "Complete", "QA Not Passed", "Blocked"). For programmatic use, see `config/jira_field_mapping.py`.

| Test Result | Jira Transition | Target Status |
|-------------|-----------------|---------------|
| **Passed** | QA passed | COMPLETE |
| **Failed** | Detect a bug | QA NOT PASSED |
| **Blocked** | Encounter impediment | BLOCKED |
| **Skipped** | (no action) | - |

### Anti-Self-Approval Rule

Peer Review has an anti-self-approval check: the **Reporter** cannot approve their own Peer Review. This means the person who created the issue cannot be the one to mark Peer Review as passed. A different developer must approve.

---

## 8. Groups & Permissions

### QA-Relevant Groups

| Group | Members | QA Purpose |
|-------|---------|------------|
| QA/QC System Testing | test-qalead, Justin Varughese | QA transitions (start test, pass, fail) |
| Scrum Masters | test-devlead, Justin Varughese | Override transitions (emergency only) |
| Product Management | robert.james, test-pm, Justin Varughese | Scheduling, cancellation |
| Developers | Nik Purohit, test-developer1, test-devlead, test-developer2, Justin Varughese | Dev work, peer review |
| Product Support | **(DOES NOT EXIST YET)** | Hotfix Support Review transitions |

### Permission Gaps

| Permission | Current State | Impact on QA |
|------------|---------------|--------------|
| Close Issues | `atlassian-addons-project-access` only | No human can close issues |
| Modify Reporter | `atlassian-addons-project-access` only | Cannot reassign reporter (affects anti-self-approval testing) |
| Set Issue Security | `atlassian-addons-project-access` only | Cannot set security levels |

---

## 9. Known Gaps & Blockers

### Blocking Issues

| Issue | Impact | Action Needed |
|-------|--------|---------------|
| Product Support group missing | Cannot test Hotfix Support Review transitions | Create group, add users |
| Epic approval automation-only | Cannot manually approve/reject Epics | Verify automation rules in Project > Automation |
| Close Issues permission | No humans can close issues | Update permission scheme |
| Modify Reporter permission | Cannot change reporter for testing | Update permission scheme |

### Workflow Gaps

| Issue | Impact | Recommendation |
|-------|--------|----------------|
| No Cancelled transition on Epic | Epics cannot be cancelled from any status | Add global Cancelled transition |
| No Cancelled transition on Spike | Spikes have no cancellation path | Add global Cancelled transition |
| No Cancelled on Hotfix | Only "Closed by Support" terminal state | Consider adding Cancelled |
| No Blocked/impediment on Spike | Cannot flag blocked spikes | Consider adding if needed |
| Dual Story Points fields | Data entry confusion | Consolidate to one field |

### Untested Workflows

- Sub-task workflow
- Child Bug workflow
- Scrum Master override transitions (verify group restriction)
- Blocked/impediment flows across all workflows
- Cancelled global transitions on Story, Bug, Task
- Closed by Support on Bug and Hotfix
- Notification scheme validation

---

## 10. Automation Integration Points

### Official Integration Architecture (Option 3 - decided 2026-02-08)

```
+------------------+     +------------------+     +------------------+
|   QA Touch       |     |   Jira NC        |     |   Playwright     |
|                  |     |                  |     |                  |
| - Test cases     |     | - Bug creation   |     | - Test execution |
| - Execution      |     |   (source of     |     | - Auto bug filing|
|   tracking       |<----|   truth)         |<----|   via API        |
| - Dashboards     |link | - All 8 fields   |     | - Result upload  |
| - Team workload  |     | - Workflows      |     |   to QA Touch    |
+------------------+     +------------------+     +------------------+
```

**Jira** is the source of truth for bugs. All NC Bugs are created directly in Jira (manual or API) where all 8 mandatory fields including Module (cascading select) can be populated.

**QA Touch** handles test case management, execution tracking, and linking to Jira issues for traceability. Bug creation through QA Touch UI is not used because the Module field (cascading select) is unsupported by QA Touch's connector.

**Playwright** runs tests, reports results to QA Touch via API, and files bugs to Jira via `smart_jira_bug_creator.py` when failures meet confidence thresholds.

### For Test Management Tool Integration

Any test management tool connecting to Jira NC should be configured to:

1. **Link test cases** to Stories/Bugs using Jira issue keys (NC-xxx)
2. **Map test results** to Jira transitions (Section 7)
3. **Respect group permissions** - QA transitions require QA/QC System Testing group membership
4. **Bug creation goes through Jira directly** - not through the test management tool's connector (due to Module field limitation)

### For Playwright/CI Automation

The smart bug creator (`tools/smart_jira_bug_creator.py`) uses:
- Confidence scoring to avoid filing bugs for flaky tests
- Environment health checks before creating bugs
- `config/jira_field_mapping.py` for field ID resolution
- All 8 mandatory NC Bug fields including Module (cascading select)

### API Integration

| Endpoint | Purpose |
|----------|---------|
| `createmeta` | Discover required fields and allowed values |
| `create_issue` | Create Bugs with all mandatory fields |
| `add_comment` | Add test execution notes |
| `transitions` | Discover available transitions for an issue |
| `do_transition` | Move issues between statuses |

### Scripts

| Script | Purpose |
|--------|---------|
| `tools/discover_jira_fields.py` | Auto-discover field IDs from Jira API |
| `tools/verify_jira_integration.py` | Validate integration configuration (17 checks) |
| `tools/smart_jira_bug_creator.py` | Multi-gate bug creation with confidence scoring |
| `tools/test_jira_connection.py` | Basic Jira connectivity test |
| `tools/test_integration.py` | 6-phase integration test suite (73 tests) |

---

## Version History

| Version | Date | Author | Changes |
|---------|------|--------|---------|
| 1.0 | 2026-02-07 | Justin Varughese | Initial creation from NC Jira configuration report |
| 1.1 | 2026-02-08 | Justin Varughese | Section 10: Added Option 3 architecture (Jira as source of truth). Added integration diagram and test_integration.py to scripts table. |
