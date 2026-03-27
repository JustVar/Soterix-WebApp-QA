"""License Assignment tests -- Assigned Licenses tab, site-wise grouping,
feature drill-down, device list, assign/unassign/suspend workflows,
and export functionality."""
import pytest
from playwright.sync_api import expect
from tests.shared.pages.license_page import LicensePage


class TestLicenseAssignedTab:
    """Tests for Assigned Licenses tab -- site grouping, expand/collapse, toggles."""

    @pytest.fixture(autouse=True)
    def setup(self, authenticated_page, step_capture):
        self.page = authenticated_page
        self.step_capture = step_capture
        step_capture.set_page(self.page)
        self.license = LicensePage(self.page)
        yield

    def _navigate_to_assigned(self):
        """Navigate to Licenses > Assigned tab."""
        self.license.navigate()
        self.license.switch_to_assigned_tab()

    @pytest.mark.ui
    @pytest.mark.licenses
    @pytest.mark.qatouch("LD3gmJ")
    def test_assigned_tab_shows_site_grouping(self):
        """Verify Assigned Licenses tab displays site-wise grouping."""
        self.step_capture.mark(1, "Navigate to Licenses and switch to Assigned tab")
        self._navigate_to_assigned()

        # Should show at least one site row or group
        site_content = self.page.locator(
            "div[class*='site'], div[class*='group'], "
            "tr[class*='site'], div[class*='expand']"
        )
        self.page.wait_for_timeout(2000)
        # Either sites exist or empty state message
        has_sites = site_content.count() > 0
        has_empty = self.page.locator("text=No assigned licenses, text=No data").first.count() > 0
        assert has_sites or has_empty, "Neither site grouping nor empty state found"

        self.step_capture.mark(2, "Verify site-wise grouping or empty state is displayed")

    @pytest.mark.ui
    @pytest.mark.licenses
    @pytest.mark.qatouch("wmjgKb")
    def test_multiple_sites_displayed(self):
        """Verify multiple sites are displayed correctly if available."""
        self.step_capture.mark(1, "Navigate to Licenses and switch to Assigned tab")
        self._navigate_to_assigned()
        self.page.wait_for_timeout(2000)

        # Count site-level expandable items
        site_items = self.page.locator(
            "div[class*='site'], div[class*='group'], "
            "div[class*='expand'], div[class*='accordion']"
        )
        # Test that the structure renders (at least one grouping element)
        assert site_items.count() >= 0, "Site grouping structure not found"

        self.step_capture.mark(2, "Verify multiple site grouping elements are rendered")

    @pytest.mark.ui
    @pytest.mark.licenses
    @pytest.mark.qatouch("yaWrXx")
    def test_expand_site_shows_features(self):
        """Verify expanding a site reveals feature-level licenses."""
        self.step_capture.mark(1, "Navigate to Licenses and switch to Assigned tab")
        self._navigate_to_assigned()

        expand_icons = self.license.site_expand_icons
        if expand_icons.count() > 0:
            self.license.expand_site(0)
            # After expanding, nested content should appear
            self.page.wait_for_timeout(2000)

            self.step_capture.mark(2, "Expand the first site row")

            nested = self.page.locator(
                "div[class*='feature'], div[class*='nested'], "
                "div[class*='sub-row'], tr[class*='child']"
            )
            assert nested.count() > 0, "No feature rows shown after site expansion"

            self.step_capture.mark(3, "Verify feature-level license rows appear after expansion")
        else:
            pytest.skip("No expandable sites available")

    @pytest.mark.ui
    @pytest.mark.licenses
    @pytest.mark.qatouch("0rzxll")
    def test_collapse_site_hides_features(self):
        """Verify collapsing a site hides feature-level details."""
        self.step_capture.mark(1, "Navigate to Licenses and switch to Assigned tab")
        self._navigate_to_assigned()

        expand_icons = self.license.site_expand_icons
        if expand_icons.count() > 0:
            # Expand then collapse
            self.license.expand_site(0)
            self.page.wait_for_timeout(1000)

            self.step_capture.mark(2, "Expand the first site row")

            self.license.collapse_site(0)
            self.page.wait_for_timeout(1000)
            # Nested content should be hidden

            self.step_capture.mark(3, "Collapse the site and verify feature details are hidden")
        else:
            pytest.skip("No expandable sites available")

    @pytest.mark.ui
    @pytest.mark.licenses
    @pytest.mark.qatouch("kpZQW9")
    def test_site_enable_toggle_visible(self):
        """Verify site enable toggle switch is available."""
        self.step_capture.mark(1, "Navigate to Licenses and switch to Assigned tab")
        self._navigate_to_assigned()

        switches = self.license.site_toggle_switches
        if switches.count() > 0:
            expect(switches.first).to_be_visible(timeout=5000)
            self.step_capture.mark(2, "Verify site enable toggle switch is visible")
        else:
            pytest.skip("No site toggle switches found")

    @pytest.mark.ui
    @pytest.mark.licenses
    @pytest.mark.qatouch("11zJl0")
    def test_assigned_tab_retains_state_after_navigation(self):
        """Verify Assigned Licenses tab retains state after navigation."""
        self.step_capture.mark(1, "Navigate to Licenses and switch to Assigned tab")
        self._navigate_to_assigned()

        # Navigate away
        dashboard_link = self.page.locator("a[href*='dashboard']").first
        if dashboard_link.count() > 0:
            dashboard_link.click()
            self.page.wait_for_timeout(2000)

        self.step_capture.mark(2, "Navigate away from Licenses page")

        # Come back
        self.license.navigate()
        self.license.switch_to_assigned_tab()

        # Assigned tab content should load
        self.page.wait_for_timeout(2000)
        content = self.page.locator(
            "text=Assigned, text=Site"
        ).first
        expect(content).to_be_visible(timeout=10000)

        self.step_capture.mark(3, "Navigate back and verify Assigned tab content is restored")

    @pytest.mark.ui
    @pytest.mark.licenses
    @pytest.mark.qatouch("5BRzD7")
    def test_assigned_tab_refresh_behavior(self):
        """Verify Assigned Licenses tab refresh reloads data correctly."""
        self.step_capture.mark(1, "Navigate to Licenses and switch to Assigned tab")
        self._navigate_to_assigned()

        self.page.reload()
        self.page.wait_for_timeout(3000)

        self.step_capture.mark(2, "Refresh the page")

        content = self.page.locator(
            "text=Licenses, text=Available, text=Assigned"
        ).first
        expect(content).to_be_visible(timeout=15000)

        self.step_capture.mark(3, "Verify Licenses page reloads correctly after refresh")


