"""
QA-API-ADM-USR-01 - Admin -> Users API smoke
Spec: qa/Automation_QA.xlsx › Test Mapping › row "QA-API-ADM-USR-01"
Section: I. API
Owner: JV
Deployment: After FT

Catalog rows (see docs/API_ENDPOINTS.md):
- GET /REST/site/user/{email}
- GET /REST/central/user/enterprise/{enterpriseId}
- GET /REST/central/user/enterprise/{enterpriseId}/profile/{profileId}
"""
import pytest


@pytest.mark.api
@pytest.mark.smoke
@pytest.mark.qa_doc("QA-API-ADM-USR-01")
def test_get_site_user_by_email(user_api, login_data):
    """GET /REST/site/user/{email} returns the user's site assignments."""
    email = login_data["username"]
    r = user_api.get(f"/REST/site/user/{email}")
    r.raise_for_status()
    body = r.json()
    assert body.get("code") in (200, 2000), f"Unexpected code: {body.get('code')}, body: {str(body)[:300]}"
    assert "result" in body, "Response missing 'result'"
    # Result is typically a list of sites; tolerate dict-of-sites variants too.
    result = body["result"]
    assert isinstance(result, (list, dict)), f"Unexpected result type: {type(result)}"


@pytest.mark.api
@pytest.mark.smoke
@pytest.mark.qa_doc("QA-API-ADM-USR-01")
def test_get_enterprise_users(user_api, test_enterprise_id):
    """GET /REST/central/user/enterprise/{enterpriseId} returns the user list."""
    r = user_api.get(f"/REST/central/user/enterprise/{test_enterprise_id}")
    r.raise_for_status()
    body = r.json()
    assert body.get("code") in (200, 2000), f"Unexpected code: {body.get('code')}"
    users = body.get("result", [])
    assert isinstance(users, list), f"Expected user list, got {type(users)}"
    if users:
        sample = users[0]
        # Spot-check fields commonly returned by this endpoint.
        for key in ("userId", "email"):
            assert key in sample or any(key.lower() in k.lower() for k in sample.keys()), (
                f"User missing expected field '{key}': keys={list(sample.keys())}"
            )


@pytest.mark.api
@pytest.mark.smoke
@pytest.mark.qa_doc("QA-API-ADM-USR-01")
def test_get_user_profile_by_id(user_api, test_enterprise_id):
    """GET /REST/central/user/enterprise/{enterpriseId}/profile/{profileId} returns profile detail.

    We discover a profileId from the roles list rather than hardcoding it,
    because profile IDs differ across environments.
    """
    roles_resp = user_api.get(f"/REST/central/role/{test_enterprise_id}")
    roles_resp.raise_for_status()
    roles = roles_resp.json().get("result", [])
    assert roles, "No roles returned for enterprise - can't test profile detail"
    profile_id = roles[0].get("profileId")
    assert profile_id, f"Role missing profileId: {roles[0]}"

    r = user_api.get(f"/REST/central/user/enterprise/{test_enterprise_id}/profile/{profile_id}")
    r.raise_for_status()
    body = r.json()
    assert body.get("code") in (200, 2000), f"Unexpected code: {body.get('code')}"
    assert "result" in body, "Response missing 'result'"
