# tests/test_dashboard.py

import pytest

@pytest.mark.smoke
def test_dashboard_landing(login):
    """
    Test to ensure user lands on dashboard after login.
    """
    page = login
    assert "/dashboard" in page.url
    assert page.locator("h1").first.inner_text().lower() in ["dashboard", "welcome"]
