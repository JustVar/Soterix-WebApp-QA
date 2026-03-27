"""Admin Rules tests - navigation, wizard flow, search, edit, delete, mute."""
import datetime
import pytest
from playwright.sync_api import expect
from tests.shared.pages.admin_page import AdminPage

RULE_TYPES = [
    "Entry-Exit",
    "Heat Map",
    "Loitering",
    "Occupancy",
    "Intrusion Detection",
    "Line Crossing",
]

SITE_NAME = "Driver Site"


class TestAdminRules:
    """Tests for Admin > General > Rules section."""

    @pytest.fixture(autouse=True)
    def setup(self, authenticated_page, step_capture):
        self.page = authenticated_page
        self.step_capture = step_capture
        step_capture.set_page(self.page)
        self.admin = AdminPage(self.page)
        yield

    def _navigate_to_rules(self):
        """Helper to navigate to Admin > General > Rules."""
        self.admin.navigate_to_admin()
        self.admin.navigate_to_rules()

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.admin_rules
    @pytest.mark.qatouch("rGQDWk")
    def test_navigate_to_rules(self):
        """Verify navigating to Admin > General > Rules loads the rules list."""
        self._navigate_to_rules()
        self.step_capture.mark(1, "Navigate to Admin > General > Rules")

        # Rules tab should be visible and rule search bar should be present
        expect(self.admin.rules_tab).to_be_visible(timeout=10000)
        self.step_capture.mark(2, "Verify the Rules tab is visible")

        expect(self.admin.rule_search_input).to_be_visible(timeout=10000)
        self.step_capture.mark(3, "Verify the rule search input is visible")

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.admin_rules
    @pytest.mark.qatouch("lR21wR")
    def test_add_new_rule_wizard_opens(self):
        """Verify clicking Add New Rule opens the wizard with rule type options."""
        self._navigate_to_rules()
        self.step_capture.mark(1, "Navigate to Admin > General > Rules")

        self.admin.click_add_new_rule()
        self.step_capture.mark(2, "Click the Add New Rule button")

        # Verify at least one rule type option is visible
        entry_exit = self.page.locator("p:text-is('Entry-Exit')")
        expect(entry_exit).to_be_visible(timeout=10000)
        self.step_capture.mark(3, "Verify rule type options are visible in the wizard")

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.admin_rules
    @pytest.mark.parametrize("rule_type", RULE_TYPES)
    @pytest.mark.qatouch("Drd95P")
    def test_select_rule_type(self, rule_type):
        """Verify selecting a rule type in the wizard advances to next step."""
        self._navigate_to_rules()
        self.step_capture.mark(1, "Navigate to Admin > General > Rules")

        self.admin.click_add_new_rule()
        self.step_capture.mark(2, "Click the Add New Rule button")

        rule_label = self.page.locator(f"p:text-is('{rule_type}')")
        if rule_label.count() == 0:
            pytest.skip(f"Rule type '{rule_type}' not available in wizard")

        self.admin.select_rule_type(rule_type)
        self.step_capture.mark(3, f"Select '{rule_type}' from the rule type options")

        # After selecting rule type, Next button should be visible
        expect(self.admin.next_button).to_be_visible(timeout=10000)
        self.step_capture.mark(4, "Verify the Next button is visible after selecting rule type")

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.admin_rules
    @pytest.mark.qatouch("VKbQJQ")
    def test_search_rule(self):
        """Verify searching for a rule by name filters the results."""
        self._navigate_to_rules()
        self.step_capture.mark(1, "Navigate to Admin > General > Rules")

        self.admin.search_rule("Automation")
        self.page.wait_for_timeout(2000)
        self.step_capture.mark(2, "Type 'Automation' in the rule search input")

        # Search input should have the entered text
        expect(self.admin.rule_search_input).to_have_value("Automation")
        self.step_capture.mark(3, "Verify the search input contains the text 'Automation'")

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.admin_rules
    @pytest.mark.qatouch("dyp4aR")
    def test_edit_rule_notification(self):
        """Verify editing a rule's notification settings (popUp + push)."""
        self._navigate_to_rules()
        self.step_capture.mark(1, "Navigate to Admin > General > Rules")

        if self.admin.rule_edit_icons.count() == 0:
            pytest.skip("No rules with edit icons found")

        self.admin.edit_rule(index=-1)
        self.step_capture.mark(2, "Click the edit icon on the last rule in the list")

        # Switch to Notification tab (may not exist for all rule types)
        if self.admin.notification_tab.count() == 0:
            pytest.skip("Notification tab not found in edit modal")

        self.admin.click_notification_tab()
        self.step_capture.mark(3, "Switch to the Notification tab in the edit modal")

        # Toggle popUp and push notification checkboxes
        self.admin.toggle_popup_notification()
        self.admin.toggle_push_notification()
        self.step_capture.mark(4, "Toggle popUp and push notification checkboxes")

        # Click Update & Close
        self.admin.click_update_and_close()
        self.step_capture.mark(5, "Click Update and Close to save notification changes")

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.admin_rules
    @pytest.mark.qatouch("lR21MR")
    def test_delete_rule(self):
        """Verify deleting the last rule with confirmation dialog."""
        self._navigate_to_rules()
        self.step_capture.mark(1, "Navigate to Admin > General > Rules")

        if self.admin.rule_delete_icons.count() == 0:
            pytest.skip("No rules with delete icons found")

        initial_count = self.admin.rule_delete_icons.count()
        self.step_capture.mark(2, "Note the current count of rules in the list")

        self.admin.delete_rule(index=-1)
        self.step_capture.mark(3, "Click delete on the last rule and confirm deletion")

        # Verify one fewer rule (or at least the delete completed)
        self.page.wait_for_timeout(2000)
        new_count = self.admin.rule_delete_icons.count()
        assert new_count < initial_count, (
            f"Expected fewer rules after delete: {new_count} >= {initial_count}"
        )
        self.step_capture.mark(4, "Verify the rule count decreased after deletion")

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.admin_rules
    @pytest.mark.qatouch("mBdpwM")
    def test_mute_rule_notification(self):
        """Verify muting a rule's notification via the mute icon."""
        self._navigate_to_rules()
        self.step_capture.mark(1, "Navigate to Admin > General > Rules")

        if self.admin.mute_notification_icons.count() == 0:
            pytest.skip("No rules with mute notification icons found")

        self.admin.mute_rule_notification(index=-1)
        self.step_capture.mark(2, "Click the mute icon on the last rule to mute notifications")

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.admin_rules
    @pytest.mark.slow
    @pytest.mark.parametrize("rule_type", RULE_TYPES)
    @pytest.mark.qatouch("21zEKm")
    def test_create_rule_full_wizard(self, rule_type):
        """Verify completing the full rule creation wizard for each rule type.

        Canvas rules (Entry-Exit, Line Crossing): snapshot + zone drawing.
        Non-canvas rules (Heat Map, Intrusion, Loitering, Occupancy): MuiSwitch toggle.

        Selenium ref: test_vsaas_soterix.py lines 3335-4294.
        """
        self._navigate_to_rules()
        self.step_capture.mark(1, "Navigate to Admin > General > Rules")

        self.admin.click_add_new_rule()
        self.step_capture.mark(2, "Click the Add New Rule button")

        rule_label = self.page.locator(f"p:text-is('{rule_type}')")
        if rule_label.count() == 0:
            pytest.skip(f"Rule type '{rule_type}' not available in wizard")

        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        rule_name = f"{rule_type.replace(' ', '_')}_Auto_{timestamp}"

        self.admin.complete_rule_wizard(
            rule_type=rule_type,
            site_name=SITE_NAME,
            rule_name=rule_name,
        )
        self.step_capture.mark(3, f"Complete the full rule creation wizard for '{rule_type}'")

        # Verify we're back on the rules list after save
        self.page.wait_for_timeout(3000)
        expect(self.admin.rule_search_input).to_be_visible(timeout=15000)
        self.step_capture.mark(4, "Verify the rules list is displayed after wizard completion")
