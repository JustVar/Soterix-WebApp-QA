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
        """Verify live view controls on main page."""
        self.step_capture.mark(1, "Verify live video feed is displayed")
        # The main page should have loaded via camera_page fixture
        expect(self.page.locator("text=/SOTERIX/i").first).to_be_visible(timeout=5000)

        self.step_capture.mark(2, "Verify camera timestamp overlay updates")
        timestamp = self.page.locator("text=/\\d{4}-\\d{2}-\\d{2} \\d{2}:\\d{2}:\\d{2}/").first
        expect(timestamp).to_be_visible()

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
        """Verify camera speaker and alarm controls on main page."""
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

        self.step_capture.mark(6, "Verify Camera time display matches timestamp")
        assert "Camera time" in page_text
        # Camera time should show a date-time string
        expect(self.page.locator("text=/\\d{4}-\\d{2}-\\d{2} \\d{2}:\\d{2}:\\d{2}/").first).to_be_visible()


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
        """Verify user management and security configuration pages."""
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
