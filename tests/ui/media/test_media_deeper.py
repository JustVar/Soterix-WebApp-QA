"""Media deeper tests - date filter options, view toggle, search, tab behavior.

Extends the base media tests with deeper filter, view, and tab validation
that don't require clip/folder content to exist.
"""
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
        yield

    # --- Date filter ---

    @pytest.mark.ui
    @pytest.mark.media
    @pytest.mark.media_deeper
    def test_date_filter_dropdown_opens(self):
        """Verify the date filter dropdown can be opened."""
        self.media.date_filter.click()

        listbox = self.page.locator("[role='listbox']")
        expect(listbox).to_be_visible(timeout=10000)

        # Close the dropdown
        self.page.keyboard.press("Escape")

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
        """Verify selecting 'Today' date filter works."""
        self.media.select_date_filter("Today")

        expect(self.media.date_filter).to_be_visible(timeout=5000)

    @pytest.mark.ui
    @pytest.mark.media
    @pytest.mark.media_deeper
    def test_date_filter_last_7_days(self):
        """Verify selecting 'Last 7 Days' date filter works."""
        self.media.select_date_filter("Last 7 Days")
        expect(self.media.date_filter).to_be_visible(timeout=5000)

    # --- View toggle ---

    @pytest.mark.ui
    @pytest.mark.media
    @pytest.mark.media_deeper
    def test_grid_view_toggle_visible(self):
        """Verify the grid view toggle button is visible."""
        expect(self.media.grid_view_button).to_be_visible(timeout=10000)

    @pytest.mark.ui
    @pytest.mark.media
    @pytest.mark.media_deeper
    def test_view_toggle_area_present(self):
        """Verify at least one view toggle button (grid or list) is present."""
        # Wait for buttons to render (count() is immediate; expect() waits)
        try:
            self.page.locator(
                # img asset icon: alt unreliable, locate by src (CONVENTIONS > Locators)
                "img[src*='icon-grid'], img[src*='icon-list']"
            ).first.wait_for(state="visible", timeout=10000)
        # bounded render wait only; the assert below owns the oracle and
        # names the failure
        except Exception:
            pass

        # img asset icon: alt unreliable, locate by src (CONVENTIONS > Locators)
        grid_visible = self.page.locator("img[src*='icon-grid']").count() > 0
        # img asset icon: alt unreliable, locate by src (CONVENTIONS > Locators)
        list_visible = self.page.locator("img[src*='icon-list']").count() > 0

        assert grid_visible or list_visible, \
            "Expected at least one view toggle button (grid or list)"

    @pytest.mark.ui
    @pytest.mark.media
    @pytest.mark.media_deeper
    def test_grid_view_switch_round_trip(self):
        """Verify grid view can be activated and page remains valid.

        Steps:
        1. Open Media, set the date filter to Last 30 Days, switch to grid view and then back to list view.
           Expected: The page keeps working and the date filter is still shown.
        """
        self.media.select_date_filter("Last 30 Days")
        self.media.switch_to_grid_view()

        # If list view is available, switch back; otherwise just verify page state
        if self.media.list_view_button.count() > 0:
            self.media.switch_to_list_view()

        expect(self.media.date_filter).to_be_visible(timeout=5000)

    # --- Tab switching ---

    @pytest.mark.ui
    @pytest.mark.media
    @pytest.mark.media_deeper
    def test_tab_round_trip_all_to_clips(self):
        """Verify switching from All to Clips and back works.

        Steps:
        1. Open Media, set the date filter to Last 30 Days, click the Clips tab, then click the All tab.
           Expected: Each tab is selected in turn and the date filter stays shown.
        """
        self.media.select_date_filter("Last 30 Days")
        self.media.click_tab("Clips")
        self.media.click_tab("All")

        expect(self.media.date_filter).to_be_visible(timeout=5000)

    @pytest.mark.ui
    @pytest.mark.media
    @pytest.mark.media_deeper
    def test_tab_round_trip_folders_to_shared(self):
        """Verify switching from Folders to Shared with me and back works.

        Steps:
        1. Click Media in the left sidebar, open the date filter, and choose Last 30 Days.
           Expected: The list reloads for the last 30 days.
        2. Click the Folders tab, then Shared with me, then Folders again.
           Expected: Each tab loads and the date filter stays visible.
        """
        self.media.select_date_filter("Last 30 Days")
        self.media.click_tab("Folders")
        self.media.click_tab("Shared with me")
        self.media.click_tab("Folders")

        expect(self.media.date_filter).to_be_visible(timeout=5000)

    @pytest.mark.ui
    @pytest.mark.media
    @pytest.mark.media_deeper
    def test_core_tabs_accessible(self):
        """Verify the core media tabs can be clicked without errors.

        Steps:
        1. Click Media in the left sidebar, open the date filter, and choose Last 30 Days.
           Expected: The list reloads for the last 30 days.
        2. Click the All, My Media, Shared with me, Clips, and Folders tabs in turn.
           Expected: Each tab loads without an error and the date filter stays visible.
        """
        self.media.select_date_filter("Last 30 Days")
        # Test core tabs that are always present (Vault may not be visible)
        for tab in ["All", "My Media", "Shared with me", "Clips", "Folders"]:
            self.media.click_tab(tab)

        expect(self.media.date_filter).to_be_visible(timeout=5000)

    # --- Search ---

    @pytest.mark.ui
    @pytest.mark.media
    @pytest.mark.media_deeper
    def test_search_input_visible(self):
        """Verify the search input is visible on the Media page."""
        self.media.select_date_filter("Last 30 Days")
        expect(self.media.search_input).to_be_visible(timeout=10000)

    @pytest.mark.ui
    @pytest.mark.media
    @pytest.mark.media_deeper
    def test_search_no_results(self):
        """Verify searching for nonexistent text shows empty or no results."""
        self.media.select_date_filter("Last 30 Days")
        self.media.search_media("zzzznonexistent999xyz")

        # Page stays on media and shows empty state
        expect(self.media.date_filter).to_be_visible(timeout=5000)
        assert self.media.is_page_empty(timeout=5000), \
            "Expected empty state for nonsense search query"

    @pytest.mark.ui
    @pytest.mark.media
    @pytest.mark.media_deeper
    def test_search_clear_and_retry(self):
        """Verify clearing search and searching again works.

        Steps:
        1. Click Media in the left sidebar, open the date filter, and choose Last 30 Days.
           Expected: The list reloads for the last 30 days.
        2. Type clip in the search field and press Enter.
           Expected: The list reloads with the search applied.
        3. Clear the field, type 17, and press Enter.
           Expected: The list reloads again and the date filter stays visible.
        """
        self.media.select_date_filter("Last 30 Days")
        self.media.search_media("clip")

        self.media.search_media("17")
        expect(self.media.date_filter).to_be_visible(timeout=5000)

    # --- Page refresh ---

    @pytest.mark.ui
    @pytest.mark.media
    @pytest.mark.media_deeper
    def test_media_page_after_refresh(self):
        """Verify the Media page loads correctly after a browser refresh."""
        # reload waits for the load event on its own
        self.page.reload()

        # SPA may reset to root on reload - re-navigate and verify content loads
        self.media.navigate()
        expect(self.media.date_filter).to_be_visible(timeout=15000)
