"""Full screen video player tests - entering/exiting fullscreen, controls, streaming."""
import pytest
from playwright.sync_api import expect
from tests.shared.pages.views_page import ViewsPage
from tests.shared.pages.fullscreen_page import FullScreenPage


class TestViewsFullscreen:
    """Tests for entering/exiting full screen mode and basic player controls."""

    @pytest.fixture(autouse=True)
    def setup(self, authenticated_page):
        self.page = authenticated_page
        self.views = ViewsPage(self.page)
        self.views.navigate()
        self.views.wait_for_page_load()

        # Ensure at least one camera is in a tile
        video_tiles = self.page.locator(
            "[class*='video_container'][class*='new_video_player']"
        )
        if video_tiles.count() == 0:
            self.views.expand_site_and_show_cameras(None)
            self.views.add_first_camera_via_checkbox()
            # the tile appearing is the added signal
            video_tiles.first.wait_for(state="visible", timeout=30000)

    def _enter_fullscreen(self) -> FullScreenPage:
        """Enter full screen on the first tile and return the page object.

        The loader clearing is not playing: the stream oracle fails
        here, named, when the configured camera never plays.
        """
        self.views.enter_fullscreen_on_tile(0)
        fs = FullScreenPage(self.page)
        fs.wait_for_stream_loaded(timeout=120000)
        fs.assert_stream_playing()
        return fs

    @pytest.mark.ui
    @pytest.mark.fullscreen
    @pytest.mark.views_fullscreen
    @pytest.mark.livestream
    def test_enter_fullscreen(self):
        """Verify clicking zoom icon enters full screen and video streams."""
        fs = self._enter_fullscreen()

        assert fs.is_streaming(), "Video should be streaming in full screen"

    @pytest.mark.ui
    @pytest.mark.fullscreen
    @pytest.mark.views_fullscreen
    @pytest.mark.livestream
    def test_exit_fullscreen(self):
        """Verify exiting full screen returns to the views grid."""
        fs = self._enter_fullscreen()

        fs.exit_fullscreen()

        # back on the views grid: the add-tab button is the signal
        self.views.add_tab_button.wait_for(state="visible", timeout=10000)

    @pytest.mark.ui
    @pytest.mark.fullscreen
    @pytest.mark.views_fullscreen
    @pytest.mark.livestream
    def test_fullscreen_pause_play(self):
        """Verify timeline controls are present in full screen.

        In LIVE mode, pause/play controls are disabled (pause-disable-mode icons).
        In archive/playback mode, they would be active. This test verifies
        the control bar and timeline elements exist regardless of mode.
        """
        fs = self._enter_fullscreen()

        if fs.is_live_mode():
            # In live mode, timeline controls show as disabled icons
            expect(fs.pause_icon_live).to_be_visible(timeout=5000)
        else:
            # In archive mode, play/pause icons are active
            expect(fs.play_icon).to_be_visible(timeout=5000)

    @pytest.mark.ui
    @pytest.mark.fullscreen
    @pytest.mark.views_fullscreen
    @pytest.mark.livestream
    def test_fullscreen_controls_visible(self):
        """Verify player controls are visible in full screen."""
        fs = self._enter_fullscreen()

        # Four independent checks on one screen: soft, so a missing
        # control reports with the others instead of hiding them
        expect.soft(fs.exit_fullscreen_button).to_be_visible(timeout=5000)
        expect.soft(fs.bookmarks_toggle).to_be_visible(timeout=5000)
        expect.soft(fs.bottom_controls).to_be_visible(timeout=5000)
        expect.soft(fs.volume_control).to_be_visible(timeout=5000)

    @pytest.mark.ui
    @pytest.mark.fullscreen
    @pytest.mark.views_fullscreen
    @pytest.mark.livestream
    def test_fullscreen_video_streaming(self):
        """Verify video is actively streaming (no loader, no error state)."""
        fs = self._enter_fullscreen()

        # _enter_fullscreen already ran assert_stream_playing, so a
        # player that does not read as streaming here contradicts it.
        # The old body skipped instead, which meant the one test named
        # for streaming could never report a dead stream (item 25).
        # run.py --retry-streams reruns exactly this class.
        assert fs.is_streaming(), (
            "The fullscreen player passed assert_stream_playing but does "
            "not read as streaming: the stream stopped inside the test"
        )
        assert fs.streaming_failed.count() == 0, "No streaming failure messages expected"
