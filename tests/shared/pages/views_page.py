"""Views Page Object Model for video wall and camera views."""
from playwright.sync_api import Page, expect


class ViewsPage:
    """Page object for Views functionality (video wall, thumbnails, tabs)."""
    
    def __init__(self, page: Page):
        self.page = page
        
        # Locators - Thumbnails
        self.camera_thumbnails = page.locator(".cameraThumbnailWrapper")
        self.drag_drop_tiles = page.locator("text=Drag & Drop Camera here")
        
        # Locators - Tabs
        self.add_tab_button = page.locator("img[src*='media/addIcon']")
        self.tab_titles = page.locator(".tabTitle")
        self.tab_close_buttons = page.locator("img[src*='closeIcon']")
        self.tab_edit_buttons = page.locator("img[src*='media/editIcon']")
        
        # Locators - Views
        self.my_views_button = page.locator("img[src*='media/myviews']")
        self.maps_button = page.locator("img[src*='media/maps']")
        self.save_view_button = page.locator("img[src*='media/saveIcon']")

        # Locators - Left Panel Navigation
        self.devices_tab = page.locator("text=Devices")
        self.my_views_tab = page.locator("text=My Views")
        self.insights_tab = page.locator("text=Insights")
        self.maps_tab = page.locator("text=Maps")
        self.channels_tab = page.locator("text=Channels")
        
        # Locators - Site/Camera Tree
        self.search_camera_input = page.locator("input[placeholder*='Search Camera']")

        # Locators - Tab Names
        self.tab_headers = page.locator("[class*='tabTitle'], [class*='tab-title']")
        self.action_not_permitted_modal = page.locator("text=Action Not Permitted")
        self.modal_ok_button = page.locator("button:has-text('OK'), button:has-text('Ok')")
        
        # Locators - Loading/Status
        self.loader = page.locator("[class*='CircularProgress']")
        self.streaming_failed = page.locator("text=failed to load")
        
        # Locators - Delete confirmation
        self.delete_button = page.locator("img[src*='delete-icon']")
        self.confirm_yes_button = page.locator("button:has-text('Yes')")
        self.success_message = page.locator("text=Successfully deleted")

    def get_thumbnail_count(self) -> int:
        """Return the number of camera thumbnails visible."""
        return self.camera_thumbnails.count()

    def get_empty_tile_count(self) -> int:
        """Return the number of empty drag/drop tiles."""
        return self.drag_drop_tiles.count()

    def add_new_tab(self):
        """Click the add tab button."""
        self.add_tab_button.click()

    def wait_for_loader_to_finish(self, timeout: int = 60000):
        """Wait for the circular progress loader to disappear."""
        self.loader.wait_for(state="hidden", timeout=timeout)

    def rename_tab(self, tab_index: int, new_name: str):
        """Rename a tab by index (0-based)."""
        # Hover over edit button and click
        edit_button = self.tab_edit_buttons.nth(tab_index)
        edit_button.hover()
        edit_button.click()
        
        # Clear existing text and type new name
        tab_title = self.tab_titles.nth(tab_index)
        tab_title.fill(new_name)

    def close_tab(self, tab_index: int):
        """Close a tab by index (0-based)."""
        # Use direct locator at time of action to avoid stale references
        close_buttons = self.page.locator("img[src*='closeIcon']")
        close_buttons.nth(tab_index).click()

    def handle_alert_dialog(self):
        """Set up a handler to automatically accept browser alert dialogs."""
        def _accept(dialog):
            try:
                dialog.accept()
            except Exception:
                pass

        # Register the dialog handler
        self.page.on("dialog", _accept)

    def drag_camera_to_tile(self, camera_locator, tile_index: int = 0):
        """Drag a camera thumbnail to a specific tile."""
        target_tile = self.drag_drop_tiles.nth(tile_index)
        camera_locator.drag_to(target_tile)

    def open_my_views(self):
        """Click the My Views button to open saved views panel."""
        self.my_views_button.click()

    def open_maps(self):
        """Click the Maps button to open maps panel."""
        self.maps_button.click()

    def save_current_view(self):
        """Click the save view button."""
        self.save_view_button.click()

    def delete_view(self, view_name: str):
        """Delete a saved view by name."""
        view_element = self.page.locator(f"span[title='{view_name}']")
        view_element.hover()
        self.delete_button.click()
        self.confirm_yes_button.click()
        
        # Wait for success message
        self.success_message.wait_for(state="visible", timeout=60000)

    def drag_view_to_tile(self, view_name: str, tile_index: int = 0):
        """Drag a saved view to a tile."""
        view_element = self.page.locator(f"span[title='{view_name}']")
        target_tile = self.drag_drop_tiles.nth(tile_index)
        view_element.drag_to(target_tile)

    def is_streaming_working(self, expected_failures: int = 0) -> bool:
        """Check if streaming is working (failures <= expected offline cameras)."""
        failure_count = self.streaming_failed.count()
        return failure_count <= expected_failures

    def get_tab_count(self) -> int:
        """Return the number of tabs currently open."""
        return self.tab_close_buttons.count()

    def get_tab_names(self) -> list:
        """Return list of all tab names."""
        count = self.tab_headers.count()
        names = []
        for i in range(count):
            names.append(self.tab_headers.nth(i).inner_text())
        return names

    def get_latest_tab_name(self) -> str:
        """Return the name of the most recently added tab (last tab)."""
        count = self.tab_headers.count()
        if count > 0:
            return self.tab_headers.nth(count - 1).inner_text()
        return ""

    def is_action_not_permitted_shown(self) -> bool:
        """Check if 'Action Not Permitted' modal is visible."""
        return self.action_not_permitted_modal.is_visible()

    def close_modal(self):
        """Close any open modal by clicking OK."""
        if self.modal_ok_button.is_visible():
            self.modal_ok_button.click()

    def click_site(self, site_name: str):
        """Click on a site in the left panel to expand it.

        Args:
            site_name: Specific site name, or None to click the first site.
        """
        if site_name:
            site = self.page.locator(f"text={site_name}").first
        else:
            # Click the first site - look for element with camera count badge (icon + number)
            # Sites show as: [icon] Site Name [camera icon] [count]
            site = self.page.locator(r"text=/.*Site.*\d+/" ).first
            if site.count() == 0:
                # Fallback: any clickable element containing "Site"
                site = self.page.locator("text=Site").first
        site.click()

    def click_all_cameras(self):
        """Click on 'All Cameras' to show all camera thumbnails."""
        all_cameras = self.page.locator("text=All Cameras").first
        all_cameras.click()

    def expand_site_and_show_cameras(self, site_name: str = None):
        """Expand a site and click All Cameras to show thumbnails."""
        self.click_site(site_name)
        self.page.wait_for_timeout(1000)
        self.click_all_cameras()
        self.page.wait_for_timeout(2000)
