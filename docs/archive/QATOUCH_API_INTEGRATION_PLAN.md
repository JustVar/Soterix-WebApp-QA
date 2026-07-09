# QA Touch API Integration Plan - QA Ops Hub & Beyond

> **Created:** 2026-03-10
> **Owner:** Justin Varughese, System Platform QA Lead
> **Status:** Planning - pending sync completion and full audit

---

## Table of Contents

1. [Discovered Internal APIs](#1-discovered-internal-apis)
2. [Gap Analysis: QA Touch vs Playwright vs Web App](#2-gap-analysis)
3. [Integration Scenarios for QA Ops Hub](#3-integration-scenarios)
4. [Manual-to-Automation Migration Pipeline](#4-manual-to-automation-pipeline)
5. [Headed Verification Workflow](#5-headed-verification-workflow)
6. [Multi-Environment Regression Strategy](#6-multi-environment-regression)
7. [Implementation Phases](#7-implementation-phases)
8. [Tool Reference](#8-tool-reference)

---

## 1. Discovered Internal APIs

The QA Touch bulk CSV import step-pairing fix project (03/2026) uncovered internal web APIs that are NOT part of the public API (`api.qatouch.com`). These work via authenticated browser session (cookies + XSRF token) using `page.evaluate()` in Playwright.

### Internal Web API Endpoints (reverse-engineered)

| Endpoint | Method | Purpose | Auth |
|----------|--------|---------|------|
| `/v1/case/edit/p/{pid}/cid/{caseKey}` | POST | Full case data: title, module, steps (with IDs), tags, mode, type, priority | XSRF cookie |
| `/v1/steps/save` | POST | Create step with paired description + expected result | XSRF cookie |
| `/v1/steps/delete/mid/{stepId}?type=true` | GET | Delete a step by internal ID | XSRF cookie |

### Public API Endpoints (documented)

| Endpoint | Method | Purpose | Auth |
|----------|--------|---------|------|
| `GET /api/v1/getAllTestCases/{projectKey}?page=N` | GET | List cases (50/page) - title, tags, module | api-token + domain |
| `GET /api/v1/getAllModules/{projectKey}?page=N` | GET | List modules (20/page) | api-token + domain |
| `GET /api/v1/getAllTestRuns/{projectKey}` | GET | List test runs | api-token + domain |
| `GET /api/v1/testRunResults/{projectKey}/{runKey}?page=N` | GET | Run results (100/page) | api-token + domain |
| `POST /api/v1/testRun/specific` | POST | Create run by case IDs or tag | api-token + domain |
| `POST /api/v1/testRun/specific/module/mode` | POST | Create run by module(s) + mode filter | api-token + domain |
| `POST /api/v1/clone/testRun` | POST | Clone existing run | api-token + domain |
| `PATCH /api/v1/testRunResults/status/multiple` | PATCH | Bulk-update result statuses | api-token + domain |
| `POST /api/v1/testCase` | POST | Create case (limited: no type/mode/tags) | api-token + domain |
| `POST /api/v1/milestone` | POST | Create release/milestone | api-token + domain |

### API Limitations (what CANNOT be done)

- **No case deletion via API** (UI only)
- **No run deletion via API** (UI only)
- **No case title/type/mode/tag update via API** - must use browser automation (`qatouch_browser.py`)
- **No step read via public API** - must use internal `/v1/case/edit/` endpoint
- **No milestone listing** - `getAllMilestones` returns empty
- **Rate limit:** 50 requests/minute (public API), internal API more lenient but needs burst pauses

### Auth Pattern for Internal APIs

```python
# Requires authenticated Playwright browser session
result = page.evaluate("""
    async (caseKey) => {
        const token = document.cookie.split('XSRF-TOKEN=')[1]?.split(';')[0];
        const resp = await fetch('/v1/case/edit/p/JlW1/cid/' + caseKey, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'Accept': 'application/json',
                'X-XSRF-TOKEN': decodeURIComponent(token || '')
            },
            body: JSON.stringify({})
        });
        return await resp.json();
    }
""", case_key)
```

**Session lifetime:** ~2-3 hours. Auth state can be saved/restored via Playwright `storage_state()`, but must validate with a real API call (deep check) before trusting.

---

## 2. Gap Analysis: QA Touch vs Playwright vs Web App

### Current Numbers

| Metric | Count |
|--------|-------|
| QA Touch total test cases | 3,011 |
| Playwright automated tests | 352 |
| Automation coverage | 11.7% (352/3,011) |
| Mapped (Playwright -> QA Touch) | 349/352 (99.1%) |
| Unmapped (infra tests, no QA Touch case) | 3 |
| Manual-only cases in QA Touch | ~2,662 |
| Cases with structured steps | 3,011 (100% after sync) |

### Coverage by Module (Top Gaps)

These are the QA Touch modules with the MOST manual-only cases - highest automation ROI:

| Module | Total Cases | Automated | Gap | Priority |
|--------|-------------|-----------|-----|----------|
| Admin - LPR | ~200 | 0 | 200 | High (complex rules engine) |
| Events - Filters & Actions | ~180 | 14 | 166 | High (regression-prone) |
| Views - Layout & Streaming | ~150 | 28 | 122 | High (core feature) |
| Camera Sequences | ~120 | 8 | 112 | Medium |
| Admin - Maps | ~100 | 12 | 88 | Medium |
| Insights - Reports & Dashboards | ~90 | 15 | 75 | Medium |
| Chats - Messaging | ~80 | 12 | 68 | Low (stable) |
| Notifications - Rules | ~70 | 10 | 60 | Medium |
| Media - Library & Export | ~60 | 8 | 52 | Low |
| Search - Advanced | ~50 | 8 | 42 | Medium |

**Recommended automation order (ROI):**
1. Events Filters - high regression risk, frequently changing
2. Admin LPR - complex, error-prone, high business value
3. Views Layout - core user-facing feature
4. Notifications Rules - medium complexity, good automation candidate
5. Insights Reports - data-driven, good for API testing

### Gap Analysis Automation Tool (Planned)

Build `tools/qatouch_gap_analysis.py` that:
1. Pulls all QA Touch cases via API (module, title, mode, tags)
2. Loads Playwright case mapping (`qatouch_case_mapping.json`)
3. Cross-references to find unautomated modules
4. Generates prioritized report by module with case counts
5. Outputs CSV for tracking and sprint planning

---

## 3. Integration Scenarios for QA Ops Hub

### Scenario A: Live Test Execution Dashboard with QA Touch Sync

**What:** Run Playwright tests from QA Ops Hub -> auto-upload results to QA Touch -> show unified status.

**Flow:**
1. User clicks "Start Run" on QA Ops Hub (smoke/sanity/regression)
2. Test Runner spawns `guarded_run.py` -> Playwright executes
3. Results auto-upload to QA Touch via `--qatouch-upload --qatouch-run <KEY>`
4. Dashboard polls QA Touch API for run progress
5. Final status: pass/fail counts, links to QA Touch run detail

**New QA Ops Hub features needed:**
- Auto-create QA Touch run when starting from dashboard (if no run key provided)
- Post-run status sync: pull final results from QA Touch, show on history page
- Link to QA Touch run detail from run history

### Scenario B: Headed Verification Mode for QA Approval

**What:** QA runs automated tests in headed (visible) mode, watches step-by-step execution, approves or rejects each test. This replaces manual test execution while keeping human judgment.

**Flow:**
1. QA opens Verification page on QA Ops Hub
2. Selects test cases to verify (from QA Touch backlog or by module)
3. System runs tests in headed mode with `--verify-mode --headed`
4. Each step captures screenshot + description (from QA Touch step definitions)
5. QA reviews evidence: step description, expected result, actual screenshot
6. QA approves (passed) or rejects (needs investigation) per step
7. Results sync back to QA Touch run with verdicts

**Why this matters:**
- Converts manual test execution (hours) into verification review (minutes)
- QA still validates behavior - not blindly trusting automation
- Creates audit trail: who verified, when, which steps passed/failed
- Gradually builds confidence in automation for each test case

### Scenario C: Regression Across Multiple Environments

**What:** Run the same test suite against QA, Stage, and Prod environments, compare results.

**Flow:**
1. Dashboard shows environment picker: QA / Stage / Prod
2. Each environment has its own QA Touch test run (per release)
3. Run triggers: manual, scheduled (cron), or post-deploy webhook
4. Results compared side-by-side on dashboard
5. Environment-specific failures highlighted (e.g., "fails on Stage only")

**New QA Ops Hub features needed:**
- Environment-specific run history
- Cross-environment comparison view
- Per-environment config (base URLs, credentials)
- Scheduled run configuration UI (replaces raw cron editing)

### Scenario D: Manual-to-Automated Case Conversion Tracker

**What:** Track which manual QA Touch cases have been automated, which are in progress, and which remain.

**Flow:**
1. Dashboard shows module-by-module automation coverage
2. QA selects a module -> sees list of manual cases
3. Click "Start Automation" -> creates scaffolded Playwright test + QA Touch mapping
4. Developer writes the test, marks as "ready for verification"
5. QA runs headed verification (Scenario B) to approve
6. Case mode updated to "Automated" in QA Touch

**Integration points:**
- Pull manual case list via QA Touch API (`getAllTestCases`, filter mode≠Automated)
- Push case creation via `scaffold` command
- Track conversion status in QA Ops Hub database
- Update mode via browser automation (`qatouch_browser.py set-mode`)

### Scenario E: Smart Test Selection (Risk-Based)

**What:** Automatically select which tests to run based on code changes, failure history, and module risk.

**Flow:**
1. Developer pushes code -> webhook fires to QA Ops Hub
2. System analyzes changed files -> maps to QA Touch modules
3. Selects relevant test cases (smoke + affected modules)
4. Creates QA Touch run with selected cases
5. Runs tests, uploads results

**Requires:**
- Code-to-module mapping (file paths -> QA Touch modules)
- Failure history database (which tests fail most often)
- QA Touch API for dynamic run creation by module

### Scenario F: QA Touch Analytics Dashboard

**What:** Rich analytics page in QA Ops Hub showing test management health metrics.

**Metrics to display:**
- Automation coverage by module (donut chart, progress bars)
- Test execution trends (pass/fail/skip over time)
- Tag distribution (smoke/sanity/regression coverage)
- Step quality metrics (avg steps per case, cases without steps)
- Release readiness gauge (% of cases executed this release)
- Failing test clusters (which modules have most failures)
- Test case growth rate (new cases added per week)

**Data sources:**
- QA Touch API for case/run/result data
- QA Ops Hub DB for run history
- Playwright case mapping for coverage numbers
- `qatouch_analytics.py` snapshots for trends

### Scenario G: Automated Nightly Regression with Slack Reporting

**What:** Scheduled nightly regression runs with automatic Slack alerts.

**Flow:**
1. Cron triggers at 2 AM: smoke on QA env, 4 AM: sanity on Stage env
2. `guarded_run.py` handles health check -> run -> upload -> validate
3. On completion: Slack bot posts summary to #qa-automation
4. On failure: Slack bot posts failing test list + links to QA Ops Hub
5. Morning: QA reviews results on dashboard, investigates failures

**Requires:**
- NUC cron configuration (already planned in roadmap)
- Playwright + Chromium installed on NUC
- Slack webhook integration (already in asset tracker, reusable)

---

## 4. Manual-to-Automation Migration Pipeline

### Step-by-Step Process

```
┌──────────────────────────────────────────────────────────┐
│ 1. IDENTIFY - Gap Analysis Tool                         │
│    qatouch_gap_analysis.py -> prioritized module list     │
│    Filter: Mode=Manual, has structured steps             │
└─────────────────────┬────────────────────────────────────┘
                      ▼
┌──────────────────────────────────────────────────────────┐
│ 2. SCAFFOLD - Create Test Structure                     │
│    qatouch_run_manager.py scaffold-new                   │
│    Creates: Playwright test file + QA Touch mapping      │
│    Auto-generates: test skeleton from QA Touch steps     │
└─────────────────────┬────────────────────────────────────┘
                      ▼
┌──────────────────────────────────────────────────────────┐
│ 3. IMPLEMENT - Write Automation Code                    │
│    Developer fills in Playwright actions                 │
│    Uses Page Object Models from tests/shared/pages/      │
│    Adds step captures for verification mode              │
└─────────────────────┬────────────────────────────────────┘
                      ▼
┌──────────────────────────────────────────────────────────┐
│ 4. VERIFY - QA Approval via Headed Mode                 │
│    QA runs test with --verify-mode --headed              │
│    Watches step-by-step execution in real browser        │
│    Reviews screenshots against expected results          │
│    Approves or rejects each step                         │
└─────────────────────┬────────────────────────────────────┘
                      ▼
┌──────────────────────────────────────────────────────────┐
│ 5. PROMOTE - Mark as Automated                          │
│    qatouch_browser.py set-mode -> Mode=Automation         │
│    Add to regression suite tags                          │
│    Update case mapping: auto_matched=true                │
│    Automation coverage metrics auto-update               │
└──────────────────────────────────────────────────────────┘
```

### Automation Generation from QA Touch Steps

Since all 3,011 cases now have structured steps, we can auto-generate Playwright test skeletons:

```python
# tools/qatouch_test_generator.py (planned)
# Input: QA Touch case key
# Output: Playwright test file with step comments

def generate_test(case_key):
    # 1. Fetch case data via internal API
    data = get_case_edit_data(page, case_key)

    # 2. Generate test skeleton
    for step in data['steps']:
        # Step: "Navigate to Admin > LPR page"
        # Expected: "LPR rules table is visible"
        -> page.goto('/admin/lpr')
        -> expect(page.locator('.lpr-table')).to_be_visible()
```

### Prioritized Conversion Batches

| Batch | Module | Cases | Effort | Business Value |
|-------|--------|-------|--------|----------------|
| 1 | Events Filters | ~180 | 3-4 weeks | High - regression-prone |
| 2 | Admin LPR | ~200 | 4-5 weeks | High - complex rules |
| 3 | Views Layout | ~150 | 3-4 weeks | High - core feature |
| 4 | Notifications | ~70 | 1-2 weeks | Medium |
| 5 | Insights Reports | ~90 | 2-3 weeks | Medium |
| 6 | Camera Sequences | ~120 | 3-4 weeks | Medium |
| 7 | Search Advanced | ~50 | 1-2 weeks | Medium |
| 8 | Remaining | ~1,800 | Ongoing | Various |

---

## 5. Headed Verification Workflow

### How It Works

The verification system already exists in QA Ops Hub. The enhancement is connecting it to QA Touch steps for richer, more meaningful verification.

**Current flow:**
```
pytest --verify-mode -> screenshots captured -> evidence JSON ->
QA Ops Hub -> manual review -> approve/reject
```

**Enhanced flow:**
```
1. Select cases from QA Touch (by module, tag, or manual pick)
2. Fetch structured steps via internal API (/v1/case/edit/)
3. Run pytest --verify-mode --headed
4. Each step: show description + expected result + screenshot
5. QA watches live execution AND reviews evidence after
6. Per-step verdict: approved / rejected / needs-review
7. Results sync back to QA Touch run
```

### QA Touch Step Integration in Verification

The internal API returns step data that maps directly to verification evidence:

```json
{
  "steps": [
    {
      "id": "l2QanJ",
      "description": "<p>Navigate to the Admin LPR page</p>",
      "expected": "<p>LPR configuration page loads with rules table</p>"
    }
  ]
}
```

This can replace or supplement the local JSON step definitions, giving a single source of truth.

### Benefits for QA Team
- **No more manual test execution** - automation does the clicking
- **QA focuses on judgment** - "does this look right?" not "click here, type there"
- **Audit trail** - who approved what, when, with evidence
- **Faster regression** - 10-minute review vs 2-hour manual execution
- **Confidence building** - QA sees the automation working, builds trust gradually

---

## 6. Multi-Environment Regression Strategy

### Environment Matrix

| Environment | URL | Purpose | Run Frequency | Suite |
|-------------|-----|---------|---------------|-------|
| QA | qa.nexaiq.com | Pre-release validation | Nightly 2 AM + on-demand | Full regression |
| Stage | stage.nexaiq.com | Release candidate | Nightly 4 AM + pre-release | Smoke + Sanity |
| Prod | app.nexaiq.com | Post-deploy verification | Post-deploy + weekly | Smoke only |

### QA Touch Run Naming Convention

```
v{VERSION} - {ENV} - {SUITE} - {DATE}
Example: v1.7.0 - QA - Smoke - 2026-03-15
```

### Implementation Plan

1. **Environment config in QA Ops Hub:**
   - Store base URLs, credentials per environment
   - Environment selector on Test Runner page
   - Auto-set `--base-url` flag for Playwright

2. **Scheduled runs via NUC cron:**
   - Cron creates QA Touch run -> triggers pytest -> uploads results
   - Different schedules per environment (see matrix above)

3. **Cross-environment comparison:**
   - Dashboard view: same tests across QA/Stage/Prod
   - Highlight environment-specific failures
   - Track "works on QA, fails on Stage" patterns

---

## 7. Implementation Phases

### Phase 1: Foundation (Immediate - after sync completion)

| Task | Effort | Dependency |
|------|--------|------------|
| Full audit of 3,011 cases (7-audit tool) | 1 day | Sync completion |
| Gap analysis tool (`qatouch_gap_analysis.py`) | 2 days | Audit pass |
| Document internal APIs in QA Touch memory files | 1 day | None |
| Update roadmap sections 1, 2, 24 | 1 day | Audit pass |

### Phase 2: QA Ops Hub Integration (Short-term - 1-2 weeks)

| Task | Effort | Dependency |
|------|--------|------------|
| QA Touch case browser page in Ops Hub | 3 days | Phase 1 |
| Auto-create QA Touch run from Test Runner | 2 days | Phase 1 |
| Post-run result sync to QA Touch | 2 days | Phase 1 |
| Automation coverage dashboard widget | 2 days | Gap analysis |
| Enhanced verification with QA Touch steps | 3 days | Phase 1 |

### Phase 3: Automation Pipeline (Medium-term - 2-4 weeks)

| Task | Effort | Dependency |
|------|--------|------------|
| Playwright NexaiQ setup on NUC | 2 days | None |
| Scheduled nightly runs (cron) | 1 day | NUC Playwright |
| Slack reporting integration | 1 day | Nightly runs |
| Test generation from QA Touch steps | 3 days | Phase 2 |
| Manual-to-automated conversion tracker | 3 days | Phase 2 |
| Headed verification workflow enhancement | 3 days | Phase 2 |

### Phase 4: Advanced (Long-term - when resources allow)

| Task | Effort | Dependency |
|------|--------|------------|
| Multi-environment regression | 5 days | Phase 3 |
| Risk-based test selection | 5 days | Phase 3 |
| CI/CD integration (post engineer hire) | 10 days | Phase 3 |
| QA Touch analytics dashboard | 3 days | Phase 2 |
| REGRESSION tag batch (~500-700 cases) | 2 days | Gap analysis |

---

## 8. Tool Reference

### Existing Tools

| Tool | Location | Purpose |
|------|----------|---------|
| `qatouch_client.py` (Playwright repo) | `qa/playwright-soterix-qa/tools/` | Full-featured API client |
| `qatouch_client.py` (QA Ops Hub) | `qa-ops/qa-ops-hub/app/` | Lightweight API client for web app |
| `qatouch_browser.py` | `qa/playwright-soterix-qa/tools/` | Browser automation for UI-only operations |
| `qatouch_run_manager.py` | `qa/playwright-soterix-qa/tools/` | CLI for runs, uploads, scaffolding |
| `qatouch_step_api.py` | `qa/playwright-soterix-qa/tools/` | Internal API for step CRUD |
| `qatouch_full_audit.py` | `qa/playwright-soterix-qa/tools/` | 7-audit verification tool |
| `qatouch_step_generator.py` | `qa/playwright-soterix-qa/tools/` | Generate step definitions from case titles |
| `qatouch_analytics.py` | `qa/playwright-soterix-qa/tools/` | Snapshots, reports, dashboard metrics |
| `qatouch_mapper.py` | `qa/playwright-soterix-qa/tools/` | Playwright-to-QA Touch case mapping |
| `qatouch_sync_check.py` | `qa/playwright-soterix-qa/tools/` | Drift detection for unmapped/stale entries |
| `qatouch_dedup.py` | `qa/playwright-soterix-qa/tools/` | Duplicate case prevention |
| `guarded_run.py` | `qa/playwright-soterix-qa/tools/` | Full orchestration: health->lock->timeout->test->validate |

### Planned Tools

| Tool | Purpose |
|------|---------|
| `qatouch_gap_analysis.py` | Module-by-module automation coverage report |
| `qatouch_test_generator.py` | Generate Playwright test skeletons from QA Touch steps |
| Enhanced `qatouch_full_audit.py` | Add step content comparison, tag drift detection |

---

## Appendix: Session Management for Internal APIs

The internal API requires careful session management:

1. **Login:** Playwright opens browser, user logs in manually
2. **Auth state save:** `ctx.storage_state(path=AUTH_STATE_FILE)` saves cookies
3. **Auth state restore:** Next run loads cookies, validates with deep check
4. **Deep check:** Makes real API call to confirm session is alive (not just URL match)
5. **Session lifetime:** ~2-3 hours before expiry
6. **Rate limiting:** Burst pause every 25-50 operations, 429 detection with retry

**For QA Ops Hub integration:** The Ops Hub should use the public API (`api.qatouch.com`) for all standard operations. Only use the internal API (via Playwright) for:
- Reading step content (not available via public API)
- Setting mode/type/tags (not available via public API)
- Step CRUD operations (not available via public API)

This means most QA Ops Hub features can work without a browser session - only the verification workflow and step-related features need Playwright.
