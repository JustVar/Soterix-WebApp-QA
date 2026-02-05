# Unified Roadmap - Soterix QA Automation

> **Last Updated:** 2026-02-05
> **Sources:** Tooling Code (Terminal), Tooling Code (VS Code), Tooling Chat (tooling.ai project)
> **Migration Progress:** ~23% (49 of ~212 Selenium tests migrated)
> **Owner:** Justin Varughese, System Platform QA Lead

---

## Status Key

| Icon | Meaning |
|------|---------|
| ✅ | Complete |
| 🔄 | In Progress |
| 🔜 | Planned (committed to doing) |
| 💡 | Mentioned / Idea (not yet committed) |
| 🚫 | Blocked / Waiting on dependency |

---

## How to Update This Roadmap

> **This file is the single source of truth for all QA roadmap items.**
> The dashboard (`docs/dashboard.html`) is auto-generated from this file.
> After making changes, regenerate the dashboard: `python tools/generate_dashboard.py`
> The "Last Updated" date is set automatically when the dashboard is regenerated.

### Instructions for AI Assistants

**When working in any AI interface, update this file when:**
- A task is started (change status icon to 🔄)
- A task is completed (change status icon to ✅, or add `- [x]` under **Completed:**)
- A new task is identified (add a row with 🔜, 💡, or 🔄)
- A task becomes blocked (change status icon to 🚫 and note the blocker in Details)
- A task is no longer relevant (remove it)

**Tooling Code (Terminal) - has direct file access:**
```
# Edit the roadmap directly:
# 1. Read the file to find the section
# 2. Use Edit tool to change the status icon or add items
# 3. Regenerate dashboard:
python tools/generate_dashboard.py
```

**Tooling Code (VS Code) - has direct file access:**
```
# Same as Terminal - edit FUTURE_ROADMAP.md directly using the Edit tool
# Then regenerate: python tools/generate_dashboard.py
```

**Tooling Chat (tooling.ai) - no file access:**
```
# Cannot edit files directly. Instead:
# 1. Tell the user what changes to make (section, item, old status -> new status)
# 2. Or provide the updated markdown block for the user to paste
# 3. Remind user to run: python tools/generate_dashboard.py
```

**ChatGPT - no file access:**
```
# Cannot edit files directly. Instead:
# 1. Tell the user what changes to make (section, item, old status -> new status)
# 2. Or provide the updated markdown block for the user to paste
# 3. Remind user to run: python tools/generate_dashboard.py
```

### Quick Reference - Common Updates
```markdown
# Mark item as in-progress:    Change 🔜 to 🔄
# Mark item as complete:       Change 🔄 to ✅  (or add - [x] under Completed:)
# Mark item as blocked:        Change 🔜 to 🚫  (add blocker in Details column)
# Add new planned item:        Add table row with 🔜
# Add new idea:                Add table row with 💡
# Regenerate dashboard:        python tools/generate_dashboard.py
```

---

## 1. Test Automation Development

### Current State (as of 2026-02-05)

| Metric | Value |
|--------|-------|
| **Playwright tests written** | 49 |
| **QA Touch manual test cases** | 2,552 |
| **Automation coverage** | ~2% (49 / 2,552) |
| **Target (Selenium migration)** | ~212 tests |
| **Selenium migration progress** | ~23% (49 / 212) |
| **Environment** | QA only (Stage/Prod planned) |

### Foundation

| Item | Status | Completed | Details |
|------|--------|-----------|---------|
| pytest markers setup | ✅ | 01/29/2026 | smoke, regression, api, ui, drag_drop, live_streaming |
| Page Object Model structure | ✅ | 01/24/2026 | shared page objects folder |
| Session caching implementation | ✅ | 01/27/2026 | cookies + localStorage injection (86% test time reduction) |
| Test organization approach | ✅ | 01/24/2026 | mix of classes, functions, and markers |
| API tests | ✅ | 01/24/2026 | 16 endpoints tested across 5 categories |

