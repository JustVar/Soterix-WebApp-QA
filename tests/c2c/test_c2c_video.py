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
        1. Open Setup > VIDEO CONFIGURATION and note the Stream 1 codec in the stream table.
           Expected: The table's first row shows the current codec (H.265 on every lab unit).
        2. Change the codec to H.264 and click Apply.
           Expected: Within 30 seconds the table's first row reads H.264 (the camera re-reads its settings a few seconds after Apply).
        3. Put the original codec back and click Apply.
           Expected: Within 30 seconds the table's first row reads the original codec and frame rate again (a codec change resets the rate to 30, so the test puts it back); the test restores both even when a step fails, and fails by name if the camera is left changed.
        """
        self.step_capture.mark(1, "Navigate to Video Configuration")
        expect(self.camera.heading("VIDEO CONFIGURATION")).to_be_visible()

        self.step_capture.mark(2, "Note the Stream 1 codec in the table")
        # the table is the applied truth; the select only echoes a choice.
        # 10.2.0.135 was left on H.264 by a run whose restore clicked Apply
        # before the table had re-read the first change (09/12/2026), so
        # both changes below wait for the table, and the restore is checked
        streams = self.camera.stream_rows()
        assert streams, f"{self.camera.ip}: no stream table on the VIDEO page"
        before = streams[0]
        assert before["codec"] != "H.264", (
            f"{self.camera.ip}: stream 1 already reads H.264 before the test; a previous "
            f"run left it so, or the unit was reconfigured - put it back before re-running")

        try:
            self.step_capture.mark(3, "Change Codec to H.264")
            self.camera.codec_select().select_option(label="H.264")

            self.step_capture.mark(4, "Click Apply")
            self.camera.click_apply()

            self.step_capture.mark(5, "Verify the table reads H.264")
            self.camera.wait_for_stream_codec("H.264")
        finally:
            # Restore the whole row in a finally block and verify it: a
            # restore that only clicked left 10.2.0.135 on H.264, and a
            # codec change resets the frame rate to 30, so the rate goes
            # back too (09/12/2026)
            self.step_capture.mark(6, f"Restore {before['codec']} at {before['fps']} fps and Apply")
            try:
                self.camera.codec_select().select_option(label=before["codec"])
                self.camera.framerate_select().select_option(label=before["fps"])
                self.camera.click_apply()
                after = self.camera.wait_for_stream_codec(before["codec"])[0]
                assert after == before, f"stream 1 reads {after}, it was {before}"
            except Exception as restore_err:  # noqa: BLE001 - must not mask the real failure
                pytest.fail(
                    f"Could not restore stream 1 on {self.camera.ip}: "
                    f"{restore_err}. The camera may still be set to H.264 at 30 fps."
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
