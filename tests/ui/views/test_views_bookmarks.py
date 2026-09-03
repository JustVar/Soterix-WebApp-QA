"""Bookmark tests - creation (tile level) and operations (full screen mode).

Everything here happens the way a person does it, through the UI: the
bookmark is made from the player's bookmark control, renamed and deleted
from its row menu, and every verdict is what the panel shows afterwards.

Two app behaviours shape the code:

  - The panel does not repaint after a mutation and the change reaches
    the list a beat later, so rows are read only after
    `refresh_bookmarks_panel()` re-opens it. Reading the open panel
    straight after a rename or delete shows the old state.
  - Rows carry only a positional id, so each test holds its OWN bookmark
    by the playback stamp the app writes on creation (a rename leaves it
    alone). A bare index could be a real user's bookmark on a shared
    camera, and rename and delete are destructive.
"""
import datetime

import pytest
from playwright.sync_api import expect

from tests.shared.pages.fullscreen_page import FullScreenPage
from tests.shared.pages.views_page import ViewsPage


def _unique_name() -> str:
    return f"AutoTest BM {datetime.datetime.now():%H%M%S}"


@pytest.mark.ui
@pytest.mark.bookmark
def test_add_bookmark(authenticated_page):
    """Create a bookmark on a streaming video tile.

    Steps:
    1. Open Views and load the configured camera into a tile.
       Expected: The camera streams in the first tile.
    2. Enter full screen and bookmark the current position.
       Expected: A new bookmark appears in the bookmarks panel.
    3. Delete the bookmark this test created.
       Expected: It is no longer listed.
    """
    page = authenticated_page
    views = ViewsPage(page)
    views.navigate()
    views.wait_for_page_load()

    video_tiles = page.locator(
        "[class*='video_container'][class*='new_video_player']"
    )
    if video_tiles.count() == 0:
        views.expand_site_and_show_cameras(None)
        views.add_first_camera_via_checkbox()
        # the tile appearing is the added signal
        video_tiles.first.wait_for(state="visible", timeout=30000)

    views.enter_fullscreen_on_tile(0)
    fs = FullScreenPage(page)
    fs.wait_for_stream_loaded(timeout=120000)
    # A dead stream must say so here, named, the way the class fixture
    # does. Without this the failure overlay simply covers the panel
    # toggle and the test dies 30s later pointing at an icon, which
    # reads as a locator bug and is not what --retry-streams matches
    # (measured on US 09/03/2026).
    fs.assert_stream_playing()
    fs.refresh_bookmarks_panel()
    before = fs.bookmark_texts()

    fs.create_bookmark()

    fs.refresh_bookmarks_panel()
    new_index = fs.new_bookmark_index(before)
    assert new_index >= 0, "Bookmark was not created - no new row in the panel"

    # Leave the shared camera as it was found
    stamp = fs.bookmark_stamp(new_index)
    fs.delete_bookmark(index=new_index)
    fs.verify_bookmark_deleted(stamp)


