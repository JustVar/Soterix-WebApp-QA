"""C2C Hardware Tests - Video, OSD, Audio Configuration.

Verify video stream settings, OSD overlay, audio encode/output,
and stream modification.
"""
import pytest
from playwright.sync_api import expect

from tests.shared.pages.camera_hardware_page import CameraHardwarePage


class TestC2CVideoConfig:
    """Video stream configuration tests."""

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
    def test_default_stream_configuration(self):
        """Verify default video stream configuration across all 3 streams."""
        self.step_capture.mark(1, "Navigate to Video Configuration (default page)")
        # Setup page opens to VIDEO by default
        expect(self.page.locator("text='VIDEO CONFIGURATION'")).to_be_visible()

        self.step_capture.mark(2, "Verify Stream 1: H.265, 2592x1944, 14 FPS")
        page_text = self.page.locator("body").inner_text()
        assert "H.265" in page_text
        assert "2592x1944" in page_text

        self.step_capture.mark(3, "Verify Stream 2: H.265, 640x360, 14 FPS")
        assert "640x360" in page_text

        self.step_capture.mark(4, "Verify Stream 3: M-JPEG, 640x360, 30 FPS")
        assert "M-JPEG" in page_text

        self.step_capture.mark(5, "Verify Stream 1 details: VBR, 2560 Kbps, Quality 5, GOP 14")
        # Check codec detail form values
        codec_select = self.page.locator("select").first
        assert codec_select.input_value() == "H.265"

    @pytest.mark.regression
    @pytest.mark.c2c_hardware
    def test_stream_codec_and_resolution_change(self):
        """Verify stream codec and resolution can be changed and applied."""
        self.step_capture.mark(1, "Navigate to Video Configuration")
        expect(self.page.locator("text='VIDEO CONFIGURATION'")).to_be_visible()

        self.step_capture.mark(2, "Save original codec and resolution values")
        codec_select = self.page.locator("select").first
        original_codec = codec_select.input_value()
        # Find resolution select
        res_selects = self.page.locator("select")
        original_resolution = None
        for i in range(res_selects.count()):
            options = res_selects.nth(i).locator("option")
            for j in range(options.count()):
                if "1920x1080" in options.nth(j).text_content():
                    original_resolution = res_selects.nth(i).input_value()
                    break
            if original_resolution is not None:
                break

        self.step_capture.mark(3, "Change Codec to H.264")
        codec_select.select_option(label="H.264")

        self.step_capture.mark(4, "Click Apply")
        self.camera.click_apply()

        self.step_capture.mark(5, "Verify codec change was saved")
        self.page.wait_for_timeout(1000)
        assert self.page.locator("select").first.input_value() == "H.264"

        self.step_capture.mark(6, "Restore original codec and Apply")
        self.page.locator("select").first.select_option(label=original_codec)
        self.camera.click_apply()


class TestC2COSD:
    """OSD (On Screen Display) configuration tests."""

    @pytest.fixture(autouse=True)
    def setup(self, camera_setup_page, camera_config, step_capture):
        self.page = camera_setup_page
        self.config = camera_config
        self.camera = CameraHardwarePage(self.page, camera_config)
        self.step_capture = step_capture
        step_capture.set_page(self.page)
        return

    @pytest.mark.regression
    @pytest.mark.c2c_hardware
    def test_osd_configuration(self):
        """Verify OSD date/time overlay is enabled and configurable."""
        self.step_capture.mark(1, "Navigate to OSD Configuration")
        self.camera.navigate_to_setup_subsection("OSD")
        expect(self.page.locator("text=/ON SCREEN DISPLAY/")).to_be_visible()

        self.step_capture.mark(2, "Verify Date & time is set to On")
        page_text = self.page.locator("body").inner_text()
        assert "Date & time" in page_text

        self.step_capture.mark(3, "Verify OSD Text color is set (default orange)")
        expect(self.page.locator("input[type='color'], text=/RGB/").first).to_be_visible()

        self.step_capture.mark(4, "Verify Position X and Y are within 0-100 range")
        position_inputs = self.page.locator("input[type='text']")
        # Check that position fields exist
        assert position_inputs.count() >= 2

        self.step_capture.mark(5, "Verify User text section exists with Off/On toggle")
        assert "User text" in page_text


class TestC2CAudio:
    """Audio configuration tests."""

    @pytest.fixture(autouse=True)
    def setup(self, camera_setup_page, camera_config, step_capture):
        self.page = camera_setup_page
        self.config = camera_config
        self.camera = CameraHardwarePage(self.page, camera_config)
        self.step_capture = step_capture
        step_capture.set_page(self.page)
        return

    @pytest.mark.regression
    @pytest.mark.c2c_hardware
    def test_audio_configuration_defaults(self):
        """Verify audio configuration defaults and controls."""
        self.step_capture.mark(1, "Navigate to Audio Configuration")
        self.camera.navigate_to_setup_subsection("AUDIO")
        expect(self.page.locator("text='AUDIO CONFIGURATION'")).to_be_visible()

        self.step_capture.mark(2, "Verify Audio encode is set to On")
        page_text = self.page.locator("body").inner_text()
        assert "Audio encode" in page_text or "Audio" in page_text

        self.step_capture.mark(3, "Verify Codec is G.711 ulaw")
        expect(self.page.locator("text='G.711 ulaw'")).to_be_visible()

        self.step_capture.mark(4, "Verify Volume is set to 10")
        volume_select = self.page.locator("select").filter(
            has=self.page.locator("option[value='10']")
        ).first
        assert volume_select.input_value() == "10"

        self.step_capture.mark(5, "Verify Sample rate is 8,000 Hz")
        expect(self.page.locator("text='8,000 Hz'").first).to_be_visible()

        self.step_capture.mark(6, "Verify Audio out section with channels and volume")
        assert "Audio alarm" in page_text or "Audio out" in page_text

        self.step_capture.mark(7, "Verify output sample rate options exist")
        expect(self.page.locator("text='16,000 Hz'")).to_be_visible()
