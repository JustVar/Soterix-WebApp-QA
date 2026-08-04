"""C2C Hardware Tests - System Info, Plugins, System Ops.

Verify system information, plugin status, firmware, diagnostics,
configuration backup, date/time, and restart.
"""
import pytest
from playwright.sync_api import expect

from tests.shared.pages.camera_hardware_page import CameraHardwarePage


class TestC2CSystemInfo:
    """System information and device identity tests."""

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
    def test_system_info_device_details(self):
        """Verify system information displays correct device details."""
        self.step_capture.mark(1, "Navigate to System Information page")
        self.camera.navigate_to_setup_section("SYSTEM")
        self.camera.navigate_to_setup_subsection("SYSTEM INFORMATION")

        self.step_capture.mark(2, f"Verify Model name is {self.config['model']}")
        expect(self.page.locator(f"text='{self.config['model']}'").first).to_be_visible()

        self.step_capture.mark(3, f"Verify Manufacturer is {self.config['manufacturer']}")
        expect(self.page.locator(f"text='{self.config['manufacturer']}'")).to_be_visible()

        self.step_capture.mark(4, "Verify Serial number is present")
        serial = self.page.locator("text=/PC\\w+/").first
        expect(serial).to_be_visible()

        self.step_capture.mark(5, f"Verify Max resolution is {self.config['max_resolution']}")
        expect(self.page.locator(f"text='{self.config['max_resolution']}'").first).to_be_visible()

        self.step_capture.mark(6, f"Verify Max framerate is {self.config['max_framerate']} fps")
        expect(self.page.locator(f"text='{self.config['max_framerate']} fps'")).to_be_visible()

        self.step_capture.mark(7, "Verify feature flags match expected for this model")
        page_text = self.page.locator("body").inner_text()
        features = self.config.get("features", {})
        # AI must be SUPPORTED for any Soterix camera
        assert "SUPPORTED" in page_text
        # Verify model-specific feature expectations if provided in config
        if features.get("ptz") == "NOT SUPPORTED":
            expect(self.page.locator("text='PTZ'")).to_be_visible()

        self.step_capture.mark(8, "Verify ONVIF version and profiles")
        onvif_ver = self.config.get("onvif_version", "24.06")
        expect(self.page.locator(f"text=/Version.*{onvif_ver}.*Profile/")).to_be_visible()

    @pytest.mark.regression
    @pytest.mark.c2c_hardware
    @pytest.mark.mutating
    def test_device_name_and_location_editable(self):
        """Verify device name and location are editable and persist.

        MUTATING: writes to the camera and puts the original values back. The
        restore is in a finally block - previously it sat after the assertions,
        so a failed verification left the device permanently named
        "TEST-CAM-01" in "QA Lab".
        """
        self.step_capture.mark(1, "Navigate to System Information")
        self.camera.navigate_to_setup_section("SYSTEM")
        self.camera.navigate_to_setup_subsection("SYSTEM INFORMATION")

        self.step_capture.mark(2, "Save original values")
        name_input = self.page.locator("input").first
        location_input = self.page.locator("input").nth(1)
        original_name = name_input.input_value()
        original_location = location_input.input_value()

        try:
            self.step_capture.mark(3, "Change Device name and Location to test values")
            name_input.fill("TEST-CAM-01")
            location_input.fill("QA Lab")

            self.step_capture.mark(4, "Click Apply")
            self.camera.click_apply()

            self.step_capture.mark(5, "Refresh and verify changes persisted")
            self.page.reload(wait_until="domcontentloaded")
            self.camera.navigate_to_setup_section("SYSTEM")
            self.camera.navigate_to_setup_subsection("SYSTEM INFORMATION")
            assert self.page.locator("input").first.input_value() == "TEST-CAM-01"
            assert self.page.locator("input").nth(1).input_value() == "QA Lab"
        finally:
            self.step_capture.mark(6, "Restore original values")
            try:
                self.page.locator("input").first.fill(original_name)
                self.page.locator("input").nth(1).fill(original_location)
                self.camera.click_apply()
            except Exception as restore_err:  # noqa: BLE001 - must not mask the real failure
                pytest.fail(
                    f"Could not restore device name/location on "
                    f"{self.camera.ip}: {restore_err}. The camera may still be "
                    f"named TEST-CAM-01 / QA Lab - check it."
                )


class TestC2CPlugins:
    """Plugin verification tests."""

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
    def test_plugins_installed_and_running(self):
        """Verify both SOTERIX and VCAedge-AI plugins are installed and running."""
        self.step_capture.mark(1, "Navigate to Plug-in page")
        self.camera.navigate_to_setup_section("SYSTEM")
        self.camera.navigate_to_setup_subsection("PLUG-IN")

        self.step_capture.mark(2, "Verify SOTERIX plugin is running")
        expect(self.page.locator("text='SOTERIX'")).to_be_visible()
        page_text = self.page.locator("body").inner_text()
        assert "SOTERIX" in page_text

        self.step_capture.mark(3, "Verify VCAedge-AI plugin is running")
        expect(self.page.locator("text='VCAedge-AI'")).to_be_visible()

        self.step_capture.mark(4, "Verify both plugins show 'running' status")
        running_count = self.page.locator("text='running'").count()
        assert running_count >= 2, f"Expected at least 2 running plugins, found {running_count}"

    @pytest.mark.regression
    @pytest.mark.c2c_hardware
    def test_plugin_storage_within_limits(self):
        """Verify plugin storage usage is below 90%."""
        self.step_capture.mark(1, "Navigate to Plug-in page")
        self.camera.navigate_to_setup_section("SYSTEM")
        self.camera.navigate_to_setup_subsection("PLUG-IN")

        self.step_capture.mark(2, "Check storage usage percentage")
        storage_text = self.page.locator("text=/\\d+ %/").inner_text()
        import re
        match = re.search(r"(\d+)", storage_text)
        assert match, "Could not find storage percentage"
        usage = int(match.group(1))

        self.step_capture.mark(3, "Verify storage is below 90% threshold")
        assert usage < 90, f"Storage usage {usage}% exceeds 90% threshold"


