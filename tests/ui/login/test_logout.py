"""Logout tests -- session termination, redirect, and re-authentication."""
import pytest
from playwright.sync_api import expect

from tests.shared.pages.login_page import LoginPage


@pytest.mark.ui
@pytest.mark.logout
@pytest.mark.qatouch("7ErGae")
def test_profile_menu_opens(authenticated_page, base_url, step_capture):
    """Verify the profile avatar menu opens and contains menu items."""
    step_capture.set_page(authenticated_page)
    page = authenticated_page
    lp = LoginPage(page, base_url)

    step_capture.mark(1, "Click the profile avatar to open the menu")
    lp.open_profile_menu()

    step_capture.mark(2, "Verify profile menu is visible with menu items")
    assert lp.is_profile_menu_open(), "Profile menu should be visible after clicking avatar"


@pytest.mark.ui
@pytest.mark.logout
@pytest.mark.qatouch("9e1NEZ")
def test_profile_menu_contains_sign_out(authenticated_page, base_url, step_capture):
    """Verify the profile menu contains a 'Sign out' option."""
    step_capture.set_page(authenticated_page)
    page = authenticated_page
    lp = LoginPage(page, base_url)

    step_capture.mark(1, "Open the profile menu")
    lp.open_profile_menu()

    step_capture.mark(2, "Verify Sign out option is visible in the profile menu")
    # Directly check that "Sign out" text is visible in the opened menu
    sign_out = page.locator('text=Sign out')
    assert sign_out.is_visible(), "Expected 'Sign out' option in profile menu"


@pytest.mark.ui
@pytest.mark.logout
@pytest.mark.qatouch("pDpmLx")
def test_logout_redirects_to_login(authenticated_page, base_url, step_capture):
    """Verify logout redirects to the login page."""
    step_capture.set_page(authenticated_page)
    page = authenticated_page
    lp = LoginPage(page, base_url)

    step_capture.mark(1, "Verify user is logged in")
    assert lp.is_logged_in(), "Precondition: must be logged in"

    lp.logout()

    step_capture.mark(2, "Log out and verify redirect to login page")
    assert lp.is_login_page(), "Should be on login page after logout"
    assert "/auth/login" in page.url, f"URL should contain /auth/login, got: {page.url}"

    step_capture.mark(3, "Verify URL contains /auth/login path")


@pytest.mark.ui
@pytest.mark.logout
@pytest.mark.qatouch("XGLe70")
def test_login_form_visible_after_logout(authenticated_page, base_url, step_capture):
    """Verify the login form is fully visible and functional after logout."""
    step_capture.set_page(authenticated_page)
    page = authenticated_page
    lp = LoginPage(page, base_url)

    step_capture.mark(1, "Log out of the application")
    lp.logout()

    step_capture.mark(2, "Verify email, password fields and submit button are visible")
    email_field = page.locator('input[name="email"]')
    password_field = page.locator('input[name="password"]')
    submit_btn = page.locator('button[type="submit"]')

    expect(email_field).to_be_visible()
    expect(password_field).to_be_visible()
    expect(submit_btn).to_be_visible()


@pytest.mark.ui
@pytest.mark.logout
@pytest.mark.qatouch("3gj93P")
def test_cannot_access_app_after_logout(authenticated_page, base_url, step_capture):
    """Verify navigating to the app after logout redirects to login.

    The SPA's root URL checks auth state and redirects unauthenticated
    users to /auth/login. Direct deep-links like /dashboard may not
    redirect (SPA serves index.html for all routes), so we test the
    root URL which reliably enforces the auth guard.
    """
    step_capture.set_page(authenticated_page)
    page = authenticated_page
    lp = LoginPage(page, base_url)

    step_capture.mark(1, "Log out of the application")
    lp.logout()

    step_capture.mark(2, "Navigate to the app root URL after logout")
    # Navigate to root URL -- the SPA auth guard should redirect to login
    page.goto(base_url)
    try:
        page.wait_for_url('**/auth/login**', timeout=15000)
    except Exception:
        page.wait_for_timeout(5000)

    step_capture.mark(3, "Verify redirect to login page after attempting to access the app")
    assert lp.is_login_page() or "/auth/login" in page.url, \
        f"Should be redirected to login after logout, got: {page.url}"


@pytest.mark.ui
@pytest.mark.logout
@pytest.mark.qatouch("41VMQv")
def test_back_button_after_logout(authenticated_page, base_url, step_capture):
    """Verify browser back button after logout doesn't bypass authentication."""
    step_capture.set_page(authenticated_page)
    page = authenticated_page
    lp = LoginPage(page, base_url)

    step_capture.mark(1, "Log out and verify login page is displayed")
    lp.logout()
    assert lp.is_login_page(), "Precondition: must be on login page after logout"

    step_capture.mark(2, "Press browser back button")
    page.go_back()
    page.wait_for_load_state("domcontentloaded", timeout=15000)
    page.wait_for_timeout(3000)

    step_capture.mark(3, "Verify back button does not bypass authentication")
    assert lp.is_login_page() or "/auth/login" in page.url, \
        "Browser back should not bypass authentication after logout"


@pytest.mark.ui
@pytest.mark.logout
@pytest.mark.qatouch("21zWgR")
def test_relogin_after_logout(authenticated_page, base_url, login_data, step_capture):
    """Verify successful re-login after logging out."""
    step_capture.set_page(authenticated_page)
    page = authenticated_page
    lp = LoginPage(page, base_url)

    step_capture.mark(1, "Log out and verify login page is displayed")
    lp.logout()
    assert lp.is_login_page(), "Precondition: must be on login page after logout"

    step_capture.mark(2, "Re-login with valid credentials")
    lp.login(login_data['username'], login_data['password'])

    step_capture.mark(3, "Verify user is logged in successfully after re-login")
    assert lp.is_logged_in(), "Should be logged in after re-login"


@pytest.mark.ui
@pytest.mark.logout
@pytest.mark.parametrize("path,page_name", [
    ("/search", "Search"),
    ("/events", "Events"),
    ("/insights", "Insights"),
])
def test_logout_from_different_pages(authenticated_page, base_url, path, page_name, step_capture):
    """Verify logout works from various application pages."""
    step_capture.set_page(authenticated_page)
    page = authenticated_page
    lp = LoginPage(page, base_url)

    step_capture.mark(1, f"Navigate to the {page_name} page")
    page.goto(base_url + path, wait_until="domcontentloaded")
    # Wait for the SPA to fully render the page header with avatar
    try:
        page.locator('.MuiAvatar-root').first.wait_for(state="visible", timeout=20000)
    except Exception:
        # Some pages render the header after heavy content -- wait and retry
        page.wait_for_timeout(5000)

    step_capture.mark(2, f"Log out from the {page_name} page")
    lp.logout()

    step_capture.mark(3, "Verify redirect to login page after logout")
    assert lp.is_login_page(), f"Should be on login page after logout from {page_name}"
