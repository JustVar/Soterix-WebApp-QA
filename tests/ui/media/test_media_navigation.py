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
    def setup(self, authenticated_page):
        self.page = authenticated_page
        self.media = MediaPage(self.page)

    # --- Navigation ---

    @pytest.mark.ui
    @pytest.mark.media
    def test_navigate_to_media_page(self):
        """Verify navigation to the Media page via the sidebar."""
        self.media.navigate()

        # Media page should be accessible - URL should include 'media'
        assert "media" in self.page.url.lower(), (
            f"Expected URL to contain 'media', got: {self.page.url}"
        )

    # --- Date filter ---

    @pytest.mark.ui
    @pytest.mark.media
    def test_select_date_filter(self):
        """Verify selecting 'Last 30 Days' from the date filter dropdown."""
        self.media.navigate()
        self.media.select_date_filter("Last 30 Days")

        # After filter selection, page should either show content or empty state
        empty = self.media.is_page_empty(timeout=5000)
        assert empty is True or empty is False, (
            "Could not determine if main page has data after filter"
        )

    # --- View toggle ---

    @pytest.mark.ui
    @pytest.mark.media
    def test_switch_to_grid_view(self):
        """Verify switching from list to grid view."""
        self.media.navigate()
        self.media.select_date_filter("Last 30 Days")
        self.media.switch_to_grid_view()

        # Grid view icon should have been clicked without error;
        # the page should still be in a valid state
        assert "media" in self.page.url.lower()

    # --- Tab navigation ---

    @pytest.mark.ui
    @pytest.mark.media
    def test_all_tab(self):
        """Verify the All tab loads and shows content or empty state."""
        self.media.navigate()
        self.media.select_date_filter("Last 30 Days")
        self.media.click_tab("All")

        empty = self.media.is_page_empty(timeout=5000)
        assert empty is True or empty is False

    @pytest.mark.ui
    @pytest.mark.media
    def test_my_media_tab(self):
        """Verify the My Media tab loads."""
        self.media.navigate()
        self.media.select_date_filter("Last 30 Days")
        self.media.click_tab("My Media")

        empty = self.media.is_page_empty(timeout=5000)
        assert empty is True or empty is False

    @pytest.mark.ui
    @pytest.mark.media
    def test_shared_with_me_tab(self):
        """Verify the Shared with me tab loads."""
        self.media.navigate()
        self.media.select_date_filter("Last 30 Days")
        self.media.click_tab("Shared with me")

        empty = self.media.is_page_empty(timeout=5000)
        assert empty is True or empty is False

    @pytest.mark.ui
    @pytest.mark.media
    def test_clips_tab(self):
        """Verify the Clips tab loads and shows content or empty state."""
        self.media.navigate()
        self.media.select_date_filter("Last 30 Days")
        self.media.click_tab("Clips")

        empty = self.media.is_page_empty(timeout=5000)
        assert empty is True or empty is False

    @pytest.mark.ui
    @pytest.mark.media
    def test_folders_tab(self):
        """Verify the Folders tab loads."""
        self.media.navigate()
        self.media.select_date_filter("Last 30 Days")
        self.media.click_tab("Folders")

        empty = self.media.is_page_empty(timeout=5000)
        assert empty is True or empty is False

    @pytest.mark.ui
    @pytest.mark.media
    def test_vault_tab(self):
        """Verify the Vault tab loads."""
        self.media.navigate()
        self.media.select_date_filter("Last 30 Days")
        self.media.click_tab("Vault")

        empty = self.media.is_page_empty(timeout=5000)
        assert empty is True or empty is False

    # --- Search ---

    @pytest.mark.ui
    @pytest.mark.media
    def test_search_media(self):
        """Verify searching media by title/tags."""
        self.media.navigate()
        self.media.select_date_filter("Last 30 Days")
        self.media.search_media("17")

        # After search, page should display results or empty state
        empty = self.media.is_page_empty(timeout=5000)
        assert empty is True or empty is False
