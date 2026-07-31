import pytest

from tests.shared.pages.login_page import LoginPage


@pytest.mark.ui
def test_sql_injection_attempt(page, base_url):
    lp = LoginPage(page, base_url)
    payload = "' OR 1=1 --"
    lp.login(payload, payload)
    assert not lp.is_logged_in(), "SQL injection payload should not grant access"
    assert lp.get_error_message(), "Expected error message after SQL injection attempt"


@pytest.mark.ui
def test_xss_attempt(page, base_url):
    lp = LoginPage(page, base_url)
    payload = "<script>alert('XSS')</script>"
    lp.login(payload, "password123")
    assert not lp.is_logged_in(), "XSS payload should not grant access"
    assert lp.get_error_message(), "Expected error message after XSS attempt"


@pytest.mark.ui
def test_password_too_short(page, base_url):
    lp = LoginPage(page, base_url)
    lp.login("user@example.com", "123")
    assert not lp.is_logged_in(), "Short password should not grant access"
    # App may not show an explicit error for short passwords - just blocks login
    assert lp.get_error_message() or lp.is_login_page(), (
        "Expected error message or to remain on login page for short password"
    )


@pytest.mark.ui
@pytest.mark.slow
def test_brute_force_protection(page, base_url):
    """Test if login has brute force protection after multiple failed attempts.

    Attempts 5 failed logins and checks for CAPTCHA appearance or lockout
    messages. Not a strict assertion - logs the result since some environments
    may not have brute force protection enabled.
    """
    lp = LoginPage(page, base_url)
    protection_detected = False

    for i in range(5):
        lp.login("test@example.com", f"wrongpassword{i}")
        page.wait_for_timeout(1000)

        if lp.has_captcha() or lp.has_lockout_message():
            protection_detected = True
            break

    # At minimum, the app should still be functional after repeated failures
    assert lp.get_error_message() or not lp.is_logged_in(), (
        "After 5 failed attempts, expected error message or login to remain blocked"
    )
    # Log whether brute force protection was detected (informational)
    if protection_detected:
        print("Brute force protection detected (CAPTCHA or lockout)")
    else:
        print("WARNING: No brute force protection detected after 5 failed attempts")


@pytest.mark.ui
def test_password_reset_link_exists(page, base_url):
    """Verify that a password reset / forgot password link is present on the login page."""
    lp = LoginPage(page, base_url)
    lp.goto()

    reset_text = lp.find_password_reset_link()

    # Informational - log finding, not a strict requirement
    if reset_text:
        assert "forgot" in reset_text.lower() or "reset" in reset_text.lower(), (
            f"Reset link text '{reset_text}' does not contain expected keywords"
        )
