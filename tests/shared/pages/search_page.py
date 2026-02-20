"""Global Search Page Object Model.

Models the Global Search page including category selection, description
filters, locations/cameras picker, duration, zone/line drawing on canvas,
search execution, and result playback.
"""
from playwright.sync_api import Page, expect


class SearchPage:
    """Page object for the Global Search page."""

    def __init__(self, page: Page):
        self.page = page

        # Navigation
        self.search_nav_link = page.locator("a[href*='search']")

        # Page identity - Category label appears when page is loaded
        self.category_label = page.locator("label[for='Category']")

        # Filter dropdowns (all use .search_select_box_container)
        self.filter_dropdowns = page.locator(".search_select_box_container")
        self.dropdown_items = page.locator(".dropdownItem")

        # Person description panel
        self.gender_container = page.locator(".gender-option-container")

        # Locations & Cameras (same pattern as Events page)
        self.camera_containers = page.locator(".global-search-camera-container")

        # Search button - shows as search-disable.svg when inactive,
        # changes to search_icon.svg when filters are set.
        # Located inside the search panel container, not the nav sidebar.
        self.search_button = page.locator(
            ".search_container_search img[src*='search']"
        ).first

        # Search results
        self.result_images = page.locator(".global-imageResults")
        self.play_clip_icon = page.locator("img[src*='media/playClip']")
        self.replay_icon = page.locator("img[alt='Replay']")

        # Zone/Line drawing
        self.canvas = page.locator(".upper-canvas")
        self.done_button = page.locator(".save-btn")
        self.create_zone_link = page.get_by_text("Create Zone", exact=True)
        self.create_line_link = page.get_by_text("Create Line", exact=True)

        # Loader
        self.loader = page.locator(".MuiCircularProgress-root")

    # --- Navigation ---

    def navigate(self):
        """Navigate to the Global Search page via the nav link."""
        self.search_nav_link.click()
        self.category_label.wait_for(state="visible", timeout=30000)

    def wait_for_page_load(self):
        """Wait for the Search page to finish loading."""
        self.category_label.wait_for(state="visible", timeout=30000)
        try:
            if self.loader.count() > 0 and self.loader.first.is_visible():
                self.loader.first.wait_for(state="hidden", timeout=30000)
        except Exception:
            pass

    # --- Filter helpers ---

    def _get_dropdown_by_text(self, label_text: str):
        """Find a .search_select_box_container dropdown by its label text.

        Dropdown containers have text like 'CategorySelect',
        'Duration Select', 'Locations & Cameras Select', etc.
        Matches if label_text appears anywhere in the container text.
        """
        count = self.filter_dropdowns.count()
        for i in range(count):
            dropdown = self.filter_dropdowns.nth(i)
            text = dropdown.evaluate("el => el.textContent || ''")
            if label_text in text:
                return dropdown
        return None

    def _select_dropdown_item(self, dropdown, item_index: int = 0):
        """Click a dropdown and select an item by index."""
        dropdown.click()
        self.page.wait_for_timeout(1000)
        items = self.dropdown_items
        items.nth(item_index).wait_for(state="visible", timeout=5000)
        items.nth(item_index).click()
        self.page.wait_for_timeout(500)

    def _select_dropdown_item_by_text(self, dropdown, text: str):
        """Click a dropdown and select an item by text."""
        dropdown.click()
        self.page.wait_for_timeout(1000)
        item = self.page.locator(f".dropdownItem:has-text('{text}')").first
        item.wait_for(state="visible", timeout=5000)
        item.click()
        self.page.wait_for_timeout(500)

    def _get_dropdown_options(self, label_text: str) -> list:
        """Open a dropdown by label, read all item texts, then close it."""
        dropdown = self._get_dropdown_by_text(label_text)
        if dropdown is None:
            return []
        dropdown.click()
        self.page.wait_for_timeout(1000)

        items = self.dropdown_items
        count = items.count()
        texts = []
        for i in range(count):
            try:
                text = items.nth(i).inner_text().strip()
                if text:
                    texts.append(text)
            except Exception:
                continue

        self.page.keyboard.press("Escape")
        self.page.wait_for_timeout(500)
        return texts

    def get_category_options(self) -> list:
        """Return all category dropdown item texts."""
        return self._get_dropdown_options("Category")

    def get_duration_options(self) -> list:
        """Return all duration dropdown item texts."""
        return self._get_dropdown_options("Duration")

    def is_description_panel_visible(self) -> bool:
        """Check if the Person description panel is visible."""
        dropdown = self._get_dropdown_by_text("Description")
        return dropdown is not None and dropdown.is_visible()

    def execute_search_safe(self, timeout: int = 60000) -> bool:
        """Click search and return True if results appear, False otherwise."""
        self.search_button.click()
        try:
            self.result_images.first.wait_for(state="visible", timeout=timeout)
            self.page.wait_for_timeout(2000)
            return True
        except Exception:
            return False

    # --- Filters ---

    def select_category(self, category_name: str):
        """Select a search category (Person, Vehicle, Event, etc.).

        Category indices in the dropdown:
            0=Person, 1=Vehicle, 2=Event, 3=Zone(?), 4=Line(?)
        """
        dropdown = self._get_dropdown_by_text("Category")
        assert dropdown is not None, "Category dropdown not found"
        self._select_dropdown_item_by_text(dropdown, category_name)

    def select_category_by_index(self, index: int):
        """Select a search category by dropdown index."""
        dropdown = self._get_dropdown_by_text("Category")
        assert dropdown is not None, "Category dropdown not found"
        self._select_dropdown_item(dropdown, index)

    def select_description_gender(self, gender: str = "Male"):
        """Select a gender in the Person description panel.

        Only available when Category = Person.
        """
        dropdown = self._get_dropdown_by_text("Description")
        if dropdown is None:
            return
        dropdown.click()
        self.page.wait_for_timeout(1000)

        self.gender_container.wait_for(state="visible", timeout=5000)
        gender_option = self.gender_container.locator(
            f"p:has-text('{gender}')"
        ).first
        gender_option.click()
        self.page.wait_for_timeout(500)

    def select_locations_cameras(self, site_name: str):
        """Open the Locations & Cameras dropdown, expand site, and select
        all cameras via the 'All Cameras' checkbox.

        The 'All Cameras' checkbox has zero-dimension elements (same MUI
        bug as Events page), but input.click() via JS successfully toggles
        the state and enables the search button.

        Uses JS to click the site node within the dropdown panel to avoid
        accidentally clicking notification toasts that also contain the
        site name text.
        """
        dropdown = self._get_dropdown_by_text("Locations")
        assert dropdown is not None, "Locations & Cameras dropdown not found"
        dropdown.click()
        self.page.wait_for_timeout(1000)

        # Click the site name within the dropdown panel (not notification)
        self.page.evaluate("""(siteName) => {
            const panel = document.querySelector('.scrollBarCustom') ||
                          document.querySelector('[class*="drop-down"]');
            if (!panel) return;
            const texts = panel.querySelectorAll('p, span');
            for (const t of texts) {
                if (t.textContent.includes(siteName) && t.offsetWidth > 0) {
                    t.click();
                    return;
                }
            }
        }""", site_name)
        self.page.wait_for_timeout(1000)

        # Click 'All Cameras' checkbox via JS (zero-dimension workaround)
        self.page.evaluate("""() => {
            const buttons = document.querySelectorAll('.MuiListItemButton-root');
            for (const btn of buttons) {
                const text = btn.textContent || '';
                if (text.startsWith('All Cameras')) {
                    const input = btn.querySelector('.PrivateSwitchBase-input');
                    if (input && !input.checked) {
                        input.click();
                    }
                    return;
                }
            }
        }""")
        self.page.wait_for_timeout(1000)

        # Dismiss by clicking the dropdown again
        dropdown.click()
        self.page.wait_for_timeout(500)

    def select_duration(self, duration_text: str = "Today"):
        """Select a duration from the Duration dropdown."""
        dropdown = self._get_dropdown_by_text("Duration")
        assert dropdown is not None, "Duration dropdown not found"
        self._select_dropdown_item_by_text(dropdown, duration_text)

    def select_duration_by_index(self, index: int = 4):
        """Select a duration by dropdown index (4 = Today in Selenium)."""
        dropdown = self._get_dropdown_by_text("Duration")
        assert dropdown is not None, "Duration dropdown not found"
        self._select_dropdown_item(dropdown, index)

    # --- Zone / Line drawing ---

    def open_zone_drawing(self, camera_name: str):
        """Hover on a camera container and click 'Create Zone'.

        Opens a canvas where a zone polygon can be drawn.
        """
        self._hover_camera_and_click_action(camera_name, "Create Zone")
        self._wait_for_loader_finish()

    def open_line_drawing(self, camera_name: str):
        """Hover on a camera container and click 'Create Line'.

        Opens a canvas where a line can be drawn.
        """
        self._hover_camera_and_click_action(camera_name, "Create Line")
        self._wait_for_loader_finish()

    def draw_zone(self):
        """Draw a rectangular zone on the canvas.

        Draws a polygon by clicking 5 points (4 corners + close).
        Uses relative offsets from the canvas center.
        """
        self.canvas.wait_for(state="visible", timeout=30000)
        box = self.canvas.bounding_box()
        assert box is not None, "Canvas bounding box not found"

        cx, cy = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
        w, h = box["width"] * 0.4, box["height"] * 0.4

        # Draw rectangle: TL -> TR -> BR -> BL -> close at TL
        points = [
            (cx - w, cy - h),
            (cx + w, cy - h),
            (cx + w, cy + h),
            (cx - w, cy + h),
            (cx - w, cy - h),
        ]
        for x, y in points:
            self.page.mouse.click(x, y)
            self.page.wait_for_timeout(300)

    def draw_line(self):
        """Draw a line on the canvas.

        Draws by clicking 2 points (start and end).
        """
        self.canvas.wait_for(state="visible", timeout=30000)
        box = self.canvas.bounding_box()
        assert box is not None, "Canvas bounding box not found"

        cx, cy = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
        w, h = box["width"] * 0.4, box["height"] * 0.4

        # Two points for a line
        self.page.mouse.click(cx - w, cy - h)
        self.page.wait_for_timeout(300)
        self.page.mouse.click(cx + w, cy + h)
        self.page.wait_for_timeout(300)

    def click_done(self):
        """Click the Done/Save button after drawing a zone or line."""
        self.done_button.wait_for(state="visible", timeout=10000)
        # Check if button is disabled (cursor: not-allowed)
        style = self.done_button.get_attribute("style") or ""
        if "not-allowed" in style:
            # Retry drawing with smaller offsets
            self.draw_zone()
        self.done_button.click()
        self.page.wait_for_timeout(2000)

    # --- Search execution ---

    def execute_search(self, timeout: int = 60000):
        """Click the search button and wait for results to load."""
        self.search_button.click()
        self.result_images.first.wait_for(state="visible", timeout=timeout)
        self.page.wait_for_timeout(2000)

    def get_result_count(self) -> int:
        """Return the number of search result images."""
        return self.result_images.count()

    def has_results(self) -> bool:
        """Check if any search results are displayed."""
        return self.result_images.count() > 0

    # --- Result playback ---

    def play_result(self, index: int = 0, timeout: int = 60000):
        """Hover on a search result and click the play clip icon.

        Results use .global-imageResults with a play overlay on hover.
        Uses MediaSource blob URLs with duration=Infinity. The app pauses
        the video and shows a Replay icon when clip data is exhausted.
        Clips typically play for ~20s before the app shows Replay.

        Stream loading is intermittent in QA env - some clips fail to
        load (readyState stays 0). Tests using this method should use
        @pytest.mark.flaky(reruns=1) to handle transient stream failures.
        """
        result = self.result_images.nth(index)
        result.hover()
        self.page.wait_for_timeout(500)

        play = self.play_clip_icon.first
        play.wait_for(state="visible", timeout=5000)
        play.click()
        self._wait_for_loader_finish(timeout)

    def is_replay_visible(self, timeout: int = 600000) -> bool:
        """Wait for the Replay icon to appear (video finished playing)."""
        try:
            self.replay_icon.first.wait_for(
                state="visible", timeout=timeout
            )
            return True
        except Exception:
            return False

    # --- Helpers ---

    def _hover_camera_and_click_action(self, camera_name: str,
                                       action_text: str):
        """Find a camera container, hover it, and click an action link.

        Uses the dropdown search field to filter to the target camera,
        then hovers the container and clicks the action (Create Zone /
        Create Line).
        """
        dropdown = self._get_dropdown_by_text("Locations")
        assert dropdown is not None, "Locations & Cameras dropdown not found"
        dropdown.click()
        self.page.wait_for_timeout(1000)

        # Type camera name in the dropdown search field to filter
        search_input = self.page.locator(".sidebarSearch input").first
        search_input.wait_for(state="visible", timeout=5000)
        search_input.fill(camera_name)
        self.page.wait_for_timeout(2000)

        # Find the matching camera container
        containers = self.camera_containers
        for i in range(containers.count()):
            container = containers.nth(i)
            if not container.is_visible():
                continue
            text = container.evaluate("el => el.textContent || ''")
            if camera_name in text:
                container.hover(force=True)
                self.page.wait_for_timeout(500)

                action_link = self.page.get_by_text(
                    action_text, exact=True
                ).first
                action_link.wait_for(state="visible", timeout=5000)
                action_link.click()
                self.page.wait_for_timeout(1000)
                return
        raise AssertionError(
            f"Camera '{camera_name}' not found in camera containers"
        )

    def _wait_for_loader_finish(self, timeout: int = 60000):
        """Wait for the CircularProgress loader to appear then disappear."""
        try:
            self.loader.first.wait_for(state="visible", timeout=5000)
        except Exception:
            pass
        try:
            self.loader.first.wait_for(state="hidden", timeout=timeout)
        except Exception:
            pass
