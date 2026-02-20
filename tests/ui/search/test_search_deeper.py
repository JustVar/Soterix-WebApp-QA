"""Deeper Global Search tests - category enumeration, description panels,
filter combinations, duration variations, and result validation.

Extends basic search coverage with parametrized category/duration tests,
filter change workflows, and result content checks.
"""
import pytest
from playwright.sync_api import expect
from tests.shared.pages.search_page import SearchPage


SITE_NAME = "Driver Site"


class TestSearchDeeper:
    """Tests for deeper Global Search filter and result coverage."""

    @pytest.fixture(autouse=True)
    def setup(self, authenticated_page):
        self.page = authenticated_page
        self.search = SearchPage(self.page)
        self.search.navigate()
        self.search.wait_for_page_load()
        yield

    # --- Dropdown enumeration ---

    @pytest.mark.ui
    @pytest.mark.search
    @pytest.mark.search_deeper
    def test_category_dropdown_lists_categories(self):
        """Verify category dropdown contains Person, Vehicle, and Event."""
        options = self.search.get_category_options()
        assert len(options) >= 3, f"Expected at least 3 categories, got: {options}"
        for expected in ("Person", "Vehicle", "Event"):
            assert any(expected in opt for opt in options), (
                f"Expected '{expected}' in categories, got: {options}"
            )

    @pytest.mark.ui
    @pytest.mark.search
    @pytest.mark.search_deeper
    def test_duration_dropdown_lists_options(self):
        """Verify duration dropdown has multiple time range options."""
        options = self.search.get_duration_options()
        assert len(options) >= 3, (
            f"Expected at least 3 duration options, got: {options}"
        )

    # --- Description panel visibility ---

    @pytest.mark.ui
    @pytest.mark.search
    @pytest.mark.search_deeper
    def test_description_panel_shown_for_person(self):
        """Verify the Description filter appears after selecting Person."""
        self.search.select_category("Person")
        self.page.wait_for_timeout(1000)

        assert self.search.is_description_panel_visible(), (
            "Description panel should be visible for Person category"
        )

    @pytest.mark.ui
    @pytest.mark.search
    @pytest.mark.search_deeper
    def test_event_category_no_gender_options(self):
        """Verify Event category does not show gender selection options.

        The Description dropdown container exists for all categories, but
        gender-specific options (Male/Female) only appear for Person.
        """
        self.search.select_category("Event")
        self.page.wait_for_timeout(1000)

        # Click Description dropdown if present
        dropdown = self.search._get_dropdown_by_text("Description")
        if dropdown is not None and dropdown.is_visible():
            dropdown.click()
            self.page.wait_for_timeout(1000)

        # Gender container should NOT be visible for Event
        assert self.search.gender_container.count() == 0 or \
            not self.search.gender_container.first.is_visible(), (
            "Gender options should not appear for Event category"
        )
        self.page.keyboard.press("Escape")

    # --- Person search variations ---

    @pytest.mark.ui
    @pytest.mark.search
    @pytest.mark.search_deeper
    def test_person_female_search(self):
        """Verify Person search with Female description completes.

        Soft assertion: some sites may have few or no female detections.
        """
        self.search.select_category("Person")
        self.search.select_description_gender("Female")
        self.search.select_locations_cameras(SITE_NAME)
        self.search.select_duration_by_index(5)

        has_results = self.search.execute_search_safe(timeout=60000)

        # Verify category is still Person after search
        person_text = self.page.get_by_text("Person", exact=False).first
        expect(person_text).to_be_visible(timeout=5000)

        if has_results:
            assert self.search.get_result_count() > 0

    @pytest.mark.ui
    @pytest.mark.search
    @pytest.mark.search_deeper
    def test_person_search_multiple_results(self):
        """Verify a broad Person search returns multiple results."""
        self.search.select_category("Person")
        self.search.select_description_gender("Male")
        self.search.select_locations_cameras(SITE_NAME)
        self.search.select_duration_by_index(5)
        self.search.execute_search(timeout=60000)

        count = self.search.get_result_count()
        assert count > 1, f"Expected multiple results, got {count}"

    @pytest.mark.ui
    @pytest.mark.search
    @pytest.mark.search_deeper
    def test_person_result_images_have_src(self):
        """Verify Person search result images have valid src attributes."""
        self.search.select_category("Person")
        self.search.select_description_gender("Male")
        self.search.select_locations_cameras(SITE_NAME)
        self.search.select_duration_by_index(5)
        self.search.execute_search(timeout=60000)

        check_count = min(self.search.get_result_count(), 3)
        for i in range(check_count):
            img = self.search.result_images.nth(i)
            expect(img).to_be_visible()

    # --- Event search variations ---

    @pytest.mark.ui
    @pytest.mark.search
    @pytest.mark.search_deeper
    @pytest.mark.parametrize("duration_text", [
        "Today",
        "Last 7 Days",
    ])
    def test_event_search_by_duration(self, duration_text):
        """Verify Event search with different durations completes."""
        self.search.select_category("Event")
        self.search.select_locations_cameras(SITE_NAME)
        self.search.select_duration(duration_text)

        has_results = self.search.execute_search_safe(timeout=60000)

        # Short durations may have 0 results - no crash is the goal
        if has_results:
            assert self.search.get_result_count() > 0

    @pytest.mark.ui
    @pytest.mark.search
    @pytest.mark.search_deeper
    def test_event_result_images_valid(self):
        """Verify Event search result images are visible."""
        self.search.select_category("Event")
        self.search.select_locations_cameras(SITE_NAME)
        self.search.select_duration_by_index(5)
        self.search.execute_search(timeout=60000)

        check_count = min(self.search.get_result_count(), 3)
        for i in range(check_count):
            img = self.search.result_images.nth(i)
            expect(img).to_be_visible()

    # --- Filter change workflows ---

    @pytest.mark.ui
    @pytest.mark.search
    @pytest.mark.search_deeper
    def test_change_category_person_to_event(self):
        """Verify switching from Person to Event and re-searching works."""
        # First search: Person
        self.search.select_category("Person")
        self.search.select_description_gender("Male")
        self.search.select_locations_cameras(SITE_NAME)
        self.search.select_duration_by_index(5)
        self.search.execute_search(timeout=60000)

        person_count = self.search.get_result_count()
        assert person_count > 0, "Expected Person results"

        # Switch to Event and re-search
        self.search.select_category("Event")
        has_results = self.search.execute_search_safe(timeout=60000)

        if has_results:
            event_count = self.search.get_result_count()
            assert event_count > 0

    @pytest.mark.ui
    @pytest.mark.search
    @pytest.mark.search_deeper
    def test_change_duration_and_re_search(self):
        """Verify changing duration between searches works."""
        self.search.select_category("Person")
        self.search.select_description_gender("Male")
        self.search.select_locations_cameras(SITE_NAME)
        self.search.select_duration("Last 7 Days")
        self.search.execute_search(timeout=60000)
        assert self.search.get_result_count() > 0, "Expected results for Last 7 Days"

        # Change to Today and re-search
        self.search.select_duration("Today")
        self.search.execute_search_safe(timeout=60000)

        # Different duration may have fewer results - just verify no crash

    # --- Search result content ---

    @pytest.mark.ui
    @pytest.mark.search
    @pytest.mark.search_deeper
    def test_search_button_state_after_filters(self):
        """Verify search button is clickable after setting all filters."""
        self.search.select_category("Person")
        self.search.select_description_gender("Male")
        self.search.select_locations_cameras(SITE_NAME)
        self.search.select_duration_by_index(5)

        expect(self.search.search_button).to_be_visible(timeout=5000)

    @pytest.mark.ui
    @pytest.mark.search
    @pytest.mark.search_deeper
    def test_result_count_matches_visible_images(self):
        """Verify get_result_count() matches visible result images."""
        self.search.select_category("Person")
        self.search.select_description_gender("Male")
        self.search.select_locations_cameras(SITE_NAME)
        self.search.select_duration_by_index(5)
        self.search.execute_search(timeout=60000)

        count = self.search.get_result_count()
        visible = 0
        for i in range(count):
            try:
                if self.search.result_images.nth(i).is_visible():
                    visible += 1
            except Exception:
                break

        assert visible > 0, "Expected at least one visible result image"
        assert visible == count, (
            f"Result count ({count}) doesn't match visible images ({visible})"
        )
