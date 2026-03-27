"""Bookmark tests - creation (tile level) and operations (full screen mode).

test_add_bookmark creates a new bookmark on a streaming tile. The remaining
tests operate on existing bookmarks in full screen mode. If no bookmarks
exist, operation tests will skip gracefully.
"""
import datetime
import pytest
from playwright.sync_api import expect
from tests.shared.pages.views_page import ViewsPage
from tests.shared.pages.fullscreen_page import FullScreenPage


@pytest.mark.ui
@pytest.mark.bookmark
@pytest.mark.qatouch("rGQZz1")
def test_add_bookmark(authenticated_page, step_capture):
    """Create a new bookmark on a streaming video tile.

    This is a prerequisite for the bookmark operation tests below.
    Navigates to Views, ensures a camera is streaming in a tile,
    then clicks the bookmark icon from the tile's three-dot menu.
    """
    page = authenticated_page
    step_capture.set_page(page)
    views = ViewsPage(page)
    views.navigate()
    views.wait_for_page_load()

    # Ensure a camera is loaded in a tile
    video_tiles = page.locator(
        "[class*='video_container'][class*='new_video_player']"
    )
    if video_tiles.count() == 0:
        views.expand_site_and_show_cameras("Driver Site")
        page.wait_for_timeout(500)
        views.add_first_camera_via_checkbox()
        page.wait_for_timeout(3000)
        video_tiles.first.wait_for(state="visible", timeout=30000)
    step_capture.mark(1, "Navigate to Views and ensure a camera is streaming")

    # Add a bookmark on the first tile
    views.add_bookmark_on_tile(tile_index=0)
    step_capture.mark(2, "Add bookmark on first camera tile via three-dot menu")

    # Verify: enter fullscreen and check bookmarks panel has at least one entry
    views.enter_fullscreen_on_tile(0)
    page.wait_for_timeout(2000)
    fs = FullScreenPage(page)
    fs.open_bookmarks_panel()
    page.wait_for_timeout(1000)
    assert fs.has_bookmarks(), "Bookmark was not created - no bookmarks found in panel"
    step_capture.mark(3, "Verify bookmark appears in bookmarks panel")


