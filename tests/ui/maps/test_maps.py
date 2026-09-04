"""Maps page tests - site selection, map cards, camera overlay, stream playback."""
import pytest
from playwright.sync_api import expect

from config.base_config import config
from tests.shared.helpers.surface import require_items
from tests.shared.pages.maps_page import MapsPage


class TestMaps:
    """Tests for the standalone Maps page."""

    @pytest.fixture(autouse=True)
    def setup(self, authenticated_page):
        self.page = authenticated_page
        self.maps = MapsPage(self.page)
        self.maps.navigate()
        # The configured site, not whichever the dropdown lists first:
        # every test here used to open the dropdown, take options[0]
        # and skip "No sites available" when the read came back empty,
        # so a tenant rename and a broken page reported the same
        # (register item 25). select_site now raises naming the sites
        # that ARE offered.
        self.site_name = config.get("test_site_name")

    def _map_with_cameras_or_skip(self):
        """A map card with cameras, after proving the card grid rendered.

        An empty grid is a data fact and skips; a grid that never
        rendered is a fault and fails (register item 25).
        """
        require_items(
            self.maps.map_cards,
            container=self.maps.dropdown_text,
            surface=f"Maps page for site '{self.site_name}'",
            artifact="map card",
            empty_means="no map is published under this site",
        )
        card = self.maps.find_map_with_cameras()
        if card is None:
            pytest.skip(
                f"All {self.maps.get_map_card_count()} map card(s) under "
                f"'{self.site_name}' report a device count of 0: no camera "
                f"is placed on a map"
            )
        return card

    @pytest.mark.ui
    @pytest.mark.maps
    def test_navigate_to_maps(self):
        """Verify the Maps page loads with the site dropdown visible."""
        expect(self.maps.site_dropdown).to_be_visible(timeout=10000)

    @pytest.mark.ui
    @pytest.mark.maps
    def test_select_site(self):
        """Verify selecting a site from the dropdown loads map cards."""
        self.maps.select_site(self.site_name)

        card_count = self.maps.get_map_card_count()
        assert card_count > 0, "Expected at least one map card after selecting site"

    @pytest.mark.ui
    @pytest.mark.maps
    def test_map_cards_have_cameras(self):
        """Verify at least one map card has cameras (device count > 0)."""
        self.maps.select_site(self.site_name)
        map_with_cameras = self._map_with_cameras_or_skip()
        # the found card must be a real rendered card, not a hidden
        # mounted copy (the finder reads counts, not visibility)
        expect(map_with_cameras).to_be_visible(timeout=5000)

    @pytest.mark.ui
    @pytest.mark.maps
    def test_open_map_with_cameras(self):
        """Verify clicking a map card opens it and shows camera icons."""
        self.maps.select_site(self.site_name)
        map_card = self._map_with_cameras_or_skip()

        self.maps.open_map(map_card)

        camera_count = self.maps.camera_icons.count()
        assert camera_count > 0, "Expected camera icons on opened map"

    @pytest.mark.ui
    @pytest.mark.maps
    @pytest.mark.slow
    def test_play_online_camera(self):
        """Verify clicking an online camera icon plays its stream without failure."""
        self.maps.select_site(self.site_name)
        map_card = self._map_with_cameras_or_skip()

        self.maps.open_map(map_card)

        online_count = self.maps.get_online_camera_count()
        if online_count == 0:
            # The map is open and its camera icons are on screen, so
            # this reads the icons' own online state, not an absence.
            pytest.skip(
                f"The open map under '{self.site_name}' shows "
                f"{self.maps.camera_icons.count()} camera icon(s) and none "
                f"is online (no green icon): nothing to play"
            )

        self.maps.play_camera(0)

        # The old body skipped on the failure overlay and closed with
        # `assert True`, so a dead stream and a live one reported the
        # same (register item 25). The overlay is the tenant's stream
        # failure, and its text is what run.py --retry-streams matches,
        # so it goes red and gets counted.
        assert not self.maps.is_stream_failed(), (
            f"Playing the first online camera on a map under "
            f"'{self.site_name}' raised the tenant's failure overlay: the "
            f"camera failed to load"
        )
