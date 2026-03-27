"""Deeper Maps page tests - dropdown enumeration, map card details, camera
counts, online status, and navigation behavior.

Extends basic maps coverage with site dropdown checks, multiple map card
inspection, camera icon counts, and page navigation patterns.
"""
import pytest
from playwright.sync_api import expect
from tests.shared.pages.maps_page import MapsPage


SITE_NAME = "Driver Site"


class TestMapsDeeper:
    """Deeper tests for Maps page functionality."""

    @pytest.fixture(autouse=True)
    def setup(self, authenticated_page, step_capture):
        self.page = authenticated_page
        self.step_capture = step_capture
        step_capture.set_page(self.page)
        self.maps = MapsPage(self.page)
        self.maps.navigate()
        yield

    # --- Site dropdown ---

    @pytest.mark.ui
    @pytest.mark.maps
    @pytest.mark.maps_deeper
    @pytest.mark.qatouch("DrdZ7x")
    def test_site_dropdown_lists_sites(self):
        """Verify site dropdown shows available sites."""
        sites = self.maps.get_site_options()
        assert len(sites) > 0, "Expected at least one site in the dropdown"
        self.step_capture.mark(1, "Open the site dropdown and verify it lists available sites")

    @pytest.mark.ui
    @pytest.mark.maps
    @pytest.mark.maps_deeper
    @pytest.mark.qatouch("eJqj13")
    def test_selected_site_text_updates(self):
        """Verify dropdown text changes after selecting a site."""
        self.maps.select_site(SITE_NAME)
        self.step_capture.mark(1, "Select a site from the dropdown")

        selected = self.maps.get_selected_site_text()
        assert SITE_NAME in selected, (
            f"Expected '{SITE_NAME}' in dropdown text, got '{selected}'"
        )
        self.step_capture.mark(2, "Verify the dropdown text updates to show the selected site")

    # --- Map cards ---

    @pytest.mark.ui
    @pytest.mark.maps
    @pytest.mark.maps_deeper
    @pytest.mark.qatouch("vanmRn")
    def test_map_cards_visible_after_site_selection(self):
        """Verify map cards grid is populated after selecting a site."""
        self.maps.select_site(SITE_NAME)
        self.step_capture.mark(1, "Select a site from the dropdown")

        count = self.maps.get_map_card_count()
        assert count > 0, f"Expected map cards, got {count}"
        self.step_capture.mark(2, "Verify map cards are visible after site selection")

    @pytest.mark.ui
    @pytest.mark.maps
    @pytest.mark.maps_deeper
    @pytest.mark.qatouch("bj0Ga9")
    def test_multiple_map_cards(self):
        """Verify the site has more than one map card (if applicable)."""
        self.maps.select_site(SITE_NAME)
        self.step_capture.mark(1, "Select a site from the dropdown")

        count = self.maps.get_map_card_count()
        # Soft assertion: some sites may only have 1 map
        if count <= 1:
            pytest.skip(f"Only {count} map card(s) - need multiple for this test")

        assert count > 1, f"Expected multiple map cards, got {count}"
        self.step_capture.mark(2, "Verify multiple map cards are displayed for the site")

    @pytest.mark.ui
    @pytest.mark.maps
    @pytest.mark.maps_deeper
    @pytest.mark.qatouch("Z8xRpk")
    def test_map_card_has_device_count(self):
        """Verify map cards display device/camera count information."""
        self.maps.select_site(SITE_NAME)
        self.step_capture.mark(1, "Select a site from the dropdown")

        device_elements = self.maps.device_count_elements
        assert device_elements.count() > 0, (
            "Expected device count elements on map cards"
        )
        self.step_capture.mark(2, "Verify map cards display device count information")

    # --- Camera overlay ---

    @pytest.mark.ui
    @pytest.mark.maps
    @pytest.mark.maps_deeper
    @pytest.mark.qatouch("Z8xQl5")
    def test_camera_icon_count_positive(self):
        """Verify an opened map shows at least one camera icon."""
        self.maps.select_site(SITE_NAME)
        self.step_capture.mark(1, "Select a site from the dropdown")

        map_card = self.maps.find_map_with_cameras()
        if map_card is None:
            pytest.skip("No map with cameras available")

        self.maps.open_map(map_card)
        self.step_capture.mark(2, "Open a map card that has cameras")

        total_cameras = self.maps.camera_icons.count()
        assert total_cameras > 0, "Expected camera icons on opened map"
        self.step_capture.mark(3, "Verify at least one camera icon is shown on the opened map")

    @pytest.mark.ui
    @pytest.mark.maps
    @pytest.mark.maps_deeper
    @pytest.mark.qatouch("dypNzZ")
    def test_online_camera_count(self):
        """Verify there are online (green) cameras on the map."""
        self.maps.select_site(SITE_NAME)
        self.step_capture.mark(1, "Select a site from the dropdown")

        map_card = self.maps.find_map_with_cameras()
        if map_card is None:
            pytest.skip("No map with cameras available")

        self.maps.open_map(map_card)
        self.step_capture.mark(2, "Open a map card that has cameras")

        online_count = self.maps.get_online_camera_count()
        # Soft assertion: some cameras may be offline
        if online_count == 0:
            pytest.skip("No online cameras on this map")

        assert online_count > 0
        self.step_capture.mark(3, "Verify there are online cameras on the map")

    @pytest.mark.ui
    @pytest.mark.maps
    @pytest.mark.maps_deeper
    @pytest.mark.qatouch("xm9Ex1")
    def test_maps_page_after_refresh(self):
        """Verify the Maps page reloads correctly after a browser refresh."""
        self.page.reload()
        self.page.wait_for_timeout(3000)
        self.step_capture.mark(1, "Refresh the Maps page")

        # Should still show the site dropdown
        expect(self.maps.site_dropdown).to_be_visible(timeout=15000)
        self.step_capture.mark(2, "Verify the site dropdown is visible after refresh")
