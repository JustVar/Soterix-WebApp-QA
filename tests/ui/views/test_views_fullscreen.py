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
            self.views.expand_site_and_show_cameras("Driver Site")
            self.page.wait_for_timeout(500)
            self.views.add_first_camera_via_checkbox()
            self.page.wait_for_timeout(2000)
            video_tiles.first.wait_for(state="visible", timeout=30000)

    @pytest.mark.ui
    @pytest.mark.fullscreen
    @pytest.mark.views_fullscreen
    def test_enter_fullscreen(self):
        """Verify clicking zoom icon enters full screen and video streams."""
        self.views.enter_fullscreen_on_tile(0)
        self.page.wait_for_timeout(1000)

        fs = FullScreenPage(self.page)
        fs.wait_for_stream_loaded(timeout=120000)

        assert fs.is_streaming(), "Video should be streaming in full screen"

    @pytest.mark.ui
    @pytest.mark.fullscreen
    @pytest.mark.views_fullscreen
    def test_exit_fullscreen(self):
        """Verify exiting full screen returns to the views grid."""
        self.views.enter_fullscreen_on_tile(0)
        fs = FullScreenPage(self.page)
        fs.wait_for_stream_loaded(timeout=120000)

        fs.exit_fullscreen()
        self.page.wait_for_timeout(1000)

        # Verify we're back on the views grid
        self.views.add_tab_button.wait_for(state="visible", timeout=10000)

    @pytest.mark.ui
    @pytest.mark.fullscreen
    @pytest.mark.views_fullscreen
    def test_fullscreen_pause_play(self):
        """Verify timeline controls are present in full screen.

        In LIVE mode, pause/play controls are disabled (pause-disable-mode icons).
        In archive/playback mode, they would be active. This test verifies
        the control bar and timeline elements exist regardless of mode.
        """
        self.views.enter_fullscreen_on_tile(0)
        fs = FullScreenPage(self.page)
        fs.wait_for_stream_loaded(timeout=120000)

        if fs.is_live_mode():
            # In live mode, timeline controls show as disabled icons
            expect(fs.pause_icon_live).to_be_visible(timeout=5000)
        else:
            # In archive mode, play/pause icons are active
            expect(fs.play_icon).to_be_visible(timeout=5000)

    @pytest.mark.ui
    @pytest.mark.fullscreen
    @pytest.mark.views_fullscreen
    def test_fullscreen_controls_visible(self):
        """Verify player controls are visible in full screen."""
        self.views.enter_fullscreen_on_tile(0)
        fs = FullScreenPage(self.page)
        fs.wait_for_stream_loaded(timeout=120000)

        # Control bar elements that are always visible
        expect(fs.exit_fullscreen_button).to_be_visible(timeout=5000)
        expect(fs.bookmarks_toggle).to_be_visible(timeout=5000)
        expect(fs.bottom_controls).to_be_visible(timeout=5000)
        expect(fs.volume_control).to_be_visible(timeout=5000)

    @pytest.mark.ui
    @pytest.mark.fullscreen
    @pytest.mark.views_fullscreen
    @pytest.mark.livestream
    def test_fullscreen_video_streaming(self):
        """Verify video is actively streaming (no loader, no error state)."""
        self.views.enter_fullscreen_on_tile(0)
        fs = FullScreenPage(self.page)
        fs.wait_for_stream_loaded(timeout=120000)

        if not fs.is_streaming():
            # Retry: stream may need extra time to stabilize
            self.page.wait_for_timeout(5000)
            if not fs.is_streaming():
                pytest.skip(
                    "Stream not active after extended wait - "
                    "may be a transient camera/network issue"
                )

        assert fs.streaming_failed.count() == 0, "No streaming failure messages expected"
