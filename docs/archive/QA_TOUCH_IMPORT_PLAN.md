# QA Touch Migration Plan

## Overview

This document outlines the plan for migrating test cases from Bugasura to QA Touch.

**Status:** ✅ IMPORT COMPLETE & VERIFIED - 1,528 test cases imported to QA Touch (2026-02-02)

**Note:** Priority field is NOT used in QA Touch import (removed from CSV).

**Import Fix:** Re-imported with newline-separated steps (v2) after initial pipe-separated format caused step truncation.

---

## Current Data Summary

| Source | Test Cases | Data Quality | Status |
|--------|-----------|--------------|--------|
| `testcases_export.json` | 428 | Full steps (title, conditions, steps) | ✅ Ready |
| `bugasura_*.json` (12 files) | 1,100 | High-level (id, title) | ✅ Ready |
| **Combined CSV** | **1,528** | Mixed | ✅ Ready for import |

**Import File:** `tests/data/qa_touch_import.csv`

---

## QA Touch Project Structure

### Recommended Hierarchy

```
NEXAIQ VSaaS (Project)
|
+-- Core Features (Module)
|     +-- Login (17 test cases) - Full steps
|     +-- Logout (8) - Full steps
|     +-- Views (186) - Full steps
|     +-- Search (167) - Mixed
|     +-- Maps (16) - Full steps
|     +-- LPR (26) - Full steps
|     +-- Insights (36) - Title only
|     +-- Media (42) - Mixed
|     +-- Notifications (21) - Full steps
|     +-- Chats (12) - Full steps
|     +-- Audio (6) - Full steps
|
+-- Admin (Module)
      +-- Dashboard (18) - Mixed
      +-- Sites (68) - Mixed
      +-- Users & Roles (55) - Title only
      +-- Maps (100) - Title only
      +-- Rules (204) - Title only ✅ COMPLETE
      +-- General (200) - Title only ✅ COMPLETE
      +-- LPR (115) - Title only
      +-- Licences (187) - Title only
      +-- Integrations (44) - Title only
```

---

## Test Case Inventory by Module

### Full Steps Available (428 test cases)

| Module | Count | Source | Ready |
|--------|-------|--------|-------|
| Core Features > Views | 186 | testcases_export.json | ✅ |
| Core Features > Search | 167 | testcases_export.json | ✅ |
| Core Features > Media | 42 | testcases_export.json | ✅ |
| Core Features > Insights | 36 | testcases_export.json | ✅ |
| Core Features > LPR | 26 | testcases_export.json | ✅ |
| Core Features > Notifications | 21 | testcases_export.json | ✅ |
| Admin > Dashboard | 18 | testcases_export.json | ✅ |
| Core Features > Login | 17 | testcases_export.json | ✅ |
| Core Features > Maps | 16 | testcases_export.json | ✅ |
| Core Features > Chats | 12 | testcases_export.json | ✅ |
| Core Features > Logout | 8 | testcases_export.json | ✅ |
| Core Features > Audio | 6 | testcases_export.json | ✅ |

### High-Level Only (1,100 test cases)

| Module | Count | JSON File | Status |
|--------|-------|-----------|--------|
| Admin > Rules | 204 | bugasura_admin_rules_test_cases.json | ✅ COMPLETE |
| Admin > General | 200 | bugasura_admin_general_test_cases.json | ✅ COMPLETE |
| Admin > Licences | 187 | bugasura_admin_licences_test_cases.json | ✅ |
| Admin > LPR | 115 | bugasura_admin_lpr_test_cases.json | ✅ |
| Admin > Maps | 100 | bugasura_admin_maps_test_cases.json | ✅ |
| Admin > Sites | 68 | bugasura_admin_sites_test_cases.json | ✅ |
| Admin > Users & Roles | 55 | bugasura_admin_users_roles_test_cases.json | ✅ |
| Admin > Integrations | 44 | bugasura_admin_integrations_test_cases.json | ✅ |

