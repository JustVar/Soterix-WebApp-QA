import pytest


@pytest.mark.api
@pytest.mark.smoke
def test_get_user_session(user_api):
    s = user_api.get_user_session()
    assert user_api.validate_session_response(s)


@pytest.mark.api
@pytest.mark.smoke
def test_get_user_roles(user_api):
    roles = user_api.get_user_roles()
    print(f"Roles response -> {roles}")
    assert isinstance(roles, (list, dict))


@pytest.mark.api
@pytest.mark.smoke
def test_get_enterprise_id_dynamic(test_enterprise_id, test_site_id):
    """Test that enterpriseId is dynamically fetched from site status."""
    print(f"Site ID: {test_site_id} -> Enterprise ID: {test_enterprise_id}")
    assert test_enterprise_id is not None
    assert isinstance(test_enterprise_id, int)
    assert test_enterprise_id > 0
