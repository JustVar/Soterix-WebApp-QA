import pytest

from tests.shared.pages.login_page import LoginPage


@pytest.mark.ui
def test_empty_fields(page, base_url):
    """Submitting an empty username and password stays on the login page."""
    lp = LoginPage(page, base_url)
    lp.login("", "")
    assert not lp.is_logged_in()
    assert ("login" in page.url.lower() or "auth" in page.url.lower() or lp.is_login_page())


@pytest.mark.ui
def test_empty_username(page, base_url):
    """Submitting the login form with no email keeps the login page.

    Steps:
    1. Leave the email empty, type a password and click Login.
       Expected: The login page stays open and the app does not sign in.
    """
    lp = LoginPage(page, base_url)
    lp.login("", "somepassword")
    assert not lp.is_logged_in()
    assert ("login" in page.url.lower() or "auth" in page.url.lower() or lp.is_login_page())


@pytest.mark.ui
def test_empty_password(page, base_url):
    """Submitting a username with no password stays on the login page."""
    lp = LoginPage(page, base_url)
    lp.login("user@example.com", "")
    assert not lp.is_logged_in()
    assert ("login" in page.url.lower() or "auth" in page.url.lower() or lp.is_login_page())


@pytest.mark.ui
def test_wrong_credentials(page, base_url):
    """Wrong credentials do not sign in.

    Steps:
    1. Type an unknown email and a wrong password and click Login.
       Expected: The app does not sign in: an error shows or the login page stays open.
    """
    lp = LoginPage(page, base_url)
    lp.login("invalid@example.com", "wrongpass")
    # Key assertion: user should not be logged in. Accept either an error
    # message, reCAPTCHA prompt, or remaining on the login page as valid failure.
    assert not lp.is_logged_in()
    assert (lp.get_error_message() or "login" in page.url.lower() or "auth" in page.url.lower() or lp.is_login_page())


@pytest.mark.ui
def test_invalid_email_format(page, base_url):
    """A malformed email address does not sign in.

    Steps:
    1. Type not-an-email as the email with any password and click Login.
       Expected: The login page stays open and the app does not sign in.
    """
    lp = LoginPage(page, base_url)
    lp.login("not-an-email", "password123")
    assert not lp.is_logged_in()
    # Expect to still be on login page / validation shown
    assert ("login" in page.url.lower() or "auth" in page.url.lower() or lp.is_login_page())
