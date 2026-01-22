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
$env:ENV='qa'
$env:AUTO_USER='qa@soterixsystems.com'
$env:AUTO_PASSWORD='***REMOVED***'
python -m pytest tests/auth/software/smoke/test_login_sw_smoke.py -v -s --headed
```

Run all smoke tests (headless):

```powershell
$env:ENV='qa'
pytest tests/**/smoke -q
```

CI notes
- Ensure `python -m playwright install chromium` runs in CI.
- Use CI secrets for `AUTO_USER` and `AUTO_PASSWORD`.

## Current test structure

- `tests/auth/` - login/auth smoke and regression
- `tests/views/` - video-wall / camera playback tests (replaces CameraPage)
- `tests/events/` - events page tests
- `tests/media/` - media/clip tests
- `tests/shared/pages/` - Playwright Page Objects (LoginPage, EventsPage, ViewsPage, etc.)

## ReCAPTCHA handling

- Production/stage include Google reCAPTCHA that blocks automated UI login.
- For reliable automation use QA where reCAPTCHA is disabled, or ask devs to provide a test key or an auth API to bypass UI login.
- The project contains a best-effort reCAPTCHA checkbox click in `tests/shared/pages/login_page.py` and a debug helper `scripts/debug_login_playwright.py` that saves screenshots and page HTML.

## Next steps

1. Implement `ViewsPage` and `tests/views/...` smoke test.
2. Add API token login fixture to bypass UI reCAPTCHA in CI.
3. Add CI artifact capture on test failures (screenshots + HTML) in `conftest.py`.

---
For more details see `IMPLEMENTATION_ROADMAP.md` and `ANALYSIS_SCREENSHOTS.md`.
# README: Playwright Python Automation for Soterix Systems

This repository contains the Playwright automation test suite built using **Python 3.11** and **pytest**, structured to support multi-tenancy and environment-specific testing for the Soterix VSAAS Platform. The project is hosted under the GitHub organization `Soterix-Systems`, though it supports the QA goals of **Soterix Systems**.

---

## Folder Structure

```
playwright-soterix-qa/
├── config/
│   ├── base_config.py          # Dynamically loads the right environment config
│   └── env/
│       ├── qa.py               # QA environment base URL
│       ├── stage.py            # Stage / UAT environment
│       └── prod.py             # Prod / Demo / User environments
├── data/
│   └── tenant1_login_data.py   # Tenant1 tenant-specific credentials (baseline demo)
├── logs/
│   └── env_config.log          # Logs resolved config at runtime
├── pages/
│   └── login_page.py           # Page Object for login actions
├── tests/
│   ├── test_login.py           # Sample login test (tenant-agnostic for now)
│   └── test_dashboard.py       # Sample dashboard test (tenant-agnostic for now)
├── utils/
│   ├── send_mail.py            # Email report sender (SMTP)
│   ├── ssh_utility.py          # Remote SSH support
│   ├── zipfolder.py            # Folders zipped for reports
│   └── password.txt            # App password for email (excluded from Git)
├── .gitignore
├── conftest.py                 # Global fixtures, includes tenant loader
├── pytest.ini
├── requirements.txt
└── venv/                       # Virtual environment (excluded)
```

---

## Setup Instructions

### 1. Prerequisites

- Python 3.11 installed
- VS Code installed
- Git properly configured (repo cloned into local workspace)

### 2. Create and Activate Virtual Environment

```bash
python -m venv venv
source venv/Scripts/activate  # For Git Bash/WSL
```

### 3. Install Requirements

```bash
python -m pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
playwright install
```

### 4. Run Tests with Dynamic Config

```bash
# ENV options: qa, stage, prod, uat, demo, user
# TENANT is optional until tenants are added
export ENV=uat TENANT=tenant1
pytest tests/
```

---

## Staging (Primary) Setup

Use `stage` as the primary test environment locally and in CI. The repository default `ENV` has been changed to `stage` so running `pytest` without setting `ENV` will target staging.

Local example (Windows PowerShell):

```powershell
$env:ENV='stage'
$env:TENANT='tenant1'   # optional
pytest -q
```

CI snippet (install Chromium and run headless Chrome only):

```yaml
# Example CI steps (generic)
- name: Install Python deps
    run: python -m pip install -r requirements.txt

