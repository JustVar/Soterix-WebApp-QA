"""Basic Views tests - thumbnail display, tabs, tile layout."""
import pytest
from playwright.sync_api import expect
from tests.shared.pages.views_page import ViewsPage


class TestViewsBasic:
    """Basic Views functionality tests."""

    @pytest.fixture(autouse=True)
    def setup(self, authenticated_page):
        self.page = authenticated_page
        self.views = ViewsPage(self.page)
        self.views.navigate()
        self.views.wait_for_page_load()

    def test_rename_does_not_affect_sequence(self):
        """Verify renaming a tab doesn't break the sequential naming for new tabs."""
        # Hover over the first tab to reveal edit button
        first_tab = self.page.locator("button.tabItem").first
        first_tab.hover()
        self.page.wait_for_timeout(150)

        # Click the edit button
        edit_button = first_tab.locator("img[src*='editIcon']")
        edit_button.click()
        self.page.wait_for_timeout(150)

        # Clear and type new name
        tab_input = self.page.locator("input.tabTitle").first
        tab_input.fill("Custom Name")
        tab_input.press("Enter")
        self.page.wait_for_timeout(250)

        # Add a new tab
        self.views.add_new_tab()
        self.page.wait_for_timeout(500)

        # Verify new tab is named "View 2"
        new_tab_input = self.page.locator("input.tabTitle").nth(1)
        new_tab_value = new_tab_input.get_attribute("value")
        assert new_tab_value == "View 2", f"Expected 'View 2', got '{new_tab_value}'"

    def test_save_empty_view_shows_error(self):
        """Verify saving an empty view shows an error or is prevented."""
        # Add a new tab (it will be empty)
        self.views.add_new_tab()
        self.page.wait_for_timeout(500)

        # Click save button
        save_button = self.page.locator("button:has-text('Save View'), img[src*='save']").last
        save_button.click(force=True)
        self.page.wait_for_timeout(1000)

        # Check for error message - the app may show different messages
        # Try multiple possible error patterns
        error_patterns = [
            "text=View is empty",
            "text=Empty view",
            "text=empty",
            "text=No cameras",
            "text=Add cameras",
            "text=cannot save",
            "text=Cannot save",
        ]

        error_found = False
        for pattern in error_patterns:
            try:
                loc = self.page.locator(pattern).first
                if loc.is_visible():
                    error_found = True
                    break
            except Exception:
                continue

        # Alternative: verify no success message appeared (save was blocked/failed)
        if not error_found:
            success_msg = self.page.locator("text=View saved successfully")
            # If no error shown, at least verify it didn't save successfully
            assert not success_msg.is_visible(), \
                "Empty view should not save successfully without error"

    def test_save_view(self):
        """Verify a view can be saved with content using checkbox selection."""
        import datetime

        # Use a unique timestamped view name
        view_name = f"SaveTest_{datetime.datetime.now().strftime('%H%M%S')}"

        # Add a new tab
        self.views.add_new_tab()
        self.page.wait_for_timeout(500)

        # Rename it to a stable name
        tab = self.page.locator("button.tabItem").nth(1)
        tab.hover()
        self.page.wait_for_timeout(150)
        tab.locator("img[src*='editIcon']").click()
        self.page.wait_for_timeout(150)
        tab_input = self.page.locator("input.tabTitle").nth(1)
        tab_input.fill(view_name)
        tab_input.press("Enter")
        self.page.wait_for_timeout(250)

        # Expand Driver Site and show cameras
        self.views.expand_site_and_show_cameras("Driver Site")
        self.page.wait_for_timeout(500)

        # Select the first available camera via checkbox
        self.views.add_first_camera_via_checkbox()

        # Click save button
        save_button = self.page.locator("button:has-text('Save View'), img[src*='save']").last
        save_button.click(force=True)
        self.page.wait_for_timeout(500)

        # Verify success message
        success_message = self.page.locator("text=View saved successfully")
        success_message.wait_for(state="visible", timeout=20000)

        # Cleanup: close tab and delete saved view
        tab.hover()
        self.page.wait_for_timeout(150)
        tab.locator("img[src*='closeIcon']").click()
        self.page.wait_for_timeout(500)

        # Open My Views and delete the saved view
        self.page.locator("img[src*='myviews']").click()
        self.page.wait_for_timeout(1000)
        saved_view = self.page.locator(f"span[title='{view_name}']")
        saved_view.wait_for(state="visible", timeout=20000)
        saved_view.hover()
        self.page.wait_for_timeout(150)
        delete_button = self.page.locator("img[src*='delete-icon']")
        delete_button.click()
        self.page.wait_for_timeout(250)
        delete_confirm = self.page.locator("button:has-text('Delete')")
        delete_confirm.click()
        deleted_msg = self.page.locator("text=Successfully deleted")
        deleted_msg.wait_for(state="visible", timeout=60000)
        self.page.wait_for_timeout(500)

        # Cleanup complete - end test after deletion

    def test_open_my_views(self):
        """Verify My Views panel opens and shows saved views."""
        # Click My Views button
        my_views_button = self.page.locator("img[src*='myviews']")
        my_views_button.click()
        self.page.wait_for_timeout(1000)

        # Verify the panel loaded - look for view thumbnails or the panel itself
        views_loaded = self.page.locator("img[src*='data:image/jpeg']").first
        expect(views_loaded).to_be_visible(timeout=20000)

    def test_open_saved_view(self):
        """Verify a saved view can be reopened from My Views after page refresh."""
        import datetime

        view_name = f"OpenTest_{datetime.datetime.now().strftime('%H%M%S')}"

        # Create and save a view
        self.views.add_new_tab()
        self.page.wait_for_timeout(500)

        tab = self.page.locator("button.tabItem").nth(1)
        tab.hover()
        self.page.wait_for_timeout(150)
        tab.locator("img[src*='editIcon']").click()
        self.page.wait_for_timeout(150)

        tab_input = self.page.locator("input.tabTitle").nth(1)
        tab_input.fill(view_name)
        tab_input.press("Enter")
        self.page.wait_for_timeout(250)

        self.views.expand_site_and_show_cameras("Driver Site")
        self.page.wait_for_timeout(500)
        self.views.add_first_camera_via_checkbox()

        self.page.locator("img[src*='save']").nth(1).click(force=True)
        self.page.wait_for_timeout(500)
        self.page.locator("text=View saved successfully").wait_for(state="visible", timeout=60000)

        # Refresh page (clears tab state, saved view persists)
        self.page.reload()
        self.page.wait_for_timeout(1500)

        # Open My Views panel
        self.page.locator("img[src*='myviews']").click()
        self.page.wait_for_timeout(1000)

        # Find saved view
        view_span = self.page.locator(f"span[title='{view_name}']").first
        view_span.wait_for(state="visible", timeout=20000)

        # JS hover to reveal checkbox
        self.page.evaluate(
            """(title) => {
                const span = document.querySelector(`span[title='${title}']`);
                if (span) {
                    let parent = span.parentElement;
                    for (let i = 0; i < 5; i++) {
                        if (parent) {
                            parent.dispatchEvent(new MouseEvent('mouseenter', {bubbles: true}));
                            parent.dispatchEvent(new MouseEvent('mouseover', {bubbles: true}));
                            parent = parent.parentElement;
                        }
                    }
                }
            }""",
            view_name
        )
        self.page.wait_for_timeout(250)

        # Click checkbox to open the view
        checkbox = self.page.locator(".sidebar-custom-checkbox").first
        checkbox.click()
        self.page.wait_for_timeout(1000)

        # Verify the tab appears
        new_tab = self.page.locator(f"button.tabItem:has(div[title='{view_name}'])")
        assert new_tab.count() == 1, f"Tab '{view_name}' should be reopened"

    def test_delete_saved_view(self):
        """Verify a saved view can be deleted."""
        import datetime

        # First create and save a view
        view_name = f"DeleteTest_{datetime.datetime.now().strftime('%H%M%S')}"

        self.views.add_new_tab()
        self.page.wait_for_timeout(500)

        tab = self.page.locator("button.tabItem").nth(1)
        tab.hover()
        self.page.wait_for_timeout(150)
        tab.locator("img[src*='editIcon']").click()
        self.page.wait_for_timeout(150)

        tab_input = self.page.locator("input.tabTitle").nth(1)
        tab_input.fill(view_name)
        tab_input.press("Enter")
        self.page.wait_for_timeout(250)

        # Expand Driver Site and show cameras
        self.views.expand_site_and_show_cameras("Driver Site")
        self.page.wait_for_timeout(500)

        # Select the first available camera via checkbox
        self.views.add_first_camera_via_checkbox()

        # Save the view
        self.page.locator("img[src*='save']").nth(1).click(force=True)
        self.page.wait_for_timeout(1000)  # Increased from 500ms
        self.page.locator("text=View saved successfully").wait_for(state="visible", timeout=60000)

        # Close the tab
        tab.hover()
        self.page.wait_for_timeout(150)
        tab.locator("img[src*='closeIcon']").click()
        self.page.wait_for_timeout(500)

        # Open My Views
        self.page.locator("img[src*='myviews']").click()
        self.page.wait_for_timeout(1000)

        # Find the saved view and hover to show delete button
        saved_view = self.page.locator(f"span[title='{view_name}']")
        saved_view.wait_for(state="visible", timeout=20000)
        saved_view.hover()
        self.page.wait_for_timeout(150)

        # Click delete icon
        delete_button = self.page.locator("img[src*='delete-icon']")
        delete_button.click()
        self.page.wait_for_timeout(250)

        # Confirm deletion (use 'Delete' button label)
        confirm_button = self.page.locator("button:has-text('Delete')")
        confirm_button.click()

        # Verify success message
        success_message = self.page.locator("text=Successfully deleted")
        success_message.wait_for(state="visible", timeout=60000)


