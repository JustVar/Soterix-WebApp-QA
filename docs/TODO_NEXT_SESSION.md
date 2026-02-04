# TODO - Next Session

## Session Summary (2026-02-03) - JIRA NexaiQ-Core Update, API Tests, QA Touch Team Guide

### Completed This Session
- ✅ Updated Jira project key from SOTE to NC across codebase (.env.template, test_jira_connection.py)
- ✅ Ran API smoke tests - 16/16 passed
- ✅ Verified pytest collects all 49 tests with no errors
- ✅ Created QA_TOUCH_TEAM_GUIDE.md - team-facing guide with usage, expectations, and import status
- ✅ Created QA_TOUCH_IMPORT_PLAN.md - import plan documentation
- ✅ Reviewed and organized files for git commit (9 files staged, excluded local/temp files)
- ✅ Updated .gitignore for permanently excluded items

### Previous Session (2026-02-02) - QA Touch Import COMPLETE & VERIFIED
- ✅ QA Touch import successful - 1,528 test cases imported
- ✅ Created compare_import.py tool for CSV comparison
- ✅ Created validate_qa_touch_import.py validation script
- ✅ Identified step truncation issue (pipe separator misinterpreted)
- ✅ Regenerated CSV with newline-separated steps (qa_touch_import_v2.csv)
- ✅ Re-imported and verified all 1,528 test cases
- ✅ Confirmed 428 test cases with full steps intact
- ✅ Confirmed 9 renamed duplicates present

### Previous Session (2026-02-01) - Bugasura Extraction
- ✅ Extracted Admin-Maps folder (100 test cases, TES662-TES761)
- ✅ Extracted Admin-Dashboard folder (17 test cases, TES57-TES74)
- ✅ Extracted Admin-Sites folder (67 test cases, TES553-TES620)
- ✅ Extracted Admin-Users&Roles folder (56 test cases, TES621-TES661, TES762-TES776)
- ✅ Extracted Admin-Integrations folder (48 test cases, TES795-TES842)

### Previous Session Extractions
- ✅ Extracted Insights folder (37 test cases, TES360-TES396)
- ✅ Extracted Search folder (118 test cases, TES410-TES527)
- ✅ Extracted Admin-Rules folder (204 test cases, TES777-TES1507)
- ✅ Extracted Admin-General folder (200 test cases, TES843-TES1042)
- ✅ Extracted Admin-LPR folder (115 test cases, TES1053-TES1542)
- ✅ Extracted Admin-Licences folder (187 test cases, TES1123-TES1309)
- ✅ Extracted Media folder (28 test cases, TES75-TES103)

---

## Bugasura Extraction Progress - COMPLETE

| Folder | Test Cases | Status | JSON File |
|--------|------------|--------|-----------|
| Login | ~20 | ✅ Complete | (in Playwright tests) |
| Chats | ~10 | ✅ Complete | (in Playwright tests) |
| Notifications | ~15 | ✅ Complete | (in Playwright tests) |
| Logout | ~10 | ✅ Complete | (in Playwright tests) |
| Views | ~50 | ✅ Complete | (in Playwright tests) |
| Events | ~30 | ✅ Complete | (in Playwright tests) |
| Search | 118 | ✅ Complete | bugasura_search_test_cases.json |
| LPR | 25 | ✅ Complete | (in Playwright tests) |
| Maps | 16 | ✅ Complete | (in Playwright tests) |
| Insights | 37 | ✅ Complete | bugasura_insights_test_cases.json |
| Admin-Rules | 204 | ✅ Complete | bugasura_admin_rules_test_cases.json |
| Admin-General | 200 | ✅ Complete | bugasura_admin_general_test_cases.json |
| Admin-LPR | 115 | ✅ Complete | bugasura_admin_lpr_test_cases.json |
| Admin-Licences | 187 | ✅ Complete | bugasura_admin_licences_test_cases.json |
| Media | 28 | ✅ Complete | bugasura_media_test_cases.json |
| Admin-Maps | 100 | ✅ Complete | bugasura_admin_maps_test_cases.json |
| Admin-Dashboard | 17 | ✅ Complete | bugasura_admin_dashboard_test_cases.json |
| Admin-Sites | 67 | ✅ Complete | bugasura_admin_sites_test_cases.json |
| Admin-Users&Roles | 56 | ✅ Complete | bugasura_admin_users_roles_test_cases.json |
| Admin-Integrations | 48 | ✅ Complete | bugasura_admin_integrations_test_cases.json |
| **TOTAL** | **~1,353** | **✅ COMPLETE** | |

---

## JSON Files Created (All High-Level Extraction)

| File | Test Cases | Test Steps |
|------|------------|------------|
| `bugasura_insights_test_cases.json` | 37 | ❌ Title only |
| `bugasura_search_test_cases.json` | 118 | ❌ Title only |
| `bugasura_admin_rules_test_cases.json` | 204 | ❌ Title only |
| `bugasura_admin_general_test_cases.json` | 200 | ❌ Title only |
| `bugasura_admin_lpr_test_cases.json` | 115 | ❌ Title only |
| `bugasura_admin_licences_test_cases.json` | 187 | ❌ Title only |
| `bugasura_media_test_cases.json` | 28 | ❌ Title only |
| `bugasura_admin_maps_test_cases.json` | 100 | ❌ Title only |
| `bugasura_admin_dashboard_test_cases.json` | 17 | ❌ Title only |
| `bugasura_admin_sites_test_cases.json` | 67 | ❌ Title only |
| `bugasura_admin_users_roles_test_cases.json` | 56 | ❌ Title only |
| `bugasura_admin_integrations_test_cases.json` | 48 | ❌ Title only |
| **Total in JSON** | **1,177** | |

---

## Next Tasks (Playwright Migration)

### 1. Add Markers to Login and API Tests
- [ ] Add markers to 10 Login tests (ui, smoke/sanity)
- [ ] Add markers to 16 API tests (api, smoke)

### 2. Continue Views Migration
- [ ] Share live view tests
- [ ] Sequence/playlist tests
- [ ] Grid layout switching tests

### 3. Events Module Migration (26 tests)
- [ ] Create EventsPage Page Object Model
- [ ] Migrate 26 events tests from legacy Selenium

---

## Commands Reference

```powershell
# Activate environment
.\.venv\Scripts\Activate.ps1

# Run all tests
pytest tests/ -v

# Run by marker
pytest -m views_devices -v
pytest -m "subtabs and checkbox" -v

# Collect only (verify markers without running)
pytest --collect-only -m views_myviews -v

# Run with visible browser
pytest tests/ui/views/ -v --headed
```

---

## Pending External Actions

- [ ] ReCAPTCHA bypass - request sent to IT/Support (pending response)
- [x] QA Touch - 1,528 test cases imported & verified ✅ (2026-02-02)
- [ ] JIRA NexaiQ-Core - company-managed instance in test phase (project key updated to NC)
- [ ] Incoming spreadsheet - for filling in "Title Only" test case steps (~1,100 need steps)
- [ ] QA Touch suite tagging - tag test cases with SMOKE and REGRESSION tags

---

## Browser Tab Reference
| Purpose | Value |
|---------|-------|
| Bugasura Tab ID | 492638011 |
