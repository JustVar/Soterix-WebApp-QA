# Test Credential Setup (Revised)

1. Copy `.env.template` to `.env`
2. Set your credentials in `.env`:

```
QA_USER=your_email@soterixsystems.com
QA_PASSWORD=your_password
```

3. Run tests (example):

```powershell
Set-Location 'C:\Users\<you>\QA-Automation\playwright-soterix-qa'
$env:ENV='qa'
python -m pytest tests/api/smoke/test_user_apis.py::test_get_user_session -v -s --tb=short
```

## Team Accounts
| Team Member | Location | Account |
|-------------|----------|---------|
| Jus | US | qa@soterixsystems.com |
| Nik | US | qa@soterixsystems.com |
| QA Engineer B | India | [his videonetics email] |
| QA Engineer A | India | [his videonetics email] |
| CI/CD (future) | Automated | qa-automation@soterixsystems.com |

## Important
- NEVER commit `.env` file
- Each person maintains their own `.env`
- Contact your team lead if you need credentials

## Site Access Note

- QA environment: Different accounts see different sites (separate edge boxes)
- `qa-lab` account: Sees "Driver Site" (US QA Lab edge box)
- Other accounts: May see India-based sites
- Stage/Prod: All accounts typically see the same sites
