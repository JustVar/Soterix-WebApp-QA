"""Global Search Page Object Model.

Models the Global Search page including category selection, description
filters, locations/cameras picker, duration, zone/line drawing on canvas,
search execution, and result playback.
"""
import re
import time

from playwright.sync_api import Error as PlaywrightError, Page, expect

from tests.shared.helpers.search_job import (
    SearchJob,
    require_finished,
    require_results,
    watch_search,
)


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
            # img asset icon: alt unreliable, locate by src (CONVENTIONS > Locators)
            ".search_container_search img[src*='search']"
        ).first

        # Search results
        self.result_images = page.locator(".global-imageResults")
        # img asset icon: alt unreliable, locate by src (CONVENTIONS > Locators)
        self.play_clip_icon = page.locator("img[src*='media/playClip']")
        self.replay_icon = page.locator("img[alt='Replay']")

        # Zone/Line drawing
        # No page-wide Create Zone/Line locators here: every camera
        # container holds its own always-mounted copy, so the links are
        # located inside the hovered container (_hover_camera_and_click_action)
        self.canvas = page.locator(".upper-canvas")
        self.done_button = page.locator(".save-btn")

        # Loader
        self.loader = page.locator(".MuiCircularProgress-root")

    # --- Navigation ---

    # Measured 09/12/2026 on US (register row 53): the four filter boxes
    # read '<label>\n<value>' with 'Select' before a choice; the search
    # button is an img whose file is search-disable*.svg until the
    # filters allow a search and /icons/search_icon.svg after.
    FILTER_LABELS = ("Category", "Description", "Locations & Cameras", "Duration")
    SEARCH_DISABLED_ICON = "search-disable"
    SEARCH_ENABLED_ICON = "search_icon"

    def filter_values(self) -> dict:
        """The filter boxes as {label: value}; a box with no choice reads 'Select'."""
        out = {}
        for text in self.filter_dropdowns.all_inner_texts():
            lines = [x.strip() for x in text.split("\n") if x.strip()]
            if lines:
                out[lines[0]] = " ".join(lines[1:])
        return out

    def search_icon_name(self) -> str:
        """The search button's icon file, minus its path and hash."""
        src = self.search_button.get_attribute("src") or ""
        return src.rsplit("/", 1)[-1].split(".")[0]

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
        # the category label above is the loaded signal; a lingering
        # spinner is only a settle before the filter waits
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
        """Click a dropdown and select an item by index.

        The item's own visible wait is the opened signal. The applied
        signal is the dropdown's value text leaving 'Select' (the
        control renders 'CategorySelect' until a pick lands, then
        'CategoryEvent'); an item click during the list's open
        animation is silently dropped, so one retry click self-heals.
        """
        dropdown.click()
        item = self.dropdown_items.nth(item_index)
        item.wait_for(state="visible", timeout=10000)
        item.click()
        self._dropdown_applied(dropdown, item)

    def _select_dropdown_item_by_text(self, dropdown, text: str):
        """Click a dropdown and select an item by text (same signals
        as the index variant)."""
        dropdown.click()
        # Exact and escaped (item 20): .dropdownItem holds the bare item
        # text (probe 09/02/2026 on the same component in insights), and
        # the page renders items of several dropdowns at once, so a
        # substring could land in the wrong dropdown.
        item = self.page.get_by_text(text, exact=True).and_(
            self.page.locator(".dropdownItem")).first
        item.wait_for(state="visible", timeout=10000)
        item.click()
        self._dropdown_applied(dropdown, item)

    def _dropdown_applied(self, dropdown, item):
        """The pick applies at once: the value text flips off 'Select'
        and the item unmounts on the same tick (measured 08/14/2026 on
        Category and Duration). The retrying expect just absorbs any
        render lag."""
        expect(dropdown).not_to_contain_text("Select", timeout=10000)

    def _get_dropdown_options(self, label_text: str) -> list:
        """Open a dropdown by label, read all item texts, then close it."""
        dropdown = self._get_dropdown_by_text(label_text)
        if dropdown is None:
            return []
        dropdown.click()
        # the first item rendering is the opened signal; a miss reads
        # an empty list, which callers treat as no options
        items = self.dropdown_items
        self._appears(items.first, timeout=10000)
        texts = [t.strip() for t in items.all_inner_texts() if t.strip()]

        # the list leaving is the closed signal
        self.page.keyboard.press("Escape")
        self._appears_hidden(items.first, timeout=5000)
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

    # --- Search execution ---
    #
    # Every search here follows the server's job (tests/shared/helpers/
    # search_job.py) rather than waiting on the first thumbnail. `timeout`
    # caps the server's work, so a search that answers in ten seconds
    # costs ten seconds, and a finished empty search reads as data, not as
    # a locator timeout. Every category (Event, Vehicle, Line, Zone) runs
    # the same job, measured 09/08/2026.

    def execute_search(self, timeout: int = 60000) -> SearchJob:
        """Click Search and return once results are on screen and settled.

        A search that completes with nothing skips with the measurements
        (the tenant holds nothing for these filters); a search that never
        ran or never finished fails, naming which.
        """
        job = watch_search(self.page, self.search_button.click, timeout_ms=timeout)
        require_results(job, surface="Search")
        self._show_results()
        return job

    def execute_search_safe(self, timeout: int = 60000) -> bool:
        """Click Search; True when it returned results, False when it finished empty.

        For flows that accept an empty answer. A search that never ran or
        never finished still fails: "no crash" is not the oracle, "the
        server answered" is.
        """
        job = watch_search(self.page, self.search_button.click, timeout_ms=timeout)
        has_results = require_finished(job, surface="Search")
        if has_results:
            self._show_results()
        return has_results

    def execute_search_dispatched(self, timeout: int = 60000) -> bool:
        """Click Search on a view that already shows results; prove it re-ran.

        Stale thumbnails satisfy a visibility wait instantly, so only the
        outgoing job proves the click did anything. Raises RuntimeError when
        no job leaves within 15 s. KNOWN APP BEHAVIOR: a search only re-runs
        after filters change; an unchanged or partially re-set view ignores
        the click by design (see TEST_REPAIRS.md). Prefer a fresh view with
        all filters re-applied; use this when a test genuinely needs to
        prove a warm re-search dispatched. Returns False when the search
        ran and finished empty.
        """
        job = watch_search(self.page, self.search_button.click, timeout_ms=timeout)
        if job.outcome == "no_request":
            raise RuntimeError(
                "Search click dispatched no request within 15s. The app "
                "re-runs a search only after filters change; re-apply "
                "the filters or start from a fresh view."
            )
        has_results = require_finished(job, surface="Search (re-run)")
        if has_results:
            self._show_results()
        return has_results

    def _show_results(self) -> None:
        """After the server delivered results, wait for the grid to draw and settle."""
        # the server has delivered at least one result; the grid's first
        # card is a render away, not a network wait
        self.result_images.first.wait_for(state="visible", timeout=10000)
        self._results_settled()

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

        # the gender container rendering is the opened signal
        self.gender_container.wait_for(state="visible", timeout=10000)
        # Whole-word match: 'Male' must not pass on 'Female' (zero-width
        # spaces tolerated, CONVENTIONS > Locators)
        exact = re.compile(rf"^[\s\u200b]*{re.escape(gender)}[\s\u200b]*$")
        gender_option = self.gender_container.locator("p").filter(has_text=exact).first
        gender_option.click()
        # The picked option gains selectedTab on the same tick (probe
        # 08/25/2026); a click during the panel's open animation can
        # drop, so one retry click self-heals before the wait raises
        picked = self.gender_container.locator("p.selectedTab").filter(has_text=exact)
        if not self._appears(picked, timeout=3000):
            gender_option.click()
            picked.wait_for(state="visible", timeout=5000)

    def _open_section(self, label: str):
        """Open a search sidebar section by clicking its value control.

        The 2026-08 search page renders each filter as a
        p.select-box-headings label with a div.select-box-sub-heading
        value control next to it. Clicking the label does nothing; the
        value control opens the panel (probe 08/09/2026).
        """
        heading = self.page.locator(
            f"p.select-box-headings:has-text('{label}')"
        ).first
        heading.wait_for(state="visible", timeout=10000)
        # No structural fallback: a grandparent-wide .first would open
        # the WRONG section under exactly the DOM drift that makes the
        # sibling lookup miss, and a wrong filter is worse than a loud
        # failure here
        value = heading.locator(
            "xpath=following-sibling::div"
            "[contains(@class,'select-box-sub-heading')]"
        ).first
        value.click()
        return value

    def select_locations_cameras(self, site_name: str | None = None):
        """Open the Locations & Cameras panel, pick a site, and select
        all cameras via the 'All Cameras' checkbox.

        The 'All Cameras' checkbox has zero-dimension elements (same MUI
        bug as Events page), so a JS input.click() toggles it. Pass None
        to use the configured test site (first row as fallback).
        """
        self._open_section("Locations & Cameras")

        panel = self.page.locator(
            ".scrollBarCustom, [class*='drop-down']"
        ).first
        panel.wait_for(state="visible", timeout=10000)
        rows = panel.locator(".MuiListItemButton-root")
        rows.first.wait_for(state="visible", timeout=10000)

        if site_name is None:
            from config.base_config import config
            site_name = config.get("test_site_name")
            if not site_name:
                raise RuntimeError(
                    "test_site_name is not set for this ENV in "
                    "config/env/. Add it before running search tests."
                )

        # Fail fast on a missing site instead of silently picking the
        # first row: the tenant renames sites, and a wrong-site search
        # passes on wrong data or fails with no hint of the cause
        # Exact inner-element match (item 20): has_text was a substring,
        # so a site name that prefixes another could land the wrong row.
        # A 0-match still fails loud below with the on-screen names.
        site_row = rows.filter(
            has=self.page.get_by_text(site_name, exact=True)).first
        try:
            site_row.wait_for(state="visible", timeout=10000)
        except PlaywrightError:
            visible = [t.strip()[:40] for t in rows.all_inner_texts()][:8]
            raise RuntimeError(
                f"Site '{site_name}' is not in the Locations panel. "
                f"On-screen entries: {visible}. The tenant may have "
                f"renamed the site: update test_site_name in config/env/."
            ) from None
        site_row.click()

        # Site expansion reveals the 'All Cameras' row
        all_row = panel.locator(
            ".MuiListItemButton-root:has-text('All Cameras')"
        ).first
        all_row.wait_for(state="visible", timeout=10000)

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

        # Dismiss by clicking the value control again, then verify the
        # section no longer reads 'Select'. This RAISES: a selection
        # that did not apply makes every later assertion meaningless.
        self._open_section("Locations & Cameras")
        try:
            expect(
                self.page.locator(
                    "p.select-box-headings:has-text('Locations')"
                ).first.locator(
                    "xpath=following-sibling::div"
                    "[contains(@class,'select-box-sub-heading')]"
                ).first
            ).not_to_have_text("Select", timeout=5000)
        except AssertionError:
            raise RuntimeError(
                "Locations & Cameras still reads 'Select' after the "
                "selection flow: the selection did not apply."
            ) from None

    def select_duration(self, duration_text: str = "Today"):
        """Select a duration from the Duration dropdown."""
        self._open_section("Duration")
        option = self.page.locator(
            f".dropdownItem:text-is('{duration_text}')"
        ).first
        option.wait_for(state="visible", timeout=10000)
        option.click()
        self._dropdown_closed(option)

    def select_duration_by_index(self, index: int = 4):
        """Select a duration by option index.

        Current option order (probe 08/09/2026): 0=Last 1 Hour,
        1=Last 2 Hours, 2=Today, 3=Yesterday, 4=Last 7 Days,
        5=Last 30 Days, 6=Custom.
        """
        self._open_section("Duration")
        options = self.page.locator(".dropdownItem")
        options.first.wait_for(state="visible", timeout=10000)
        option = options.nth(index)
        option.click()
        self._dropdown_closed(option)

    def _dropdown_closed(self, option) -> None:
        """Wait for a clicked dropdownItem to leave with its list."""
        try:
            option.wait_for(state="hidden", timeout=5000)
        except PlaywrightError:
            print("[SEARCH] Dropdown option list still open 5s after "
                  "selection")

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
            # canvas vertex pacing: the fabric canvas registers points
            # from discrete clicks with no DOM signal between them
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
        self.page.wait_for_timeout(300)  # canvas vertex pacing, no DOM signal
        self.page.mouse.click(cx + w, cy + h)
        self.page.wait_for_timeout(300)  # canvas vertex pacing, no DOM signal

    def click_done(self):
        """Click the Done/Save button after drawing a zone or line."""
        self.done_button.wait_for(state="visible", timeout=10000)
        # Check if button is disabled (cursor: not-allowed)
        style = self.done_button.get_attribute("style") or ""
        if "not-allowed" in style:
            # Retry drawing with smaller offsets
            self.draw_zone()
        self.done_button.click()
        # the Done control leaving is the drawing-committed signal
        self._appears_hidden(self.done_button, timeout=10000)

    # --- Search execution ---

    def _results_settled(self, timeout_s: float = 8.0):
        """Wait for the result grid to hold still for two seconds.

        Results stream in from the async search job, so the first
        image is not the whole set, and the grid reflows as cards
        land - a hover on nth(0) mid-stream loses the play overlay
        (measured 08/14/2026: play tests failed with a one-second
        window and passed with the old two-second settle). Two
        seconds of unchanged count is the settled signal, and it
        never returns sooner than the old fixed settle did.
        """
        deadline = time.monotonic() + timeout_s
        last = -1
        stable = 0
        while time.monotonic() < deadline:
            current = self.result_images.count()
            stable = stable + 1 if current == last else 0
            if stable >= 8:
                return
            last = current
            self.page.wait_for_timeout(250)  # poll tick for result stream

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

        # the hover-rendered play icon's own wait is the signal
        play = self.play_clip_icon.first
        play.wait_for(state="visible", timeout=10000)
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
        # Open the panel via its value control (the old label click
        # went dead with the 2026-08 sidebar, same as the filters)
        self._open_section("Locations")
        panel = self.page.locator(
            ".scrollBarCustom, [class*='drop-down']"
        ).first
        panel.wait_for(state="visible", timeout=10000)

        # Camera containers render only after expanding the site and
        # its All Cameras node (probe 08/09/2026); the search filter
        # alone does not reveal them
        rows = panel.locator(".MuiListItemButton-root")
        rows.first.wait_for(state="visible", timeout=10000)
        from config.base_config import config
        site = config.get("test_site_name")
        # Fail fast on a missing site: silently drawing on the first
        # row's cameras would test the wrong site without a trace.
        # Exact inner-element match (item 20): has_text was a substring,
        # so a site name that prefixes another could land the wrong row.
        site_row = rows.filter(
            has=self.page.get_by_text(site, exact=True)).first
        try:
            site_row.wait_for(state="visible", timeout=10000)
        except PlaywrightError:
            visible = [t.strip()[:40] for t in rows.all_inner_texts()][:8]
            raise RuntimeError(
                f"Site '{site}' is not in the Locations panel. "
                f"On-screen entries: {visible}. Update test_site_name "
                f"in config/env/ if the tenant renamed it."
            ) from None
        site_row.click()
        all_row = panel.locator(
            ".MuiListItemButton-root:has-text('All Cameras')"
        ).first
        all_row.wait_for(state="visible", timeout=10000)
        all_row.click()
        self.camera_containers.first.wait_for(state="visible", timeout=10000)

        # Find the matching camera container
        containers = self.camera_containers
        for i in range(containers.count()):
            container = containers.nth(i)
            if not container.is_visible():
                continue
            text = container.evaluate("el => el.textContent || ''")
            if camera_name in text:
                # Scope to the hovered container: every container has
                # its own always-mounted copy of the action link, so a
                # page-wide .first grabs another container's hidden one
                action_link = container.get_by_text(
                    action_text, exact=True
                ).first
                # the panel scrolls: a container below its fold (the 17th
                # on the box, 09/12/2026) never reveals its action link
                # under a forced hover, so bring it into view first. The
                # reveal is hover-driven and the containers repaint with
                # their snapshots, so one hover can land between paints
                # and reveal nothing (india, the 7th container, two of
                # three nights 09/12-09/14): leave, come back, up to
                # three times, then fail naming the container
                for _ in range(3):
                    container.scroll_into_view_if_needed()
                    container.hover(force=True)
                    if self._appears(action_link, timeout=5000):
                        action_link.click()
                        # The drawing canvas opening is the caller's wait
                        return
                    self.page.mouse.move(0, 0)
                raise AssertionError(
                    f"Hovering camera container {i} of {containers.count()} "
                    f"('{camera_name}') revealed no '{action_text}' link "
                    f"in three attempts"
                )
        raise AssertionError(
            f"Camera '{camera_name}' not found in camera containers"
        )

    @staticmethod
    def _appears(locator, timeout: int = 5000) -> bool:
        """True when the element shows within timeout, False otherwise."""
        try:
            locator.wait_for(state="visible", timeout=timeout)
            return True
        except PlaywrightError:
            return False

    @staticmethod
    def _appears_hidden(locator, timeout: int = 5000) -> bool:
        """True when the element hides within timeout, False otherwise."""
        try:
            locator.wait_for(state="hidden", timeout=timeout)
            return True
        except PlaywrightError:
            return False

    def _wait_for_loader_finish(self, timeout: int = 60000):
        """Wait for the CircularProgress loader to appear then disappear."""
        try:
            self.loader.first.wait_for(state="visible", timeout=5000)
        # the loader may never show on a fast load; the caller's canvas
        # or replay wait is the oracle
        except Exception:
            pass
        try:
            self.loader.first.wait_for(state="hidden", timeout=timeout)
        # a lingering spinner is a settle; callers wait on the canvas or
        # assert the replay icon
        except Exception:
            pass