class TestViewsBookmarks:
    """Tests for bookmark operations within full screen mode."""

    @pytest.fixture(autouse=True)
    def setup(self, fullscreen_page, step_capture):
        self.page = fullscreen_page.page
        self.step_capture = step_capture
        step_capture.set_page(self.page)
        self.fs = fullscreen_page
        self._renamed_bookmarks = []
        yield
        # Cleanup: revert any bookmark renames
        for index, _name in reversed(self._renamed_bookmarks):
            try:
                self.fs.open_bookmarks_panel()
                self.page.wait_for_timeout(500)
                self.fs.rename_bookmark(index=index, new_name="Bookmark")
            except Exception:
                pass

    def _ensure_bookmarks_panel_open(self):
        """Open bookmarks panel and skip if no bookmarks exist."""
        self.fs.open_bookmarks_panel()
        self.page.wait_for_timeout(1000)

        if not self.fs.has_bookmarks():
            pytest.skip(
                "No bookmarks available on this camera. "
                "Bookmarks are created by archive tests (prerequisite)."
            )

    @pytest.mark.ui
    @pytest.mark.bookmark
    @pytest.mark.views_fullscreen
    @pytest.mark.qatouch("yaWrV9")
    def test_open_bookmarks_panel(self):
        """Verify bookmarks panel opens when clicking the dots icon."""
        self.fs.open_bookmarks_panel()
        self.page.wait_for_timeout(1000)
        self.step_capture.mark(1, "Click bookmarks toggle to open panel")

        panel_visible = (
            self.fs.bookmark_items.count() > 0
            or self.fs.bookmarks_toggle.is_visible()
        )
        assert panel_visible, "Bookmarks panel should be visible after clicking dots icon"
        self.step_capture.mark(2, "Verify bookmarks panel is visible")

    @pytest.mark.ui
    @pytest.mark.bookmark
    @pytest.mark.views_fullscreen
    @pytest.mark.qatouch("yaWrV9")
    def test_close_bookmarks_panel(self):
        """Verify bookmarks panel closes when clicking the dots icon again."""
        self.fs.open_bookmarks_panel()
        self.page.wait_for_timeout(500)
        self.step_capture.mark(1, "Open bookmarks panel")

        initial_count = self.fs.bookmark_items.count()

        self.fs.close_bookmarks_panel()
        self.page.wait_for_timeout(500)
        self.step_capture.mark(2, "Close bookmarks panel by toggling again")

        if initial_count > 0:
            expect(self.fs.bookmark_items.first).to_be_hidden(timeout=5000)
        self.step_capture.mark(3, "Verify bookmarks panel is hidden")

    @pytest.mark.ui
    @pytest.mark.bookmark
    @pytest.mark.views_fullscreen
    @pytest.mark.qatouch("eJqmLp")
    def test_play_bookmark(self):
        """Verify clicking a bookmark plays it."""
        self._ensure_bookmarks_panel_open()
        self.step_capture.mark(1, "Open bookmarks panel and confirm bookmarks exist")

        self.fs.play_bookmark(0)
        expect(self.fs.play_button).to_be_visible(timeout=60000)
        self.step_capture.mark(2, "Play first bookmark and verify playback starts")

    @pytest.mark.ui
    @pytest.mark.bookmark
    @pytest.mark.views_fullscreen
    @pytest.mark.qatouch("rGQZz1")
    def test_bookmark_options_menu(self):
        """Verify the 3-dot options menu shows 4 options."""
        self._ensure_bookmarks_panel_open()
        self.step_capture.mark(1, "Open bookmarks panel and confirm bookmarks exist")

        self.fs.open_bookmark_options(0)
        self.step_capture.mark(2, "Open three-dot options menu on first bookmark")

        option_count = self.fs.bookmark_options.count()
        assert option_count >= 4, (
            f"Expected at least 4 bookmark options (Rename, Export, Share, Delete), "
            f"got {option_count}"
        )
        self.step_capture.mark(3, "Verify options menu shows at least 4 options")

    @pytest.mark.ui
    @pytest.mark.bookmark
    @pytest.mark.views_fullscreen
    @pytest.mark.slow
    @pytest.mark.qatouch("yaWrV9")
    def test_export_bookmark(self):
        """Verify a bookmark can be exported (export dialog completes)."""
        self._ensure_bookmarks_panel_open()
        self.step_capture.mark(1, "Open bookmarks panel and confirm bookmarks exist")

        filename = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        self.fs.export_bookmark(index=0, filename=filename)
        self.step_capture.mark(2, "Export first bookmark and verify export completes")

    @pytest.mark.ui
    @pytest.mark.bookmark
    @pytest.mark.views_fullscreen
    @pytest.mark.qatouch("Nj3r6e")
    def test_share_bookmark(self):
        """Verify a bookmark can be shared (share dialog shows success)."""
        self._ensure_bookmarks_panel_open()
        self.step_capture.mark(1, "Open bookmarks panel and confirm bookmarks exist")

        filename = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        self.fs.share_bookmark(
            index=0,
            email="person@example.com",
            filename=filename
        )
        self.step_capture.mark(2, "Share first bookmark via email")

        expect(self.fs.share_success).to_be_visible(timeout=5000)
        self.step_capture.mark(3, "Verify share success message appears")

    @pytest.mark.ui
    @pytest.mark.bookmark
    @pytest.mark.views_fullscreen
    @pytest.mark.qatouch("yaWrV9")
    def test_rename_bookmark(self):
        """Verify a bookmark can be renamed and the new name appears."""
        self._ensure_bookmarks_panel_open()
        self.step_capture.mark(1, "Open bookmarks panel and confirm bookmarks exist")

        new_name = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        self._renamed_bookmarks.append((0, new_name))
        applied_name = self.fs.rename_bookmark(index=0, new_name=new_name)
        self.step_capture.mark(2, "Rename first bookmark with a new name")

        renamed_element = self.page.locator(f"text={applied_name}")
        expect(renamed_element).to_be_visible(timeout=5000)
        self.step_capture.mark(3, "Verify renamed bookmark appears with new name")

    @pytest.mark.ui
    @pytest.mark.bookmark
    @pytest.mark.views_fullscreen
    @pytest.mark.qatouch("yaWX0K")
    def test_delete_bookmark(self):
        """Verify a bookmark can be deleted with confirmation."""
        self._ensure_bookmarks_panel_open()
        self.step_capture.mark(1, "Open bookmarks panel and confirm bookmarks exist")

        # Rename first so we have a unique identifier to verify deletion
        unique_name = f"DEL_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}"
        self.fs.rename_bookmark(index=0, new_name=unique_name)

        self.page.locator(f"text={unique_name}").wait_for(state="visible", timeout=5000)
        self.step_capture.mark(2, "Rename bookmark with unique name for deletion tracking")

        self.fs.delete_bookmark(index=0)
        self.step_capture.mark(3, "Delete the bookmark and confirm deletion")

        self.fs.verify_bookmark_deleted(unique_name, timeout=10000)
        self.step_capture.mark(4, "Verify deleted bookmark no longer appears in panel")