### Phase 1: Initial Migration (IN PROGRESS)

| Item | Tests | Status | Details |
|------|-------|--------|---------|
| Login tests migration | 10 | 🔄 | Basic login tests exist; `smoke`/`sanity` markers still needed |
| API tests migration | 16 | 🔄 | All 16 have markers; need validation against QA Touch cases |
| Views module migration | ~40 | 🔄 | 23 of ~40 migrated; live view, sequence/playlist, grid layout remaining |
| Events module migration | 26 | 🔜 | EventsPage POM complete; test files still needed |
| Logout tests | - | 🔜 | `test_logout()` exists in login suite; standalone suite not yet created |

### Phase 2: Extended Coverage (PLANNED)

Modules to migrate from Selenium or add new coverage:

| Module | Status | Notes |
|--------|--------|-------|
| Search | 🔜 | HAR capture needed |
| Media | 🔜 | Clip management |
| Insights | 🔜 | System Status dashboard click-through |
| Chats | 🔜 | |
| Maps | 🔜 | |
| Notifications | 🔜 | |
| LPR | 💡 | No existing Selenium coverage |

### Phase 3: Admin Module Coverage (FUTURE)

| Module | Status | Notes |
|--------|--------|-------|
| Admin Rules | 🔜 | |
| Admin Sites | 🔜 | |
| Admin Users | 🔜 | |
| Admin Maps | 💡 | No existing Selenium coverage |
| Admin Integrations | 💡 | No existing Selenium coverage |
| Admin General | 💡 | No existing Selenium coverage |
| Admin LPR | 💡 | No existing Selenium coverage |
| Admin Licenses | 💡 | No existing Selenium coverage |

### Video/Streaming Validation (Planned)

| Item | Status | Details |
|------|--------|---------|
| Video element validation tests | 🔜 | Check video element, readyState, currentTime incrementing, frame comparison |
| Streaming performance metrics | 🔜 | Time to first frame, buffering events, frame drops, bandwidth |
| Screenshot comparison for frozen frame detection | 🔜 | Capture frames at intervals, compare pixel differences |
| Dynamic camera discovery helper | 🔜 | Auto-discover available cameras/channels per environment at runtime |

### Test Tooling & Infrastructure

| Item | Status | Details |
|------|--------|---------|
| Playwright trace viewer setup | 🔜 | For detailed failure analysis |

### Manual Test Case Identification (PENDING)

| Item | Status | Details |
|------|--------|---------|
| Map QA Touch test cases to automation candidates | 🔜 | Identify which manual tests should be automated |
| Prioritize automation based on execution frequency | 🔜 | Focus on high-run-rate tests first |
| Gap analysis: QA Touch vs Playwright coverage | 🔜 | Track what's automated vs manual-only |

---

## 2. Test Management Platform

### Current State (as of 2026-02-05)

| Metric | Value |
|--------|-------|
| **Total test cases (target)** | 2,583 |
| **Incoming from spreadsheet** | 2,552 |
| **Preserved (Login/Logout/Audio)** | 31 |
| **With full steps** | 2,552 (100% of incoming) |
| **Unique modules (incl. sub-modules)** | 425 |
| **Waiting for corrected file** | Admin-LPR (200 rows duplicate of Admin-General) |

**Completed:**
- [x] Full import v3: 2,552 test cases with steps prepared (02/04/2026)
- [x] Comparison analysis document generated (02/04/2026)
- [x] Import tracking document generated (02/04/2026)
- [x] QA Touch team guide created (02/03/2026)
- [x] Module structure created with 425 sub-modules (02/03/2026)
- [x] Admin > General sub-modules programmatically assigned (02/03/2026)
- [x] Admin > Maps sub-modules programmatically assigned (02/03/2026)
- [x] CSV import issues resolved (02/03/2026)
- [x] DELETE-REQUEST saved filter setup (02/03/2026)
- [x] Field mapping finalized (02/03/2026)

