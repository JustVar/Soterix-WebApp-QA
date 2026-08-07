# Email Test Reports

Send test run reports via email to team members using Microsoft Graph API.

## Setup

### Environment Variables

Add these to your `.env` file:

```env
# Microsoft Azure OAuth (for email sending)
AZURE_TENANT_ID=<your-tenant-id>
AZURE_CLIENT_ID=<your-client-id>
AZURE_CLIENT_SECRET=<your-client-secret>
EMAIL_FROM=<person@example.com>

# Email Report Settings (optional)
REPORT_RECIPIENT=person@example.com
SEND_TEST_REPORT=1  # Set to 1 to auto-send after tests
```

## Usage

### Option 1: Auto-Send After Test Run

Run tests with automatic report sending:

```bash
export SEND_TEST_REPORT=1
export REPORT_RECIPIENT=person@example.com
pytest tests/ui/events/test_events_filters.py
```

The report will be generated as `report.html` and automatically emailed to the recipient.

### Option 2: Manual Report Sending

Generate a report first, then send it:

```bash
# Run tests (generates reports/report.html)
pytest tests/ui/events/test_events_filters.py

# Send the report manually
python tools/send_test_report.py reports/report.html person@example.com
```

### Option 3: Send Custom Report

```bash
python tools/send_test_report.py reports/custom_report.html person@example.com
```

## Report Format

- **Location**: `reports/report.html`
- **Type**: HTML (self-contained, embeds all styles/images)
- **Includes**: Test results, pass/fail counts, execution time
- **Attachment**: HTML report file is also attached to email
- **Subject**: `Test Report - PASSED` or `Test Report - FAILED`

## Requirements

- `pytest-html` plugin (for HTML report generation)
- `msal` (Microsoft authentication library)
- `requests` (HTTP client)
- Azure OAuth credentials configured

## Troubleshooting

### "Missing Azure OAuth environment variables"

Make sure all required env vars are set in `.env`:
- `AZURE_TENANT_ID`
- `AZURE_CLIENT_ID`
- `AZURE_CLIENT_SECRET`
- `EMAIL_FROM`

### Report not sent after tests

Check that:
1. `SEND_TEST_REPORT=1` is set
2. `reports/report.html` was generated
3. Azure credentials are valid
4. Email address is correct

### "Report file not found"

Run tests first to generate the report:
```bash
pytest tests/ui/events/
# Report auto-generated to reports/report.html
```

## Example: Nightly Test Report

Run full test suite and email report:

```bash
#!/bin/bash
export SEND_TEST_REPORT=1
export REPORT_RECIPIENT=person@example.com

cd /path/to/Soterix-WebApp-QA
pytest tests/ui/ -m smoke
# Report automatically sent after tests complete
```

You can schedule this script with cron or a task scheduler.
