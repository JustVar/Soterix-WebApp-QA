"""Event search, filtering, and pin tests.

Covers the Events page search flow: site selection, camera selection,
duration filtering, searching, validating results, and pinning events.
"""
import pytest
from playwright.sync_api import expect
from tests.shared.pages.events_page import EventsPage


# Site name used across event tests (same as Views tests)
SITE_NAME = "Driver Site"


class TestEventsSearch:
    """Tests for Events page search and pin functionality."""

    @pytest.fixture(autouse=True)
    def setup(self, authenticated_page):
        self.page = authenticated_page
        self.events = EventsPage(self.page)

    @pytest.mark.ui
    @pytest.mark.events
    @pytest.mark.events_search
    def test_navigate_to_events(self):
        """Verify clicking Events nav link loads the events page."""
        self.events.navigate()
        expect(self.events.events_container).to_be_visible(timeout=60000)

    @pytest.mark.ui
    @pytest.mark.events
    @pytest.mark.events_search
    def test_select_site(self):
        """Verify site dropdown opens and a site can be selected."""
        self.events.navigate()
        self.events.wait_for_page_load()

        self.events.select_site(SITE_NAME)

        # After selecting, the dropdown should close and site name visible
        site_label = self.page.get_by_text(SITE_NAME, exact=False).first
        expect(site_label).to_be_visible(timeout=5000)

    @pytest.mark.ui
    @pytest.mark.events
    @pytest.mark.events_search
    def test_select_camera(self):
        """Verify camera dropdown opens and lists cameras.

        The camera dropdown uses a #simple-menu MUI Popover with a
        tree: Site > All Cameras > individual camera containers.
        Each container shows a thumbnail, camera name, and status icon.

        KNOWN LIMITATION: The MUI Checkbox inside each camera container
        has zero-dimension elements (no bounding box) and cannot be
        toggled via Playwright. Search uses 'all cameras' by default.
        """
        self.events.navigate()
        self.events.wait_for_page_load()

        self.events.select_site(SITE_NAME)
        self.events.select_first_available_camera(SITE_NAME)

        # After dismissing menu, search button should be visible
        expect(self.events.search_button).to_be_visible(timeout=5000)

    @pytest.mark.ui
    @pytest.mark.events
    @pytest.mark.events_search
    def test_select_duration(self):
        """Verify duration filter can be changed from default.

        Duration dropdown is disabled until a site is selected.
        """
        self.events.navigate()
        self.events.wait_for_page_load()

        # Site must be selected first (duration is disabled without it)
        self.events.select_site(SITE_NAME)
        self.events.select_duration("Last 7")

        # The selected duration text should be visible
        duration_label = self.page.get_by_text("Last 7", exact=False).first
        expect(duration_label).to_be_visible(timeout=5000)

    @pytest.mark.ui
    @pytest.mark.events
    @pytest.mark.events_search
    def test_select_rule(self):
        """Verify rule type filter opens and a rule can be selected.

        The 'All Rules' dropdown is an optional filter -- not required
        for search, but allows narrowing results by rule type.
        """
        self.events.navigate()
        self.events.wait_for_page_load()

        self.events.select_rule("Intrusion Detection")

        # After selecting, the combobox text should change from "All Rules"
        combo_text = self.page.locator('[role="combobox"]').first.inner_text()
        assert "Intrusion Detection" in combo_text, (
            f"Expected 'Intrusion Detection' in combobox, got '{combo_text}'"
        )

    @pytest.mark.ui
    @pytest.mark.events
    @pytest.mark.events_search
    def test_search_events(self):
        """Verify search returns event results after selecting filters.

        Uses default 'all cameras' (no specific camera selection) to
        ensure results are returned regardless of per-camera event data.
        """
        self.events.navigate()
        self.events.wait_for_page_load()

        self.events.select_site(SITE_NAME)
        self.events.select_duration("Last 7")
        self.events.search_events(timeout=60000)

        count = self.events.get_event_count()
        assert count > 0, "Expected at least one event result after search"

    @pytest.mark.ui
    @pytest.mark.events
    @pytest.mark.events_search
    def test_event_snapshots_valid(self):
        """Verify event thumbnails have real images, not placeholders."""
        self.events.navigate()
        self.events.wait_for_page_load()

        self.events.select_site(SITE_NAME)
        self.events.select_duration("Last 7")
        self.events.search_events(timeout=60000)

        assert self.events.has_valid_snapshots(), (
            "First event thumbnail should be a real image, "
            "not 'No_Image_Available' placeholder"
        )

    @pytest.mark.ui
    @pytest.mark.events
    @pytest.mark.events_search
    def test_pin_event(self):
        """Verify pinning an event updates the pinned clips counter."""
        self.events.navigate()
        self.events.wait_for_page_load()

        self.events.select_site(SITE_NAME)
        self.events.select_duration("Last 7")
        self.events.search_events(timeout=60000)

        self.events.pin_event(0)

        pinned_text = self.events.get_pinned_count_text()
        assert "1" in pinned_text, (
            f"Expected pinned count to contain '1', got '{pinned_text}'"
        )

    @pytest.mark.ui
    @pytest.mark.events
    @pytest.mark.events_search
    def test_review_pinned_clips_button(self):
        """Verify 'Review Pinned Clips' button appears after pinning."""
        self.events.navigate()
        self.events.wait_for_page_load()

        self.events.select_site(SITE_NAME)
        self.events.select_duration("Last 7")
        self.events.search_events(timeout=60000)

        self.events.pin_event(0)

        expect(self.events.review_pinned_button).to_be_visible(timeout=10000)

    @pytest.mark.ui
    @pytest.mark.events
    @pytest.mark.events_search
    def test_search_with_specific_camera(self):
        """Verify search filters results by a single camera channel.

        Uses route interception to modify the API channelList from all
        cameras to just channel 14 (Hanwha_6). This bypasses the MUI
        checkbox zero-dimension limitation while verifying per-camera
        search works at the API level.

        Channel 14 = Hanwha_6 (confirmed to have events in Last 7 Days).
        """
        self.events.navigate()
        self.events.wait_for_page_load()

        self.events.select_site(SITE_NAME)
        self.events.select_duration("Last 7")
        self.events.search_events_for_channels([14], timeout=60000)

        count = self.events.get_event_count()
        assert count > 0, (
            "Expected events for Hanwha_6 (channel 14) in the last 7 days"
        )

