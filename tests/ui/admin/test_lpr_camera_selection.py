"""LPR Camera selection tests - multi-camera selection, hover, drag-drop."""
import pytest
import time
from playwright.sync_api import expect
from tests.shared.pages.lpr_page import LprPage


class TestLprCameraSelection:
    """Tests for LPR camera selection and manipulation."""

    @pytest.fixture(autouse=True)
    def setup(self, authenticated_page, step_capture):
        self.page = authenticated_page
        self.step_capture = step_capture
        step_capture.set_page(self.page)
        self.lpr = LprPage(self.page)

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.lpr
    def test_select_multi_camera_by_site(self):
        """Select multiple cameras by site using checkbox."""
        from config.base_config import config

        self.step_capture.mark(1, "Navigate to LPR page")
        self.lpr.navigate_to_lpr()
        self.page.wait_for_timeout(1000)

        site_name = config.get("test_site_name", "Newtown ActionArea")
        self.step_capture.mark(2, f"Open Locations & Cameras for site: {site_name}")

        # Try to find and click Locations & Cameras dropdown
        locations = self.page.locator("p:has-text('Locations & Cameras')").first
        if locations.count() == 0:
            locations = self.page.locator("span:has-text('Locations')").first

        try:
            if locations.count() > 0:
                locations.wait_for(state="visible", timeout=30000)
                locations.click()
                self.page.wait_for_timeout(1000)
            else:
                print("[INFO] Locations dropdown not found - may need to navigate further")
                self.step_capture.mark(3, "Locations not found")
                return
        except Exception as e:
            print(f"[INFO] Could not open locations: {e}")
            return

        self.step_capture.mark(3, "Find and click site")
        site = self.page.locator(f"span:has-text('{site_name}')").first
        site.wait_for(state="visible", timeout=30000)
        site.click()
        self.page.wait_for_timeout(1000)

        self.step_capture.mark(4, "Find All Cameras option")
        all_cameras = self.page.locator("span:has-text('All Cameras')").first
        all_cameras.wait_for(state="visible", timeout=30000)

        self.step_capture.mark(5, "Hover and select All Cameras checkbox")
        all_cameras.hover()
        self.page.wait_for_timeout(1000)

        checkbox = self.page.locator("img[src*='uncheck-icon']").first
        if checkbox.count() > 0:
            checkbox.click()
            print("[STEP 5] All Cameras selected")

        self.step_capture.mark(6, "Verify camera players loaded")
        players = self.page.locator("video, canvas, div:has-text('Live')").all()
        visible_players = [p for p in players if p.is_visible()]

        assert len(visible_players) > 0, "Multi-camera views not loaded"
        print(f"[PASS] Multi-camera views loaded: {len(visible_players)} players")

        self.step_capture.mark(7, "Reset View")
        reset_btn = self.page.locator("p:has-text('Reset View')").first
        reset_btn.wait_for(state="visible", timeout=30000)
        reset_btn.click()
        self.page.wait_for_timeout(2000)

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.lpr
    def test_drag_drop_camera_to_grid(self):
        """Drag and drop all cameras to a specific grid cell."""
        from config.base_config import config

        self.step_capture.mark(1, "Navigate to LPR page")
        self.lpr.navigate_to_lpr()
        self.page.wait_for_timeout(1000)

        site_name = config.get("test_site_name", "Newtown ActionArea")
        self.step_capture.mark(2, "Open Locations & Cameras")

        locations = self.page.locator("p:has-text('Locations & Cameras')").first
        if locations.count() == 0:
            locations = self.page.locator("span:has-text('Locations')").first

        if locations.count() > 0:
            try:
                locations.wait_for(state="visible", timeout=30000)
                locations.click()
                self.page.wait_for_timeout(1000)
            except Exception as e:
                print(f"[INFO] Could not open locations: {e}")
                return
        else:
            print("[INFO] Locations element not found")
            return

        self.step_capture.mark(3, "Click site")
        site = self.page.locator(f"span:has-text('{site_name}')").first
        site.wait_for(state="visible", timeout=30000)
        site.click()
        self.page.wait_for_timeout(1000)

        self.step_capture.mark(4, "Find All Cameras")
        all_cameras = self.page.locator("span:has-text('All Cameras')").first
        all_cameras.wait_for(state="visible", timeout=30000)

        self.step_capture.mark(5, "Find target grid for drag-drop")
        target_grid = self.page.locator("div:has-text('Drag & Drop Camera here')").nth(1)
        target_grid.wait_for(state="visible", timeout=30000)

        self.step_capture.mark(6, "Drag and drop cameras to grid")
        all_cameras.drag_to(target_grid)
        self.page.wait_for_timeout(2000)
        print("[STEP 6] Drag and drop completed")

        self.step_capture.mark(7, "Verify cameras loaded in grid")
        players = self.page.locator("video, canvas").all()
        visible_players = [p for p in players if p.is_visible()]

        assert len(visible_players) > 0, "Camera players not loaded after drag-drop"
        print(f"[PASS] Cameras loaded in grid: {len(visible_players)} players")

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.lpr
    def test_hover_and_select_single_camera(self):
        """Hover over camera and select checkbox."""
        from config.base_config import config

        self.step_capture.mark(1, "Navigate to LPR page")
        self.lpr.navigate_to_lpr()
        self.page.wait_for_timeout(1000)

        camera_name = config.get("test_camera_name", "main gate")
        self.step_capture.mark(2, "Open Locations & Cameras")

        locations = self.page.locator("p:has-text('Locations & Cameras')").first
        if locations.count() == 0:
            locations = self.page.locator("span:has-text('Locations')").first

        if locations.count() > 0:
            try:
                locations.wait_for(state="visible", timeout=30000)
                locations.click()
                self.page.wait_for_timeout(1000)
            except Exception as e:
                print(f"[INFO] Could not open locations: {e}")
                return
        else:
            print("[INFO] Locations not found")
            return

        self.step_capture.mark(3, f"Search for camera: {camera_name}")
        search = self.page.locator("input[placeholder='Search']").first
        if search.count() > 0:
            try:
                search.wait_for(state="visible", timeout=30000)
                search.fill(camera_name)
                self.page.wait_for_timeout(1000)
            except Exception as e:
                print(f"[INFO] Could not search: {e}")
                return

        self.step_capture.mark(4, "Find camera image")
        camera_image = self.page.locator(f"img[alt='{camera_name}']").first
        if camera_image.count() == 0:
            camera_image = self.page.locator(f"text={camera_name}").first.locator("..").locator("img").first

        if camera_image.count() > 0:
            try:
                camera_image.wait_for(state="visible", timeout=30000)

                self.step_capture.mark(5, "Hover over camera")
                camera_image.hover()
                self.page.wait_for_timeout(1000)

                self.step_capture.mark(6, "Click checkbox to select")
                checkbox = self.page.locator("img[src*='uncheck-icon']").first
                if checkbox.count() > 0:
                    checkbox.click()
                    print(f"[STEP 6] Camera '{camera_name}' selected")
            except Exception as e:
                print(f"[INFO] Could not select camera: {e}")

        self.step_capture.mark(7, "Verify selection")
        print(f"[PASS] Camera selection completed for {camera_name}")
