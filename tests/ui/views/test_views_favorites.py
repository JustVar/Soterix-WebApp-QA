"""Favorites tests - add/remove camera favorites and verify panel contents."""
import pytest
from tests.shared.pages.views_page import ViewsPage

SITE_NAME = "Driver Site"


class TestViewsFavorites:
    """Tests for camera favorites functionality."""

    @pytest.fixture(autouse=True)
    def setup(self, authenticated_page, step_capture):
        self.page = authenticated_page
        self.step_capture = step_capture
        step_capture.set_page(self.page)
        self.views = ViewsPage(self.page)
        self.views.navigate()
        self.views.wait_for_page_load()
        yield

    def _expand_site(self):
        """Expand the site tree and show cameras."""
        self.views.expand_site_and_show_cameras(SITE_NAME)
        self.page.wait_for_timeout(2000)

    def _get_first_camera_name(self) -> str:
        """Get the name of the first camera thumbnail."""
        thumbnails = self.page.locator(".cameraThumbnailWrapper")
        if thumbnails.count() == 0:
            pytest.skip("No camera thumbnails available")
        # Extract text from the first thumbnail
        text = thumbnails.first.inner_text().strip()
        # Camera name is typically the first line
        return text.split("\n")[0].strip()

    @pytest.mark.ui
    @pytest.mark.favorites
    @pytest.mark.qatouch("Nj3JdQ")
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
        self.step_capture.mark(1, "Expand site tree to reveal cameras")

        # Get a camera name from the thumbnails to use for favorite toggle
        camera_name = self._get_first_camera_name()

        # Add to favorites
        self.views.toggle_favorite(camera_name)
        self.page.wait_for_timeout(2000)
        self.step_capture.mark(2, "Click favorite star on a camera to add it")

        # Open favorites and verify camera appears
        self.views.open_favorites_panel()
        assert self.views.is_camera_in_favorites(camera_name), (
            f"Camera '{camera_name}' should appear in favorites after adding"
        )
        self.step_capture.mark(3, "Open favorites panel and verify camera appears")
        self.views.close_favorites_panel()

        # Remove from favorites
        self.views.toggle_favorite(camera_name)
        self.page.wait_for_timeout(2000)
        self.step_capture.mark(4, "Click favorite star again to remove camera")

        # Open favorites and verify camera is gone
        self.views.open_favorites_panel()
        assert not self.views.is_camera_in_favorites(camera_name), (
            f"Camera '{camera_name}' should not appear in favorites after removing"
        )
        self.step_capture.mark(5, "Open favorites panel and verify camera is removed")
        self.views.close_favorites_panel()
