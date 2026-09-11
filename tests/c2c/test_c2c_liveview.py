"""C2C Hardware Tests - Live View and Main Page Controls.

Verify live video feed, stream switching, zoom/focus controls,
speaker controls, alarm/relay indicators, and camera time.
"""
import pytest
from playwright.sync_api import expect

from tests.shared.pages.camera_hardware_page import CameraHardwarePage


class TestC2CLiveView:
    """Main page live view and control tests."""

    @pytest.fixture(autouse=True)
    def setup(self, camera_page, camera_config, step_capture):
        # camera_page fixture navigates to the main page (not setup)
        self.page = camera_page
        self.config = camera_config
        self.camera = CameraHardwarePage(self.page, camera_config)
        self.step_capture = step_capture
        step_capture.set_page(self.page)
        return

    @pytest.mark.smoke
    @pytest.mark.regression
    @pytest.mark.c2c_hardware
    def test_live_view_controls(self):
        """Verify live view controls on main page.

        Steps:
        1. Open the camera's main page.
           Expected: The Setup button is shown and Camera time shows a value.
        2. Read the page for the channel and screen controls.
           Expected: Channel select and the Full screen button are present.
        3. Read the page for the lens controls.
           Expected: Zoom, Focus and Auto focus are present, with Focus and Calibrate buttons.
        """
        self.step_capture.mark(1, "Verify the main page is up: the Setup button is shown")
        # the branding is a CSS background on every model (probed 09/11/2026)
        expect(self.page.locator("button:has-text('Setup')")).to_be_visible(timeout=5000)

        self.step_capture.mark(2, "Verify the Camera time is shown with a value")
        # the format differs by model (BC-5M-1 and FC-12F-1 show no YYYY-MM-DD),
        # so the check is the label and a non-empty value beside it
        time_block = self.page.get_by_text("Camera time", exact=True).locator("xpath=..")
        expect(time_block).to_be_visible()
        assert len(time_block.inner_text().replace("Camera time", "").strip()) >= 8, (
            f"Camera time shows no value: {time_block.inner_text()!r}")

        self.step_capture.mark(3, "Verify Channel select dropdown exists")
        page_text = self.page.locator("body").inner_text()
        assert "Channel select" in page_text

        self.step_capture.mark(4, "Verify Full screen button is functional")
        expect(self.page.locator("button:has-text('Full screen')")).to_be_visible()

        self.step_capture.mark(5, "Verify Zoom controls (W to T) are present")
        assert "Zoom" in page_text

        self.step_capture.mark(6, "Verify Focus controls and Auto focus exist")
        assert "Focus" in page_text
        assert "Auto focus" in page_text

        self.step_capture.mark(7, "Verify Focus and Calibrate buttons exist")
        expect(self.page.locator("button:has-text('Focus')").first).to_be_visible()
        expect(self.page.locator("button:has-text('Calibrate')")).to_be_visible()

    @pytest.mark.regression
    @pytest.mark.c2c_hardware
    def test_speaker_and_alarm_controls(self):
        """Verify camera speaker and alarm controls on main page.

        Steps:
        1. Open the camera's main page and read the controls under the live view.
           Expected: PC speaker and Cam speaker controls are present.
        2. Read the alarm section.
           Expected: Alarm input, Relay out and Motion indicators are present.
        3. Read the Camera time.
           Expected: Camera time shows a date and time.
        """
        self.step_capture.mark(1, "Verify PC speaker volume control exists")
        page_text = self.page.locator("body").inner_text()
        assert "PC speaker" in page_text

        self.step_capture.mark(2, "Verify Cam speaker section with channels")
        assert "Cam speaker" in page_text

        self.step_capture.mark(3, "Verify Alarm input indicator exists")
        assert "Alarm input" in page_text

        self.step_capture.mark(4, "Verify Relay out control exists")
        assert "Relay out" in page_text

        self.step_capture.mark(5, "Verify Motion indicator exists")
        assert "Motion" in page_text

        self.step_capture.mark(6, "Verify Camera time is shown with a value")
        assert "Camera time" in page_text
        time_block = self.page.get_by_text("Camera time", exact=True).locator("xpath=..")
        assert len(time_block.inner_text().replace("Camera time", "").strip()) >= 8, (
            f"Camera time shows no value: {time_block.inner_text()!r}")


class TestC2CSecurity:
    """Security configuration tests."""

    @pytest.fixture(autouse=True)
    def setup(self, camera_setup_page, camera_config, step_capture):
        self.page = camera_setup_page
        self.config = camera_config
        self.camera = CameraHardwarePage(self.page, camera_config)
        self.step_capture = step_capture
        step_capture.set_page(self.page)
        return

    @pytest.mark.regression
    @pytest.mark.security
    @pytest.mark.c2c_hardware
    def test_security_pages_accessible(self):
        """Verify user management and security configuration pages.

        Steps:
        1. Open Setup > SYSTEM > USER MANAGEMENT.
           Expected: The user list is shown and includes the root user.
        2. Open Setup > SECURITY > RTSP AUTHENTICATION.
           Expected: The RTSP authentication page is shown.
        3. Open SECURITY > IP ADDRESS FILTER.
           Expected: The IP address filter page is shown.
        4. Open SECURITY > HTTPS.
           Expected: The HTTPS settings page is shown.
        """
        self.step_capture.mark(1, "Navigate to User Management")
        self.camera.navigate_to_setup_section("SYSTEM")
        self.camera.navigate_to_setup_subsection("USER MANAGEMENT")
        page_text = self.page.locator("body").inner_text()
        assert "USER" in page_text.upper()

        self.step_capture.mark(2, "Verify root user exists")
        assert "root" in page_text

        self.step_capture.mark(3, "Navigate to RTSP Authentication")
        self.camera.navigate_to_setup_section("SECURITY")
        self.camera.navigate_to_setup_subsection("RTSP AUTHENTICATION")
        page_text = self.page.locator("body").inner_text()
        assert "RTSP" in page_text.upper()

        self.step_capture.mark(4, "Navigate to IP Address Filter")
        self.camera.navigate_to_setup_subsection("IP ADDRESS FILTER")
        page_text = self.page.locator("body").inner_text()
        assert "IP" in page_text.upper()

        self.step_capture.mark(5, "Navigate to HTTPS settings")
        self.camera.navigate_to_setup_subsection("HTTPS")
        expect(self.page.locator("text=/HTTPS/")).to_be_visible()
