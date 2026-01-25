"""Basic Views tests - thumbnail display, add tab, tile layout."""
import pytest
from tests.shared.pages.views_page import ViewsPage


class TestViewsBasic:
    """Basic Views functionality tests."""

    @pytest.fixture(autouse=True)
    def setup(self, authenticated_page):
        """Set up ViewsPage for each test."""
        self.page = authenticated_page
        self.views = ViewsPage(self.page)

    def test_camera_thumbnails_visible(self):
        """Verify camera thumbnails are displayed after expanding a site."""
        # Navigate: expand first available site and show cameras
        self.views.expand_site_and_show_cameras()
        
        # Wait for thumbnails to load
        self.page.wait_for_timeout(3000)
        
        count = self.views.get_thumbnail_count()
        assert count > 0, "No camera thumbnails visible"
        print(f"Found {count} camera thumbnails")

    def test_add_new_tab(self):
        """Verify adding a new tab creates empty tiles."""
        # Get initial tile count
        initial_tiles = self.views.get_empty_tile_count()
        
        # Add new tab
        self.views.add_new_tab()
        self.page.wait_for_timeout(2000)  # Wait for tab to load
        
        # Verify new tiles appeared (should be 8 empty tiles in new tab)
        new_tiles = self.views.get_empty_tile_count()
        assert new_tiles == 8, f"Expected 8 empty tiles in new tab, got {new_tiles}"

    def test_close_tab(self):
        """Verify closing a tab removes it."""
        # First add a tab
        self.views.add_new_tab()
        self.page.wait_for_timeout(2000)
        
        # Count tiles before close
        tiles_before = self.views.get_empty_tile_count()
        
        # Close the new tab (index 1, since 0 is the default tab)
        self.views.close_tab(1)
        self.page.wait_for_timeout(2000)
        
        # Verify tiles decreased
        tiles_after = self.views.get_empty_tile_count()
        assert tiles_after < tiles_before, "Tab was not closed"
