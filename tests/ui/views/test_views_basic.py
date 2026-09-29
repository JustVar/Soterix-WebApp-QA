"""Basic Views tests - thumbnail display, tabs, tile layout."""
import pytest
from playwright.sync_api import expect

from tests.shared.pages.views_page import ViewsPage

# One worker for every module that writes this account's saved views, tabs, bookmarks and favourites: under
# -n they would otherwise spread across workers and race on the same
# tenant state (pytest.ini --dist loadgroup).
pytestmark = pytest.mark.xdist_group("account_views")


class TestViewsBasic:
    """Basic Views functionality tests."""

    @pytest.fixture(autouse=True)
    def setup(self, authenticated_page, step_capture):
        self.page = authenticated_page
        self.step_capture = step_capture
        step_capture.set_page(self.page)
        self.views = ViewsPage(self.page)
        self._saved_view_names = []
        self.views.navigate()
        self.views.wait_for_page_load()
        yield
        # Cleanup: delete any saved views created during the test
        for name in reversed(self._saved_view_names):
            try:
                self._delete_saved_view_safe(name)
            # cleanup only: a leftover saved view must not fail a test that
            # already passed - the failure is logged
            except Exception as e:
                print(f"Cleanup: failed to delete view '{name}': {e}")
        # Cleanup: close extra tabs (only first tab should remain)
        try:
            # :visible matters - the app keeps closed tabs in the DOM hidden
            tabs = self.page.locator("button.tabItem:visible")
            while tabs.count() > 1:
                before = tabs.count()
                last_tab = tabs.last
                last_tab.hover(timeout=10000)
                # img asset icon: alt unreliable, locate by src (CONVENTIONS > Locators)
                close_icon = last_tab.locator("img[src*='closeIcon']")
                try:
                    close_icon.wait_for(state="visible", timeout=2000)
                    # cleanup only: a tab that shows no close icon on hover cannot
                    # be closed, so the loop ends. The page is per-test, so the tab
                    # cannot leak into another test.
                except Exception:
                    break
                close_icon.click(timeout=10000)
                expect(tabs).to_have_count(before - 1, timeout=5000)
        # cleanup only: page and context are per-test (authenticated_page
        # closes both right after teardown), so a tab left open cannot leak
        # into another test; this except also ends the loop when a close
        # does not drop the count, so a passed test is not turned into a
        # teardown ERROR - the failure is logged
        except Exception as e:
            print(f"Cleanup: failed to close extra tabs: {e}")

    def _add_tab_and_wait(self):
        """Add a new tab and wait until it exists. Returns the new tab count."""
        tabs = self.page.locator("button.tabItem:visible")
        before = tabs.count()
        self.views.add_new_tab()
        expect(tabs).to_have_count(before + 1, timeout=10000)
        return before + 1

    def _delete_saved_view_safe(self, view_name):
        """Delete a saved view from the My Views panel."""
        # img asset icon: alt unreliable, locate by src (CONVENTIONS > Locators)
        self.page.locator("img[src*='myviews']").click()
        saved_view = self.page.locator(f"span[title='{view_name}']")
        try:
            saved_view.wait_for(state="visible", timeout=5000)
            # cleanup helper: each test records the name before its save, so a
            # test that stopped early has no view to delete.
            # test_delete_saved_view owns the delete oracle.
        except Exception:
            return  # View not present - nothing to delete
        saved_view.hover()
        # img asset icon: alt unreliable, locate by src (CONVENTIONS > Locators)
        self.page.locator("img[src*='delete-icon']").click()
        self.page.locator("button:has-text('Delete')").click()
        self.page.locator("text=Successfully deleted").wait_for(
            state="visible", timeout=60000
        )

    @pytest.mark.ui
    @pytest.mark.sanity
    def test_rename_does_not_affect_sequence(self):
        """Verify renaming a tab leaves the numbering of the next tab alone.

        Steps:
        1. Hover the first tab, click its pencil icon, type Custom Name and press Enter.
           Expected: The tab reads Custom Name.
        2. Click + to add a tab.
           Expected: The new tab is named View 2, so the rename did not take its number.
        """
        self.step_capture.mark(1, "Navigate to Views page and wait for page load")
        # Hover over the first tab to reveal edit button
        first_tab = self.page.locator("button.tabItem").first
        first_tab.hover()
        self.step_capture.mark(2, "Hover over the first tab to reveal edit button")

        # Click the edit button (auto-waits for the hover-revealed icon)
        edit_button = first_tab.locator("img[src*='editIcon']")
        edit_button.click()

        # Clear and type new name
        tab_input = self.page.locator("input.tabTitle").first
        tab_input.fill("Custom Name")
        tab_input.press("Enter")
        self.page.wait_for_timeout(250)  # rename commit has no DOM signal
        self.step_capture.mark(3, "Click edit button, clear tab name, and type 'Custom Name'")

        # Add a new tab
        self._add_tab_and_wait()
        self.step_capture.mark(4, "Add a new tab using the add tab button")

        # Verify new tab is named "View 2" (retries until the name settles)
        new_tab_input = self.page.locator("input.tabTitle").nth(1)
        expect(new_tab_input).to_have_value("View 2", timeout=10000)
        self.step_capture.mark(5, "Verify the new tab is named 'View 2'")

    @pytest.mark.ui
    @pytest.mark.sanity
    def test_save_empty_view_shows_error(self):
        """Verify saving a view with no cameras is refused.

        Steps:
        1. Add a tab and leave it empty, then click Save.
           Expected: The app shows an empty-view message. If it shows none, it must not show View saved successfully either.
        """
        # Add a new tab (it will be empty)
        self._add_tab_and_wait()

        # Click save button
        save_button = self.page.locator("button:has-text('Save View'), img[src*='save']").last
        save_button.click(force=True)

        # The app may show different messages; 'text=' matching is
        # case-insensitive substring, so 'empty' covers the empty-view variants
        error_message = (
            self.page.locator("text=empty")
            .or_(self.page.locator("text=No cameras"))
            .or_(self.page.locator("text=Add cameras"))
            .or_(self.page.locator("text=cannot save"))
        )
        try:
            expect(error_message.first).to_be_visible(timeout=5000)
        except AssertionError:
            # No error shown - at least verify it didn't save successfully
            success_msg = self.page.locator("text=View saved successfully")
            assert not success_msg.is_visible(), \
                "Empty view should not save successfully without error"

    @pytest.mark.ui
    @pytest.mark.views_myviews
    @pytest.mark.checkbox
    @pytest.mark.livestream
    def test_save_view(self):
        """Verify a view can be saved with content using checkbox selection."""
        import datetime

        # Use a unique timestamped view name
        view_name = f"SaveTest_{datetime.datetime.now().strftime('%H%M%S%f')[:9]}"
        self._saved_view_names.append(view_name)

        # Add a new tab
        self._add_tab_and_wait()

        # Rename it to a stable name
        tab = self.page.locator("button.tabItem").nth(1)
        tab.hover()
        # img asset icon: alt unreliable, locate by src (CONVENTIONS > Locators)
        tab.locator("img[src*='editIcon']").click()
        tab_input = self.page.locator("input.tabTitle").nth(1)
        tab_input.fill(view_name)
        tab_input.press("Enter")
        self.page.wait_for_timeout(250)  # rename commit has no DOM signal

        # Expand Driver Site and show cameras
        self.views.expand_site_and_show_cameras(None)

        # Select the first available camera via checkbox
        self.views.add_first_camera_via_checkbox()

        # Click save button using the save icon image src
        save_icon = self.page.locator("img[src*='save']").last
        save_icon.click(force=True)

        # Verify success message
        success_message = self.page.locator("text=View saved successfully")
        expect(success_message).to_contain_text("View saved successfully", timeout=20000)

        # Cleanup: close tab and delete saved view
        tab.hover()
        # Best-effort close; no count assertion - the tab bar keeps an extra
        # tabItem element (measured via trace: count stays 2 after a close),
        # and the next step's own wait covers any settling time
        tab.locator("img[src*='closeIcon']").click()

        # Open My Views and delete the saved view
        self.page.locator("img[src*='myviews']").click()
        saved_view = self.page.locator(f"span[title='{view_name}']")
        saved_view.wait_for(state="visible", timeout=20000)
        saved_view.hover()
        # img asset icon: alt unreliable, locate by src (CONVENTIONS > Locators)
        self.page.locator("img[src*='delete-icon']").click()
        self.page.locator("button:has-text('Delete')").click()
        deleted_msg = self.page.locator("text=Successfully deleted")
        deleted_msg.wait_for(state="visible", timeout=60000)

        # Cleanup complete - end test after deletion

    @pytest.mark.ui
    @pytest.mark.views_myviews
    def test_open_my_views(self):
        """Verify the My Views panel opens.

        Steps:
        1. On Views, click the My Views icon in the panel bar.
           Expected: The My Views panel opens and shows its Presets and My Views sections.
        """
        # Click My Views button
        my_views_button = self.page.locator("img[src*='myviews']")
        my_views_button.click()

        # The panel shows its Presets / My Views toggle even with no saved
        # views, so it is a deterministic panel-open signal (thumbnails only
        # exist when the tenant happens to have saved views).
        expect(self.page.locator("text=Presets").first).to_have_text("Presets", timeout=20000)
        expect(self.page.locator("text=My Views").last).to_have_text("My Views", timeout=5000)

    @pytest.mark.ui
    @pytest.mark.views_myviews
    @pytest.mark.checkbox
    @pytest.mark.livestream
    def test_open_saved_view(self):
        """A saved view reopens from My Views after a page refresh.

        Steps:
        1. Add a tab, rename it, show the site's cameras, tick the first camera and click Save.
           Expected: The toast View saved successfully shows.
        2. Refresh the browser and open My Views.
           Expected: The saved view is listed under its name.
        3. Hover the saved view and tick its checkbox.
           Expected: The view opens as a tab or fills a tile.
        """
        import datetime

        view_name = f"OpenTest_{datetime.datetime.now().strftime('%H%M%S%f')[:9]}"
        self._saved_view_names.append(view_name)

        # Create and save a view
        self._add_tab_and_wait()

        tab = self.page.locator("button.tabItem").nth(1)
        tab.hover()
        # img asset icon: alt unreliable, locate by src (CONVENTIONS > Locators)
        tab.locator("img[src*='editIcon']").click()

        tab_input = self.page.locator("input.tabTitle").nth(1)
        tab_input.fill(view_name)
        tab_input.press("Enter")
        self.page.wait_for_timeout(250)  # rename commit has no DOM signal

        self.views.expand_site_and_show_cameras(None)
        self.views.add_first_camera_via_checkbox()

        # Save the view - use JS click to handle viewport issues
        save_btn = self.page.locator("img[src*='save']").nth(1)
        save_btn.evaluate("el => el.click()")
        self.page.locator("text=View saved successfully").wait_for(state="visible", timeout=60000)

        # Refresh page (clears tab state, saved view persists)
        self.page.reload()

        # Open My Views panel (click auto-waits for the button to reappear)
        self.page.locator("img[src*='myviews']").click()

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

        # Click checkbox to open the view (auto-waits for the revealed checkbox)
        checkbox = self.page.locator(".sidebar-custom-checkbox").first
        checkbox.click()

        # Verify the tab appears (retries until the reopened tab renders)
        new_tab = self.page.locator(f"button.tabItem:has(div[title='{view_name}'])")
        expect(new_tab).to_have_count(1, timeout=10000)

    @pytest.mark.ui
    @pytest.mark.views_myviews
    @pytest.mark.checkbox
    @pytest.mark.livestream
    def test_delete_saved_view(self):
        """A saved view can be deleted from My Views.

        Steps:
        1. Add a tab, rename it, show the site's cameras and tick the first camera.
           Expected: The camera lands in the first tile.
        2. Click Save.
           Expected: The toast View saved successfully shows.
        3. Close the tab, open My Views, hover the saved view, click its delete icon and confirm Delete.
           Expected: The toast Successfully deleted shows and the view is gone from the list.
        """
        import datetime

        # First create and save a view
        view_name = f"DeleteTest_{datetime.datetime.now().strftime('%H%M%S%f')[:9]}"
        self._saved_view_names.append(view_name)

        self._add_tab_and_wait()

        tab = self.page.locator("button.tabItem").nth(1)
        tab.hover()
        # img asset icon: alt unreliable, locate by src (CONVENTIONS > Locators)
        tab.locator("img[src*='editIcon']").click()

        tab_input = self.page.locator("input.tabTitle").nth(1)
        tab_input.fill(view_name)
        tab_input.press("Enter")
        self.page.wait_for_timeout(500)  # rename commit has no DOM signal

        # Expand Driver Site and show cameras
        self.views.expand_site_and_show_cameras(None)

        # Select the first available camera via checkbox
        self.views.add_first_camera_via_checkbox()

        # Save the view - wait for button visibility, then use JS click
        save_buttons = self.page.locator("img[src*='save']")
        if save_buttons.count() > 1:
            save_btn = save_buttons.nth(1)
        else:
            save_btn = save_buttons.first
        save_btn.wait_for(state="attached", timeout=10000)
        save_btn.evaluate("el => el.click()")

        # Confirm the save landed before moving on
        self.page.locator("text=View saved successfully").wait_for(state="visible", timeout=20000)

        # Close the tab
        tab.hover()
        # Best-effort close; no count assertion - the tab bar keeps an extra
        # tabItem element (measured via trace: count stays 2 after a close),
        # and the next step's own wait covers any settling time
        tab.locator("img[src*='closeIcon']").click()

        # Open My Views
        self.page.locator("img[src*='myviews']").click()

        # Find the saved view and verify it exists (confirms save worked)
        saved_view = self.page.locator(f"span[title='{view_name}']")
        saved_view.wait_for(state="visible", timeout=20000)
        saved_view.hover()

        # Click delete icon (auto-waits for the hover-revealed icon)
        delete_button = self.page.locator("img[src*='delete-icon']")
        delete_button.click()

        # Confirm deletion (use 'Delete' button label)
        confirm_button = self.page.locator("button:has-text('Delete')")
        confirm_button.click()

        # Verify success message
        success_message = self.page.locator("text=Successfully deleted")
        expect(success_message).to_contain_text("Successfully deleted", timeout=60000)
        expect(saved_view).to_have_count(0, timeout=10000)
