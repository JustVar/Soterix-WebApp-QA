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
    assert isinstance(roles, (list, dict))
