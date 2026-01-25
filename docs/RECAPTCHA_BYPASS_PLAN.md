# ReCAPTCHA Bypass Plan for Test Automation

## Overview

Our test automation framework needs to authenticate against multiple environments. ReCAPTCHA blocks automated logins, which prevents our tests from running reliably.

This document contains:
1. Email templates to request ReCAPTCHA bypass from the tech team
2. Environment-by-environment plan
3. Automation account naming convention

---

## First Step: Find Out ReCAPTCHA Process

Before requesting accounts, ask your tech team:

> **"How is ReCAPTCHA bypass handled for test automation? Is there an existing whitelist we can add accounts to?"**

Their answer will determine:
- How much effort is needed per account
- Whether we need to minimize accounts or can have multiple
- Which bypass method to use in our requests

---

## Automation Account Naming Convention

We need **3 accounts per environment** to test different permission levels:

### QA Environment (qa.example.invalid)
| Email | Role | Purpose |
|-------|------|---------|
| automation@soterixsystems.com | Admin | Full access tests |
| automation-supervisor@soterixsystems.com | Supervisor | Limited admin tests |
| automation-operator@soterixsystems.com | Operator | Basic user permission tests |

### Staging Environment (staging.example.invalid)
| Email | Role | Purpose |
|-------|------|---------|
| automation-stage@soterixsystems.com | Admin | Full access tests |
| automation-stage-supervisor@soterixsystems.com | Supervisor | Limited admin tests |
| automation-stage-operator@soterixsystems.com | Operator | Basic user permission tests |

### Pre-Prod Environment (URL TBD)
| Email | Role | Purpose |
|-------|------|---------|
| automation-preprod@soterixsystems.com | Admin | Full access tests |
| automation-preprod-supervisor@soterixsystems.com | Supervisor | Limited admin tests |
| automation-preprod-operator@soterixsystems.com | Operator | Basic user permission tests |

### Production Environment (app.example.invalid)
| Email | Role | Purpose |
|-------|------|---------|
| automation-prod@soterixsystems.com | Operator | Read-only tests only |

**Note:** Production only needs one Operator account - no destructive testing allowed.

### Summary: 10 Total Accounts
- QA: 3 accounts
- Staging: 3 accounts
- Pre-Prod: 3 accounts
- Production: 1 account (read-only)

---

## Email Template 1: ReCAPTCHA Bypass Request

**Subject:** Request: ReCAPTCHA Bypass for Test Automation Accounts

**To:** [Tech Team / DevOps]

**Body:**

Hi Team,

We are setting up automated QA testing across our environments and need ReCAPTCHA bypassed for dedicated automation accounts.

**Request:**
Please whitelist the following email addresses to bypass ReCAPTCHA during login:

**QA Environment (qa.example.invalid)**
- automation@soterixsystems.com (Admin)
- automation-supervisor@soterixsystems.com (Supervisor)
- automation-operator@soterixsystems.com (Operator)

**Staging Environment (staging.example.invalid)**
- automation-stage@soterixsystems.com (Admin)
- automation-stage-supervisor@soterixsystems.com (Supervisor)
- automation-stage-operator@soterixsystems.com (Operator)

**Pre-Prod Environment ([pre-prod URL])**
- automation-preprod@soterixsystems.com (Admin)
- automation-preprod-supervisor@soterixsystems.com (Supervisor)
- automation-preprod-operator@soterixsystems.com (Operator)

**Production Environment (app.example.invalid)**
- automation-prod@soterixsystems.com (Operator - read-only)

**Why this is needed:**
- ReCAPTCHA is designed to block bots, which includes our test automation
- We currently use retry logic and delays, but this is unreliable and slow (adds 60-90 seconds per login)
- Whitelisting specific automation accounts is the industry-standard approach

**Suggested implementation options:**

