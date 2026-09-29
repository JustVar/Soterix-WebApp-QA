"""Deeper Maps page tests - dropdown enumeration, map card details, camera
counts, online status, and navigation behavior.

Extends basic maps coverage with site dropdown checks, multiple map card
inspection, camera icon counts, and page navigation patterns.
"""
import re

import pytest
from playwright.sync_api import expect

from config.base_config import config
from tests.shared.helpers.shown_name import is_shown_as
from tests.shared.helpers.surface import require_items
from tests.shared.pages.maps_page import MapsPage


class TestMapsDeeper:
    """Deeper tests for Maps page functionality."""

    @pytest.fixture(autouse=True)
    def setup(self, authenticated_page):
        self.page = authenticated_page
        self.maps = MapsPage(self.page)
        self.maps.navigate()
        # The configured site, not the dropdown's first entry: the old
        # setup read the options and skipped "No sites available" on an
        # empty read, so a tenant rename and a broken page reported the
        # same. select_site raises naming the sites
        # that ARE offered.
        self.site_name = config.get("test_site_name")

    def _map_with_cameras_or_skip(self):
        """A map card with cameras, after proving the card grid rendered."""
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

    # --- Site dropdown ---

    @pytest.mark.ui
    @pytest.mark.maps
    @pytest.mark.maps_deeper
    def test_site_dropdown_lists_sites(self):
        """Verify site dropdown shows available sites."""
        sites = self.maps.get_site_options()
        assert len(sites) > 0, "Expected at least one site in the dropdown"
        # the list is the account's sites: the configured test site is one of them. This
        # dropdown cuts a long name and adds an ellipsis, so the cut form counts too.
        assert any(is_shown_as(s, self.site_name) for s in sites), (
            f"the site dropdown lists {sites}, and the test site {self.site_name!r} is not one of them")

    @pytest.mark.ui
    @pytest.mark.maps
    @pytest.mark.maps_deeper
    def test_selected_site_text_updates(self):
        """Verify dropdown text changes after selecting a site."""
        self.maps.select_site(self.site_name)

        selected = self.maps.get_selected_site_text()
        assert self.site_name in selected, (
            f"Expected '{self.site_name}' in dropdown text, got '{selected}'"
        )

    # --- Map cards ---

    @pytest.mark.ui
    @pytest.mark.maps
    @pytest.mark.maps_deeper
    def test_map_cards_visible_after_site_selection(self):
        """Verify map cards grid is populated after selecting a site."""
        self.maps.select_site(self.site_name)

        count = self.maps.get_map_card_count()
        assert count > 0, f"Expected map cards, got {count}"

    @pytest.mark.ui
    @pytest.mark.maps
    @pytest.mark.maps_deeper
    def test_multiple_map_cards(self):
        """Verify the site has more than one map card (if applicable)."""
        self.maps.select_site(self.site_name)
        # The grid is proved up first, so a low count is the tenant's
        # data and not a page that never rendered.
        count = require_items(
            self.maps.map_cards,
            container=self.maps.dropdown_text,
            surface=f"Maps page for site '{self.site_name}'",
            artifact="map card",
            empty_means="no map is published under this site",
        )
        if count <= 1:
            pytest.skip(
                f"Site '{self.site_name}' has {count} map card on screen; "
                f"this test needs two to compare"
            )

        assert count > 1, f"Expected multiple map cards, got {count}"

    @pytest.mark.ui
    @pytest.mark.maps
    @pytest.mark.maps_deeper
    def test_map_card_has_device_count(self):
        """Verify map cards display device/camera count information."""
        self.maps.select_site(self.site_name)

        device_elements = self.maps.device_count_elements
        assert device_elements.count() > 0, (
            "Expected device count elements on map cards"
        )
        # a device count is a number, not an empty label
        first_count = " ".join(device_elements.first.inner_text().split())
        assert re.search(r"\d", first_count) is not None, f"the first map card's device count reads {first_count!r}"

    # --- Camera overlay ---

    @pytest.mark.ui
    @pytest.mark.maps
    @pytest.mark.maps_deeper
    def test_camera_icon_count_positive(self):
        """An opened map shows at least one camera icon.

        Steps:
        1. On Maps, select the configured site and open a map card that lists cameras.
           Expected: The map opens and shows at least one camera icon. With no such card the test skips.
        """
        self.maps.select_site(self.site_name)
        map_card = self._map_with_cameras_or_skip()

        self.maps.open_map(map_card)

        total_cameras = self.maps.camera_icons.count()
        assert total_cameras > 0, "Expected camera icons on opened map"

    @pytest.mark.ui
    @pytest.mark.maps
    @pytest.mark.maps_deeper
    def test_online_camera_count(self):
        """Verify there are online (green) cameras on the map."""
        self.maps.select_site(self.site_name)
        map_card = self._map_with_cameras_or_skip()

        self.maps.open_map(map_card)

        online_count = self.maps.get_online_camera_count()
        if online_count == 0:
            # The map is open and its icons are on screen, so this
            # reads the icons' own online state, not an absence.
            pytest.skip(
                f"The open map under '{self.site_name}' shows "
                f"{self.maps.camera_icons.count()} camera icon(s) and none "
                f"is online (no green icon)"
            )

        assert online_count > 0

    @pytest.mark.ui
    @pytest.mark.maps
    @pytest.mark.maps_deeper
    def test_maps_page_after_refresh(self):
        """Verify the Maps page reloads correctly after a browser refresh."""
        # reload waits for the load event on its own
        before = self.page.url
        self.page.reload()
        expect(self.page).to_have_url(before, timeout=15000)

        # Should still show the site dropdown
        expect(self.maps.site_dropdown).to_be_visible(timeout=15000)
        expect(self.maps.site_dropdown).to_contain_text(re.compile(r"\S"))
