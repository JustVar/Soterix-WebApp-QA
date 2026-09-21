"""LPR (License Plate Recognition) navigation and state management tests.

Tests the ability to navigate between LPR pages and ensure correct page state:
- Main LPR page (Lists)
- Plate page (inside a list)
- Filter panel (on Plate page)
- Search Results (after applying filters)
- Categories page
"""
import contextlib
import datetime
import re

import pytest
from playwright.sync_api import (
    Error as PlaywrightError,
    TimeoutError as PlaywrightTimeoutError,
    expect,
)

from tests.shared.pages.lpr_page import CATEGORY_HEADERS, PLATE_HEADERS, LprPage

# One worker for every module that writes this account's LPR lists, views and widgets: under
# -n they would otherwise spread across workers and race on the same
# tenant state (pytest.ini --dist loadgroup; audit 09/17/2026, row 86).
pytestmark = pytest.mark.xdist_group("account_lpr")


class TestLprNavigation:
    """Tests for LPR navigation between pages and states."""

    @pytest.fixture(autouse=True)
    def setup(self, authenticated_page, step_capture):
        self.page = authenticated_page
        self.step_capture = step_capture
        step_capture.set_page(self.page)
        self.lpr = LprPage(self.page)
        self._owned_lists = []
        yield
        self._cleanup_lists()

    def _own_a_list(self) -> str:
        """Create an LPR list this test owns, and return its name.

        Taking the tenant's first list made these tests pass only while
        an earlier run had leaked one, and pointed edits and deletes at
        a real user's data (register item 27).
        """
        name = "AutoTest List " + datetime.datetime.now().strftime("%H%M%S%f")[:12]
        self.lpr.create_list(name)
        self._owned_lists.append(name)
        return name

    def _cleanup_lists(self):
        """Delete every list this test made, and say so when one stays.

        The old body navigated and deleted nothing under a docstring
        that said it deleted them, which is how Test_List_* rows built
        up on the tenant.
        """
        errors = []
        for name in reversed(self._owned_lists):
            # typed: a refused delete or a row that never leaves is
            # what this collects; anything else is a real fault and
            # must not be swallowed by a teardown
            try:
                self.lpr.delete_list(name)
            except (PlaywrightError, RuntimeError) as e:
                errors.append(f"{name}: {e}")
        self._owned_lists = []
        if errors:
            raise RuntimeError("LPR list cleanup failed: " + "; ".join(errors))

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.lpr
    def test_navigate_to_lpr_main_page(self):
        """Verify navigation to Admin > LPR Lists page.

        Steps:
        1. Click Admin in the left sidebar, then click LPR.
           Expected: The LPR Lists page opens and shows the Create List button.
        """
        self.step_capture.mark(1, "Navigate to Admin > LPR")
        self.lpr.navigate_to_lpr()

        self.step_capture.mark(2, "Verify 'Create List' button is visible")
        expect(self.lpr.create_list_button.first).to_be_enabled(timeout=15000)

        self.step_capture.mark(3, "Verify on LPR Lists page")
        # The Lists page and not a different LPR page: its own search box shows,
        # and the search boxes of the Categories and Plate pages do not.
        expect(self.lpr.list_search).to_be_visible()
        expect(self.lpr.category_search).to_have_count(0)
        expect(self.lpr.plate_search).to_have_count(0)
        print("[PASS] Successfully navigated to LPR Lists page")

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.lpr
    def test_ensure_lpr_page_already_on_lists(self):
        """Verify clicking LPR while the Lists page is open keeps it open.

        Steps:
        1. Click Admin in the left sidebar, then click LPR.
           Expected: The LPR Lists page opens and shows the Create List button.
        2. Click LPR again while the Lists page is open.
           Expected: The Lists page stays as it is and the Create List button stays visible.
        """
        self.step_capture.mark(1, "Navigate to LPR Lists page")
        self.lpr.navigate_to_lpr()
        url_before = self.page.url

        self.step_capture.mark(2, "Click LPR again while the Lists page is open")
        self.lpr.lpr_menu.first.click()
        expect(self.lpr.create_list_button.first).to_be_visible(timeout=10000)
        assert self.page.url == url_before, (
            f"the second LPR click moved the page to {self.page.url}")

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.lpr
    def test_navigate_from_search_results_to_lists(self):
        """Verify navigation from Search Results back to Lists via breadcrumb.

        Steps:
        1. Click Admin in the left sidebar, then click LPR, and click the View icon on a list row.
           Expected: The Plate page opens and shows the Add Plate button.
        2. Click the Filter icon, then click Apply.
           Expected: The Search Results view opens with its header.
        3. Click LPR in the breadcrumb.
           Expected: The Lists page opens with the Create List button, and the Search Results header is gone.
        """
        self.step_capture.mark(1, "Open a list's Plate page")
        self.lpr.navigate_to_lpr()
        list_name = self._own_a_list()
        row = self.lpr.get_list_row(list_name)
        row.locator("img[aria-label='View']").click()
        expect(self.lpr.add_plate_button.first).to_be_visible(timeout=30000)

        self.step_capture.mark(2, "Apply a filter to reach Search Results")
        self.lpr.filter_icon.first.click()
        expect(self.lpr.apply_filter_button.first).to_be_visible(timeout=30000)
        self.lpr.apply_filter_button.first.click()
        expect(self.lpr.search_results_header.first).to_be_visible(timeout=15000)

        self.step_capture.mark(3, "Return to Lists via the breadcrumb")
        self.lpr.lpr_breadcrumb.first.click()
        expect(self.lpr.create_list_button.first).to_be_visible(timeout=30000)
        expect(self.lpr.search_results_header).to_have_count(0)
        expect(self.lpr.get_list_row(list_name)).to_contain_text(list_name)

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.lpr
    def test_categories_page_navigation(self):
        """Verify navigation to Categories page.

        Steps:
        1. Click Admin in the left sidebar, then click LPR.
           Expected: The LPR Lists page opens and shows the Create List button.
        2. Click the Categories tab.
           Expected: The Categories page opens and shows the Add Category button.
        """
        self.step_capture.mark(1, "Navigate to LPR Lists page")
        self.lpr.navigate_to_lpr()

        self.step_capture.mark(2, "Navigate to Categories tab")
        self.lpr.ensure_lpr_categories_page()

        self.step_capture.mark(3, "Verify 'Add Category' button is visible")
        expect(self.lpr.add_category_button.first).to_be_enabled(timeout=15000)
        # The Categories table and not the Lists one: its columns, and no list search box
        expect(self.lpr.table_headers).to_have_text(CATEGORY_HEADERS)
        expect(self.lpr.list_search).to_have_count(0)

        self.step_capture.mark(4, "Verify on Categories page")
        print("[PASS] Successfully navigated to Categories page")

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.lpr
    def test_categories_page_already_on_categories(self):
        """Verify clicking the Categories tab while Categories is open keeps it open.

        Steps:
        1. Click Admin in the left sidebar, click LPR, then click the Categories tab.
           Expected: The Categories page opens and shows the Add Category button.
        2. Click the Categories tab again.
           Expected: The Categories page stays open and the Add Category button stays visible.
        """
        self.step_capture.mark(1, "Navigate to Categories page")
        self.lpr.navigate_to_lpr()
        self.lpr.ensure_lpr_categories_page()
        url_before = self.page.url

        self.step_capture.mark(2, "Click the Categories tab again")
        self.lpr.categories_tab.first.click(force=True)
        expect(self.lpr.add_category_button.first).to_be_visible(timeout=10000)
        assert self.page.url == url_before, (
            f"the second Categories click moved the page to {self.page.url}")

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.lpr
    def test_navigate_back_to_lists_from_categories(self):
        """Verify navigation back to Lists page from Categories via List tab.

        Steps:
        1. Click Admin in the left sidebar, click LPR, then click the Categories tab.
           Expected: The Categories page opens and shows the Add Category button.
        2. Click the List tab.
           Expected: The Lists page opens and shows the Create List button.
        """
        self.step_capture.mark(1, "Navigate to Categories page")
        self.lpr.navigate_to_lpr()
        self.lpr.ensure_lpr_categories_page()

        self.step_capture.mark(2, "Click List tab to switch from Categories")
        # Click the List tab button instead of trying to navigate away
        list_tab = self.page.locator("button:has-text('List')").first
        list_tab.wait_for(state="visible", timeout=30000)
        list_tab.click(force=True)

        self.step_capture.mark(3, "Verify on Lists page")
        # the Create List button is the Lists-page signal
        self.lpr.create_list_button.first.wait_for(state="visible", timeout=15000)
        # The click changed the page: the Categories search box and column are gone,
        # and the Lists search box is back
        expect(self.lpr.category_search).to_have_count(0)
        expect(self.page.get_by_role("columnheader", name="Category Name", exact=True)).to_have_count(0)
        expect(self.lpr.list_search).to_be_visible()

        self.step_capture.mark(4, "Navigation completed successfully")
        print("[PASS] Successfully navigated from Categories back to Lists")

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.lpr
    def test_open_plate_page_from_lists(self):
        """Verify opening Plate page by clicking View icon on a list.

        Steps:
        1. Click Admin in the left sidebar, then click LPR.
           Expected: The Lists page shows at least one list row.
        2. Click the View icon on the first list row.
           Expected: The Plate page for that list opens and shows the Add Plate button.
        """
        self.step_capture.mark(1, "Navigate to Lists page")
        self.lpr.navigate_to_lpr()

        # Get first available list
        self.step_capture.mark(2, "Find first available list")
        # Make the list this test works on. Taking the tenant's
        # first one passed only while a leaked list was there.
        list_name = self._own_a_list()
        first_list_row = self.lpr.get_list_row(list_name)

        self.step_capture.mark(3, f"Open list: {list_name}")

        # Click View icon
        view_icon = first_list_row.locator("img[aria-label='View']")
        view_icon.click()

        self.step_capture.mark(4, "Verify 'Add Plate' button is visible")
        self.lpr.add_plate_button.first.wait_for(state="visible", timeout=30000)
        # The Plate page of the list: the plate columns, and the Lists search box is gone
        expect(self.lpr.table_headers).to_have_text(PLATE_HEADERS)
        expect(self.lpr.list_search).to_have_count(0)

        self.step_capture.mark(5, "Verify on Plate page")
        print(f"[PASS] Successfully opened Plate page for list: {list_name}")

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.lpr
    def test_filter_panel_navigation(self):
        """Verify opening and closing filter panel on Plate page.

        Steps:
        1. Click Admin, then LPR, and click the View icon on the first list row.
           Expected: The Plate page for that list opens and shows the Add Plate button.
        2. Click the Filter icon.
           Expected: The filter panel opens and shows the Apply and Reset buttons.
        """
        self.step_capture.mark(1, "Navigate to Lists page")
        self.lpr.navigate_to_lpr()

        # Get first available list
        # Make the list this test works on. Taking the tenant's
        # first one passed only while a leaked list was there.
        list_name = self._own_a_list()
        first_list_row = self.lpr.get_list_row(list_name)

        self.step_capture.mark(2, f"Open Plate page for list: {list_name}")
        view_icon = first_list_row.locator("img[aria-label='View']")
        view_icon.click()
        self.lpr.add_plate_button.first.wait_for(state="visible", timeout=30000)

        self.step_capture.mark(3, "Open filter panel")
        self.lpr.ensure_lpr_filter_panel(list_name)

        self.step_capture.mark(4, "Verify 'Apply' and 'Reset' buttons are visible")
        # The panel is open and usable: its 2 text fields take input, and its 2 buttons can be clicked
        expect(self.page.locator("input[placeholder='Enter Make']")).to_be_editable()
        expect(self.page.locator("input[placeholder='Enter Vehicle Model']")).to_be_editable()
        expect(self.lpr.apply_filter_button.first).to_be_enabled()
        expect(self.lpr.reset_filter_button.first).to_be_enabled()

        self.step_capture.mark(5, "Verify filter panel is open")
        print("[PASS] Successfully opened filter panel")

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.lpr
    def test_no_search_results_view_before_a_filter(self):
        """Verify the Lists page shows no Search Results view before a filter is applied.

        Steps:
        1. Click Admin in the left sidebar, then click LPR.
           Expected: The Lists page opens with the Create List button and no Search Results header.
        """
        self.step_capture.mark(1, "Open the Lists page with no filter applied")
        self.lpr.navigate_to_lpr()
        expect(self.lpr.create_list_button.first).to_be_visible()
        expect(self.lpr.search_results_header).to_have_count(0)
        # the page object's own guard agrees: it refuses the Lists page
        with pytest.raises(Exception, match="Not in Search Results"):
            self.lpr.ensure_in_search_results()
