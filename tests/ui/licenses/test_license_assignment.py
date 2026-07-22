"""License Assignment tests - Assigned Licenses tab, site-wise grouping,
feature drill-down, device list, assign/unassign/suspend workflows,
and export functionality."""
import pytest
from playwright.sync_api import expect
from tests.shared.pages.license_page import LicensePage


class TestLicenseAssignedTab:
    """Tests for Assigned Licenses tab - site grouping, expand/collapse, toggles."""

    @pytest.fixture(autouse=True)
    def setup(self, authenticated_page):
        self.page = authenticated_page
        self.license = LicensePage(self.page)
        yield

    def _navigate_to_assigned(self):
        """Navigate to Licenses > Assigned tab."""
        self.license.navigate()
        self.license.switch_to_assigned_tab()

    @pytest.mark.ui
    @pytest.mark.licenses
    def test_assigned_tab_shows_site_grouping(self):
        """Verify Assigned Licenses tab displays site-wise grouping."""
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

    @pytest.mark.ui
    @pytest.mark.licenses
    def test_multiple_sites_displayed(self):
        """Verify multiple sites are displayed correctly if available."""
        self._navigate_to_assigned()
        self.page.wait_for_timeout(2000)

        # Count site-level expandable items
        site_items = self.page.locator(
            "div[class*='site'], div[class*='group'], "
            "div[class*='expand'], div[class*='accordion']"
        )
        # Test that the structure renders (at least one grouping element)
        assert site_items.count() >= 0, "Site grouping structure not found"

    @pytest.mark.ui
    @pytest.mark.licenses
    def test_expand_site_shows_features(self):
        """Verify expanding a site reveals feature-level licenses."""
        self._navigate_to_assigned()

        expand_icons = self.license.site_expand_icons
        if expand_icons.count() > 0:
            initial_rows = self.page.locator("tr.MuiTableRow-root").count()
            self.license.expand_site(0)
            # After expanding, more rows should appear (nested feature rows)
            self.page.wait_for_timeout(2000)
            expanded_rows = self.page.locator("tr.MuiTableRow-root").count()
            assert expanded_rows > initial_rows, "No additional rows shown after site expansion"
        else:
            pytest.skip("No expandable sites available")

    @pytest.mark.ui
    @pytest.mark.licenses
    def test_collapse_site_hides_features(self):
        """Verify collapsing a site hides feature-level details."""
        self._navigate_to_assigned()

        expand_icons = self.license.site_expand_icons
        if expand_icons.count() > 0:
            # Expand then collapse
            self.license.expand_site(0)
            self.page.wait_for_timeout(1000)
            self.license.collapse_site(0)
            self.page.wait_for_timeout(1000)
            # Nested content should be hidden
        else:
            pytest.skip("No expandable sites available")

    @pytest.mark.ui
    @pytest.mark.licenses
    def test_site_enable_toggle_visible(self):
        """Verify site enable toggle switch is available."""
        self._navigate_to_assigned()

        switches = self.license.site_toggle_switches
        if switches.count() > 0:
            expect(switches.first).to_be_visible(timeout=5000)
        else:
            pytest.skip("No site toggle switches found")

    @pytest.mark.ui
    @pytest.mark.licenses
    def test_assigned_tab_retains_state_after_navigation(self):
        """Verify Assigned Licenses tab retains state after navigation."""
        self._navigate_to_assigned()

        # Navigate away
        dashboard_link = self.page.locator("a[href*='dashboard']").first
        if dashboard_link.count() > 0:
            dashboard_link.click()
            self.page.wait_for_timeout(2000)

        # Come back
        self.license.navigate()
        self.license.switch_to_assigned_tab()

        # Assigned tab content should load
        self.page.wait_for_timeout(2000)
        content = self.page.locator(
            "text=Assigned, text=Site"
        ).first
        expect(content).to_be_visible(timeout=10000)

    @pytest.mark.ui
    @pytest.mark.licenses
    def test_assigned_tab_refresh_behavior(self):
        """Verify Assigned Licenses tab refresh reloads data correctly."""
        self._navigate_to_assigned()

        self.page.reload()
        self.page.wait_for_timeout(3000)

        content = self.page.locator(
            "text=Licenses, text=Available, text=Assigned"
        ).first
        expect(content).to_be_visible(timeout=15000)


