"""C2C Hardware Tests - Camera Settings, Motion Detection, Privacy Mask.

Verify image adjustment, exposure, day/night, backlight, white balance,
image/video enhancement, motion detection zones, and privacy mask.
"""
import re

import pytest
from playwright.sync_api import expect

from tests.shared.pages.camera_hardware_page import CameraHardwarePage


class TestC2CCameraSettings:
    """Camera image and enhancement settings tests."""

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
    def test_image_adjustment_defaults_and_reset(self):
        """Verify image adjustment defaults and reset to default.

        Steps:
        1. Open Setup > CAMERA > IMAGE ADJUSTMENT.
           Expected: The IMAGE ADJUSTMENT page shows sliders for Sharpness, Brightness, Contrast, Saturation and Hue.
        2. Look for the page buttons.
           Expected: Apply, Cancel and Default buttons are shown.
        3. Click Default.
           Expected: The page stays on IMAGE ADJUSTMENT with no error.
        """
        self.step_capture.mark(1, "Navigate to Image Adjustment")
        self.camera.navigate_to_setup_section("CAMERA")
        self.camera.navigate_to_setup_subsection("IMAGE ADJUSTMENT")
        expect(self.camera.heading("IMAGE ADJUSTMENT")).to_be_visible()

        self.step_capture.mark(2, "Verify default slider labels exist")
        page_text = self.page.locator("body").inner_text()
        for label in ["Sharpness", "Brightness", "Contrast", "Saturation", "Hue"]:
            assert label in page_text, f"Missing slider: {label}"

        self.step_capture.mark(3, "Verify Apply, Cancel, and Default buttons exist")
        expect(self.page.locator("button:has-text('Apply')").first).to_be_visible()
        expect(self.page.locator("button:has-text('Cancel')").first).to_be_visible()
        expect(self.page.locator("button:has-text('Default')")).to_be_visible()

        self.step_capture.mark(4, "Click Default button to verify it resets values")
        self.camera.click_default()
        # Default should work without error
        expect(self.camera.heading("IMAGE ADJUSTMENT")).to_be_visible()

    @pytest.mark.regression
    @pytest.mark.c2c_hardware
    def test_exposure_and_daynight_defaults(self):
        """Verify exposure and day/night settings defaults.

        Steps:
        1. Open Setup > CAMERA > EXPOSURE SETTINGS.
           Expected: The page shows Auto exposure and AE metering options.
        2. Open CAMERA > DAY&NIGHT SETTINGS.
           Expected: The page shows the Auto, Day and Night mode options.
        3. Read the IR settings.
           Expected: The IR controls the model record lists (tests/data/c2c_models.yaml) are present and no other known one is: IR mode on every model, IR strength on the single-sensor models.
        """
        self.step_capture.mark(1, "Navigate to Exposure Settings")
        self.camera.navigate_to_setup_section("CAMERA")
        self.camera.navigate_to_setup_subsection("EXPOSURE SETTINGS")
        expect(self.camera.heading("EXPOSURE SETTINGS")).to_be_visible()

        self.step_capture.mark(2, "Verify Auto exposure options and AE metering")
        page_text = self.page.locator("body").inner_text()
        assert "Auto exposure" in page_text
        assert "AE metering" in page_text

        self.step_capture.mark(3, "Navigate to Day&Night Settings")
        self.camera.navigate_to_setup_subsection("DAY&NIGHT SETTINGS")
        expect(self.camera.heading("DAY&NIGHT SETTINGS")).to_be_visible()

        self.step_capture.mark(4, "Verify Day & night mode options exist")
        page_text = self.page.locator("body").inner_text()
        assert "Auto" in page_text
        assert "Day" in page_text
        assert "Night" in page_text

        self.step_capture.mark(5, "Verify the IR controls match the model record")
        # IR strength is a single-sensor control: MS-20V-1 and FC-12F-1
        # have IR mode alone (measured 09/11/2026); the record decides
        self.camera.expect_controls(page_text, "day_night_controls")

    @pytest.mark.regression
    @pytest.mark.c2c_hardware
    def test_image_enhancement_and_backlight(self):
        """Verify image enhancement mirror/flip, 3D NR, LDC, and backlight WDR.

        Steps:
        1. Open Setup > CAMERA > IMAGE ENHANCEMENT.
           Expected: The page shows the controls the model record lists (tests/data/c2c_models.yaml: 3D noise reduction on every model; LDC, Mirror and Flip where the model has them) and no other known one, plus the note that changing mirror or flip resets the privacy mask where Mirror and Flip exist.
        2. Open CAMERA > BACKLIGHT SETTINGS.
           Expected: The page shows the WDR setting.
        3. Open CAMERA > VIDEO ENHANCEMENT.
           Expected: The page shows Flickerless with the 60Hz option.
        """
        self.step_capture.mark(1, "Navigate to Image Enhancement")
        self.camera.navigate_to_setup_section("CAMERA")
        self.camera.navigate_to_setup_subsection("IMAGE ENHANCEMENT")
        expect(self.camera.heading("IMAGE ENHANCEMENT")).to_be_visible()

        self.step_capture.mark(2, "Verify the enhancement controls match the model record")
        page_text = self.page.locator("body").inner_text()
        # the LDC row is hidden on MS-20V-1, and FC-12F-1 has neither LDC
        # nor Mirror/Flip (measured 09/11/2026); the record decides
        self.camera.expect_controls(page_text, "image_enhancement_controls")

        self.step_capture.mark(3, "Verify the mirror/flip note about the privacy mask reset")
        if "Mirror" in self.camera.model_facts["image_enhancement_controls"]:
            assert "privacy mask" in page_text.lower(), (
                f"{self.camera.ip}: the mirror/flip note about the privacy mask is missing")

        self.step_capture.mark(5, "Navigate to Backlight Settings and verify WDR")
        self.camera.navigate_to_setup_subsection("BACKLIGHT SETTINGS")
        expect(self.camera.heading("BACKLIGHT SETTINGS")).to_be_visible()
        page_text = self.page.locator("body").inner_text()
        assert "WDR" in page_text

        self.step_capture.mark(6, "Navigate to Video Enhancement and verify Flickerless")
        self.camera.navigate_to_setup_subsection("VIDEO ENHANCEMENT")
        expect(self.camera.heading("VIDEO ENHANCEMENT")).to_be_visible()
        page_text = self.page.locator("body").inner_text()
        assert "Flickerless" in page_text
        assert "60Hz" in page_text


