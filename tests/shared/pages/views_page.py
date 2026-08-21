"""Views Page Object Model for video wall and camera views."""
import time

from playwright.sync_api import Error as PlaywrightError, Page, expect


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
        
        # Locators - Full Screen
        self.fullscreen_buttons = page.locator("img[src*='media/Zoom.']")

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

    def _appears(self, locator, timeout: int = 3000) -> bool:
        """Wait up to `timeout` ms for a locator to become visible.

        Returns True once visible, False on timeout. Use for optional
        elements: returns as soon as the element shows instead of always
        sleeping the full duration.
        """
        try:
            locator.first.wait_for(state="visible", timeout=timeout)
            return True
        except Exception:
            return False

    def _tile_count_changed(self, before: int, action: str,
                            timeout_s: float = 10.0,
                            extra_signal=None) -> bool:
        """Wait for the empty-tile count to move off a pre-action baseline.

        Dropping content consumes a tile; loading a saved view redraws
        the grid. Both change the count of 'Drag & Drop' placeholders.
        Some outcomes never move the count (a drop can land a stream
        the count misses; a dropped view can open as its own tab), so
        extra_signal lets a caller poll a second success sign alongside
        the count.

        Returns True as soon as either signal lands; logs and returns
        False on timeout so the caller owns the verdict.
        """
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            if self.drag_drop_tiles.count() != before:
                return True
            if extra_signal is not None and extra_signal():
                return True
            self.page.wait_for_timeout(250)  # poll tick for tile change
        print(f"[VIEWS] {action} finished but the empty-tile count "
              f"stayed at {before} for {timeout_s:.0f}s")
        return False

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
            # accept() raises only if another listener already handled
            # this dialog or the page is gone; either way the dialog no
            # longer blocks the test, and playwright-python would
            # otherwise re-raise the listener error at the test's next
            # unrelated API call, blaming the wrong step
            except Exception:
                pass

        # Register the dialog handler
        self.page.on("dialog", _accept)

    def mouse_drag(self, source, target, steps: int = 12):
        """Drag source onto target with a stepped manual mouse gesture.

        drag_to jumps the pointer to the target in one move, which the
        app's drag layer reads as nothing at all - observed live, the
        press-move only text-selects the source label. The intermediate
        move events are the signal the drag layer needs to recognize a
        drag in progress.

        The app wires HTML5 drag onto specific elements (draggable="true"
        - camera wrappers, site rows, and an unclassed div four levels
        above a saved view's name span). Pressing anywhere else - the
        name label a caller naturally locates by - starts a text
        selection instead of a drag, so the grip is re-aimed at the
        nearest draggable ancestor when one exists.

        While the pointer dwells over the target, one frame is stashed
        on page._drag_captures; the report_media plugin files it with
        the test's evidence as <test>__<suffix>__mid-drag-<n>.png.
        """
        handle = source.locator(
            "xpath=ancestor-or-self::*[@draggable='true'][1]"
        )
        # grip decision, not an oracle: no draggable ancestor means the
        # app never wired drag here - keep the caller's element and let
        # the ladder's landed-check decide the outcome
        if handle.count():
            source = handle.first
        source.hover()
        self.page.mouse.down()
        try:
            src_box = source.bounding_box()
            tgt_box = target.bounding_box()
            if src_box is None or tgt_box is None:
                missing = "source" if src_box is None else "target"
                raise RuntimeError(
                    f"mouse_drag: the {missing} element has no bounding "
                    "box (hidden or detached), so the drag cannot be aimed"
                )
            self.page.mouse.move(
                tgt_box["x"] + tgt_box["width"] / 2,
                tgt_box["y"] + tgt_box["height"] / 2,
                steps=steps,
            )
            # dwell over the target so its dragover state registers
            # before the release
            self.page.wait_for_timeout(200)
            # This dwell is the only moment the drag is visibly in
            # flight: pointer down, the target's dragover styling
            # applied, and any caller-drawn outlines (the subtabs
            # tests' red source / green target borders) still on
            # screen. The end-of-test screenshot can never show that
            # state, so stash one frame here for report_media to file
            # with the test's evidence.
            try:
                stash = getattr(self.page, "_drag_captures", None)
                if stash is None:
                    stash = []
                    self.page._drag_captures = stash
                # timeout=3000: a wedged capture must not stretch the
                # dwell by the 30s screenshot default while the mouse
                # button is still down
                stash.append(("mid-drag",
                              self.page.screenshot(timeout=3000)))
            # capture is evidence, not testing: a failed screenshot is
            # logged but must not disturb the drag or the release in
            # the finally
            except Exception as e:  # noqa: BLE001
                print(f"[VIEWS] mid-drag capture failed: {e}")
        finally:
            # the button must never stay pressed into the next action
            # on the shared page
            self.page.mouse.up()

    def drag_camera_to_tile(self, camera_locator, tile_index: int = 0):
        """Drag a camera thumbnail to a specific tile.

        Native mouse drag first; a drag that raises or consumes no
        tile falls back to the JS DataTransfer simulation. A stalled
        tile count is logged, never raised - some drops land streams
        without changing the counted tiles, so callers keep the
        verdict with their own oracles. Only a fallback that cannot
        even dispatch raises.
        """
        target_tile = self.drag_drop_tiles.nth(tile_index)
        before_tiles = self.drag_drop_tiles.count()
        try:
            self.mouse_drag(camera_locator, target_tile)
            # A successful drop consumes the empty tile
            landed = self._tile_count_changed(before_tiles, "camera drag")
        # RuntimeError is mouse_drag's no-bounding-box failure; the
        # geometry-free JS simulation still works there
        except (RuntimeError, PlaywrightError):
            landed = False
        if not landed:
            print("[VIEWS] camera drag: mouse drag did not consume a tile; "
                  "trying JS DataTransfer fallback")
            # the JS simulation finds the camera by its visible name
            camera_name = camera_locator.inner_text().split("\n")[0]
            self._simulate_camera_drag_via_js(camera_name, tile_index)

    def add_camera_via_checkbox(self, camera_name: str):
        """Select a camera by revealing its checkbox and clicking it.

        Args:
            camera_name: The visible name of the camera to select.
        """
        # Find the camera thumbnail by its visible name
        camera = self.page.locator(f".cameraThumbnailWrapper:has-text('{camera_name}')").first

        # Hover to reveal the checkbox. The reveal is flaky (React listens
        # on a parent the pointer sometimes misses), so retry once with a
        # pointer jiggle instead of letting the click hang its full timeout.
        camera.hover()
        checkbox = camera.locator(".sidebar-custom-checkbox")
        try:
            checkbox.wait_for(state="visible", timeout=5000)
        except Exception:
            self.page.mouse.move(0, 0)
            camera.hover()
            checkbox.wait_for(state="visible", timeout=10000)

        # Adding a camera consumes an empty tile - wait for that instead of
        # sleeping, so a save that follows cannot race the add. Logged (not
        # raised) on timeout: callers assert the outcome themselves and a
        # camera-add that renders without consuming a tile should not fail
        # here, but a silent swallow would hide the race this wait exists
        # to close.
        before_tiles = self.drag_drop_tiles.count()
        # JS-click fallback on the inner input: camera rows re-render
        # with their snapshot refresh, so a pointer click can churn on
        # the stability check until it times out (the same class the
        # LPR panel checkbox hit); MUI handles the change on the input
        try:
            checkbox.click(timeout=5000)
        except PlaywrightError:
            # no inner input on this custom checkbox - JS-click the
            # element itself
            checkbox.first.evaluate("el => el.click()")
        if before_tiles > 0:
            try:
                expect(self.drag_drop_tiles).not_to_have_count(before_tiles, timeout=10000)
            except AssertionError:
                print("[VIEWS] Camera checkbox clicked but no tile was "
                      f"consumed within 10s (still {before_tiles} empty)")

    def add_first_camera_via_checkbox(self, camera_name: str = None):
        """Select a camera by revealing its checkbox and clicking it.

        Args:
            camera_name: Specific camera name to select. If None, uses configured test_camera_name or first camera.
        """
        # Use configured camera name if not specified
        if camera_name is None:
            from config.base_config import config
            camera_name = config.get("test_camera_name")

        # Find camera thumbnail
        camera_count = self.page.locator(".cameraThumbnailWrapper").count()
        print(f"DEBUG add_first_camera_via_checkbox: Found {camera_count} camera(s), looking for: {camera_name}")

        if camera_count == 0:
            raise RuntimeError("No cameras found in sidebar. User may not have access to any sites.")

        # Try to find camera by name if specified
        camera = None
        available_cameras = []
        if camera_name:
            # Search for camera with matching text
            cameras = self.page.locator(".cameraThumbnailWrapper")
            for i in range(camera_count):
                cam = cameras.nth(i)
                cam_text = cam.inner_text().strip()
                available_cameras.append(cam_text)
                if camera_name.lower() in cam_text.lower():
                    camera = cam
                    print(f"DEBUG add_first_camera_via_checkbox: Found camera by name: {camera_name}")
                    break

        # Print available cameras for debugging
        if available_cameras:
            print(f"DEBUG add_first_camera_via_checkbox: Available cameras: {available_cameras}")

        # Fallback to first camera if not found by name
        if camera is None:
            print(f"DEBUG add_first_camera_via_checkbox: Camera '{camera_name}' not found, using first camera")
            camera = self.page.locator(".cameraThumbnailWrapper").first

        # Hover to reveal the checkbox. The reveal is flaky (React listens
        # on a parent the pointer sometimes misses), so retry once with a
        # pointer jiggle instead of letting the click hang its full timeout.
        camera.hover()
        checkbox = camera.locator(".sidebar-custom-checkbox")
        try:
            checkbox.wait_for(state="visible", timeout=5000)
        except Exception:
            self.page.mouse.move(0, 0)
            camera.hover()
            checkbox.wait_for(state="visible", timeout=10000)

        # Adding a camera consumes an empty tile - wait for that instead of
        # sleeping, so a save that follows cannot race the add. Logged (not
        # raised) on timeout: callers assert the outcome themselves and a
        # camera-add that renders without consuming a tile should not fail
        # here, but a silent swallow would hide the race this wait exists
        # to close.
        before_tiles = self.drag_drop_tiles.count()
        # JS-click fallback on the inner input: camera rows re-render
        # with their snapshot refresh, so a pointer click can churn on
        # the stability check until it times out (the same class the
        # LPR panel checkbox hit); MUI handles the change on the input
        try:
            checkbox.click(timeout=5000)
        except PlaywrightError:
            # no inner input on this custom checkbox - JS-click the
            # element itself
            checkbox.first.evaluate("el => el.click()")
        if before_tiles > 0:
            try:
                expect(self.drag_drop_tiles).not_to_have_count(before_tiles, timeout=10000)
            except AssertionError:
                print("[VIEWS] Camera checkbox clicked but no tile was "
                      f"consumed within 10s (still {before_tiles} empty)")

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
        # Open My Views panel if not already open; the view-span wait
        # below is the panel-open signal
        my_views_btn = self.page.locator("img[src*='myviews']")
        my_views_btn.click()

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

        # Click checkbox to open the view; loading the view changes the
        # number of empty tiles, which is the applied signal
        before_tiles = self.drag_drop_tiles.count()
        checkbox = self.page.locator(".sidebar-custom-checkbox").first
        checkbox.click()
        self._tile_count_changed(before_tiles, "open saved view")

    def save_current_view(self):
        """Click the save view button."""
        self.save_view_button.click()

    def navigate(self):
        """Navigate to the Views page with verification.

        Clicks the Views nav link and verifies the page loaded by checking
        for the add tab button. Uses force=True to bypass any overlays.
        Tests should start within 2 seconds after page elements are loaded.
        """
        max_attempts = 2
        for attempt in range(max_attempts):
            try:
                # Wait for the Views nav item to be visible
                nav = self.page.locator("text=Views").first
                nav.wait_for(state="visible", timeout=10000)

                # Click with force=True to bypass any overlays
                nav.click(force=True)

                # Verify we're on the Views page - this is the key element
                self.add_tab_button.wait_for(state="visible", timeout=15000)
                return  # Success
            except Exception as e:
                if attempt < max_attempts - 1:
                    # Retry: refresh and try again (the nav wait at the top of
                    # the loop absorbs the reload time)
                    self.page.reload()
                else:
                    raise RuntimeError(f"Failed to navigate to Views page after {max_attempts} attempts: {e}")

    def wait_for_page_load(self, timeout: int = 5000):
        """Wait for the Views page to finish loading.

        Only waits if loader is actually visible. Quick check - doesn't block.
        """
        try:
            if self.loader.count() > 0 and self.loader.first.is_visible():
                self.loader.wait_for(state="hidden", timeout=timeout)
        # quick settle only: tile placeholder spinners can stay alive;
        # every caller waits on its own next element
        except Exception:
            pass  # Loader may not exist or may have already hidden

    def delete_view(self, view_name: str):
        """Delete a saved view by name."""
        view_element = self.page.locator(f"span[title='{view_name}']")
        view_element.hover()
        self.delete_button.click()
        self.confirm_yes_button.click()
        
        # Wait for success message
        self.success_message.wait_for(state="visible", timeout=60000)

    def drag_view_to_tile(self, view_name: str, tile_index: int = 0):
        """Drag a saved view to a tile.

        Native mouse drag first; a drag that raises or lands nothing
        falls back to the JS DataTransfer simulation. A stalled tile
        count is logged, never raised - a dropped view can open as its
        own tab or redraw the grid to the same count, so callers keep
        the verdict with their own oracles. Only a fallback that
        cannot even dispatch raises.
        """
        view_selector = f"span[title='{view_name}']"
        view_element = self.page.locator(view_selector)
        target_tile = self.drag_drop_tiles.nth(tile_index)
        # A drop can open the view as its own tab whose grid holds the
        # same number of placeholders; the tab appearing is that
        # outcome's landed signal, and without it a second drop would
        # be fired at a view that already opened
        view_tab = self.page.locator(
            f"button.tabItem:has(div[title='{view_name}'])"
        )
        tabs_before = view_tab.count()

        def tab_opened():
            return view_tab.count() > tabs_before

        before_tiles = self.drag_drop_tiles.count()
        try:
            self.mouse_drag(view_element, target_tile)
            landed = self._tile_count_changed(before_tiles, "view drag",
                                              extra_signal=tab_opened)
        # RuntimeError is mouse_drag's no-bounding-box failure; the
        # geometry-free JS simulation still works there
        except (RuntimeError, PlaywrightError):
            landed = False
        if not landed:
            print("[VIEWS] view drag: mouse drag did not consume a tile; "
                  "trying JS DataTransfer fallback")
            self._simulate_drag_via_js(view_selector, tile_index,
                                       extra_signal=tab_opened)

    def _simulate_drag_via_js(self, view_selector: str, tile_index: int = 0,
                              extra_signal=None):
        """Simulate HTML5 drag-and-drop using DataTransfer via page.evaluate.

        This is a fallback when Playwright's native drag doesn't trigger the
        application's drop handlers (common with React drag libraries).
        """
        script = r"""
        ([viewSelector, tileIndex]) => {
            // The dragstart listener sits on the draggable ancestor,
            // not the name label the selector finds
            const label = document.querySelector(viewSelector);
            if (!label) return {ok:false, reason: 'source-not-found'};
            const src = label.closest('[draggable="true"]') || label;

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

        before_tiles = self.drag_drop_tiles.count()
        # evaluate carries one serializable arg, so both go in a list
        result = self.page.evaluate(script, [view_selector, tile_index])
        if not result.get("ok"):
            raise RuntimeError(
                f"JS view drag could not dispatch: {result.get('reason')}"
            )
        # React applies the simulated drop async; a consumed tile (or
        # the caller's extra signal) is the applied sign - logged, not
        # raised, when neither lands: the caller's oracle decides
        self._tile_count_changed(before_tiles, "JS view drag",
                                 extra_signal=extra_signal)
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

        Native mouse drag first; a drag that raises or consumes no
        tile falls back to the JS DataTransfer simulation. A stalled
        tile count is logged, never raised - some drops land streams
        without changing the counted tiles, so callers keep the
        verdict with their own oracles. Only a fallback that cannot
        even dispatch raises.

        Args:
            camera_name: The visible name of the camera to drag.
            tile_index: Target tile index (0-based). Default is first tile.
        """
        # Find the camera thumbnail by name
        camera = self.page.locator(f".cameraThumbnailWrapper:has-text('{camera_name}')").first
        camera.wait_for(state="visible", timeout=10000)

        target_tile = self.drag_drop_tiles.nth(tile_index)
        target_tile.wait_for(state="visible", timeout=10000)

        before_tiles = self.drag_drop_tiles.count()
        try:
            self.mouse_drag(camera, target_tile)
            # A successful drop consumes the empty tile
            landed = self._tile_count_changed(before_tiles, "camera drag")
        # RuntimeError is mouse_drag's no-bounding-box failure; the
        # geometry-free JS simulation still works there
        except (RuntimeError, PlaywrightError):
            landed = False
        if not landed:
            print("[VIEWS] camera drag: mouse drag did not consume a tile; "
                  "trying JS DataTransfer fallback")
            self._simulate_camera_drag_via_js(camera_name, tile_index)

    def _simulate_camera_drag_via_js(self, camera_name: str, tile_index: int = 0):
        """Simulate HTML5 drag-and-drop for camera using DataTransfer via page.evaluate.

        This is a fallback when Playwright's native drag doesn't trigger the
        application's drop handlers (common with React drag libraries).
        """
        script = r"""
        ([cameraName, tileIndex]) => {
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
        before_tiles = self.drag_drop_tiles.count()
        # evaluate carries one serializable arg, so both go in a list
        result = self.page.evaluate(script, [camera_name, tile_index])
        if not result.get("ok"):
            raise RuntimeError(
                f"JS camera drag could not dispatch: {result.get('reason')}"
            )
        # React applies the simulated drop async; a consumed tile is
        # the applied sign - logged, not raised, when it never moves:
        # the caller's oracle decides
        self._tile_count_changed(before_tiles, "JS camera drag")
        return result

    def drag_location_to_tile(self, location_name: str, tile_index: int = 0):
        """Drag a location/site from the left panel to a tile.

        Native mouse drag first; a drag that raises or consumes no
        tile falls back to the JS DataTransfer simulation. A stalled
        tile count is logged, never raised - some drops land streams
        without changing the counted tiles, so callers keep the
        verdict with their own oracles. Only a fallback that cannot
        even dispatch raises.

        Args:
            location_name: The visible name of the location/site to drag.
            tile_index: Target tile index (0-based). Default is first tile.
        """
        # Find the location in the left panel (site tree)
        location = self.page.locator(f"text={location_name}").first
        location.wait_for(state="visible", timeout=10000)

        target_tile = self.drag_drop_tiles.nth(tile_index)
        target_tile.wait_for(state="visible", timeout=10000)

        before_tiles = self.drag_drop_tiles.count()
        try:
            self.mouse_drag(location, target_tile)
            # A successful drop consumes the empty tile
            landed = self._tile_count_changed(before_tiles, "location drag")
        # RuntimeError is mouse_drag's no-bounding-box failure; the
        # geometry-free JS simulation still works there
        except (RuntimeError, PlaywrightError):
            landed = False
        if not landed:
            print("[VIEWS] location drag: mouse drag did not consume a tile; "
                  "trying JS DataTransfer fallback")
            self._simulate_location_drag_via_js(location_name, tile_index)

    def _simulate_location_drag_via_js(self, location_name: str, tile_index: int = 0):
        """Simulate drag-and-drop for location using DataTransfer via page.evaluate."""
        script = r"""
        ([locationName, tileIndex]) => {
            // Find location element by text
            const allElements = Array.from(document.querySelectorAll('*'));
            const found = allElements.find(el =>
                el.textContent === locationName ||
                (el.innerText && el.innerText.trim() === locationName)
            );
            if (!found) return {ok:false, reason: 'location-not-found'};
            // The dragstart listener sits on the draggable ancestor
            // (the site row), not the text node the hunt lands on
            const src = found.closest('[draggable="true"]') || found;

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
        before_tiles = self.drag_drop_tiles.count()
        # evaluate carries one serializable arg, so both go in a list
        result = self.page.evaluate(script, [location_name, tile_index])
        if not result.get("ok"):
            raise RuntimeError(
                f"JS location drag could not dispatch: {result.get('reason')}"
            )
        # React applies the simulated drop async; a consumed tile is
        # the applied sign - logged, not raised, when it never moves:
        # the caller's oracle decides
        self._tile_count_changed(before_tiles, "JS location drag")
        return result

    def drag_map_to_tile(self, map_name: str = None, tile_index: int = 0):
        """Drag a map element to a tile.

        Native mouse drag first; a drag that raises or consumes no
        tile falls back to the JS DataTransfer simulation. A stalled
        tile count is logged, never raised - some drops land content
        without changing the counted tiles, so callers keep the
        verdict with their own oracles. Only a fallback that cannot
        even dispatch raises.

        Args:
            map_name: The name of the map to drag. If None, drags the first map.
            tile_index: Target tile index (0-based). Default is first tile.
        """
        # Open maps panel first; the map-element wait below is the
        # panel-open signal
        self.open_maps()

        # Find the map element
        if map_name:
            map_element = self.page.locator(f"text={map_name}").first
        else:
            # Try to find any map thumbnail or element
            map_element = self.page.locator("[class*='map'], img[src*='map']").first

        map_element.wait_for(state="visible", timeout=10000)
        target_tile = self.drag_drop_tiles.nth(tile_index)

        before_tiles = self.drag_drop_tiles.count()
        try:
            self.mouse_drag(map_element, target_tile)
            # A successful drop consumes the empty tile
            landed = self._tile_count_changed(before_tiles, "map drag")
        # RuntimeError is mouse_drag's no-bounding-box failure; the
        # geometry-free JS simulation still works there
        except (RuntimeError, PlaywrightError):
            landed = False
        if not landed:
            print("[VIEWS] map drag: mouse drag did not consume a tile; "
                  "trying JS DataTransfer fallback")
            # Maps have no dedicated simulation; the location one matches
            # its source by exact text, which the map's visible name
            # satisfies. An unlabeled map gives it nothing to find, so
            # there is no fallback left to try.
            label = map_name or map_element.inner_text().strip().split("\n")[0]
            if not label:
                raise RuntimeError(
                    "map drag landed nothing and the map has no visible "
                    "name for the JS fallback to search by"
                )
            self._simulate_location_drag_via_js(label, tile_index)

    def is_streaming_working(self, expected_failures: int = 0) -> bool:
        """Check if streaming is working (failures <= expected offline cameras)."""
        failure_count = self.streaming_failed.count()
        return failure_count <= expected_failures

    def content_health_snapshot(self) -> dict | None:
        """Count broken images and stream-failure tiles, page-wide.

        The pre-action baseline for log_new_content_issues. Raw counts
        prove nothing on their own - the tenant's legitimately offline
        cameras always show the app's stream-failure state - so only
        growth across an action means anything. One evaluate for the
        images plus one locator count keeps it cheap and read-only.
        """
        # Advisory only: a snapshot that cannot be taken (page mid-crash,
        # context torn down) returns None and the logger stands down -
        # observability must never decide a test's outcome
        try:
            broken_images = self.page.evaluate(
                "() => Array.from(document.images)"
                ".filter(img => img.complete && img.naturalWidth === 0).length"
            )
            return {
                "broken_images": broken_images,
                "stream_failures": self.streaming_failed.count(),
            }
        except Exception as e:  # noqa: BLE001 - advisory layer, log and stand down
            print(f"[VIEWS] content health snapshot failed: {e}")
            return None

    def log_new_content_issues(self, before: dict, action: str):
        """Print one greppable line when an action grew either count.

        Advisory only, never an assertion: a drop can succeed
        mechanically (tile consumed) while the tile renders a broken
        image or a dead stream - observed live on a channel drop. The
        offline-camera baseline makes asserting here a flake trap, so
        the signal is a log line for grepping run output, printed only
        when something grew past the caller's pre-action snapshot.
        """
        try:
            after = self.content_health_snapshot()
            if before is None or after is None:
                return
            broken_delta = after["broken_images"] - before["broken_images"]
            stream_delta = after["stream_failures"] - before["stream_failures"]
            if broken_delta > 0 or stream_delta > 0:
                print(f"[VIEWS] content health after {action}: "
                      f"{broken_delta:+d} broken image(s), "
                      f"{stream_delta:+d} stream failure(s)")
        except Exception as e:  # noqa: BLE001 - advisory layer, log and stand down
            print(f"[VIEWS] content health check failed: {e}")

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
            site_name: Specific site name, or None to click the first available site.
        """
        if site_name:
            site = self.page.locator(f"text={site_name}").first
            try:
                site.wait_for(state="visible", timeout=15000)
            except Exception:
                # Tenant data drift guard: the shared QA tenant renames sites
                # under the tests (a 2026-08-07 rename broke every site-
                # selecting test). Fail fast with the names that ARE there
                # so the fix is one config edit, not an hour of triage.
                visible = self.page.evaluate(
                    """() => {
                        const els = document.querySelectorAll(
                            "[role='treeitem'], [class*='panel'] p, [class*='camera'] p, button"
                        );
                        const out = [];
                        for (const el of els) {
                            const t = (el.innerText || '').trim().split('\\n')[0];
                            if (t && t.length <= 60 && el.offsetWidth > 0 && !out.includes(t)) {
                                out.push(t);
                            }
                        }
                        return out.slice(0, 20);
                    }"""
                )
                raise RuntimeError(
                    f"The configured site '{site_name}' is not in the site "
                    f"picker. Entries on screen: {visible}. The tenant may "
                    f"have renamed the site. Update test_site_name in "
                    f"config/env/ to match the picker."
                ) from None
            site.click()
        else:
            # Check if "All Cameras" is already visible - site already expanded
            if self.page.locator("text=All Cameras").count() > 0:
                return "all_cameras_already_visible"

            # Give the site tree a moment to render before scanning the DOM -
            # the JS scan below runs immediately and does not retry
            self._appears(
                self.page.locator("[role='treeitem'], [class*='panel'] p"),
                timeout=3000,
            )
            # Use JS to click the first site-like element in the panel.
            # Sites may be in p/span/div elements, tree nodes, or MUI menu items
            known_labels = {
                'Devices', 'My Views', 'Insights', 'Maps', 'All Cameras',
                'Favorites', 'Search', 'Events', 'Sequences', 'Admin',
                'Views', 'Chats', 'Dashboard', 'Notifications', 'Settings',
                'Logout', 'Profile', 'Help', 'Channels', 'Licenses',
                'Login', 'Media', 'Reports', 'Select Location & Cameras',
                'More Layouts', 'Layouts', 'Layout',
            }
            result = self.page.evaluate("""(knownLabels) => {
                const exclude = new Set(knownLabels);

                // Try multiple selector patterns to find site elements
                const selectorPatterns = [
                    // MUI TreeItem nodes (within tree)
                    '[role="treeitem"]',
                    // MUI Menu items
                    '[role="menuitem"]',
                    // MUI ListItem
                    '[role="option"]',
                    // Standard panel/sidebar p/span/div
                    '.cameraPanel p', '.leftPanel p', '.sidebarPanel p',
                    '[class*="camera"] p', '[class*="panel"] p',
                    '[class*="device"] p', '[class*="sidebar"] p',
                    // Fallback to all clickable-looking elements
                    'p', 'span', 'div[role="button"]',
                ];

                const found = [];
                for (const selector of selectorPatterns) {
                    const els = document.querySelectorAll(selector);
                    if (els.length === 0) continue;

                    for (const el of els) {
                        const text = (el.innerText || el.textContent || '').trim();
                        if (text.length >= 2 && text.length <= 100 && el.offsetWidth > 0 && el.offsetHeight > 0) {
                            if (!found.includes(text)) {
                                found.push(text);
                            }
                            if (!exclude.has(text)) {
                                el.click();
                                return {clicked: text, candidates: found.slice(0, 15)};
                            }
                        }
                    }
                }
                return {clicked: null, candidates: found.slice(0, 15)};
            }""", list(known_labels))
            print(f"DEBUG click_site JS result: {result}")
            self.page.wait_for_timeout(500)  # JS click bypasses waits; no signal
            return result

    def click_all_cameras(self):
        """Click on 'All Cameras' to show all camera thumbnails."""
        all_cameras = self.page.locator("text=All Cameras").first
        all_cameras.wait_for(state="visible", timeout=10000)
        all_cameras.click(force=True)

    def expand_site_and_show_cameras(self, site_name: str = None):
        """Expand a site and click All Cameras to show thumbnails.

        Flow: Devices tab -> site node -> All Cameras -> thumbnails appear.
        Idempotent: skips if camera thumbnails are already visible.

        Args:
            site_name: Specific site name to expand. If None, uses config test_site_name.
        """
        if self.camera_thumbnails.count() > 0:
            print(f"DEBUG expand_site_and_show_cameras: Cameras already visible, skipping")
            return  # Already expanded, nothing to do

        # Use configured site name if not specified
        if site_name is None:
            from config.base_config import config
            site_name = config.get("test_site_name")
            print(f"DEBUG expand_site_and_show_cameras: Using configured site_name={site_name}")

        print(f"DEBUG expand_site_and_show_cameras: Starting site expansion (site_name={site_name})")

        # Step 1: activate Devices panel
        if self.devices_subtab.count() > 0:
            self.devices_subtab.click()
            print(f"DEBUG expand_site_and_show_cameras: Clicked devices subtab")
        elif self.devices_tab.count() > 0:
            self.devices_tab.first.click()
            print(f"DEBUG expand_site_and_show_cameras: Clicked devices tab")

        # Step 2: "Select Location & Cameras" is a placeholder button that opens
        # the site picker - it renders once the Devices panel loads, so wait
        # for it briefly instead of sleeping a fixed amount
        select_loc = self.page.locator("text=Select Location & Cameras")
        if self._appears(select_loc, timeout=5000):
            select_loc.first.click()
            print(f"DEBUG expand_site_and_show_cameras: Clicked 'Select Location & Cameras'")

        # Step 3: click the site in the now-visible tree (a named site click
        # auto-waits for the tree to render)
        print(f"DEBUG expand_site_and_show_cameras: Calling click_site({site_name})")
        self.click_site(site_name)

        # Step 4: click "All Cameras" if it appears
        all_cameras = self.page.locator("text=All Cameras")
        if self._appears(all_cameras, timeout=5000):
            print(f"DEBUG expand_site_and_show_cameras: Clicking 'All Cameras'")
            self.click_all_cameras()
            # A click that lands during a tree re-render is silently dropped
            # (measured in trace: click dispatched, no thumbnails loaded).
            # Retry once if no thumbnails appear.
            if not self._appears(self.camera_thumbnails, timeout=8000):
                print(f"DEBUG expand_site_and_show_cameras: Retrying 'All Cameras' click")
                self.click_all_cameras()
                self._appears(self.camera_thumbnails, timeout=10000)
        else:
            print(f"DEBUG expand_site_and_show_cameras: 'All Cameras' not visible")
            # Some tenants show thumbnails without an All Cameras node
            self._appears(self.camera_thumbnails, timeout=8000)

        camera_count = self.camera_thumbnails.count()
        print(f"DEBUG expand_site_and_show_cameras: Final result - {camera_count} cameras visible")

    def add_bookmark_on_tile(self, tile_index: int = 0):
        """Add a bookmark on a video tile in fullscreen mode.

        Flow:
        1. Enter fullscreen on the tile
        2. Wait for stream to load
        3. Hover the timeline to reveal bookmark icon
        4. Click the bookmark icon
        """
        # Enter fullscreen first (timeline is always available in
        # fullscreen); the stream wait below is the entered signal
        print(f"DEBUG add_bookmark_on_tile: Entering fullscreen...")
        self.enter_fullscreen_on_tile(tile_index)

        # Import FullScreenPage for fullscreen operations
        from tests.shared.pages.fullscreen_page import FullScreenPage
        fs = FullScreenPage(self.page)

        # Wait for stream to load
        print(f"DEBUG add_bookmark_on_tile: Waiting for stream to load in fullscreen...")
        fs.wait_for_stream_loaded(timeout=30000)
        print(f"DEBUG add_bookmark_on_tile: Stream loaded!")

        # In fullscreen, timeline is always available - hover it to reveal
        # bookmark icon; the icon click waits for the reveal on its own
        print(f"DEBUG add_bookmark_on_tile: Hovering timeline in fullscreen...")
        timeline = fs.video_container.locator("[class*='timeline'], svg").first
        timeline.hover()

        # Click the bookmark icon
        print(f"DEBUG add_bookmark_on_tile: Clicking bookmark icon...")
        bookmark_icon = fs.video_container.locator("img[src*='Bookmark']")
        bookmark_icon.click()
        # The bookmark save shows no confirmation on the timeline
        self.page.wait_for_timeout(2000)
        print(f"DEBUG add_bookmark_on_tile: Bookmark added!")

        # Exit fullscreen
        print(f"DEBUG add_bookmark_on_tile: Exiting fullscreen...")
        fs.exit_fullscreen()
        # The fullscreen exit animation has no reliable DOM signal
        self.page.wait_for_timeout(1000)
        print(f"DEBUG add_bookmark_on_tile: Done!")

    def share_live_view_on_tile(self, email: str, tile_index: int = 0):
        """Share a live view from a video tile via email and copy link.

        Hovers the video tile, opens three-dot menu, hovers timeline,
        clicks share icon, fills email, clicks Share, then Copy.
        Returns the copy button text (or empty string if not found).
        """
        video_tile = self.page.locator(
            "[class*='video_container'][class*='new_video_player']"
        ).nth(tile_index)

        # Hover chains: each following click waits for its own target,
        # so no pacing sleeps are needed between the reveals
        video_tile.hover()

        # Click three-dot menu
        three_dots = video_tile.locator(".control-small-view")
        three_dots.click()

        # Hover timeline to reveal share icon. The svg line itself has
        # a zero-height box that Playwright treats as never visible, so
        # hover its parent svg; fall back to a forced hover on the line.
        timeline = video_tile.locator("#svg-line-2")
        try:
            timeline.locator("xpath=..").hover(timeout=5000)
        except Exception:
            timeline.hover(force=True)

        # Click share icon; the dialog wait below is the opened signal.
        # The tile renders two share imgs (controls bar + timeline
        # overlay): click the one the hover revealed.
        share_icon = video_tile.locator(
            "img[src*='media/icon-share']:visible"
        ).first
        share_icon.click()

        # Fill email in share dialog. The dialog holds two
        # .fileName_inputfield inputs; prefer the one whose placeholder
        # names an email.
        share_container = self.page.locator(".share_live_main_container")
        share_container.wait_for(state="visible", timeout=10000)
        email_field = share_container.locator(
            "input[placeholder*='mail' i]"
        ).first
        if email_field.count() == 0:
            email_field = share_container.locator(".fileName_inputfield").first
        email_field.fill(email)

        # Click Share button; the Copy button wait is the shared signal
        share_button = self.page.locator("button:has(span:text-is('Share'))")
        share_button.click()

        # Click Copy button for the link
        copy_button = self.page.locator("span:text-is('Copy')")
        try:
            copy_button.wait_for(state="visible", timeout=10000)
        except PlaywrightError:
            raise AssertionError(
                "No Copy button appeared within 10s of clicking Share: "
                "the share did not complete"
            ) from None
        copy_button.click()

        # Close the share dialog if it is still open
        cancel_btn = share_container.locator(".cancel_button_share_live")
        if self._appears(cancel_btn, timeout=3000):
            cancel_btn.first.click()

    def toggle_favorite(self, camera_name: str):
        """Toggle the favorite star on a camera in the left panel.

        Finds the camera by name in the site tree and clicks its
        favorite button.
        """
        # Scope to the camera's row (grandparent of the title span),
        # then find its favorite button. The old selector mixed XPath
        # into a CSS string and never parsed.
        row_anchor = self.page.locator(f"span[title='{camera_name}']").first
        if not self._appears(row_anchor, timeout=3000):
            # The camera tree collapses itself shortly after expansion,
            # and the bare panel toggle reopens it collapsed (probe
            # 08/09/2026): run the full expansion to reach the row
            self.expand_site_and_show_cameras(None)
            row_anchor.wait_for(state="visible", timeout=10000)
        row_anchor.hover()
        fav_button = row_anchor.locator("xpath=../..").locator(
            "button:has(img[alt='favorite'])"
        ).first
        fav_button.wait_for(state="visible", timeout=10000)
        fav_button.click()
        # The favorite state is saved server-side with no validated DOM
        # signal for the toggle landing
        self.page.wait_for_timeout(2000)

    def is_camera_favorited(self, camera_name: str) -> bool:
        """Return True if the camera has a filled favorite icon.

        Re-expands the tree when the row is unreachable, exactly like
        toggle_favorite: a one-shot count on a self-collapsed tree
        would report not-favorited for a favorited camera and make the
        caller invert its toggle.
        """
        row_anchor = self.page.locator(f"span[title='{camera_name}']").first
        if not self._appears(row_anchor, timeout=3000):
            self.expand_site_and_show_cameras(None)
            row_anchor.wait_for(state="visible", timeout=10000)
        filled_icon = row_anchor.locator("xpath=../..").locator(
            "img[src*='media/favoriteIconFilled']"
        )
        return filled_icon.count() > 0

    def open_favorites_panel(self):
        """Open the favorites panel by clicking the favorites icon."""
        fav_icon = self.page.locator("img[src*='media/favoriteIcon']").first
        fav_icon.click()
        # The panel slide-in has no known DOM signal
        self.page.wait_for_timeout(2000)

    def close_favorites_panel(self):
        """Close the favorites panel by clicking the favorites icon again."""
        fav_icon = self.page.locator("img[src*='media/favoriteIcon']").first
        fav_icon.click()
        # The panel slide-out has no known DOM signal
        self.page.wait_for_timeout(1000)

    def is_camera_in_favorites(self, camera_name: str) -> bool:
        """Return True if the camera name appears in the currently open favorites panel."""
        return self.page.locator(f"text={camera_name}").count() > 0

    def enter_fullscreen_on_tile(self, tile_index: int = 0):
        """Enter full screen mode on a specific video tile.

        Hovers the video container to reveal controls, then clicks the zoom
        button. The app renders two zoom icons per tile - the second one
        triggers full screen mode.
        """
        video_tile = self.page.locator(
            "[class*='video_container'][class*='new_video_player']"
        ).nth(tile_index)

        video_tile.hover()

        # Wait for the hover-revealed controls before counting them
        zoom_buttons = video_tile.locator("img[src*='media/Zoom.']")
        self._appears(zoom_buttons, timeout=5000)
        if zoom_buttons.count() > 1:
            zoom_buttons.nth(1).click()
        else:
            zoom_buttons.first.click()