### Pending Tasks

| Item | Status | Details |
|------|--------|---------|
| Verify import total = 2,583 | 🔜 | 2,552 imported + 31 preserved |
| Tag test cases with SMOKE (~100-150) | 🔜 | Critical path tests for deployment validation |
| Tag test cases with REGRESSION (~500-700) | 🔜 | Broader coverage for release testing |
| Set up test execution plans | 🔜 | |
| Test Run creation workflows | 🔜 | 5 run types: Release, Smoke, Sprint, Nightly, Full Regression |
| Import corrected Admin-LPR sheet | 🚫 | Waiting for corrected file from QA team |

### Future Enhancements

| Item | Status | Priority | Details |
|------|--------|----------|---------|
| Manual Playwright result upload to QA Touch | 🔜 | Medium | Batch import process before automation is ready |
| Automated Playwright -> QA Touch result upload | 🔜 | High | Needs QA Touch API + Playwright migration further along |
| AUTOMATED tag sync script | 🔜 | Low | Auto-tag test cases matching Playwright tests |
| QA Touch API integration for bulk ops | 🔜 | Medium | API key available |
| Gap analysis automation | 🔜 | Medium | Compare QA Touch vs Playwright vs website features |
| Test case versioning and maintenance procedures | 🔜 | Low | |
| Requirements traceability in QA Touch | 🔜 | Low | |
| QA dashboards | 🔜 | Medium | Test execution metrics, pass/fail rates, coverage |
| Leadership/PM dashboards | 🔜 | Medium | Milestone-based, release readiness, quality trends |
| Additional QA Touch projects | 💡 | Future | NexaiQ-Private Cloud, NexaiQ-iOS, NexaiQ-Android, NexaiQ-Technician App, NexaiQ-Partner Admin Tool |

---

## 3. JIRA NexaiQ-Core Integration

| Item | Status | Details |
|------|--------|---------|
| Complete Jira instance setup/testing | 🔄 | Company-managed, project key = NC |
| Smart bug creation scripts | 🔄 | `smart_jira_bug_creator.py`, `update_failure_history.py`, `review_queue.py`, `flaky_tests.json` - scripts created |
| Review custom labels | 🔄 | Updating Jira labels |
| Define project structure and workflows | 🔜 | |
| Configure QA Touch -> Jira integration | 🔜 | API token setup, field mapping |
| Configure Playwright -> Jira integration | 🔜 | Automated bug creation on test failure |
| Sprint/release test coverage reports | 🔜 | |
| Create QA metrics dashboards | 🔜 | |

---

## 4. Gap Analysis

| Item | Status | Details |
|------|--------|---------|
| Compare QA Touch vs Playwright vs website features | 🔜 | Identify missing test cases |
| Run Tooling through NexaiQ website to discover untested features | 🔜 | Tooling browses app, identifies features not in master test list |
| Website feature inventory creation | 🔜 | Foundation for gap analysis |
| Gap analysis automation script | 🔜 | Compare QA Touch inventory vs Playwright inventory |
| Determine automation vs. manual classification | 🔜 | For each test case |

---

## 5. Slack Automation

| Item | Status | Details |
|------|--------|---------|
| Slack webhook setup for QA Touch | 🔜 | #qa-execution and #qa-automation channels |
| Automated Slack bot for #qa-automation | 🔜 (High) | Post Playwright results after nightly runs |
| Slack notifications for critical failures | 🔜 | Triggered by nightly runs |
| #qa-release-gates channel setup | 🔜 (Low) | Go/No-Go release workflow with automated reporting |

**Completed:**
- [x] Automated weekly Slack standup report system (01/25/2026)

---

## 6. CI/CD Pipeline & Automation Infrastructure