---

## Import Strategy

### Phase 1: CSV Import (Ready Now)
Import all test cases from the prepared CSV file:

1. **Create QA Touch project**: NEXAIQ VSaaS
2. **Import CSV**: `tests/data/qa_touch_import.csv`
3. **Verify import**: 1,528 test cases across all modules

**CSV Format** (no priority column):
- external_id, module, title, preconditions, steps, expected_result, tags, data_quality

### Phase 2: Enrich with Full Steps (If Needed)
For test cases marked "Title Only":
1. Match by Test ID (TES###)
2. Update with steps, conditions, expected results from spreadsheet
3. Verify completeness

---

## QA Touch Import Format

### CSV Format (Used for import - NO PRIORITY)
```csv
external_id,module,title,preconditions,steps,expected_result,tags,data_quality
TES101,Core Features > Login,XSS Attack Attempt Test,"User on login page","1. Navigate to login|2. Enter script in username|3. Click Login",No script execution,Security,Full
```

**Note:** Priority column has been removed as it will not be used in QA Touch.

---

## Field Mapping: Bugasura to QA Touch

| Bugasura Field | QA Touch Field | Notes |
|----------------|----------------|-------|
| id (TES###) | External ID | For cross-reference |
| title | Title | Required |
| ~~priority~~ | ~~Priority~~ | **NOT USED** |
| folder | Module | Map to hierarchy |
| subfolder | Sub-module | Optional |
| testConditions | Preconditions | If available |
| steps | Test Steps | If available |
| acceptanceCriteria | Expected Result | If available |
| tags | Tags | Optional |

---

## Files Ready for Import

| File | Location | Records | Status |
|------|----------|---------|--------|
| **Import CSV v2** | `tests/data/qa_touch_import_v2.csv` | **1,528** | ✅ IMPORTED |
| Master CSV | `tests/data/qa_touch_master.csv` | 1,528 | Source (duplicates fixed) |
| Full steps source | `testcases_export.json` | 428 | Source data |
| High-level source | `tests/data/bugasura_*.json` | 1,100 | Source data |

---

## Action Items

### Completed
- [x] Generate merged CSV for import ✅
- [x] Remove priority column ✅
- [x] Add missing Admin-General test cases (8 added) ✅
- [x] Access QA Touch and create project ✅
- [x] Import `tests/data/qa_touch_import.csv` ✅
- [x] Fix step truncation issue (re-import with newline separator) ✅
- [x] Verify 1,528 test cases imported with correct steps ✅ (2026-02-02)
- [x] Validate 428 test cases with full steps intact ✅
- [x] Confirm 9 renamed duplicates present ✅

### Post-Import (In Progress)
- [ ] Fill in missing steps for "Title Only" test cases (~1,100 need steps)
- [ ] Set up test execution plans

---

## Notes

- **Import completed & verified**: 2026-02-02 - 1,528 test cases imported to QA Touch
- **With full steps**: 428 test cases have complete steps, conditions, expected results
- **Multi-line steps**: 426 test cases with newline-separated steps working correctly
- **Title only**: ~1,100 test cases need steps added (from incoming spreadsheet)
- **Step format fix**: Changed from pipe (`|`) to newline (`\n`) separator - v2 file
- **Renamed duplicates**: 9 duplicate titles renamed with `(2)`, `(3)`, `(4)` suffixes
- **Import file**: `tests/data/qa_touch_import_v2.csv` (final working version)
- **Master file**: `tests/data/qa_touch_master.csv` (source with duplicates fixed)
- **Priority NOT used**: Removed from CSV per project requirements
- **Admin-General**: ✅ COMPLETE - 200 test cases (TES843-TES1042)
- **Admin-Rules**: ✅ COMPLETE - 204 test cases (TES777-TES1507)
- **Bugasura reference**: https://my.bugasura.io/testCases/120847
