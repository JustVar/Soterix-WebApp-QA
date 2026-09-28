# Credentials Setup Guide

This guide explains how to set up your credentials for running automated tests across different environments.

---

## Overview

The test automation framework supports multiple environments:

| Environment | URL | Write Access | Delete Access |
|-------------|-----|--------------|---------------|
| QA | qa.example.invalid | ✅ Yes | ✅ Yes |
| Staging | staging.example.invalid | ✅ Yes | ❌ No |
| Production | app.example.invalid | ❌ No | ❌ No |

Each environment can have multiple "boxes" (regional deployments) with different user accounts.

---

## Step 1: Get Your Credentials

### For US Team Members
1. Your credentials are stored in **1Password** under the "QA Automation" vault
2. Contact your team lead if you don't have access

### For India Team Members
1. Request credentials from the US team lead
2. Credentials will be shared via secure channel (encrypted email or Teams DM)
3. Store them securely - do not share or commit to Git

---

## Step 2: Create Your .env File

1. Navigate to the project root folder:
```powershell
    cd C:\Users\YourName\QA-Automation\Soterix-WebApp-QA
```

2. Copy the template file:
```powershell
    copy .env.template .env
```

3. Open `.env` in a text editor (VS Code, Notepad++, etc.)

4. Fill in your credentials for each environment you need access to

---

## Step 3: Add Your Credentials

### Current .env Variables
```bash
# QA Environment
QA_INDIA_USER=your_email@soterixsystems.com   # india box account
QA_INDIA_PASSWORD=your_password_here

# Staging Environment
STAGE_USER=your_email@soterixsystems.com
STAGE_PASSWORD=your_password_here

# Production Environment (read-only access)
HARDWARE_LAB_PASSWORD=your_password_here   # shared QA production box
```

### Adding a New Team Member

If you need to add your own account, follow these steps:

**Step 1:** Edit the environment config file (e.g., `config/env/qa.py`)

Add a new entry in the `boxes` section:
```python
"boxes": {
     "us": {
          # ... existing US config ...
     },
     "india": {
          # ... existing India config ...
     },
     "qa_engineer_a": {  # ADD THIS NEW ENTRY
          "user_key": "QA_ENGINEER_A",
          "email": "person@example.com",
          "password_env": "QA_ENGINEER_A_PASSWORD",
          "default_site_id": None,  # Auto-discovered - leave as None
     },
},
```

**Step 2:** Add to your `.env` file:
```bash
QA_ENGINEER_A_PASSWORD=your_actual_password_here
```

**Step 3:** Also update `.env.template` so others know the variable exists:
```bash
QA_ENGINEER_A_PASSWORD=your_password_here
```

---

## Step 4: Verify Your Setup

1. Open PowerShell and navigate to the project:
```powershell
    cd C:\Users\YourName\QA-Automation\Soterix-WebApp-QA
```

2. Activate the virtual environment:
```powershell
    venv\Scripts\Activate.ps1
```

3. Test your credentials are loaded:
```powershell
    python -c "from config.base_config import get_credentials; print(get_credentials())"
```

    You should see output like:
{'email': 'your_email@soterixsystems.com', 'password': 'your_password', 'site_id': None}

4. Run a quick test to verify everything works:
```powershell
    # moved: run from the Soterix-API-QA repo -> pytest tests/smoke/test_user_apis.py::test_auto_discover_site_and_enterprise -v -s
```

    Expected output:
[SITE DISCOVERY] Found 1 site(s) for user your_email@soterixsystems.com
- Driver Site (Site ID: 110, Enterprise ID: 132)
PASSED

---

## How Site and Enterprise IDs Work

### In this repo (UI tests)

UI tests do not need a Site ID. The browser session sees whatever sites the
account has access to. `get_credentials()` returns `site_id` from the box
config when one is set, and `None` otherwise.

### Auto-Discovery (API repo)

The login-time site discovery (`/REST/site/user/{your-email}`) lives in the
Soterix-API-QA repo with the API clients. See that repo's
`Soterix-API-QA/docs/API_SURFACES.md`.

### Manual Override (Optional)

