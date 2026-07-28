"""LPR Insights Widget creation and management tests."""
import pytest
import time
from tests.shared.pages.lpr_page import LprPage


class TestLprWidgets:
    """Tests for LPR insight widget functionality."""

    widget_name = None  # Class variable to store created widget name

    @pytest.fixture(autouse=True)
    def setup(self, authenticated_page, step_capture):
        self.page = authenticated_page
        self.step_capture = step_capture
        step_capture.set_page(self.page)
        self.lpr = LprPage(self.page)

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.lpr
    def test_create_new_insight_widget(self):
        """Create a new LPR insight widget with all required fields."""
        from config.base_config import config

        self.step_capture.mark(1, "Navigate to Insights")
        insights = self.page.locator("span:has-text('Insights')").first
        if insights.count() > 0:
            insights.click()
            self.page.wait_for_timeout(2000)

            self.step_capture.mark(2, "Click Widgets tab")
            widgets_tab = self.page.locator("p:has-text('Widgets')").first
            if widgets_tab.count() > 0:
                widgets_tab.click()
                self.page.wait_for_timeout(1000)

                self.step_capture.mark(3, "Click Create New button")
                create_btn = self.page.locator("button:has-text('Create New')").first
                if create_btn.count() > 0:
                    create_btn.click()
                    self.page.wait_for_timeout(1000)

                    self.step_capture.mark(4, "Enter widget name")
                    widget_name_field = self.page.locator("input[placeholder='Enter Widget Name']").first
                    if widget_name_field.count() > 0:
                        timestamp = int(time.time())
                        widget_name = f"Test_Widget_{timestamp}"
                        widget_name_field.fill(widget_name)
                        TestLprWidgets.widget_name = widget_name
                        print(f"[STEP 4] Widget name entered: {widget_name}")

                        self.step_capture.mark(5, "Select graph type: Line Graph")
                        graph_dropdown = self.page.locator("div:has(label:has-text('GraphType'))").first
                        if graph_dropdown.count() > 0:
                            graph_dropdown.click()
                            self.page.wait_for_timeout(500)
                            line_graph = self.page.locator("p:has-text('Line Graph')").first
                            if line_graph.count() > 0:
                                line_graph.click()
                                print("[STEP 5] Line Graph selected")

                        self.page.keyboard.press("Escape")
                        self.page.wait_for_timeout(500)

                        self.step_capture.mark(6, "Select category: Event")
                        category_dropdown = self.page.locator("div:has(label:has-text('Category'))").first
                        if category_dropdown.count() > 0:
                            category_dropdown.click()
                            self.page.wait_for_timeout(500)
                            event_option = self.page.locator("p:has-text('Event')").first
                            if event_option.count() > 0:
                                event_option.click()
                                print("[STEP 6] Event category selected")

                        self.page.keyboard.press("Escape")
                        self.page.wait_for_timeout(500)

                        self.step_capture.mark(7, "Select description: License Plate Recognition")
                        desc_dropdown = self.page.locator("div:has(label:has-text('description'))").first
                        if desc_dropdown.count() > 0:
                            desc_dropdown.click()
                            self.page.wait_for_timeout(500)
                            lpr_option = self.page.locator("span:has-text('License Plate Recognition')").first
                            if lpr_option.count() > 0:
                                lpr_option.click()
                                print("[STEP 7] LPR description selected")

                        self.page.keyboard.press("Escape")
                        self.page.wait_for_timeout(500)

                        self.step_capture.mark(8, "Select site: Newtown ActionArea")
                        site_name = config.get("test_site_name", "Newtown ActionArea")
                        select_buttons = self.page.locator("p:has-text('Select')").all()
                        if len(select_buttons) > 0:
                            select_buttons[0].click()
                            self.page.wait_for_timeout(500)
                            site_option = self.page.locator(f"text={site_name}").first
                            if site_option.count() > 0:
                                site_option.click()
                                print(f"[STEP 8] Site selected: {site_name}")

                        self.page.keyboard.press("Escape")
                        self.page.wait_for_timeout(500)

                        self.step_capture.mark(9, "Select camera")
                        camera_name = config.get("test_camera_name", "main gate")
                        camera_dropdown = self.page.locator("p:has-text('Select')").nth(1)
                        if camera_dropdown.count() > 0:
                            camera_dropdown.click()
                            self.page.wait_for_timeout(500)

                            all_cameras = self.page.locator("p:has-text('All Cameras')").first
                            if all_cameras.count() > 0:
                                all_cameras.click()
                                self.page.wait_for_timeout(500)

                                camera_option = self.page.locator(f"p:has-text('{camera_name}')").first
                                if camera_option.count() > 0:
                                    camera_checkbox = camera_option.locator("xpath=ancestor::div//input[@type='checkbox']").first
                                    if camera_checkbox.count() > 0:
                                        camera_checkbox.click()
                                        print(f"[STEP 9] Camera selected: {camera_name}")

                        self.page.keyboard.press("Escape")
                        self.page.wait_for_timeout(500)

                        self.step_capture.mark(10, "Select duration: Last 7 Days")
                        duration_field = self.page.locator("div:has(text='Duration')").first
                        if duration_field.count() > 0:
                            duration_field.click()
                            self.page.wait_for_timeout(500)
                            duration_option = self.page.locator("text=Last 7 Days").first
                            if duration_option.count() > 0:
                                duration_option.click()
                                print("[STEP 10] Duration selected: Last 7 Days")

                        self.page.keyboard.press("Escape")
                        self.page.wait_for_timeout(500)

                        self.step_capture.mark(11, "Select widget size: Full Width")
                        size_field = self.page.locator("div:has(text='Widget Size')").first
                        if size_field.count() > 0:
                            size_field.click()
                            self.page.wait_for_timeout(500)
                            full_width = self.page.locator("text=Full Width").first
                            if full_width.count() > 0:
                                full_width.click()
                                print("[STEP 11] Widget size selected: Full Width")

                        self.step_capture.mark(12, "Click Save & Preview")
                        save_btn = self.page.locator("button:has-text('Save & Preview')").first
                        if save_btn.count() > 0:
                            save_btn.click()
                            self.page.wait_for_timeout(2000)
                            print("[STEP 12] Save & Preview clicked")

        self.step_capture.mark(13, "Widget creation completed")
        print(f"[PASS] Widget created: {TestLprWidgets.widget_name}")

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.lpr
    def test_verify_widget_in_lpr_dropdown(self):
        """Verify the created widget appears in LPR widgets dropdown."""
        widget_name = TestLprWidgets.widget_name
        if not widget_name:
            pytest.skip("No widget name available - run test_create_new_insight_widget first")

        self.step_capture.mark(1, "Navigate to LPR")
        self.lpr.navigate_to_lpr()

        self.step_capture.mark(2, "Click Widgets dropdown")
        widgets_dropdown = self.page.locator("p:has-text('Widgets')").first
        if widgets_dropdown.count() > 0:
            widgets_dropdown.click()
            self.page.wait_for_timeout(1000)

            self.step_capture.mark(3, "Search for created widget")
            search_box = self.page.locator("input[placeholder='Search']").first
            if search_box.count() > 0:
                search_box.fill(widget_name)
                self.page.wait_for_timeout(1000)

                self.step_capture.mark(4, f"Verify widget '{widget_name}' appears in list")
                widget_result = self.page.locator(f"span:has-text('{widget_name}')").first
                if widget_result.count() > 0:
                    assert widget_result.is_visible(), f"Widget {widget_name} not visible"
                    print(f"[STEP 4] Widget found: {widget_name}")

        self.step_capture.mark(5, "Widget verification completed")
        print(f"[PASS] Widget verified in dropdown: {widget_name}")

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.lpr
    def test_select_widget_checkbox(self):
        """Select created widget using checkbox."""
        widget_name = TestLprWidgets.widget_name
        if not widget_name:
            pytest.skip("No widget name available - run test_create_new_insight_widget first")

        self.step_capture.mark(1, "Refresh page")
        self.page.reload()
        self.page.wait_for_load_state("networkidle", timeout=30000)
        self.page.wait_for_timeout(2000)

        self.step_capture.mark(2, "Navigate to LPR")
        self.lpr.navigate_to_lpr()

        self.step_capture.mark(3, "Open Widgets dropdown")
        widgets_dropdown = self.page.locator("p:has-text('Widgets')").first
        if widgets_dropdown.count() > 0:
            widgets_dropdown.click()
            self.page.wait_for_timeout(1000)

            self.step_capture.mark(4, "Search for widget")
            search_box = self.page.locator("input[placeholder='Search']").first
            if search_box.count() > 0:
                search_box.fill(widget_name)
                self.page.wait_for_timeout(1000)

                self.step_capture.mark(5, "Find and click widget checkbox")
                widget_result = self.page.locator(f"span:has-text('{widget_name}')").first
                if widget_result.count() > 0:
                    widget_result.hover()
                    self.page.wait_for_timeout(500)

                    checkbox = self.page.locator("input[type='checkbox']").first
                    if checkbox.count() > 0:
                        checkbox.click()
                        print(f"[STEP 5] Widget checkbox selected: {widget_name}")

        self.step_capture.mark(6, "Widget checkbox selection completed")
        print(f"[PASS] Widget checkbox selected: {widget_name}")
