# ReCAPTCHA Bypass Plan for Test Automation

## Executive Summary

Our QA automation framework needs to run unattended across multiple environments. Currently, ReCAPTCHA on Stage (and likely Production) requires manual intervention, which blocks overnight and CI/CD automation runs.

**Goal:** Enable fully automated test runs across all environments without manual CAPTCHA solving.

---

## Current Environment Status

| Environment | ReCAPTCHA Status | Automation Impact |
|-------------|------------------|-------------------|
| **QA** (vsaas-qa-env) | Disabled | ✅ Works perfectly |
| **Stage** (staging.soterixcloud) | Enabled | ⚠️ Requires manual CAPTCHA solve |
| **Pre-Prod** (TBD) | Not set up | 🔲 Need to configure |
| **Production** (user.soterixcloud) | Enabled | ⚠️ Requires manual CAPTCHA solve |

### Current Workaround (Stage & Production)

1. QA manually runs the login test
2. QA solves the ReCAPTCHA manually in the browser
3. Session is cached (using Playwright storage state)
4. Remaining automation suite runs using cached session

**Problem:** This approach:
- Cannot run overnight without human presence
- Cannot integrate with CI/CD pipelines
- Blocks any future scheduled/triggered test runs
- Session expires, requiring re-intervention
- Must be repeated for each environment (Stage AND Production)

---

## Proposed Solutions for Tech Team

### Option 1: Disable ReCAPTCHA on Non-Production Environments (Recommended)

**What:** Disable ReCAPTCHA entirely on Stage and Pre-Prod (matching QA setup)

**Pros:**
- Simplest implementation
- Zero maintenance
- Already proven on QA environment
- Standard practice for test environments

**Cons:**
- Requires environment configuration change

**Implementation:** Environment variable or config flag to disable ReCAPTCHA check

```
# Example config
RECAPTCHA_ENABLED=false  # Stage, Pre-Prod
RECAPTCHA_ENABLED=true   # Production only
```

---

### Option 2: Email Whitelist for Automation Accounts

**What:** Skip ReCAPTCHA check if login email matches a whitelist

**Pros:**
- Surgical approach - only automation accounts bypass
- Works on any environment including Production
- Audit trail shows automation vs human logins

**Cons:**
- Requires code change in login flow
- Need to maintain whitelist

**Implementation:**
```python
# Backend pseudocode
AUTOMATION_EMAILS = [
    "automation@soterixsystems.com",
    "automation-stage@soterixsystems.com",
    "automation-prod@soterixsystems.com"
]

def should_show_recaptcha(email):
    return email not in AUTOMATION_EMAILS
```

---

### Option 3: IP Address Whitelist

**What:** Skip ReCAPTCHA for requests from known automation server IPs

**Pros:**
- No account-specific changes needed
- Works for any user logging in from whitelisted IP

**Cons:**
- Need static IP for automation server
- Won't work from developer machines (good or bad?)
- Requires network configuration

**Implementation:** Firewall or application-level IP check before ReCAPTCHA

---

### Option 4: API-Based Authentication (Bypass UI Login)

**What:** Create an API endpoint for programmatic login without ReCAPTCHA

**Pros:**
- Cleaner separation of human vs automation flows
- Can add rate limiting, API keys for security
- Faster than UI login

**Cons:**
- Requires new API endpoint development
- Doesn't test the actual UI login flow

**Implementation:**
```
POST /api/v1/auth/automation-login
Headers: X-Automation-Key: <secret>
Body: { "email": "...", "password": "..." }
Response: { "token": "JSESSIONID..." }
```

---

### Option 5: Long-Lived API Tokens

**What:** Generate non-expiring or long-lived tokens for automation accounts

**Pros:**
- One-time setup
- No login needed at all
- Works even if login flow changes

**Cons:**
- Security risk if tokens are compromised
- Need token management/revocation capability
- Still requires periodic refresh (90 days, etc.)

---

## Recommended Approach

**For Stage and Pre-Prod:** Option 1 (Disable ReCAPTCHA)
- Matches QA environment behavior
- Zero ongoing maintenance
- Enables immediate overnight automation

**For Production:** Option 2 (Email Whitelist) OR Option 4 (API Login)
- Production should keep ReCAPTCHA for regular users
- Single read-only automation account whitelisted
- Limits blast radius if account is compromised

---

## Email Template for Tech Team

**Subject:** Request: Enable Unattended Automation Testing on Stage Environment

**To:** [Tech Team / Engineering]

---

Hi Team,

**TL;DR:** We need ReCAPTCHA bypassed on Stage (and future Pre-Prod) to enable overnight/CI automation runs.

### Current Situation

| Environment | ReCAPTCHA | Automation Status |
|-------------|-----------|-------------------|
| QA | Disabled | ✅ Fully automated |
| Stage | Enabled | ⚠️ Requires manual CAPTCHA |
| Production | Enabled | ⚠️ Requires manual CAPTCHA |