If you need to test a specific site (not your default), you can set it in the config:
```python
"boxes": {
     "us": {
          "user_key": "QA_LAB",
          "email": "your_email@soterixsystems.com",
          "password_env": "QA_LAB_PASSWORD",
          "default_site_id": 110,  # Optional: override auto-discovery
     },
}
```

### The Relationship
User Login
↓
Auto-discover sites -> Site ID (e.g., 110)
↓
Site contains -> Enterprise ID (e.g., 132)
↓
Enterprise ID used for -> Roles, Permissions, User Management APIs

---

## Running Tests in Different Environments

### QA Environment (Default)
```powershell
pytest -m sanity -v
```

### QA Environment - Different Box
```powershell
$env:BOX="india"; pytest -m sanity -v
```

### Staging Environment
```powershell
$env:ENV="staging"; pytest -m sanity -v
```

### Production Environment (Read-Only Tests)
```powershell
$env:ENV="prod"; pytest -m sanity -v
```

### Reset to Default
```powershell
$env:ENV="qa"; $env:BOX="us"
```

---

## Environment Variables Reference

| Variable | Default | Description |
|----------|---------|-------------|
| `ENV` | qa | Environment to use (qa, staging, stage, prod) |
| `BOX` | us | Box/region to use (us, india) |

### Password Variables by Environment

| Variable | Environment | Account |
|----------|-------------|---------|
| `QA_INDIA_USER` / `QA_INDIA_PASSWORD` | QA | your own account (india box) |
| `QA_US_USER` / `QA_US_PASSWORD` | QA | your own account (us box) |
| `STAGE_USER` / `STAGE_PASSWORD` | Staging | your own account |
| `HARDWARE_LAB_PASSWORD` | Production | hardware-lab@soterixsystems.com (shared) |

---

## SSL Verification

Nothing in this repo reads an SSL variable. The browser manages its own
certificate trust, and the QA server presents a valid certificate as of
2026-08-07 (checked with `curl -I https://qa.example.invalid`, which
verifies by default).

The `SSL_VERIFY` override belonged to the Python API clients and moved with
them to the Soterix-API-QA repo. If a page ever shows a certificate warning,
report it: that is an environment problem, not something to configure around
here.


## User Roles

The system has these roles (in order of access level):

| Role | Profile ID | Description |
|------|------------|-------------|
| Enterprise Super Admin | 102 | Master admin, can create other admins |
| Admin | 103 | Full admin rights (same as ESA for testing) |
| Supervisor | 104 | Limited admin capabilities |
| Operator | 105 | Basic user access |

**For testing:** Enterprise Super Admin and Admin are treated the same - both have full admin rights.

---

## Security Best Practices

### DO:
- ✅ Keep `.env` file local only (it's in `.gitignore`)
- ✅ Use unique passwords for each environment
- ✅ Store credentials in 1Password (US team) or securely (India team)
- ✅ Rotate passwords periodically
- ✅ Report any credential compromise immediately

### DON'T:
- ❌ Never commit `.env` to Git
- ❌ Never share passwords in Slack/email unencrypted
- ❌ Never use production credentials for write/delete tests
- ❌ Never hardcode passwords in test files

---

## Troubleshooting

### "Invalid username and/or password" Error

1. Verify your `.env` file has the correct password
2. Check that the password variable name matches the config
3. Try logging in manually via browser to confirm credentials work

### "No password found" or Empty Password

1. Make sure `.env` file exists in project root
2. Check for typos in variable names
3. Ensure no extra spaces around the `=` sign
4. Restart your terminal after editing `.env`

### Tests Running Against Wrong Environment

1. Check your environment variables:
```powershell
    echo $env:ENV
    echo $env:BOX
```
2. Reset to default:
```powershell
    $env:ENV="qa"; $env:BOX="us"
```

### "No sites found for user" Error

1. Verify the account has Site access in the web UI
2. Contact admin to grant site permissions
3. Check you're using the correct environment

### ReCAPTCHA Failures

The framework retries ReCAPTCHA up to 3 times. If it still fails:
1. Check your network connection
2. Try running the test again
3. For CI/CD, consider using cached auth tokens

---

## Getting Help

- Check 1Password for shared account credentials.
- **India Team:** Contact your US team lead for credential assistance
- **Technical Issues:** Create a Jira ticket or ask in #qa-automation Slack channel
