"""License Assignment tests - the Assigned Licenses tab (a site row per
site, feature rows under an expanded site, the site switch), the
Assign New License panel, and the device-list tripwires.

Measured on the app: a site row reads
"1 | <site> | All Licenses | 18/74 | Enabled" and its expanded feature
rows "1 | <feature> | 1 / 6 | <issued> | <expires> | <key> | Enabled";
the site's a/b is the sum of its features' a/b. The app has no
device-list drill-down: no cell in the Assigned table is a link and
clicking one only toggles the expansion. The device-list tests stay as
tripwires: they skip on that measured absence and run the day a
feature row links somewhere.
"""
import pytest
from playwright.sync_api import expect

from tests.shared.helpers.surface import require_items
from tests.shared.pages.license_page import LicensePage

NO_DRILL_DOWN = ("this build's Assigned table has no device-list drill-down: no cell "
                 "of a feature row is a link")


class TestLicenseAssignedTab:
    """Tests for Assigned Licenses tab - site grouping, expand/collapse, toggles."""

    @pytest.fixture(autouse=True)
    def setup(self, authenticated_page):
        self.page = authenticated_page
        self.license = LicensePage(self.page)
        return

    def _navigate_to_assigned(self):
        """Navigate to Licenses > Assigned tab."""
        self.license.navigate()
        self.license.switch_to_assigned_tab()

    def _require_expandable_site(self):
        """A site row that can be expanded, proved or explained.

        The Assigned TAB is the surface, not the table: a tenant with
        no assigned licence renders an empty state and no table rows,
        and a row-level container would turn that data fact into a
        failure.
        """
        require_items(
            self.license.site_expand_icons,
            container=self.license.assigned_tab,
            surface="Licenses > Assigned",
            artifact="expandable site row",
            empty_means="no licence is assigned on this tenant",
        )

    @pytest.mark.ui
    @pytest.mark.licenses
    def test_assigned_tab_shows_site_grouping(self):
        """Verify the Assigned table lists one well-formed row per site.

        Steps:
        1. Open Admin > Licenses and click Assigned Licenses.
           Expected: The headers read No., Site / Device, License Item(SKU), Quantity, Issue Date, Expiry Date, License Key, Status.
        2. Read the site rows.
           Expected: Each has a site name, reads All Licenses, a Quantity of the form assigned/total with assigned no more than total, and a Status of Enabled or Disabled.
        """
        self._navigate_to_assigned()
        assert self.license.table_headers() == LicensePage.ASSIGNED_HEADERS, self.license.table_headers()
        self._require_expandable_site()
        sites = self.license.site_entries()
        assert sites, f"No site row parsed from the Assigned table: {self.license.data_rows()[:3]}"
        bad = [s for s in sites if not s["site"] or s["assigned"] < 0 or s["assigned"] > s["total"]
               or s["status"] not in ("Enabled", "Disabled")]
        assert not bad, f"Malformed site rows: {bad}"

    @pytest.mark.ui
    @pytest.mark.licenses
    def test_multiple_sites_displayed(self):
        """Verify the site rows are numbered 1 to N in order, one per site.

        Steps:
        1. Open Admin > Licenses > Assigned Licenses and read the No. column of the site rows.
           Expected: The numbers run 1, 2, ... N with no gap or repeat, and no site name repeats.
        """
        self._navigate_to_assigned()
        self._require_expandable_site()
        sites = self.license.site_entries()
        numbers = [s["no"] for s in sites]
        assert numbers == [str(i) for i in range(1, len(sites) + 1)], f"Site numbering is {numbers}"
        names = [s["site"] for s in sites]
        assert len(names) == len(set(names)), f"A site is listed twice: {names}"

    @pytest.mark.ui
    @pytest.mark.licenses
    def test_expand_site_shows_features(self):
        """Verify expanding a site lists its feature licences and their quantities add up to the site's.

        Steps:
        1. Open Admin > Licenses > Assigned Licenses and note the first site's Quantity (assigned/total).
           Expected: A row reading All Licenses with a Quantity like 18/74.
        2. Click the expand arrow on that site.
           Expected: Feature rows appear under it, each with a name, a Quantity like 1 / 6, an issue date, an expiry date and a licence key.
        3. Add the feature rows' assigned and total counts.
           Expected: The sums equal the site row's assigned and total.
        """
        self._navigate_to_assigned()
        self._require_expandable_site()
        site = self.license.site_entries()[0]
        rows = self.page.locator("tr.MuiTableRow-root")
        initial_rows = rows.count()
        self.license.expand_site(0)
        expect(rows).not_to_have_count(initial_rows, timeout=10000)
        features = self.license.wait_for_feature_rows()
        assert features, f"No feature row parsed after expanding {site['site']!r}: {self.license.data_rows()[:4]}"
        assert all(f["name"] and f["key"] and f["issued"] and f["expires"] for f in features), features
        total = (sum(f["assigned"] for f in features), sum(f["total"] for f in features))
        assert total == (site["assigned"], site["total"]), (
            f"{site['site']!r} shows {site['assigned']}/{site['total']} but its features add up to {total[0]}/{total[1]}")

    @pytest.mark.ui
    @pytest.mark.licenses
    def test_collapse_site_hides_features(self):
        """Verify collapsing a site removes exactly the feature rows it showed.

        Steps:
        1. Open Admin > Licenses > Assigned Licenses and click the expand arrow on the first site.
           Expected: Feature rows appear under the site.
        2. Click the arrow again.
           Expected: The feature rows are gone and the table has the same rows as before the expansion.
        """
        self._navigate_to_assigned()
        self._require_expandable_site()
        before = self.license.data_rows()
        rows = self.page.locator("tr.MuiTableRow-root")
        self.license.expand_site(0)
        expect(rows).not_to_have_count(len(before) + 1, timeout=10000)
        assert self.license.wait_for_feature_rows(), "Expanding showed no feature row"
        self.license.collapse_site(0)
        expect(rows).to_have_count(len(before) + 1, timeout=10000)   # + the header row
        assert self.license.feature_rows() == []
        assert self.license.data_rows() == before

    @pytest.mark.ui
    @pytest.mark.licenses
    def test_site_enable_toggle_visible(self):
        """Verify each site's switch agrees with its Status column.

        Steps:
        1. Open Admin > Licenses > Assigned Licenses and read each site row's switch and Status.
           Expected: One switch per site row; a switch that is on sits beside Enabled, a switch that is off beside Disabled.
        """
        self._navigate_to_assigned()
        require_items(
            self.license.site_toggle_switches,
            container=self.license.assigned_tab,
            surface="Licenses > Assigned",
            artifact="site enable toggle",
            empty_means="no licence is assigned on this tenant",
            timeout_ms=5000,
        )
        sites = self.license.site_entries()
        states = self.license.switch_states()
        assert len(states) == len(sites), f"{len(states)} switches for {len(sites)} site rows"
        mismatched = [(s["site"], s["status"], on) for s, on in zip(sites, states, strict=True)
                      if on != (s["status"] == "Enabled")]
        assert not mismatched, f"Switch and Status disagree: {mismatched}"

    @pytest.mark.ui
    @pytest.mark.licenses
    def test_assigned_tab_retains_state_after_navigation(self):
        """Verify the Assigned table shows the same site rows after leaving for Views and coming back.

        Steps:
        1. Open Admin > Licenses > Assigned Licenses and note the site rows.
           Expected: At least one site row.
        2. Click Views in the sidebar, then open Admin > Licenses and click Assigned Licenses again.
           Expected: Assigned Licenses is selected and the site rows read the same as before.
        """
        self._navigate_to_assigned()
        self._require_expandable_site()
        before = self.license.site_entries()
        self.license.go_to_views_and_back()
        self.license.switch_to_assigned_tab()
        assert self.license.selected_tab() == "Assigned Licenses"
        assert self.license.site_entries() == before, "The site rows changed across the trip to Views"

    @pytest.mark.ui
    @pytest.mark.licenses
    def test_assigned_tab_refresh_behavior(self):
        """Verify the Assigned tab re-selects and shows the same site rows after a page reload.

        Steps:
        1. Open Admin > Licenses > Assigned Licenses and note the site rows.
           Expected: At least one site row.
        2. Reload the browser page, open Admin > Licenses and click Assigned Licenses.
           Expected: Assigned Licenses is selected and the site rows read the same as before.
        """
        self._navigate_to_assigned()
        self._require_expandable_site()
        before = self.license.site_entries()
        self.page.reload()
        self.license.navigate()
        self.license.switch_to_assigned_tab()
        expect(self.license.assigned_tab).to_have_attribute("aria-selected", "true", timeout=10000)
        assert self.license.site_entries() == before, "The site rows changed across a reload"