1. **Email whitelist** (Preferred) - Skip ReCAPTCHA check if email matches automation account
2. **IP whitelist** - Skip ReCAPTCHA for requests from our office IP / test server IP
3. **Secret header** - Skip ReCAPTCHA if request includes a secret header (e.g., `X-Automation-Key: <secret>`)
4. **Test mode flag** - Environment variable to disable ReCAPTCHA entirely on non-prod environments

**Security considerations:**
- Automation accounts will have strong, rotated passwords
- Production account will be read-only (no write/delete permissions)
- We can restrict automation accounts to specific IP ranges if needed

Please let me know which approach works best for your infrastructure, and I can provide additional details.

Thanks,
[Your Name]
QA Team

---

## Email Template 2: Automation Account Creation Request

**Subject:** Request: Create Automation Test Accounts for QA Environments

**To:** [Admin / Account Management]

**Body:**

Hi,

We need dedicated automation accounts created for our test framework. These accounts will be used exclusively by automated tests, not human users.

**Accounts to create:**

**QA Environment (qa.example.invalid)**
| Email | Role |
|-------|------|
| automation@soterixsystems.com | Admin |
| automation-supervisor@soterixsystems.com | Supervisor |
| automation-operator@soterixsystems.com | Operator |

**Staging Environment (staging.example.invalid)**
| Email | Role |
|-------|------|
| automation-stage@soterixsystems.com | Admin |
| automation-stage-supervisor@soterixsystems.com | Supervisor |
| automation-stage-operator@soterixsystems.com | Operator |

**Pre-Prod Environment ([URL TBD])**
| Email | Role |
|-------|------|
| automation-preprod@soterixsystems.com | Admin |
| automation-preprod-supervisor@soterixsystems.com | Supervisor |
| automation-preprod-operator@soterixsystems.com | Operator |

**Production Environment (app.example.invalid)**
| Email | Role |
|-------|------|
| automation-prod@soterixsystems.com | Operator |

**Total: 10 accounts**

**For each account, please:**
1. Create the user with the specified email
2. Assign to the appropriate role
3. Grant access to all test sites (or specify which sites)
4. Send the temporary password to me securely (1Password, encrypted email, or Slack DM)

**Why dedicated accounts:**
- Audit trail shows "automation" vs human actions
- Can disable automation accounts without affecting human users
- Easier to manage permissions and access
- Industry best practice for test automation

Let me know if you need any additional information.

Thanks,
[Your Name]
QA Team

---

## Email Template 3: Combined Request (If Same Team Handles Both)

**Subject:** Request: Automation Test Accounts + ReCAPTCHA Bypass for QA Framework

**To:** [Tech Team]

**Body:**

Hi Team,

We're implementing automated testing across all environments and need two things:

### 1. Create Automation Accounts

**QA Environment** (qa.example.invalid)
- automation@soterixsystems.com (Admin)
- automation-supervisor@soterixsystems.com (Supervisor)
- automation-operator@soterixsystems.com (Operator)

**Staging Environment** (staging.example.invalid)
- automation-stage@soterixsystems.com (Admin)
- automation-stage-supervisor@soterixsystems.com (Supervisor)
- automation-stage-operator@soterixsystems.com (Operator)

**Pre-Prod Environment** ([URL TBD])
- automation-preprod@soterixsystems.com (Admin)
- automation-preprod-supervisor@soterixsystems.com (Supervisor)
- automation-preprod-operator@soterixsystems.com (Operator)

**Production Environment** (app.example.invalid)
- automation-prod@soterixsystems.com (Operator - read-only)

### 2. Bypass ReCAPTCHA for All 10 Accounts Above

Please whitelist the above emails to skip ReCAPTCHA during login. Options:
- Email-based whitelist (preferred)
- IP whitelist (provide our test server IP)
- Secret header bypass
- Disable ReCAPTCHA on non-prod environments

### Why This Matters

- Current approach: Retry ReCAPTCHA 3 times with delays -> 60-90 seconds per login, still flaky
- With bypass: Instant login -> faster, reliable tests
- Industry standard: Dedicated automation accounts with ReCAPTCHA bypass

Please let me know the best path forward and timeline.