| Item | Status | Details |
|------|--------|---------|
| Windows Task Scheduler for nightly Playwright runs | 🔜 | Daily health checks at 6:00 AM, regression off-hours |
| Email notifications for test results | 🔜 | Python scripts for daily summaries |
| CI/CD pipeline integration | 💡 (Medium) | Blocked on pipeline engineer hire |
| Automated test runs on code push | 💡 | |
| GitHub Actions or similar CI setup | 💡 | |
| Environment-specific test gates | 💡 | |
| QA Touch CI upload script | 💡 | `tools/upload_to_qatouch.py` to scaffold |
| Test result reporting to QA Touch/Jira via pipeline | 💡 | |

---

## 7. Environment & Access

| Item | Status | Details |
|------|--------|---------|
| ReCAPTCHA bypass - Stage | 🚫 | Request sent to IT/Support, pending response |
| ReCAPTCHA bypass - Production | 🚫 | Request sent to IT/Support, pending response |
| Pre-Prod URL | 🚫 | URL needed |
| Staging environment access | 🚫 | Needs ReCAPTCHA bypass |
| Production environment access | 🚫 | Needs ReCAPTCHA bypass |
| Dedicated automation accounts | ✅ | Created as shared mailboxes with Admin role |
| OAuth email reporting setup | ✅ | qa-reports@ with Mail.Send (Application) permission |

**Automation Accounts (Created):**
- QA: `test-auto-qa@soterixsystems.com` (Admin, shared mailbox)
- Stage: `test-auto-stage@soterixsystems.com` (Admin, shared mailbox)
- Production: `test-auto-prod@soterixsystems.com` (Admin, shared mailbox - manually restrict to read-only if needed)
- Email Reporting: `qa-reports@soterixsystems.com` (User account, OAuth sender)

**Completed:**
- [x] QA environment ReCAPTCHA disabled for automation (01/25/2026)
- [x] Automation accounts created (test-auto-qa/stage/prod@) (02/05/2026)
- [x] OAuth email reporting configured (02/05/2026)

**See:** [ReCAPTCHA Bypass Plan](RECAPTCHA_BYPASS_PLAN.md)

---

## 8. Mobile Testing

| Item | Status | Details |
|------|--------|---------|
| Android automation (Appium) | 🔜 (Month 2-3) | Can run on Windows, no special hardware |
| Mobile browser emulation via Playwright | 🔜 | Chrome/Safari mobile viewport testing |
| iOS automation (Appium) | 💡 (Month 4+) | Requires Mac procurement |
| Mac Mini M2 purchase | 💡 | ~$700 - justification document created |
| Mobile device compatibility matrix | 🔜 | Define supported devices per platform |
| Mobile bug template | 💡 | Separate template with device/OS/app version fields |
| QA Touch mobile projects | 💡 | Separate projects when those spin up |

**Current State:**
- iOS: Fully native, tested manually via TestFlight
- Android: Fully native, tested manually via APK/Play Store internal testing
- No mobile web version exists

**Current Environment:** App connects to Production. QR code feature is being implemented to allow environment switching (QA/Stage/Prod) - will enable multi-environment testing when available.

**Completed:**
- [x] Mac justification document created (01/25/2026)
- [x] Identified backend environment (Production) (01/25/2026)

---

## 9. Hardware Testing (Triple Helix - Strand 2)

### Phase 1: AI-Assisted Edge Box Investigation (Short-Term)

Installing Tooling on an edge box with v1.5.0 software to explore and map the system.

| Item | Status | Details |
|------|--------|---------|
| Install Tooling on edge box (v1.5.0) | 🔄 | Set up Tooling on a live edge box to begin system investigation |
| Edge box system mapping with AI | 🔜 | Use AI to map underlying processes, services, Docker containers, and architecture |
| Create QA dashboards for system understanding | 🔜 | Visualize discovered architecture, service dependencies, and data flows |
| Document edge box architecture findings | 🔜 | Capture all discovered processes, ports, services, GPU utilization patterns |
| Build testing plan from discovered architecture | 🔜 | Use investigation findings to define what can and should be tested |
| Edge box security hardening | 🔜 | Prevent local AI tool installation and reverse engineering of system processes |

