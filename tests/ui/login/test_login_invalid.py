import pytest

from tests.shared.pages.login_page import LoginPage


@pytest.mark.ui
@pytest.mark.qatouch("RgGQLR")
def test_empty_fields(page, base_url, step_capture):
    step_capture.set_page(page)
    lp = LoginPage(page, base_url)

    step_capture.mark(1, "Navigate to the login page")
    lp.login("", "")

    step_capture.mark(2, "Submit login form with both fields empty")
    assert not lp.is_logged_in()
    assert ("login" in page.url.lower() or "auth" in page.url.lower() or lp.is_login_page())

    step_capture.mark(3, "Verify user remains on login page and is not authenticated")


@pytest.mark.ui
@pytest.mark.qatouch("wmjREm")
def test_empty_username(page, base_url, step_capture):
    step_capture.set_page(page)
    lp = LoginPage(page, base_url)

    step_capture.mark(1, "Navigate to the login page")
    lp.login("", "somepassword")

    step_capture.mark(2, "Submit login form with empty username and a password")
    assert not lp.is_logged_in()
    assert ("login" in page.url.lower() or "auth" in page.url.lower() or lp.is_login_page())

    step_capture.mark(3, "Verify user remains on login page and is not authenticated")


@pytest.mark.ui
@pytest.mark.qatouch("68leQP")
def test_empty_password(page, base_url, step_capture):
    step_capture.set_page(page)
    lp = LoginPage(page, base_url)

    step_capture.mark(1, "Navigate to the login page")
    lp.login("user@example.com", "")

    step_capture.mark(2, "Submit login form with a username and empty password")
    assert not lp.is_logged_in()
    assert ("login" in page.url.lower() or "auth" in page.url.lower() or lp.is_login_page())

    step_capture.mark(3, "Verify user remains on login page and is not authenticated")


@pytest.mark.ui
@pytest.mark.qatouch("gQxma3")
def test_wrong_credentials(page, base_url, step_capture):
    step_capture.set_page(page)
    lp = LoginPage(page, base_url)

    step_capture.mark(1, "Navigate to the login page")
    lp.login("invalid@example.com", "wrongpass")

    step_capture.mark(2, "Submit login form with incorrect email and password")
    # Key assertion: user should not be logged in. Accept either an error
    # message, reCAPTCHA prompt, or remaining on the login page as valid failure.
    assert not lp.is_logged_in()
    assert (lp.get_error_message() or "login" in page.url.lower() or "auth" in page.url.lower() or lp.is_login_page())

    step_capture.mark(3, "Verify login fails with error message or user stays on login page")


@pytest.mark.ui
@pytest.mark.qatouch("41VM9q")
def test_invalid_email_format(page, base_url, step_capture):
    step_capture.set_page(page)
    lp = LoginPage(page, base_url)

    step_capture.mark(1, "Navigate to the login page")
    lp.login("not-an-email", "password123")

    step_capture.mark(2, "Submit login form with malformed email format")
    assert not lp.is_logged_in()
    # Expect to still be on login page / validation shown
    assert ("login" in page.url.lower() or "auth" in page.url.lower() or lp.is_login_page())

    step_capture.mark(3, "Verify user remains on login page and validation rejects the input")
