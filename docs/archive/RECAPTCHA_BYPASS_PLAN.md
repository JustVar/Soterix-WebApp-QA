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
    "test-auto-stage@soterixsystems.com",
    "test-auto-prod@soterixsystems.com"
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

**Chosen approach (02/18/2026):** Option 2 - Email Whitelist for all environments.

**For Stage:** Whitelist `test-auto-stage@soterixsystems.com`
- Surgical bypass - only automation account skips CAPTCHA
- Maintains CAPTCHA for all human logins
- Enables immediate overnight automation

**For Production:** Whitelist `test-auto-prod@soterixsystems.com`
- Account will be restricted to Operator/read-only role
- Smoke tests only, no write/delete operations
- Limits blast radius if account is compromised

---

## Email Sent (02/18/2026)

**Subject:** Request: Whitelist Automation Accounts to Bypass ReCAPTCHA on Stage & Production

**To:** DevOps/Platform Engineering Team

**Status:** ✅ Sent 02/18/2026, awaiting response

**Approach requested:** Email whitelist - skip ReCAPTCHA for dedicated automation accounts only.

**Accounts to whitelist:**

| Environment | Account | Role |
|-------------|---------|------|
| Stage | test-auto-stage@soterixsystems.com | Admin |
| Production | test-auto-prod@soterixsystems.com | Admin (restrict to Operator/read-only) |

---

## Automation Account Requirements

### Existing Accounts (Created 02/05/2026)
| Email | Environment | Role | Purpose |
|-------|-------------|------|---------|
| test-auto-qa@soterixsystems.com | QA | Admin | Full regression testing (✅ working) |
| test-auto-stage@soterixsystems.com | Stage | Admin | Full regression testing (⏳ needs whitelist) |
| test-auto-prod@soterixsystems.com | Production | Admin* | Smoke tests only (⏳ needs whitelist) |

*Production account will be restricted to Operator/read-only role when bypass is enabled.

### Future Role-Based Accounts (Planned, not yet created)
| Email | Environment | Role | Purpose |
|-------|-------------|------|---------|
| TBD-supervisor@soterixsystems.com | Stage | Supervisor | Permission boundary tests |
| TBD-operator@soterixsystems.com | Stage | Operator | Basic user flow tests |

---

## Implementation Checklist

### Stage Environment
- [x] Create test-auto-stage@soterixsystems.com (Admin) - (02/05/2026)
- [x] Configure config/env/stage.py with credentials
- [x] Send email whitelist request to DevOps/Platform Engineering - (02/18/2026)
- [ ] Receive confirmation that whitelist is applied
- [ ] Verify unattended login works (no manual CAPTCHA solve)
- [ ] Schedule first overnight run

### Pre-Prod Environment
- [ ] Confirm Pre-Prod URL when available
- [ ] Request whitelist for Pre-Prod (match Stage)
- [ ] Create config/env/preprod.py
- [ ] Verify login and run smoke tests

### Production Environment
- [x] Create test-auto-prod@soterixsystems.com (Admin) - (02/05/2026)
- [x] Configure config/env/prod.py with credentials
- [x] Send email whitelist request to DevOps/Platform Engineering - (02/18/2026)
- [ ] Receive confirmation that whitelist is applied
- [ ] Restrict account to Operator/read-only role
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

1. [x] Send email whitelist request to DevOps/Platform Engineering (02/18/2026)
2. [ ] Wait for response (follow up after 3 business days if no reply)
3. [ ] Get confirmation that whitelist is applied
4. [ ] Verify unattended login on Stage (no manual CAPTCHA)
5. [ ] Verify unattended login on Production (no manual CAPTCHA)
6. [ ] Run first overnight regression on Stage
7. [ ] Set up scheduled nightly runs

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
