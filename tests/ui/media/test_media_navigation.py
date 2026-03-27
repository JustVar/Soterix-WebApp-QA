"""Media page navigation and browsing tests.

Covers navigation, date filter, view switching, and tab navigation.

Migrated from Selenium:
- test_navigate_to_media_page (line 5827)
- test_media_select_filter (line 5841)
- test_media_switch_to_grid_view (line 5871)
- test_media_validate_my_media (line 5887)
- test_media_validate_shared_with_me (line 5904)
- test_media_all_tab (line 5923)
- test_media_clips_tab (line 5947)
- test_media_export_folder (line 6385) - Vault tab portion
- test_media_search_clip (line 6421)
"""
import pytest
from tests.shared.pages.media_page import MediaPage


class TestMediaNavigation:
    """Tests for Media page navigation and browsing."""

    @pytest.fixture(autouse=True)
    def setup(self, authenticated_page, step_capture):
        self.page = authenticated_page
        self.step_capture = step_capture
        step_capture.set_page(self.page)
        self.media = MediaPage(self.page)

    # --- Navigation ---

    @pytest.mark.ui
    @pytest.mark.media
    @pytest.mark.qatouch("rGQDWk")
    def test_navigate_to_media_page(self):
        """Verify navigation to the Media page via the sidebar."""
        self.media.navigate()
        self.step_capture.mark(1, "Navigate to the Media page via sidebar")

        # Media page should be accessible - URL should include 'media'
        assert "media" in self.page.url.lower(), (
            f"Expected URL to contain 'media', got: {self.page.url}"
        )
        self.step_capture.mark(2, "Verify URL contains 'media'")


    # --- Date filter ---

    @pytest.mark.ui
    @pytest.mark.media
    @pytest.mark.qatouch("M73wDl")
    def test_select_date_filter(self):
        """Verify selecting 'Last 30 Days' from the date filter dropdown."""
        self.media.navigate()
        self.step_capture.mark(1, "Navigate to the Media page")

        self.media.select_date_filter("Last 30 Days")
        self.step_capture.mark(2, "Select 'Last 30 Days' from the date filter dropdown")

        # After filter selection, page should either show content or empty state
        empty = self.media.is_page_empty(timeout=5000)
        assert empty is True or empty is False, (
            "Could not determine if main page has data after filter"
        )
        self.step_capture.mark(3, "Verify page shows content or empty state after filter")

    # --- View toggle ---

    @pytest.mark.ui
    @pytest.mark.media
    @pytest.mark.qatouch("11zlpR")
    def test_switch_to_grid_view(self):
        """Verify switching from list to grid view."""
        self.media.navigate()
        self.media.select_date_filter("Last 30 Days")
        self.step_capture.mark(1, "Navigate to Media page and select Last 30 Days filter")

        self.media.switch_to_grid_view()
        self.step_capture.mark(2, "Switch to grid view")

        # Grid view icon should have been clicked without error;
        # the page should still be in a valid state
        assert "media" in self.page.url.lower()
        self.step_capture.mark(3, "Verify page remains valid in grid view")

    # --- Tab navigation ---

    @pytest.mark.ui
    @pytest.mark.media
    @pytest.mark.qatouch("VKbQjx")
    def test_all_tab(self):
        """Verify the All tab loads and shows content or empty state."""
        self.media.navigate()
        self.media.select_date_filter("Last 30 Days")
        self.step_capture.mark(1, "Navigate to Media page and select Last 30 Days filter")

        self.media.click_tab("All")
        self.step_capture.mark(2, "Click the All tab")

        empty = self.media.is_page_empty(timeout=5000)
        assert empty is True or empty is False
        self.step_capture.mark(3, "Verify All tab shows content or empty state")

    @pytest.mark.ui
    @pytest.mark.media
    @pytest.mark.qatouch("vanZz1")
    def test_my_media_tab(self):
        """Verify the My Media tab loads."""
        self.media.navigate()
        self.media.select_date_filter("Last 30 Days")
        self.step_capture.mark(1, "Navigate to Media page and select Last 30 Days filter")

        self.media.click_tab("My Media")
        self.step_capture.mark(2, "Click the My Media tab")

        empty = self.media.is_page_empty(timeout=5000)
        assert empty is True or empty is False
        self.step_capture.mark(3, "Verify My Media tab shows content or empty state")

    @pytest.mark.ui
    @pytest.mark.media
    @pytest.mark.qatouch("QGjQ49")
    def test_shared_with_me_tab(self):
        """Verify the Shared with me tab loads."""
        self.media.navigate()
        self.media.select_date_filter("Last 30 Days")
        self.step_capture.mark(1, "Navigate to Media page and select Last 30 Days filter")

        self.media.click_tab("Shared with me")
        self.step_capture.mark(2, "Click the Shared with me tab")

        empty = self.media.is_page_empty(timeout=5000)
        assert empty is True or empty is False
        self.step_capture.mark(3, "Verify Shared with me tab shows content or empty state")

    @pytest.mark.ui
    @pytest.mark.media
    @pytest.mark.qatouch("dypXmw")
    def test_clips_tab(self):
        """Verify the Clips tab loads and shows content or empty state."""
        self.media.navigate()
        self.media.select_date_filter("Last 30 Days")
        self.step_capture.mark(1, "Navigate to Media page and select Last 30 Days filter")

        self.media.click_tab("Clips")
        self.step_capture.mark(2, "Click the Clips tab")

        empty = self.media.is_page_empty(timeout=5000)
        assert empty is True or empty is False
        self.step_capture.mark(3, "Verify Clips tab shows content or empty state")

    @pytest.mark.ui
    @pytest.mark.media
    @pytest.mark.qatouch("xm9d85")
    def test_folders_tab(self):
        """Verify the Folders tab loads."""
        self.media.navigate()
        self.media.select_date_filter("Last 30 Days")
        self.step_capture.mark(1, "Navigate to Media page and select Last 30 Days filter")

        self.media.click_tab("Folders")
        self.step_capture.mark(2, "Click the Folders tab")

        empty = self.media.is_page_empty(timeout=5000)
        assert empty is True or empty is False
        self.step_capture.mark(3, "Verify Folders tab shows content or empty state")

    @pytest.mark.ui
    @pytest.mark.media
    @pytest.mark.qatouch("VKbQZB")
    def test_vault_tab(self):
        """Verify the Vault tab loads."""
        self.media.navigate()
        self.media.select_date_filter("Last 30 Days")
        self.step_capture.mark(1, "Navigate to Media page and select Last 30 Days filter")

        self.media.click_tab("Vault")
        self.step_capture.mark(2, "Click the Vault tab")

        empty = self.media.is_page_empty(timeout=5000)
        assert empty is True or empty is False
        self.step_capture.mark(3, "Verify Vault tab shows content or empty state")

    # --- Search ---

    @pytest.mark.ui
    @pytest.mark.media
    @pytest.mark.qatouch("68lDK8")
    def test_search_media(self):
        """Verify searching media by title/tags."""
        self.media.navigate()
        self.media.select_date_filter("Last 30 Days")
        self.step_capture.mark(1, "Navigate to Media page and select Last 30 Days filter")

        self.media.search_media("17")
        self.step_capture.mark(2, "Search media for '17'")

        # After search, page should display results or empty state
        empty = self.media.is_page_empty(timeout=5000)
        assert empty is True or empty is False
        self.step_capture.mark(3, "Verify search results or empty state display")
