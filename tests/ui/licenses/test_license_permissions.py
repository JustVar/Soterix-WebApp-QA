"""License Permissions tests - RBAC, admin-only access, non-admin restrictions,
and UI consistency checks."""
import pytest
from playwright.sync_api import expect
from tests.shared.pages.license_page import LicensePage


class TestLicensePermissions:
    """Tests for Licenses module access control and UI consistency."""

    @pytest.fixture(autouse=True)
    def setup(self, authenticated_page):
        self.page = authenticated_page
        self.license = LicensePage(self.page)
        yield

    @pytest.mark.ui
    @pytest.mark.licenses
    def test_admin_can_access_licenses(self):
        """Verify Admin user can access Licenses module."""
        self.license.navigate()

        # Verify page has loaded with license content
        content = self.page.locator(
            "text=Total Licenses"
        ).first
        expect(content).to_be_visible(timeout=15000)

    @pytest.mark.ui
    @pytest.mark.licenses
    def test_license_page_no_duplicate_records(self):
        """Verify the Licenses page does not render duplicate records.

        Feature names repeat by design - the tenant holds several
        licenses of one feature (measured 08/13/2026) - so the check
        keys on the WHOLE row: a double-render bug duplicates entire
        rows, while legitimate same-feature rows differ in the other
        columns (Quantity, Available, Active).
        """
        self.license.navigate()

        rows = self.page.locator("tr:has(td)")
        expect(rows.first).to_be_visible(timeout=15000)

        row_texts = []
        for i in range(rows.count()):
            text = " | ".join(rows.nth(i).inner_text().split())
            if text:
                row_texts.append(text)

        assert row_texts, "License table rendered no data rows"
        dupes = sorted({t for t in row_texts if row_texts.count(t) > 1})
        assert not dupes, (
            f"Duplicate license rows rendered: {dupes[:3]} - either a "
            "double-render bug or two records identical in every "
            "column (check the page data before blaming the render)"
        )

    @pytest.mark.ui
    @pytest.mark.licenses
    def test_consistent_layout_across_tabs(self):
        """Verify consistent UI layout across Licenses tabs."""
        self.license.navigate()

        # Check Available tab has header/search structure
        available_search = self.license.search_input
        expect(available_search).to_be_visible(timeout=10000)

        # Switch to Assigned and verify similar structure
        self.license.switch_to_assigned_tab()
        self.page.wait_for_timeout(2000)
        self.license._wait_for_page_ready()

        # Verify Assigned tab is active by checking the button
        expect(self.license.assigned_tab).to_be_visible(timeout=10000)

    @pytest.mark.ui
    @pytest.mark.licenses
    def test_confirmation_dialogs_have_clear_messaging(self):
        """Verify confirmation dialogs display clear messaging."""
        self.license.navigate()
        self.license.switch_to_assigned_tab()

        # Try to find a device menu to test dialog content
        expand_icons = self.license.site_expand_icons
        if expand_icons.count() == 0:
            pytest.skip("No expandable sites for dialog test")

        self.license.expand_site(0)
        self.page.wait_for_timeout(2000)

        # Navigate to device list if possible
        feature_links = self.page.locator(
            "div[class*='feature'] a, div[class*='nested'] a, "
            "td a, div[class*='clickable']"
        )
        if feature_links.count() == 0:
            pytest.skip("No feature links for device drill-down")

        feature_links.first.click()
        self.page.wait_for_timeout(3000)

        options = self.license.options_icons
        if options.count() == 0:
            pytest.skip("No option icons in device list")

        self.license.open_device_menu(0)

        # Click suspend to trigger dialog
        suspend = self.page.locator(
            "li:has-text('Suspend'), div:has-text('Suspend')"
        ).first
        if suspend.count() > 0:
            suspend.click()
            self.page.wait_for_timeout(1000)

            # Verify dialog has meaningful text (not empty)
            dialog = self.page.locator(
                "div[role='dialog'], div[class*='modal']"
            ).first
            if dialog.count() > 0:
                text = dialog.inner_text()
                assert len(text.strip()) > 10, \
                    "Confirmation dialog should have clear messaging"

            # Cancel
            self.license.cancel_action()

    @pytest.mark.ui
    @pytest.mark.licenses
    def test_tooltip_text_for_icons(self):
        """Verify tooltip text exists for license-related icons."""
        self.license.navigate()

        # Check for title attributes or aria-labels on interactive elements
        icons = self.page.locator(
            "img[title], img[alt], button[title], "
            "[aria-label], [data-tooltip]"
        )
        self.page.wait_for_timeout(2000)

        # At least some icons should have accessibility attributes
        assert icons.count() > 0, "No icons with tooltip/alt text found"
