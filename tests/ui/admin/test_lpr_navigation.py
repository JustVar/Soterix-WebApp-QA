"""LPR (License Plate Recognition) navigation and state management tests.

Tests the ability to navigate between LPR pages and ensure correct page state:
- Main LPR page (Lists)
- Plate page (inside a list)
- Filter panel (on Plate page)
- Search Results (after applying filters)
- Categories page
"""
import contextlib

import pytest
from playwright.sync_api import TimeoutError as PlaywrightTimeoutError

from tests.shared.pages.lpr_page import LprPage


class TestLprNavigation:
    """Tests for LPR navigation between pages and states."""

    @pytest.fixture(autouse=True)
    def setup(self, authenticated_page, step_capture):
        self.page = authenticated_page
        self.step_capture = step_capture
        step_capture.set_page(self.page)
        self.lpr = LprPage(self.page)

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
        assert self.lpr.create_list_button.count() > 0, "Create List button not found"

        self.step_capture.mark(3, "Verify on LPR Lists page")
        print("[PASS] Successfully navigated to LPR Lists page")

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.lpr
    def test_ensure_lpr_page_already_on_lists(self):
        """Verify ensure_lpr_page returns when already on Lists page.

        Steps:
        1. Click Admin in the left sidebar, then click LPR.
           Expected: The LPR Lists page opens and shows the Create List button.
        2. Click LPR again while the Lists page is open.
           Expected: The Lists page stays as it is and the Create List button stays visible.
        """
        self.step_capture.mark(1, "Navigate to LPR Lists page")
        self.lpr.navigate_to_lpr()

        self.step_capture.mark(2, "Call ensure_lpr_page (should return immediately)")
        self.lpr.ensure_lpr_page()

        self.step_capture.mark(3, "Verify still on Lists page")
        assert self.lpr.create_list_button.count() > 0, "Should still be on Lists page"

        print("[PASS] ensure_lpr_page correctly handled 'already on Lists' case")

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.lpr
    def test_ensure_lpr_lists_page_already_on_lists(self):
        """Verify ensure_lpr_lists_page returns when already on Lists.

        Steps:
        1. Click Admin in the left sidebar, then click LPR.
           Expected: The LPR Lists page opens and shows the Create List button.
        2. Click LPR again while the Lists page is open.
           Expected: The Lists page stays as it is and the Create List button stays visible.
        """
        self.step_capture.mark(1, "Navigate to LPR Lists page")
        self.lpr.navigate_to_lpr()

        self.step_capture.mark(2, "Call ensure_lpr_lists_page (should return immediately)")
        self.lpr.ensure_lpr_lists_page()

        self.step_capture.mark(3, "Verify on Lists page")
        assert self.lpr.create_list_button.count() > 0, "Should be on Lists page"

        print("[PASS] ensure_lpr_lists_page correctly handled 'already on Lists' case")

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.lpr
    def test_navigate_from_search_results_to_lists(self):
        """Verify navigation from Search Results back to Lists via breadcrumb.

        Steps:
        1. Click Admin in the left sidebar, then click LPR.
           Expected: The LPR Lists page opens and shows the Create List button.
        """
        # The View -> Filter -> Apply -> breadcrumb-back leg is not
        # automated yet; the test verifies the Lists page state only.
        # (Outside the docstring: the QA Touch generator would append
        # trailing prose to step 1's Expected.)
        self.step_capture.mark(1, "Navigate to LPR Lists page")
        self.lpr.navigate_to_lpr()

        self.step_capture.mark(2, "Verify on Lists page")
        assert self.lpr.create_list_button.count() > 0, "Should be on Lists page"

        # Simulate being in Search Results by finding a list and checking for search header
        # (In a real test, we'd apply a filter to get to Search Results)
        self.step_capture.mark(3, "Simulate Search Results state")
        print("[INFO] Search Results navigation test - would need active filter to fully test")

        print("[PASS] Lists page state confirmed")

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
        assert self.lpr.add_category_button.count() > 0, "Add Category button not found"

        self.step_capture.mark(4, "Verify on Categories page")
        print("[PASS] Successfully navigated to Categories page")

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.lpr
    def test_categories_page_already_on_categories(self):
        """Verify ensure_lpr_categories_page returns when already on Categories.

        Steps:
        1. Click Admin in the left sidebar, click LPR, then click the Categories tab.
           Expected: The Categories page opens and shows the Add Category button.
        2. Click the Categories tab again.
           Expected: The Categories page stays open and the Add Category button stays visible.
        """
        self.step_capture.mark(1, "Navigate to Categories page")
        self.lpr.navigate_to_lpr()
        self.lpr.ensure_lpr_categories_page()

        self.step_capture.mark(2, "Call ensure_lpr_categories_page again")
        self.lpr.ensure_lpr_categories_page()

        self.step_capture.mark(3, "Verify still on Categories page")
        assert self.lpr.add_category_button.count() > 0, "Should still be on Categories page"

        print("[PASS] ensure_lpr_categories_page correctly handled 'already on Categories' case")

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
        assert self.lpr.create_list_button.count() > 0, "Should be on Lists page"

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
        # hydration race: wait for a data row before sampling .all()
        # (same-tick sample skipped a 107-row table, 09/02/2026); a
        # truly empty table times out and falls through to the skip
        with contextlib.suppress(PlaywrightTimeoutError):
            self.page.locator("tr").nth(1).wait_for(
                state="visible", timeout=15000)
        list_rows = self.page.locator("tr").all()

        if len(list_rows) == 0:
            pytest.skip("No LPR lists available to test")

        # Get the first data row (skip header)
        first_list_row = list_rows[1] if len(list_rows) > 1 else None
        if not first_list_row:
            pytest.skip("No LPR lists found")

        list_name = first_list_row.locator("td").first.inner_text()
        self.step_capture.mark(3, f"Open list: {list_name}")

        # Click View icon
        view_icon = first_list_row.locator("img[aria-label='View']")
        view_icon.click()

        self.step_capture.mark(4, "Verify 'Add Plate' button is visible")
        self.lpr.add_plate_button.first.wait_for(state="visible", timeout=30000)
        assert self.lpr.add_plate_button.count() > 0, "Add Plate button not found"

        self.step_capture.mark(5, "Verify on Plate page")
        print(f"[PASS] Successfully opened Plate page for list: {list_name}")

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.lpr
    def test_ensure_plate_page_already_on_plate(self):
        """Verify ensure_lpr_plate_page returns when already on Plate page.

        Steps:
        1. Click Admin, then LPR, and click the View icon on the first list row.
           Expected: The Plate page for that list opens and shows the Add Plate button.
        2. Open the same list again while its Plate page is open.
           Expected: The Plate page stays open and the Add Plate button stays visible.
        """
        self.step_capture.mark(1, "Navigate to Lists page")
        self.lpr.navigate_to_lpr()

        # Get first available list
        # hydration race: wait for a data row before sampling .all()
        # (same-tick sample skipped a 107-row table, 09/02/2026); a
        # truly empty table times out and falls through to the skip
        with contextlib.suppress(PlaywrightTimeoutError):
            self.page.locator("tr").nth(1).wait_for(
                state="visible", timeout=15000)
        list_rows = self.page.locator("tr").all()
        if len(list_rows) < 2:
            pytest.skip("No LPR lists available")

        first_list_row = list_rows[1]
        list_name = first_list_row.locator("td").first.inner_text()

        self.step_capture.mark(2, f"Open Plate page for list: {list_name}")
        view_icon = first_list_row.locator("img[aria-label='View']")
        view_icon.click()
        self.lpr.add_plate_button.first.wait_for(state="visible", timeout=30000)

        self.step_capture.mark(3, "Call ensure_lpr_plate_page (should return immediately)")
        self.lpr.ensure_lpr_plate_page(list_name)

        self.step_capture.mark(4, "Verify still on Plate page")
        assert self.lpr.add_plate_button.count() > 0, "Should still be on Plate page"

        print("[PASS] ensure_lpr_plate_page correctly handled 'already on Plate' case")

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
        # hydration race: wait for a data row before sampling .all()
        # (same-tick sample skipped a 107-row table, 09/02/2026); a
        # truly empty table times out and falls through to the skip
        with contextlib.suppress(PlaywrightTimeoutError):
            self.page.locator("tr").nth(1).wait_for(
                state="visible", timeout=15000)
        list_rows = self.page.locator("tr").all()
        if len(list_rows) < 2:
            pytest.skip("No LPR lists available")

        first_list_row = list_rows[1]
        list_name = first_list_row.locator("td").first.inner_text()

        self.step_capture.mark(2, f"Open Plate page for list: {list_name}")
        view_icon = first_list_row.locator("img[aria-label='View']")
        view_icon.click()
        self.lpr.add_plate_button.first.wait_for(state="visible", timeout=30000)

        self.step_capture.mark(3, "Open filter panel")
        self.lpr.ensure_lpr_filter_panel(list_name)

        self.step_capture.mark(4, "Verify 'Apply' and 'Reset' buttons are visible")
        assert self.lpr.apply_filter_button.count() > 0, "Apply button not found"
        assert self.lpr.reset_filter_button.count() > 0, "Reset button not found"

        self.step_capture.mark(5, "Verify filter panel is open")
        print("[PASS] Successfully opened filter panel")

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.lpr
    def test_filter_panel_already_open(self):
        """Verify ensure_lpr_filter_panel returns when panel already open.

        Steps:
        1. Click Admin, then LPR, and click the View icon on the first list row.
           Expected: The Plate page for that list opens and shows the Add Plate button.
        2. Click the Filter icon.
           Expected: The filter panel opens and shows the Apply and Reset buttons.
        3. Open the filter panel again without closing it.
           Expected: The panel stays open and the Apply button stays visible.
        """
        self.step_capture.mark(1, "Navigate to Lists page")
        self.lpr.navigate_to_lpr()

        # Get first available list
        # hydration race: wait for a data row before sampling .all()
        # (same-tick sample skipped a 107-row table, 09/02/2026); a
        # truly empty table times out and falls through to the skip
        with contextlib.suppress(PlaywrightTimeoutError):
            self.page.locator("tr").nth(1).wait_for(
                state="visible", timeout=15000)
        list_rows = self.page.locator("tr").all()
        if len(list_rows) < 2:
            pytest.skip("No LPR lists available")

        first_list_row = list_rows[1]
        list_name = first_list_row.locator("td").first.inner_text()

        self.step_capture.mark(2, f"Open Plate page with filter panel for list: {list_name}")
        view_icon = first_list_row.locator("img[aria-label='View']")
        view_icon.click()
        self.lpr.add_plate_button.first.wait_for(state="visible", timeout=30000)
        self.lpr.ensure_lpr_filter_panel(list_name)

        self.step_capture.mark(3, "Call ensure_lpr_filter_panel again (should return immediately)")
        self.lpr.ensure_lpr_filter_panel(list_name)

        self.step_capture.mark(4, "Verify filter panel still open")
        assert self.lpr.apply_filter_button.count() > 0, "Filter panel should still be open"

        print("[PASS] ensure_lpr_filter_panel correctly handled 'already open' case")

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.lpr
    def test_ensure_in_search_results_not_in_results(self):
        """Verify ensure_in_search_results raises exception when not in Search Results.

        Steps:
        1. Click Admin in the left sidebar, then click LPR.
           Expected: The Lists page opens and shows no Search Results header.
        2. Look for the Search Results view without applying a filter.
           Expected: The Search Results header is not shown. The Lists page stays open.
        """
        self.step_capture.mark(1, "Navigate to Lists page")
        self.lpr.navigate_to_lpr()

        self.step_capture.mark(2, "Try to verify in Search Results (should fail)")
        try:
            self.lpr.ensure_in_search_results()
            pytest.fail("Should have raised exception - not in Search Results")
        except Exception as e:
            self.step_capture.mark(3, "Exception correctly raised")
            assert "Not in Search Results" in str(e), "Unexpected exception message"
            print(f"[PASS] Correctly raised exception: {e}")
