"""C2C Hardware Tests - Authentication.

Verify camera web UI login with valid and invalid credentials.
"""
import pytest
from playwright.sync_api import expect


class TestC2CAuth:
    """Camera authentication tests - parametrized across all enabled cameras."""

    @pytest.mark.smoke
    @pytest.mark.regression
    @pytest.mark.c2c_hardware
    def test_camera_login_and_live_view(self, browser, camera_config, step_capture):
        """Verify camera web UI login and session - happy path."""
        context = browser.new_context(
            http_credentials={
                "username": camera_config["user"],
                "password": camera_config["password"],
            },
            ignore_https_errors=True,
        )
        page = context.new_page()
        step_capture.set_page(page)

        step_capture.mark(1, "Navigate to camera web UI")
        page.goto(
            f"http://{camera_config['ip']}/cgi-bin/index.cgi",
            wait_until="domcontentloaded",
            timeout=15000,
        )

        step_capture.mark(2, "Verify Soterix Systems branding is visible")
        expect(page.locator("text=/SOTERIX/i").first).to_be_visible(timeout=5000)

        step_capture.mark(3, "Verify camera timestamp overlay is present")
        expect(page.locator("text=/\\d{4}-\\d{2}-\\d{2}/").first).to_be_visible(timeout=5000)

        step_capture.mark(4, "Verify Setup button is accessible")
        expect(page.locator("button:has-text('Setup')")).to_be_visible()

        step_capture.mark(5, "Verify live view controls are present")
        expect(page.locator("button:has-text('Full screen')")).to_be_visible()

        context.close()

    @pytest.mark.smoke
    @pytest.mark.security
    @pytest.mark.c2c_hardware
    def test_camera_rejects_invalid_credentials(self, browser, camera_config, step_capture):
        """Verify camera rejects invalid credentials."""
        context = browser.new_context(
            http_credentials={
                "username": "admin",
                "password": "wrongpass",
            },
            ignore_https_errors=True,
        )
        page = context.new_page()
        step_capture.set_page(page)

        step_capture.mark(1, "Attempt login with invalid credentials")
        response = page.goto(
            f"http://{camera_config['ip']}/cgi-bin/index.cgi",
            wait_until="domcontentloaded",
            timeout=15000,
        )

        step_capture.mark(2, "Verify access is denied (401 Unauthorized)")
        assert response.status == 401, f"Expected 401, got {response.status}"

        step_capture.mark(3, "Verify no camera UI content is accessible")
        # Should NOT see Setup button or Soterix branding
        assert page.locator("button:has-text('Setup')").count() == 0

        context.close()
