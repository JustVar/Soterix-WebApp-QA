"""Maps Page Object Model.

Models the standalone Maps page (sidebar nav link), including site selection,
map card grid, camera overlay, and online camera playback.
"""
import re

from playwright.sync_api import Error as PlaywrightError, Page, expect


class MapsPage:
    """Page object for the Maps page."""

    def __init__(self, page: Page):
        self.page = page

        # Navigation
        self.maps_nav_link = page.locator("a[href*='maps']")

        # Site dropdown
        self.site_dropdown = page.locator(".dropdown-box")
        self.dropdown_text = page.locator(".dropdown_text")
        self.dropdown_options = page.locator(".optionsdataDiv")
        self.site_option_rows = self.dropdown_options.locator(".option-container")

        # Map cards grid
        self.map_cards = page.locator(".grid-cards")

        # Device count inside a map card
        self.device_count_elements = page.locator(".icon-text-aligner, .icon-text-alinger")

        # Camera icons on opened map
        self.camera_icons = page.locator("img[src*='media/cameraIcon']")
        # img asset icon: alt unreliable, locate by src (CONVENTIONS > Locators)
        self.online_camera_icons = page.locator("img[src*='media/cameraIconGreen']")

        # Loader
        self.loader = page.locator(".MuiCircularProgress-root")

        # Stream failure
        self.stream_failed_text = page.locator("text=failed to load")

    # --- Navigation ---

    def navigate(self):
        """Navigate to the Maps page via sidebar nav link."""
        self.maps_nav_link.click()
        self._wait_for_dropdown_loaded()

    # A site name: anything holding a character that is not the
    # dropdown's own "...sites" loading text.
    # The flag goes in the compile call, never inline: the pattern is
    # handed to the browser as a JavaScript regex, which has no (?i).
    SITE_TITLE_RE = re.compile(r"^(?!.*sites).*\S.*$", re.IGNORECASE)

    def _wait_for_dropdown_loaded(self):
        """Wait for the page to name the site it opened on.

        The title is EMPTY for the first instants and the app writes its
        default about 0.3 s later (measured on india, 09/15/2026). The
        old wait only refused the "...sites" loading text, which an empty
        title already satisfies, so a test could pick a site inside that
        window and the app's own default would overwrite the pick a
        moment later: the maps site test then read the default and failed
        naming it. Requiring a real name closes the window.
        """
        self.dropdown_text.wait_for(state="visible", timeout=15000)
        expect(self.dropdown_text).to_have_attribute(
            "title", self.SITE_TITLE_RE, timeout=60000
        )

    # --- Site selection ---

    # An option row is .option-container holding the name in
    # .option-text-space and the site's map count in .option-box-counter
    # (probed 09/15/2026). The row is what takes the click.
    SITE_OPTION_ROW = ".option-container"
    SITE_OPTION_NAME = ".option-text-space"
    # A long name is cut in the DOM itself, not by CSS: the option reads
    # 'Example Corporat...', so the full name is nowhere in the row
    # and an exact-text match cannot reach it.
    ELLIPSIS_RE = re.compile(r"(\.\.\.|\u2026)$")

    def site_option_names(self) -> list[str]:
        """Each option row's name as the row shows it, truncation included."""
        return [" ".join(t.split())
                for t in self.site_option_rows.locator(self.SITE_OPTION_NAME).all_inner_texts()]

    def _site_option_index(self, site_name: str):
        """The row for this site, or None. A truncated row matches when
        the name it shows is the head of the one asked for; an ambiguous
        head (two sites sharing it) matches nothing, so the caller
        reports the drift rather than picking the wrong site."""
        hits = []
        for i, shown in enumerate(self.site_option_names()):
            if shown == site_name:
                return i
            head = self.ELLIPSIS_RE.sub("", shown)
            if head and self.ELLIPSIS_RE.search(shown) and site_name.startswith(head):
                hits.append(i)
        return hits[0] if len(hits) == 1 else None


    def select_site(self, site_name: str):
        """Open dropdown and select a site by name.

        Raises listing the sites that ARE offered when the named one is
        missing. The shared tenant renames sites under the tests, and
        the old callers turned that into "No sites available in
        dropdown" - a skip that read the same as a broken page
        (register item 25).
        """
        # the page's own default has to land first, or it overwrites
        # this pick (see _wait_for_dropdown_loaded)
        self._wait_for_dropdown_loaded()
        self.site_dropdown.click()

        # the options container's own wait is the opened signal
        self.dropdown_options.wait_for(state="visible", timeout=10000)
        # Exact and escaped (item 19): each option's text-space div holds
        # the bare site name (probe 09/02/2026); the old text= engine was
        # a case-insensitive substring. Strictness kept - no .first.
        index = self._site_option_index(site_name)
        if index is None:
            offered = self.list_site_options()
            detail = offered or (
                "none - the dropdown rendered empty, which is a broken "
                "page, not a data gap"
            )
            raise AssertionError(
                "The configured site " + repr(site_name) + " is not in the "
                "Maps site dropdown. Sites offered: " + str(detail) + ". "
                "Update test_site_name in config/env/ to match."
            )
        site_option = self.site_option_rows.nth(index)
        site_option.scroll_into_view_if_needed()
        site_option.click()

        # The dropdown's own title is the app's commit signal. A card
        # being visible is not: the grid still holds the last site's
        # cards, so the old wait passed at once and a read of the title
        # could still return the site that was selected before (india,
        # 09/15/2026). Wait for the title, then for a card.
        expect(self.dropdown_text).to_have_attribute(
            "title", site_name, timeout=15000)
        self.map_cards.first.wait_for(state="visible", timeout=60000)

    def list_site_options(self) -> list:
        """Site names in the ALREADY OPEN dropdown, for a failure message.

        The rows' own names: the old reader walked every p, div and span
        and returned the count badges beside the names ('Newtown Action
        Area', '10', 'Example Corporat...', '1'), which read as
        sites that do not exist.
        """
        return self.site_option_names()

    def get_site_options(self) -> list:
        """Open dropdown and return available site names."""
        self.site_dropdown.click()

        # the options container's own wait is the opened signal
        self.dropdown_options.wait_for(state="visible", timeout=10000)
        options = self.dropdown_options.locator("p, div, span")
        texts = []
        for i in range(options.count()):
            # inner_text() may include count badges after a newline (e.g. "Site Name\n0")
            text = options.nth(i).inner_text().strip().split('\n')[0].strip()
            if text and text not in texts:
                texts.append(text)

        # Close by toggling the dropdown (Escape may navigate away in
        # some SPAs); the options leaving is the closed signal
        self.site_dropdown.click()
        try:
            self.dropdown_options.wait_for(state="hidden", timeout=5000)
        # a lingering list is harmless here - the texts are already read
        except PlaywrightError:
            pass
        return texts

    def get_selected_site_text(self) -> str:
        """Return the currently selected site name from the dropdown."""
        return (self.dropdown_text.get_attribute("title") or "").strip()

    # --- Map cards ---

    def get_map_card_count(self) -> int:
        """Return the number of map cards displayed."""
        return self.map_cards.count()

    def find_map_with_cameras(self):
        """Find and return the first map card that has cameras (device count > 0).

        Returns the card locator, or None if no map has cameras.
        """
        card_count = self.map_cards.count()
        for i in range(card_count):
            card = self.map_cards.nth(i)
            device_elements = card.locator(".icon-text-aligner div, .icon-text-alinger div")
            # The second div inside icon-text-aligner contains the count
            if device_elements.count() >= 2:
                count_text = device_elements.nth(1).inner_text().strip()
                if count_text != "0":
                    return card
        return None

    # --- Map interaction ---

    def open_map(self, map_card):
        """Click a map card to open it and wait for camera icons to appear."""
        map_card.click()
        # the first camera icon is the opened signal
        self.camera_icons.first.wait_for(state="visible", timeout=60000)

    def get_online_camera_count(self) -> int:
        """Return the number of online (green) camera icons on the open map."""
        return self.online_camera_icons.count()

    def play_camera(self, index: int = 0):
        """Click an online camera icon to play its stream."""
        self.online_camera_icons.nth(index).click()
        self._wait_for_loader_finish()

    def _wait_for_loader_finish(self):
        """Wait for CircularProgress loader to appear and disappear."""
        try:
            if self.loader.count() > 0 and self.loader.first.is_visible():
                self.loader.first.wait_for(state="hidden", timeout=60000)
        except PlaywrightError:
            raise AssertionError(
                "Map camera stream loader still visible 60s after clicking "
                "the camera icon: the stream never started"
            ) from None
        # a stream that starts has no DOM signal past the loader
        # leaving (the player renders before the frames arrive); the
        # settle lets a failed-to-load overlay appear before callers
        # read is_stream_failed
        self.page.wait_for_timeout(2000)

    def is_stream_failed(self) -> bool:
        """Check if stream shows a 'failed to load' message."""
        return self.stream_failed_text.count() > 0
