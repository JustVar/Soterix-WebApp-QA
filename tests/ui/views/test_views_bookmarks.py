"""Bookmark tests - creation (tile level) and operations (full screen mode).

Every operation test provisions its OWN bookmark through the internal API
(`api_bookmark`, named `AutoTest ...`, deleted at teardown) and finds it in
the panel by that name. Two app behaviours force this shape:

  - Panel rows carry only a positional id, so a bare index could be a real
    user's bookmark on the shared camera. A destructive test must not guess.
  - The panel does not repaint after a mutation, and a UI delete is a SOFT
    delete, so the API is the oracle for a delete or a rename: "gone" means
    deletedAt above 0 (`bookmark_deleted`), not a row leaving the panel.
"""
import datetime
import time

import pytest
from playwright.sync_api import expect

from tests.shared.api.fixtures import bookmark_deleted
from tests.shared.pages.fullscreen_page import FullScreenPage
from tests.shared.pages.views_page import ViewsPage


@pytest.mark.ui
@pytest.mark.bookmark
def test_add_bookmark(authenticated_page, api):
    """Create a bookmark on a streaming video tile.

    Steps:
    1. Open Views and load the configured camera into a tile.
       Expected: The camera streams in the first tile.
    2. Add a bookmark on that tile from its bookmark control.
       Expected: The site's bookmark list gains one live bookmark.
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

    listed = f"/REST/clipbookmark/{api.site_id}"
    before = {row["bookmarkId"] for row in api.get(listed)}

    views.add_bookmark_on_tile(tile_index=0)

    # The API is the oracle: the panel cannot tell a new bookmark from one
    # an earlier run left, and it does not repaint in place.
    created = [row for row in api.get(listed)
               if row["bookmarkId"] not in before and not bookmark_deleted(row)]
    assert len(created) == 1, (
        f"Expected exactly one new live bookmark after the add, got "
        f"{[row['bookmarkId'] for row in created]}"
    )

    # Do not leak it onto the shared camera
    api.delete(f"/REST/clipbookmark/{created[0]['bookmarkId']}")


class TestViewsBookmarks:
    """Bookmark operations in full screen mode, each on its own bookmark."""

    @pytest.fixture(autouse=True)
    def setup(self, fullscreen_page):
        self.page = fullscreen_page.page
        self.fs = fullscreen_page

    # far enough back to be a real archive position: a bookmark stamped
    # "now" seeks to the live edge, and the player stays in LIVE mode
    ARCHIVE_LAG_MS = 180_000

    def _own(self, api_bookmark) -> dict:
        """This test's own bookmark: provisioned through the API at an
        archive position, then located in the panel by its AutoTest
        name. Returns the row."""
        row = api_bookmark(
            timestamp_ms=int(time.time() * 1000) - self.ARCHIVE_LAG_MS)
        # the panel re-fetches only on re-open, so a bookmark made
        # outside it shows up only after a refresh
        self.fs.refresh_bookmarks_panel()
        assert self.fs.bookmark_index_by_name(row["comment"]) >= 0, (
            f"provisioned bookmark {row['comment']!r} is not in the panel"
        )
        return row

    def _idx(self, row: dict) -> int:
        idx = self.fs.bookmark_index_by_name(row["comment"])
        assert idx >= 0, f"{row['comment']!r} is not in the panel"
        return idx

    def _api_row(self, api, bookmark_id: int) -> dict | None:
        for row in api.get(f"/REST/clipbookmark/{api.site_id}"):
            if row["bookmarkId"] == bookmark_id:
                return row
        return None

    @pytest.mark.ui
    @pytest.mark.bookmark
    @pytest.mark.views_fullscreen
    def test_open_bookmarks_panel(self, api_bookmark):
        """Verify bookmarks panel opens when clicking the dots icon.

        Steps:
        1. Open a camera in full screen and click the bookmarks dots icon.
           Expected: The bookmarks panel opens and lists the bookmark.
        """
        row = self._own(api_bookmark)
        assert self.fs.bookmark_index_by_name(row["comment"]) >= 0, (
            "Bookmarks panel should list the bookmark after opening"
        )

    @pytest.mark.ui
    @pytest.mark.bookmark
    @pytest.mark.views_fullscreen
    def test_close_bookmarks_panel(self, api_bookmark):
        """Verify bookmarks panel closes when clicking the dots icon again.

        Steps:
        1. With the bookmarks panel open, click the dots icon again.
           Expected: The bookmark rows are no longer shown.
        """
        self._own(api_bookmark)
        self.fs.close_bookmarks_panel()
        # the retrying expect absorbs the close animation
        expect(self.fs.bookmark_items.first).to_be_hidden(timeout=5000)

    @pytest.mark.ui
    @pytest.mark.bookmark
    @pytest.mark.views_fullscreen
    def test_play_bookmark(self, api_bookmark):
        """Verify clicking a bookmark navigates to that snapshot position.

        Steps:
        1. Click a bookmark in the panel.
           Expected: The player streams that archive position, not live.
        """
        row = self._own(api_bookmark)
        self.fs.play_bookmark(self._idx(row))
        assert self.fs.is_streaming(), "Stream should be available after clicking bookmark"
        assert not self.fs.is_live_mode(), "Should be in archive mode after clicking bookmark"

    @pytest.mark.ui
    @pytest.mark.bookmark
    @pytest.mark.views_fullscreen
    def test_bookmark_options_menu(self, api_bookmark):
        """Verify the 3-dot options menu shows 4 options.

        Steps:
        1. Click the 3-dot icon on a bookmark row.
           Expected: The menu shows Rename, Export, Share and Delete.
        """
        row = self._own(api_bookmark)
        self.fs.open_bookmark_options(self._idx(row))

        option_count = self.fs.bookmark_options.count()
        assert option_count >= 4, (
            f"Expected at least 4 bookmark options (Rename, Export, Share, "
            f"Delete), got {option_count}"
        )

    @pytest.mark.ui
    @pytest.mark.bookmark
    @pytest.mark.views_fullscreen
    @pytest.mark.slow
    def test_export_bookmark(self, api_bookmark):
        """Verify a bookmark can be exported (export dialog completes).

        Steps:
        1. Choose Export on a bookmark, name the file and confirm.
           Expected: The export progress bar appears and completes.
        """
        row = self._own(api_bookmark)
        filename = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        # oracle: export_bookmark raises unless the export dialog opens
        # and the progress bar appears and completes
        self.fs.export_bookmark(index=self._idx(row), filename=filename)

    @pytest.mark.ui
    @pytest.mark.bookmark
    @pytest.mark.views_fullscreen
    def test_share_bookmark(self, api_bookmark):
        """Verify a bookmark can be shared (share dialog shows success).

        Steps:
        1. Choose Share on a bookmark, enter an address and confirm.
           Expected: The dialog reports the share succeeded.
        """
        row = self._own(api_bookmark)
        filename = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
        self.fs.share_bookmark(
            index=self._idx(row),
            email="person@example.com",
            filename=filename,
        )
        expect(self.fs.share_success).to_be_visible(timeout=5000)

    @pytest.mark.ui
    @pytest.mark.bookmark
    @pytest.mark.views_fullscreen
    def test_rename_bookmark(self, api_bookmark, api):
        """Verify a bookmark can be renamed and the new name persists.

        Steps:
        1. Choose Rename on a bookmark, type a new name and save.
           Expected: The bookmark keeps the new name.
        """
        row = self._own(api_bookmark)
        new_name = f"AutoTest Renamed {datetime.datetime.now():%H%M%S}"
        self.fs.rename_bookmark(index=self._idx(row), new_name=new_name)

        # The API is the oracle: the panel does not repaint after a
        # rename, so waiting for the new label there is flaky.
        stored = self._api_row(api, row["bookmarkId"])
        assert stored and stored.get("comment") == new_name, (
            f"Rename did not persist: the API row holds "
            f"{stored and stored.get('comment')!r}, expected {new_name!r}"
        )

    @pytest.mark.ui
    @pytest.mark.bookmark
    @pytest.mark.views_fullscreen
    def test_delete_bookmark(self, api_bookmark, api):
        """Verify a bookmark can be deleted with confirmation.

        Steps:
        1. Choose Delete on a bookmark and confirm.
           Expected: The bookmark is no longer listed.
        """
        row = self._own(api_bookmark)
        self.fs.delete_bookmark(index=self._idx(row))

        # A UI delete is a SOFT delete and it is ASYNC: the row stays
        # listed with deletedAt above 0, and the confirm click returns
        # before the server records it - so poll the API, the panel
        # never decides this.
        deadline = time.time() + 15
        while True:
            stored = self._api_row(api, row["bookmarkId"])
            if stored is None or bookmark_deleted(stored):
                # the oracle passed: soft-deleted (or purged) server-side
                return
            assert time.time() < deadline, (
                f"Delete did not register within 15s: bookmark "
                f"{row['bookmarkId']} still live (deletedAt "
                f"{stored.get('deletedAt')})"
            )
            # no DOM signal to wait on - the panel is not the oracle
            # here - so pace the API poll between reads
            time.sleep(1)
