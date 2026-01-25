"""Basic Views tests - thumbnail display, tabs, tile layout."""
import pytest
from tests.shared.pages.views_page import ViewsPage


class TestViewsBasic:
    """Basic Views functionality tests."""

    @pytest.fixture(autouse=True)
    def setup(self, authenticated_page):
        self.page = authenticated_page
        self.views = ViewsPage(self.page)

    def test_camera_thumbnails_visible(self):
        self.views.expand_site_and_show_cameras()
        self.page.wait_for_timeout(3000)
        count = self.views.get_thumbnail_count()
        assert count > 0, "No camera thumbnails visible"

    def test_add_new_tab(self):
        """Verify adding a new tab creates 4 additional empty tiles."""
        initial_tiles = self.views.get_empty_tile_count()
        self.views.add_new_tab()
        self.page.wait_for_timeout(1000)
        new_total_tiles = self.views.get_empty_tile_count()
        tiles_added = new_total_tiles - initial_tiles
        assert tiles_added == 4, (
            f"Expected 4 new tiles, got {tiles_added} (was {initial_tiles}, now {new_total_tiles})"
        )

    def test_add_multiple_tabs(self):
        initial_count = self.views.get_tab_count()
        self.views.add_new_tab()
        self.page.wait_for_timeout(1000)
        self.views.add_new_tab()
        self.page.wait_for_timeout(1000)
        final_count = self.views.get_tab_count()
        assert final_count == initial_count + 2

    def test_tab_naming_sequence(self):
        self.views.add_new_tab()
        self.page.wait_for_timeout(1000)
        tab_names = self.views.get_tab_names()
        assert len(tab_names) >= 2, "Expected at least 2 tabs"

    def test_tab_naming_after_delete(self):
        self.views.add_new_tab()
        self.page.wait_for_timeout(1000)
        self.page.wait_for_timeout(500)
        self.views.add_new_tab()
        self.page.wait_for_timeout(1000)
        self.page.wait_for_timeout(500)
        # close the tab that contains the input with value 'View 2'
        tab = self.page.locator("button.tabItem:has(input[value='View 2'])")
        tab.hover()
        self.page.wait_for_timeout(300)
        tab.locator("img[src*='closeIcon']").click()
        self.page.wait_for_timeout(1000)
        self.views.add_new_tab()
        self.page.wait_for_timeout(1000)
        self.page.wait_for_timeout(500)
        latest_tab = self.views.get_latest_tab_name()
        assert latest_tab != "View 2", f"Tab name reused: {latest_tab}"

    def test_cannot_delete_last_tab(self):
        while self.views.get_tab_count() > 1:
            self.views.close_tab(1)
            self.page.wait_for_timeout(500)
        # Last-tab deletion triggers a browser alert; register handler
        self.views.handle_alert_dialog()
        self.views.close_tab(0)
        self.page.wait_for_timeout(1000)
        # Alert should have prevented deletion, tab count remains 1
        assert self.views.get_tab_count() == 1

    def test_close_tab(self):
        self.views.add_new_tab()
        self.page.wait_for_timeout(2000)
        tabs_before = self.views.get_tab_count()
        self.views.close_tab(1)
        self.page.wait_for_timeout(2000)
        tabs_after = self.views.get_tab_count()
        assert tabs_after == tabs_before - 1

    def test_rename_tab(self):
        """Verify a tab can be renamed."""
        # Add a new tab first
        self.views.add_new_tab()
        self.page.wait_for_timeout(1000)

        # Get the tab's edit button (second tab = index 1)
        edit_button = self.page.locator("img[src*='editIcon']").nth(1)
        edit_button.click()
        self.page.wait_for_timeout(300)

        # The input should now be enabled - clear and type new name
        tab_input = self.page.locator("input.tabTitle").nth(1)
        tab_input.fill("My Custom View")

        # Press Enter to confirm
        tab_input.press("Enter")
        self.page.wait_for_timeout(500)

        # Verify the tab was renamed
        tab_value = tab_input.get_attribute("value")
        assert tab_value == "My Custom View", f"Expected 'My Custom View', got '{tab_value}'"

    def test_rename_does_not_affect_sequence(self):
        """Verify renaming a tab doesn't break the sequential naming for new tabs."""
        # Hover over the first tab to reveal edit button
        first_tab = self.page.locator("button.tabItem").first
        first_tab.hover()
        self.page.wait_for_timeout(300)

        # Click the edit button
        edit_button = first_tab.locator("img[src*='editIcon']")
        edit_button.click()
        self.page.wait_for_timeout(300)

        # Clear and type new name
        tab_input = self.page.locator("input.tabTitle").first
        tab_input.fill("Custom Name")
        tab_input.press("Enter")
        self.page.wait_for_timeout(500)

        # Add a new tab
        self.views.add_new_tab()
        self.page.wait_for_timeout(1000)

        # Verify new tab is named "View 2"
        new_tab_input = self.page.locator("input.tabTitle").nth(1)
        new_tab_value = new_tab_input.get_attribute("value")
        assert new_tab_value == "View 2", f"Expected 'View 2', got '{new_tab_value}'"
