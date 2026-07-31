"""LPR (License Plate Recognition) Page Object Model."""
from playwright.sync_api import Page, expect


class LprPage:
    """Page object for LPR module functionality."""

    def __init__(self, page: Page):
        self.page = page

    # ===================== Locators =====================
    # Main LPR elements
    @property
    def admin_nav(self):
        return self.page.locator("span:has-text('Admin')")

    @property
    def lpr_menu(self):
        return self.page.locator("p:has-text('LPR')")

    # LPR Lists page
    @property
    def create_list_button(self):
        return self.page.locator("button:has-text('Create List')")

    # Plate page
    @property
    def add_plate_button(self):
        return self.page.locator("button:has-text('Add Plate')")

    # Filter panel
    @property
    def filter_icon(self):
        return self.page.locator("img[alt*='Filter']")

    @property
    def apply_filter_button(self):
        return self.page.locator("button:has-text('Apply')")

    @property
    def reset_filter_button(self):
        return self.page.locator("button:has-text('Reset')")

    # Search Results
    @property
    def search_results_header(self):
        return self.page.locator("span:has-text('Search Results')")

    @property
    def lpr_breadcrumb(self):
        return self.page.locator("span[style*='cursor']:has-text('LPR')")

    # Categories
    @property
    def add_category_button(self):
        return self.page.locator("button:has-text('Add Category')")

    @property
    def categories_tab(self):
        return self.page.locator("button:has-text('Categories')")

    @property
    def results_table(self):
        return self.page.locator("table")

    # ===================== Navigation Methods =====================

    def navigate_to_lpr(self):
        """Navigate to Admin > LPR from any page."""
        # Wait for main layout
        self.page.locator("body").wait_for(state="visible", timeout=30000)

        # Click Admin
        self.admin_nav.first.click()
        self.page.wait_for_timeout(1000)

        # Click LPR menu
        self.lpr_menu.first.click()
        self.page.wait_for_timeout(1000)

        # Wait for LPR Lists page to load
        self.create_list_button.first.wait_for(state="visible", timeout=30000)

    def ensure_lpr_page(self):
        """Ensure on LPR main page (Lists page).

        Handles three cases:
        1. Already on Lists page - return
        2. Inside Plate page - navigate back via breadcrumb
        3. Not on LPR - navigate to LPR
        """
        # CASE 1: Already on Lists page
        if self.create_list_button.count() > 0:
            print("[LPR] Already on Lists page")
            return

        # CASE 2: Inside Plate page
        if self.add_plate_button.count() > 0:
            print("[LPR] On Plate page, navigating back to Lists")
            self.lpr_breadcrumb.first.click()
            self.create_list_button.first.wait_for(state="visible", timeout=30000)
            return

        # CASE 3: Navigate to LPR
        print("[LPR] Navigating to Admin > LPR")
        self.navigate_to_lpr()

    def ensure_lpr_lists_page(self):
        """Ensure on LPR Lists page.

        Handles four cases:
        0. In Search Results - use breadcrumb to return
        1. Already on Lists - return
        2. Inside Plate page - use breadcrumb to return
        3. Anywhere else - navigate to LPR
        """
        # CASE 0: In Search Results
        if self.search_results_header.count() > 0:
            print("[LPR] In Search Results, returning to Lists via breadcrumb")
            self.lpr_breadcrumb.first.click()
            self.create_list_button.first.wait_for(state="visible", timeout=60000)
            return

        # CASE 1: Already on Lists
        if self.create_list_button.count() > 0:
            print("[LPR] Already on Lists page")
            return

        # CASE 2: Inside Plate page
        if self.add_plate_button.count() > 0:
            print("[LPR] On Plate page, returning to Lists via breadcrumb")
            self.lpr_breadcrumb.first.click()
            self.create_list_button.first.wait_for(state="visible", timeout=60000)
            return

        # CASE 3: Navigate from anywhere else
        print("[LPR] Navigating to Lists page")
        self.navigate_to_lpr()

    def ensure_lpr_plate_page(self, list_name: str):
        """Ensure on LPR Plate page (inside a list).

        Handles three cases:
        0. In Search Results - click Reset button
        1. Already on Plate page - return
        2. On Lists page - open the specified list
        """
        # CASE 0: In Search Results
        if self.search_results_header.count() > 0:
            print("[LPR] In Search Results, resetting to Plate page")
            self.reset_filter_button.first.click()
            self.add_plate_button.first.wait_for(state="visible", timeout=60000)
            return

        # CASE 1: Already on Plate page
        if self.add_plate_button.count() > 0:
            print("[LPR] Already on Plate page")
            return

        # CASE 2: On Lists page - open the list
        if self.create_list_button.count() > 0:
            print(f"[LPR] On Lists page, opening list: {list_name}")
            self._open_list_by_name(list_name)
            return

        # CASE 3: Navigate to Lists first, then open list
        print("[LPR] Navigating to Lists, then opening plate")
        self.ensure_lpr_lists_page()
        self._open_list_by_name(list_name)

    def ensure_lpr_filter_panel(self, list_name: str):
        """Ensure filter panel is open on Plate page."""
        # First, ensure we're on Plate page
        self.ensure_lpr_plate_page(list_name)

        # If filter panel already open, return
        if self.apply_filter_button.count() > 0:
            print("[LPR] Filter panel already open")
            return

        print("[LPR] Opening filter panel")
        self.filter_icon.first.click()
        self.apply_filter_button.first.wait_for(state="visible", timeout=30000)

    def ensure_in_search_results(self):
        """Verify we are in Search Results view."""
        if self.search_results_header.count() > 0:
            print("[LPR] Already in Search Results view")
            return

        raise Exception("[LPR] Not in Search Results - apply a filter first")

    def ensure_lpr_categories_page(self):
        """Ensure on LPR Categories page."""
        # If already on Categories, return
        if self.add_category_button.count() > 0:
            print("[LPR] Already on Categories page")
            return

        # Navigate to Lists first
        self.ensure_lpr_lists_page()
        self.page.wait_for_timeout(1000)

        # Click Categories tab with force=True to bypass overlays
        print("[LPR] Clicking Categories tab")
        self.categories_tab.first.click(force=True)
        self.page.wait_for_timeout(1000)
        self.add_category_button.first.wait_for(state="visible", timeout=20000)

    # ===================== Helper Methods =====================

    def _open_list_by_name(self, list_name: str):
        """Open a specific list by name from Lists page."""
        # Find the row containing the list name
        list_row = self.page.locator(f"tr:has-text('{list_name}')").first
        list_row.wait_for(state="visible", timeout=60000)

        # Click the View icon in that row
        view_icon = list_row.locator("img[aria-label='View']")
        view_icon.click()

        # Wait for Plate page to load
        self.add_plate_button.first.wait_for(state="visible", timeout=60000)
        print(f"[LPR] Opened list: {list_name}")

    def apply_filter_and_wait_results(self):
        """Click Apply button and wait for Search Results."""
        print("[LPR] Applying filter")
        self.apply_filter_button.first.click()

        # Wait for Search Results header and table
        self.search_results_header.first.wait_for(state="visible", timeout=60000)
        self.results_table.first.wait_for(state="visible", timeout=60000)
        print("[LPR] Search Results loaded")

    def reset_filter_and_return_to_plate(self):
        """Click Reset button and return to Plate page."""
        print("[LPR] Resetting filter")
        self.reset_filter_button.first.click()

        # Wait for Plate page to load
        self.add_plate_button.first.wait_for(state="visible", timeout=60000)
        print("[LPR] Returned to Plate page")

    def get_list_row(self, list_name: str):
        """Get a list row by name for further operations."""
        return self.page.locator(f"tr:has-text('{list_name}')").first

    def click_view_icon_on_list(self, list_name: str):
        """Click View icon on a specific list."""
        list_row = self.get_list_row(list_name)
        view_icon = list_row.locator("img[aria-label='View']")
        view_icon.click()

    # ===================== LPR Camera/Playback Methods =====================

    def ensure_lpr_camera_page(self):
        """Navigate to LPR camera/playback page from left sidebar."""
        # Check if already on LPR camera page
        if self.page.url.endswith("/lpr") or "/lpr" in self.page.url:
            drag_drop_text = self.page.locator("div:has-text('Drag & Drop Camera here')")
            if drag_drop_text.count() > 0:
                print("[LPR] Already on LPR camera page")
                return

        print("[LPR] Navigating to LPR camera page")
        lpr_link = self.page.locator("a[href='/lpr']").first
        lpr_link.wait_for(state="visible", timeout=30000)
        lpr_link.click()

        # Wait for page to load
        self.page.wait_for_url("**/lpr", timeout=30000)
        self.page.locator("div:has-text('Drag & Drop Camera here')").first.wait_for(
            state="visible", timeout=30000
        )
        print("[LPR] LPR camera page ready")

    def ensure_lpr_dropdown_open(self):
        """Opens the Locations & Cameras dropdown on LPR page."""
        # Check if already open (up arrow icon visible)
        up_arrow = self.page.locator("img[contains(@src,'upAccordionIcon')][alt='up-icon']")
        if up_arrow.count() > 0:
            print("[LPR] Locations & Cameras dropdown already open")
            return

        print("[LPR] Opening Locations & Cameras dropdown")
        # Click the dropdown header
        dropdown_btn = self.page.locator(
            "p[contains(@class,'select-box-content')]:has-text('Locations')"
        ).first
        dropdown_btn.wait_for(state="visible", timeout=30000)
        dropdown_btn.click()
        self.page.wait_for_timeout(1500)

        # Verify it opened by checking for up arrow or site list
        try:
            self.page.locator("img[contains(@src,'upAccordionIcon')][alt='up-icon']").first.wait_for(
                state="visible", timeout=10000
            )
            print("[LPR] Dropdown confirmed open (up arrow visible)")
        except:
            # Fallback: check if site list is visible
            self.page.locator("div[contains(@class,'select-box-sub-heading')]").first.wait_for(
                state="visible", timeout=10000
            )
            print("[LPR] Dropdown confirmed open (site list visible)")

    def dismiss_any_backdrop(self):
        """Helper to close any open modal/backdrop before proceeding."""
        try:
            backdrop = self.page.locator("div[contains(@class,'MuiBackdrop-root')]")
            if backdrop.count() > 0 and backdrop.first.is_visible(timeout=2000):
                print("[LPR] Backdrop detected, dismissing with Escape")
                self.page.keyboard.press("Escape")
                self.page.wait_for_timeout(1000)
                backdrop.first.wait_for(state="hidden", timeout=10000)
                print("[LPR] Backdrop dismissed")
        except Exception as e:
            print(f"[LPR] No backdrop to dismiss: {e}")

    def open_playback_timeout_popup(self):
        """Open Playback Timeout popup (generic views page)."""
        print("[LPR] Opening Playback Timeout popup")
        timeout_icon = self.page.locator("img[src='/icons/timer.svg']").last
        timeout_icon.wait_for(state="visible", timeout=30000)
        timeout_icon.click()
        self.page.wait_for_timeout(1000)

        # Verify popup opened
        popup_title = self.page.locator("p:has-text('Set Timeout Duration')")
        popup_title.first.wait_for(state="visible", timeout=30000)
        print("[LPR] Playback Timeout popup opened")

    def open_lpr_playback_timeout_popup(self):
        """Open LPR-specific Playback Timeout popup."""
        print("[LPR] Opening LPR Playback Timeout popup")
        timeout_icon = self.page.locator("img[src='/icons/timer.svg']").last
        timeout_icon.wait_for(state="visible", timeout=30000)
        timeout_icon.click()
        self.page.wait_for_timeout(1000)

        # Verify popup opened
        popup_title = self.page.locator("p:has-text('Set Timeout Duration')")
        popup_title.first.wait_for(state="visible", timeout=30000)
        print("[LPR] LPR Playback Timeout popup opened")

    def dismiss_lpr_backdrop(self):
        """Dismiss backdrop on LPR page."""
        self.dismiss_any_backdrop()

    # ===================== Camera Playback Methods =====================

    def play_camera(self, site_name: str, location_name: str, camera_name: str = "", play_all_cameras: bool = False):
        """Play camera(s) by dragging to tile."""
        self.page.wait_for_timeout(5000)

        # Wait for site to load
        print(f"[LPR] Checking for Site '{site_name}'")
        self.page.locator(f"text={site_name}").first.wait_for(state="visible", timeout=60000)
        print(f"[LPR] Site '{site_name}' loaded")

        # Click site
        self.page.wait_for_timeout(5000)
        site_elements = self.page.locator(f"text='{site_name}'")
        site_elements.first.click()
        print(f"[LPR] Clicked on site '{site_name}'")
        self.page.wait_for_timeout(3000)

        # Select location
        print(f"[LPR] Selecting location '{location_name}'")
        location_elements = self.page.locator(f"text='{location_name}'")
        location_elements.first.scroll_into_view_if_needed()
        location_elements.first.click()
        print(f"[LPR] Clicked on location '{location_name}'")

        # Wait for cameras to load
        camera_elements = self.page.locator(
            "div[contains(@class,'MuiStack-root')][contains(@class,'mui-ebmxkk')]"
        )
        camera_elements.first.wait_for(state="visible", timeout=60000)

        # Filter cameras if camera_name provided
        if camera_name:
            filtered = camera_elements.filter(has_text=camera_name)
            if filtered.count() == 0:
                raise AssertionError(f"Camera '{camera_name}' not available")
            cameras_to_play = [filtered.nth(0)]
            print(f"[LPR] Camera '{camera_name}' found")
        else:
            cameras_to_play = [camera_elements.nth(i) for i in range(camera_elements.count())]
            print(f"[LPR] Found {len(cameras_to_play)} camera(s) to play")

        # Drag and drop cameras
        tiles = self.page.locator("div:has-text('Drag & Drop Camera here')")
        if tiles.count() == 0:
            raise AssertionError("No available tiles to drop camera into")

        for idx, camera in enumerate(cameras_to_play):
            try:
                print(f"[LPR] Dragging camera {idx + 1}")
                tiles.nth(0 if not "lpr" in self.page.url.lower() else 1).drag_to(camera)
                self.page.wait_for_timeout(2000)

                # Wait for loader to disappear
                loader = self.page.locator("*[contains(@class,'CircularProgress')]")
                if loader.count() > 0:
                    loader.first.wait_for(state="hidden", timeout=60000)

                # Check stream status
                error = self.page.locator("text=failed to load")
                if error.count() > 0:
                    print(f"[LPR] Streaming failed for camera")
                    raise AssertionError("Streaming failed for camera")

                print(f"[LPR] Camera {idx + 1} playing successfully")

                if play_all_cameras:
                    self.page.wait_for_timeout(2000)
                    clear_btn = self.page.locator("button:has-text('Clear All')").first
                    clear_btn.wait_for(state="visible", timeout=10000)
                    clear_btn.click()
                    print("[LPR] Cleared camera for next")

            except Exception as e:
                raise AssertionError(f"Error playing camera {idx + 1}: {e}")

    def ensure_camera_present(self):
        """Verify camera is present on page."""
        videos = self.page.locator("video")
        if videos.count() == 0:
            print("[LPR] No active camera found")
            return False
        print("[LPR] Active camera present")
        return True

    def activate_camera_tile(self):
        """Activate camera tile for playback."""
        print("[LPR] Activating camera tile")

        # Wait for video or canvas
        video_or_canvas = self.page.locator("video, canvas").first
        video_or_canvas.wait_for(state="visible", timeout=60000)
        self.page.wait_for_timeout(3000)

        # Click to activate
        video_or_canvas.click()
        print("[LPR] Camera tile activated")

    # ===================== Views Page Methods =====================

    def go_to_views_page(self):
        """Navigate to Views page safely."""
        print("[LPR] Ensuring Views page (safe mode)")

        # Check if already on Views
        if "/views" in self.page.url.lower():
            print("[LPR] Already on Views page")
            return

        print("[LPR] Navigating to Views page")
        views_tab = self.page.locator("span:has-text('Views')").first
        views_tab.wait_for(state="visible", timeout=30000)
        views_tab.click(force=True)
        self.page.wait_for_timeout(2000)
        print("[LPR] Switched to Views page")

    def wait_for_site_list(self, site_name: str):
        """Wait for site list to load."""
        print(f"[LPR] Waiting for site '{site_name}' to appear")
        self.page.locator(f"text='{site_name}'").first.wait_for(state="visible", timeout=60000)
        print("[LPR] Site list loaded")

    def safe_reset_to_views(self):
        """Safe reset to Views page (non-breaking)."""
        print("[LPR] Safe reset to Views (non-breaking)")
        try:
            self.page.reload()
            self.page.wait_for_timeout(5000)
        except:
            pass

        # Try navigating to Views
        try:
            views_btn = self.page.locator("span:has-text('Views')").first
            if views_btn.is_visible(timeout=2000):
                views_btn.click()
                self.page.wait_for_timeout(3000)
        except:
            print("[LPR] Views button not found, continuing")

        # Remove any overlay
        try:
            self.page.locator("body").first.click()
            self.page.wait_for_timeout(1000)
        except:
            pass

        print("[LPR] Safe reset done")
