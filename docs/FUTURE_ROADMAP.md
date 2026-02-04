# Unified Roadmap - Soterix QA Automation

> **Last Updated:** 2026-02-03
> **Sources:** Tooling Code (Terminal), Tooling Code (VS Code), Tooling Chat (tooling.ai project)
> **Migration Progress:** ~16% (49 of ~212 Selenium tests migrated)
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

## 1. Playwright Test Migration

### Phase 2: Core Modules (IN PROGRESS)

| Item | Tests | Status | Details |
|------|-------|--------|---------|
| Add markers to Login tests | 10 | 🔜 | `ui`, `smoke`/`sanity` markers |
| Add markers to API tests | 16 | 🔜 | `api`, `smoke` markers |
| Views module expansion | ~34 remaining | 🔄 | 6 of ~40 migrated; live view, sequence/playlist, grid layout remaining |
| Events module migration | 26 | 🔜 | Need EventsPage POM first |
| Logout tests | - | 🔜 | Standalone test suite |

### Phase 3: Extended Coverage (PLANNED)

| Module | Tests | Priority | Notes |
|--------|-------|----------|-------|
| Search | 24 | High | HAR capture needed |
| Media | 30 | Medium | Clip management |
| Insights | 26 | Medium | System Status dashboard click-through |
| Admin Rules | 14 | Medium | |
| Admin Sites | 12 | Low | |
| Admin Users | 9 | Low | |
| Chats | 12 | Low | |
| Maps | 4 | Low | |
| Notifications | 3 | Low | |

### Phase 4: New Coverage (FUTURE)

Modules with no existing Selenium coverage:

| Module | Test Cases Identified |
|--------|----------------------|
| LPR | 14 |
| Admin Maps | 17 |
| Admin Integrations | 21 |
| Admin General | 16 |
| Admin LPR | 10 |
| Admin Licenses | 10 |

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
| Test organization decision | 💡 | Class-based vs markers vs separate files - pending |
| Project hours tracking system | 💡 | PROJECT_HOURS_LOG.md proposed |

**Completed:**
- [x] pytest markers setup (smoke, regression, api, ui, drag_drop, live_streaming)
- [x] Page Object Model structure (shared page objects folder)
- [x] Session caching implementation (cookies + localStorage injection)
- [x] Session summary template created

---

## 2. QA Touch Integration

| Item | Status | Details |
|------|--------|---------|
| Fill in ~1,100 "Title Only" test case steps | 🚫 | Waiting on incoming spreadsheet from QA team |
| QA Touch Setup Guide v2.0 expansion | 🔄 | Expanded from 619 to 1,360 lines |
| Tag test cases with SMOKE (~50-75) | 🔜 | |
| Tag test cases with REGRESSION (~200-400) | 🔜 | |
| Set up test execution plans | 🔜 | |
| Test Run creation workflows | 🔜 | 5 run types: Release, Smoke, Sprint, Nightly, Full Regression |
| Manual Playwright result upload to QA Touch | 🔜 | Batch import process before automation is ready |
| Automated Playwright -> QA Touch result upload | 🔜 (High) | Needs QA Touch API + Playwright migration further along |
| AUTOMATED tag sync script | 🔜 (Low) | Auto-tag test cases matching Playwright tests |
| QA Touch API integration for bulk ops | 🔜 (Medium) | |
| Gap analysis automation | 🔜 (Medium) | Compare QA Touch vs Playwright vs website features |
| Test case versioning and maintenance procedures | 🔜 | |
| Requirements traceability in QA Touch | 🔜 | |
| QA dashboards | 🔜 | Test execution metrics, pass/fail rates, coverage |
| Leadership/PM dashboards | 🔜 | Milestone-based, release readiness, quality trends |
| Additional QA Touch projects | 💡 | NexaiQ-Private Cloud, NexaiQ-iOS, NexaiQ-Android, NexaiQ-Technician App, NexaiQ-Partner Admin Tool |

**Completed:**
- [x] 1,528 test cases imported (verified 2026-02-02)
- [x] QA Touch team guide created
- [x] Module structure created (mirrors NexaiQ navigation)
- [x] CSV import issues resolved (pipe separator, duplicates, grammar)
- [x] DELETE-REQUEST saved filter setup

---

## 3. JIRA NexaiQ-Core Integration

