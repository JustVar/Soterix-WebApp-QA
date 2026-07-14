"""
QA-API-ADM-RUL-01 - Admin -> Rules API smoke
Spec: qa/Automation_QA.xlsx › Test Mapping › row "QA-API-ADM-RUL-01"
Section: I. API
Owner: JV
Deployment: After FT

Read-only smoke for rule search and the supporting metadata endpoints. Rule
CRUD is intentionally out of scope here - those require throwaway test data
and live in Tier 3 of the smoke-test plan (see docs/API_ENDPOINTS.md).

Catalog rows:
- POST /REST/rule/enterprise/{enterpriseId}/search
- GET  /REST/analyticschedule/{enterpriseId}/type/{type}
- GET  /REST/webhook/{enterpriseId}
- GET  /REST/site/analytics/enterprise/{enterpriseId}/licensed
"""
import pytest


@pytest.mark.api
@pytest.mark.smoke
@pytest.mark.qa_doc("QA-API-ADM-RUL-01")
def test_rule_search(user_api, test_enterprise_id):
    """POST /REST/rule/enterprise/{enterpriseId}/search returns the rule list.

    Empty-body POST mirrors what the SPA sends on initial tab load. If the
    endpoint later requires filter params, this test will surface that via
    a 4xx response.
    """
    r = user_api.post(f"/REST/rule/enterprise/{test_enterprise_id}/search", json={})
    r.raise_for_status()
    body = r.json()
    assert body.get("code") in (200, 2000), f"Unexpected code: {body.get('code')}, body: {str(body)[:300]}"
    assert "result" in body, "Response missing 'result'"
    rules = body["result"]
    assert isinstance(rules, (list, dict)), f"Unexpected result type: {type(rules)}"


@pytest.mark.api
@pytest.mark.smoke
@pytest.mark.qa_doc("QA-API-ADM-RUL-01")
def test_get_analytic_schedule(user_api, test_enterprise_id):
    """GET /REST/analyticschedule/{enterpriseId}/type/{type} returns schedule metadata.

    Type=1 is the default observed in capture. Other types may exist; we only
    smoke the default here.
    """
    r = user_api.get(f"/REST/analyticschedule/{test_enterprise_id}/type/1")
    r.raise_for_status()
    body = r.json()
    assert body.get("code") in (200, 2000), f"Unexpected code: {body.get('code')}"


@pytest.mark.api
@pytest.mark.smoke
@pytest.mark.qa_doc("QA-API-ADM-RUL-01")
def test_get_webhooks_for_enterprise(user_api, test_enterprise_id):
    """GET /REST/webhook/{enterpriseId} returns the enterprise's webhook config list."""
    r = user_api.get(f"/REST/webhook/{test_enterprise_id}")
    r.raise_for_status()
    body = r.json()
    assert body.get("code") in (200, 2000), f"Unexpected code: {body.get('code')}"
    # Empty list is a valid response if no webhooks are configured.
    assert "result" in body, "Response missing 'result'"


@pytest.mark.api
@pytest.mark.smoke
@pytest.mark.qa_doc("QA-API-ADM-RUL-01")
def test_get_licensed_analytics(user_api, test_enterprise_id):
    """GET /REST/site/analytics/enterprise/{enterpriseId}/licensed returns the licensed analytic types."""
    r = user_api.get(f"/REST/site/analytics/enterprise/{test_enterprise_id}/licensed")
    r.raise_for_status()
    body = r.json()
    assert body.get("code") in (200, 2000), f"Unexpected code: {body.get('code')}"
    assert "result" in body, "Response missing 'result'"
