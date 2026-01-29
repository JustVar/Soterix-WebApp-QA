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
        
        # Locators - Views subtab buttons (inside .viewTabs container, NOT left nav)
        # Structure: div.viewTabs > div.viewTabItem > img[alt="TabName"] + "TabName"
        self.view_tabs_container = page.locator(".viewTabs")
        self.devices_subtab = self.view_tabs_container.locator(".viewTabItem:has(img[alt='Devices'])")
        self.my_views_button = self.view_tabs_container.locator(".viewTabItem:has(img[alt='My Views'])")
        self.insights_button = self.view_tabs_container.locator(".viewTabItem:has(img[alt='Insights'])")
        self.maps_button = self.view_tabs_container.locator(".viewTabItem:has(img[alt='Maps'])")
        self.channels_button = self.view_tabs_container.locator(".viewTabItem:has(img[alt='Channels'])")
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

    def add_camera_via_checkbox(self, camera_name: str):
        """Select a camera by revealing its checkbox and clicking it.

        Args:
            camera_name: The visible name of the camera to select.
        """
        # Find the camera thumbnail by its visible name
        camera = self.page.locator(f".cameraThumbnailWrapper:has-text('{camera_name}')").first

        # Hover to reveal the checkbox
        camera.hover()
        self.page.wait_for_timeout(150)

        # Click the checkbox inside the thumbnail
        checkbox = camera.locator(".sidebar-custom-checkbox")
        checkbox.click()

        # Wait briefly for the tile/UI to update
        self.page.wait_for_timeout(500)

    def add_first_camera_via_checkbox(self):
        """Select the first camera by revealing its checkbox and clicking it.

        This is a convenience wrapper when the specific camera name is not needed.
        """
        # Find the first camera thumbnail
        camera = self.page.locator(".cameraThumbnailWrapper").first

        # Hover to reveal the checkbox
        camera.hover()
        self.page.wait_for_timeout(150)

        # Click the checkbox inside the thumbnail
        checkbox = camera.locator(".sidebar-custom-checkbox")
        checkbox.click()

        # Wait briefly for the tile/UI to update
        self.page.wait_for_timeout(500)

    def open_my_views(self):
        """Click the My Views button to open saved views panel."""
        self.my_views_button.click()

    def open_maps(self):
        """Click the Maps button to open maps panel."""
        self.maps_button.click()

    def open_insights(self):
        """Click the Insights subtab button to open insights widget panel.

        Insights is a subtab in the top bar within Views (between My Views and Maps).
        """
        self.insights_button.click()

    def open_channels(self):
        """Click the Channels button to open channels panel."""
        self.channels_button.click()

    def open_saved_view_by_name(self, view_name: str):
        """Open a saved view from My Views panel by clicking its checkbox.

        Note: Requires JS hover workaround because Playwright's native hover
        doesn't trigger React's mouseover handlers for checkbox reveal.
        """
        # Open My Views panel if not already open
        my_views_btn = self.page.locator("img[src*='myviews']")
        my_views_btn.click()
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

    def save_current_view(self):
        """Click the save view button."""
        self.save_view_button.click()

    def navigate(self):
        """Navigate to the Views page with verification.

        Clicks the Views nav link and verifies the page loaded by checking
        for the add tab button. Retries once if initial navigation fails.
        """
        max_attempts = 2
        for attempt in range(max_attempts):
            try:
                # Wait for the Views nav item to be visible and click it
                nav = self.page.locator("text=Views").first
                nav.wait_for(state="visible", timeout=10000)

                # Wait for any loading overlays to disappear (MUI Box overlays)
                overlay = self.page.locator("div.MuiBox-root[class*='mui-1rzq1k9']")
                try:
                    overlay.wait_for(state="hidden", timeout=10000)
                except Exception:
                    pass  # Overlay may not exist

                # Also wait for circular progress loader if present
                try:
                    self.loader.wait_for(state="hidden", timeout=5000)
                except Exception:
                    pass

                # Click with force=True as fallback for any remaining overlay issues
                nav.click(force=True)
                # Wait for navigation
                self.page.wait_for_timeout(2000)

                # Verify we're on the Views page by checking for the add tab button
                self.add_tab_button.wait_for(state="visible", timeout=15000)
                return  # Success
            except Exception as e:
                if attempt < max_attempts - 1:
                    # Retry: refresh and try again
                    self.page.reload()
                    self.page.wait_for_timeout(2000)
                else:
                    raise RuntimeError(f"Failed to navigate to Views page after {max_attempts} attempts: {e}")

    def wait_for_page_load(self, timeout: int = 20000):
        """Wait for the Views page to finish loading (loader hidden).

        If loader is not found or already hidden, continues without error.
        """
        try:
            # Check if loader exists and is visible first
            if self.loader.count() > 0 and self.loader.first.is_visible():
                self.loader.wait_for(state="hidden", timeout=timeout)
        except Exception:
            # Loader may not exist or may have already hidden - that's OK
            pass

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
        view_selector = f"span[title='{view_name}']"
        try:
            # Try Playwright's high-level drag first
            view_element = self.page.locator(view_selector)
            target_tile = self.drag_drop_tiles.nth(tile_index)
            view_element.drag_to(target_tile)
            return
        except Exception:
            # Fall back to JS-driven DataTransfer-based drag/drop simulation
            self._simulate_drag_via_js(view_selector, tile_index)

    def _simulate_drag_via_js(self, view_selector: str, tile_index: int = 0):
        """Simulate HTML5 drag-and-drop using DataTransfer via page.evaluate.

        This is a fallback when Playwright's native drag doesn't trigger the
        application's drop handlers (common with React drag libraries).
        """
        script = r"""
        (viewSelector, tileIndex) => {
            const src = document.querySelector(viewSelector);
            if (!src) return {ok:false, reason: 'source-not-found'};

            // Find tiles by text content to match Playwright locator
            const allDivs = Array.from(document.querySelectorAll('div'));
            const tileCandidates = allDivs.filter(d => d.textContent && d.textContent.includes('Drag & Drop Camera here'));
            const tgt = tileCandidates[tileIndex];
            if (!tgt) return {ok:false, reason: 'target-not-found'};

            const dt = new DataTransfer();
            try { dt.setData('text/plain', viewSelector); } catch(e) {}

            function dispatch(el, name, extra={}){
                const ev = new DragEvent(name, Object.assign({bubbles:true, cancelable:true, dataTransfer: dt}, extra));
                return el.dispatchEvent(ev);
            }

            // Sequence of events: dragstart on source, dragenter/dragover on target, drop, dragend
            dispatch(src, 'dragstart');
            dispatch(tgt, 'dragenter');
            dispatch(tgt, 'dragover');
            const dropped = dispatch(tgt, 'drop');
            dispatch(src, 'dragend');

            return {ok: true, dropped: !!dropped};
        }
        """

        result = self.page.evaluate(script, view_selector, tile_index)
        return result

    def get_available_tiles(self) -> list:
        """Return list of empty 'Drag & Drop Camera here' tile locators.

        Returns:
            List of Locator objects for each available tile.
        """
        tiles = []
        count = self.drag_drop_tiles.count()
        for i in range(count):
            tiles.append(self.drag_drop_tiles.nth(i))
        return tiles

    def get_available_tile_count(self) -> int:
        """Return the number of empty 'Drag & Drop' tiles available."""
        return self.drag_drop_tiles.count()

    def drag_camera_to_tile_by_name(self, camera_name: str, tile_index: int = 0):
        """Drag a camera thumbnail to a specific tile by camera name.

        Args:
            camera_name: The visible name of the camera to drag.
            tile_index: Target tile index (0-based). Default is first tile.
        """
        # Find the camera thumbnail by name
        camera = self.page.locator(f".cameraThumbnailWrapper:has-text('{camera_name}')").first
        camera.wait_for(state="visible", timeout=10000)

        target_tile = self.drag_drop_tiles.nth(tile_index)
        target_tile.wait_for(state="visible", timeout=10000)

        try:
            # Try Playwright's high-level drag first
            camera.drag_to(target_tile)
            self.page.wait_for_timeout(1000)
        except Exception:
            # Fall back to JS-driven DataTransfer-based drag/drop simulation
            self._simulate_camera_drag_via_js(camera_name, tile_index)

    def _simulate_camera_drag_via_js(self, camera_name: str, tile_index: int = 0):
        """Simulate HTML5 drag-and-drop for camera using DataTransfer via page.evaluate.

        This is a fallback when Playwright's native drag doesn't trigger the
        application's drop handlers (common with React drag libraries).
        """
        script = r"""
        (cameraName, tileIndex) => {
            // Find camera by text content
            const thumbnails = Array.from(document.querySelectorAll('.cameraThumbnailWrapper'));
            const src = thumbnails.find(t => t.textContent && t.textContent.includes(cameraName));
            if (!src) return {ok:false, reason: 'camera-not-found'};

            // Find tiles by text content
            const allDivs = Array.from(document.querySelectorAll('div'));
            const tileCandidates = allDivs.filter(d => d.textContent && d.textContent.includes('Drag & Drop Camera here'));
            const tgt = tileCandidates[tileIndex];
            if (!tgt) return {ok:false, reason: 'target-tile-not-found'};

            const dt = new DataTransfer();
            try { dt.setData('text/plain', cameraName); } catch(e) {}

            function dispatch(el, name, extra={}){
                const ev = new DragEvent(name, Object.assign({bubbles:true, cancelable:true, dataTransfer: dt}, extra));
                return el.dispatchEvent(ev);
            }

            // Sequence: dragstart on source, dragenter/dragover on target, drop, dragend
            dispatch(src, 'dragstart');
            dispatch(tgt, 'dragenter');
            dispatch(tgt, 'dragover');
            const dropped = dispatch(tgt, 'drop');
            dispatch(src, 'dragend');

            return {ok: true, dropped: !!dropped};
        }
        """
        result = self.page.evaluate(script, camera_name, tile_index)
        self.page.wait_for_timeout(1000)
        return result

    def drag_location_to_tile(self, location_name: str, tile_index: int = 0):
        """Drag a location/site from the left panel to a tile.

        Args:
            location_name: The visible name of the location/site to drag.
            tile_index: Target tile index (0-based). Default is first tile.
        """
        # Find the location in the left panel (site tree)
        location = self.page.locator(f"text={location_name}").first
        location.wait_for(state="visible", timeout=10000)

        target_tile = self.drag_drop_tiles.nth(tile_index)
        target_tile.wait_for(state="visible", timeout=10000)

        try:
            # Try Playwright's high-level drag first
            location.drag_to(target_tile)
            self.page.wait_for_timeout(1000)
        except Exception:
            # Fall back to JS simulation
            self._simulate_location_drag_via_js(location_name, tile_index)

    def _simulate_location_drag_via_js(self, location_name: str, tile_index: int = 0):
        """Simulate drag-and-drop for location using DataTransfer via page.evaluate."""
        script = r"""
        (locationName, tileIndex) => {
            // Find location element by text
            const allElements = Array.from(document.querySelectorAll('*'));
            const src = allElements.find(el =>
                el.textContent === locationName ||
                (el.innerText && el.innerText.trim() === locationName)
            );
            if (!src) return {ok:false, reason: 'location-not-found'};

            // Find tiles
            const allDivs = Array.from(document.querySelectorAll('div'));
            const tileCandidates = allDivs.filter(d => d.textContent && d.textContent.includes('Drag & Drop Camera here'));
            const tgt = tileCandidates[tileIndex];
            if (!tgt) return {ok:false, reason: 'target-tile-not-found'};

            const dt = new DataTransfer();
            try { dt.setData('text/plain', locationName); } catch(e) {}

            function dispatch(el, name, extra={}){
                const ev = new DragEvent(name, Object.assign({bubbles:true, cancelable:true, dataTransfer: dt}, extra));
                return el.dispatchEvent(ev);
            }

            dispatch(src, 'dragstart');
            dispatch(tgt, 'dragenter');
            dispatch(tgt, 'dragover');
            const dropped = dispatch(tgt, 'drop');
            dispatch(src, 'dragend');

            return {ok: true, dropped: !!dropped};
        }
        """
        result = self.page.evaluate(script, location_name, tile_index)
        self.page.wait_for_timeout(1000)
        return result

    def drag_map_to_tile(self, map_name: str = None, tile_index: int = 0):
        """Drag a map element to a tile.

        Args:
            map_name: The name of the map to drag. If None, drags the first map.
            tile_index: Target tile index (0-based). Default is first tile.
        """
        # Open maps panel first
        self.open_maps()
        self.page.wait_for_timeout(1000)

        # Find the map element
        if map_name:
            map_element = self.page.locator(f"text={map_name}").first
        else:
            # Try to find any map thumbnail or element
            map_element = self.page.locator("[class*='map'], img[src*='map']").first

        map_element.wait_for(state="visible", timeout=10000)
        target_tile = self.drag_drop_tiles.nth(tile_index)

        try:
            map_element.drag_to(target_tile)
            self.page.wait_for_timeout(1000)
        except Exception:
            # Maps may need special handling
            pass

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
        all_cameras.wait_for(state="visible", timeout=10000)
        all_cameras.click(force=True)

    def expand_site_and_show_cameras(self, site_name: str = None):
        """Expand a site and click All Cameras to show thumbnails."""
        self.click_site(site_name)
        self.page.wait_for_timeout(500)
        self.click_all_cameras()
        self.page.wait_for_timeout(1000)
