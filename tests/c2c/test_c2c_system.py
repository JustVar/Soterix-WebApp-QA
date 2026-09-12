"""C2C Hardware Tests - System Info, Plugins, System Ops.

Verify system information, plugin status, firmware, diagnostics,
configuration backup, date/time, and restart.
"""
import re

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
        """Verify system information displays correct device details.

        Steps:
        1. Open Setup > SYSTEM > SYSTEM INFORMATION.
           Expected: Model name and Manufacturer match the registry entry for this camera, and a serial number starting with PC is shown.
        2. Read the video capabilities.
           Expected: Max resolution and Max framerate (fps) match the registry entry.
        3. Read the feature list.
           Expected: AI is SUPPORTED, and PTZ is listed for models the registry marks as not supporting it.
        4. Read the ONVIF line.
           Expected: It shows the ONVIF version from the registry (24.06 unless set) with its profiles.
        """
        self.step_capture.mark(1, "Navigate to System Information page")
        self.camera.navigate_to_setup_section("SYSTEM")
        self.camera.navigate_to_setup_subsection("SYSTEM INFORMATION")

        self.step_capture.mark(2, f"Verify Model name is {self.config['model']}")
        expect(self.page.locator(f"text='{self.config['model']}'").first).to_be_visible()

        self.step_capture.mark(3, f"Verify Manufacturer is {self.config['manufacturer']}")
        expect(self.page.locator(f"text='{self.config['manufacturer']}'")).to_be_visible()

        # the serial is the last part of the registry id (q300c5b44, pc00c5552);
        # the old /PC\w+/ pattern only fitted the BC and FC units
        serial = self.config["id"].rsplit("-", 1)[-1].upper()
        self.step_capture.mark(4, f"Verify Serial number {serial} is shown")
        expect(self.page.locator("#tabs").get_by_text(serial, exact=True)).to_be_visible()

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

        Steps:
        1. Open Setup > SYSTEM > SYSTEM INFORMATION and note the Device name and Location.
           Expected: Both fields are editable.
        2. Change Device name to TEST-CAM-01 and Location to QA Lab, then click Apply.
           Expected: The change is accepted.
        3. Refresh the page and reopen SYSTEM > SYSTEM INFORMATION.
           Expected: Device name reads TEST-CAM-01 and Location reads QA Lab.
        4. Put the original name and location back and click Apply.
           Expected: The original values are restored (the test restores them even when a step fails).
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
        """Verify both SOTERIX and VCAedge-AI plugins are installed and running.

        Steps:
        1. Open Setup > SYSTEM > PLUG-IN.
           Expected: The SOTERIX and VCAedge-AI plugins are listed.
        2. Read each plugin's status.
           Expected: Every listed plugin shows running; a stopped one is named in the failure.
        """
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
        # each plug-in row by name and status, so a stopped one is named
        # (SOTERIX 1.5.1 'stopped' beside a running VCAedge-AI on
        # 10.2.0.129, 09/11/2026)
        rows = self.camera.table_rows()
        plugins = {r[0]: r[-1] for r in rows if len(r) >= 3 and r[0]}
        assert plugins, f"no plug-in rows on {self.camera.ip}: the tables read {rows}"
        stopped = [f"{name} {status}" for name, status in plugins.items() if status != "running"]
        assert not stopped, (
            f"plug-ins not running on {self.camera.ip}: {stopped} (the table reads {plugins})")

    @pytest.mark.regression
    @pytest.mark.c2c_hardware
    def test_plugin_storage_within_limits(self):
        """Verify plugin storage usage is below 90%.

        Steps:
        1. Open Setup > SYSTEM > PLUG-IN and read the storage usage.
           Expected: A usage percentage is shown.
        2. Compare it with the limit.
           Expected: Usage is below 90%.
        """
        self.step_capture.mark(1, "Navigate to Plug-in page")
        self.camera.navigate_to_setup_section("SYSTEM")
        self.camera.navigate_to_setup_subsection("PLUG-IN")

        self.step_capture.mark(2, "Check storage usage percentage")
        import re
        page_text = " ".join(self.page.locator("#tabs").inner_text().split())
        match = re.search(r"(\d+)\s*%", page_text)
        assert match, f"The Plug-in page shows no storage percentage; it reads: {page_text[:200]!r}"
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
        """Verify firmware version and system diagnostics are accessible.

        Steps:
        1. Open Setup > SYSTEM > FIRMWARE UPDATE.
           Expected: The firmware page shows the running firmware version as a dated build (for example 2025.06.30_A20.3.3) and a control to select a firmware file.
        2. Open SYSTEM > SYSTEM DIAGNOSTICS.
           Expected: The diagnostics page is shown.
        3. Open SYSTEM > LOG.
           Expected: The system log page is shown.
        """
        self.step_capture.mark(1, "Navigate to Firmware Update page")
        self.camera.navigate_to_setup_section("SYSTEM")
        self.camera.navigate_to_setup_subsection("FIRMWARE UPDATE")
        expect(self.camera.heading("FIRMWARE UPDATE")).to_be_visible()

        self.step_capture.mark(2, "Verify the running version and the upload control")
        # the running firmware version is a dated build string
        # (2025.06.30_A20.3.3 on BC-5V-1, 09/11/2026)
        version = self.camera.content(re.compile(r"\d{4}\.\d{2}\.\d{2}_\w+"))
        expect(version).to_have_text(re.compile(r"^\s*\d{4}\.\d{2}\.\d{2}_\w+"))
        # one selector engine per locator: a CSS list cannot carry text=
        expect(self.page.locator("#tabs input[type='file']")).to_be_visible()

        self.step_capture.mark(3, "Navigate to System Diagnostics")
        self.camera.navigate_to_setup_subsection("SYSTEM DIAGNOSTICS")
        expect(self.camera.heading("SYSTEM DIAGNOSTICS")).to_be_visible()

        self.step_capture.mark(4, "Navigate to System Log")
        self.camera.navigate_to_setup_subsection("LOG")
        expect(self.camera.heading("SYSTEM LOG")).to_be_visible()

    @pytest.mark.regression
    @pytest.mark.c2c_hardware
    def test_date_time_settings(self):
        """Verify date/time settings and language options.

        Steps:
        1. Open Setup > SYSTEM > DATE&TIME SETTING.
           Expected: The date and time page shows the time settings (NTP or manual).
        2. Open SYSTEM > DST SETTINGS.
           Expected: The DST page is shown.
        3. Open SYSTEM > LANGUAGE.
           Expected: The language page is shown.
        """
        self.step_capture.mark(1, "Navigate to Date & Time Setting")
        self.camera.navigate_to_setup_section("SYSTEM")
        self.camera.navigate_to_setup_subsection("DATE&TIME SETTING")
        expect(self.camera.heading("DATE&TIME SETTING")).to_be_visible()

        self.step_capture.mark(2, "Verify time configuration options exist")
        # Should have NTP or manual time settings
        page_text = self.page.locator("body").inner_text()
        assert "NTP" in page_text or "Manual" in page_text or "Time" in page_text

        self.step_capture.mark(3, "Navigate to DST Settings")
        self.camera.navigate_to_setup_subsection("DST SETTINGS")
        expect(self.camera.heading("DST SETTINGS")).to_be_visible()

        self.step_capture.mark(4, "Navigate to Language settings")
        self.camera.navigate_to_setup_subsection("LANGUAGE")
        expect(self.camera.heading("LANGUAGE")).to_be_visible()

    @pytest.mark.regression
    @pytest.mark.c2c_hardware
    def test_configuration_backup_accessible(self):
        """Verify configuration backup page is accessible.

        Steps:
        1. Open Setup > SYSTEM > CONFIGURATION BACKUP.
           Expected: The CONFIGURATION BACKUP page offers a backup (export or download) option.
        """
        self.step_capture.mark(1, "Navigate to Configuration Backup")
        self.camera.navigate_to_setup_section("SYSTEM")
        self.camera.navigate_to_setup_subsection("CONFIGURATION BACKUP")

        self.step_capture.mark(2, "Verify export/download option exists")
        expect(self.camera.heading("CONFIGURATION BACKUP")).to_be_visible()
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
        registry - without the guard, a routine `pytest tests/c2c/` reboots
        the entire lab fleet.

        Steps:
        1. Open Setup > SYSTEM > PLUG-IN and note how many plugins show running.
           Expected: The count is known for the check after the restart.
        2. Open SYSTEM > RESTART and click Restart.
           Expected: The camera goes offline.
        3. Wait for the camera to come back (up to 3 minutes).
           Expected: The setup page answers again.
        4. Open SYSTEM > PLUG-IN again.
           Expected: At least as many plugins show running as before the restart.
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
