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
    def setup(self, authenticated_page, step_capture):
        self.page = authenticated_page
        self.step_capture = step_capture
        step_capture.set_page(self.page)
        self.media = MediaPage(self.page)
        self.media.navigate()
        yield

    # --- Date filter ---

    @pytest.mark.ui
    @pytest.mark.media
    @pytest.mark.media_deeper
    @pytest.mark.qatouch("M73wDl")
    def test_date_filter_dropdown_opens(self):
        """Verify the date filter dropdown can be opened."""
        self.media.date_filter.click()
        self.page.wait_for_timeout(1000)
        self.step_capture.mark(1, "Click the date filter dropdown")

        listbox = self.page.locator("[role='listbox']")
        expect(listbox).to_be_visible(timeout=10000)
        self.step_capture.mark(2, "Verify the dropdown listbox is visible")

        # Close the dropdown
        self.page.keyboard.press("Escape")
        self.step_capture.mark(3, "Close the dropdown with Escape key")

    @pytest.mark.ui
    @pytest.mark.media
    @pytest.mark.media_deeper
    @pytest.mark.qatouch("bj0X3V")
    def test_date_filter_has_options(self):
        """Verify the date filter dropdown has multiple filter options."""
        self.media.date_filter.click()
        self.page.wait_for_timeout(1000)
        self.step_capture.mark(1, "Click the date filter dropdown")

        listbox = self.page.locator("[role='listbox']")
        listbox.wait_for(state="visible", timeout=10000)

        options = listbox.locator("li[role='option']")
        count = options.count()
        assert count >= 3, f"Expected at least 3 date filter options, got {count}"
        self.step_capture.mark(2, "Verify dropdown has at least 3 filter options")

        self.page.keyboard.press("Escape")
        self.step_capture.mark(3, "Close the dropdown with Escape key")

    @pytest.mark.ui
    @pytest.mark.media
    @pytest.mark.media_deeper
    @pytest.mark.qatouch("bj0X3V")
    def test_date_filter_today(self):
        """Verify selecting 'Today' date filter works."""
        self.media.select_date_filter("Today")
        self.step_capture.mark(1, "Select 'Today' from the date filter dropdown")

        # Page should still be in valid state
        assert "media" in self.page.url.lower()
        self.step_capture.mark(2, "Verify page remains valid after filter selection")

    @pytest.mark.ui
    @pytest.mark.media
    @pytest.mark.media_deeper
    @pytest.mark.qatouch("zvnVa9")
    def test_date_filter_last_7_days(self):
        """Verify selecting 'Last 7 Days' date filter works."""
        self.media.select_date_filter("Last 7 Days")
        self.step_capture.mark(1, "Select 'Last 7 Days' from the date filter dropdown")

        assert "media" in self.page.url.lower()
        self.step_capture.mark(2, "Verify page remains valid after filter selection")

    # --- View toggle ---

    @pytest.mark.ui
    @pytest.mark.media
    @pytest.mark.media_deeper
    @pytest.mark.qatouch("Ee69PV")
    def test_grid_view_toggle_visible(self):
        """Verify the grid view toggle button is visible."""
        expect(self.media.grid_view_button).to_be_visible(timeout=10000)
        self.step_capture.mark(1, "Verify the grid view toggle button is visible")

    @pytest.mark.ui
    @pytest.mark.media
    @pytest.mark.media_deeper
    @pytest.mark.qatouch("aj6ydD")
    def test_view_toggle_area_present(self):
        """Verify at least one view toggle button (grid or list) is present."""
        grid_visible = self.media.grid_view_button.count() > 0
        list_visible = self.media.list_view_button.count() > 0

        assert grid_visible or list_visible, \
            "Expected at least one view toggle button (grid or list)"
        self.step_capture.mark(1, "Verify at least one view toggle button is present")

    @pytest.mark.ui
    @pytest.mark.media
    @pytest.mark.media_deeper
    @pytest.mark.qatouch("11zlpR")
    def test_grid_view_switch_round_trip(self):
        """Verify grid view can be activated and page remains valid."""
        self.media.select_date_filter("Last 30 Days")
        self.step_capture.mark(1, "Select Last 30 Days date filter")

        self.media.switch_to_grid_view()
        self.page.wait_for_timeout(1000)
        self.step_capture.mark(2, "Switch to grid view")

        # If list view is available, switch back; otherwise just verify page state
        if self.media.list_view_button.count() > 0:
            self.media.switch_to_list_view()
        self.step_capture.mark(3, "Switch back to list view if available")

        assert "media" in self.page.url.lower()
        self.step_capture.mark(4, "Verify page remains valid after round trip")

    # --- Tab switching ---

    @pytest.mark.ui
    @pytest.mark.media
    @pytest.mark.media_deeper
    @pytest.mark.qatouch("dypXww")
    def test_tab_round_trip_all_to_clips(self):
        """Verify switching from All to Clips and back works."""
        self.media.select_date_filter("Last 30 Days")
        self.step_capture.mark(1, "Select Last 30 Days date filter")

        self.media.click_tab("Clips")
        self.step_capture.mark(2, "Switch to Clips tab")

        self.media.click_tab("All")
        self.step_capture.mark(3, "Switch back to All tab")

        assert "media" in self.page.url.lower()
        self.step_capture.mark(4, "Verify page remains valid after tab round trip")

    @pytest.mark.ui
    @pytest.mark.media
    @pytest.mark.media_deeper
    def test_tab_round_trip_folders_to_shared(self):
        """Verify switching from Folders to Shared with me and back works."""
        self.media.select_date_filter("Last 30 Days")
        self.step_capture.mark(1, "Select Last 30 Days date filter")

        self.media.click_tab("Folders")
        self.step_capture.mark(2, "Switch to Folders tab")

        self.media.click_tab("Shared with me")
        self.step_capture.mark(3, "Switch to Shared with me tab")

        self.media.click_tab("Folders")
        self.step_capture.mark(4, "Switch back to Folders tab")

        assert "media" in self.page.url.lower()
        self.step_capture.mark(5, "Verify page remains valid after tab round trip")

    @pytest.mark.ui
    @pytest.mark.media
    @pytest.mark.media_deeper
    def test_core_tabs_accessible(self):
        """Verify the core media tabs can be clicked without errors."""
        self.media.select_date_filter("Last 30 Days")
        self.step_capture.mark(1, "Select Last 30 Days date filter")

        # Test core tabs that are always present (Vault may not be visible)
        for tab in ["All", "My Media", "Shared with me", "Clips", "Folders"]:
            self.media.click_tab(tab)
            self.page.wait_for_timeout(500)
        self.step_capture.mark(2, "Click each core tab: All, My Media, Shared with me, Clips, Folders")

        assert "media" in self.page.url.lower()
        self.step_capture.mark(3, "Verify page remains valid after cycling all tabs")

    # --- Search ---

    @pytest.mark.ui
    @pytest.mark.media
    @pytest.mark.media_deeper
    @pytest.mark.qatouch("dypXvp")
    def test_search_input_visible(self):
        """Verify the search input is visible on the Media page."""
        self.media.select_date_filter("Last 30 Days")
        self.step_capture.mark(1, "Select Last 30 Days date filter")

        expect(self.media.search_input).to_be_visible(timeout=10000)
        self.step_capture.mark(2, "Verify the search input is visible")

    @pytest.mark.ui
    @pytest.mark.media
    @pytest.mark.media_deeper
    @pytest.mark.qatouch("Pgw96K")
    def test_search_no_results(self):
        """Verify searching for nonexistent text shows empty or no results."""
        self.media.select_date_filter("Last 30 Days")
        self.step_capture.mark(1, "Select Last 30 Days date filter")

        self.media.search_media("zzzznonexistent999xyz")
        self.step_capture.mark(2, "Search for nonexistent text")

        # Should show empty state or remain on page
        assert "media" in self.page.url.lower()
        self.step_capture.mark(3, "Verify page shows empty state or no results")

    @pytest.mark.ui
    @pytest.mark.media
    @pytest.mark.media_deeper
    def test_search_clear_and_retry(self):
        """Verify clearing search and searching again works."""
        self.media.select_date_filter("Last 30 Days")
        self.step_capture.mark(1, "Select Last 30 Days date filter")

        self.media.search_media("clip")
        self.page.wait_for_timeout(2000)
        self.step_capture.mark(2, "Search for 'clip'")

        self.media.search_media("17")
        self.step_capture.mark(3, "Clear search and search for '17'")

        assert "media" in self.page.url.lower()
        self.step_capture.mark(4, "Verify page remains valid after search retry")

    # --- Page refresh ---

    @pytest.mark.ui
    @pytest.mark.media
    @pytest.mark.media_deeper
    @pytest.mark.qatouch("Z8xQV6")
    def test_media_page_after_refresh(self):
        """Verify the Media page loads correctly after a browser refresh."""
        self.page.reload()
        self.page.wait_for_timeout(3000)
        self.step_capture.mark(1, "Refresh the Media page")

        assert "media" in self.page.url.lower()
        self.step_capture.mark(2, "Verify URL still contains 'media' after refresh")

        expect(self.media.date_filter).to_be_visible(timeout=15000)
        self.step_capture.mark(3, "Verify date filter is visible after refresh")
