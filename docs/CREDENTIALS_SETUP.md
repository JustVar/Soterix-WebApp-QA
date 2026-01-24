# Test Credential Setup

## Quick Start

1. Copy `.env.template` to `.env`
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

## Option B: Adding a New User Account

When adding a new user account configuration in `config/environments.yaml` or in a `boxes` mapping, you no longer need to set `default_site_id`. The framework will discover the user's sites at login and choose the first accessible site as the default.

If you want to target a different site than the discovered default, set `default_site_id` explicitly as shown in the Manual Override section above.

---

## Notes and Troubleshooting

- If your account sees no sites, the tests will skip with a helpful message. Verify the account has Site access in the UI or contact the admin.
- For Stage/Prod environments, reCAPTCHA may block automated UI logins - prefer API login + token cache for CI.
- Never commit `.env` to source control.
