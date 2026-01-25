**Overview**
- Why migrate: Move from Selenium to Playwright for faster, more reliable, and easier-to-maintain UI tests.

# Selenium to Playwright Migration

## Current Status

**Migration Progress: 12% complete (26 of ~212 tests)**

| Metric | Value |
|--------|-------|
| Playwright Tests Passing | 26 |
| API Smoke Tests | 16 |
| Login UI Tests | 10 |
| Selenium Tests to Migrate | ~202 remaining |

## File Structure

### Legacy Selenium (Reference Only)
legacy-selenium-tests/test_vsaas_web/
├── test_vsaas_soterix.py (7,569 lines - main test file)
├── test_login_validator.py (487 lines)
├── test_login_webclient.py (585 lines)
└── conftest.py

### New Playwright Structure
tests/
├── api/
│   └── smoke/
│       ├── test_user_apis.py (5 tests)
│       ├── test_platform_apis.py (5 tests)
│       ├── test_camera_apis.py
│       ├── test_dashboard_apis.py
│       └── test_search_api.py
├── ui/
│   └── login/
│       ├── test_login_valid.py (2 tests)
│       ├── test_login_invalid.py (5 tests)
│       ├── test_login_security.py (3 tests)
│       └── README.md
└── shared/
├── pages/
│   └── login_page.py
├── api_clients/
│   ├── base_api_client.py
│   ├── auth_helper.py
│   └── site_discovery.py
└── helpers/
└── role_helper.py

## Migration Status by Module

| Module | Selenium Tests | Playwright Tests | Status |
|--------|---------------|------------------|--------|
| Login | 14 | 10 | ✅ DONE |
| API Tests | N/A | 16 | ✅ DONE (new) |
| Views - Thumbnail | 27 | 0 | 🔄 NEXT |
| Views - Full Screen | 13 | 0 | PENDING |
| Events | 26 | 0 | PENDING |
| Search | 24 | 0 | PENDING |
| Media | 30 | 0 | PENDING |
| Insights | 26 | 0 | PENDING |
| Maps | 4 | 0 | PENDING |
| Admin Rules | 14 | 0 | PENDING |
| Admin Sites | 12 | 0 | PENDING |
| Admin Users | 9 | 0 | PENDING |
| Chats | 12 | 0 | PENDING |
| Notifications | 3 | 0 | PENDING |
| LPR | 0 | 0 | NOT STARTED |
| Admin - Other | 0 | 0 | NOT STARTED |
| **TOTAL** | **212** | **26** | **12%** |

## What's Been Migrated

### Login Module (COMPLETE)
- Login Page Object Model with ReCAPTCHA handling
- 10 login UI tests:
  - test_valid_credentials - Login with valid credentials
  - test_logout - Logout via profile menu
  - test_empty_fields - Validation for empty form
  - test_empty_username - Validation for missing email
  - test_empty_password - Validation for missing password
  - test_wrong_credentials - Invalid credentials handling
  - test_invalid_email_format - Email format validation
  - test_sql_injection_attempt - SQL injection protection
  - test_xss_attempt - XSS protection
  - test_password_too_short - Password length validation

### API Tests (NEW - Not in Selenium)
- 16 API smoke tests covering top platform APIs:
  - User Session API
  - User Roles API
  - Site Status API
  - Camera Tree API
  - Camera Snap API
  - Widgets API
  - Search API
  - Site/Enterprise auto-discovery

## Key Improvements Over Selenium

| Feature | Selenium | Playwright |
|---------|----------|------------|
| Auto-wait | Manual WebDriverWait | Built-in auto-wait |
| Selectors | XPath heavy, brittle IDs | Stable name/data-testid |
| ReCAPTCHA | Ad-hoc workarounds | Retry logic with verification |
| Session reuse | Browser profile | Cookie + localStorage injection |
| Test speed | ~5-10 min | ~3-5 min |
| Debugging | Screenshots only | Traces, videos, screenshots |

## Syntax Quick Reference

| Selenium | Playwright |
|----------|------------|
| `driver.get(url)` | `page.goto(url)` |
| `driver.find_element(By.CSS, sel)` | `page.locator(sel)` |
| `element.click()` | `locator.click()` |
| `element.send_keys(text)` | `locator.fill(text)` |
| `WebDriverWait(...).until(...)` | `page.wait_for_selector(...)` |
| `driver.execute_script(js)` | `page.evaluate(js)` |

## How to Run Tests
```powershell
# Activate virtual environment
.\venv\Scripts\Activate.ps1

# Run all tests
pytest tests/ -v

# Run API tests only
pytest tests/api/smoke/ -v

# Run Login UI tests only
pytest tests/ui/login/ -v

# Run with visible browser
pytest tests/ui/login/ -v --headed
```

## How to Contribute to Migration

1. Pick a module from the "PENDING" list
2. Read the Selenium tests in `legacy-selenium-tests/`
3. Create Page Object Model in `tests/shared/pages/`
4. Create test file in appropriate `tests/ui/` subfolder
5. Run and validate tests
6. Update this migration status table
7. Commit and push

## Next Steps

1. Fix SSL verification issue in base_api_client.py
2. Migrate Views module (27 tests)
3. Migrate Events module (26 tests)
4. Request ReCAPTCHA bypass for automation accounts (See <attachments> above for file contents. You may not need to search or read the file again.)
