# Login Test Module

## Overview
This directory contains Playwright-based UI tests for the application's login flows. The tests were migrated from legacy Selenium coverage to Playwright Page Object Model (POM) located at `tests/shared/pages/login_page.py`.

The module covers:
- Valid login and logout
- Invalid input validation (empty fields, wrong credentials)
- Security-focused edge cases (SQL injection, XSS, short password)
- ReCAPTCHA best-effort handling and session caching for faster test setup

## Test list (10 tests)
1. `test_valid_credentials` - Verify successful login with known-good credentials and landing on the dashboard.
2. `test_logout` - Verify user can logout via profile menu (avatar) and returns to the login page.
3. `test_empty_fields` - Submit with both email and password empty; expect validation or remain on login page.
4. `test_empty_username` - Submit with missing username; expect validation or remain on login page.
5. `test_empty_password` - Submit with missing password; expect validation or remain on login page.
6. `test_wrong_credentials` - Attempt login with invalid credentials; expect error and no login.
7. `test_invalid_email_format` - Provide malformed email; expect client-side validation and no login.
8. `test_sql_injection` - Input SQL-like payloads into fields to ensure the app doesn't authenticate or crash.
9. `test_xss_input` - Input script-like payloads and verify no persistent execution and no login.
10. `test_short_password` - Attempt login with an overly short password to validate server/client-side enforcement.

> Note: test names and exact placement are in the files in this directory. The above list reflects coverage provided by the Playwright suite.

## How to run
From the repository root:

```bash
# Run full login suite
pytest tests/ui/login/ -v -s

# Run a single test
pytest tests/ui/login/test_login_valid.py::test_logout -v -s
```

Ensure environment variables are set (see `.env.template`):
- `BOX` and its `QA_<BOX>_USER` / `QA_<BOX>_PASSWORD` pair (the legacy `QA_USER` / `QA_PASSWORD` when `BOX` is unset)
- `BASE_URL` - base URL for the environment (defaults to QA site)

## Migration notes (Selenium -> Playwright)
Files migrated from legacy Selenium implementation:
- Legacy references: `legacy/test_vsaas_web/test_login_validator.py` and other legacy files in `tests/legacy/`.

Key migration changes:
- Replaced Selenium WebDriver interactions with Playwright POM (`tests/shared/pages/login_page.py`).
- Selectors normalized to stable attributes (`name`, `data-testid`, `aria-label`) with fallback CSS/XPath.
- ReCAPTCHA: Playwright implements a best-effort checkbox click and waits for the client-side `g-recaptcha-response` to be populated. This is not a solver - tests may still hit reCAPTCHA in some environments.
- Session caching: A capture script stores `JSESSIONID` cookie and `localStorage` in `.session_cache` to allow `authenticated_page` fixture to inject session state and avoid UI login in subsequent tests.

## Key differences from Selenium implementation
- Playwright auto-waits for elements and network idle where applicable, reducing explicit sleep usage.
- POM centralizes robust selector fallbacks and button-detection heuristics.
- ReCAPTCHA handling is best-effort; Selenium had ad-hoc workarounds previously.
- Session state restoration uses Playwright `context.add_cookies` and `localStorage` injection rather than browser profile reuse.

## Known limitations
- ReCAPTCHA cannot be reliably solved by automation; the `_handle_recaptcha` method attempts to click the checkbox but may fail in some environments (stage/prod). Prefer running tests in QA where ReCAPTCHA behavior is test-friendly.
- Session caching currently writes `.session_cache` with cookie metadata and localStorage; running tests in parallel (`pytest-xdist`) can cause race conditions - consider converting to per-worker cache files.
- Some UI selector differences across environments may still require minor selector tweaks.

## Contact
If you need assistance adapting tests for a different environment (stage/prod) or improving caching for parallel runs, open an issue or request a follow-up change.
