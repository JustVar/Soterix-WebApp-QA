"""Events Page Object Model.

Models the Events page including site/camera selection, duration filtering,
event search, pinning, review, playback, and export flows.
"""
import datetime
import json
import time

from playwright.sync_api import Error as PlaywrightError, Page, expect

from tests.shared.helpers.search_job import (
    SearchJob,
    require_finished,
    require_results,
    watch_search,
)


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
        # img asset icon: alt unreliable, locate by src (CONVENTIONS > Locators)
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
        # the loader is optional and page-global; the container wait above is
        # the arrival signal and every caller waits on its own next element
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

        # Accessible-name match: exact and escaped (option text is the
        # bare rule name, probe 09/02/2026), so 'Occupancy' can never
        # land a longer rule that merely contains it.
        option = listbox.get_by_role(
            "option", name=rule_name, exact=True
        ).first
        option.click()
        # Listbox hidden = MUI applied the selection
        listbox.wait_for(state="hidden", timeout=10000)

    def select_site(self, site_name: str | None = None):
        """Open site dropdown and select a site by name.

        MUI Select renders options as li[role='option'] MuiMenuItem elements.
        Each option has a data-value attribute with the site ID.
        Pass None to use test_site_name from config/env/.
        """
        if site_name is None:
            from config.base_config import config
            site_name = config.get("test_site_name")
            if not site_name:
                raise RuntimeError(
                    "test_site_name is not set for this ENV in config/env/. "
                    "Add it before running site-dependent tests."
                )

        self.site_dropdown.click()

        # Wait for the MUI Menu listbox to appear
        listbox = self.page.locator("[role='listbox']")
        listbox.wait_for(state="visible", timeout=20000)

        # Accessible-name match on the option (its text is the bare site
        # name, probe 09/02/2026): exact and escaped, unlike the old
        # span:has-text substring that also matched name-prefix sites.
        option = listbox.get_by_role(
            "option", name=site_name, exact=True
        ).first

        # Click the MuiMenuItem (li element) to trigger selection
        option.click()

        # Listbox hidden = MUI applied the selection
        listbox.wait_for(state="hidden", timeout=20000)

        # The combobox now shows the chosen site: that is the signal that
        # the selection reached component state and search may proceed.
        self.page.get_by_text(site_name, exact=False).first.wait_for(
            state="visible", timeout=10000
        )

    def select_camera(self, site_name: str, camera_name: str,
                      location_name: str | None = None):
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

        menu = self.page.locator("#simple-menu")
        menu.wait_for(state="visible", timeout=10000)

        # Expand the site
        # The node's own text is name+camera-count ('Newtown Action Area10',
        # probe 09/02/2026), so match the inner element that holds the exact
        # bare name - escaped, and never a substring of another site.
        site_node = menu.locator(".MuiListItemButton-root").filter(
            has=self.page.get_by_text(site_name, exact=True)).first
        site_node.click()
        self._clear_hover_tooltip()

        # Site expansion reveals the "All Cameras" node
        all_cameras = menu.get_by_text("All Cameras").first
        if self._appears(all_cameras, timeout=5000):
            all_cameras.click()
            menu.locator(".global-search-camera-container").first.wait_for(
                state="visible", timeout=10000
            )

        # Expand the location if specified
        if location_name:
            location_node = menu.get_by_text(location_name, exact=False).first
            if self._appears(location_node, timeout=3000):
                location_node.click()

        # Find and scroll to the target camera
        containers = menu.locator(".global-search-camera-container")
        for i in range(containers.count()):
            container = containers.nth(i)
            text = container.evaluate("el => el.textContent || ''")
            if camera_name in text:
                container.scroll_into_view_if_needed()
                break

        # Dismiss the menu
        self._dismiss_camera_menu()

    def _clear_hover_tooltip(self) -> None:
        """Move the pointer off the menu row just clicked and wait for its
        tooltip to go. A site row cut by CSS ('textEllipsis') opens a MUI
        tooltip with the full name on hover, and that popper sat over the
        'All Cameras' row and intercepted its click for the full 30 s
        (india, 'Example Corporate Office', 09/16/2026)."""
        self.page.mouse.move(0, 0)
        tooltip = self.page.locator("[role='tooltip']")
        try:
            tooltip.first.wait_for(state="hidden", timeout=2000)
        # why: a tooltip still up after 2 s is left to the next click to
        # report; hidden resolves at once when none ever showed
        except PlaywrightError:
            pass

    def camera_menu_counts(self, site_name: str) -> tuple[int, int]:
        """Open the Locations & Cameras menu, expand the site to its
        cameras and return (the count the site node declares, the camera
        containers listed), then dismiss the menu. The site node reads
        '<site> <count>' (measured 09/12/2026: 'Spartan0 22')."""
        self.camera_dropdown.click()
        menu = self.page.locator("#simple-menu")
        menu.wait_for(state="visible", timeout=10000)
        # exact name inside the row; the menu lists each site once, and
        # the row is what carries the count
        site_node = menu.locator(".MuiListItemButton-root").filter(
            # .first: the menu lists each site once
            has=self.page.get_by_text(site_name, exact=True)).first
        digits = [t for t in site_node.inner_text().split() if t.isdigit()]
        declared = int(digits[-1]) if digits else -1
        site_node.click()
        self._clear_hover_tooltip()
        # .first: one All Cameras group node per expanded site
        all_cameras = menu.get_by_text("All Cameras").first
        if self._appears(all_cameras, timeout=5000):
            all_cameras.click()
        containers = menu.locator(".global-search-camera-container")
        containers.first.wait_for(state="visible", timeout=10000)
        listed = containers.count()
        self._dismiss_camera_menu()
        return declared, listed

    def selector_texts(self) -> list[str]:
        """What the page's MUI selects read, left to right (All Rules,
        the site, the duration)."""
        return [" ".join(t.split()) for t in self.page.locator(".MuiSelect-select").all_inner_texts()]

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

        # The menu renders in a popover with id="simple-menu"
        menu = self.page.locator("#simple-menu")
        menu.wait_for(state="visible", timeout=10000)

        # Exact bare-name node match - see select_camera for the DOM
        # shape (probe 09/02/2026)
        site_node = menu.locator(".MuiListItemButton-root").filter(
            has=self.page.get_by_text(site_name, exact=True)).first
        site_node.click()
        self._clear_hover_tooltip()

        # Site expansion reveals the "All Cameras" node
        all_cameras = menu.get_by_text("All Cameras").first
        if self._appears(all_cameras, timeout=5000):
            all_cameras.click()

        # Verify cameras are listed
        containers = menu.locator(".global-search-camera-container")
        containers.first.wait_for(state="visible", timeout=10000)

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
            # each label is one guess at the current dropdown text; a miss
            # tries the next, and the listbox wait below raises when nothing
            # opened
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
        # Listbox hidden = MUI applied the selection
        listbox.wait_for(state="hidden", timeout=10000)

    def get_rule_options(self) -> list:
        """Open rule dropdown and return all available rule type names."""
        self.rule_dropdown.click()
        listbox = self.page.locator("[role='listbox']")
        listbox.wait_for(state="visible", timeout=10000)
        options = listbox.locator("li[role='option']")
        options.first.wait_for(state="visible", timeout=10000)
        texts = []
        for i in range(options.count()):
            txt = options.nth(i).inner_text().strip()
            if txt:
                texts.append(txt)
        self.page.keyboard.press("Escape")
        listbox.wait_for(state="hidden", timeout=5000)
        return texts

    def get_site_options(self) -> list:
        """Open site dropdown and return all available site names."""
        self.site_dropdown.click()
        listbox = self.page.locator("[role='listbox']")
        listbox.wait_for(state="visible", timeout=10000)
        options = listbox.locator("li[role='option']")
        options.first.wait_for(state="visible", timeout=10000)
        texts = []
        for i in range(options.count()):
            txt = options.nth(i).inner_text().strip()
            if txt:
                texts.append(txt)
        self.page.keyboard.press("Escape")
        listbox.wait_for(state="hidden", timeout=5000)
        return texts

    # --- Search ---
    #
    # Every search here follows the server's job (tests/shared/helpers/
    # search_job.py) rather than waiting on the first thumbnail. `timeout`
    # caps the server's work, so a search that answers in ten seconds
    # costs ten seconds, and a finished empty search reads as data, not as
    # a locator timeout.

    def search_events(self, timeout: int = 60000) -> SearchJob:
        """Click Search and return once results are on screen and settled.

        A search that completes with nothing skips with the measurements
        (the tenant holds no events for these filters); a search that never
        ran or never finished fails, naming which.
        """
        job = watch_search(self.page, self.search_button.click, timeout_ms=timeout)
        require_results(job, surface="Events search")
        self._show_results()
        return job

    def search_events_safe(self, timeout: int = 60000) -> bool:
        """Click Search; True when it returned results, False when it finished empty.

        For flows that accept an empty answer. A search that never ran or
        never finished still fails: "no crash" is not the oracle, "the
        server answered" is.
        """
        job = watch_search(self.page, self.search_button.click, timeout_ms=timeout)
        has_results = require_finished(job, surface="Events search")
        if has_results:
            self._show_results()
        return has_results

    def search_events_for_channels(self, channel_list: list[int],
                                   timeout: int = 60000) -> SearchJob:
        """Search events filtered to specific camera channels via route intercept.

        Intercepts the search API POST and replaces channelList with
        the given channel numbers before the request reaches the server.
        This bypasses the MUI camera checkbox (which has zero-dimension
        elements) while still using the UI's full search flow.

        Channel N = camera at 0-based index (N-1) in the site's
        alphabetical camera list. The mapping was captured on the tenant
        before the 2026-08 site rename; re-derive it if a channel search
        returns nothing.
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
            job = watch_search(self.page, self.search_button.click, timeout_ms=timeout)
        finally:
            self.page.unroute("**/v-apiserver/REST/site/search**")
        require_results(job, surface=f"Events search on channels {channel_list}")
        self._show_results()
        return job

    def _show_results(self) -> None:
        """After the server delivered events, wait for the grid to draw and settle."""
        # the server has delivered at least one event; the grid's first
        # thumbnail is a render away, not a network wait
        self.event_results.first.wait_for(state="visible", timeout=10000)
        self._results_settled()

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

        # Pin icon appears on hover within the overlay
        # Find pin icon within the hovered event's container, not globally
        event_container = event_img.locator("xpath=ancestor::div[1]")
        # img asset icon: alt unreliable, locate by src (CONVENTIONS > Locators)
        pin = event_container.locator("img[src*='roundPinIcon']")
        pin.wait_for(state="visible", timeout=5000)

        # The pinned counter reflects the click: wait for its text to
        # change from the pre-click baseline (it hides at zero pins).
        before = self._pinned_state()
        pin.click()
        deadline = time.monotonic() + 5.0
        while time.monotonic() < deadline:
            if self._pinned_state() != before:
                return
            self.page.wait_for_timeout(250)  # poll tick for counter update
        print(f"[EVENTS] Pin clicked but the counter still reads "
              f"'{before or 'hidden'}' after 5s")

    def get_pinned_count_text(self) -> str:
        """Return the text from the pinned clips counter."""
        return self.pinned_counter.inner_text()

    def click_review_pinned_clips(self):
        """Click the 'Review Pinned Clips' button."""
        self.review_pinned_button.wait_for(state="visible", timeout=10000)
        self.review_pinned_button.click()
        # The click opens the pinned review player; the button leaves the
        # page with the results grid.
        if not self._appears_hidden(self.review_pinned_button, timeout=10000):
            print("[EVENTS] Review Pinned Clips clicked but the button "
                  "is still visible after 10s")

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
        event_img.hover(force=True)

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
        close = self.player_close_button.first
        close.click()
        # The clicked CloseIcon leaves the DOM with the player. The
        # locator is page-global, so another visible CloseIcon (toast,
        # dialog) may keep matching: report instead of raising.
        if not self._appears_hidden(close, timeout=10000):
            print("[EVENTS] Player close clicked but a CloseIcon is "
                  "still visible after 10s")

    # --- Export ---

    def export_event(self, filename: str | None = None):
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
            self._appears_hidden(menu, timeout=3000)

        # Verify menu dismissed; if still open, force-close via JS.
        # The evaluate() removal is synchronous, so no wait follows it.
        if menu.count() > 0 and menu.is_visible():
            self.page.evaluate(
                "document.querySelector('#simple-menu')?.remove()"
            )

    @staticmethod
    def _appears(locator, timeout: int = 5000) -> bool:
        """True when the element shows within timeout, False otherwise.

        Returns as soon as the element appears; use for optional elements
        instead of a one-shot count() check after an action.
        """
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

    def _results_settled(self, timeout_s: float = 6.0):
        """Wait until the result thumbnail count stops growing.

        Results stream in after the first thumbnail renders and there is
        no completion signal in the DOM, so poll the count until it holds
        for a full second (three equal 500ms reads); a single quiet gap
        in the stream is not settled.
        """
        deadline = time.monotonic() + timeout_s
        last = -1
        stable_reads = 0
        while time.monotonic() < deadline:
            current = self.event_results.count()
            if current == last:
                stable_reads += 1
                if stable_reads >= 2:
                    return
            else:
                stable_reads = 0
            last = current
            self.page.wait_for_timeout(500)  # poll tick for streamed results

    def _pinned_state(self) -> str:
        """Return the pinned counter text, or '' while it is hidden."""
        counter = self.pinned_counter.first
        try:
            if counter.is_visible():
                return counter.inner_text().strip()
        # probe: the counter hides at zero pins and can detach mid-read;
        # '' only means "no change seen yet" to pin_event's before/after
        # poll, which re-reads on the next tick and reports if the counter
        # never moves
        except PlaywrightError:
            pass
        return ""

    def _wait_for_loader_finish(self, timeout: int = 60000):
        """Wait for the CircularProgress loader to appear then disappear."""
        try:
            # Short appear grace: burning 5s on every fast search adds up
            self.loader.first.wait_for(state="visible", timeout=2000)
        # instant responses show no loader at all; its absence is not a failure
        except Exception:
            pass
        try:
            self.loader.first.wait_for(state="hidden", timeout=timeout)
        # the loader locator is page-global and a stray spinner can stay
        # visible; callers wait on the results or player as the real signal
        except Exception:
            pass

    def is_on_event_player_page(self) -> bool:
        """Check if the inline event player is active."""
        return self.player_close_button.count() > 0 and \
            self.player_close_button.first.is_visible()
