"""C2C Hardware Tests - Authentication.

Verify camera web UI login with valid and invalid credentials.
"""
import re

import pytest
from playwright.sync_api import expect


class TestC2CAuth:
    """Camera authentication tests - parametrized across all enabled cameras."""

    @pytest.mark.smoke
    @pytest.mark.regression
    @pytest.mark.c2c_hardware
    def test_camera_login_and_live_view(self, browser, camera_config, step_capture):
        """Verify camera web UI login and session - happy path.

        Steps:
        1. Open the camera's web UI (http://<camera IP>/cgi-bin/index.cgi) and sign in with the lab login when the browser asks.
           Expected: The main page opens with the Setup button and the Channel select.
        2. Read the Camera time.
           Expected: A Camera time is shown.
        3. Look at the live view controls.
           Expected: The Full screen button is shown.
        """
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

        # The branding is a CSS background on every model (no text, no img;
        # probed 09/11/2026), so the login's proof is the main page itself:
        # its Setup button and its Channel select.
        step_capture.mark(2, "Verify the main page opened: Setup button and Channel select")
        expect(page.locator("button:has-text('Setup')")).to_be_visible(timeout=10000)
        expect(page.get_by_text("Channel select", exact=True)).to_be_visible()

        step_capture.mark(3, "Verify the camera time is shown")
        expect(page.get_by_text("Camera time", exact=True)).to_be_visible(timeout=5000)
        # the label's row carries the clock, hh:mm:ss (measured 09/12/2026)
        expect(page.get_by_text("Camera time", exact=True).locator("xpath=..")).to_contain_text(
            re.compile(r"\d{2}:\d{2}:\d{2}"))

        step_capture.mark(4, "Verify the Full screen control is present")
        expect(page.locator("button:has-text('Full screen')")).to_be_visible()

        context.close()

    @pytest.mark.smoke
    @pytest.mark.security
    @pytest.mark.c2c_hardware
    def test_camera_rejects_invalid_credentials(self, browser, camera_config, step_capture):
        """Verify camera rejects invalid credentials.

        Steps:
        1. Open the camera's web UI and sign in with a wrong username and password (admin / wrongpass).
           Expected: The camera answers 401 Unauthorized.
        2. Look at the page.
           Expected: No camera page content is shown, and there is no Setup button.
        """
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