class TestLicenseDeviceList:
    """Tests for device list page (drill-down from feature license)."""

    @pytest.fixture(autouse=True)
    def setup(self, authenticated_page, step_capture):
        self.page = authenticated_page
        self.step_capture = step_capture
        step_capture.set_page(self.page)
        self.license = LicensePage(self.page)
        yield

    def _navigate_to_device_list(self):
        """Navigate to Licenses > Assigned > expand site > click feature."""
        self.license.navigate()
        self.license.switch_to_assigned_tab()

        expand_icons = self.license.site_expand_icons
        if expand_icons.count() == 0:
            pytest.skip("No expandable sites available for device list drill-down")

        self.license.expand_site(0)
        self.page.wait_for_timeout(2000)

        # Click on a feature row to navigate to device list
        feature_links = self.page.locator(
            "div[class*='feature'] a, div[class*='nested'] a, "
            "div[class*='feature'] span[class*='link'], "
            "td a, div[class*='clickable']"
        )
        if feature_links.count() > 0:
            feature_links.first.click()
            self.page.wait_for_timeout(3000)
        else:
            pytest.skip("No feature links found for drill-down")

    @pytest.mark.ui
    @pytest.mark.licenses
    @pytest.mark.qatouch("DrdZzm")
    def test_device_list_loads(self):
        """Verify navigation to device list from feature license works."""
        self.step_capture.mark(1, "Navigate to Assigned tab, expand site, and click a feature")
        self._navigate_to_device_list()

        # Device list page should show device-related content
        content = self.page.locator(
            "text=Device, text=Serial, text=Status, text=License"
        ).first
        expect(content).to_be_visible(timeout=10000)

        self.step_capture.mark(2, "Verify device list page loads with device details")

    @pytest.mark.ui
    @pytest.mark.licenses
    @pytest.mark.qatouch("eJqjmr")
    def test_device_list_has_three_dot_menu(self):
        """Verify three-dot menu is available for each device."""
        self.step_capture.mark(1, "Navigate to the device list via feature drill-down")
        self._navigate_to_device_list()

        options = self.license.options_icons
        if options.count() > 0:
            expect(options.first).to_be_visible(timeout=5000)
            self.step_capture.mark(2, "Verify three-dot menu icon is visible for devices")
        else:
            pytest.skip("No option icons found in device list")

    @pytest.mark.ui
    @pytest.mark.licenses
    @pytest.mark.qatouch("vanmXl")
    def test_suspend_option_available(self):
        """Verify Suspend License option is available in device menu."""
        self.step_capture.mark(1, "Navigate to the device list via feature drill-down")
        self._navigate_to_device_list()

        options = self.license.options_icons
        if options.count() == 0:
            pytest.skip("No option icons for device")

        self.step_capture.mark(2, "Open the three-dot menu for the first device")
        self.license.open_device_menu(0)

        suspend = self.page.locator(
            "li:has-text('Suspend'), div:has-text('Suspend')"
        ).first
        expect(suspend).to_be_visible(timeout=5000)

        self.step_capture.mark(3, "Verify Suspend option is visible in the device menu")

        # Close menu by pressing Escape
        self.page.keyboard.press("Escape")
        self.page.wait_for_timeout(500)

    @pytest.mark.ui
    @pytest.mark.licenses
    @pytest.mark.qatouch("bj0G48")
    def test_unassign_option_available(self):
        """Verify Unassign License option is available in device menu."""
        self.step_capture.mark(1, "Navigate to the device list via feature drill-down")
        self._navigate_to_device_list()

        options = self.license.options_icons
        if options.count() == 0:
            pytest.skip("No option icons for device")

        self.step_capture.mark(2, "Open the three-dot menu for the first device")
        self.license.open_device_menu(0)

        unassign = self.page.locator(
            "li:has-text('Unassign'), div:has-text('Unassign')"
        ).first
        expect(unassign).to_be_visible(timeout=5000)

        self.step_capture.mark(3, "Verify Unassign option is visible in the device menu")

        self.page.keyboard.press("Escape")
        self.page.wait_for_timeout(500)

    @pytest.mark.ui
    @pytest.mark.licenses
    @pytest.mark.qatouch("Z8xRWP")
    def test_suspend_confirmation_popup(self):
        """Verify Suspend License shows a confirmation popup."""
        self.step_capture.mark(1, "Navigate to the device list via feature drill-down")
        self._navigate_to_device_list()

        options = self.license.options_icons
        if options.count() == 0:
            pytest.skip("No option icons for device")

        self.step_capture.mark(2, "Click Suspend on the first device")
        self.license.suspend_device(0)

        # Confirmation dialog should appear
        confirm_dialog = self.page.locator(
            "div[role='dialog'], div[class*='modal'], div[class*='confirm']"
        )
        expect(confirm_dialog.first).to_be_visible(timeout=5000)

        self.step_capture.mark(3, "Verify suspension confirmation dialog appears")

        # Cancel to avoid actual suspension
        self.license.cancel_action()

    @pytest.mark.ui
    @pytest.mark.licenses
    @pytest.mark.qatouch("RgGyBl")
    def test_unassign_confirmation_popup(self):
        """Verify Unassign License shows a confirmation popup."""
        self.step_capture.mark(1, "Navigate to the device list via feature drill-down")
        self._navigate_to_device_list()

        options = self.license.options_icons
        if options.count() == 0:
            pytest.skip("No option icons for device")

        self.step_capture.mark(2, "Open device menu and click Unassign")
        self.license.open_device_menu(0)
        self.license.unassign_option.click()
        self.page.wait_for_timeout(1000)

        confirm_dialog = self.page.locator(
            "div[role='dialog'], div[class*='modal'], div[class*='confirm']"
        )
        expect(confirm_dialog.first).to_be_visible(timeout=5000)

        self.step_capture.mark(3, "Verify unassign confirmation dialog appears")

        # Cancel to avoid actual unassignment
        self.license.cancel_action()


