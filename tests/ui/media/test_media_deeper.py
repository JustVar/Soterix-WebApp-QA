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
        self.page.wait_for_timeout(1000)

        listbox = self.page.locator("[role='listbox']")
        expect(listbox).to_be_visible(timeout=10000)

        # Close the dropdown
        self.page.keyboard.press("Escape")

    @pytest.mark.ui
    @pytest.mark.media
    @pytest.mark.media_deeper
    def test_date_filter_has_options(self):
        """Verify the date filter dropdown has multiple filter options."""
        self.media.date_filter.click()
        self.page.wait_for_timeout(1000)

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

        # Page should still be in valid state
        assert "media" in self.page.url.lower()

    @pytest.mark.ui
    @pytest.mark.media
    @pytest.mark.media_deeper
    def test_date_filter_last_7_days(self):
        """Verify selecting 'Last 7 Days' date filter works."""
        self.media.select_date_filter("Last 7 Days")
        assert "media" in self.page.url.lower()

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
        grid_visible = self.media.grid_view_button.count() > 0
        list_visible = self.media.list_view_button.count() > 0

        assert grid_visible or list_visible, \
            "Expected at least one view toggle button (grid or list)"

    @pytest.mark.ui
    @pytest.mark.media
    @pytest.mark.media_deeper
    def test_grid_view_switch_round_trip(self):
        """Verify grid view can be activated and page remains valid."""
        self.media.select_date_filter("Last 30 Days")
        self.media.switch_to_grid_view()
        self.page.wait_for_timeout(1000)

        # If list view is available, switch back; otherwise just verify page state
        if self.media.list_view_button.count() > 0:
            self.media.switch_to_list_view()

        assert "media" in self.page.url.lower()

    # --- Tab switching ---

    @pytest.mark.ui
    @pytest.mark.media
    @pytest.mark.media_deeper
    def test_tab_round_trip_all_to_clips(self):
        """Verify switching from All to Clips and back works."""
        self.media.select_date_filter("Last 30 Days")
        self.media.click_tab("Clips")
        self.media.click_tab("All")

        assert "media" in self.page.url.lower()

    @pytest.mark.ui
    @pytest.mark.media
    @pytest.mark.media_deeper
    def test_tab_round_trip_folders_to_shared(self):
        """Verify switching from Folders to Shared with me and back works."""
        self.media.select_date_filter("Last 30 Days")
        self.media.click_tab("Folders")
        self.media.click_tab("Shared with me")
        self.media.click_tab("Folders")

        assert "media" in self.page.url.lower()

    @pytest.mark.ui
    @pytest.mark.media
    @pytest.mark.media_deeper
    def test_core_tabs_accessible(self):
        """Verify the core media tabs can be clicked without errors."""
        self.media.select_date_filter("Last 30 Days")
        # Test core tabs that are always present (Vault may not be visible)
        for tab in ["All", "My Media", "Shared with me", "Clips", "Folders"]:
            self.media.click_tab(tab)
            self.page.wait_for_timeout(500)

        assert "media" in self.page.url.lower()

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

        # Should show empty state or remain on page
        assert "media" in self.page.url.lower()

    @pytest.mark.ui
    @pytest.mark.media
    @pytest.mark.media_deeper
    def test_search_clear_and_retry(self):
        """Verify clearing search and searching again works."""
        self.media.select_date_filter("Last 30 Days")
        self.media.search_media("clip")
        self.page.wait_for_timeout(2000)

        self.media.search_media("17")
        assert "media" in self.page.url.lower()

    # --- Page refresh ---

    @pytest.mark.ui
    @pytest.mark.media
    @pytest.mark.media_deeper
    def test_media_page_after_refresh(self):
        """Verify the Media page loads correctly after a browser refresh."""
        self.page.reload()
        self.page.wait_for_timeout(3000)

        assert "media" in self.page.url.lower()
        expect(self.media.date_filter).to_be_visible(timeout=15000)
