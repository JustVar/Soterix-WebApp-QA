# Maintenance Reminders

## OAuth Secret Expiration ⚠️
- **Current Secret Expires:** July 22, 2026
- **Set Calendar Reminder:** July 8, 2026 (2 weeks before)
- **Action Required:** Generate new client secret

### How to Renew Secret:
1. Go to **Microsoft Entra ID Admin Portal** (NOT Azure Portal)
   - URL: https://entra.microsoft.com
2. Navigate to: Identity -> Applications -> App registrations
3. Find: "QA Test Automation"
4. Go to: Certificates & secrets -> Client secrets
5. Click "New client secret"
   - Description: "QA Automation Secret - Generated [date]"
   - Expires: 6 months (or 12 months if available)
6. Copy the secret VALUE (not the ID)
7. Update `.env` file:
   - AZURE_CLIENT_SECRET=[new_secret_value]
   - AZURE_SECRET_EXPIRES=[new_expiration_date]
8. Test email functionality:
   - Run: `python tools/test_oauth_email.py`
   - Verify test email arrives
9. Commit updated `.env.template` if expiration date changed (don't commit actual secret!)

**Important:** The old secret will stop working after expiration. Update BEFORE it expires to avoid email failures.

---

### Slack Alerts
- Slack webhook configured via `SLACK_WEBHOOK_URL` in `.env`
- Alert channel: `SLACK_ALERT_CHANNEL` (example: `#qa-automation`)
- Use `python tools/check_oauth_expiration.py --slack` to send Slack alerts when expiration < 30 days

## Monthly Maintenance Tasks

### Review Flaky Tests
- **File:** `flaky_tests.json`
- **Action:** Review tests with >30% failure rate
- **Decision:** Fix test or mark as known flaky

### QA Touch Cleanup
- Archive test runs older than 3 months
- Remove obsolete test cases
- Update test case automation status

### Test Coverage Review
- Check coverage by module (aim for 80% smoke coverage)
- Identify untested features from recent releases
- Add missing test cases

---

## Quarterly Maintenance Tasks

### API Schema Updates
- **Action:** Re-download OpenAPI specs
- **Command:** `python tools/download_openapi_spec.py`
- **Check:** Compare endpoint counts, identify new APIs
- **Update:** Add tests for new endpoints

### Credential Rotation
- Update QA test user passwords if rotated
- Update role-based test accounts (Super Admin, Admin, Supervisor, Operator)
- Update `.env` with new passwords
- Verify all tests still pass

### JIRA NexaiQ-Core Custom Field Review
- **Action:** Check if NexaiQ-Core (NC) project custom fields changed
- **Command:** `python tools/test_jira_connection.py`
- **Update:** `smart_jira_bug_creator.py` if field IDs changed

### Dependency Updates
- `requirements.txt` pins exact versions (since 08/2026). To upgrade: check
  `pip list --outdated`, raise the pin, `pip install -r requirements.txt`,
  run a suite, then commit the new pin.
- Update Playwright browsers after a playwright upgrade:
  `playwright install chrome`
- Watch: pytest-playwright 0.8.0 declares support through Python 3.13 only
  and we run 3.14. No failures seen so far. Re-check the pytest-playwright
  changelog for a 3.14 release on each quarterly pass.

---

## Annual Maintenance Tasks

### Framework Review
- Review test execution speed (target: <5 min for smoke suite)
- Identify slow tests and optimize
- Review and update documentation
- Team training on new features

### Security Audit
- Rotate all API keys and tokens
- Review `.gitignore` - ensure no secrets committed
- Update OAuth app permissions if needed
- Review who has access to credentials

---

## Contact Information

**For OAuth/Entra ID Issues:**
- Contact: IT Support
- Portal: https://entra.microsoft.com
- App Name: QA Test Automation
- App ID: ***REMOVED***

**For JIRA NexaiQ-Core Issues:**
- Project: NexaiQ-Core (key: NC)
- Admin: [Project Admin Name]
- URL: https://soterixsystems.atlassian.net

**For QA Touch Issues:**
- URL: https://soterixsystems.qatouch.com
- Project: Soterix AI VSAAS
- API Key Location: Settings -> API

---

## Emergency Procedures

### If OAuth Email Stops Working:
1. Check secret expiration date in `.env`
2. Test authentication: `python tools/test_oauth_email.py`
3. If expired, generate new secret immediately
4. If other error, check Entra ID app status

### If API Tests Start Failing:
1. Check if APIs are down: manually test in browser
2. Verify authentication token is valid
3. Check if API schemas changed: re-download OpenAPI spec
4. Review `flaky_tests.json` for patterns

### If Jira Integration Breaks:
1. Test connection: `python tools/test_jira_connection.py`
2. Verify API token still valid
3. Check if project permissions changed
4. Verify custom field IDs unchanged

---
# Maintenance Reminders

## Azure OAuth Secret Expiration
- **Expires:** July 22, 2026
- **Action Required:** Generate new secret 2 weeks before expiration
- **Where:** Azure Portal -> App Registrations -> QA Test Automation -> Certificates & secrets
- **Update:** AZURE_CLIENT_SECRET in .env

### Automated Expiration Monitoring
- Check runs automatically: `python tools/check_oauth_expiration.py`
- Add to daily test script to alert early
- Will fail CI/CD builds when < 7 days remain

## Monthly Tasks
- Review `flaky_tests.json` for consistently flaky tests
- Archive old test runs in QA Touch
- Update test coverage metrics

## Quarterly Tasks
- Review and update API schemas from OpenAPI spec
- Update role-based test credentials if passwords rotated
- Review Jira custom field mappings
