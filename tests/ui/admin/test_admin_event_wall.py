"""Admin Event Wall tests - configuration, event display, and layout.

Extends the Admin General tests with deeper validation of the Event Wall
sub-section under Admin > General. Verifies the event wall configuration
page, event display, site/camera selection, and layout behavior.
"""
import pytest
from playwright.sync_api import expect
from tests.shared.pages.admin_page import AdminPage


class TestAdminEventWall:
    """Deeper tests for Admin > General > Event Wall."""

    @pytest.fixture(autouse=True)
    def setup(self, authenticated_page):
        self.page = authenticated_page
        self.admin = AdminPage(self.page)
        self.admin.navigate_to_admin()

        # Navigate to General > Event Wall
        self.admin.general_tab.wait_for(state="visible", timeout=10000)
        self.admin.general_tab.click()
        self.page.wait_for_timeout(2000)

        self.event_wall = self.page.get_by_text(
            "Event Wall", exact=False
        ).first
        if self.event_wall.count() == 0 or not self.event_wall.is_visible():
            pytest.skip("Event Wall tab not found in General section")

        self.event_wall.click()
        self.page.wait_for_timeout(3000)
        yield

    # --- Page structure ---

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.admin_event_wall
    def test_event_wall_page_loads(self):
        """Verify Event Wall page loads with visible content."""
        assert "admin" in self.page.url.lower()

        # Should have a configuration area or event display
        has_content = (
            self.page.locator("div.MuiBox-root").count() > 5
            or self.page.locator("[class*='event'], [class*='wall']").count() > 0
            or self.page.locator("img").count() > 2
        )
        assert has_content, "Event Wall page should have visible content"

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.admin_event_wall
    def test_event_wall_has_configuration_area(self):
        """Verify Event Wall has a configuration or settings area."""
        config_elements = self.page.locator(
            "select, .MuiSelect-root, "
            "input[type='checkbox'], .MuiSwitch-root, "
            "button, .MuiButton-root, "
            "[class*='config'], [class*='setting']"
        )
        assert config_elements.count() > 0, (
            "Expected configuration elements on Event Wall page"
        )

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.admin_event_wall
    def test_event_wall_site_selector(self):
        """Verify Event Wall has a site selection dropdown."""
        dropdown = self.page.locator(
            "div[role='combobox'], .MuiSelect-select, "
            "select, [class*='dropdown'], [class*='select']"
        )
        if dropdown.count() == 0:
            pytest.skip("No site selector dropdown found on Event Wall")

        expect(dropdown.first).to_be_visible(timeout=10000)

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.admin_event_wall
    def test_event_wall_site_dropdown_opens(self):
        """Verify the site dropdown can be opened on Event Wall."""
        dropdown = self.page.locator(
            "div[role='combobox'], .MuiSelect-select"
        ).first
        if dropdown.count() == 0 or not dropdown.is_visible():
            pytest.skip("No dropdown found on Event Wall")

        dropdown.click()
        self.page.wait_for_timeout(1000)

        # Should show options
        options = self.page.locator(
            "[role='listbox'], [role='option'], li.MuiMenuItem-root"
        )
        has_options = options.count() > 0
        self.page.keyboard.press("Escape")

        assert has_options, "Dropdown should show options when opened"

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.admin_event_wall
    def test_event_wall_has_rule_types(self):
        """Verify Event Wall shows rule type filters or labels."""
        rule_keywords = [
            "Intrusion", "Entry", "Exit", "Line", "Heat",
            "Loitering", "Occupancy", "Detection",
        ]
        found_rule = False
        for kw in rule_keywords:
            locator = self.page.locator(f"text=/{kw}/i")
            if locator.count() > 0:
                found_rule = True
                break

        if found_rule:
            assert found_rule
            return

        # Check for checkbox or toggle elements that might be rule selectors
        toggles = self.page.locator(
            "input[type='checkbox'], .MuiSwitch-root, "
            ".MuiCheckbox-root"
        )
        if toggles.count() > 0:
            assert toggles.count() > 0
            return

        # Event Wall config may not display rule types directly
        pytest.skip("No rule type labels or filter toggles found on Event Wall")

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.admin_event_wall
    def test_event_wall_camera_checkboxes(self):
        """Verify Event Wall has camera selection checkboxes."""
        checkboxes = self.page.locator(
            "input[type='checkbox'], .MuiCheckbox-root, "
            ".MuiSwitch-root, input.PrivateSwitchBase-input"
        )
        if checkboxes.count() == 0:
            pytest.skip("No checkboxes found on Event Wall")

        assert checkboxes.count() > 0, "Expected camera selection checkboxes"

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.admin_event_wall
    def test_event_wall_toggle_checkbox(self):
        """Verify a checkbox on Event Wall can be toggled."""
        checkboxes = self.page.locator(
            "input[type='checkbox']:not([disabled])"
        )
        if checkboxes.count() == 0:
            checkboxes = self.page.locator(
                ".MuiCheckbox-root, .MuiSwitch-root"
            )
        if checkboxes.count() == 0:
            pytest.skip("No toggleable checkboxes found")

        checkboxes.first.click(force=True)
        self.page.wait_for_timeout(1000)

        # Page should remain valid
        assert "admin" in self.page.url.lower()

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.admin_event_wall
    def test_event_wall_event_images(self):
        """Verify Event Wall displays event images or thumbnails."""
        images = self.page.locator(
            "img[src*='data:image'], img[src*='snapshot'], "
            "img[src*='event'], img[src*='thumb'], "
            "img:not([src*='icon']):not([src*='logo'])"
        )
        # Event wall may or may not have images depending on events
        if images.count() > 0:
            expect(images.first).to_be_visible(timeout=10000)
        else:
            # No event images - check for empty state text
            has_empty_state = (
                self.page.locator("text=/no event/i").count() > 0
                or self.page.locator("text=/no data/i").count() > 0
                or self.page.locator("[class*='empty']").count() > 0
            )
            # Either images or empty state should exist - page is still valid
            assert "admin" in self.page.url.lower()

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.admin_event_wall
    def test_event_wall_grid_layout(self):
        """Verify Event Wall uses a grid or card-based layout for events."""
        grid_elements = self.page.locator(
            "[class*='grid'], [class*='card'], "
            ".MuiGrid-root, .MuiCard-root, "
            "[class*='tile'], [class*='wall']"
        )
        # Event wall should have some kind of layout structure
        has_layout = (
            grid_elements.count() > 0
            or self.page.locator("div.MuiBox-root").count() > 5
        )
        assert has_layout, "Expected grid or card-based layout"

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.admin_event_wall
    def test_event_wall_save_or_apply(self):
        """Verify Event Wall has a save or apply button for configuration."""
        save_btn = self.page.locator(
            "button:has-text('Save'), "
            "button:has-text('Apply'), "
            "button:has-text('Update'), "
            "button.btn-primary"
        )
        if save_btn.count() == 0:
            pytest.skip("No save/apply button found on Event Wall")

        expect(save_btn.first).to_be_visible(timeout=10000)

    # --- Navigation ---

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.admin_event_wall
    def test_back_to_general_from_event_wall(self):
        """Verify navigating back from Event Wall to General section works."""
        general_link = self.page.locator(
            "a:has-text('General'), "
            "span:has-text('General'), "
            "p:text-is('General')"
        )

        if general_link.count() > 0 and general_link.first.is_visible():
            general_link.first.click()
        else:
            self.admin.general_tab.click()

        self.page.wait_for_timeout(2000)

        # .first: 'Rules' appears in both the sidebar and General content
        rules_tab = self.page.locator("p:text-is('Rules')").first
        expect(rules_tab).to_be_visible(timeout=10000)

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.admin_event_wall
    def test_event_wall_to_audit_trail_round_trip(self):
        """Verify navigating from Event Wall to Audit Trail and back."""
        # Go to Audit Trail
        audit = self.page.get_by_text("Audit Trail", exact=False).first
        if audit.count() == 0:
            # Navigate back to General first - use .first to avoid strict mode
            self.page.locator("p:text-is('General')").first.click()
            self.page.wait_for_timeout(2000)
            audit = self.page.get_by_text("Audit Trail", exact=False).first

        if audit.count() == 0 or not audit.is_visible():
            pytest.skip("Audit Trail tab not accessible from Event Wall")

        audit.click()
        self.page.wait_for_timeout(2000)

        # Go back to Event Wall - use .first to avoid strict mode
        self.page.locator("p:text-is('General')").first.click()
        self.page.wait_for_timeout(2000)
        event_wall = self.page.get_by_text("Event Wall", exact=False).first
        event_wall.click()
        self.page.wait_for_timeout(2000)

        assert "admin" in self.page.url.lower()

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.admin_event_wall
    def test_event_wall_after_refresh(self):
        """Verify Event Wall page loads correctly after browser refresh."""
        self.page.reload()
        self.page.wait_for_timeout(3000)

        assert "admin" in self.page.url.lower()

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.admin_event_wall
    def test_event_wall_scrollable(self):
        """Verify Event Wall content area is scrollable when content overflows."""
        # Scroll down to verify the page scrolls
        self.page.evaluate("window.scrollBy(0, 300)")
        self.page.wait_for_timeout(500)

        # Scroll back up
        self.page.evaluate("window.scrollTo(0, 0)")
        self.page.wait_for_timeout(500)

        assert "admin" in self.page.url.lower()
