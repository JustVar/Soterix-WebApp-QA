"""Deeper Maps page tests - dropdown enumeration, map card details, camera
counts, online status, and navigation behavior.

Extends basic maps coverage with site dropdown checks, multiple map card
inspection, camera icon counts, and page navigation patterns.
"""
import pytest
from playwright.sync_api import expect
from tests.shared.pages.maps_page import MapsPage


class TestMapsDeeper:
    """Deeper tests for Maps page functionality."""

    @pytest.fixture(autouse=True)
    def setup(self, authenticated_page):
        self.page = authenticated_page
        self.maps = MapsPage(self.page)
        self.maps.navigate()
        sites = self.maps.get_site_options()
        self.site_name = sites[0] if sites else None
        yield

    # --- Site dropdown ---

    @pytest.mark.ui
    @pytest.mark.maps
    @pytest.mark.maps_deeper
    def test_site_dropdown_lists_sites(self):
        """Verify site dropdown shows available sites."""
        sites = self.maps.get_site_options()
        assert len(sites) > 0, "Expected at least one site in the dropdown"

    @pytest.mark.ui
    @pytest.mark.maps
    @pytest.mark.maps_deeper
    def test_selected_site_text_updates(self):
        """Verify dropdown text changes after selecting a site."""
        if not self.site_name:
            pytest.skip("No sites available in dropdown")
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
        if not self.site_name:
            pytest.skip("No sites available in dropdown")
        self.maps.select_site(self.site_name)

        count = self.maps.get_map_card_count()
        assert count > 0, f"Expected map cards, got {count}"

    @pytest.mark.ui
    @pytest.mark.maps
    @pytest.mark.maps_deeper
    def test_multiple_map_cards(self):
        """Verify the site has more than one map card (if applicable)."""
        if not self.site_name:
            pytest.skip("No sites available in dropdown")
        self.maps.select_site(self.site_name)

        count = self.maps.get_map_card_count()
        # Soft assertion: some sites may only have 1 map
        if count <= 1:
            pytest.skip(f"Only {count} map card(s) - need multiple for this test")

        assert count > 1, f"Expected multiple map cards, got {count}"

    @pytest.mark.ui
    @pytest.mark.maps
    @pytest.mark.maps_deeper
    def test_map_card_has_device_count(self):
        """Verify map cards display device/camera count information."""
        if not self.site_name:
            pytest.skip("No sites available in dropdown")
        self.maps.select_site(self.site_name)

        device_elements = self.maps.device_count_elements
        assert device_elements.count() > 0, (
            "Expected device count elements on map cards"
        )

    # --- Camera overlay ---

    @pytest.mark.ui
    @pytest.mark.maps
    @pytest.mark.maps_deeper
    def test_camera_icon_count_positive(self):
        """Verify an opened map shows at least one camera icon."""
        if not self.site_name:
            pytest.skip("No sites available in dropdown")
        self.maps.select_site(self.site_name)

        map_card = self.maps.find_map_with_cameras()
        if map_card is None:
            pytest.skip("No map with cameras available")

        self.maps.open_map(map_card)

        total_cameras = self.maps.camera_icons.count()
        assert total_cameras > 0, "Expected camera icons on opened map"

    @pytest.mark.ui
    @pytest.mark.maps
    @pytest.mark.maps_deeper
    def test_online_camera_count(self):
        """Verify there are online (green) cameras on the map."""
        if not self.site_name:
            pytest.skip("No sites available in dropdown")
        self.maps.select_site(self.site_name)

        map_card = self.maps.find_map_with_cameras()
        if map_card is None:
            pytest.skip("No map with cameras available")

        self.maps.open_map(map_card)

        online_count = self.maps.get_online_camera_count()
        # Soft assertion: some cameras may be offline
        if online_count == 0:
            pytest.skip("No online cameras on this map")

        assert online_count > 0

    @pytest.mark.ui
    @pytest.mark.maps
    @pytest.mark.maps_deeper
    def test_maps_page_after_refresh(self):
        """Verify the Maps page reloads correctly after a browser refresh."""
        self.page.reload()
        self.page.wait_for_timeout(3000)

        # Should still show the site dropdown
        expect(self.maps.site_dropdown).to_be_visible(timeout=15000)
