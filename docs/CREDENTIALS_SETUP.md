# Test Credential Setup

## Quick Start

1. Copy `.env.template` to `.env`a
2. Set your credentials in `.env`:

   QA_USER=your_email@soterixsystems.com
   QA_PASSWORD=your_password

3. (Optional) Use team accounts for CI or shared runs.

4. Verify your setup by running a quick session test:

```powershell
Set-Location 'C:\Users\<you>\QA-Automation\playwright-soterix-qa'
$env:ENV='qa'
python -m pytest tests/api/smoke/test_user_apis.py::test_get_user_session -v -s --tb=short
```

---

## How Site and Enterprise IDs Work

### Auto-Discovery (Recommended)

The framework **automatically discovers** your Site ID and Enterprise ID after login:

1. You login with your email/password
2. Framework calls `/REST/site/user/{your-email}`
3. Returns all sites you have access to
4. Uses the first site as default

**You don't need to configure Site IDs manually!**

Example auto-discovery output:

[SITE DISCOVERY] Found 1 site(s) for user qa@soterixsystems.com

Driver Site (Site ID: 110, Enterprise ID: 132)


### Manual Override (Optional)

If you need to test a specific site (not your default), you can set it in the config:

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
    cd C:\Users\YourName\QA-Automation\playwright-soterix-qa
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
QA_LAB_PASSWORD=your_password_here      # For qa@soterixsystems.com (US box)
JUSTIN_PASSWORD=your_password_here       # For justin.varughese@ (India box)

# Staging Environment
JUSTIN_STAGE_PASSWORD=your_password_here

# Production Environment (read-only access)
JUSTIN_PROD_PASSWORD=your_password_here
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
    cd C:\Users\YourName\QA-Automation\playwright-soterix-qa
```

2. Activate the virtual environment:
```powershell
    .venv\Scripts\Activate.ps1
```

3. Test your credentials are loaded:
```powershell
    python -c "from config.base_config import get_credentials; print(get_credentials())"
```

    You should see output like:
{'email': 'qa@soterixsystems.com', 'password': 'your_password', 'site_id': None}

4. Run a quick test to verify everything works:
```powershell
    pytest tests/api/smoke/test_user_apis.py::test_auto_discover_site_and_enterprise -v -s
```

    Expected output:
[SITE DISCOVERY] Found 1 site(s) for user qa@soterixsystems.com
- Driver Site (Site ID: 110, Enterprise ID: 132)
PASSED

---

## How Site and Enterprise IDs Work

### Auto-Discovery (Recommended)

The framework **automatically discovers** your Site ID and Enterprise ID after login:

1. You login with your email/password
2. Framework calls `/REST/site/user/{your-email}`
3. Returns all sites you have access to
4. Uses the first site as default

**You don't need to configure Site IDs manually!**

Example auto-discovery output:
[SITE DISCOVERY] Found 1 site(s) for user qa@soterixsystems.com

Driver Site (Site ID: 110, Enterprise ID: 132)


### Manual Override (Optional)

If you need to test a specific site (not your default), you can set it in the config:
```python
"boxes": {
     "us": {
          "user_key": "QA_LAB",
          "email": "qa@soterixsystems.com",
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
pytest tests/api/smoke/ -v
```

### QA Environment - Different Box
```powershell
$env:BOX="india"; pytest tests/api/smoke/ -v
```

### Staging Environment
```powershell
$env:ENV="staging"; pytest tests/api/smoke/ -v
```

### Production Environment (Read-Only Tests)
```powershell
$env:ENV="prod"; pytest tests/api/smoke/ -v
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
| `QA_LAB_PASSWORD` | QA | qa@soterixsystems.com |
| `JUSTIN_PASSWORD` | QA | justin.varughese@ (India box) |
| `JUSTIN_STAGE_PASSWORD` | Staging | justin.varughese@ |
| `JUSTIN_PROD_PASSWORD` | Production | justin.varughese@ |

---

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

- **US Team:** Contact Justin Varughese or check 1Password
- **India Team:** Contact your US team lead for credential assistance
- **Technical Issues:** Create a Jira ticket or ask in #qa-automation Slack channel