Currently on Stage and Production, we must:
1. Manually solve CAPTCHA before each test run
2. Cannot schedule overnight runs
3. Cannot integrate with CI/CD pipelines
4. Session expires, requiring repeated manual intervention

### Request

**Stage & Pre-Prod:** Please disable ReCAPTCHA (matching QA configuration)

This is standard practice for test environments and enables:
- Overnight regression runs
- CI/CD integration (run tests on every deploy)
- Faster feedback loops for development

**Production (Future):** When we're ready to test Production, we'd like to discuss:
- Email whitelist for a single read-only automation account, OR
- API-based authentication endpoint for automation

### Proposed Automation Accounts

| Environment | Account | Role |
|-------------|---------|------|
| Stage | automation-stage@soterixsystems.com | Admin |
| Pre-Prod | automation-preprod@soterixsystems.com | Admin |
| Production | automation-prod@soterixsystems.com | Operator (read-only) |

### Timeline

We'd like to enable overnight runs on Stage as soon as possible. Can we schedule a quick call to discuss implementation options?

Thanks,
[Your Name]
QA Automation Team

---

## Automation Account Requirements

### Stage Environment (Priority)
| Email | Role | Purpose |
|-------|------|---------|
| automation-stage@soterixsystems.com | Admin | Full regression testing |
| automation-stage-supervisor@soterixsystems.com | Supervisor | Permission boundary tests |
| automation-stage-operator@soterixsystems.com | Operator | Basic user flow tests |

### Pre-Prod Environment (When Available)
| Email | Role | Purpose |
|-------|------|---------|
| automation-preprod@soterixsystems.com | Admin | Pre-release validation |
| automation-preprod-supervisor@soterixsystems.com | Supervisor | Permission tests |
| automation-preprod-operator@soterixsystems.com | Operator | User flow tests |

### Production Environment (Future, Read-Only)
| Email | Role | Purpose |
|-------|------|---------|
| automation-prod@soterixsystems.com | Operator | Smoke tests only, NO write operations |

---

## Implementation Checklist

### Stage Environment
- [ ] Request ReCAPTCHA disable (or whitelist)
- [ ] Create automation-stage@soterixsystems.com (Admin)
- [ ] Create automation-stage-supervisor@soterixsystems.com (Supervisor)
- [ ] Create automation-stage-operator@soterixsystems.com (Operator)
- [ ] Update config/env/stage.py with credentials
- [ ] Verify unattended login works
- [ ] Schedule first overnight run

### Pre-Prod Environment
- [ ] Confirm Pre-Prod URL when available
- [ ] Request ReCAPTCHA disable (match Stage)
- [ ] Create automation accounts (3)
- [ ] Create config/env/preprod.py
- [ ] Verify login and run smoke tests

### Production Environment
- [ ] Discuss whitelist approach with tech team
- [ ] Create automation-prod@soterixsystems.com (Operator ONLY)
- [ ] Ensure account has NO write/delete permissions
- [ ] Update config/env/prod.py
- [ ] Verify with read-only smoke tests
- [ ] Add safety flags to prevent destructive tests

---

## Security Considerations

1. **Dedicated Accounts:** Automation accounts are separate from human users for audit trail
2. **Role Restrictions:** Production only gets Operator (read-only) role
3. **Password Management:** Credentials stored in .env file, never committed to Git
4. **Rotation Policy:** Passwords rotated quarterly
5. **IP Restrictions:** Consider limiting automation accounts to specific IPs if required
6. **Monitoring:** Alert if automation accounts used outside normal test windows

---

## Fallback Options (If Bypass Denied)

If the tech team cannot bypass ReCAPTCHA:

### Option A: Session Caching with Manual Bootstrap
- QA manually logs in once per day/week
- Session cached and reused until expiration
- Limitation: Cannot handle expired sessions overnight

### Option B: CAPTCHA Solving Service (Last Resort)
- Services like 2Captcha, Anti-Captcha
- Cost: ~$3 per 1000 CAPTCHAs
- Limitation: Adds latency, cost, external dependency

### Option C: API-Only Testing
- Skip UI login entirely
- Use API token if available
- Limitation: Doesn't test UI login flow

**Recommendation:** Push for Option 1 (disable on non-prod) - it's the cleanest solution.

---

## Next Steps

1. [ ] Send email to tech team (use template above)
2. [ ] Schedule follow-up call if needed
3. [ ] Get confirmation on approach
4. [ ] Receive/create automation accounts
5. [ ] Update framework configuration
6. [ ] Verify unattended runs work
7. [ ] Set up scheduled overnight runs

---

## Appendix: QA Environment Reference

QA environment has ReCAPTCHA disabled, and our automation works perfectly:

```python
# Current working setup (QA)
# config/env/qa.py
qa_config = {
    "base_url": "https://qa.example.invalid",
    # No CAPTCHA handling needed - disabled server-side
}
```

This is the model we want to replicate for Stage and Pre-Prod.
