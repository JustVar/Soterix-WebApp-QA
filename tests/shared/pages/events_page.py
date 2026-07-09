"""Events Page Object Model.

Models the Events page including site/camera selection, duration filtering,
event search, pinning, review, playback, and export flows.
"""
import json
import datetime
from playwright.sync_api import Page, expect


class EventsPage:
    """Page object for the Events page and its sub-flows."""

    def __init__(self, page: Page):
        self.page = page

        # Navigation
        self.events_nav_link = page.locator("a[href*='events']")
        self.events_container = page.locator(".eventfeedContainer")

        # Rule type dropdown (first combobox on the page)
        self.rule_dropdown = page.locator('[role="combobox"]').first

        # Site dropdown (MUI Select)
        self.site_dropdown = page.get_by_text("Select Site")

        # Locations & Cameras (collapsible panel, not a MUI Select)
        self.camera_dropdown = page.get_by_text("Locations & Cameras")
        self.camera_containers = page.locator(".global-search-camera-container")

        # Duration dropdown (MUI Select, may be disabled until site is selected)
        self.duration_dropdown = page.get_by_text("Last 1 Hour")
        self.duration_options = page.locator(".dropdownItem")

        # Search button (MUI IconButton wrapping SearchIcon SVG)
        # NOTE: icon-searchFilter.svg is the "More Filters" toggle, NOT search
        self.search_button = page.locator(
            "button:has(svg[data-testid='SearchIcon'])"
        )

        # Event results
        self.event_results = page.locator("img[alt='videoImg1']")
        self.pin_icon = page.locator("img[src*='media/roundPinIcon']")
        self.pinned_counter = page.locator(".pinnedClip_text")
        self.review_pinned_button = page.locator(
            "button:has-text('Review Pinned Clips')"
        )

        # Event playback (inline player)
        self.play_video_icon = page.locator("img[alt='Play Video']")
        self.player_close_button = page.locator(
            "svg[data-testid='CloseIcon']"
        )

        # Inline player controls (appear after playing an event)
        self.player_play_pause = page.locator("img[alt='pause']")
        self.player_backward = page.locator("img[alt='Backward']").first
        self.player_forward = page.locator("img[alt='forward']")
        self.player_volume = page.locator("img[alt='volumn icon']")
        self.player_screenshot = page.locator(
            "img[alt='Backward']"
        ).last  # Screenshot icon alt is also "Backward" (Image.svg)

        # Event action toolbar (appears above the inline player)
        self.lightbox_button = page.locator("img[src*='light box']")
        self.share_button = page.locator("img[alt='Share']")
        self.create_link_button = page.locator("img[alt='Create Link']")

        # Export button (use alt="Export" to avoid matching global download icon)
        self.export_button = page.get_by_alt_text("Export")
        self.export_popup = page.locator(".export_main_container_popup")
        self.export_filename_input = page.locator(
            ".export_main_container_popup #name"
        )
        self.export_save_to_media_toggle = page.locator(
            ".export_main_container_popup .PrivateSwitchBase-input"
        )
        self.export_confirm_button = page.locator(".save_button_export")
        self.export_progress_bar = page.locator(".export-progress-bar")

        # Loader
        self.loader = page.locator(".MuiCircularProgress-root")

    # --- Navigation ---

    def navigate(self):
        """Navigate to the Events page via the nav link."""
        self.events_nav_link.click()
        self.events_container.wait_for(state="visible", timeout=60000)

    def wait_for_page_load(self):
        """Wait for the Events page to finish loading."""
        self.events_container.wait_for(state="visible", timeout=60000)
        try:
            if self.loader.count() > 0 and self.loader.first.is_visible():
                self.loader.first.wait_for(state="hidden", timeout=30000)
        except Exception:
            pass

    # --- Filters ---

    def select_rule(self, rule_name: str = "Intrusion Detection"):
        """Open the rule type dropdown and select a rule.

        The 'All Rules' default is a placeholder -- a specific rule type
        must be selected before search will return results.
        """
        self.rule_dropdown.click()

        listbox = self.page.locator("[role='listbox']")
        listbox.wait_for(state="visible", timeout=10000)

        option = listbox.locator(
            f"li[role='option']:has-text('{rule_name}')"
        ).first
        option.click()
        self.page.wait_for_timeout(1000)

    def select_site(self, site_name: str = None):
        """Open site dropdown and select a site by name.

        MUI Select renders options in a portal as li[role='option'] inside
        a ul[role='listbox']. The invisible backdrop blocks other elements.
        Pass None to select the first available site using keyboard navigation.
        """
        self.site_dropdown.click()
        self.page.wait_for_timeout(1000)

        # Wait for the MUI Menu listbox to appear
        listbox = self.page.locator("[role='listbox']")
        listbox.wait_for(state="visible", timeout=20000)
        self.page.wait_for_timeout(1500)

        if site_name:
            # Find the option by name
            option = listbox.locator(
                f"li[role='option']:has-text('{site_name}')"
            ).first
            option.focus()
            self.page.wait_for_timeout(500)
            option.evaluate("el => el.click()")  # Use JS click instead
        else:
            # Use keyboard to navigate to first option
            self.page.keyboard.press("Home")
            self.page.wait_for_timeout(500)
            self.page.keyboard.press("Enter")

        self.page.wait_for_timeout(2000)

    def select_camera(self, site_name: str, camera_name: str,
                      location_name: str = None):
        """Open camera menu and navigate to a specific camera by name.

        Opens #simple-menu popover, expands site > All Cameras, and
        scrolls the named camera into view.

        KNOWN LIMITATION: The MUI Checkbox inside each camera container
        has zero-dimension elements (.container-item, .MuiCheckbox-root,
        and SVG icon all have no bounding box). Neither Playwright click
        methods nor React-compatible JS events reliably toggle the camera
        selection state. Search uses 'all cameras' by default.
        """
        self.camera_dropdown.click()
        self.page.wait_for_timeout(1000)

        menu = self.page.locator("#simple-menu")
        menu.wait_for(state="visible", timeout=10000)

        # Expand the site
        site_node = menu.locator(
            f".MuiListItemButton-root:has-text('{site_name}')"
        ).first
        site_node.click()
        self.page.wait_for_timeout(1000)

        # Expand "All Cameras" to show individual cameras
        all_cameras = menu.get_by_text("All Cameras")
        if all_cameras.count() > 0:
            all_cameras.click()
            self.page.wait_for_timeout(1000)

        # Expand the location if specified
        if location_name:
            location_node = menu.get_by_text(location_name, exact=False)
            if location_node.count() > 0:
                location_node.first.click()
                self.page.wait_for_timeout(1000)

        # Find and scroll to the target camera
        containers = menu.locator(".global-search-camera-container")
        for i in range(containers.count()):
            container = containers.nth(i)
            text = container.evaluate("el => el.textContent || ''")
            if camera_name in text:
                container.scroll_into_view_if_needed()
                self.page.wait_for_timeout(300)
                break
        self.page.wait_for_timeout(500)

        # Dismiss the menu
        self._dismiss_camera_menu()

    def select_first_available_camera(self, site_name: str):
        """Open camera menu and navigate to the first available camera.

        Clicking "Locations & Cameras" opens a #simple-menu MUI Popover
        with a tree: Site > All Cameras > individual cameras.
        Expands the site node and verifies cameras are listed.

        KNOWN LIMITATION: The MUI Checkbox inside camera containers has
        zero-dimension elements and cannot be toggled via automation.
        Search uses 'all cameras' by default when no checkbox is checked.
        """
        self.camera_dropdown.click()
        self.page.wait_for_timeout(1000)

        # The menu renders in a popover with id="simple-menu"
        menu = self.page.locator("#simple-menu")
        menu.wait_for(state="visible", timeout=10000)

        # Expand the site node inside the menu
        site_node = menu.locator(
            f".MuiListItemButton-root:has-text('{site_name}')"
        ).first
        site_node.click()
        self.page.wait_for_timeout(1000)

        # Click "All Cameras" to expand the cameras list
        all_cameras = menu.get_by_text("All Cameras")
        if all_cameras.count() > 0:
            all_cameras.click()
            self.page.wait_for_timeout(1000)

        # Verify cameras are listed
        containers = menu.locator(".global-search-camera-container")
        containers.first.wait_for(state="visible", timeout=10000)
        self.page.wait_for_timeout(500)

        # Dismiss the menu
        self._dismiss_camera_menu()

    def select_duration(self, duration_text: str):
        """Open duration dropdown and select an option by text.

        Duration dropdown is disabled until a site is selected.
        Uses MUI Select option pattern. The dropdown locator is resolved
        dynamically since the text changes after selection.
        """
        # Find the duration dropdown by current text (may have changed)
        duration_labels = ["Last 1", "Last 3", "Last 6", "Last 12", "Last 24", "Last 7", "Custom"]
        clicked = False
        for label in duration_labels:
            try:
                loc = self.page.get_by_text(label, exact=False).first
                if loc.is_visible(timeout=1000):
                    loc.click()
                    clicked = True
                    break
            except Exception:
                continue
        if not clicked:
            self.duration_dropdown.click()

        listbox = self.page.locator("[role='listbox']")
        listbox.wait_for(state="visible", timeout=10000)

        option = listbox.locator(
            f"li[role='option']:has-text('{duration_text}')"
        ).first
        option.click()
        self.page.wait_for_timeout(1000)

    def get_rule_options(self) -> list:
        """Open rule dropdown and return all available rule type names."""
        self.rule_dropdown.click()
        listbox = self.page.locator("[role='listbox']")
        listbox.wait_for(state="visible", timeout=10000)
        options = listbox.locator("li[role='option']")
        texts = []
        for i in range(options.count()):
            txt = options.nth(i).inner_text().strip()
            if txt:
                texts.append(txt)
        self.page.keyboard.press("Escape")
        self.page.wait_for_timeout(500)
        return texts

    def get_site_options(self) -> list:
        """Open site dropdown and return all available site names."""
        self.site_dropdown.click()
        listbox = self.page.locator("[role='listbox']")
        listbox.wait_for(state="visible", timeout=10000)
        options = listbox.locator("li[role='option']")
        texts = []
        for i in range(options.count()):
            txt = options.nth(i).inner_text().strip()
            if txt:
                texts.append(txt)
        self.page.keyboard.press("Escape")
        self.page.wait_for_timeout(500)
        return texts

    def search_events_safe(self, timeout: int = 60000) -> bool:
        """Click search and return True if results appear, False if no results.

        Unlike search_events() this does not raise on zero results.
        """
        self.search_button.click()
        try:
            self.event_results.first.wait_for(state="visible", timeout=timeout)
            self.page.wait_for_timeout(2000)
            return True
        except Exception:
            self.page.wait_for_timeout(2000)
            return False

    # --- Search ---

    def search_events(self, timeout: int = 60000):
        """Click the search button and wait for event results to load."""
        self.search_button.click()
        self.event_results.first.wait_for(state="visible", timeout=timeout)
        self.page.wait_for_timeout(2000)

    def search_events_for_channels(self, channel_list: list[int],
                                   timeout: int = 60000):
        """Search events filtered to specific camera channels via route intercept.

        Intercepts the search API POST and replaces channelList with
        the given channel numbers before the request reaches the server.
        This bypasses the MUI camera checkbox (which has zero-dimension
        elements) while still using the UI's full search flow.

        Camera-to-channel mapping (Driver Site, alphabetical order):
            CH 1=Advidia, CH 7=Axis_1, CH 11=Hanwha_2, CH 13=Hanwha_5,
            CH 14=Hanwha_6, CH 15=Hanwha_7, CH 23=Hanwha_PTZ, etc.
        Channel N = camera at 0-based index (N-1) in alphabetical list.
        """
        def modify_search(route):
            request = route.request
            if (request.method == "POST"
                    and request.post_data
                    and "queryList" in request.post_data):
                body = json.loads(request.post_data)
                body["queryList"][0]["query"]["channelList"] = channel_list
                route.continue_(post_data=json.dumps(body))
            else:
                route.continue_()

        self.page.route("**/v-apiserver/REST/site/search**", modify_search)
        try:
            self.search_button.click()
            self.event_results.first.wait_for(
                state="visible", timeout=timeout
            )
            self.page.wait_for_timeout(2000)
        finally:
            self.page.unroute("**/v-apiserver/REST/site/search**")

    def get_event_count(self) -> int:
        """Return the number of event result thumbnails."""
        return self.event_results.count()

    def has_valid_snapshots(self) -> bool:
        """Check that at least one event thumbnail is a real image.

        Blob URLs and data URIs are considered valid. Only
        'No_Image_Available' placeholders are invalid.
        """
        count = min(self.event_results.count(), 5)
        if count == 0:
            return False
        for i in range(count):
            src = self.event_results.nth(i).get_attribute("src") or ""
            if src.startswith("blob:") or src.startswith("data:image"):
                return True
            if "No_Image_Available" not in src and src:
                return True
        return False

    # --- Pin events ---

    def pin_event(self, index: int = 0):
        """Hover over an event result and click its pin icon.

        A .hover-overlay div sits on top of each event thumbnail
        (hidden by default, visible on CSS :hover). Using force=True
        bypasses the interception check and triggers the hover state.
        """
        event_img = self.event_results.nth(index)
        event_img.hover(force=True)
        self.page.wait_for_timeout(500)

        # Pin icon appears on hover within the overlay
        pin = self.page.locator("img[src*='roundPinIcon']").first
        pin.wait_for(state="visible", timeout=5000)
        pin.click()
        self.page.wait_for_timeout(500)

    def get_pinned_count_text(self) -> str:
        """Return the text from the pinned clips counter."""
        return self.pinned_counter.inner_text()

    def click_review_pinned_clips(self):
        """Click the 'Review Pinned Clips' button."""
        self.review_pinned_button.wait_for(state="visible", timeout=10000)
        self.review_pinned_button.click()
        self.page.wait_for_timeout(1000)

    # --- Single event playback ---

    def play_event(self, index: int = 0, timeout: int = 60000):
        """Hover on an event and click its play icon.

        The .hover-overlay intercepts pointer events on the event image.
        Using force=True bypasses the interception check. After a pin
        action the hover state may be stale, so we move mouse away
        first and re-hover to trigger a fresh CSS :hover.
        """
        event_img = self.event_results.nth(index)

        # Move mouse away then re-hover to guarantee a fresh :hover state
        self.page.mouse.move(0, 0)
        self.page.wait_for_timeout(300)
        event_img.hover(force=True)
        self.page.wait_for_timeout(500)

        play_icon = self.page.locator("img[alt='Play Video']").first
        try:
            play_icon.wait_for(state="visible", timeout=5000)
            play_icon.click()
        except Exception:
            # Overlay may not have activated; click with force
            play_icon.click(force=True)
        self._wait_for_loader_finish(timeout)

    def is_player_visible(self) -> bool:
        """Check if the inline video player is visible."""
        return self.player_play_pause.count() > 0 and \
            self.player_play_pause.is_visible()

    def close_player(self):
        """Close the inline event player via CloseIcon."""
        self.player_close_button.first.click()
        self.page.wait_for_timeout(1000)

    # --- Export ---

    def export_event(self, filename: str = None):
        """Click export, fill the dialog, and wait for progress to start.

        The export progress bar appears after clicking save. We verify
        the export initiated (progress bar visible) but don't wait for
        full completion, as it can take several minutes for large clips.
        """
        if filename is None:
            filename = datetime.datetime.now().strftime("%Y%m%d%H%M%S")

        self.export_button.click()
        self.export_popup.wait_for(state="visible", timeout=10000)

        self.export_filename_input.fill(filename)
        self.export_save_to_media_toggle.click()
        self.export_confirm_button.click()

        # Verify export started (progress bar appears)
        self.export_progress_bar.wait_for(state="visible", timeout=30000)

        return filename

    # --- Helpers ---

    def _dismiss_camera_menu(self):
        """Dismiss the #simple-menu camera selection popover.

        The MUI Menu backdrop is overlaid by the Paper element, so standard
        click-outside doesn't work. Click the backdrop with force=True and
        verify the menu is actually hidden.
        """
        menu = self.page.locator("#simple-menu")
        if menu.count() == 0 or not menu.is_visible():
            return

        # Click backdrop with force to bypass Paper overlay interception
        backdrop = self.page.locator("#simple-menu .MuiBackdrop-root")
        if backdrop.count() > 0:
            backdrop.click(force=True)
            self.page.wait_for_timeout(500)

        # Verify menu dismissed; if still open, force-close via JS
        if menu.count() > 0 and menu.is_visible():
            self.page.evaluate(
                "document.querySelector('#simple-menu')?.remove()"
            )
            self.page.wait_for_timeout(300)

    def _wait_for_loader_finish(self, timeout: int = 60000):
        """Wait for the CircularProgress loader to appear then disappear."""
        try:
            self.loader.first.wait_for(state="visible", timeout=5000)
        except Exception:
            pass  # Loader may have already finished
        try:
            self.loader.first.wait_for(state="hidden", timeout=timeout)
        except Exception:
            pass  # Some loaders may not fully disappear

    def is_on_event_player_page(self) -> bool:
        """Check if the inline event player is active."""
        return self.player_close_button.count() > 0 and \
            self.player_close_button.first.is_visible()
