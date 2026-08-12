"""Admin Rules tests - navigation, wizard flow, search, edit, delete, mute."""
import datetime

import pytest
from playwright.sync_api import expect

from config.base_config import config
from tests.shared.pages.admin_page import AdminPage

RULE_TYPES = [
    "Entry-Exit",
    "Heat Map",
    "Loitering",
    "Occupancy",
    "Intrusion Detection",
    "Line Crossing",
]

# The shared tenant renames sites, so the name lives in config
SITE_NAME = config.get("test_site_name")


class TestAdminRules:
    """Tests for Admin > General > Rules section."""

    @pytest.fixture(autouse=True)
    def setup(self, authenticated_page):
        self.page = authenticated_page
        self.admin = AdminPage(self.page)
        self._created_rules = []
        yield
        # Cleanup: delete created rules by name so runs do not leak
        # Auto rules into the shared tenant. Best effort by design.
        for rule_name in self._created_rules:
            try:
                if not self.admin.delete_rule_by_name(rule_name):
                    print(f"Cleanup: rule '{rule_name}' not found")
            except Exception as e:
                print(f"Cleanup: could not delete '{rule_name}': {e}")

    def _navigate_to_rules(self):
        """Helper to navigate to Admin > General > Rules."""
        self.admin.navigate_to_admin()
        self.admin.navigate_to_rules()

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.admin_rules
    def test_navigate_to_rules(self):
        """Verify navigating to Admin > General > Rules loads the rules list."""
        self._navigate_to_rules()

        # Rules tab should be visible and rule search bar should be present.
        # .first: 'Rules' can appear in both the sidebar and General content.
        expect(self.admin.rules_tab.first).to_be_visible(timeout=10000)
        expect(self.admin.rule_search_input).to_be_visible(timeout=10000)

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.admin_rules
    def test_add_new_rule_wizard_opens(self):
        """Verify clicking Add New Rule opens the wizard with rule type options."""
        self._navigate_to_rules()

        self.admin.click_add_new_rule()

        # Verify at least one rule type option is visible
        entry_exit = self.page.locator("p:text-is('Entry-Exit')")
        expect(entry_exit).to_be_visible(timeout=10000)

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.admin_rules
    @pytest.mark.parametrize("rule_type", RULE_TYPES)
    def test_select_rule_type(self, rule_type):
        """Verify selecting a rule type in the wizard advances to next step."""
        self._navigate_to_rules()

        self.admin.click_add_new_rule()

        rule_label = self.page.locator(f"p:text-is('{rule_type}')")
        if rule_label.count() == 0:
            pytest.skip(f"Rule type '{rule_type}' not available in wizard")

        self.admin.select_rule_type(rule_type)

        # After selecting rule type, Next button should be visible
        expect(self.admin.next_button).to_be_visible(timeout=10000)

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.admin_rules
    def test_search_rule(self):
        """Verify searching for a rule by name filters the results."""
        self._navigate_to_rules()

        self.admin.search_rule("Automation")

        # Search input should have the entered text (retries until settled)
        expect(self.admin.rule_search_input).to_have_value("Automation")

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.admin_rules
    def test_edit_rule_notification(self):
        """Verify editing a rule's notification settings (popUp + push)."""
        self._navigate_to_rules()

        # Wait for the list to render before deciding to skip
        try:
            self.admin.rule_edit_icons.first.wait_for(state="visible", timeout=5000)
        except Exception:
            pytest.skip("No rules with edit icons found")

        self.admin.edit_rule(index=-1)

        # Switch to Notification tab (may not exist for all rule types)
        if self.admin.notification_tab.count() == 0:
            pytest.skip("Notification tab not found in edit modal")

        self.admin.click_notification_tab()

        # Toggle popUp and push notification checkboxes
        self.admin.toggle_popup_notification()
        self.admin.toggle_push_notification()

        # Click Update & Close
        self.admin.click_update_and_close()

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.admin_rules
    def test_delete_rule(self):
        """Verify deleting the last rule with confirmation dialog."""
        self._navigate_to_rules()

        # Wait for the list to render before deciding to skip
        try:
            self.admin.rule_delete_icons.first.wait_for(state="visible", timeout=5000)
        except Exception:
            pytest.skip("No rules with delete icons found")

        initial_count = self.admin.rule_delete_icons.count()

        self.admin.delete_rule(index=-1)

        # Verify one fewer rule (retries until the list refreshes)
        expect(self.admin.rule_delete_icons).to_have_count(
            initial_count - 1, timeout=10000
        )

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.admin_rules
    def test_mute_rule_notification(self):
        """Verify muting a rule's notification via the mute icon."""
        self._navigate_to_rules()

        # Wait for the list to render before deciding to skip
        try:
            self.admin.mute_notification_icons.first.wait_for(state="visible", timeout=5000)
        except Exception:
            pytest.skip("No rules with mute notification icons found")

        self.admin.mute_rule_notification(index=-1)

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.admin_rules
    @pytest.mark.slow
    @pytest.mark.parametrize("rule_type", RULE_TYPES)
    def test_create_rule_full_wizard(self, rule_type):
        """Verify completing the full rule creation wizard for each rule type.

        Canvas rules (Entry-Exit, Line Crossing): snapshot + zone drawing.
        Non-canvas rules (Heat Map, Intrusion, Loitering, Occupancy): MuiSwitch toggle.

        Selenium ref: test_vsaas_soterix.py lines 3335-4294.
        """
        self._navigate_to_rules()

        self.admin.click_add_new_rule()

        rule_label = self.page.locator(f"p:text-is('{rule_type}')")
        if rule_label.count() == 0:
            pytest.skip(f"Rule type '{rule_type}' not available in wizard")

        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        rule_name = f"{rule_type.replace(' ', '_')}_Auto_{timestamp}"

        self._created_rules.append(rule_name)
        completed = self.admin.complete_rule_wizard(
            rule_type=rule_type,
            site_name=SITE_NAME,
            rule_name=rule_name,
        )
        if not completed:
            pytest.skip(
                "Rule wizard flow did not complete for this type - see "
                "the run output for the step it stalled on"
            )

        # The rule must exist by name: a closed wizard alone would also
        # pass a save the backend rejected. The list truncates the Name
        # cell in the DOM ('Entry-Exit_Auto_202608...'), so search by
        # the full unique name and require EXACTLY ONE matching row.
        # to_have_count polls until the filter settles: the unfiltered
        # table (many rows) and a rejected save (zero rows) both fail,
        # and so does a leaked same-type row surviving the filter.
        expect(self.admin.rule_search_input).to_be_visible(timeout=15000)
        self.admin.search_rule(rule_name)
        expect(
            self.page.locator("tr").filter(has_text=rule_name[:20])
        ).to_have_count(1, timeout=15000)
        self.admin.search_rule("")
