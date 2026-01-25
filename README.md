# Playwright Soterix QA

This repository contains the Playwright automation test suite (Python + pytest) for Soterix VSAAS. It is structured for multi-environment testing and includes Page Objects, fixtures, and pilot smoke tests.

## Quick Setup

Prerequisites
- Python 3.11+ installed
- Node.js (for Playwright browsers installer) - recommended LTS
- Git

Create & activate venv (Windows PowerShell):

```powershell
python -m venv venv
venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -r requirements.txt
python -m playwright install chromium
```

## Configure environments

We support `qa`, `stage`, `prod` and partner `APP_TYPE=partner` variants. By default pilot tests target `qa` (ReCAPTCHA disabled).

Copy template to `.env.qa.local` and fill secrets:

```powershell
copy .env.qa.template .env.qa.local
# edit .env.qa.local and populate AUTO_USER/AUTO_PASSWORD
```

Key env vars
- `ENV` - `qa|stage|prod`
- `APP_TYPE` - `customer|partner`
- `TENANT` - optional tenant name
- `AUTO_USER` / `AUTO_PASSWORD` - automation credentials
- `EXPECTED_LANDING` - optional post-login path (default `/dashboard`)

## Run tests (examples)

Run a single login smoke test (headed):

```powershell
# set environment and credentials via your local env or .env file
$env:ENV='qa'
$env:AUTO_USER='your_username_here'
$env:AUTO_PASSWORD='your_password_here'  # or load from .env
python -m pytest tests/auth/software/smoke/test_login_sw_smoke.py -v -s --headed
```

Run API or UI tests:

```powershell
# API smoke tests
pytest tests/api/smoke/ -v

# UI login tests
pytest tests/ui/login/ -v

# All tests
pytest tests/ -v
```

CI notes
- Ensure `python -m playwright install chromium` runs in CI.
- Use CI secrets for `AUTO_USER` and `AUTO_PASSWORD`.

## Current test structure

- `tests/api/smoke/` - API smoke tests (16 tests)
- `tests/ui/login/` - Login UI tests (10 tests)
- `tests/shared/pages/` - Page Object Models
- `tests/shared/api_clients/` - API client helpers
- `tests/shared/helpers/` - Utility helpers

## ReCAPTCHA handling

- Production/stage include Google reCAPTCHA that can block automated UI login. For reliable automation prefer QA with a test key or use API-token login in CI.
- The project contains a best-effort reCAPTCHA checkbox click in `tests/shared/pages/login_page.py` and debug helpers that capture screenshots and page HTML.

## Next steps

1. Implement `ViewsPage` and `tests/views/...` smoke test.
2. Add API token login fixture to bypass UI reCAPTCHA in CI.
3. Add CI artifact capture on test failures (screenshots + HTML) in `conftest.py`.

For more details see `IMPLEMENTATION_ROADMAP.md` and `ANALYSIS_SCREENSHOTS.md`.