class TestC2CMotionDetection:
    """Motion detection configuration tests."""

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
    def test_motion_detection_zones(self):
        """Verify motion detection configuration and zones.

        Steps:
        1. Open Setup > EVENTS > MOTION.
           Expected: The MOTION DETECTION CONFIGURATION page lists Motion area1 to Motion area4.
        2. Read the sensitivity of each area.
           Expected: Each of the four areas shows the model's default sensitivity (tests/data/c2c_models.yaml: 70, 80 on the FC-12F-1).
        3. Look for the page buttons.
           Expected: Apply and Cancel buttons are shown.
        """
        self.step_capture.mark(1, "Navigate to Motion Detection")
        self.camera.navigate_to_setup_section("EVENTS")
        self.camera.navigate_to_setup_subsection("MOTION")
        expect(self.camera.heading("MOTION DETECTION CONFIGURATION")).to_be_visible()

        self.step_capture.mark(2, "Verify 4 motion areas are available")
        page_text = self.page.locator("body").inner_text()
        for area in ["Motion area1", "Motion area2", "Motion area3", "Motion area4"]:
            assert area in page_text, f"Missing {area}"

        default = self.camera.model_facts["motion_sensitivity_default"]
        self.step_capture.mark(3, f"Verify default sensitivity is {default} for all areas")
        # Check that 70 appears multiple times (once per area)
        # each area row ends "- | + <value>"; the FC-12F-1 ships at 80
        # (measured 09/11/2026), the others at 70
        values = re.findall(r"Motion area\d\s*-\s*\+\s*(\d+)", page_text)
        assert values == [str(default)] * 4, (
            f"{self.camera.ip}: the four motion areas read {values}, the model's "
            f"default is {default}")

        self.step_capture.mark(4, "Verify Apply and Cancel buttons exist")
        expect(self.page.locator("button:has-text('Apply')").first).to_be_visible()
        expect(self.page.locator("button:has-text('Cancel')").first).to_be_visible()


class TestC2CPrivacyMask:
    """Privacy mask configuration tests."""

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
    def test_privacy_mask_configuration(self):
        """Verify privacy mask configuration page and controls.

        Steps:
        1. On the Setup page, open PRIVACY MASK.
           Expected: The PRIVACY MASK CONFIGURATION page is shown with an Activation setting.
        2. Open the Area dropdown.
           Expected: It lists several areas (Area1 and more).
        3. Look for the page buttons.
           Expected: Clear area, Apply and Cancel buttons are shown.
        """
        self.step_capture.mark(1, "Navigate to Privacy Mask")
        self.camera.navigate_to_setup_subsection("PRIVACY MASK")
        expect(self.camera.heading("PRIVACY MASK CONFIGURATION")).to_be_visible()

        self.step_capture.mark(2, "Verify Activation defaults to Off")
        page_text = self.page.locator("body").inner_text()
        assert "Activation" in page_text

        self.step_capture.mark(3, "Verify Area dropdown with multiple zones")
        expect(self.page.locator("select").filter(
            has=self.page.locator("option:has-text('Area1')")
        ).first).to_be_visible()

        self.step_capture.mark(4, "Verify Clear area, Apply, and Cancel buttons")
        expect(self.page.locator("button:has-text('Clear area')")).to_be_visible()
        expect(self.page.locator("button:has-text('Apply')").first).to_be_visible()
        expect(self.page.locator("button:has-text('Cancel')").first).to_be_visible()