### Phase 2: Hardware Test Automation (Long-Term)

Full automated testing framework for edge box hardware - dependent on Phase 1 investigation findings.

| Item | Status | Details |
|------|--------|---------|
| Edge box health monitoring | 🔜 | Docker, RAID, GPU |
| Camera connectivity testing | 🔜 | Hanwha, i-Pro, Avigilon, Vivotek, Axis, VCA, and more |
| Temperature/power/storage monitoring | 🔜 | Environmental monitoring |
| Power management testing | 🔜 | |
| RAID/network/firmware validation | 🔜 | |
| ONVIF compliance & camera discovery | 🔜 | Protocol compliance testing |
| Storage health (RAID status) | 🔜 | |
| Network interface testing | 🔜 | |

### Phase 3: LLM Testing (Future)

| Item | Status | Details |
|------|--------|---------|
| Identify LLM testing requirements | 💡 | Define scope for on-device LLM validation |
| LLM hardware testing | 💡 | GPU utilization, memory requirements, thermal performance |
| LLM software testing | 💡 | Model loading, inference accuracy, response quality |
| LLM benchmarking | 💡 | Latency, throughput, tokens/second metrics |

**Access:**
- WireGuard VPN configured for remote access
- TeamViewer available for remote desktop
- QA Lab has 25 cameras across 6 brands

---

## 10. AI/ML Testing (Triple Helix - Strand 3)

| Item | Status | Details |
|------|--------|---------|
| Model accuracy benchmarks | 🔜 | Precision/recall on live feeds |
| Inference performance tests | 🔜 | |
| Bias detection / drift monitoring | 🔜 | |
| False positive/negative analysis | 🔜 | |
| Performance under different lighting/conditions | 🔜 | |
| Data annotation quality verification | 🔜 | |

---

## 11. Cloud Infrastructure

| Item | Status | Details |
|------|--------|---------|
| Linode instance monitoring | 🚫 | Console access request needed |
| MongoDB test data validation | 🚫 | Read-only access requested |
| Prometheus/Grafana dashboards | 🔄 | Basic setup from Richard available; evaluating DCT (3rd party MSP) platform |
| Performance/load testing (k6 or Locust) | 🔜 | |

**Current Access:**
- Grafana dashboards (view-only)
- Basic Prometheus/Grafana setup (Richard)

---

## 12. Performance Testing

| Item | Status | Details |
|------|--------|---------|
| Load testing for concurrent users | 🔜 | |
| Stress testing for camera feeds | 🔜 | |
| API response time benchmarking | 🔜 | |
| Video/streaming latency measurement | 💡 | |

---

## 13. Security Testing

| Item | Status | Details |
|------|--------|---------|
| Authentication bypass attempts | Partially covered | |
| API authorization validation | 🔜 | |
| Input validation (SQL injection, XSS) | Partially covered | |
| Session management testing | 🔜 | |
| Security testing expansion | 💡 | Beyond current XSS/SQL injection coverage |

---

## 14. Accessibility & Localization

| Item | Status | Details |
|------|--------|---------|
| WCAG compliance for web UI | 💡 | |
| Screen reader compatibility | 💡 | |
| Keyboard navigation | 💡 | |
| Timezone testing | 💡 | English-only; timezone format validation |

---

## 15. Role-Based Permission Testing

| Item | Status | Details |
|------|--------|---------|
| Role-based test framework | 💡 | Super Admin, Admin, Supervisor, Operator test suites |
| Permission boundary testing | 💡 | Parametrized tests for what each role CAN and CANNOT do |
| Role switching workflows | 💡 | |
| Dedicated test accounts per role per environment | 💡 | `qa-superadmin@`, `qa-admin@`, `qa-supervisor@`, `qa-operator@` |

**Dependencies:** Role matrix finalized, dedicated accounts created by IT

---

## 16. Partner Admin Tool Testing