Thanks,
[Your Name]
QA Team

---

## Environment-by-Environment Plan

### QA Environment (qa.example.invalid)
**Current State:** Working with ReCAPTCHA retry logic (slow but functional)
**Action Items:**
1. ☐ Create automation@soterixsystems.com (Admin)
2. ☐ Create automation-supervisor@soterixsystems.com (Supervisor)
3. ☐ Create automation-operator@soterixsystems.com (Operator)
4. ☐ Request ReCAPTCHA bypass for all 3 accounts
5. ☐ Update config/env/qa.py with new credentials
6. ☐ Replace current qa@soterixsystems.com in tests

### Staging Environment (staging.example.invalid)
**Current State:** Not tested yet, ReCAPTCHA will block automation
**Action Items:**
1. ☐ Create automation-stage@soterixsystems.com (Admin)
2. ☐ Create automation-stage-supervisor@soterixsystems.com (Supervisor)
3. ☐ Create automation-stage-operator@soterixsystems.com (Operator)
4. ☐ Request ReCAPTCHA bypass for all 3 accounts
5. ☐ Update config/env/stage.py with new credentials
6. ☐ Verify login and run smoke tests

### Pre-Prod Environment (URL TBD)
**Current State:** Environment details needed
**Action Items:**
1. ☐ Confirm Pre-Prod URL
2. ☐ Create automation-preprod@soterixsystems.com (Admin)
3. ☐ Create automation-preprod-supervisor@soterixsystems.com (Supervisor)
4. ☐ Create automation-preprod-operator@soterixsystems.com (Operator)
5. ☐ Request ReCAPTCHA bypass for all 3 accounts
6. ☐ Create config/env/preprod.py
7. ☐ Verify login and run smoke tests

### Production Environment (app.example.invalid)
**Current State:** Config exists, not tested
**Action Items:**
1. ☐ Create automation-prod@soterixsystems.com (Operator - READ-ONLY)
2. ☐ Request ReCAPTCHA bypass for this account
3. ☐ Update config/env/prod.py with new credentials
4. ☐ Verify login works (run read-only tests only)
5. ☐ Ensure safety flags prevent any write/delete operations

**Note:** Production only gets Operator role - no Admin/Supervisor testing in prod.

---

## Alternative: If ReCAPTCHA Bypass is Denied

If the tech team cannot bypass ReCAPTCHA, here are fallback options:

### Option A: API-Only Testing
- Skip UI login entirely
- Get JSESSIONID token via direct API call (if login API exists without ReCAPTCHA)
- Limitation: Can't test UI flows

### Option B: Pre-Generated Tokens
- Manually login once, save the JSESSIONID
- Use long-lived tokens if available
- Limitation: Tokens expire, need manual refresh

### Option C: Browser Profile with Saved Session
- Login manually once in a browser profile
- Playwright reuses that profile's cookies
- Limitation: Sessions expire, need periodic manual refresh

### Option D: Selenium Grid with Human Verification
- First login done manually or with CAPTCHA-solving service
- Token cached and reused
- Limitation: Cost, complexity

**Recommendation:** Push for Option 1 (email whitelist) - it's the cleanest solution and industry standard.

---

## Next Steps

1. [ ] Send Email Template 1 or 3 to tech team
2. [ ] Wait for ReCAPTCHA bypass confirmation
3. [ ] Send Email Template 2 for account creation (if not combined)
4. [ ] Receive credentials securely
5. [ ] Update .env and config files
6. [ ] Test each environment
7. [ ] Update CREDENTIALS_SETUP.md with new accounts

---

## Security Notes

- Store all passwords in .env file (never commit to Git)
- Use 1Password or similar for team credential sharing
- Rotate passwords quarterly
- Production account must be read-only
- Consider IP restrictions for automation accounts

---

**After you create the file:**

**Tell Tooling Code:**
```
git add docs/RECAPTCHA_BYPASS_PLAN.md
git commit -m "docs: Add ReCAPTCHA bypass plan with email templates"
git push
```