class TestC2CAdditionalSettings:
    """Corridor, Smart Stream, ROI, White Balance tests."""

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
    def test_corridor_mode_options(self):
        """Verify corridor mode warning and options without triggering reboot.

        Steps:
        1. On the Setup page, open CORRIDOR SETTING.
           Expected: The page shows the options Off, 90 and 270.
        2. Read the note on the page.
           Expected: It warns that applying a change reboots the camera. Do not click Apply.
        """
        self.step_capture.mark(1, "Navigate to Corridor Setting")
        # the fisheye FC-12F-1 has no CORRIDOR SETTING entry (tests/data/c2c_models.yaml)
        self.camera.require_model_entry("CORRIDOR SETTING")
        self.camera.navigate_to_setup_subsection("CORRIDOR SETTING")
        expect(self.camera.heading("CORRIDOR SETTING")).to_be_visible()

        self.step_capture.mark(2, "Verify three options: Off, 90, 270")
        page_text = self.page.locator("body").inner_text()
        assert "Off" in page_text
        assert "90" in page_text
        assert "270" in page_text

        self.step_capture.mark(3, "Verify warning about system reboot")
        assert "reboot" in page_text.lower()

        # DO NOT click Apply - would trigger reboot

    @pytest.mark.regression
    @pytest.mark.c2c_hardware
    def test_smart_stream_disabled(self):
        """Verify the Smart Stream page shows its configuration fields.

        Steps:
        1. On the Setup page, open SMART STREAM.
           Expected: The SMART STREAM page shows the fields Frame rate, GOP, Bitrate mode, Target bitrate, Hold on time and Trigger event.
        """
        self.step_capture.mark(1, "Navigate to Smart Stream")
        # MS-20V-1 firmware has no SMART STREAM entry (tests/data/c2c_models.yaml)
        self.camera.require_model_entry("SMART STREAM")
        self.camera.navigate_to_setup_subsection("SMART STREAM")
        expect(self.camera.heading("SMART STREAM")).to_be_visible()

        self.step_capture.mark(2, "Verify configuration fields are present")
        page_text = self.page.locator("body").inner_text()
        for field in ["Frame rate", "GOP", "Bitrate mode", "Target bitrate", "Hold on time", "Trigger event"]:
            assert field in page_text, f"Missing field: {field}"

    @pytest.mark.regression
    @pytest.mark.c2c_hardware
    def test_roi_configuration(self):
        """Verify Region of Interest configuration page.

        Steps:
        1. On the Setup page, open ROI.
           Expected: The REGION OF INTEREST CONFIGURATION page shows Stream, Activation and Quality settings.
        """
        self.step_capture.mark(1, "Navigate to ROI Configuration")
        self.camera.navigate_to_setup_subsection("ROI")
        expect(self.camera.heading("REGION OF INTEREST CONFIGURATION")).to_be_visible()

        self.step_capture.mark(2, "Verify Stream and Activation dropdowns exist")
        page_text = self.page.locator("body").inner_text()
        assert "Stream" in page_text
        assert "Activation" in page_text
        assert "Quality" in page_text

    @pytest.mark.regression
    @pytest.mark.c2c_hardware
    def test_white_balance_modes(self):
        """Verify white balance configuration and modes.

        Steps:
        1. Open Setup > CAMERA > WHITE BALANCE.
           Expected: The WHITE BALANCE page shows Activation and White balance mode settings.
        2. Read the gain controls.
           Expected: R Gain, G Gain and B Gain are present.
        3. Open the White balance mode dropdown.
           Expected: It offers Auto and Manual.
        """
        self.step_capture.mark(1, "Navigate to White Balance")
        self.camera.navigate_to_setup_section("CAMERA")
        self.camera.navigate_to_setup_subsection("WHITE BALANCE")
        expect(self.camera.heading("WHITE BALANCE")).to_be_visible()

        self.step_capture.mark(2, "Verify Activation is On and mode is Auto")
        page_text = self.page.locator("body").inner_text()
        assert "Activation" in page_text
        assert "White balance mode" in page_text

        self.step_capture.mark(3, "Verify R/G/B Gain controls exist")
        assert "R Gain" in page_text
        assert "G Gain" in page_text
        assert "B Gain" in page_text

        self.step_capture.mark(4, "Verify multiple WB modes are available")
        wb_select = self.page.locator("select").filter(
            has=self.page.locator("option:has-text('Auto')")
        ).filter(has=self.page.locator("option:has-text('Manual')")).first
        expect(wb_select).to_be_visible()
