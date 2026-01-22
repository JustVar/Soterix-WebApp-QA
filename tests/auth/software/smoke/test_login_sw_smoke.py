import os
import pytest
from tests.shared.pages.login_page import LoginPage

# Force QA environment for pilot tests (ReCAPTCHA disabled in QA)
os.environ.setdefault("ENV", "qa")


def test_login_sw_smoke(page, base_url, tenant_login):
    """Smoke: verify valid login redirects to expected landing."""
    app_type = os.environ.get("APP_TYPE", "customer")

    login_page = LoginPage(page)
    login_page.goto(base_url, app_type=app_type).login(tenant_login["username"], tenant_login["password"])

    # Wait for expected landing (some environments redirect to root '/').
    expected = base_url.rstrip("/") + tenant_login.get("expected_landing", "/dashboard")
    try:
        page.wait_for_url(expected, timeout=15000)
        assert expected in page.url
    except Exception:
        # Fallback: wait for a known post-login UI element instead of exact URL
        # (sidebar / cameras list present in QA after successful login)
        page.wait_for_selector("nav.camerasList, div.sidebarWrapper, main.page_main__GlU4n", timeout=15000)
        assert page.url.startswith(base_url)
