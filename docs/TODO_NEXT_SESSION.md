# TODO - Next Session

## Before Continuing Development

### 1. Project Cleanup & Refactor
- [ ] Fix SSL verification issue (make configurable in `tests/shared/api_clients/base_api_client.py`)
- [ ] Run full test suite and verify all 26 core tests pass
- [ ] Check for any remaining scaffolding files that should be removed
- [ ] Review all files in `tests/` folder for consistency

### 2. Verify Current State
- [ ] 16 API smoke tests passing
- [ ] 10 Login UI tests passing
- [ ] All tests run against QA environment by default

## Pending External Actions
- [ ] Send ReCAPTCHA bypass request to tech team
- [ ] Create automation accounts for all environments (10 total)
- [ ] Get Pre-Prod environment URL

## Test Count Summary
| Category | Tests |
|----------|-------|
| API Smoke | 16 |
| Login UI | 10 |
| **Total** | **26** |

## Commands Reference
- Run API tests: `pytest tests/api/smoke/ -v`
- Run Login tests: `pytest tests/ui/login/ -v`
- Run all tests: `pytest tests/ -v`
# TODO - Next Session

## Before Continuing Development

### 1. Project Cleanup & Refactor
- [ ] Fix SSL verification issue (make configurable in base_api_client.py)
- [ ] Run full test suite and verify all 26 core tests pass
- [ ] Check for any remaining scaffolding files that should be removed
- [ ] Review all files in tests/ folder for consistency

### 2. Documentation Updates
- [ ] Update IMPLEMENTATION_ROADMAP.md with current status
- [ ] Update SELENIUM_TO_PLAYWRIGHT_MIGRATION.md with actual structure
- [ ] Verify no hardcoded credentials in any files
- [ ] Update SESSION_SUMMARY with final status

### 3. Verify Current State
- [ ] 16 API smoke tests passing
- [ ] 10 Login UI tests passing
- [ ] All tests run against QA environment by default

## Ready to Continue
- [ ] Start Views module migration (27 Selenium tests)
- [ ] Create ViewsPage Page Object Model
- [ ] Migrate Views tests incrementally

## Pending External Actions
- [ ] Send ReCAPTCHA bypass request to tech team
- [ ] Create automation accounts for all environments (10 total)
- [ ] Get Pre-Prod environment URL

## Test Count Summary
| Category | Tests |
|----------|-------|
| API Smoke | 16 |
| Login UI | 10 |
| **Total** | **26** |

## Commands Reference
- Run API tests: pytest tests/api/smoke/ -v
- Run Login tests: pytest tests/ui/login/ -v
- Run all tests: pytest tests/ -v (See <attachments> above for file contents. You may not need to search or read the file again.)
