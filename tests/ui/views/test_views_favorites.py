"""Favorites tests - add/remove camera favorites and verify panel contents."""
import pytest
from playwright.sync_api import expect

from config.base_config import config
from tests.shared.pages.views_page import ViewsPage

# One worker for every module that writes this account's saved views, tabs, bookmarks and favourites: under
# -n they would otherwise spread across workers and race on the same
# tenant state (pytest.ini --dist loadgroup).
pytestmark = pytest.mark.xdist_group("account_views")

SITE_NAME = None


class TestViewsFavorites:
    """Tests for camera favorites functionality."""

    @pytest.fixture(autouse=True)
    def setup(self, authenticated_page):
        self.page = authenticated_page
        self.views = ViewsPage(self.page)
        self.views.navigate()
        self.views.wait_for_page_load()
        return

    def _expand_site(self):
        """Expand the site tree and show cameras.

        No settling sleep here: the tree collapses itself within a few
        seconds of expansion, so act on it immediately (toggle_favorite
        re-expands when it finds the tree closed).
        """
        self.views.expand_site_and_show_cameras(SITE_NAME)

    def _get_camera_name(self) -> str:
        """Get a real camera name to favorite.

        The configured test_camera_name is authoritative: parsing the
        first thumbnail's text returns the location header ("Training
        Area"), which is not a camera and never reaches the favorites
        panel.
        """
        camera_name = config.get("test_camera_name")
        if camera_name:
            return camera_name
        thumbnails = self.page.locator(".cameraThumbnailWrapper")
        # Reached only when test_camera_name is unset, so the panel
        # being empty as well leaves nothing to name.
        expect(thumbnails.first).to_be_visible(timeout=10000)
        return thumbnails.first.inner_text().strip().split("\n")[0].strip()

    @pytest.mark.ui
    @pytest.mark.favorites
    def test_add_remove_favorites(self):
        """Verify adding a camera to favorites, seeing it in the panel, and removing it.

        Flow:
        1. Expand site tree to reveal cameras
        2. Click favorite star on a camera
        3. Open favorites panel - verify camera appears
        4. Close favorites panel
        5. Click favorite star again to remove
        6. Open favorites panel - verify camera is gone
        7. Close favorites panel
        """
        self._expand_site()

        # Get a camera name to use for the favorite toggle
        camera_name = self._get_camera_name()

        # Clean start: a failed earlier run can leave the star on
        if self.views.is_camera_favorited(camera_name):
            self.views.toggle_favorite(camera_name)

        # Add to favorites
        self.views.toggle_favorite(camera_name)

        # Open favorites and verify camera appears
        self.views.open_favorites_panel()
        assert self.views.is_camera_in_favorites(camera_name) is True, (
            f"Camera '{camera_name}' should appear in favorites after adding"
        )
        self.views.close_favorites_panel()

        # Remove from favorites
        self.views.toggle_favorite(camera_name)

        # Open favorites and verify camera is gone
        self.views.open_favorites_panel()
        assert self.views.is_camera_in_favorites(camera_name, present=False) is True, (
            f"Camera '{camera_name}' should not appear in favorites after removing"
        )
        self.views.close_favorites_panel()
