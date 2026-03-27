import pytest

from tests.shared.pages.login_page import LoginPage


@pytest.mark.ui
@pytest.mark.qatouch("RgGBDz")
def test_valid_credentials(page, base_url, login_data, step_capture):
    step_capture.set_page(page)
    lp = LoginPage(page, base_url)

    step_capture.mark(1, "Navigate to the login page")
    lp.login(login_data['username'], login_data['password'])
    # allow app to navigate

    step_capture.mark(2, "Submit valid credentials and verify login succeeds")
    assert lp.is_logged_in(), "Expected to be logged in with valid credentials"


@pytest.mark.ui
@pytest.mark.logout
@pytest.mark.qatouch("bj04pP")
def test_logout(authenticated_page, base_url, step_capture):
    """Basic logout smoke test. See test_logout.py for comprehensive coverage."""
    step_capture.set_page(authenticated_page)
    page = authenticated_page
    lp = LoginPage(page, base_url)

    step_capture.mark(1, "Verify user is logged in")
    assert lp.is_logged_in(), "Precondition: authenticated_page must be logged in"

    lp.logout()

    step_capture.mark(2, "Log out and verify redirect to login page")
    assert lp.is_login_page(), "Expected to be back on login page after logout"
