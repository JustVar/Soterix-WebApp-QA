"""
QA-API-ADM-STE-01 - Admin -> Sites API smoke
Spec: qa/Automation_QA.xlsx › Test Mapping › row "QA-API-ADM-STE-01"
Section: I. API
Owner: JV
Deployment: After FT

Catalog rows (see docs/API_ENDPOINTS.md):
- POST /REST/enterprise/sitedetails
- GET  /REST/site/{siteId}/getsitedetails
- GET  /REST/edge/version/latest
- GET  /REST/edge/version/site/{siteId}/current
- GET  /REST/edge/version/site/{siteId}/previous
"""
import pytest


@pytest.mark.api
@pytest.mark.smoke
@pytest.mark.qa_doc("QA-API-ADM-STE-01")
def test_get_site_details(user_api, test_site_id):
    """GET /REST/site/{siteId}/getsitedetails returns details for one site."""
    r = user_api.get(f"/REST/site/{test_site_id}/getsitedetails")
    r.raise_for_status()
    body = r.json()
    assert body.get("code") in (200, 2000), f"Unexpected code: {body.get('code')}"
    assert "result" in body, "Response missing 'result'"


@pytest.mark.api
@pytest.mark.smoke
@pytest.mark.qa_doc("QA-API-ADM-STE-01")
def test_enterprise_sitedetails(user_api, test_enterprise_id):
    """POST /REST/enterprise/sitedetails returns the enterprise's site roster.

    Payload shape was inferred from live capture; if the endpoint requires
    fields we haven't yet observed, this test will surface that quickly via
    a clear assertion failure.
    """
    r = user_api.post(
        "/REST/enterprise/sitedetails",
        json={"enterpriseId": test_enterprise_id},
    )
    r.raise_for_status()
    body = r.json()
    assert body.get("code") in (200, 2000), f"Unexpected code: {body.get('code')}, body: {str(body)[:300]}"
    assert "result" in body, "Response missing 'result'"
    assert isinstance(body["result"], (list, dict))


@pytest.mark.api
@pytest.mark.smoke
@pytest.mark.qa_doc("QA-API-ADM-STE-01")
def test_edge_version_latest(user_api):
    """GET /REST/edge/version/latest returns the latest published edge version."""
    r = user_api.get("/REST/edge/version/latest")
    r.raise_for_status()
    body = r.json()
    assert body.get("code") in (200, 2000), f"Unexpected code: {body.get('code')}"
    assert body.get("result") is not None, "Expected a non-null version result"


@pytest.mark.api
@pytest.mark.smoke
@pytest.mark.qa_doc("QA-API-ADM-STE-01")
def test_edge_version_site_current(user_api, test_site_id):
    """GET /REST/edge/version/site/{siteId}/current returns the site's running edge build."""
    r = user_api.get(f"/REST/edge/version/site/{test_site_id}/current")
    r.raise_for_status()
    body = r.json()
    assert body.get("code") in (200, 2000), f"Unexpected code: {body.get('code')}"


@pytest.mark.api
@pytest.mark.smoke
@pytest.mark.qa_doc("QA-API-ADM-STE-01")
def test_edge_version_site_previous(user_api, test_site_id):
    """GET /REST/edge/version/site/{siteId}/previous returns the site's previous edge build."""
    r = user_api.get(f"/REST/edge/version/site/{test_site_id}/previous")
    r.raise_for_status()
    body = r.json()
    assert body.get("code") in (200, 2000), f"Unexpected code: {body.get('code')}"