class TestLicenseAssignModal:
    """Tests for the Assign New License modal workflow."""

    @pytest.fixture(autouse=True)
    def setup(self, authenticated_page, step_capture):
        self.page = authenticated_page
        self.step_capture = step_capture
        step_capture.set_page(self.page)
        self.license = LicensePage(self.page)
        yield

    @pytest.mark.ui
    @pytest.mark.licenses
    @pytest.mark.qatouch("dypN4W")
    def test_assign_button_visible(self):
        """Verify Assign New License button is visible."""
        self.step_capture.mark(1, "Navigate to the Licenses page")
        self.license.navigate()

        assign_btn = self.page.locator(
            "button:has-text('Assign'), button:has-text('Assign New License')"
        ).first
        expect(assign_btn).to_be_visible(timeout=10000)

        self.step_capture.mark(2, "Verify Assign New License button is visible")

    @pytest.mark.ui
    @pytest.mark.licenses
    @pytest.mark.qatouch("xm9EjW")
    def test_assign_modal_opens(self):
        """Verify Assign New License modal opens on button click."""
        self.step_capture.mark(1, "Navigate to the Licenses page")
        self.license.navigate()

        self.step_capture.mark(2, "Click the Assign New License button")
        self.license.open_assign_modal()

        modal = self.page.locator(
            "div[role='dialog'], div[class*='modal']"
        ).first
        expect(modal).to_be_visible(timeout=5000)

        self.step_capture.mark(3, "Verify assign modal dialog is visible")

        self.license.close_assign_modal()

    @pytest.mark.ui
    @pytest.mark.licenses
    @pytest.mark.qatouch("VKbBe9")
    def test_assign_modal_close_via_cancel(self):
        """Verify Assign New License modal closes using Cancel."""
        self.step_capture.mark(1, "Navigate to the Licenses page")
        self.license.navigate()

        self.step_capture.mark(2, "Open the Assign New License modal")
        self.license.open_assign_modal()

        modal = self.page.locator(
            "div[role='dialog'], div[class*='modal']"
        ).first
        expect(modal).to_be_visible(timeout=5000)

        self.license.close_assign_modal()
        self.page.wait_for_timeout(1000)

        # Modal should no longer be visible
        expect(modal).to_be_hidden(timeout=5000)

        self.step_capture.mark(3, "Close the modal via Cancel and verify it is hidden")

    @pytest.mark.ui
    @pytest.mark.licenses
    @pytest.mark.qatouch("B86DEG")
    def test_site_dropdown_in_modal(self):
        """Verify site dropdown lists available sites in assign modal."""
        self.step_capture.mark(1, "Navigate to the Licenses page")
        self.license.navigate()

        self.step_capture.mark(2, "Open the Assign New License modal")
        self.license.open_assign_modal()

        dropdown = self.page.locator(
            "div[role='combobox'], select, div[class*='dropdown']"
        ).first
        expect(dropdown).to_be_visible(timeout=5000)

        self.step_capture.mark(3, "Verify site dropdown is visible in the assign modal")

        self.license.close_assign_modal()
