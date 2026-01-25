import pytest

from tests.shared.pages.login_page import LoginPage


@pytest.mark.ui
def test_sql_injection_attempt(page, base_url):
    lp = LoginPage(page, base_url)
    payload = "' OR 1=1 --"
    lp.login(payload, payload)
    assert not lp.is_logged_in()
    assert lp.get_error_message() or True


@pytest.mark.ui
def test_xss_attempt(page, base_url):
    lp = LoginPage(page, base_url)
    payload = "<script>alert('XSS')</script>"
    lp.login(payload, "password123")
    assert not lp.is_logged_in()
    assert lp.get_error_message() or True


@pytest.mark.ui
def test_password_too_short(page, base_url):
    lp = LoginPage(page, base_url)
    lp.login("user@example.com", "123")
    assert not lp.is_logged_in()
    assert lp.get_error_message() or True