- name: Install Playwright Chromium
    run: playwright install chromium

- name: Run tests (Chrome headless)
    run: pytest -q
    env:
        ENV: stage
        TENANT: tenant1   # set as needed or use CI secrets for credentials
```

Notes:
- The `base_url` in the environment configs points to the site root (e.g., https://staging.example.invalid). Tests append paths such as `/auth/login`.
- `pytest.ini` now includes `--headless` so CI runs headless Chrome by default.

---

## How to Use .gitignore (Step-by-Step)

The `.gitignore` file tells Git which files and folders should NOT be tracked or uploaded to the remote repository. This is important for keeping sensitive data secure and the repo clean.

### When to Use It

- To exclude passwords or personal files (like `password.txt`)
- To avoid syncing virtual environments (like `venv/`)
- To prevent uploading temporary test reports or logs

### How to Edit the `.gitignore` File

1. Open **VS Code** and make sure your project folder is open.
2. In the left panel, click the `.gitignore` file. If it doesn't exist, create one:
   - Right-click on the project root > **New File** > name it `.gitignore`
3. Add the following lines:

```
# Ignore Python virtual environment
venv/

# Ignore environment logs
logs/

# Ignore email credentials (security)
utils/password.txt

# Ignore generated test reports
*.html
*.zip
```

4. Save the file (Ctrl + S)

### Apply the Changes to Git

After editing `.gitignore`, Git will not remove already-tracked files automatically. To clean up:

```bash
git rm --cached utils/password.txt
```

Then commit the change:

```bash
git add .gitignore
git commit -m "Updated .gitignore to exclude sensitive files"
git push origin main
```

If this is your first time editing `.gitignore`, this ensures sensitive files like passwords are excluded before they're ever uploaded.

---

## Dynamic Environment Loader

The `base_config.py` file:

- Reads the `ENV` variable.
- Maps aliases like `uat`, `demo`, `user`, etc. to real config files (`stage.py`, `prod.py`).
- Logs the resolved file to `logs/env_config.log`

Example log:

```
[ENV CONFIG] Resolved environment alias 'uat' -> loading config.env.stage
```

---

## Tenant Login Example (Python-based)

```python
# data/tenant1_login_data.py
login_data = {
    "username": "tenant1_admin@soterix.com",
    "password": "securepass",
    "expected_landing": "/dashboard"
}
```

---

## Tenant Loader in conftest.py

Even though tenants are not yet configured, the project is prepared for multi-tenant testing. The `conftest.py` includes logic that:

- Reads `TENANT` from environment variables
- Defaults to `tenant1` if none is provided
- Loads `data/<tenant>_login_data.py` dynamically

This allows seamless future support for:

```bash
TENANT=metropolis pytest tests/
```

Without modifying the core logic or fixtures.

---

## Why Multi-Tenancy Matters

This framework supports:

- Reuse of test logic across **multiple environments** (QA, Stage, Prod).
- Easy onboarding of **multiple tenants** via separate login data.
- The objective is to ensure that data from multiple tenants is securely isolated from one another.
- CI/CD integration using dynamic environment variables.

To add a new tenant:

1. Create a new file like `data/metropolis_login_data.py`
2. Run with `TENANT=metropolis ENV=prod pytest tests/`

---

## Logging Strategy

- Environment resolution events are logged to `logs/env_config.log`
- The structure is designed to be extended to capture debug/test logs in the future

---

## Goals Achieved

- 100% Python stack
- Clean repo synced with Git (.gitignore enforced)
- Cross-environment, multi-tenant support
- Aliased configs + logging
- Ready for QA Touch, Slack, Jira integration

