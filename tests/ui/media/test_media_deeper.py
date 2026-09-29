"""Media deeper tests - date filter options, view toggle, search, tab behavior.

Extends the base media tests with deeper filter, view, and tab validation
that don't require clip/folder content to exist. Every check reads a value
the page shows: the filter's text and options, the toggle's pressed state
and the item layout, the selected tab's paint, the names a search returns
(all measured on the app).
"""
import re

import pytest
from playwright.sync_api import expect

from tests.shared.pages.media_page import MediaPage


class TestMediaDeeper:
    """Deeper tests for the Media page."""

    @pytest.fixture(autouse=True)
    def setup(self, authenticated_page):
        self.page = authenticated_page
        self.media = MediaPage(self.page)
        self.media.navigate()
        return

    def _items_or_skip(self) -> list[str]:
        """The listed item names, or a skip that says the list is empty.

        The page is proved up first (the date filter is on screen), so an
        empty list is the tenant's state, not a broken page.
        """
        expect(self.media.date_filter).to_be_visible(timeout=10000)
        names = self.media.item_names()
        if not names:
            assert self.media.is_page_empty(timeout=5000), (
                "the Media list shows neither items nor its empty state")
            pytest.skip("the Media list is empty for the last 30 days on this tenant "
                        "(the empty state is shown), so there is nothing to measure")
        return names

    # --- Date filter ---

    @pytest.mark.ui
    @pytest.mark.media
    @pytest.mark.media_deeper
    def test_date_filter_dropdown_opens(self):
        """Verify the date filter dropdown opens on the page's date ranges.

        Steps:
        1. Open Media and click the date filter.
           Expected: The list opens and offers Today, Yesterday, Last 7 Days, Last 30 Days and Custom, in that order.
        """
        options = self.media.date_options()
        assert options == list(MediaPage.DATE_RANGES), (
            f"the date filter offers {options}, expected {list(MediaPage.DATE_RANGES)}")

    @pytest.mark.ui
    @pytest.mark.media
    @pytest.mark.media_deeper
    def test_date_filter_has_options(self):
        """Verify the date filter dropdown has multiple filter options.

        Steps:
        1. Open Media and open the date filter dropdown.
           Expected: The dropdown offers at least three date ranges.
        """
        self.media.date_filter.click()
        listbox = self.page.locator("[role='listbox']")
        listbox.wait_for(state="visible", timeout=10000)
        options = listbox.locator("li[role='option']")
        count = options.count()
        assert count >= 3, f"Expected at least 3 date filter options, got {count}"
        self.page.keyboard.press("Escape")

    @pytest.mark.ui
    @pytest.mark.media
    @pytest.mark.media_deeper
    def test_date_filter_today(self):
        """Verify selecting 'Today' date filter works.

        Steps:
        1. Open Media, choose Last 7 Days, then choose Today.
           Expected: The date filter reads Today again.
        """
        self.media.select_date_filter("Last 7 Days")
        expect(self.media.date_filter).to_have_text("Last 7 Days", timeout=5000)
        self.media.select_date_filter("Today")
        expect(self.media.date_filter).to_have_text("Today", timeout=5000)

    @pytest.mark.ui
    @pytest.mark.media
    @pytest.mark.media_deeper
    def test_date_filter_last_7_days(self):
        """Verify selecting 'Last 7 Days' date filter works.

        Steps:
        1. Open Media and choose Last 7 Days.
           Expected: The date filter reads Last 7 Days instead of Today.
        """
        self.media.select_date_filter("Last 7 Days")
        expect(self.media.date_filter).to_have_text("Last 7 Days", timeout=5000)

    # --- View toggle ---

    @pytest.mark.ui
    @pytest.mark.media
    @pytest.mark.media_deeper
    def test_grid_view_toggle_visible(self):
        """Verify the view toggle starts in list view.

        Steps:
        1. Open Media and read the view toggle.
           Expected: The list (table) button reads pressed and the grid button does not.
        """
        expect(self.media.list_view_button).to_have_attribute("aria-pressed", "true", timeout=10000)
        expect(self.media.grid_view_button).to_have_attribute("aria-pressed", "false")

    @pytest.mark.ui
    @pytest.mark.media
    @pytest.mark.media_deeper
    def test_view_toggle_area_present(self):
        """Verify the view toggle offers exactly the list and grid buttons.

        Steps:
        1. Open Media and read the view toggle group.
           Expected: It holds a table button and a grid button, one of them pressed.
        """
        expect(self.media.list_view_button).to_be_visible(timeout=10000)
        expect(self.media.grid_view_button).to_be_visible()
        pressed = [self.media.list_view_button.get_attribute("aria-pressed"),
                   self.media.grid_view_button.get_attribute("aria-pressed")]
        assert pressed.count("true") == 1, f"table/grid pressed states read {pressed}"

    @pytest.mark.ui
    @pytest.mark.media
    @pytest.mark.media_deeper
    def test_grid_view_switch_round_trip(self):
        """Verify grid view can be activated and the list view comes back.

        Steps:
        1. Open Media, set the date filter to Last 30 Days, switch to grid view and then back to list view.
           Expected: The items move from one column into several and back into one; the pressed button follows.
        """
        self.media.select_date_filter("Last 30 Days")
        self._items_or_skip()
        assert self.media.view_columns() == 1, "the list view does not lay the items out in one column"
        self.media.switch_to_grid_view()
        columns = self.media.view_columns()
        assert columns > 1, f"the grid view lays the items out in {columns} column(s)"
        self.media.switch_to_list_view()
        assert self.media.view_columns() == 1, "back in list view the items are not in one column"

    # --- Tab switching ---

    @pytest.mark.ui
    @pytest.mark.media
    @pytest.mark.media_deeper
    def test_tab_round_trip_all_to_clips(self):
        """Verify switching from All to Clips and back works.

        Steps:
        1. Open Media, set the date filter to Last 30 Days, click the Clips tab, then click the All tab.
           Expected: Clips is painted as selected after the first click, the type row's All after the second, and the date filter still reads Last 30 Days.
        """
        self.media.select_date_filter("Last 30 Days")
        self.media.click_tab("Clips")
        self.media.expect_tab_selected("Clips")
        # the type row's All, not the scope button above it: the scope
        # buttons and the type tabs select independently (measured 09/12/2026)
        self.media.click_tab("All (types)")
        self.media.expect_tab_selected("All (types)")
        assert not self.media.tab_is_selected("Clips"), "Clips stays painted as selected beside All"
        expect(self.media.date_filter).to_have_text("Last 30 Days")

    @pytest.mark.ui
    @pytest.mark.media
    @pytest.mark.media_deeper
    def test_tab_round_trip_folders_to_shared(self):
        """Verify switching from Folders to Shared with me and back works.

        Steps:
        1. Click Media in the left sidebar, open the date filter, and choose Last 30 Days.
           Expected: The date filter reads Last 30 Days.
        2. Click the Folders tab, then Shared with me, then Folders again.
           Expected: Each tab is painted as selected in turn and the date filter still reads Last 30 Days.
        """
        self.media.select_date_filter("Last 30 Days")
        for tab in ("Folders", "Shared with me", "Folders"):
            self.media.click_tab(tab)
            self.media.expect_tab_selected(tab)
        expect(self.media.date_filter).to_have_text("Last 30 Days")

    @pytest.mark.ui
    @pytest.mark.media
    @pytest.mark.media_deeper
    def test_core_tabs_accessible(self):
        """Verify the core media tabs can be selected in turn.

        Steps:
        1. Click Media in the left sidebar, open the date filter, and choose Last 30 Days.
           Expected: The date filter reads Last 30 Days.
        2. Click the All, My Media, Shared with me, Clips, and Folders tabs in turn.
           Expected: Each tab is painted as selected after its click, and each shows items or its empty state.
        """
        self.media.select_date_filter("Last 30 Days")
        # Test core tabs that are always present (Vault may not be visible)
        for tab in ["All", "My Media", "Shared with me", "Clips", "Folders"]:
            self.media.click_tab(tab)
            self.media.expect_tab_selected(tab)
            if not self.media.item_names():
                expect(self.media.no_results_text).to_have_text(MediaPage.EMPTY_STATE, timeout=10000)

    # --- Search ---

    @pytest.mark.ui
    @pytest.mark.media
    @pytest.mark.media_deeper
    def test_search_input_visible(self):
        """Verify the search field on the Media page.

        Steps:
        1. Open Media and set the date filter to Last 30 Days.
           Expected: The search field is shown, empty, with the placeholder "Search by title, tags, sites, etc.".
        """
        self.media.select_date_filter("Last 30 Days")
        expect(self.media.search_input).to_be_visible(timeout=10000)
        expect(self.media.search_input).to_have_value("")
        expect(self.media.search_input).to_have_attribute("placeholder", MediaPage.SEARCH_PLACEHOLDER)

    @pytest.mark.ui
    @pytest.mark.media
    @pytest.mark.media_deeper
    def test_search_no_results(self):
        """Verify searching for nonexistent text shows the empty state.

        Steps:
        1. Open Media, set the date filter to Last 30 Days and search for zzzznonexistent999xyz.
           Expected: No items are listed and the page says "No results found for selected criteria".
        """
        self.media.select_date_filter("Last 30 Days")
        self.media.search_media("zzzznonexistent999xyz")
        expect(self.media.no_results_text).to_have_text(MediaPage.EMPTY_STATE, timeout=10000)
        assert self.media.item_names() == [], "items are listed beside the empty state"

    @pytest.mark.ui
    @pytest.mark.media
    @pytest.mark.media_deeper
    def test_search_clear_and_retry(self):
        """Verify clearing search and searching again works.

        Steps:
        1. Click Media in the left sidebar, open the date filter, and choose Last 30 Days.
           Expected: The list shows items.
        2. Type the first item's name in the search field and press Enter.
           Expected: The list narrows to items carrying that name.
        3. Clear the field and press Enter.
           Expected: The full list comes back with the same number of items as before.
        """
        self.media.select_date_filter("Last 30 Days")
        names = self._items_or_skip()
        query = names[0]
        self.media.search_media(query)
        results = self.media.item_names()
        assert results, f"searching {query!r} returned nothing"
        assert all(query.lower() in n.lower() for n in results), (
            f"searching {query!r} returned {results}")
        self.media.search_media("")
        expect(self.media.search_input).to_have_value("")
        restored = self.media.item_names()
        assert len(restored) == len(names), (
            f"clearing the search lists {len(restored)} items, {len(names)} were listed before")

    # --- Page refresh ---

    @pytest.mark.ui
    @pytest.mark.media
    @pytest.mark.media_deeper
    def test_media_page_after_refresh(self):
        """Verify the Media page loads correctly after a browser refresh.

        Steps:
        1. On the Media page, refresh the browser and open Media again.
           Expected: The address ends in /media and the date filter reads Today, its default.
        """
        # reload waits for the load event on its own
        self.page.reload()
        # SPA may reset to root on reload - re-navigate and verify content loads
        self.media.navigate()
        expect(self.page).to_have_url(re.compile(r"/media/?$"))
        expect(self.media.date_filter).to_have_text("Today", timeout=15000)
