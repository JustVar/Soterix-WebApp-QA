"""License Permissions tests - the admin's way in, the same furniture on
both tabs, no duplicated rows, the confirmation wording (a device-list
tripwire), and the labels the icons carry."""
import pytest
from playwright.sync_api import expect

from tests.shared.helpers.surface import require_items
from tests.shared.pages.license_page import LicensePage
from tests.ui.licenses.test_license_assignment import NO_DRILL_DOWN


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
        """Verify the admin's sidebar offers Licenses under Admin and it opens the licence page.

        Steps:
        1. Click Admin in the sidebar.
           Expected: A Licenses entry is shown, linking to the licence route.
        2. Click Licenses.
           Expected: The page shows the Total Licenses summary with a whole number and the two licence tabs.
        """
        self.page.locator("a[href*='admin']").first.click(force=True)
        entry = self.page.get_by_text("Licenses", exact=True).first
        expect(entry).to_be_visible(timeout=10000)
        self.license.navigate()
        counts = self.license.summary_counts()
        assert counts["total"] >= 0
        assert self.license.tab_names() == ["Available Licenses", "Assigned Licenses"]

    @pytest.mark.ui
    @pytest.mark.licenses
    def test_license_page_no_duplicate_records(self):
        """Verify the Licenses page does not render duplicate records.

        Feature names repeat by design - the tenant holds several
        licenses of one feature (measured 08/13/2026) - so the check
        keys on the WHOLE row: a double-render bug duplicates entire
        rows, while legitimate same-feature rows differ in the other
        columns (Quantity, Available, Active).

        Steps:
        1. Open Admin > Licenses and read every row of the Available Licenses table.
           Expected: At least one row.
        2. Compare the rows with each other, whole row against whole row.
           Expected: No two rows are identical in every column.
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
        """Verify the summary, the search box and the Download control are the same on both tabs.

        Steps:
        1. Open Admin > Licenses and note the summary numbers, the search box and the Download icon.
           Expected: All three are present on the Available Licenses tab.
        2. Click Assigned Licenses.
           Expected: The summary reads the same numbers, the search box and the Download icon are still there, and Assigned Licenses is the selected tab.
        """
        self.license.navigate()
        before = self.license.summary_counts()
        expect(self.license.search_input).to_be_visible(timeout=10000)
        # img asset icon: alt unreliable, locate by src (CONVENTIONS > Locators)
        expect(self.page.locator("img[src*='downloadLicense']")).to_have_count(1)

        self.license.switch_to_assigned_tab()
        assert self.license.selected_tab() == "Assigned Licenses"
        assert self.license.summary_counts() == before, "The summary changed between the tabs"
        expect(self.license.search_input).to_be_visible(timeout=10000)
        # img asset icon: alt unreliable, locate by src (CONVENTIONS > Locators)
        expect(self.page.locator("img[src*='downloadLicense']")).to_have_count(1)

    @pytest.mark.ui
    @pytest.mark.licenses
    def test_confirmation_dialogs_have_clear_messaging(self):
        """Verify the Suspend confirmation names the action and offers Cancel (device-list tripwire).

        Neither box has a device-list drill-down today (test_license_assignment
        module docstring); the test skips on that measured absence and runs
        the day a feature row links somewhere.

        Steps:
        1. Open Admin > Licenses > Assigned Licenses, expand the first site and click a feature licence.
           Expected: The device list opens under a breadcrumb.
        2. Open the first device's three-dot menu and choose Suspend.
           Expected: A confirmation dialog whose text mentions the suspension and the device, with a Cancel button.
        3. Click Cancel.
           Expected: The dialog closes.
        """
        self.license.navigate()
        self.license.switch_to_assigned_tab()
        require_items(
            self.license.site_expand_icons,
            container=self.license.assigned_tab,
            surface="Licenses > Assigned",
            artifact="expandable site row",
            empty_means="no licence is assigned on this tenant",
        )
        self.license.expand_site(0)
        feature_links = self.page.locator("table a, td [role='link']")
        require_items(
            feature_links,
            container=self.license.assigned_tab,
            surface="Licenses > Assigned, site expanded",
            artifact="feature licence link",
            empty_means=NO_DRILL_DOWN,
        )
        feature_links.first.click()
        expect(self.license.breadcrumb.first).to_be_visible(timeout=15000)
        self.license.open_device_menu(0)
        self.page.locator("li:has-text('Suspend')").first.click()
        dialog = self.page.locator("div[role='dialog'], div[class*='modal']").first
        expect(dialog).to_be_visible(timeout=5000)
        text = " ".join(dialog.inner_text().split())
        assert "suspend" in text.lower(), f"The dialog does not say what it does: {text!r}"
        expect(self.license.cancel_button).to_be_visible()
        self.license.cancel_action()
        expect(dialog).to_be_hidden(timeout=5000)

    @pytest.mark.ui
    @pytest.mark.licenses
    def test_tooltip_text_for_icons(self):
        """Verify the licence page's icons carry a name: the Download icon's alt and the expand arrow's test id.

        The summary icons (sites, site admins, total licences) carry no
        alt text in this build (measured 09/11/2026), so they are not asked.

        Steps:
        1. Open Admin > Licenses and read the Download icon.
           Expected: Its alt text reads Download.
        2. Click Assigned Licenses and read the expand arrow on a site row.
           Expected: It is the ExpandMoreIcon.
        """
        self.license.navigate()
        # img asset icon: alt unreliable, locate by src (CONVENTIONS > Locators)
        expect(self.page.locator("img[src*='downloadLicense']").first).to_have_attribute("alt", "Download")
        self.license.switch_to_assigned_tab()
        require_items(
            self.license.site_expand_icons,
            container=self.license.assigned_tab,
            surface="Licenses > Assigned",
            artifact="expandable site row",
            empty_means="no licence is assigned on this tenant",
        )
        expect(self.license.site_expand_icons.first).to_have_attribute("data-testid", "ExpandMoreIcon")
