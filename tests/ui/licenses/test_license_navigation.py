"""License Navigation & Layout tests - landing, the summary numbers, the
tabs, the Available table, and what survives a reload or a trip away.

Every check here reads a value the page renders and compares it with
another one (the summary against itself, the table against the summary,
the tabs' aria-selected, the same rows before and after), measured on both
boxes 09/11/2026 - the old checks proved only that a label was visible.
"""
import pytest
from playwright.sync_api import expect

from tests.shared.pages.license_page import LicensePage


class TestLicenseNavigation:
    """Tests for Licenses page navigation, tabs, and layout."""

    @pytest.fixture(autouse=True)
    def setup(self, authenticated_page):
        self.page = authenticated_page
        self.license = LicensePage(self.page)
        yield

    def _navigate(self):
        """Helper to navigate to Licenses page."""
        self.license.navigate()

    # --- Access & Landing ---

    @pytest.mark.ui
    @pytest.mark.licenses
    def test_navigate_to_licenses(self):
        """Verify Admin > Licenses lands on the two licence tabs with Available selected.

        Steps:
        1. Open Admin from the sidebar and click Licenses.
           Expected: The page shows exactly two tabs, Available Licenses and Assigned Licenses, with Available Licenses selected.
        """
        self._navigate()
        assert self.license.tab_names() == ["Available Licenses", "Assigned Licenses"], (
            f"Expected the two licence tabs, got {self.license.tab_names()}")
        assert self.license.selected_tab() == "Available Licenses"

    @pytest.mark.ui
    @pytest.mark.licenses
    def test_default_layout(self):
        """Verify the licence summary reconciles: Total equals Active plus Available plus Suspended.

        Steps:
        1. Open Admin > Licenses and read the Total Licenses block.
           Expected: Total Licenses, Active, Available and Suspended are all whole numbers.
        2. Add Active, Available and Suspended.
           Expected: The sum equals Total Licenses.
        """
        self._navigate()
        counts = self.license.summary_counts()
        assert counts["total"] == counts["active"] + counts["available"] + counts["suspended"], (
            f"Total {counts['total']} is not Active {counts['active']} + Available "
            f"{counts['available']} + Suspended {counts['suspended']}")

    @pytest.mark.ui
    @pytest.mark.licenses
    def test_total_licenses_widget_visible(self):
        """Verify Total Licenses equals the Quantity column of the Available table.

        Steps:
        1. Open Admin > Licenses and read Total Licenses.
           Expected: A whole number.
        2. Add the Quantity column of every row on the Available Licenses tab.
           Expected: The sum equals Total Licenses, and the Available and Active columns add up to the summary's Available and Active.
        """
        self._navigate()
        counts = self.license.summary_counts()
        rows = self.license.available_rows()
        assert rows, "The Available table has no feature rows to add up"
        sums = {k: sum(r[k] for r in rows) for k in ("quantity", "available", "active")}
        assert sums["quantity"] == counts["total"], (
            f"Quantity column adds to {sums['quantity']}, Total Licenses says {counts['total']}")
        assert (sums["available"], sums["active"]) == (counts["available"], counts["active"]), (
            f"Table Available/Active {sums['available']}/{sums['active']} differ from the summary "
            f"{counts['available']}/{counts['active']}")

    @pytest.mark.ui
    @pytest.mark.licenses
    def test_license_counts_displayed(self):
        """Verify every feature row's Available and Active fit inside its Quantity.

        Steps:
        1. Open Admin > Licenses and read each row of the Available Licenses table.
           Expected: Quantity, Available and Active are whole numbers on every row.
        2. Compare the columns row by row.
           Expected: Available plus Active never exceeds Quantity, and neither is negative.
        """
        self._navigate()
        rows = self.license.available_rows()
        assert rows, "The Available table has no feature rows"
        bad = [r for r in rows if r["available"] + r["active"] > r["quantity"]
               or min(r["available"], r["active"]) < 0]
        assert not bad, f"Rows whose Available + Active exceed Quantity: {bad}"

    @pytest.mark.ui
    @pytest.mark.licenses
    def test_counts_persist_after_refresh(self):
        """Verify the licence summary reads the same numbers after a page reload.

        Steps:
        1. Open Admin > Licenses and note Total, Active, Available and Suspended.
           Expected: Four whole numbers.
        2. Reload the browser page and open Admin > Licenses again.
           Expected: The four numbers are the same as before the reload.
        """
        self._navigate()
        before = self.license.summary_counts()
        self.page.reload()
        self.license.navigate()
        after = self.license.summary_counts()
        assert after == before, f"Summary changed across a reload: {before} -> {after}"

    # --- Tab Switching ---

    @pytest.mark.ui
    @pytest.mark.licenses
    def test_available_tab_is_default(self):
        """Verify Available Licenses is the selected tab on landing and Assigned is not.

        Steps:
        1. Open Admin > Licenses without clicking a tab.
           Expected: The Available Licenses tab is selected and the Assigned Licenses tab is not.
        2. Read the table headers.
           Expected: Feature, Quantity, Available, Active (the Available table).
        """
        self._navigate()
        expect(self.license.available_tab).to_have_attribute("aria-selected", "true")
        expect(self.license.assigned_tab).to_have_attribute("aria-selected", "false")
        assert self.license.table_headers() == LicensePage.AVAILABLE_HEADERS

    @pytest.mark.ui
    @pytest.mark.licenses
    def test_switch_between_tabs(self):
        """Verify switching tabs moves the selection and swaps the table.

        Steps:
        1. Open Admin > Licenses and click Assigned Licenses.
           Expected: Assigned Licenses is selected, Available Licenses is not, and the table headers are the Assigned columns (No., Site / Device, License Item(SKU), Quantity, Issue Date, Expiry Date, License Key, Status).
        2. Click Available Licenses.
           Expected: The selection returns to Available Licenses and the headers are Feature, Quantity, Available, Active again.
        """
        self._navigate()
        self.license.switch_to_assigned_tab()
        expect(self.license.assigned_tab).to_have_attribute("aria-selected", "true")
        expect(self.license.available_tab).to_have_attribute("aria-selected", "false")
        assert self.license.table_headers() == LicensePage.ASSIGNED_HEADERS

        self.license.switch_to_available_tab()
        expect(self.license.available_tab).to_have_attribute("aria-selected", "true")
        expect(self.license.assigned_tab).to_have_attribute("aria-selected", "false")
        assert self.license.table_headers() == LicensePage.AVAILABLE_HEADERS

    @pytest.mark.ui
    @pytest.mark.licenses
    def test_available_tab_displays_feature_list(self):
        """Verify the Available table lists named features, not the No Data row.

        Steps:
        1. Open Admin > Licenses on the Available Licenses tab.
           Expected: At least one row with a feature name and three whole numbers; no row reads No Data!.
        2. Read the feature names.
           Expected: Every name is non-empty and each row is unique in full.
        """
        self._navigate()
        self.license.switch_to_available_tab()
        assert not self.license.is_no_data(), "The Available table shows 'No Data!' with no filter applied"
        rows = self.license.available_rows()
        assert rows, f"No feature rows parsed from the Available table; rows: {self.license.data_rows()[:3]}"
        assert all(r["name"] for r in rows), f"A feature row has no name: {rows}"
        keys = [tuple(r.values()) for r in rows]
        assert len(keys) == len(set(keys)), "The Available table repeats a whole row"

    @pytest.mark.ui
    @pytest.mark.licenses
    def test_available_tab_columns(self):
        """Verify the Available Licenses table has exactly the columns Feature, Quantity, Available, Active.

        Steps:
        1. Open Admin > Licenses on the Available Licenses tab and read the column headers.
           Expected: Feature, Quantity, Available, Active, in that order and nothing else.
        """
        self._navigate()
        self.license.switch_to_available_tab()
        assert self.license.table_headers() == LicensePage.AVAILABLE_HEADERS, (
            f"Headers are {self.license.table_headers()}")

    @pytest.mark.ui
    @pytest.mark.licenses
    def test_available_tab_retains_state_after_navigation(self):
        """Verify the Available table shows the same rows after leaving for Views and coming back.

        Steps:
        1. Open Admin > Licenses and note the Available Licenses rows.
           Expected: At least one feature row.
        2. Click Views in the sidebar, then open Admin > Licenses again.
           Expected: Available Licenses is selected and the rows read the same as before.
        """
        self._navigate()
        self.license.switch_to_available_tab()
        before = self.license.data_rows()
        assert before, "No rows on the Available tab to compare"
        self.license.go_to_views_and_back()
        assert self.license.selected_tab() == "Available Licenses"
        assert self.license.data_rows() == before, "The Available rows changed across the trip to Views"

    @pytest.mark.ui
    @pytest.mark.licenses
    def test_search_bar_visible(self):
        """Verify the search box is empty, says what it searches, and takes text.

        Steps:
        1. Open Admin > Licenses and read the search box.
           Expected: It is empty and its placeholder reads 'Search by feature, availability.'.
        2. Type a word into it.
           Expected: The box holds the word.
        """
        self._navigate()
        expect(self.license.search_input).to_have_value("")
        expect(self.license.search_input).to_have_attribute("placeholder", "Search by feature, availability.")
        self.license.search_input.fill("probe")
        expect(self.license.search_input).to_have_value("probe")

    @pytest.mark.ui
    @pytest.mark.licenses
    def test_license_module_accessible_after_refresh(self):
        """Verify three reloads in a row leave the licence summary unchanged.

        Steps:
        1. Open Admin > Licenses and note the summary numbers.
           Expected: Four whole numbers.
        2. Reload the page and open Admin > Licenses again, three times.
           Expected: The summary reads the same numbers after each reload.
        """
        self._navigate()
        before = self.license.summary_counts()
        for attempt in range(3):
            self.page.reload()
            self.license.navigate()
            assert self.license.summary_counts() == before, f"Summary changed on reload {attempt + 1}"
