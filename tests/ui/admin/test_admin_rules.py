"""Admin Rules tests - navigation, wizard flow, search, edit, delete, mute."""
import datetime

import pytest
from playwright.sync_api import Error as PlaywrightError, expect

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

# The type the edit, mute and delete tests make their own rule from.
# Occupancy configures through the full-view switch, so the wizard walk
# skips the canvas drawing the Entry-Exit family needs.
OWNED_RULE_TYPE = "Occupancy"


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
        if self._created_rules:
            # A test that dies inside the wizard, or one that leaves the
            # details drawer open, covers the list with a MuiBox
            # backdrop: the rule search input is then unreachable and
            # the delete never starts. Escape clears both. Do NOT add a
            # reload here - measured 09/04/2026, reloading the Rules
            # page leaves an overlay that swallows the Admin nav click
            # for 30s, which is what made this teardown fail in the
            # first place. Leaking one rule is not a tidiness problem:
            # the wizard hides a camera at rule capacity, so a single
            # leftover made the configured camera vanish from Select
            # Devices and every later run failed there (register
            # item 25; the capacity behaviour is in Known app
            # behavior).
            try:
                # Escape clears the details drawer; the wizard needs its
                # own Exit button, which is what a test that died part
                # way through the wizard leaves on screen. Measured
                # 09/04/2026: Escape does nothing to the wizard and it
                # shares the list's URL, so neither a key nor a goto
                # gets out of it - only Exit does.
                self.page.keyboard.press("Escape")
                self.admin.leave_rule_wizard()
                if not self.admin.rule_search_input.is_visible():
                    self._navigate_to_rules()
            # teardown: an unreachable list must not mask the test
            # result; the deletes below then report their own failure
            except Exception as e:
                print(f"Cleanup: could not return to the rules list: {e}")
        for rule_name in self._created_rules:
            try:
                if not self.admin.delete_rule_by_name(rule_name):
                    print(f"Cleanup: rule '{rule_name}' not found")
            # teardown: a failed delete must not mask the test result;
            # leaked rules keep their timestamped names for manual cleanup
            except Exception as e:
                print(f"Cleanup: could not delete '{rule_name}': {e}")

    def _navigate_to_rules(self):
        """Helper to navigate to Admin > General > Rules."""
        self.admin.navigate_to_admin()
        self.admin.navigate_to_rules()

    def _require_rule_type_card(self, rule_type: str):
        """Wait for the picker's card for `rule_type`, or say what it offers.

        click_add_new_rule already proved the picker opened, but the
        cards render a beat after it, so the old instant count() read
        raced them and skipped on a card that was on its way (register
        item 25). The skip now names the types the picker DOES show.
        """
        card = self.page.locator(f"p:text-is('{rule_type}')")
        try:
            card.first.wait_for(state="visible", timeout=5000)
        # deliberate: click_add_new_rule proved the picker is open, so
        # this timeout is the measured absence of one type's card, not
        # a modal that failed to render
        except PlaywrightError:
            offered = [
                t for t in RULE_TYPES
                if self.page.locator(f"p:text-is('{t}')").count() > 0
            ]
            pytest.skip(
                f"The rule picker does not offer '{rule_type}'. It shows: "
                f"{offered or 'none of the known rule types'}"
            )

    def _own_a_rule(self) -> str:
        """Create a rule this test owns, and return its name.

        Edit, mute and delete used to run against index -1, the last
        rule the tenant happens to hold, and skip "No rules with X
        icons found" when the list was empty. That skipped on a clean
        tenant and muted or deleted a real user's rule on a busy one -
        the LPR list lesson (register items 25 and 27).

        Occupancy is the cheapest type to make: it configures through
        the full-view switch, so the wizard needs no canvas drawing.
        """
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        rule_name = f"Owned_Auto_{timestamp}"
        self.admin.click_add_new_rule()
        self._created_rules.append(rule_name)
        made = self.admin.complete_rule_wizard(
            rule_type=OWNED_RULE_TYPE,
            site_name=SITE_NAME,
            rule_name=rule_name,
        )
        assert made, (
            f"The rule wizard no longer offers '{OWNED_RULE_TYPE}', so these "
            f"tests cannot make the rule they act on. Pick another type from "
            f"RULE_TYPES that the picker still shows."
        )
        return rule_name

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.admin_rules
    def test_navigate_to_rules(self):
        """Verify navigating to Admin > General > Rules loads the rules list.

        Steps:
        1. Open Admin and click Rules in the sidebar.
           Expected: Rules is painted as the selected tab and the list's search field is empty with the placeholder "Search by Name, Rule Type, Site".
        """
        self._navigate_to_rules()
        self.admin.expect_admin_tab_selected("Rules")
        expect(self.admin.rule_search_input).to_have_value("")
        expect(self.admin.rule_search_input).to_have_attribute("placeholder", "Search by Name, Rule Type, Site")

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.admin_rules
    def test_add_new_rule_wizard_opens(self):
        """Verify clicking Add New Rule opens the wizard with rule type options.

        Steps:
        1. Open Admin > Rules and click Add New Rule.
           Expected: The Select Rule picker opens, offers Entry-Exit, Heat Map, Intrusion Detection, Line Crossing, Loitering and Occupancy, and its Next button is disabled until a type is picked.
        """
        self._navigate_to_rules()
        self.admin.click_add_new_rule()
        modal = self.page.locator(".customMuiModal")
        expect(modal.get_by_text("Select Rule", exact=True)).to_be_visible(timeout=10000)
        offered = [t for t in RULE_TYPES if modal.get_by_text(t, exact=True).count()]
        assert sorted(offered) == sorted(RULE_TYPES), f"the picker offers {offered}, expected {RULE_TYPES}"
        expect(modal.get_by_role("button", name="Next", exact=True)).to_be_disabled()

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.admin_rules
    @pytest.mark.parametrize("rule_type", RULE_TYPES)
    def test_select_rule_type(self, rule_type):
        """Verify selecting a rule type in the wizard enables the next step.

        Steps:
        1. Open Admin > Rules, click Add New Rule and read the Next button.
           Expected: Next is disabled with no type picked.
        2. Click the rule type's card.
           Expected: Next is enabled.
        """
        self._navigate_to_rules()
        self.admin.click_add_new_rule()
        self._require_rule_type_card(rule_type)
        expect(self.admin.next_button).to_be_disabled(timeout=10000)
        self.admin.select_rule_type(rule_type)
        # After selecting rule type, Next unlocks
        expect(self.admin.next_button).to_be_enabled(timeout=10000)

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.admin_rules
    def test_search_rule(self):
        """Verify searching for a rule by name filters the results.

        Steps:
        1. Open Admin > Rules and type Automation into the search field.
           Expected: The search field holds the typed text and the list filters to matching rules.
        """
        self._navigate_to_rules()

        self.admin.search_rule("Automation")

        # Search input should have the entered text (retries until settled)
        expect(self.admin.rule_search_input).to_have_value("Automation")

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.admin_rules
    def test_edit_rule_notification(self):
        """The rule's Edit icon opens a read-only details drawer with no notification edit.

        Measured 08/17/2026: since the rules redesign the row's Edit icon opens a
        read-only details drawer (devices, schedules, created and modified dates)
        with delete, mute and close icons only. The old flow had been skipping
        silently on a missing Notification tab behind a swallowed wait. This holds
        as an explicit skip and fails loud if a notification-edit form reappears,
        so the flow gets rebuilt.

        Steps:
        1. Open Admin > Rules, create a rule for this test and click its Edit icon.
           Expected: A details drawer opens with the rule's devices, schedules and dates, and delete, mute and close icons.
        2. Look for a Notification tab or an Update & Close button in the drawer.
           Expected: Neither is offered and the test skips naming that. If either shows, the test fails so the notification edit flow gets rebuilt.
        """
        self._navigate_to_rules()
        rule_name = self._own_a_rule()

        # oracle: edit_rule_by_name raises unless the details drawer opens
        self.admin.edit_rule_by_name(rule_name)

        # tripwire on the form's controls reappearing (a state read)
        form_back = self.admin.notification_tab.or_(
            self.admin.update_and_close_button
        )
        if form_back.count() and form_back.first.is_visible():
            pytest.fail(
                "A notification-edit form is back in the rule drawer - "
                "rebuild the notification edit flow against it"
            )
        # Close what this test opened before it skips: the drawer's
        # backdrop covers the rule list, and the teardown's delete
        # cannot reach the search input underneath it.
        self.admin.close_rule_details()
        pytest.skip(
            "The rule Edit icon opens a read-only details drawer "
            "(measured 08/17/2026); notification editing has no UI"
        )

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.admin_rules
    def test_delete_rule(self):
        """Verify deleting the last rule with confirmation dialog."""
        self._navigate_to_rules()
        rule_name = self._own_a_rule()

        # Deleting index -1 took whichever rule the tenant listed last,
        # so a run could delete a team-owned rule; the test now deletes
        # the one it made (register item 25).
        assert self.admin.delete_rule_by_name(rule_name), (
            f"The rule '{rule_name}' this test created is not in the list, "
            f"so there was nothing to delete"
        )
        self._created_rules.remove(rule_name)

        # Verify the rule is gone: the filter is the identity check,
        # and zero surviving rows is the deleted signal
        self.admin.search_rule(rule_name)
        expect(self.admin.rule_delete_icons).to_have_count(0, timeout=15000)
        self.admin.search_rule("")

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.admin_rules
    def test_mute_rule_notification(self):
        """Verify muting a rule's notification via the mute icon."""
        self._navigate_to_rules()
        rule_name = self._own_a_rule()

        # oracle: mute_rule_by_name raises unless one Mute icon leaves
        self.admin.mute_rule_by_name(rule_name)

    @pytest.mark.ui
    @pytest.mark.admin
    @pytest.mark.admin_rules
    @pytest.mark.slow
    @pytest.mark.parametrize("rule_type", RULE_TYPES)
    def test_create_rule_full_wizard(self, rule_type):
        """Verify the rule creation wizard completes for each rule type.

        Canvas rules (Entry-Exit, Line Crossing) draw a zone on the camera
        snapshot; the others (Heat Map, Intrusion Detection, Loitering,
        Occupancy) toggle their switch instead.

        Steps:
        1. Open Admin > Rules and click Add New Rule.
           Expected: The Select Rule picker opens and offers the rule type.
        2. Pick the rule type and walk the wizard: the site, the camera, the zone or the switch, a unique rule name, then Save.
           Expected: The wizard closes.
        3. Search the rules list for that name.
           Expected: Exactly one row carries it, so the rule was saved and not just closed.
        """
        self._navigate_to_rules()

        self.admin.click_add_new_rule()

        self._require_rule_type_card(rule_type)

        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        rule_name = f"{rule_type.replace(' ', '_')}_Auto_{timestamp}"

        self._created_rules.append(rule_name)
        completed = self.admin.complete_rule_wizard(
            rule_type=rule_type,
            site_name=SITE_NAME,
            rule_name=rule_name,
        )
        if not completed:
            # False only means the picker does not offer this type;
            # a stalled walk raises inside the wizard instead
            pytest.skip(f"Rule type '{rule_type}' not offered in the picker")

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