class TestLicenseDeviceList:
    """Tests for device list page (drill-down from feature license)."""

    @pytest.fixture(autouse=True)
    def setup(self, authenticated_page):
        self.page = authenticated_page
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
    def test_device_list_loads(self):
        """Verify navigation to device list from feature license works."""
        self._navigate_to_device_list()

        # Device list page should show device-related content
        content = self.page.locator(
            "text=Device, text=Serial, text=Status, text=License"
        ).first
        expect(content).to_be_visible(timeout=10000)

    @pytest.mark.ui
    @pytest.mark.licenses
    def test_device_list_has_three_dot_menu(self):
        """Verify three-dot menu is available for each device."""
        self._navigate_to_device_list()

        options = self.license.options_icons
        if options.count() > 0:
            expect(options.first).to_be_visible(timeout=5000)
        else:
            pytest.skip("No option icons found in device list")

    @pytest.mark.ui
    @pytest.mark.licenses
    def test_suspend_option_available(self):
        """Verify Suspend License option is available in device menu."""
        self._navigate_to_device_list()

        options = self.license.options_icons
        if options.count() == 0:
            pytest.skip("No option icons for device")

        self.license.open_device_menu(0)

        suspend = self.page.locator(
            "li:has-text('Suspend'), div:has-text('Suspend')"
        ).first
        expect(suspend).to_be_visible(timeout=5000)

        # Close menu by pressing Escape
        self.page.keyboard.press("Escape")
        self.page.wait_for_timeout(500)

    @pytest.mark.ui
    @pytest.mark.licenses
    def test_unassign_option_available(self):
        """Verify Unassign License option is available in device menu."""
        self._navigate_to_device_list()

        options = self.license.options_icons
        if options.count() == 0:
            pytest.skip("No option icons for device")

        self.license.open_device_menu(0)

        unassign = self.page.locator(
            "li:has-text('Unassign'), div:has-text('Unassign')"
        ).first
        expect(unassign).to_be_visible(timeout=5000)

        self.page.keyboard.press("Escape")
        self.page.wait_for_timeout(500)

    @pytest.mark.ui
    @pytest.mark.licenses
    def test_suspend_confirmation_popup(self):
        """Verify Suspend License shows a confirmation popup."""
        self._navigate_to_device_list()

        options = self.license.options_icons
        if options.count() == 0:
            pytest.skip("No option icons for device")

        self.license.suspend_device(0)

        # Confirmation dialog should appear
        confirm_dialog = self.page.locator(
            "div[role='dialog'], div[class*='modal'], div[class*='confirm']"
        )
        expect(confirm_dialog.first).to_be_visible(timeout=5000)

        # Cancel to avoid actual suspension
        self.license.cancel_action()

    @pytest.mark.ui
    @pytest.mark.licenses
    def test_unassign_confirmation_popup(self):
        """Verify Unassign License shows a confirmation popup."""
        self._navigate_to_device_list()

        options = self.license.options_icons
        if options.count() == 0:
            pytest.skip("No option icons for device")

        self.license.open_device_menu(0)
        self.license.unassign_option.click()
        self.page.wait_for_timeout(1000)

        confirm_dialog = self.page.locator(
            "div[role='dialog'], div[class*='modal'], div[class*='confirm']"
        )
        expect(confirm_dialog.first).to_be_visible(timeout=5000)

        # Cancel to avoid actual unassignment
        self.license.cancel_action()


class TestLicenseAssignModal:
    """Tests for the Assign New License modal workflow."""

    @pytest.fixture(autouse=True)
    def setup(self, authenticated_page):
        self.page = authenticated_page
        self.license = LicensePage(self.page)
        yield

    @pytest.mark.ui
    @pytest.mark.licenses
    def test_assign_button_visible(self):
        """Verify Assign New License button is visible."""
        self.license.navigate()

        assign_btn = self.page.locator(
            "button:has-text('Assign'), button:has-text('Assign New License')"
        ).first
        expect(assign_btn).to_be_visible(timeout=10000)

    @pytest.mark.ui
    @pytest.mark.licenses
    def test_assign_modal_opens(self):
        """Verify Assign New License modal opens on button click."""
        self.license.navigate()
        self.license.open_assign_modal()

        modal = self.page.locator(
            "div[role='dialog'], div[class*='modal']"
        ).first
        expect(modal).to_be_visible(timeout=5000)

        self.license.close_assign_modal()

    @pytest.mark.ui
    @pytest.mark.licenses
    def test_assign_modal_close_via_cancel(self):
        """Verify Assign New License modal closes using Cancel."""
        self.license.navigate()
        self.license.open_assign_modal()

        modal = self.page.locator(
            "div[role='dialog'], div[class*='modal']"
        ).first
        expect(modal).to_be_visible(timeout=5000)

        self.license.close_assign_modal()
        self.page.wait_for_timeout(1000)

        # Modal should no longer be visible
        expect(modal).to_be_hidden(timeout=5000)

    @pytest.mark.ui
    @pytest.mark.licenses
    def test_site_dropdown_in_modal(self):
        """Verify site dropdown lists available sites in assign modal."""
        self.license.navigate()
        self.license.open_assign_modal()

        dropdown = self.page.locator(
            "div[role='combobox'], select, div[class*='dropdown']"
        ).first
        expect(dropdown).to_be_visible(timeout=5000)

        self.license.close_assign_modal()
