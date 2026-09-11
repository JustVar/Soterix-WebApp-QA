"""C2C Hardware Tests - Network and RTSP.

Verify network status, IP configuration, and RTSP stream endpoint.
"""
import pytest
from playwright.sync_api import expect

from tests.shared.pages.camera_hardware_page import CameraHardwarePage


class TestC2CNetwork:
    """Network configuration and RTSP tests."""

    @pytest.fixture(autouse=True)
    def setup(self, camera_setup_page, camera_config, step_capture):
        self.page = camera_setup_page
        self.config = camera_config
        self.camera = CameraHardwarePage(self.page, camera_config)
        self.step_capture = step_capture
        step_capture.set_page(self.page)
        return

    @pytest.mark.smoke
    @pytest.mark.regression
    @pytest.mark.c2c_hardware
    def test_network_status(self):
        """Verify network status displays correct configuration.

        Steps:
        1. Open Setup > NETWORK > STATUS.
           Expected: The NETWORK STATUS page is shown.
        2. Read the addresses.
           Expected: A MAC address is shown, the IP address is the camera's IP, the subnet mask is 255.255.255.0 and a default gateway on the lab network (192.168.x.x) is shown.
        3. Read the ports.
           Expected: HTTP 80, HTTPS 443 and RTSP 554 are listed.
        """
        self.step_capture.mark(1, "Navigate to Network Status")
        self.camera.navigate_to_setup_section("NETWORK")
        self.camera.navigate_to_setup_subsection("STATUS")
        expect(self.page.locator("text='NETWORK STATUS'")).to_be_visible()

        self.step_capture.mark(2, "Verify MAC address is displayed")
        expect(self.page.locator("text=/([0-9A-Fa-f]{2}:){5}[0-9A-Fa-f]{2}/")).to_be_visible()

        self.step_capture.mark(3, "Verify IP address matches camera IP")
        ip = self.config["ip"]
        expect(self.page.locator(f"text='{ip}'")).to_be_visible()

        self.step_capture.mark(4, "Verify Subnet mask is 255.255.255.0")
        expect(self.page.locator("text='255.255.255.0'")).to_be_visible()

        self.step_capture.mark(5, "Verify Default gateway is populated")
        expect(self.page.locator("text=/192\\.168\\.\\d+\\.\\d+/").first).to_be_visible()

        self.step_capture.mark(6, "Verify HTTP=80, HTTPS=443, RTSP=554")
        page_text = self.page.locator("body").inner_text()
        assert "80" in page_text
        assert "443" in page_text
        assert "554" in page_text

    @pytest.mark.smoke
    @pytest.mark.regression
    @pytest.mark.c2c_hardware
    def test_rtsp_stream_configuration(self):
        """Verify RTSP stream is accessible and configured correctly.

        Steps:
        1. Open Setup > NETWORK > RTSP INFORMATION.
           Expected: The RTSP INFORMATION page is shown.
        2. Read the RTSP URI.
           Expected: It is rtsp://<camera IP>:554/<channel> (channel1, or the lens's channel on a multi-lens camera), and the Identifier field shows the same channel.
        3. Read the RTSP options.
           Expected: Audio and Meta options are present, and a Copy button is beside the URI.
        """
        self.step_capture.mark(1, "Navigate to RTSP Information")
        self.camera.navigate_to_setup_section("NETWORK")
        self.camera.navigate_to_setup_subsection("RTSP INFORMATION")
        expect(self.page.locator("text='RTSP INFORMATION'")).to_be_visible()

        self.step_capture.mark(2, "Verify RTSP URI contains camera IP and channel")
        ip = self.config["ip"]
        # Multi-lens cameras use channel1/channel2/etc. based on lens_id
        channel = self.config.get("channel", "channel1")
        expected_uri = f"rtsp://{ip}:554/{channel}"
        expect(self.page.locator(f"text='{expected_uri}'")).to_be_visible()

        self.step_capture.mark(3, f"Verify Identifier is {channel}")
        identifier_input = self.page.locator(f"input[value='{channel}']")
        expect(identifier_input).to_be_visible()

        self.step_capture.mark(4, "Verify RTSP Options include Audio and Meta")
        page_text = self.page.locator("body").inner_text()
        assert "Audio" in page_text
        assert "Meta" in page_text

        self.step_capture.mark(5, "Verify Copy button exists for RTSP URI")
        expect(self.page.locator("button:has-text('Copy')")).to_be_visible()
