# QA Touch Integration Guide

Goal: upload test results to QA Touch from CI and map automated tests to QA Touch cases.

Quick (manual) import
- Export JUnit XML locally:
  ```bash
  python -m pytest --junitxml=reports/junit-report.xml
  ```
- Use QA Touch UI import (if available) to upload the XML.

Automated (CI)
1. Configure QA Touch API credentials in CI secrets: `QA_TOUCH_API_KEY`, `QA_TOUCH_PROJECT_ID`, `QA_TOUCH_API_URL`.
2. In CI pipeline, after tests run and produce `reports/junit-report.xml`, run the upload script:

```bash
python tools/upload_to_qatouch.py --file=reports/junit-report.xml --project=$QA_TOUCH_PROJECT_ID --api_key=$QA_TOUCH_API_KEY --url=$QA_TOUCH_API_URL
```

Mapping strategy
- Add a table `qa_touch_map.csv` mapping `test_file::test_name` -> `qatouch_case_id`.
- The upload script should parse `junit-report.xml` and map each test result to the QA Touch case id.

Implementation tips
- Use Python `requests` to POST to QA Touch REST endpoints.
- Use a pytest marker like `@pytest.mark.qatouch(12345)` to embed QA Touch case ids.
- Store mapping in CSV until direct marker annotation is standardized.

Security
- Never store API keys in repo. Use CI secret storage and environment variables.

Next steps
- I can scaffold `tools/upload_to_qatouch.py` if you want an initial uploader script.