| Item | Status | Details |
|------|--------|---------|
| Site provisioning testing | 🔄 | Edge Box device certification underway |
| Automated edge box validation tool testing | 🔜 | Test the automated validation tool devs are building |
| Billing and licensing testing | 💡 | |
| White-label configuration testing | 💡 | |

**Completed:**
- [x] Partner Admin test cases created and in use (01/25/2026)

---

## 17. Reporting & Communication

| Item | Status | Details |
|------|--------|---------|
| QA Touch executive dashboards | 🔜 | Weekly summary, release readiness |
| Automated test execution summaries (email) | 🔜 | Triggered by nightly runs |
| Investor slide QA content updates | 🔜 | Keep slide current as progress advances |
| Standardized test execution reports template | 🔜 | |

**Completed:**
- [x] Automated weekly Slack standup report system (01/25/2026)
- [x] iOS/Android mobile category tracking in reports (01/25/2026)
- [x] Automation vs. Manual tracking in reports (01/25/2026)

---

## 18. Documentation & Deliverables

| Item | Status | Details |
|------|--------|---------|
| QA team onboarding guide for new members | 🔜 | Roles, permissions, tool access |
| Standardized test execution reports template | 🔜 | |

**Completed:**
- [x] Triple-Helix Testing Methodology document (01/25/2026)
- [x] Simplified QA Priority Matrix / Bug Priority Guide (01/25/2026)
- [x] Soterix brand-compliant PPTX template (01/25/2026)
- [x] QA Touch Setup Guide v2.0 (01/25/2026)
- [x] Future Roadmap doc (01/25/2026)
- [x] Selenium to Playwright Migration status (01/25/2026)
- [x] ReCAPTCHA bypass plan (01/25/2026)
- [x] Mac justification document (01/25/2026)
- [x] Session summary template (01/25/2026)
- [x] Credentials setup guide (01/25/2026)
- [x] API testing notes (01/24/2026)
- [x] Session caching implementation doc (01/27/2026)
- [x] QA Touch import plan (02/03/2026)
- [x] QA Touch team guide (02/03/2026)
- [x] QA Things to Know guide (01/27/2026)
- [x] Interactive HTML dashboard with auto-generation script (02/03/2026)

---

## 19. Team & Process

| Item | Status | Details |
|------|--------|---------|
| QA Touch team setup (3 additional testers) | 🔄 | Roles and permissions |
| Onboard Nik to QA support | 🔄 | Backlogs and foundational tool ramp up |
| Cross-training requirements | 🔜 | Prevent bottlenecks |
| Secrets management for India team | 🔜 | No 1Password - secure .env sharing process needed |

**Completed:**
- [x] Team structure defined (01/25/2026)
- [x] Daily Slack standups at 9:15 AM CST (01/25/2026)

---

## 20. Recurring Maintenance

| Item | Cadence | Details |
|------|---------|---------|
| Azure OAuth secret rotation | **Due July 22, 2026** | Reminder set for July 8 |
| Flaky test review | Monthly | |
| QA Touch cleanup | Monthly | |
| Coverage review | Monthly | |
| API schema updates | Quarterly | |
| Credential rotation | Quarterly | |
| Jira custom field review | Quarterly | |
| Dependency updates | Quarterly | |
| Framework review | Annual | |
| Security audit | Annual | |

---

## Timeline Overview

| Timeframe | Focus |
|-----------|-------|
| **Month 1-2 (Current)** | Complete Views & Events migration, QA Touch tagging & guide v2.0, JIRA NexaiQ-Core setup, pytest markers, gap analysis start |
| **Month 2-3** | Search/Media/Insights/Admin migration, Windows Task Scheduler nightly runs, Android Appium, QA Touch step fill-in, Slack webhooks, smart bug creation scripts |
| **Month 3-4** | Complete Selenium migration, hardware testing framework, 100+ tests, role-based permission framework |
| **Month 5-6** | Cloud infrastructure testing, performance testing, Partner Admin Tool, Mac procurement for iOS |
| **Month 7+** | iOS automation, advanced AI/ML testing, new feature coverage, localization, continuous improvement |

