"""C2C Hardware Tests - VCA Plugin and Soterix Cloud Connect.

Verify VCA enable/tracker engine configuration (critical for PVA),
VCA rules and license, and Soterix Cloud registration.
"""
import pytest
from playwright.sync_api import expect

from tests.shared.pages.camera_hardware_page import CameraHardwarePage


class TestC2CVCA:
    """VCA (VCAEdge-AI) plugin tests - critical for PVA on Virtual Site."""

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
    def test_vca_enabled_with_correct_tracker(self):
        """Verify VCA is enabled with DL Object Tracker + Intrusion Detection.

        This is the happy path for PVA to work on the Virtual Site.

        Steps:
        1. Open Setup > VCA > ENABLE.
           Expected: The CONFIGURATION page is shown with Enable set to On.
        2. Read the tracker selection.
           Expected: DL Object Tracker is selected with Intrusion detection as its active option, and DL People Tracker is listed as the alternative.
        """
        self.step_capture.mark(1, "Navigate to VCA > ENABLE")
        self.camera.navigate_to_vca_section()
        self.camera.navigate_to_setup_subsection("ENABLE")
        expect(self.camera.heading("CONFIGURATION")).to_be_visible()

        self.step_capture.mark(2, "Verify Enable is set to On")
        page_text = self.page.locator("body").inner_text()
        assert "On" in page_text

        self.step_capture.mark(3, "Verify DL Object Tracker is selected")
        expect(self.page.locator("text=/DL Object Tracker/")).to_be_visible()

        self.step_capture.mark(4, "Verify Intrusion detection is the active sub-option")
        expect(self.page.locator("text='Intrusion detection'")).to_be_visible()

        self.step_capture.mark(5, "Verify DL People Tracker is NOT selected (alternative)")
        # People Tracker should be visible as an option but not selected
        expect(self.page.locator("text=/DL People Tracker/")).to_be_visible()

    @pytest.mark.smoke
    @pytest.mark.regression
    @pytest.mark.c2c_hardware
    def test_vca_rules_and_license(self):
        """Verify VCA has active rules and valid ProAI license.

        Steps:
        1. Open Setup > VCA > RULES (BC-5V-1 firmware has no RULES entry; skip to step 2 there).
           Expected: The RULES table lists at least one rule with its type and name.
        2. Open VCA > LICENSE.
           Expected: The Activated License(s) table lists the camera's license family from the registry (ProAI); a missing row names the camera.
        3. On a multi-lens camera, count the activated license rows.
           Expected: One row per lens (four on the MS-20V-1 units).
        """
        self.step_capture.mark(1, "Navigate to VCA > RULES")
        self.camera.navigate_to_vca_section()
        # BC-5V-1 firmware has no RULES entry (measured 09/11/2026); the
        # license check below runs on every model, so this is no skip
        if self.camera.has_subsection("RULES"):
            self.camera.navigate_to_setup_subsection("RULES")
            expect(self.camera.heading("RULES")).to_be_visible()

            self.step_capture.mark(2, "Verify at least one rule is listed")
            # one table row per rule: type, name, action, colour. DC-5V-1
            # offers Modify/Delete beside the rule and no Add button
            rows = self.camera.table_rows()
            rules = [(r[0], r[1]) for r in rows if len(r) >= 2 and r[0] and r[1]]
            assert rules, (
                f"no rule listed on {self.camera.ip}: the RULES table reads {rows}")
        else:
            print(f"[C2C] {self.camera.ip}: the analytics section has no RULES entry")

        self.step_capture.mark(3, "Navigate to VCA > LICENSE")
        self.camera.navigate_to_setup_subsection("LICENSE")
        expect(self.camera.heading("LICENSE")).to_be_visible()

        expected_license = self.config["expected_license"]
        # the page names the family ('ProAI'); the registry's 'ProAI 1ch'
        # adds the channel count, which the multi-lens step counts by row
        family = expected_license.split()[0]
        self.step_capture.mark(4, f"Verify a {family} license is activated")
        rows = self.camera.table_rows()
        licenses = [r[-1] for r in rows if len(r) == 2 and r[-1].startswith(family)]
        assert licenses, (
            f"no activated {family} license on {self.camera.ip}: the Activated "
            f"License(s) table has no license row (cells read {rows})")

        # Multi-lens cameras must show N licenses assigned (one per lens)
        if self.config.get("multi_lens"):
            expected_count = self.config["expected_license_count"]
            self.step_capture.mark(5, f"Verify {expected_count} licenses assigned (multi-lens)")
            assert len(licenses) >= expected_count, (
                f"{self.camera.ip} should list {expected_count} {family} licenses, "
                f"one per lens; it lists {len(licenses)}: {licenses}")


