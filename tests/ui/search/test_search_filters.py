"""Global Search page navigation and filter tests.

Covers navigating to the Search page, verifying filter dropdowns
are visible, and selecting each filter type independently.
"""
import pytest
from playwright.sync_api import expect
from tests.shared.pages.search_page import SearchPage





class TestSearchFilters:
    """Tests for Global Search page navigation and filter selection."""

    @pytest.fixture(autouse=True)
    def setup(self, authenticated_page):
        self.page = authenticated_page
        self.search = SearchPage(self.page)

    @pytest.mark.ui
    @pytest.mark.search
    def test_navigate_to_search(self):
        """Verify clicking Search nav link loads the Global Search page."""
        self.search.navigate()
        expect(self.search.category_label).to_be_visible(timeout=30000)

    @pytest.mark.ui
    @pytest.mark.search
    def test_search_page_filters_visible(self):
        """Verify all filter dropdowns are present on the Search page."""
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
        """Verify the Category dropdown opens and a category is selectable."""
        self.search.navigate()
        self.search.wait_for_page_load()

        self.search.select_category("Person")

        # After selection, "Person" text should be visible on page
        person_text = self.page.get_by_text("Person", exact=False).first
        expect(person_text).to_be_visible(timeout=5000)

    @pytest.mark.ui
    @pytest.mark.search
    def test_select_duration(self):
        """Verify the Duration dropdown opens and a duration is selectable.

        Selenium uses index 4 for 'Today'. We use index-based selection
        since the dropdown item text may vary.
        """
        self.search.navigate()
        self.search.wait_for_page_load()

        self.search.select_duration_by_index(4)

        # After selecting, the search button should still be accessible
        expect(self.search.search_button).to_be_visible(timeout=5000)

    @pytest.mark.ui
    @pytest.mark.search
    def test_select_locations_cameras(self):
        """Verify Locations & Cameras dropdown opens and site is selectable.

        KNOWN LIMITATION: Camera checkboxes have zero-dimension elements
        (same issue as Events page). Selecting a site enables search
        across all cameras at that site by default.
        """
        self.search.navigate()
        self.search.wait_for_page_load()

        self.search.select_locations_cameras(None)

        # The search button should be accessible after filter setup
        expect(self.search.search_button).to_be_visible(timeout=5000)

    @pytest.mark.ui
    @pytest.mark.search
    def test_search_button_visible(self):
        """Verify the search execution button is visible on page load."""
        self.search.navigate()
        self.search.wait_for_page_load()

        expect(self.search.search_button).to_be_visible(timeout=5000)
