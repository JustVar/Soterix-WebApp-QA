import pytest

from tests.shared.pages.login_page import LoginPage


@pytest.mark.ui
def test_valid_credentials(page, base_url, login_data):
    lp = LoginPage(page, base_url)
    lp.login(login_data['username'], login_data['password'])
    # allow app to navigate
    assert lp.is_logged_in(), "Expected to be logged in with valid credentials"


@pytest.mark.ui
def test_logout(authenticated_page, base_url):
    page = authenticated_page
    lp = LoginPage(page, base_url)
    # Ensure we're logged in (authenticated_page should provide an authenticated context)
    assert lp.is_logged_in(), "Precondition: authenticated_page must be logged in"
    # Click profile menu (top right avatar)
    try:
        profile_btn = page.locator('.MuiAvatar-root').first
        profile_btn.click()
        page.wait_for_timeout(1000)  # Wait for menu to open

        # Click Sign out
        if page.locator('text=Sign out').count():
            page.locator('text=Sign out').first.click()
        else:
            # fallback selector
            page.locator('p:has-text("Sign out")').first.click()
        page.wait_for_timeout(3000)  # Wait for logout redirect
    except Exception:
        pass

    # verify we returned to login page
    assert ('/auth/login' in page.url) or (page.locator('input[name="email"]').count()), "Expected to be back on login page after logout"