class TestLicenseDeviceList:
    """Tripwires for a device list under a feature licence.

    The app renders none today (module docstring): every test here
    skips on that measured absence and runs the day a feature row links
    somewhere. The oracles are written for that day.
    """

    @pytest.fixture(autouse=True)
    def setup(self, authenticated_page):
        self.page = authenticated_page
        self.license = LicensePage(self.page)
        return

    _require_expandable_site = TestLicenseAssignedTab._require_expandable_site

    def _navigate_to_device_list(self):
        """Navigate to Licenses > Assigned > expand site > click feature."""
        self.license.navigate()
        self.license.switch_to_assigned_tab()
        self._require_expandable_site()
        self.license.expand_site(0)
        feature_links = self.page.locator("table a, table button:not(.MuiSwitch-root button), td [role='link']")
        require_items(
            feature_links,
            container=self.license.assigned_tab,
            surface="Licenses > Assigned, site expanded",
            artifact="feature licence link",
            empty_means=NO_DRILL_DOWN,
        )
        feature_links.first.click()
        expect(self.license.breadcrumb.first).to_be_visible(timeout=15000)

    @pytest.mark.ui
    @pytest.mark.licenses
    def test_device_list_loads(self):
        """Verify a feature licence opens its device list with a breadcrumb and device rows.

        Steps:
        1. Open Admin > Licenses > Assigned Licenses, expand the first site and click a feature licence.
           Expected: A device list opens under a breadcrumb naming the site and the feature.
        2. Read the device table.
           Expected: A Device column and a Status column, and at least one device row.
        """
        self._navigate_to_device_list()
        headers = self.license.table_headers()
        assert any("Device" in h for h in headers), headers
        assert any("Status" in h for h in headers), headers
        assert self.license.data_rows(), "The device list has no rows"
        assert not self.license.is_no_data(), self.license.data_rows()[:2]

    @pytest.mark.ui
    @pytest.mark.licenses
    def test_device_list_has_three_dot_menu(self):
        """Verify every device row carries an options menu.

        Steps:
        1. Open a feature licence's device list.
           Expected: The list shows its device rows.
        2. Count the three-dot options icons.
           Expected: One per device row.
        """
        self._navigate_to_device_list()
        rows = [r for r in self.license.data_rows() if LicensePage.NO_DATA not in r]
        expect(self.license.options_icons).to_have_count(len(rows), timeout=5000)

    @pytest.mark.ui
    @pytest.mark.licenses
    def test_suspend_option_available(self):
        """Verify a device's options menu offers Suspend and closes on Escape.

        Steps:
        1. Open a feature licence's device list and click the first device's three-dot icon.
           Expected: A menu opens listing Suspend.
        2. Press Escape.
           Expected: The menu closes.
        """
        self._navigate_to_device_list()
        self.license.open_device_menu(0)
        items = [li.inner_text().strip() for li in self.page.locator("[role='menu']:visible li").all()]
        assert any(i.startswith("Suspend") for i in items), f"Menu items: {items}"
        self.page.keyboard.press("Escape")
        expect(self.page.locator("[role='menu']:visible")).to_have_count(0, timeout=5000)

    @pytest.mark.ui
    @pytest.mark.licenses
    def test_unassign_option_available(self):
        """Verify a device's options menu offers Unassign and closes on Escape.

        Steps:
        1. Open a feature licence's device list and click the first device's three-dot icon.
           Expected: A menu opens listing Unassign.
        2. Press Escape.
           Expected: The menu closes.
        """
        self._navigate_to_device_list()
        self.license.open_device_menu(0)
        items = [li.inner_text().strip() for li in self.page.locator("[role='menu']:visible li").all()]
        assert any(i.startswith("Unassign") for i in items), f"Menu items: {items}"
        self.page.keyboard.press("Escape")
        expect(self.page.locator("[role='menu']:visible")).to_have_count(0, timeout=5000)

    @pytest.mark.ui
    @pytest.mark.licenses
    def test_suspend_confirmation_popup(self):
        """Verify Suspend asks for confirmation naming the action, and Cancel changes nothing.

        Steps:
        1. Open a feature licence's device list, open the first device's menu and choose Suspend.
           Expected: A confirmation dialog opens whose text mentions suspending, with Cancel and a confirm button.
        2. Click Cancel.
           Expected: The dialog closes and the device row reads as before.
        """
        self._navigate_to_device_list()
        before = self.license.data_rows()
        self.license.suspend_device(0)
        dialog = self.page.locator("div[role='dialog'], div[class*='modal']").first
        expect(dialog).to_be_visible(timeout=5000)
        assert "suspend" in dialog.inner_text().lower(), dialog.inner_text()
        self.license.cancel_action()
        assert self.license.data_rows() == before

    @pytest.mark.ui
    @pytest.mark.licenses
    def test_unassign_confirmation_popup(self):
        """Verify Unassign asks for confirmation naming the action, and Cancel changes nothing.

        Steps:
        1. Open a feature licence's device list, open the first device's menu and choose Unassign.
           Expected: A confirmation dialog opens whose text mentions unassigning, with Cancel and a confirm button.
        2. Click Cancel.
           Expected: The dialog closes and the device row reads as before.
        """
        self._navigate_to_device_list()
        before = self.license.data_rows()
        self.license.open_device_menu(0)
        self.license.unassign_option.click()
        dialog = self.page.locator("div[role='dialog'], div[class*='modal']").first
        expect(dialog).to_be_visible(timeout=5000)
        assert "unassign" in dialog.inner_text().lower(), dialog.inner_text()
        self.license.cancel_action()
        assert self.license.data_rows() == before