class TestViewsBookmarks:
    """Bookmark operations in full screen mode, each on its own bookmark."""

    @pytest.fixture(autouse=True)
    def setup(self, fullscreen_page):
        self.page = fullscreen_page.page
        self.fs = fullscreen_page
        self._owned: list[str] = []
        yield
        # Remove what this test made, by its stamp - never a bare index,
        # which could be someone's own bookmark
        for stamp in reversed(self._owned):
            try:
                self.fs.refresh_bookmarks_panel()
                index = self.fs.bookmark_index_by_name(stamp)
                if index >= 0:
                    self.fs.delete_bookmark(index=index)
            # best-effort: the verdict is already decided
            except Exception:
                pass

    def _own_a_bookmark(self) -> str:
        """Make a bookmark this test owns and return its playback stamp."""
        self.fs.refresh_bookmarks_panel()
        before = self.fs.bookmark_texts()
        self.fs.create_bookmark()
        self.fs.refresh_bookmarks_panel()
        index = self.fs.new_bookmark_index(before)
        assert index >= 0, "the created bookmark is not in the panel"
        stamp = self.fs.bookmark_stamp(index)
        self._owned.append(stamp)
        return stamp

    def _index(self, stamp: str) -> int:
        index = self.fs.bookmark_index_by_name(stamp)
        assert index >= 0, f"the bookmark at {stamp!r} is not in the panel"
        return index

    @pytest.mark.ui
    @pytest.mark.bookmark
    @pytest.mark.views_fullscreen
    def test_open_bookmarks_panel(self):
        """Verify bookmarks panel opens when clicking the dots icon.

        Steps:
        1. In full screen, click the bookmarks dots icon.
           Expected: The panel opens and lists the bookmark.
        """
        stamp = self._own_a_bookmark()
        assert self.fs.bookmark_index_by_name(stamp) >= 0, (
            "The bookmarks panel should list the bookmark"
        )

    @pytest.mark.ui
    @pytest.mark.bookmark
    @pytest.mark.views_fullscreen
    def test_close_bookmarks_panel(self):
        """Verify bookmarks panel closes when clicking the dots icon again.

        Steps:
        1. With the panel open, click the dots icon again.
           Expected: The bookmark rows are no longer shown.
        """
        self._own_a_bookmark()
        self.fs.close_bookmarks_panel()
        # the retrying expect absorbs the close animation
        expect(self.fs.bookmark_items.first).to_be_hidden(timeout=5000)

    @pytest.mark.ui
    @pytest.mark.bookmark
    @pytest.mark.views_fullscreen
    def test_play_bookmark(self):
        """Verify clicking a bookmark navigates to that snapshot position.

        Steps:
        1. Click the bookmark in the panel.
           Expected: The player streams that archive position, not live.
        """
        stamp = self._own_a_bookmark()
        self.fs.play_bookmark(self._index(stamp))
        assert self.fs.is_streaming(), "Stream should be available after clicking bookmark"
        assert not self.fs.is_live_mode(), "Should be in archive mode after clicking bookmark"

    @pytest.mark.ui
    @pytest.mark.bookmark
    @pytest.mark.views_fullscreen
    def test_bookmark_options_menu(self):
        """Verify the 3-dot options menu shows 4 options.

        Steps:
        1. Click the 3-dot icon on the bookmark row.
           Expected: The menu shows Rename, Export, Share and Delete.
        """
        stamp = self._own_a_bookmark()
        self.fs.open_bookmark_options(self._index(stamp))

        option_count = self.fs.bookmark_options.count()
        assert option_count >= 4, (
            f"Expected at least 4 bookmark options (Rename, Export, Share, "
            f"Delete), got {option_count}"
        )

    @pytest.mark.ui
    @pytest.mark.bookmark
    @pytest.mark.views_fullscreen
    @pytest.mark.slow
    def test_export_bookmark(self):
        """Verify a bookmark can be exported (export dialog completes).

        Steps:
        1. Choose Export on the bookmark, name the file and confirm.
           Expected: The export progress bar appears and completes.
        """
        stamp = self._own_a_bookmark()
        filename = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        # oracle: export_bookmark raises unless the export dialog opens
        # and the progress bar appears and completes
        self.fs.export_bookmark(index=self._index(stamp), filename=filename)

    @pytest.mark.ui
    @pytest.mark.bookmark
    @pytest.mark.views_fullscreen
    def test_share_bookmark(self):
        """Verify a bookmark can be shared (share dialog shows success).

        Steps:
        1. Choose Share on the bookmark, enter an address and confirm.
           Expected: The dialog reports the share succeeded.
        """
        stamp = self._own_a_bookmark()
        filename = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        self.fs.share_bookmark(
            index=self._index(stamp),
            email="person@example.com",
            filename=filename,
        )
        expect(self.fs.share_success).to_be_visible(timeout=5000)

    @pytest.mark.ui
    @pytest.mark.bookmark
    @pytest.mark.views_fullscreen
    def test_rename_bookmark(self):
        """Verify a bookmark can be renamed and the new name appears.

        Steps:
        1. Choose Rename on the bookmark, type a new name and save.
           Expected: The bookmark row shows the new name.
        """
        stamp = self._own_a_bookmark()
        new_name = _unique_name()
        self.fs.rename_bookmark(index=self._index(stamp), new_name=new_name)

        # The panel keeps the old label until it re-opens; the stamp is
        # untouched by a rename, so the row is still found by it.
        self.fs.refresh_bookmarks_panel()
        row_text = self.fs.bookmark_items.nth(self._index(stamp)).inner_text()
        assert new_name in row_text, (
            f"The renamed bookmark still reads {row_text!r}"
        )

    @pytest.mark.ui
    @pytest.mark.bookmark
    @pytest.mark.views_fullscreen
    def test_delete_bookmark(self):
        """Verify a bookmark can be deleted with confirmation.

        Steps:
        1. Choose Delete on the bookmark and confirm.
           Expected: The bookmark is no longer listed.
        """
        stamp = self._own_a_bookmark()
        self.fs.delete_bookmark(index=self._index(stamp))
        # oracle: verify_bookmark_deleted re-opens the panel between
        # reads and raises while the row is still listed
        self.fs.verify_bookmark_deleted(stamp)
        self._owned.remove(stamp)  # gone; teardown must not re-seek it