| Item | Status | Details |
|------|--------|---------|
| Complete Jira instance setup/testing | 🔄 | Company-managed, project key = NC |
| Define project structure and workflows | 🔜 | |
| Configure QA Touch -> Jira integration | 🔜 | API token setup, field mapping |
| Configure Playwright -> Jira integration | 🔜 | Automated bug creation on test failure |
| Smart bug creation scripts | 🔜 | `smart_jira_bug_creator.py`, `update_failure_history.py`, `review_queue.py`, `flaky_tests.json` |
| Sprint/release test coverage reports | 🔜 | |
| Create QA metrics dashboards | 🔜 | |
| Jira custom field review | Quarterly | Recurring maintenance |

**Completed:**
- [x] Jira instance created (https://soterixsystems.atlassian.net)

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
- [x] Automated weekly Slack standup report system (Python + Slack SDK + pandas + openpyxl)

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
| Dedicated automation accounts | 🔜 | Disabled password expiration, disabled MFA, enabled IMAP |

**Requested Automation Accounts:**
- Stage: `automation-stage@soterixsystems.com` (Admin)
- Pre-Prod: `automation-preprod@soterixsystems.com` (Admin)
- Production: `automation-prod@soterixsystems.com` (Operator, read-only)

**Completed:**
- [x] QA environment ReCAPTCHA disabled for automation

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

**To Request from India Developer:**
- [ ] Documentation on which backend environment the app connects to
- [ ] Instructions for switching environments in the app (if possible)
- [ ] Release notes for each TestFlight/APK build

**Completed:**
- [x] Mac justification document created

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
| Edge box health monitoring | 🔜 | Docker, RAID, GPU (A-100/A-1000/A-4000) |
| Camera connectivity testing | 🔜 | Hanwha, i-Pro, Avigilon, Vivotek, Axis, VCA |
| Temperature/power/storage monitoring | 🔜 | Environmental monitoring |
| Power management testing | 🔜 | |
| RAID/network/firmware validation | 🔜 | |
| ONVIF compliance & camera discovery | 🔜 | Protocol compliance testing |
| Storage health (RAID status) | 🔜 | |
| Network interface testing | 🔜 | |

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
| Prometheus custom metrics | 🚫 | Direct access request needed |
| Performance/load testing (k6 or Locust) | 🔜 | |

**Current Access:**
- Grafana dashboards (view-only)

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
| Localization testing | 💡 | Multi-language, date/time formats |

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
| Partner login and authentication testing | 💡 | Credentials available per environment |
| Customer/site management testing | 💡 | System Integrator workflows |
| Site provisioning testing | 💡 | |
| Billing and licensing testing | 💡 | |
| White-label configuration testing | 💡 | |

---

## 17. Reporting & Communication

| Item | Status | Details |
|------|--------|---------|
| QA Touch executive dashboards | 🔜 | Weekly summary, release readiness |
| Automated test execution summaries (email) | 🔜 | Triggered by nightly runs |
| Investor slide QA content updates | 🔜 | Keep slide current as progress advances |
| Standardized test execution reports template | 🔜 | |

**Completed:**
- [x] Automated weekly Slack standup report system (Python + Slack SDK + pandas + openpyxl)
- [x] Customer-feature mapping (Video Wall -> UTSW, etc.)
- [x] iOS/Android mobile category tracking in reports
- [x] Automation vs. Manual tracking in reports

---

## 18. Documentation & Deliverables

| Item | Status | Details |
|------|--------|---------|
| QA team onboarding guide for new members | 🔜 | Roles, permissions, tool access |
| Standardized test execution reports template | 🔜 | |

**Completed:**
- [x] Triple-Helix Testing Methodology document (85% alignment with 2025 QA trends)
- [x] Triple-Helix Venn diagram visual (three-circle design)
- [x] Simplified QA Priority Matrix / Bug Priority Guide (HTML)
- [x] Brand Guidelines skill for Tooling (installed in private user folder)
- [x] Soterix brand-compliant PPTX template (validated)
- [x] QA Touch Setup Guide v2.0 (1,360 lines, 13 sections + appendices)
- [x] Future Roadmap doc in Playwright repo
- [x] Migration status tracking
- [x] ReCAPTCHA bypass plan documented
- [x] Mac justification document for iOS testing
- [x] Session summary template

---

## 19. Team & Process

| Item | Status | Details |
|------|--------|---------|
| QA Touch team setup (3 additional testers) | 🔄 | Roles and permissions |
| Specialization streams | 🔜 | Automation Specialist + Process & Systems Specialist |
| Cross-training requirements | 🔜 | Prevent bottlenecks |
| Secrets management for India team | 🔜 | No 1Password - secure .env sharing process needed |

**Completed:**
- [x] Team structure defined (QA Lead Justin + QA Engineer A + QA Engineer B in India)
- [x] Daily Slack standups at 9:15 AM CST (automated via Slack workflow)

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
