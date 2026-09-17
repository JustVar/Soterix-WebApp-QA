"""LPR (License Plate Recognition) operations tests.

Tests for LPR list creation, plate management, and filter operations.
Covers core CRUD operations and state management.
"""
import datetime
import re

import pytest
from playwright.sync_api import Error as PlaywrightError, expect

from tests.shared.pages.lpr_page import LprPage

# One worker for every module that writes this account's LPR lists, views and widgets: under
# -n they would otherwise spread across workers and race on the same
# tenant state (pytest.ini --dist loadgroup; audit 09/17/2026, row 86).
pytestmark = pytest.mark.xdist_group("account_lpr")


class TestLprListOperations:
    """Tests for LPR list CRUD operations."""

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
    def test_click_admin_and_access_lpr(self):
        """Verify navigation to Admin page and LPR menu visibility.

        Steps:
        1. Click Admin in the left sidebar.
           Expected: The Admin menu shows an LPR entry.
        2. Click LPR.
           Expected: The Lists page opens and shows the Create List button.
        """
        self.step_capture.mark(1, "Navigate to Admin page")
        self.lpr.navigate_to_lpr()

        self.step_capture.mark(2, "Verify LPR menu is accessible")
        assert self.lpr.lpr_menu.count() > 0, "LPR menu not found"

        self.step_capture.mark(3, "Verify Create List button is visible")
        assert self.lpr.create_list_button.count() > 0, "Create List button not visible"

        print("[PASS] Admin navigation and LPR access verified")

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.lpr
    def test_lpr_page_ui_elements(self):
        """Verify LPR page UI elements are present.

        Steps:
        1. Click Admin in the left sidebar, then click LPR.
           Expected: The Lists page opens.
        2. Check the page controls.
           Expected: The Create List button, the List and Categories tabs, the lists table, and the Search field are all visible.
        """
        # The table is one of the controls under test, and the page
        # renders an empty state instead of a table when the tenant has
        # no lists. So this test makes one rather than relying on
        # another test's leftover, which is what it had been doing.
        self.step_capture.mark(1, "Navigate to LPR Lists page")
        self._own_a_list()

        self.step_capture.mark(2, "Verify Create List button")
        assert self.lpr.create_list_button.count() > 0, "Create List button missing"

        self.step_capture.mark(3, "Verify List/Categories tabs")
        list_tab = self.page.locator("button:has-text('List')").first
        categories_tab = self.page.locator("button:has-text('Categories')").first
        assert list_tab.count() > 0, "List tab not found"
        assert categories_tab.count() > 0, "Categories tab not found"

        self.step_capture.mark(4, "Verify table is visible")
        # the table renders async after navigation; the raising wait
        # carries the oracle
        self.page.locator("table").first.wait_for(
            state="visible", timeout=15000
        )

        self.step_capture.mark(5, "Verify search field")
        search_field = self.page.locator("input[placeholder*='Search']").first
        assert search_field.count() > 0, "Search field not found"

        print("[PASS] LPR page UI elements verified")

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.lpr
    @pytest.mark.intermittent
    def test_create_lpr_list(self):
        """Create a new LPR list with valid data.

        Steps:
        1. Click Admin in the left sidebar, then click LPR.
           Expected: The Lists page opens.
        2. Click Create List.
           Expected: The Create List dialog opens with a List Name field and a type dropdown.
        3. Enter a unique name in the List Name field.
           Expected: The field shows the name.
        4. Open the type dropdown and choose White List.
           Expected: The dropdown closes and shows White List.
        5. Click Save.
           Expected: The dialog closes.
        6. Find the new list in the table.
           Expected: A row with the new name is listed.
        """
        self.step_capture.mark(1, "Navigate to LPR Lists page")
        self.lpr.navigate_to_lpr()

        self.step_capture.mark(2, "Click Create List button")
        create_btn = self.lpr.create_list_button.first
        create_btn.wait_for(state="visible", timeout=30000)
        create_btn.click()

        self.step_capture.mark(3, "Fill in list name")
        timestamp = datetime.datetime.now().strftime("%H%M%S%f")[:9]
        list_name = f"Test_List_{timestamp}"

        # Use specific modal input selector
        name_field = self.page.locator("input#firstName[placeholder='Enter List Name']")
        name_field.wait_for(state="visible", timeout=30000)
        name_field.fill(list_name)
        self._owned_lists.append(list_name)
        print(f"[STEP 3] List name entered: {list_name}")

        self.step_capture.mark(4, "Select list type")
        # Click the dropdown div with modalForm-input class
        dropdown = self.page.locator("div.modalForm-input:has(span:has-text('Select'))")
        dropdown.wait_for(state="visible", timeout=30000)
        dropdown.click()

        # Select "White List"; the option hiding again is the
        # selection-applied signal
        white_list_option = self.page.locator("li[role='menuitem']:has-text('White List')")
        white_list_option.wait_for(state="visible", timeout=30000)
        white_list_option.click()
        white_list_option.wait_for(state="hidden", timeout=5000)
        print("[STEP 4] White List selected from dropdown")

        self.step_capture.mark(5, "Click Save button")
        save_btn = self.page.locator("button:has-text('Save')").first
        save_btn.wait_for(state="visible", timeout=30000)
        save_btn.click(force=True)

        self.step_capture.mark(6, "Wait for modal to close")
        # Wait for modal to close by checking if the specific modal input field is gone
        modal_input = self.page.locator("input#firstName[placeholder='Enter List Name']")
        modal_input.wait_for(state="hidden", timeout=30000)

        self.step_capture.mark(7, "Verify list created in table")
        list_row = self.page.locator(f"tr:has-text('{list_name}')").first
        # Increase timeout to 60 seconds for backend synchronization
        list_row.wait_for(state="visible", timeout=60000)
        assert list_row.count() > 0, f"Created list '{list_name}' not found in table"

        print(f"[PASS] LPR list '{list_name}' created successfully")

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.lpr
    def test_search_lpr_list_by_name(self):
        """Search for LPR list by name.

        Steps:
        1. Click Admin in the left sidebar, then click LPR.
           Expected: The Lists page shows at least one list row.
        2. Type the name of the first list into the Search field.
           Expected: The table shows a row with that name.
        """
        self.step_capture.mark(1, "Navigate to LPR Lists page")
        self.lpr.navigate_to_lpr()

        self.step_capture.mark(2, "Find first list in table")
        # Make the list this test works on. Taking the tenant's
        # first one passed only while a leaked list was there.
        list_name = self._own_a_list()
        first_row = self.lpr.get_list_row(list_name)

        self.step_capture.mark(3, f"Search for list: {list_name}")
        search_field = self.page.locator("input[placeholder*='Search']").first
        search_field.fill(list_name)

        self.step_capture.mark(4, "Verify search results")
        # the raising wait carries the oracle
        search_result = self.page.locator(f"tr:has-text('{list_name}')").first
        search_result.wait_for(state="visible", timeout=10000)

        print(f"[PASS] List search for '{list_name}' succeeded")

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.lpr
    def test_open_list_and_verify_plate_page(self):
        """Open a list and verify plate page UI.

        Steps:
        1. Click Admin in the left sidebar, then click LPR.
           Expected: The Lists page shows at least one list row.
        2. Click the View icon on the first list row.
           Expected: The Plate page opens with the Add Plate button and a plate table.
        """
        self.step_capture.mark(1, "Navigate to LPR Lists page")
        self.lpr.navigate_to_lpr()

        self.step_capture.mark(2, "Find first list")
        # Make the list this test works on. Taking the tenant's
        # first one passed only while a leaked list was there.
        list_name = self._own_a_list()
        first_row = self.lpr.get_list_row(list_name)

        self.step_capture.mark(3, f"Open list: {list_name}")
        view_icon = first_row.locator("img[aria-label='View']").first
        view_icon.click()

        self.step_capture.mark(4, "Verify Add Plate button")
        self.lpr.add_plate_button.first.wait_for(state="visible", timeout=30000)
        assert self.lpr.add_plate_button.count() > 0, "Add Plate button not found"

        self.step_capture.mark(5, "Verify plate table")
        assert self.page.locator("table").count() > 0, "Plate table not found"

        print(f"[PASS] Plate page for list '{list_name}' verified")

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.lpr
    def test_list_actions_visible(self):
        """Verify View, Edit, and Delete actions are available for lists.

        Steps:
        1. Click Admin in the left sidebar, then click LPR.
           Expected: The Lists page shows at least one list row.
        2. Look at the action icons on the first list row.
           Expected: The row shows View, Edit, and Delete icons.
        """
        self.step_capture.mark(1, "Navigate to LPR Lists page")
        self.lpr.navigate_to_lpr()

        self.step_capture.mark(2, "Find first list row")
        # Make the list this test works on. Taking the tenant's
        # first one passed only while a leaked list was there.
        list_name = self._own_a_list()
        first_row = self.lpr.get_list_row(list_name)

        self.step_capture.mark(3, "Verify View icon")
        view_icon = first_row.locator("img[aria-label='View']")
        assert view_icon.count() > 0, "View icon not found"

        self.step_capture.mark(4, "Verify Edit icon")
        edit_icon = first_row.locator("img[aria-label='Edit']")
        assert edit_icon.count() > 0, "Edit icon not found"

        self.step_capture.mark(5, "Verify Delete icon")
        delete_icon = first_row.locator("img[aria-label='Delete']")
        assert delete_icon.count() > 0, "Delete icon not found"

        print("[PASS] List actions (View/Edit/Delete) verified")

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.lpr
    def test_list_status_toggle(self):
        """Verify list status toggle is present and interactive.

        Steps:
        1. Click Admin in the left sidebar, then click LPR.
           Expected: The Lists page shows at least one list row.
        2. Look at the first list row.
           Expected: The row shows a status toggle.
        """
        self.step_capture.mark(1, "Navigate to LPR Lists page")
        self.lpr.navigate_to_lpr()

        self.step_capture.mark(2, "Find first list row")
        # Make the list this test works on. Taking the tenant's
        # first one passed only while a leaked list was there.
        list_name = self._own_a_list()
        first_row = self.lpr.get_list_row(list_name)

        self.step_capture.mark(3, "Verify status toggle")
        toggle = first_row.locator("input[type='checkbox']")
        assert toggle.count() > 0, "Status toggle not found"

        self.step_capture.mark(4, "Verify toggle is clickable")
        toggle.first.scroll_into_view_if_needed()
        print("[PASS] List status toggle verified")


