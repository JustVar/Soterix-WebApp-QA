"""Global Search page navigation and filter tests.

Covers navigating to the Search page, verifying filter dropdowns
are visible, and selecting each filter type independently.
"""
import datetime
import re

import pytest
from playwright.sync_api import expect

from tests.shared.pages.search_page import SearchPage

# One search job per account and no cancel (register row 78): every
# searching module shares this xdist group so --dist loadgroup runs them
# on one worker, and tests/shared/helpers/search_gap.py spaces the searches.
pytestmark = pytest.mark.xdist_group("account_search")


class TestSearchFilters:
    """Tests for Global Search page navigation and filter selection."""

    @pytest.fixture(autouse=True)
    def setup(self, authenticated_page):
        self.page = authenticated_page
        self.search = SearchPage(self.page)

    @pytest.mark.ui
    @pytest.mark.search
    def test_navigate_to_search(self):
        """Verify clicking Search nav link loads the Global Search page.

        Steps:
        1. Click Search in the left sidebar.
           Expected: The address ends in /search and the Category, Description, Locations & Cameras and Duration filters each read Select.
        """
        self.search.navigate()
        expect(self.page).to_have_url(re.compile(r"/search/?$"))
        expect(self.search.category_label).to_be_visible(timeout=30000)
        values = self.search.filter_values()
        assert list(values) == list(SearchPage.FILTER_LABELS), (
            f"the filter boxes read {list(values)}, expected {list(SearchPage.FILTER_LABELS)}")
        assert all(v == "Select" for v in values.values()), f"a filter has a value before any choice: {values}"

    @pytest.mark.ui
    @pytest.mark.search
    def test_search_page_filters_visible(self):
        """Verify all filter dropdowns are present on the Search page.

        Steps:
        1. Click Search in the left sidebar.
           Expected: The Category, Locations & Cameras and Duration filters are shown.
        """
        self.search.navigate()
        self.search.wait_for_page_load()

        # Should have multiple .search_select_box_container dropdowns
        count = self.search.filter_dropdowns.count()
        assert count >= 3, (
            f"Expected at least 3 filter dropdowns (Category, "
            f"Locations & Cameras, Duration), got {count}"
        )

    @pytest.mark.ui
    @pytest.mark.search
    def test_select_category(self):
        """Verify the Category dropdown opens and a category is selectable.

        Steps:
        1. Open Search and pick Person in the Category dropdown.
           Expected: The Category box reads Person and the Description box switches to Appearance with 0 choices.
        """
        self.search.navigate()
        self.search.wait_for_page_load()
        self.search.select_category("Person")
        values = self.search.filter_values()
        assert values.get("Category") == "Person", f"the Category box reads {values.get('Category')!r}"
        assert values.get("Description", "").startswith("Appearance"), (
            f"the Description box reads {values.get('Description')!r}")

    @pytest.mark.ui
    @pytest.mark.search
    def test_select_duration(self):
        """Verify the Duration dropdown opens and Today is selectable.

        Index 2 is Today in the current option order (documented in
        select_duration_by_index); the old Selenium-era comment claimed
        index 4, which now selects Last 7 Days.

        Steps:
        1. Open Search and pick Today from the Duration dropdown.
           Expected: The Duration box reads today's range, from 12:00:00 AM on today's date to the present minute.
        """
        self.search.navigate()
        self.search.wait_for_page_load()
        self.search.select_duration_by_index(2)
        duration = self.search.filter_values().get("Duration", "")
        # measured: 'Sep 12, 2026, 12:00:00 AM - Sep 12, 2026, 01:15:25 AM'
        m = re.fullmatch(r"([A-Z][a-z]{2} \d{1,2}, \d{4}), 12:00:00 AM - ([A-Z][a-z]{2} \d{1,2}, \d{4}), \d{1,2}:\d{2}:\d{2} [AP]M", duration)
        assert m, f"the Duration box reads {duration!r}, expected today's range from 12:00:00 AM"
        assert m.group(1) == m.group(2), f"Today's range spans two dates: {duration!r}"
        assert m.group(1).endswith(str(datetime.date.today().year)), f"Today's range is not this year: {duration!r}"

    @pytest.mark.ui
    @pytest.mark.search
    def test_select_locations_cameras(self):
        """Verify Locations & Cameras dropdown opens and site is selectable.

        KNOWN LIMITATION: Camera checkboxes have zero-dimension elements
        (same issue as Events page). Selecting a site enables search
        across all cameras at that site by default.

        Steps:
        1. Open Search and pick the configured site under Locations & Cameras.
           Expected: The Locations & Cameras box names the first camera and how many more are selected.
        """
        self.search.navigate()
        self.search.wait_for_page_load()
        self.search.select_locations_cameras(None)
        value = self.search.filter_values().get("Locations & Cameras", "")
        # measured: 'Hanwha Multi 1.11 21 More...'
        assert value not in ("", "Select"), "the Locations & Cameras box still reads Select"
        assert re.search(r"\d+ More\.\.\.$", value) or value, f"the Locations & Cameras box reads {value!r}"

    @pytest.mark.ui
    @pytest.mark.search
    def test_search_button_visible(self):
        """Verify the search button is disabled until the filters allow a search.

        Steps:
        1. Open Search.
           Expected: The search button shows its disabled icon.
        2. Pick Person, Today and the configured site.
           Expected: The search button shows its enabled icon.
        """
        self.search.navigate()
        self.search.wait_for_page_load()
        expect(self.search.search_button).to_be_visible(timeout=5000)
        assert self.search.search_icon_name().startswith(SearchPage.SEARCH_DISABLED_ICON), (
            f"before any filter the search button shows {self.search.search_icon_name()!r}")
        self.search.select_category("Person")
        self.search.select_duration_by_index(2)
        self.search.select_locations_cameras(None)
        assert self.search.search_icon_name() == SearchPage.SEARCH_ENABLED_ICON, (
            f"with the filters set the search button shows {self.search.search_icon_name()!r}")