---

## Tool Stack

| Purpose | Current | Planned |
|---------|---------|---------|
| Test Automation (Web) | Playwright + pytest | Continue |
| API Testing | requests + pytest | Continue |
| Test Management | QA Touch | + CI integration, API bulk ops |
| Issue Tracking | Jira (NC, company-managed) | + Smart bug creation scripts |
| Communication | Slack (automated standups) | + QA Touch webhooks & Playwright bot |
| CI/CD | Windows Task Scheduler (planned) | GitHub Actions / Jenkins (future) |
| Monitoring | Grafana (view) | + Prometheus direct access |
| Mobile Testing (Android) | Manual (APK) | Appium + Playwright mobile emulation |
| Mobile Testing (iOS) | TestFlight (manual) | Appium (requires Mac) |
| Performance | - | k6 or Locust |
| Reporting | Weekly Slack standup reports | + Email summaries, QA Touch dashboards |

---

## Outstanding Questions

| Question | Action Needed |
|----------|---------------|
| Pre-Prod URL | URL not yet available |
| MongoDB access | Request read-only access for test data validation |
| Prometheus access | Request direct access for custom metric queries |
| Linode access | Request console access for instance monitoring |
| Mobile backend | Ask India developer which environment app connects to |
| Environment switching | Ask if app can switch between QA/Stage/Prod |
| Pipeline engineer | Hire timeline affects CI/CD work |
| Role matrix | Needs finalization for permission testing suite |
| India team secrets | 1Password alternative needed for secure credential sharing |

---

## Priority Summary (Quick Reference)

### Immediate (Now)
1. Continue Playwright Views/Events module migration
2. Finish QA Touch Setup Guide v2.0 expansion
3. Add steps to 1,100+ title-only test cases in QA Touch
4. Complete QA Touch-Jira integration configuration
5. Add pytest markers to Login & API tests

### Short-Term (Next 1-2 Months)
6. Expand Playwright automation toward 212-test target
7. Set up Windows Task Scheduler for nightly runs
8. Set up dedicated automation service accounts
9. Gap analysis: QA Touch vs Playwright vs website features
10. QA Touch Slack webhooks
11. QA and Leadership dashboards in QA Touch
12. Edge box AI investigation - install Tooling on v1.5.0 edge box, map system architecture

### Medium-Term (2-4 Months)
13. Android automation with Appium
14. Role-based permission testing framework
15. Camera streaming validation tests
16. Smart bug creation scripts (Playwright -> Jira)
17. Partner Admin Tool testing
18. Cloud infrastructure monitoring dashboards

### Long-Term / When Resources Allow
19. iOS automation (requires Mac purchase)
20. CI/CD pipeline integration (requires engineer hire)
21. AI analytics testing framework
22. Edge box hardware test automation (dependent on Phase 1 investigation findings)
23. Load testing for multi-customer simulation

---

## Related Documents

- [Implementation Roadmap](IMPLEMENTATION_ROADMAP.md)
- [Selenium Migration Status](SELENIUM_TO_PLAYWRIGHT_MIGRATION.md)
- [ReCAPTCHA Bypass Plan](RECAPTCHA_BYPASS_PLAN.md)
- [QA Touch Import Plan](QA_TOUCH_IMPORT_PLAN.md)
- [QA Touch Team Guide](QA_TOUCH_TEAM_GUIDE.md)
- [Mac Justification for iOS Testing](MAC_JUSTIFICATION_FOR_IOS_TESTING.md)
- [Credentials Setup](CREDENTIALS_SETUP.md)
- [Maintenance Reminders](MAINTENANCE_REMINDERS.md)
- [Triple-Helix Methodology](../Optimized_Triple-Helix_Testing_Methodology_for_AI_VSAAS_QA.md)
