import re

import pytest
from playwright.sync_api import expect

from tests.shared.pages.login_page import LoginPage

LOGIN_URL_RE = re.compile(r"/auth/login")


@pytest.mark.ui
@pytest.mark.smoke
def test_valid_credentials(page, base_url, login_data):
    """Valid credentials log the user in."""
    lp = LoginPage(page, base_url)
    lp.login(login_data['username'], login_data['password'])
    # allow app to navigate
    assert lp.is_logged_in(), "Expected to be logged in with valid credentials"
    # the login changed the address: the browser left the login page
    expect(page).not_to_have_url(LOGIN_URL_RE)


@pytest.mark.ui
@pytest.mark.logout
def test_logout(authenticated_page, base_url):
    """Basic logout smoke test. See test_logout.py for comprehensive coverage."""
    page = authenticated_page
    lp = LoginPage(page, base_url)
    assert lp.is_logged_in(), "Precondition: authenticated_page must be logged in"

    lp.logout()
    assert lp.is_login_page(), "Expected to be back on login page after logout"
    # the logout changed the address: the browser is on the login page again
    expect(page).to_have_url(LOGIN_URL_RE)
