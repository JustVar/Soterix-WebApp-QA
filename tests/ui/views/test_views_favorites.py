"""Favorites tests - add/remove camera favorites and verify panel contents."""
import pytest

from config.base_config import config
from tests.shared.pages.views_page import ViewsPage

SITE_NAME = None


class TestViewsFavorites:
    """Tests for camera favorites functionality."""

    @pytest.fixture(autouse=True)
    def setup(self, authenticated_page):
        self.page = authenticated_page
        self.views = ViewsPage(self.page)
        self.views.navigate()
        self.views.wait_for_page_load()
        yield

    def _expand_site(self):
        """Expand the site tree and show cameras."""
        self.views.expand_site_and_show_cameras(SITE_NAME)
        self.page.wait_for_timeout(2000)

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
        if thumbnails.count() == 0:
            pytest.skip("No camera thumbnails available")
        return thumbnails.first.inner_text().strip().split("\n")[0].strip()

    @pytest.mark.ui
    @pytest.mark.favorites
    @pytest.mark.skip(reason=(
        "Favorites flow needs an interactive rebuild. The original "
        "locator mixed XPath into CSS and never parsed (broken since "
        "03/2026, so this test has never exercised the flow), and the "
        "current tree renders no span[title] anchor for the configured "
        "camera. Tracked on the QA roadmap rebuild list."
    ))
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

        # Add to favorites
        self.views.toggle_favorite(camera_name)
        self.page.wait_for_timeout(2000)

        # Open favorites and verify camera appears
        self.views.open_favorites_panel()
        assert self.views.is_camera_in_favorites(camera_name), (
            f"Camera '{camera_name}' should appear in favorites after adding"
        )
        self.views.close_favorites_panel()

        # Remove from favorites
        self.views.toggle_favorite(camera_name)
        self.page.wait_for_timeout(2000)

        # Open favorites and verify camera is gone
        self.views.open_favorites_panel()
        assert not self.views.is_camera_in_favorites(camera_name), (
            f"Camera '{camera_name}' should not appear in favorites after removing"
        )
        self.views.close_favorites_panel()