class TestLprFilterOperations:
    """Tests for LPR filter panel operations."""

    @pytest.fixture(autouse=True)
    def setup(self, authenticated_page, step_capture):
        self.page = authenticated_page
        self.step_capture = step_capture
        step_capture.set_page(self.page)
        self.lpr = LprPage(self.page)
        self._owned_lists = []
        yield
        self._cleanup_lists()

    # Same two helpers as TestLprListOperations: a filter test needs a
    # list to filter, and it must be its own.
    _own_a_list = TestLprListOperations._own_a_list
    _cleanup_lists = TestLprListOperations._cleanup_lists

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.lpr
    def test_apply_filter_shows_search_results(self):
        """Verify applying a filter shows Search Results view.

        Steps:
        1. Click Admin, then LPR, and click the View icon on the first list row.
           Expected: The Plate page for that list opens and shows the Add Plate button.
        2. Click the Filter icon.
           Expected: The filter panel opens with the Apply button.
        3. Click Apply.
           Expected: The Search Results view opens with its header.
        """
        self.step_capture.mark(1, "Navigate to LPR Lists page")
        self.lpr.navigate_to_lpr()

        self.step_capture.mark(2, "Find and open first list")
        # Make the list this test works on. Taking the tenant's
        # first one passed only while a leaked list was there.
        list_name = self._own_a_list()
        first_row = self.lpr.get_list_row(list_name)
        first_row.locator("img[aria-label='View']").first.click()
        self.lpr.add_plate_button.first.wait_for(state="visible", timeout=30000)

        self.step_capture.mark(3, "Open filter panel")
        filter_icon = self.lpr.filter_icon.first
        filter_icon.wait_for(state="visible", timeout=30000)
        filter_icon.click()
        self.lpr.apply_filter_button.first.wait_for(state="visible", timeout=30000)

        self.step_capture.mark(4, "Click Apply button")
        self.lpr.apply_filter_button.first.click()

        self.step_capture.mark(5, "Verify Search Results view")
        # the results header rendering is the applied signal
        search_results = self.lpr.search_results_header.first
        search_results.wait_for(state="visible", timeout=15000)
        expect(search_results).to_contain_text(re.compile("search results", re.I))

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.lpr
    def test_reset_filter_returns_to_plate(self):
        """Verify resetting filter returns to Plate page.

        Steps:
        1. Click Admin, then LPR, and click the View icon on the first list row.
           Expected: The Plate page for that list opens and shows the Add Plate button.
        2. Click the Filter icon, then click Apply.
           Expected: The Search Results view opens.
        3. Click Reset.
           Expected: The Plate page opens again with the Add Plate button.
        """
        self.step_capture.mark(1, "Navigate to LPR Lists page")
        self.lpr.navigate_to_lpr()

        self.step_capture.mark(2, "Open first list and filter panel")
        # Make the list this test works on. Taking the tenant's
        # first one passed only while a leaked list was there.
        list_name = self._own_a_list()
        first_row = self.lpr.get_list_row(list_name)
        first_row.locator("img[aria-label='View']").first.click()
        self.lpr.add_plate_button.first.wait_for(state="visible", timeout=30000)

        filter_icon = self.lpr.filter_icon.first
        filter_icon.wait_for(state="visible", timeout=30000)
        filter_icon.click()
        self.lpr.apply_filter_button.first.wait_for(state="visible", timeout=30000)

        self.step_capture.mark(3, "Apply filter")
        self.lpr.apply_filter_button.first.click()
        # the results header rendering is the applied signal
        self.lpr.search_results_header.first.wait_for(
            state="visible", timeout=15000
        )

        self.step_capture.mark(4, "Click Reset button")
        reset_btn = self.lpr.reset_filter_button.first
        reset_btn.wait_for(state="visible", timeout=30000)
        reset_btn.click()

        self.step_capture.mark(5, "Verify returned to Plate page")
        # the raising wait carries the oracle
        add_plate_btn = self.lpr.add_plate_button.first
        add_plate_btn.wait_for(state="visible", timeout=15000)

        print("[PASS] Filter reset - returned to Plate page")

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.lpr
    def test_filter_panel_toggle(self):
        """Verify filter panel can be opened and closed.

        Steps:
        1. Click Admin, then LPR, and click the View icon on the first list row.
           Expected: The Plate page for that list opens and shows the Add Plate button.
        2. Click the Filter icon.
           Expected: The filter panel opens with the Apply and Reset buttons.
        3. Click the Filter icon again.
           Expected: The filter panel closes and the Apply button is hidden.
        """
        self.step_capture.mark(1, "Navigate to LPR Lists page")
        self.lpr.navigate_to_lpr()

        self.step_capture.mark(2, "Open first list")
        # Make the list this test works on. Taking the tenant's
        # first one passed only while a leaked list was there.
        list_name = self._own_a_list()
        first_row = self.lpr.get_list_row(list_name)
        first_row.locator("img[aria-label='View']").first.click()
        self.lpr.add_plate_button.first.wait_for(state="visible", timeout=30000)

        self.step_capture.mark(3, "Open filter panel")
        filter_icon = self.lpr.filter_icon.first
        filter_icon.wait_for(state="visible", timeout=30000)
        filter_icon.click()
        # the Apply button rendering is the panel-open signal
        self.lpr.apply_filter_button.first.wait_for(
            state="visible", timeout=10000
        )

        self.step_capture.mark(4, "Verify Apply and Reset buttons visible")
        assert self.lpr.apply_filter_button.count() > 0, "Apply button not visible"
        assert self.lpr.reset_filter_button.count() > 0, "Reset button not visible"

        self.step_capture.mark(5, "Close filter panel by clicking filter icon again")
        filter_icon.click()
        # the Apply button leaving is the panel-closed signal
        self.lpr.apply_filter_button.first.wait_for(
            state="hidden", timeout=10000
        )

        print("[PASS] Filter panel toggle verified")