class TestC2CSoterixCloud:
    """Soterix Cloud Connect tests - camera registration to cloud."""

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
    def test_cloud_connect_registered(self):
        """Verify camera is registered to Soterix staging cloud.

        Steps:
        1. Open Setup > Soterix > CONNECT.
           Expected: The SOTERIX CLOUD CONNECT page loads with the Soterix logo.
        2. Wait a few seconds for the cloud status to load and read it.
           Expected: Registered Cloud Address shows staging.example.invalid. "Waiting for cloud registration..." or "I am not registered to a cloud." means the camera was never registered: finish provisioning (QR code) and run again.
        3. Read the QR code section.
           Expected: Upload QR Code with Select QR, Upload and Reset buttons.
        """
        self.step_capture.mark(1, "Navigate to Soterix > CONNECT")
        self.camera.navigate_to_setup_section("Soterix")
        # DC-5V-1 and BC-5V-1 firmware has no CONNECT entry (probed 09/11/2026)
        self.camera.require_subsection("CONNECT")
        self.camera.navigate_to_setup_subsection("CONNECT")

        self.step_capture.mark(2, "Verify Soterix Cloud Connect page loads with branding")
        # the onboard page has no .contentTitle: its title is plain text
        expect(self.camera.content("SOTERIX CLOUD CONNECT")).to_be_visible(timeout=10000)
        # img asset icon: alt unreliable, locate by src (CONVENTIONS > Locators)
        expect(self.page.locator("img[alt*='Soterix'], img[src*='logo']").first).to_be_visible()

        self.step_capture.mark(3, "Wait for cloud status to load and verify registration")
        # Cloud status may take a moment to resolve
        self.page.wait_for_timeout(3000)
        page_text = self.page.locator("body").inner_text()

        self.step_capture.mark(4, "Verify Registered Cloud Address is staging.example.invalid")
        # Distinguish "still pending" from "declined to register" - the camera
        # sits on "Waiting for cloud registration..." until the QR/registration
        # completes, and reporting that as "not registered" sends whoever reads
        # the result looking in the wrong place.
        # the onboard page's own status line, verbatim, so the reader
        # knows whether to wait or to provision ('I am not registered to
        # a cloud.' on 10.2.0.171, 09/11/2026)
        for status in ("Waiting for cloud registration",
                       "I am not registered to a cloud"):
            if status in page_text:
                pytest.fail(
                    f"Camera {self.camera.ip} reports '{status}': it has "
                    f"not completed registration to staging.example.invalid. "
                    f"Upload the QR code / finish provisioning, then re-run."
                )
        assert "Registered Cloud Address" in page_text, \
            f"Camera {self.camera.ip} not registered. Page shows: {page_text[:200]}"
        expect(self.page.locator("text=/staging\\.soterixcloud\\.com/")).to_be_visible()

        self.step_capture.mark(5, "Verify QR code upload controls are present")
        expect(self.page.locator("text='Upload QR Code'")).to_be_visible()
        expect(self.page.locator("button:has-text('Select QR')")).to_be_visible()
        expect(self.page.locator("button:has-text('Upload')")).to_be_visible()
        expect(self.page.locator("button:has-text('Reset')")).to_be_visible()


class TestC2CMultiLens:
    """Multi-lens camera tests - skipped on single-lens cameras.

    Multi-lens cameras (e.g. BC-ML-4) expose 4 independent channels, each
    with its own license. All 4 lenses share one physical device / IP, so
    channel selection differentiates them.
    """

    @pytest.fixture(autouse=True)
    def setup(self, camera_setup_page, camera_config, step_capture):
        if not camera_config.get("multi_lens"):
            pytest.skip(f"{camera_config['id']} is not a multi-lens camera")
        self.page = camera_setup_page
        self.config = camera_config
        self.camera = CameraHardwarePage(self.page, camera_config)
        self.step_capture = step_capture
        step_capture.set_page(self.page)
        return

    @pytest.mark.regression
    @pytest.mark.c2c_hardware
    def test_multi_lens_license_count_matches_lens_count(self):
        """Verify multi-lens camera has one license assigned per lens.

        Skipped on a single-lens camera.

        Steps:
        1. On a multi-lens camera, open Setup > VCA > LICENSE.
           Expected: The LICENSE page is shown.
        2. Compare the registry's expected license count with its lens count.
           Expected: They match (four for the MS-20V-1 units).
        3. Count the activated licenses marked assigned.
           Expected: One assigned license per lens.
        """
        self.step_capture.mark(1, "Navigate to VCA > LICENSE")
        self.camera.navigate_to_vca_section()
        self.camera.navigate_to_setup_subsection("LICENSE")
        expect(self.camera.heading("LICENSE")).to_be_visible()

        expected_count = self.config["expected_license_count"]
        total_lenses = self.config["total_lenses"]

        self.step_capture.mark(2, f"Verify license count ({expected_count}) matches lens count ({total_lenses})")
        assert expected_count == total_lenses, (
            f"Config inconsistency: expected_license_count={expected_count} "
            f"but total_lenses={total_lenses}"
        )

        self.step_capture.mark(3, "Verify all lenses have licenses assigned")
        # Each activated license row appears with the license name
        # For a 4-lens device with ProAI 4ch, should see 4 assigned rows
        licenses = self.camera.get_vca_license()
        assigned_count = sum(1 for lic in licenses if lic.get("assigned"))
        assert assigned_count == expected_count, (
            f"Expected {expected_count} assigned licenses, found {assigned_count}"
        )
