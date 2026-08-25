"""Logout tests - session termination, redirect, and re-authentication."""
import pytest
from playwright.sync_api import expect

from tests.shared.pages.login_page import LoginPage


@pytest.mark.ui
@pytest.mark.logout
def test_profile_menu_opens(authenticated_page, base_url):
    """Verify the profile avatar menu opens and contains menu items."""
    page = authenticated_page
    lp = LoginPage(page, base_url)

    lp.open_profile_menu()
    assert lp.is_profile_menu_open(), "Profile menu should be visible after clicking avatar"


@pytest.mark.ui
@pytest.mark.logout
def test_profile_menu_contains_sign_out(authenticated_page, base_url):
    """Verify the profile menu contains a 'Sign out' option."""
    page = authenticated_page
    lp = LoginPage(page, base_url)

    lp.open_profile_menu()
    # Directly check that "Sign out" text is visible in the opened menu
    sign_out = page.locator('text=Sign out')
    assert sign_out.is_visible(), "Expected 'Sign out' option in profile menu"


@pytest.mark.ui
@pytest.mark.logout
def test_logout_redirects_to_login(authenticated_page, base_url):
    """Verify logout redirects to the login page."""
    page = authenticated_page
    lp = LoginPage(page, base_url)
    assert lp.is_logged_in(), "Precondition: must be logged in"

    lp.logout()
    assert lp.is_login_page(), "Should be on login page after logout"
    assert "/auth/login" in page.url, f"URL should contain /auth/login, got: {page.url}"


@pytest.mark.ui
@pytest.mark.logout
def test_login_form_visible_after_logout(authenticated_page, base_url):
    """Verify the login form is fully visible and functional after logout."""
    page = authenticated_page
    lp = LoginPage(page, base_url)

    lp.logout()

    email_field = page.locator('input[name="email"]')
    password_field = page.locator('input[name="password"]')
    submit_btn = page.locator('button[type="submit"]')

    # Three independent checks on one screen: soft, so a missing
    # field reports with the others instead of hiding them
    expect.soft(email_field).to_be_visible()
    expect.soft(password_field).to_be_visible()
    expect.soft(submit_btn).to_be_visible()


@pytest.mark.ui
@pytest.mark.logout
def test_cannot_access_app_after_logout(authenticated_page, base_url):
    """Verify navigating to the app after logout redirects to login.

    The SPA's root URL checks auth state and redirects unauthenticated
    users to /auth/login. Direct deep-links like /dashboard may not
    redirect (SPA serves index.html for all routes), so we test the
    root URL which reliably enforces the auth guard.
    """
    page = authenticated_page
    lp = LoginPage(page, base_url)

    lp.logout()

    # Navigate to root URL - the SPA auth guard should redirect to login
    page.goto(base_url)
    try:
        page.wait_for_url('**/auth/login**', timeout=15000)
    except Exception:
        # the URL wait missed; give the redirect one more beat and
        # let the assert below decide
        page.wait_for_timeout(5000)

    assert lp.is_login_page() or "/auth/login" in page.url, \
        f"Should be redirected to login after logout, got: {page.url}"


@pytest.mark.ui
@pytest.mark.logout
def test_back_button_after_logout(authenticated_page, base_url):
    """Verify browser back button after logout doesn't bypass authentication."""
    page = authenticated_page
    lp = LoginPage(page, base_url)

    lp.logout()
    assert lp.is_login_page(), "Precondition: must be on login page after logout"

    page.go_back()
    page.wait_for_load_state("domcontentloaded", timeout=15000)
    # the auth guard bounces back to login; a miss leaves the assert
    # below to decide
    try:
        page.wait_for_url('**/auth/login**', timeout=10000)
    # staying off the login URL is exactly what the assert reports
    except Exception:
        pass

    assert lp.is_login_page() or "/auth/login" in page.url, \
        "Browser back should not bypass authentication after logout"


@pytest.mark.ui
@pytest.mark.logout
def test_relogin_after_logout(authenticated_page, base_url, login_data):
    """Verify successful re-login after logging out."""
    page = authenticated_page
    lp = LoginPage(page, base_url)

    lp.logout()
    assert lp.is_login_page(), "Precondition: must be on login page after logout"

    lp.login(login_data['username'], login_data['password'])
    assert lp.is_logged_in(), "Should be logged in after re-login"


@pytest.mark.ui
@pytest.mark.logout
@pytest.mark.parametrize("path,page_name", [
    ("/search", "Search"),
    ("/events", "Events"),
    ("/insights", "Insights"),
])
def test_logout_from_different_pages(authenticated_page, base_url, path, page_name):
    """Verify logout works from various application pages.

    Steps:
    1. Open the Search page from its URL.
       Expected: The page renders with the profile avatar in the header.
    2. Click the avatar, then click Sign out.
       Expected: The login page opens.
    3. Repeat from the Events page and from the Insights page.
       Expected: The login page opens each time.
    """
    page = authenticated_page
    lp = LoginPage(page, base_url)

    page.goto(base_url + path, wait_until="domcontentloaded")
    # Wait for the SPA to fully render the page header with avatar
    try:
        page.locator('.MuiAvatar-root').first.wait_for(state="visible", timeout=20000)
    except Exception:
        # Some pages render the header after heavy content; one more
        # bounded beat before logout tries anyway
        page.wait_for_timeout(5000)

    lp.logout()
    assert lp.is_login_page(), f"Should be on login page after logout from {page_name}"
