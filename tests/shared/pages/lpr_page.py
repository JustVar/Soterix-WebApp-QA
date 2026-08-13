"""LPR (License Plate Recognition) Page Object Model."""
import re

from playwright.sync_api import Error as PlaywrightError, Page, expect

# An event card's timestamp line ('1:37:38 AM | Aug 11 2026'). The
# time part alone anchors the card; assertions add the date part.
EVENT_TIME_RE = re.compile(r"\d{1,2}:\d{2}:\d{2} [AP]M")


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

        # Click Admin; the LPR menu click waits for the submenu itself
        self.admin_nav.first.click()

        # Click LPR menu
        self.lpr_menu.first.click()

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

        # Click Categories tab with force=True to bypass overlays
        print("[LPR] Clicking Categories tab")
        self.categories_tab.first.click(force=True)
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
        """Open the Locations & Cameras panel when it is closed.

        Open means a site row (draggable) is visible. The accordion
        icon cannot carry the state check: the app keeps the
        downAccordionIcon src and only flips the alt text, and the
        panel sub-headings are visible even when the panel is closed,
        so both old checks re-clicked an open panel shut.
        """
        site_rows = self.page.locator("div[draggable='true']")
        try:
            site_rows.first.wait_for(state="visible", timeout=2000)
            print("[LPR] Locations & Cameras panel already open")
            return
        except PlaywrightError:
            pass

        print("[LPR] Opening Locations & Cameras panel")
        dropdown_btn = self.page.locator(
            "p[class*='select-box-content']:has-text('Locations')"
        ).first
        dropdown_btn.wait_for(state="visible", timeout=30000)
        dropdown_btn.click()
        # The header is a toggle: if the panel was open with rows still
        # rendering, that click closed it - one more click self-heals
        try:
            site_rows.first.wait_for(state="visible", timeout=15000)
        except PlaywrightError:
            dropdown_btn.click()
            site_rows.first.wait_for(state="visible", timeout=15000)

    def dismiss_any_backdrop(self):
        """Helper to close any open modal/backdrop before proceeding.

        Gates on visible backdrops: MUI leaves detached hidden
        backdrops in the DOM, so a .first check can look at a stale
        one while a real backdrop sits later in the list.
        """
        try:
            backdrop = self.page.locator(
                "div[class*='MuiBackdrop-root']:visible"
            )
            if backdrop.count() > 0:
                print("[LPR] Backdrop detected, dismissing with Escape")
                self.page.keyboard.press("Escape")
                backdrop.first.wait_for(state="hidden", timeout=10000)
                print("[LPR] Backdrop dismissed")
        except Exception as e:
            print(f"[LPR] No backdrop to dismiss: {e}")

    def open_playback_timeout_popup(self):
        """Open the playback timeout popup.

        The popup opens only while a stream is playing and is titled
        'Set Timeout Duration'. The icon's TOOLTIP reads 'Playback
        Auto-Timeout' and shows on any click, which made a
        tooltip-text wait pass with the popup never opening
        (measured 08/12/2026).
        """
        print("[LPR] Opening Playback Timeout popup")
        timeout_icon = self.page.locator("img[src='/icons/timer.svg']").last
        timeout_icon.wait_for(state="visible", timeout=30000)
        timeout_icon.click()

        self.page.get_by_text("Set Timeout Duration").first.wait_for(
            state="visible", timeout=15000
        )
        print("[LPR] Playback Timeout popup opened")

    def open_lpr_playback_timeout_popup(self):
        """Open the playback timeout popup on the LPR page.

        Same contract as open_playback_timeout_popup: a stream must
        be playing, and 'Set Timeout Duration' is the popup title.
        """
        print("[LPR] Opening LPR Playback Timeout popup")
        timeout_icon = self.page.locator("img[src='/icons/timer.svg']").last
        timeout_icon.wait_for(state="visible", timeout=30000)
        timeout_icon.click()

        self.page.get_by_text("Set Timeout Duration").first.wait_for(
            state="visible", timeout=15000
        )
        print("[LPR] LPR Playback Timeout popup opened")

    # ===================== Camera Playback Methods =====================

    def open_site_group(self, site_name: str, group_name: str = "All Cameras"):
        """Expand the panel down to a site's camera group.

        The Locations & Cameras panel starts closed and lists
        site > camera groups > cameras; every level is a draggable row.
        Returns the group row locator with the group open.
        """
        self.ensure_lpr_dropdown_open()

        site = self.page.locator("div[draggable='true']").filter(
            has_text=site_name
        ).first
        site.wait_for(state="visible", timeout=60000)

        group = self.page.locator("div[draggable='true']").filter(
            has_text=group_name
        ).first
        # A click during tree hydration is silently dropped: re-click
        # the site once if the group list does not appear
        try:
            group.wait_for(state="visible", timeout=3000)
        except PlaywrightError:
            site.click()
            try:
                group.wait_for(state="visible", timeout=15000)
            except PlaywrightError:
                print("[LPR] Site click did not expand the tree, retrying")
                site.click()
                group.wait_for(state="visible", timeout=15000)
        return group

    def _empty_tile(self):
        """An empty playback tile, clearing the view when none is free.

        The last tile: the Locations & Cameras panel floats over the
        left side of the grid, so a drop on the first tile lands on
        the panel and does nothing.
        """
        tile = self.page.get_by_text(
            "Drag & Drop Camera here", exact=True
        ).last
        try:
            tile.wait_for(state="visible", timeout=5000)
            return tile
        except PlaywrightError:
            pass
        self.clear_all_tiles()
        tile.wait_for(state="visible", timeout=15000)
        return tile

    def clear_all_tiles(self):
        """Clear playing streams so empty tiles come back. Best effort."""
        for label in ("Clear All", "Reset View"):
            btn = self.page.get_by_text(label, exact=True).first
            try:
                if btn.is_visible():
                    btn.click()
                    # Clearing re-renders the tiles with no other signal
                    self.page.wait_for_timeout(1500)
                    return
            except PlaywrightError:
                continue

    def play_camera(self, site_name: str, camera_name: str = "",
                    play_all_cameras: bool = False,
                    group_name: str = "All Cameras"):
        """Drag a camera (or the whole group) onto a playback tile.

        Raises AssertionError when the camera is missing from the group
        or no new stream element appears after the drop.
        """
        group = self.open_site_group(site_name, group_name)

        if play_all_cameras:
            # The oracle stays at one new stream: the shared tenant
            # keeps offline cameras in the group, so requiring all of
            # them would fail on tenant state, not on the drop
            source = group
            print(f"[LPR] Playing the '{group_name}' group")
        else:
            cameras = self.page.locator("div[draggable='true']").filter(
                has_text=camera_name
            )
            # Expand the group only when the camera is not already
            # showing: a click on an expanded group collapses it. If
            # that first click collapsed a slow-rendering open group,
            # one more click self-heals before the loud failure.
            try:
                cameras.first.wait_for(state="visible", timeout=2000)
            except PlaywrightError:
                group.click()
                try:
                    cameras.first.wait_for(state="visible", timeout=20000)
                except PlaywrightError:
                    group.click()
                    try:
                        cameras.first.wait_for(state="visible", timeout=15000)
                    except PlaywrightError:
                        raise AssertionError(
                            f"Camera '{camera_name}' is not in group "
                            f"'{group_name}' of site '{site_name}'"
                        ) from None
            source = cameras.first
            print(f"[LPR] Camera '{camera_name}' found")

        tile = self._empty_tile()
        before = self.page.locator("video").count()
        failed_before = self.page.locator("text=failed to load").count()
        tile.scroll_into_view_if_needed()
        source.drag_to(tile)

        # No loader wait: empty tiles keep placeholder spinners alive
        # forever (same trap as in-camera search), so CircularProgress
        # hidden can never finish. The new stream element is the signal;
        # failed_before keeps a leftover failed tile from being blamed.
        # A new stream element past the baseline is the played signal
        try:
            self.page.locator("video").nth(before).wait_for(
                state="attached", timeout=60000
            )
        except PlaywrightError:
            # Name the real cause when the app rendered a failure
            if self.page.locator(
                "text=failed to load"
            ).count() > failed_before:
                raise AssertionError(
                    f"Stream failed to load for "
                    f"'{camera_name or group_name}'"
                ) from None
            raise AssertionError(
                f"No new stream appeared after dropping "
                f"'{camera_name or group_name}' (had {before} videos)"
            ) from None
        print("[LPR] Stream playing")

    def activate_camera_tile(self):
        """Activate camera tile for playback."""
        print("[LPR] Activating camera tile")

        # The last video: play_camera drops on the last tile, and a
        # video-canvas union resolves .last to a hidden canvas overlay
        video = self.page.locator("video").last
        video.wait_for(state="visible", timeout=60000)
        # The stream needs a beat after the first frame before the tile
        # accepts activation clicks; there is no DOM signal for that
        self.page.wait_for_timeout(3000)

        # force: tile overlays (controls fade layer) intercept the
        # actionability check while the click itself lands fine
        video.click(force=True)
        # The player's live icon appearing is the activation signal
        # (measured: it shows only after the tile click)
        self.page.locator("img[alt='live icon']").first.wait_for(
            state="visible", timeout=10000
        )
        print("[LPR] Camera tile activated")

    # ===================== Event Feed Methods =====================

    def event_cards(self):
        """Event cards in the live feed on the LPR camera page.

        A card is the third ancestor of its timestamp line: the feed
        carries no stable class names, and the plate texts end with a
        trailing space, so the timestamp is the dependable anchor.
        """
        return self.page.get_by_text(EVENT_TIME_RE).locator(
            "xpath=ancestor::*[position()=3]"
        )

    def open_first_event(self):
        """Open the first event's clip player; the video is the signal."""
        cards = self.event_cards()
        cards.first.wait_for(state="visible", timeout=30000)
        cards.first.click()
        self.page.locator("video").first.wait_for(
            state="attached", timeout=30000
        )

    def close_event_player(self):
        """Close the clip player; the video leaving is the signal."""
        self.page.locator("img[alt='close icon']").first.click()
        self.page.locator("video").first.wait_for(
            state="detached", timeout=10000
        )

    # ===================== Views Page Methods =====================

    def go_to_views_page(self):
        """Navigate to the Views page.

        The app renders Views at the root URL, so the subtab bar
        (.viewTabs) is the page marker, not the URL.
        """
        marker = self.page.locator(".viewTabs").first
        try:
            if marker.is_visible():
                print("[LPR] Already on Views page")
                return
        except PlaywrightError:
            pass

        print("[LPR] Navigating to Views page")
        views_tab = self.page.locator("span:has-text('Views')").first
        views_tab.wait_for(state="visible", timeout=30000)
        views_tab.click(force=True)
        marker.wait_for(state="visible", timeout=15000)
        print("[LPR] Views page ready")

    def wait_for_site_list(self, site_name: str):
        """Wait for site list to load."""
        print(f"[LPR] Waiting for site '{site_name}' to appear")
        self.page.locator(f"text='{site_name}'").first.wait_for(state="visible", timeout=60000)
        print("[LPR] Site list loaded")

    def safe_reset_to_views(self):
        """Safe reset to Views page (non-breaking)."""
        print("[LPR] Safe reset to Views (non-breaking)")
        try:
            # reload() waits for the load event on its own
            self.page.reload()
        except Exception:
            pass

        # Try navigating to Views (rendered at the root URL, so the
        # subtab bar is the arrival signal)
        try:
            views_btn = self.page.locator("span:has-text('Views')").first
            if self._appears(views_btn, timeout=10000):
                views_btn.click()
                self.page.locator(".viewTabs").first.wait_for(
                    state="visible", timeout=15000
                )
        except Exception:
            print("[LPR] Views button not found, continuing")

        # Remove any overlay
        try:
            self.page.locator("body").first.click()
        except Exception:
            pass

        print("[LPR] Safe reset done")

    # ===================== Wait helpers =====================

    @staticmethod
    def _appears(locator, timeout: int = 5000) -> bool:
        """True when the element shows within timeout, False otherwise."""
        try:
            locator.wait_for(state="visible", timeout=timeout)
            return True
        except PlaywrightError:
            return False
