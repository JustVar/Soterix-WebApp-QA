# TODO - Next Session

## Before Continuing Development

### 1. Project Cleanup & Refactor
- [x] Fix SSL verification issue (configured in `tests/shared/api_clients/base_api_client.py`)
- [ ] Run full test suite and verify all 35 core tests pass
- [ ] Check for any remaining scaffolding files that should be removed
- [ ] Review all files in `tests/` folder for consistency

## Immediate Tasks

### 1. Verify Tests Pass
- [ ] Run: `pytest tests/api/smoke/ tests/ui/login/ -v`
- [ ] Confirm all 35 core tests pass
- [ ] Fix any remaining failures

## Ready to Continue Development

### Views Module Migration (In Progress)
- [x] Create `ViewsPage` Page Object Model
- [x] Implement 9 Views UI tests (tab management, thumbnails, rename functionality)
- [ ] Migrate remaining thumbnail view tests (18 remaining)
- [ ] Migrate 13 full screen view tests

Notes:
- 9 Views tests passing

### Events Module Migration
- [ ] Create `EventsPage` Page Object Model
- [ ] Migrate 26 events tests

## Pending External Actions

### ReCAPTCHA Bypass (Send Request to Tech Team)
- [ ] Send email from `docs/RECAPTCHA_BYPASS_PLAN.md`
- [ ] Create 10 automation accounts across 4 environments
- [ ] Get bypass configured for automation accounts

### Tool Integration (Waiting on Licenses/Setup)
- [ ] QA Touch - waiting for yearly license purchase
- [ ] Jira - new company-managed instance in test phase

## Test Summary
| Category | Tests |
|----------|-------|
| API Smoke | 16 |
| Login UI | 10 |
| Views UI | 9 |
| **Total** | **35** |

## Commands Reference
```powershell
# Activate environment
.\.venv\Scripts\Activate.ps1

# Run API tests
pytest tests/api/smoke/ -v

# Run Login UI tests
pytest tests/ui/login/ -v

# Run all tests
pytest tests/ -v

# Run with SSL verification disabled (if needed for QA)
$env:SSL_VERIFY='false'; pytest tests/ -v
```
