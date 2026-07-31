"""
QA-API-USR-01 - User APIs smoke (session, roles, enterprise discovery)
Spec: qa/Automation_QA.xlsx › Test Mapping › row "QA-API-USR-01"
Section: I. API
Owner: JV
Deployment: After FT
"""
import pytest


@pytest.mark.api
@pytest.mark.smoke
def test_get_user_session(user_api):
    """GET current user session and validate response shape."""
    s = user_api.get_user_session()
    assert user_api.validate_session_response(s), "Session response did not validate"


@pytest.mark.api
@pytest.mark.smoke
def test_get_user_roles(user_api):
    """GET user roles and assert returned shape is list or dict."""
    roles = user_api.get_user_roles()
    print(f"Roles response -> {roles}")
    assert isinstance(roles, (list, dict)), f"Unexpected roles type: {type(roles)}"


@pytest.mark.api
@pytest.mark.smoke
def test_get_enterprise_id_dynamic(test_enterprise_id, test_site_id):
    """Test that enterpriseId is dynamically fetched from site status."""
    print(f"Site ID: {test_site_id} -> Enterprise ID: {test_enterprise_id}")
    assert test_enterprise_id is not None
    assert isinstance(test_enterprise_id, int)
    assert test_enterprise_id > 0


@pytest.mark.api
@pytest.mark.smoke
def test_get_roles_by_enterprise(user_api, test_enterprise_id):
    """Test fetching roles for a dynamically discovered enterprise."""
    print(f"Testing roles for enterprise ID: {test_enterprise_id}")
    
    # Call the roles endpoint with dynamic enterprise ID
    url = f"/REST/central/role/{test_enterprise_id}"
    response = user_api.get(url)
    response.raise_for_status()
    
    data = response.json()
    print(f"Roles response: {data}")
    
    # Validate response structure
    assert data.get("code") == 200, f"Expected code 200, got {data.get('code')}"
    assert "result" in data, "Response missing 'result' field"
    
    roles = data.get("result", [])
    assert isinstance(roles, list), "Result should be a list of roles"
    assert len(roles) > 0, "Expected at least one role"
    
    # Validate each role has required fields
    for role in roles:
        assert "profileId" in role, f"Role missing profileId: {role}"
        assert "profileName" in role, f"Role missing profileName: {role}"
        assert "priority" in role, f"Role missing priority: {role}"
        print(f"  - {role['profileName']} (ID: {role['profileId']}, Priority: {role['priority']})")


@pytest.mark.api
@pytest.mark.smoke
def test_auto_discover_site_and_enterprise(discovered_site, discovered_site_id, discovered_enterprise_id):
    """Test that site and enterprise IDs are auto-discovered from user login."""
    print(f"Auto-discovered site: {discovered_site.get('name')}")
    print(f"  Site ID: {discovered_site_id}")
    print(f"  Enterprise ID: {discovered_enterprise_id}")
    print(f"  Address: {discovered_site.get('address', {}).get('city')}, {discovered_site.get('address', {}).get('state')}")
    
    assert discovered_site_id is not None, "Site ID should be auto-discovered"
    assert discovered_enterprise_id is not None, "Enterprise ID should be auto-discovered"
    assert isinstance(discovered_site_id, int), "Site ID should be an integer"
    assert isinstance(discovered_enterprise_id, int), "Enterprise ID should be an integer"

