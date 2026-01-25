# TODO - Next Session

## Before Continuing Development

### 1. Project Cleanup & Refactor
- [ ] Fix SSL verification issue (make configurable in `tests/shared/api_clients/base_api_client.py`)
- [ ] Run full test suite and verify all 26 core tests pass
- [ ] Check for any remaining scaffolding files that should be removed
- [ ] Review all files in `tests/` folder for consistency

# TODO - Next Session

## Immediate Tasks

### 1. Fix SSL Verification Issue
- [ ] Make SSL verification configurable in `tests/shared/api_clients/base_api_client.py`
- [ ] Add `SSL_VERIFY` environment variable support
- [ ] Test with `SSL_VERIFY=false` for QA environment

# TODO - Next Session

## Immediate Tasks

### 1. Fix SSL Verification Issue
- [ ] Make SSL verification configurable in `tests/shared/api_clients/base_api_client.py`
- [ ] Add `SSL_VERIFY` environment variable support
- [ ] Test with `SSL_VERIFY=false` for QA environment

### 2. Verify Tests Pass
- [ ] Run: `pytest tests/api/smoke/ tests/ui/login/ -v`
- [ ] Confirm all 26 core tests pass
- [ ] Fix any remaining failures

## Ready to Continue Development

### Views Module Migration (Next Priority)
- [ ] Review Selenium Views tests in `legacy-selenium-tests/`
- [ ] Create `ViewsPage` Page Object Model
- [ ] Migrate 27 thumbnail view tests
- [ ] Migrate 13 full screen view tests
### Views Module Migration (Next Priority)
- [ ] Review Selenium Views tests in `legacy-selenium-tests/`
- [x] Create `ViewsPage` Page Object Model
- [ ] Migrate 27 thumbnail view tests
- [ ] Migrate 13 full screen view tests

Notes:
- 3 basic Views tests passing

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
| **Total** | **29** |

## Commands Reference
```powershell
# Activate environment
.\venv\Scripts\Activate.ps1

# Run API tests
pytest tests/api/smoke/ -v

# Run Login UI tests
pytest tests/ui/login/ -v

# Run all tests
pytest tests/ -v

# Run with SSL verification disabled (if needed for QA)
$env:SSL_VERIFY='false'; pytest tests/ -v
```
