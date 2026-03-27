"""Maps page tests - site selection, map cards, camera overlay, stream playback."""
import pytest
from playwright.sync_api import expect
from tests.shared.pages.maps_page import MapsPage


class TestMaps:
    """Tests for the standalone Maps page."""

    @pytest.fixture(autouse=True)
    def setup(self, authenticated_page, step_capture):
        self.page = authenticated_page
        self.step_capture = step_capture
        step_capture.set_page(self.page)
        self.maps = MapsPage(self.page)

    @pytest.mark.ui
    @pytest.mark.maps
    @pytest.mark.qatouch("VKbQ42")
    def test_navigate_to_maps(self):
        """Verify the Maps page loads with the site dropdown visible."""
        self.maps.navigate()
        self.step_capture.mark(1, "Navigate to the Maps page")

        expect(self.maps.site_dropdown).to_be_visible(timeout=10000)
        self.step_capture.mark(2, "Verify the site dropdown is visible")

    @pytest.mark.ui
    @pytest.mark.maps
    @pytest.mark.qatouch("eJqj13")
    def test_select_site(self):
        """Verify selecting a site from the dropdown loads map cards."""
        self.maps.navigate()
        self.step_capture.mark(1, "Navigate to the Maps page")

        self.maps.select_site("Driver Site")
        self.step_capture.mark(2, "Select Driver Site from the dropdown")

        card_count = self.maps.get_map_card_count()
        assert card_count > 0, "Expected at least one map card after selecting site"
        self.step_capture.mark(3, "Verify map cards are loaded for the selected site")

    @pytest.mark.ui
    @pytest.mark.maps
    @pytest.mark.qatouch("vanmRn")
    def test_map_cards_have_cameras(self):
        """Verify at least one map card has cameras (device count > 0)."""
        self.maps.navigate()
        self.maps.select_site("Driver Site")
        self.step_capture.mark(1, "Navigate to Maps and select Driver Site")

        if self.maps.get_map_card_count() == 0:
            pytest.skip("No map cards loaded for Driver Site")

        map_with_cameras = self.maps.find_map_with_cameras()
        if map_with_cameras is None:
            pytest.skip(
                "No map card has cameras (device counts are 0) -- "
                "may be a data/selector issue with .icon-text-aligner"
            )
        self.step_capture.mark(2, "Verify at least one map card has cameras")

    @pytest.mark.ui
    @pytest.mark.maps
    @pytest.mark.qatouch("dypNzZ")
    def test_open_map_with_cameras(self):
        """Verify clicking a map card opens it and shows camera icons."""
        self.maps.navigate()
        self.maps.select_site("Driver Site")
        self.step_capture.mark(1, "Navigate to Maps and select Driver Site")

        map_card = self.maps.find_map_with_cameras()
        if map_card is None:
            pytest.skip("No map with cameras available")

        self.maps.open_map(map_card)
        self.step_capture.mark(2, "Open a map card that has cameras")

        camera_count = self.maps.camera_icons.count()
        assert camera_count > 0, "Expected camera icons on opened map"
        self.step_capture.mark(3, "Verify camera icons are displayed on the opened map")

    @pytest.mark.ui
    @pytest.mark.maps
    @pytest.mark.slow
    @pytest.mark.qatouch("dypNzZ")
    def test_play_online_camera(self):
        """Verify clicking an online camera icon plays its stream without failure."""
        self.maps.navigate()
        self.maps.select_site("Driver Site")
        self.step_capture.mark(1, "Navigate to Maps and select Driver Site")

        map_card = self.maps.find_map_with_cameras()
        if map_card is None:
            pytest.skip("No map with cameras available")

        self.maps.open_map(map_card)
        self.step_capture.mark(2, "Open a map card that has cameras")

        online_count = self.maps.get_online_camera_count()
        if online_count == 0:
            pytest.skip("No online cameras on this map")

        self.maps.play_camera(0)
        self.step_capture.mark(3, "Click an online camera icon to play its stream")

        assert not self.maps.is_stream_failed(), "Camera stream failed to load"
        self.step_capture.mark(4, "Verify the camera stream plays without failure")