class TestLicenseAssignModal:
    """Tests for the Assign New License panel workflow.

    The 2026-08 app renders assignment as a customMuiModal overlay
    (heading 'Assign New License', Bulk/Individual toggle, Site select,
    Features, Devices, Assign). The 'Assign New' button only exists on
    the Assigned Licenses tab. Test names keep the historical 'modal'
    wording so QA Touch nodeid mappings stay stable. Each test closes
    the modal it opens: contexts are per-test, but a lingering backdrop
    would block every later step inside the same test.
    """

    @pytest.fixture(autouse=True)
    def setup(self, authenticated_page):
        self.page = authenticated_page
        self.license = LicensePage(self.page)
        return

    @pytest.mark.ui
    @pytest.mark.licenses
    def test_assign_button_visible(self):
        """Verify Assign New is offered on the Assigned tab and not on the Available tab.

        Steps:
        1. Open Admin > Licenses on the Available Licenses tab.
           Expected: No Assign New button.
        2. Click Assigned Licenses.
           Expected: A button reading Assign New is shown and enabled.
        """
        self.license.navigate()
        expect(self.license.assign_button).to_have_count(0)
        self.license.switch_to_assigned_tab()
        expect(self.license.assign_button).to_be_visible(timeout=10000)
        expect(self.license.assign_button).to_have_text("Assign New")
        expect(self.license.assign_button).to_be_enabled()

    @pytest.mark.ui
    @pytest.mark.licenses
    def test_assign_modal_opens(self):
        """Verify Assign New opens the assignment panel with its heading, both modes and its sections.

        Steps:
        1. Open Admin > Licenses > Assigned Licenses and click Assign New.
           Expected: A panel headed Assign New License opens, offering Assign to Bulk and Assign to Individual, a Site select reading Select, Features and Devices sections, and an Assign button.
        2. Press Escape.
           Expected: The panel closes.
        """
        self.license.navigate()
        if not self.license.open_assign_panel():
            pytest.skip("Assign New is not available on this tenant")
        panel = self.page.locator(".customMuiModal, div[class*='modal']:visible").first
        expect(panel).to_be_visible()
        text = " ".join(panel.inner_text().split())
        for part in ("Assign New License", "Assign to Bulk", "Assign to Individual", "Site", "Features", "Devices"):
            assert part in text, f"{part!r} missing from the panel: {text[:200]}"
        expect(panel.get_by_text("Select", exact=True).first).to_be_visible()
        expect(panel.locator("button:has-text('Assign')").last).to_be_visible()
        self.license.close_assign_modal()

    @pytest.mark.ui
    @pytest.mark.licenses
    def test_assign_modal_close_via_cancel(self):
        """Verify Escape dismisses the assignment panel and frees the page.

        The customMuiModal has no Cancel button; its backdrop blocks the
        page (tab clicks included), and Escape dismisses it.

        Steps:
        1. Open Admin > Licenses > Assigned Licenses, click Assign New, then press Escape.
           Expected: The panel is gone.
        2. Click Available Licenses.
           Expected: The tab responds: Available Licenses becomes the selected tab.
        """
        self.license.navigate()
        if not self.license.open_assign_panel():
            pytest.skip("Assign New is not available on this tenant")
        expect(self.license.assign_panel).to_be_visible()
        self.license.close_assign_modal()
        expect(self.license.assign_panel).to_be_hidden(timeout=10000)
        self.license.switch_to_available_tab()
        assert self.license.selected_tab() == "Available Licenses", "The page stayed blocked after Escape"

    @pytest.mark.ui
    @pytest.mark.licenses
    def test_site_dropdown_in_modal(self):
        """Verify the panel's Site select lists the tenant's sites, including the configured one.

        Steps:
        1. Open Admin > Licenses > Assigned Licenses, click Assign New and open the Site select.
           Expected: The options are the placeholder Select followed by the tenant's site names, the configured test site among them, with no name repeated.
        2. Press Escape twice.
           Expected: The list and the panel close.
        """
        from config.base_config import config

        self.license.navigate()
        if not self.license.open_assign_panel():
            pytest.skip("Assign New is not available on this tenant")
        panel = self.page.locator(".customMuiModal, div[class*='modal']:visible").first
        panel.get_by_text("Select", exact=True).first.click()
        options = self.page.locator("[role='option']")
        expect(options.first).to_be_visible(timeout=10000)
        names = [o.inner_text().strip() for o in options.all()]
        assert names[0] == "Select", names
        sites = names[1:]
        assert sites, f"Site options: {names}"
        assert len(sites) == len(set(sites)), f"A site is offered twice: {names}"
        assert config.get("test_site_name") in sites, f"{config.get('test_site_name')!r} not in {sites}"
        self.page.keyboard.press("Escape")
        self.license.close_assign_modal()