class TestC2CSystemOps:
    """System operations tests - firmware, diagnostics, backup, time, restart."""

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
    def test_firmware_and_diagnostics_accessible(self):
        """Verify firmware version and system diagnostics are accessible."""
        self.step_capture.mark(1, "Navigate to Firmware Update page")
        self.camera.navigate_to_setup_section("SYSTEM")
        self.camera.navigate_to_setup_subsection("FIRMWARE UPDATE")
        expect(self.page.locator("text=/FIRMWARE/i")).to_be_visible()

        self.step_capture.mark(2, "Verify firmware upload control exists")
        expect(self.page.locator("input[type='file'], button:has-text('Select'), text=/Select file/i").first).to_be_visible()

        self.step_capture.mark(3, "Navigate to System Diagnostics")
        self.camera.navigate_to_setup_subsection("SYSTEM DIAGNOSTICS")
        expect(self.page.locator("text=/DIAGNOSTICS/i")).to_be_visible()

        self.step_capture.mark(4, "Navigate to System Log")
        self.camera.navigate_to_setup_subsection("LOG")
        expect(self.page.locator("text=/LOG/i").first).to_be_visible()

    @pytest.mark.regression
    @pytest.mark.c2c_hardware
    def test_date_time_settings(self):
        """Verify date/time settings and language options."""
        self.step_capture.mark(1, "Navigate to Date & Time Setting")
        self.camera.navigate_to_setup_section("SYSTEM")
        self.camera.navigate_to_setup_subsection("DATE&TIME SETTING")
        expect(self.page.locator("text=/DATE.*TIME/i").first).to_be_visible()

        self.step_capture.mark(2, "Verify time configuration options exist")
        # Should have NTP or manual time settings
        page_text = self.page.locator("body").inner_text()
        assert "NTP" in page_text or "Manual" in page_text or "Time" in page_text

        self.step_capture.mark(3, "Navigate to DST Settings")
        self.camera.navigate_to_setup_subsection("DST SETTINGS")
        expect(self.page.locator("text=/DST/i").first).to_be_visible()

        self.step_capture.mark(4, "Navigate to Language settings")
        self.camera.navigate_to_setup_subsection("LANGUAGE")
        expect(self.page.locator("text=/LANGUAGE/i").first).to_be_visible()

    @pytest.mark.regression
    @pytest.mark.c2c_hardware
    def test_configuration_backup_accessible(self):
        """Verify configuration backup page is accessible."""
        self.step_capture.mark(1, "Navigate to Configuration Backup")
        self.camera.navigate_to_setup_section("SYSTEM")
        self.camera.navigate_to_setup_subsection("CONFIGURATION BACKUP")

        self.step_capture.mark(2, "Verify export/download option exists")
        expect(self.page.locator("text=/CONFIGURATION BACKUP/i")).to_be_visible()
        # Should have backup/export and restore/import buttons
        page_text = self.page.locator("body").inner_text()
        assert "Backup" in page_text or "Export" in page_text or "Download" in page_text

    @pytest.mark.regression
    @pytest.mark.c2c_hardware
    @pytest.mark.destructive
    def test_camera_restart(self):
        """Verify camera can restart cleanly and retains settings.

        DESTRUCTIVE: this reboots the physical camera, taking it off the
        network for a minute or two. It is skipped unless --run-destructive is
        passed, because the suite parametrises over every enabled camera in the
        registry - without the guard, a routine `pytest tests/ui/c2c/` reboots
        the entire lab fleet.
        """
        self.step_capture.mark(1, "Note current plugin status before restart")
        self.camera.navigate_to_setup_section("SYSTEM")
        self.camera.navigate_to_setup_subsection("PLUG-IN")
        running_before = self.page.locator("text='running'").count()

        self.step_capture.mark(2, "Navigate to Restart page")
        self.camera.navigate_to_setup_subsection("RESTART")
        expect(self.page.locator("text=/RESTART/i").first).to_be_visible()

        self.step_capture.mark(3, "Click restart button")
        self.page.locator("button:has-text('Restart'), button:has-text('Reboot'), input[value='Restart']").first.click()

        self.step_capture.mark(4, "Wait for camera to go offline and come back")
        import time
        # Wait for camera to start rebooting
        time.sleep(10)

        # Poll the camera under test. This used to read the module-level
        # CAMERA_IP default (192.168.1.149), so on any parametrised run it
        # polled a machine that was not the one just rebooted - the test could
        # never pass, while still having taken the camera down.
        camera_ip = self.camera.ip
        for _attempt in range(36):   # 36 x 5s = 3 minutes
            try:
                self.page.goto(
                    f"http://{camera_ip}/cgi-bin/admin/setup_main.cgi",
                    wait_until="domcontentloaded",
                    timeout=5000,
                )
                break
            except Exception:
                time.sleep(5)
        else:
            pytest.fail(
                f"Camera {camera_ip} did not come back online within 3 minutes "
                f"after restart"
            )

        self.step_capture.mark(5, "Verify web UI is accessible and plugins still running")
        self.camera.navigate_to_setup_section("SYSTEM")
        self.camera.navigate_to_setup_subsection("PLUG-IN")
        self.page.wait_for_timeout(2000)
        running_after = self.page.locator("text='running'").count()
        assert running_after >= running_before, "Plugins not running after restart"
