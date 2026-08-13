"""Bookmark tests - creation (tile level) and operations (full screen mode).

test_add_bookmark creates a new bookmark on a streaming tile. The remaining
tests operate on existing bookmarks in full screen mode. If no bookmarks
exist, operation tests will skip gracefully.
"""
import datetime
import pytest
from playwright.sync_api import Error as PlaywrightError, expect
from tests.shared.pages.views_page import ViewsPage
from tests.shared.pages.fullscreen_page import FullScreenPage


@pytest.mark.ui
@pytest.mark.bookmark
def test_add_bookmark(authenticated_page):
    """Create a new bookmark on a streaming video tile.

    This is a prerequisite for the bookmark operation tests below.
    Navigates to Views, ensures a camera is streaming in a tile,
    then clicks the bookmark icon from the tile's three-dot menu.
    """
    page = authenticated_page
    views = ViewsPage(page)
    views.navigate()
    views.wait_for_page_load()

    # Ensure a camera is loaded in a tile
    video_tiles = page.locator(
        "[class*='video_container'][class*='new_video_player']"
    )
    if video_tiles.count() == 0:
        views.expand_site_and_show_cameras(None)
        views.add_first_camera_via_checkbox()
        # the tile appearing is the added signal
        video_tiles.first.wait_for(state="visible", timeout=30000)

    # Add a bookmark on the first tile
    views.add_bookmark_on_tile(tile_index=0)

    # Verify: enter fullscreen and check bookmarks panel has at least one entry
    views.enter_fullscreen_on_tile(0)
    fs = FullScreenPage(page)
    fs.wait_for_stream_loaded(timeout=120000)
    fs.open_bookmarks_panel()
    # bookmark rows render async after the panel opens; the first row
    # appearing is the signal
    try:
        fs.bookmark_items.first.wait_for(state="visible", timeout=10000)
    # no row within the bound means no bookmarks - the assert fails
    except PlaywrightError:
        pass
    assert fs.has_bookmarks(), "Bookmark was not created - no bookmarks found in panel"


class TestViewsBookmarks:
    """Tests for bookmark operations within full screen mode."""

    @pytest.fixture(autouse=True)
    def setup(self, fullscreen_page):
        self.page = fullscreen_page.page
        self.fs = fullscreen_page
        self._renamed_bookmarks = []
        yield
        # Cleanup: revert any bookmark renames
        for index, _name in reversed(self._renamed_bookmarks):
            try:
                self.fs.open_bookmarks_panel()
                self.fs.rename_bookmark(index=index, new_name="Bookmark")
            # best-effort revert: the verdict is already decided
            except Exception:
                pass

    def _ensure_bookmarks_panel_open(self):
        """Open bookmarks panel and skip if no bookmarks exist."""
        self.fs.open_bookmarks_panel()
        # bookmark rows render async; the first row appearing is the
        # signal, and none appearing routes to the skip below
        try:
            self.fs.bookmark_items.first.wait_for(
                state="visible", timeout=10000
            )
        # no row within the bound routes to the skip below
        except PlaywrightError:
            pass

        if not self.fs.has_bookmarks():
            pytest.skip(
                "No bookmarks available on this camera. "
                "Bookmarks are created by archive tests (prerequisite)."
            )

    @pytest.mark.ui
    @pytest.mark.bookmark
    @pytest.mark.views_fullscreen
    def test_open_bookmarks_panel(self):
        """Verify bookmarks panel opens when clicking the dots icon."""
        self.fs.open_bookmarks_panel()

        panel_visible = (
            self.fs.bookmark_items.count() > 0
            or self.fs.bookmarks_toggle.is_visible()
        )
        assert panel_visible, "Bookmarks panel should be visible after clicking dots icon"

    @pytest.mark.ui
    @pytest.mark.bookmark
    @pytest.mark.views_fullscreen
    def test_close_bookmarks_panel(self):
        """Verify bookmarks panel closes when clicking the dots icon again."""
        self.fs.open_bookmarks_panel()
        # rows render async; count only after the first row lands (a
        # zero count just skips the hidden check below)
        try:
            self.fs.bookmark_items.first.wait_for(
                state="visible", timeout=10000
            )
        # no row within the bound leaves a zero count, which just
        # skips the hidden check
        except PlaywrightError:
            pass
        initial_count = self.fs.bookmark_items.count()

        self.fs.close_bookmarks_panel()

        if initial_count > 0:
            # the retrying expect absorbs the close animation
            expect(self.fs.bookmark_items.first).to_be_hidden(timeout=5000)

    @pytest.mark.ui
    @pytest.mark.bookmark
    @pytest.mark.views_fullscreen
    def test_play_bookmark(self):
        """Verify clicking a bookmark navigates to that snapshot position."""
        self._ensure_bookmarks_panel_open()

        # Click the bookmark to navigate to its position
        self.fs.play_bookmark(0)

        # Verify the stream loaded and we're in archive mode (stream is available)
        assert self.fs.is_streaming(), "Stream should be available after clicking bookmark"
        assert not self.fs.is_live_mode(), "Should be in archive mode after clicking bookmark"

    @pytest.mark.ui
    @pytest.mark.bookmark
    @pytest.mark.views_fullscreen
    def test_bookmark_options_menu(self):
        """Verify the 3-dot options menu shows 4 options."""
        self._ensure_bookmarks_panel_open()

        self.fs.open_bookmark_options(0)

        option_count = self.fs.bookmark_options.count()
        assert option_count >= 4, (
            f"Expected at least 4 bookmark options (Rename, Export, Share, Delete), "
            f"got {option_count}"
        )

    @pytest.mark.ui
    @pytest.mark.bookmark
    @pytest.mark.views_fullscreen
    @pytest.mark.slow
    def test_export_bookmark(self):
        """Verify a bookmark can be exported (export dialog completes)."""
        self._ensure_bookmarks_panel_open()

        filename = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        # oracle: export_bookmark raises unless the export dialog
        # opens and the progress bar appears and completes
        self.fs.export_bookmark(index=0, filename=filename)

    @pytest.mark.ui
    @pytest.mark.bookmark
    @pytest.mark.views_fullscreen
    def test_share_bookmark(self):
        """Verify a bookmark can be shared (share dialog shows success)."""
        self._ensure_bookmarks_panel_open()

        filename = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        self.fs.share_bookmark(
            index=0,
            email="person@example.com",
            filename=filename
        )

        expect(self.fs.share_success).to_be_visible(timeout=5000)

    @pytest.mark.ui
    @pytest.mark.bookmark
    @pytest.mark.views_fullscreen
    def test_rename_bookmark(self):
        """Verify a bookmark can be renamed and the new name appears."""
        self._ensure_bookmarks_panel_open()

        new_name = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        self._renamed_bookmarks.append((0, new_name))
        applied_name = self.fs.rename_bookmark(index=0, new_name=new_name)

        renamed_element = self.page.locator(f"text={applied_name}")
        expect(renamed_element).to_be_visible(timeout=5000)

    @pytest.mark.ui
    @pytest.mark.bookmark
    @pytest.mark.views_fullscreen
    def test_delete_bookmark(self):
        """Verify a bookmark can be deleted with confirmation."""
        self._ensure_bookmarks_panel_open()

        # Rename first so we have a unique identifier to verify deletion
        unique_name = f"DEL_{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}"
        self.fs.rename_bookmark(index=0, new_name=unique_name)

        self.page.locator(f"text={unique_name}").wait_for(state="visible", timeout=5000)

        self.fs.delete_bookmark(index=0)

        self.fs.verify_bookmark_deleted(unique_name, timeout=10000)
