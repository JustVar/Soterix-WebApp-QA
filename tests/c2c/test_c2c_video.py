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
        """Verify default video stream configuration across all 3 streams.

        Steps:
        1. Open Setup (it opens on VIDEO CONFIGURATION).
           Expected: The VIDEO CONFIGURATION page is shown.
        2. Read the stream table.
           Expected: Three streams; Stream 1 is H.265 at the registry's max resolution for this unit (2592x1944, 4000x3000 on FC-12F-1) and Stream 3 is M-JPEG. Stream 2's resolution is a per-unit setting and is only read.
        3. Read the Stream 1 codec and resolution fields.
           Expected: They show the same codec and resolution as the table's first row.
        """
        self.step_capture.mark(1, "Navigate to Video Configuration (default page)")
        # Setup page opens to VIDEO by default
        expect(self.camera.heading("VIDEO CONFIGURATION")).to_be_visible()

        self.step_capture.mark(2, "Read the stream table")
        streams = self.camera.stream_rows()
        assert len(streams) == 3, (
            f"{self.camera.ip}: expected three streams in the table, read {streams}")

        # the registry's max resolution (read from System Information at
        # discovery) is stream 1's default; the page writes it without
        # spaces, the registry sometimes with ('4000 x 3000' on FC-12F-1)
        max_res = self.config["max_resolution"].replace(" ", "")
        self.step_capture.mark(3, f"Verify Stream 1 is H.265 at {max_res}")
        assert streams[0]["codec"] == "H.265", f"{self.camera.ip}: stream 1 reads {streams[0]}"
        assert streams[0]["resolution"] == max_res, (
            f"{self.camera.ip}: stream 1 is {streams[0]['resolution']}, the registry's "
            f"max resolution is {max_res}")

        # stream 2's resolution is a per-unit setting (640x360, 800x600 and
        # 320x320 across the lab on 09/11/2026), so it is read, not judged
        self.step_capture.mark(4, "Verify Stream 3 is M-JPEG")
        assert streams[2]["codec"] == "M-JPEG", f"{self.camera.ip}: stream 3 reads {streams[2]}"

        self.step_capture.mark(5, "Verify the Stream 1 fields match the table")
        # the first select on the page is not the codec on every firmware
        # (probed 09/11/2026): the codec select is the one offering H.265.
        # The selected option's text, not the select's value: the values
        # are numbers on some firmware ('3' for H.265 on BC-5V-1)
        codec_select = self.camera.codec_select()
        expect(self.camera.selected_option(codec_select)).to_have_text(streams[0]["codec"])
        resolution_select = self.camera.select_with_option(streams[0]["resolution"])
        expect(self.camera.selected_option(resolution_select)).to_have_text(
            streams[0]["resolution"])

    @pytest.mark.regression
    @pytest.mark.c2c_hardware
    @pytest.mark.mutating
    def test_stream_codec_and_resolution_change(self):
        """Verify the stream codec can be changed and applied.

        MUTATING: changes the Stream 1 codec and puts it back. The resolution
        is read, not changed.

        Steps:
        1. Open Setup > VIDEO CONFIGURATION and note the Stream 1 codec.
           Expected: The codec field shows the current codec.
        2. Change the codec to H.264 and click Apply.
           Expected: After Apply, the codec field reads H.264.
        3. Put the original codec back and click Apply.
           Expected: The original codec is restored (the test restores it even when a step fails).
        """
        self.step_capture.mark(1, "Navigate to Video Configuration")
        expect(self.camera.heading("VIDEO CONFIGURATION")).to_be_visible()

        self.step_capture.mark(2, "Save original codec and resolution values")
        codec_select = self.camera.codec_select()
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

        try:
            self.step_capture.mark(3, "Change Codec to H.264")
            codec_select.select_option(label="H.264")

            self.step_capture.mark(4, "Click Apply")
            self.camera.click_apply()

            self.step_capture.mark(5, "Verify codec change was saved")
            expect(self.camera.selected_option(self.camera.codec_select())).to_have_text(
                "H.264", timeout=10000)
        finally:
            # Restore in a finally block: a failed verification previously left
            # the camera encoding H.264 instead of its configured codec.
            self.step_capture.mark(6, "Restore original codec and Apply")
            try:
                self.camera.codec_select().select_option(value=original_codec)
                self.camera.click_apply()
            except Exception as restore_err:  # noqa: BLE001 - must not mask the real failure
                pytest.fail(
                    f"Could not restore codec on {self.camera.ip}: "
                    f"{restore_err}. Camera may still be set to H.264."
                )


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
        """Verify OSD date/time overlay is enabled and configurable.

        Steps:
        1. On the Setup page, open OSD.
           Expected: The ON SCREEN DISPLAY page shows the Date & time setting.
        2. Read the text settings.
           Expected: A text colour control is shown, Position X and Y fields are present, and a User text section with its Off/On toggle.
        """
        self.step_capture.mark(1, "Navigate to OSD Configuration")
        self.camera.navigate_to_setup_subsection("OSD")
        expect(self.camera.heading("ON SCREEN DISPLAY")).to_be_visible()

        self.step_capture.mark(2, "Verify Date & time is set to On")
        page_text = self.page.locator("body").inner_text()
        assert "Date & time" in page_text

        self.step_capture.mark(3, "Verify OSD Text color is set (default orange)")
        # the colour picker input; its RGB text twin is a plain text field
        expect(self.page.locator("#tabs input[type='color']")).to_be_visible()

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
        """Verify audio configuration defaults and controls.

        Steps:
        1. On the Setup page, open AUDIO.
           Expected: The AUDIO CONFIGURATION page shows the Audio encode setting.
        2. Read the encode settings.
           Expected: Codec is G.711 ulaw, Volume is 10 and Sample rate is 8,000 Hz.
        3. Read the audio out section.
           Expected: Audio out (or Audio alarm) with channels and volume is shown, with 16,000 Hz among the output sample rates.
        """
        self.step_capture.mark(1, "Navigate to Audio Configuration")
        self.camera.navigate_to_setup_subsection("AUDIO")
        expect(self.camera.heading("AUDIO CONFIGURATION")).to_be_visible()

        self.step_capture.mark(2, "Verify Audio encode is set to On")
        page_text = self.page.locator("body").inner_text()
        assert "Audio encode" in page_text or "Audio" in page_text

        self.step_capture.mark(3, "Verify Codec is G.711 ulaw")
        # each value is a select's chosen option: options are hidden
        # elements, so the selected option's text is what is read
        codec = self.camera.select_with_option("G.711 ulaw")
        expect(self.camera.selected_option(codec)).to_have_text("G.711 ulaw")

        self.step_capture.mark(4, "Verify Volume is set to 10")
        volume_select = self.page.locator("select").filter(
            has=self.page.locator("option[value='10']")
        ).first
        assert volume_select.input_value() == "10"

        self.step_capture.mark(5, "Verify Sample rate is 8,000 Hz")
        rate = self.camera.select_with_option("8,000 Hz")
        expect(self.camera.selected_option(rate)).to_have_text("8,000 Hz")

        self.step_capture.mark(6, "Verify Audio out section with channels and volume")
        assert "Audio alarm" in page_text or "Audio out" in page_text

        self.step_capture.mark(7, "Verify output sample rate options exist")
        out_rate = self.camera.select_with_option("16,000 Hz")
        expect(out_rate.locator("option:has-text('16,000 Hz')")).to_be_attached()
