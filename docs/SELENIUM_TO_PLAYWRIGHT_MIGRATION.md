**Overview**
- Why migrate: Move from Selenium to Playwright for faster, more reliable, and easier-to-maintain UI tests.

**Benefits of Playwright**
- Faster execution and parallelism
- Auto-waiting for elements and network events
- Better debugging tools (trace, videos, inspections)
- Modern, consistent API across browsers

**Migration approach**
- Migrate module-by-module (feature area or folder)
- Keep legacy tests in `legacy-selenium-tests/` for reference
- Implement Playwright equivalents under `tests/ui_playwright/` or existing `tests/pages` structure
- Run both suites in CI during migration

**File structure comparison**
- Old Selenium:
  - `legacy-selenium-tests/test_vsaas_web/`
    - `test_vsaas_soterix.py` (large, many tests)
    - `test_login_webclient.py`
    - `test_login_validator.py`
    - `conftest.py`

- New Playwright (recommended):
  - `tests/ui_playwright/`
    - `tests/` (smaller, focused test files)
    - `pages/` (page objects)
    - `fixtures/` (Playwright fixtures, auth helpers)
    - `conftest.py` (pytest + Playwright integration)

**How to read migration status**
- Use a simple checklist in the repo (e.g., `docs/migration.md` or this file)
- Status keys:
  - DONE: Fully migrated and validated
  - IN-PROGRESS: Partially migrated or flaky
  - PENDING: Not started
- Example table (update as you migrate):
  - Login tests: DONE
  - Dashboard tests: IN-PROGRESS
  - Camera tests: PENDING

**Syntax comparison (Selenium -> Playwright)**
- Selenium: `driver.get(url)` -> Playwright: `page.goto(url)`
- Selenium: `driver.find_element(By.CSS_SELECTOR, selector)` -> Playwright: `page.locator(selector)`
- Selenium: `elem.click()` -> Playwright: `page.click(selector)` or `locator.click()`
- Selenium: `elem.send_keys(text)` -> Playwright: `page.fill(selector, text)`
- Selenium: `WebDriverWait(driver, 10).until(...)` -> Playwright: built-in auto-wait; explicit `page.wait_for_selector(selector)`
- Selenium: `driver.execute_script(js)` -> Playwright: `page.evaluate(js)`

**How to run Playwright tests**
- Run a single test:
```powershell
pytest tests/ui_playwright/tests/test_login.py::test_login -v -s
```
- Run all Playwright UI tests:
```powershell
pytest tests/ui_playwright/ -v -k "not legacy"
```
- Run with Playwright trace and video enabled (use pytest-playwright fixture options)

**How to contribute**
- Pick a small module (login, dashboard, search)
- Create a Playwright page object in `tests/ui_playwright/pages/`
- Write one test that uses the page object and Playwright fixtures
- Run locally and validate; open a PR against `main` with description of migrated tests
- Update migration status table in this file

---
Notes:
- Keep legacy tests unchanged for reference. Migrate tests incrementally and validate behavior against the app.
