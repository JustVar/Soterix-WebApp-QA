"""Admin Page Object Model.

Shared page object for Admin section navigation, user management,
rules management, and sites/camera group management.
Used by Admin Users, Admin Sites, and Admin Rules test modules.
"""
import datetime
import time

from playwright.sync_api import Error as PlaywrightError, Page, expect


class AdminPage:
    """Page object for the Admin section."""

    def __init__(self, page: Page):
        self.page = page

        # Navigation
        self.admin_nav_link = page.locator("a[href*='admin']")
        self.users_tab = page.locator("p:text-is('Users')")
        self.sites_tab = page.locator("p:text-is('Sites')")
        self.general_tab = page.locator("p:text-is('General')")
        self.rules_tab = page.locator("p:text-is('Rules')")

        # User management - buttons
        self.add_user_button = page.locator("button.add-btn").first
        self.save_button = page.locator("button.add-btn.save-btn")

        # User form fields
        self.name_input = page.locator("input[name='name'].modalForm-input")
        self.last_name_input = page.locator(
            "input[name='lastName'].modalForm-input"
        )
        self.email_input = page.locator(
            "input[name='mailId'].modalForm-input"
        )
        self.role_dropdown = page.locator(
            "div.MuiStack-root.modalForm-input"
        )

        # Search
        self.search_input = page.locator("input[placeholder='Search']")

        # User row actions
        self.options_icon = page.locator("img[src*='optionIcon']")
        # img asset icon: alt unreliable, locate by src (CONVENTIONS > Locators)
        self.delete_icon = page.locator("img[src*='delete-icon']")
        self.delete_confirm = page.locator(
            "button:has-text('Delete'), div.MuiBox-root:text-is('Delete')"
        )

        # User status toggle. Class, not get_by_role('switch'): this
        # build's MUI Switch input carries no role attribute (a bare
        # type=checkbox, probed 08/24/2026), so the role matches nothing
        self.user_switch = page.locator(".MuiSwitch-root")

        # Role filter
        self.role_filter_dropdown = page.locator("div[role='combobox']")
        # The filter is a MUI Select: its items render as role=option
        # inside a role=listbox, not menuitems (probed 08/24/2026)
        self.role_options = page.get_by_role("option")

        # Rules management
        self.add_new_rule_button = page.locator(
            "#topRightBox button:has-text('Add New Rule')"
        )
        self.next_button = page.locator(
            "button:has-text('Next')"
        )
        self.rule_search_input = page.locator(
            "input.input-search-bar[placeholder*='Rule Type']"
        )
        self.rule_edit_icons = page.locator("img[aria-label='Edit']")
        # the drawer the Edit icon opens (read-only details, see edit_rule)
        self.rule_details_panel = page.locator(
            "[class*='modal' i], .customMuiModal, [role='dialog']"
        ).filter(has_text="Details").first
        self.rule_delete_icons = page.locator("img[aria-label='Delete']")
        self.rule_delete_confirm = page.locator(
            "button.btn-primary:has-text('Delete')"
        )
        self.notification_tab = page.locator(
            "button.btn-modalTab:has-text('Notification')"
        )
        self.update_and_close_button = page.locator(
            "button.btn-primary:has-text('Update & Close')"
        )
        self.popup_checkbox = page.locator("input[name='popUp']")
        self.push_checkbox = page.locator("input[name='push']")
        self.mute_notification_icons = page.locator(
            "img[aria-label='Mute Notification']"
        )
        self.canvas = page.locator("canvas.upper-canvas")

        # Sites management
        self.list_view_toggle = page.locator("img[alt='tableIcon']")
        # img asset icon: alt unreliable, locate by src (CONVENTIONS > Locators)
        self.grid_view_toggle = page.locator("img[src*='icon-grid']")
        self.online_status_icons = page.locator("img[alt='Online']")
        self.offline_status_icons = page.locator("img[alt='Offline']")
        # img asset icon: alt unreliable, locate by src (CONVENTIONS > Locators)
        self.sort_az_icon = page.locator("img[src*='a-to-z-sort']")
        # img asset icon: alt unreliable, locate by src (CONVENTIONS > Locators)
        self.sort_za_icon = page.locator("img[src*='z-to-a-sort']")
        self.accordion_icon = page.locator(
            # img asset icon: alt unreliable, locate by src (CONVENTIONS > Locators)
            "img[src*='downAccordionIcon']"
        )
        # Exact text node: a :has-text MuiBox union matches ancestor
        # boxes too, and clicking their center misses the item
        self.create_new_button = page.get_by_text("Create New", exact=True)
        self.group_name_input = page.locator(
            "input[placeholder='Type here...']"
        )
        self.camera_search_input = page.locator(
            "input#outlined-adornment-search"
        )
        self.camera_checkbox = page.locator(
            "input.PrivateSwitchBase-input[type='checkbox']"
        )
        self.create_button = page.locator(
            "div.MuiBox-root:text-is('Create')"
        )
        self.group_edit_icons = page.locator(
            "img[alt='edit'].edit-icon"
        )
        self.group_delete_icons = page.locator(
            "img[alt='delete'].delete-icon"
        )
        # The Delete Group confirmation renders in a customMuiModal;
        # its Delete control may be a button or a MuiBox. Modal-scoped
        # only: unscoped legacy candidates can outrank these in DOM
        # order via .first
        self.group_delete_confirm = page.locator(
            ".customMuiModal button:has-text('Delete'), "
            ".customMuiModal div.MuiBox-root:text-is('Delete')"
        ).first

    # --- Navigation ---

    def navigate_to_admin(self):
        """Navigate to the Admin section via sidebar nav link."""
        self.admin_nav_link.click()
        try:
            self.page.wait_for_url("**/admin**", timeout=30000)
        except Exception:
            # SPA may not change URL immediately - verify via visible element
            if "admin" not in self.page.url.lower():
                raise
        # The sidebar tabs are the signal that the Admin section rendered
        self.users_tab.first.wait_for(state="visible", timeout=15000)

    def navigate_to_users(self):
        """Click the Users tab in the Admin sidebar.

        Uses .first because 'Users' text appears twice on the Admin page
        (sidebar tab + page header).
        """
        self.users_tab.first.wait_for(state="visible", timeout=10000)
        self.users_tab.first.click()
        # The Add button is the signal that the Users content rendered
        self.add_user_button.wait_for(state="visible", timeout=15000)

    def navigate_to_sites(self):
        """Click the Sites tab in the Admin sidebar.

        Uses .first because 'Sites' text appears twice on the Admin page
        (sidebar tab + page header).
        """
        self.sites_tab.first.wait_for(state="visible", timeout=10000)
        self.sites_tab.first.click()
        # The search field is the signal that the Sites content rendered
        self.page.locator("input[placeholder*='Search']").first.wait_for(
            state="visible", timeout=15000
        )

    # --- User CRUD ---

    def click_add_user(self):
        """Click the Add User button to open the form."""
        self.add_user_button.wait_for(state="visible", timeout=10000)
        self.add_user_button.click()
        # The form's first field is the signal that the modal opened
        self.name_input.wait_for(state="visible", timeout=10000)

    def fill_user_form(self, name: str, last_name: str, email: str):
        """Fill out the Add User form fields."""
        self.name_input.wait_for(state="visible", timeout=10000)
        self.name_input.fill(name)
        self.last_name_input.fill(last_name)
        self.email_input.fill(email)

    def select_role(self, role_index: int = 1):
        """Open the role dropdown in the form and select a role by index.

        Default index 1 = Admin (0-based in the sitesBox list, but li[2] in Selenium = index 1 here).
        """
        self.role_dropdown.click()

        # The role options appear in #sitesBox container; the wait below is
        # the dropdown-open signal
        options = self.page.locator("#sitesBox li")
        options.nth(role_index).wait_for(state="visible", timeout=10000)
        options.nth(role_index).click()

    def save_user(self):
        """Click the Save button to submit the user form.

        Waits for the form to close. A validation failure keeps the form
        open, so the wait raises instead of silently moving on.
        """
        self.save_button.click()
        self.name_input.wait_for(state="hidden", timeout=15000)

    def search_user(self, search_text: str):
        """Type in the user search input.

        Filtering has no completion signal (zero matches is a valid result),
        so this method does not wait. Callers wait on the row or control
        they need next, with a bounded timeout.
        """
        self.search_input.wait_for(state="visible", timeout=10000)
        self.search_input.clear()
        self.search_input.fill(search_text)

    def delete_user(self, match_text: str | None = None):
        """Delete a listed user via options icon > delete > confirm.

        With match_text, the options icon is scoped to the user card
        (.MuiPaper-root) containing that text, so an unfiltered or
        still-filtering list can never hand the delete an arbitrary
        first user - the 08/13/2026 near-miss: the server-side filter
        was still running, the pre-filter rows were visible, and the
        first options icon belonged to a real tenant user. Without
        match_text the first icon is used, which is only safe on a
        list the caller has verified as filtered.
        """
        if match_text:
            # same selector as options_icon: these render as img
            # assets on this page (probed), not MUI svg icons
            icon = self.page.locator(
                ".MuiPaper-root", has_text=match_text
            # img asset icon: alt unreliable, locate by src (CONVENTIONS > Locators)
            ).locator("img[src*='optionIcon']").first
        else:
            icon = self.options_icon.first
        icon.wait_for(state="visible", timeout=10000)
        icon.click()

        self.delete_icon.wait_for(state="visible", timeout=5000)
        self.delete_icon.click()

        # Click the confirm Delete button in the dialog - try multiple
        # selectors, waiting for the dialog rather than sleeping
        confirm = self.page.get_by_role("button", name="Delete", exact=True)
        clicked = None
        try:
            confirm.first.wait_for(state="visible", timeout=5000)
            confirm.first.click()
            clicked = confirm.first
        except Exception:
            # Fallback: broader text match for MUI styled "buttons" (div-based)
            fallback = self.page.locator(
                "div.MuiBox-root:text-is('Delete'), "
                "button:text-is('Delete'), "
                "span:text-is('Delete')"
            )
            if fallback.count() > 0:
                fallback.first.click()
                clicked = fallback.first
            else:
                # Last resort: click any visible "Delete" text in a dialog
                last_resort = self.page.locator("[role='dialog'] >> text=Delete").first
                last_resort.click()
                clicked = last_resort

        # The confirm control disappearing is the signal the delete was
        # accepted. Waiting on the clicked element (not a blind
        # [role='dialog'] lookup) because the confirm popup is often a
        # div-based MUI box with no dialog role, and a zero-match hidden
        # wait returns instantly with no settle at all.
        if clicked is not None:
            try:
                clicked.wait_for(state="hidden", timeout=15000)
            except Exception:
                print("[ADMIN] Delete confirm did not close within 15s - "
                      "the delete may have been rejected")

    def toggle_user_status(self, user_text: str | None = None):
        """Toggle the active/suspended switch for a user.

        Pass user_text to scope the click to the card that contains that
        text. Without it the first switch on the page is used, which can
        belong to another account while a search filter is still applying -
        never do that after search_user().
        """
        if user_text:
            # XPath ancestor hop: the nearest container around the matched
            # text that holds a switch is that user's card. Class-keyed
            # like user_switch: the switch input has no role to scope on
            switch = self.page.get_by_text(user_text).first.locator(
                "xpath=ancestor::*[.//*[contains(@class,'MuiSwitch-root')]][1]"
            ).locator(".MuiSwitch-root").first
        else:
            switch = self.user_switch.first
        switch.wait_for(state="visible", timeout=10000)
        # a switch mid-server-reconcile reports not-enabled for a while
        # (measured on half-created users, 08/17/2026): give it a
        # bounded chance to become usable, then fail loud - a click that
        # never lands is a real failure, not a settle
        checkbox = switch.locator("input[type='checkbox']").first
        try:
            expect(checkbox).to_be_enabled(timeout=15000)
        except AssertionError:
            raise AssertionError(
                f"The status switch for {user_text or 'the first user'} "
                "stayed disabled for 15s - the account is not toggleable"
            ) from None
        before = checkbox.is_checked()
        switch.click()
        # the checked state flipping is the applied signal
        if before:
            expect(checkbox).not_to_be_checked(timeout=10000)
        else:
            expect(checkbox).to_be_checked(timeout=10000)

    # --- Role filter ---

    def get_role_options(self) -> list[str]:
        """Open the role filter dropdown and return available role names."""
        self.role_filter_dropdown.first.click()

        options = self.role_options
        options.first.wait_for(state="visible", timeout=10000)

        # The list shows only the 'All Roles' placeholder until a server
        # fetch fills it - wait for more than 1 entry before reading
        try:
            self.page.wait_for_function(
                "() => document.querySelectorAll('[role=option]').length > 1",
                timeout=10000,
            )
        # best effort settle wait: the caller asserts on the returned
        # role names, so an unfilled list fails there
        except Exception:
            pass

        role_names = []
        for i in range(options.count()):
            role_names.append(options.nth(i).inner_text().strip())
        return role_names

    def select_role_filter(self, role_name: str):
        """Select a role from the filter dropdown by name."""
        option = self.page.get_by_role(
            "option", name=role_name, exact=True
        )
        option.scroll_into_view_if_needed()
        option.click()

    # --- Rules management ---

    def navigate_to_rules(self):
        """Navigate to the Admin Rules list.

        The sidebar carries a top-level Rules entry (2026 layout); older
        builds nested Rules under General as a card. 'Rules' appears twice
        on the page (sidebar + General card), so this uses .first for the
        sidebar and falls back to the General card by its icon.
        """
        self.rules_tab.first.wait_for(state="visible", timeout=10000)
        self.rules_tab.first.click()
        try:
            # The Add button is the signal that the Rules content rendered
            self.add_new_rule_button.wait_for(state="visible", timeout=10000)
            return
        # layout probe: the older-build fallback below reaches Rules via
        # the General card and its final wait raises if neither renders
        except Exception:
            pass
        # Fallback: older layout reaches Rules through the General card
        self.general_tab.click()
        self.page.locator("img[alt='rules']").click()
        self.add_new_rule_button.wait_for(state="visible", timeout=15000)

    def click_add_new_rule(self):
        """Click the Add New Rule button to open the rule wizard."""
        self.add_new_rule_button.wait_for(state="visible", timeout=10000)
        self.add_new_rule_button.click()
        # The wizard's Next button is the signal that it opened
        self.next_button.first.wait_for(state="visible", timeout=10000)

    def select_rule_type(self, rule_type: str):
        """Select a rule type in the wizard (e.g., 'Entry-Exit', 'Heat Map')."""
        rule_label = self.page.locator(f"p:text-is('{rule_type}')")
        rule_label.wait_for(state="visible", timeout=10000)
        rule_label.click()

    def click_next(self):
        """Click the Next button in the rule creation wizard.

        Does not wait for the next step: each step's own method waits for
        the control it needs.
        """
        self.next_button.first.wait_for(state="visible", timeout=10000)
        self.next_button.first.click()

    def search_rule(self, search_text: str):
        """Type in the rule search input.

        Filtering has no completion signal (zero matches is a valid result),
        so this method does not wait. Callers wait on the row or control
        they need next, with a bounded timeout.
        """
        self.rule_search_input.wait_for(state="visible", timeout=10000)
        self.rule_search_input.clear()
        self.rule_search_input.fill(search_text)

    def edit_rule(self, index: int = -1):
        """Click the edit icon for a rule at the given index.

        Default index -1 clicks the last edit icon in the list.
        """
        self.rule_edit_icons.first.wait_for(
            state="visible", timeout=10000
        )
        count = self.rule_edit_icons.count()
        target = count + index if index < 0 else index
        self.rule_edit_icons.nth(target).scroll_into_view_if_needed()
        self.rule_edit_icons.nth(target).click()
        # The 'Edit' icon opens a read-only rule DETAILS drawer (devices,
        # schedules, created/modified audit) since the 08/2026 rules
        # redesign - measured 08/17/2026; there is no edit form or
        # Update & Close anymore. The drawer's Details heading is the
        # opened signal.
        self.rule_details_panel.wait_for(state="visible", timeout=15000)

    def click_notification_tab(self):
        """Switch to the Notification tab in the rule edit modal."""
        self.notification_tab.wait_for(state="visible", timeout=15000)
        self.notification_tab.scroll_into_view_if_needed()
        self.notification_tab.click()
        # The notification checkboxes are the signal that the tab rendered
        self.popup_checkbox.wait_for(state="attached", timeout=10000)

    def toggle_popup_notification(self):
        """Toggle the popUp notification checkbox."""
        self.popup_checkbox.wait_for(state="attached", timeout=10000)
        self.popup_checkbox.click(force=True)

    def toggle_push_notification(self):
        """Toggle the push notification checkbox."""
        self.push_checkbox.wait_for(state="attached", timeout=10000)
        self.push_checkbox.click(force=True)

    def click_update_and_close(self):
        """Click the Update & Close button in the rule edit modal."""
        self.update_and_close_button.wait_for(
            state="visible", timeout=10000
        )
        self.update_and_close_button.click()
        # The modal closing is the signal that the update was accepted
        self.update_and_close_button.wait_for(state="hidden", timeout=15000)

    def delete_rule_by_name(self, name: str) -> bool:
        """Delete the rule with the given name; False when not found.

        Name-scoped so cleanup never deletes a team-owned rule on the
        shared tenant.
        """
        self.search_rule(name)
        try:
            self.rule_delete_icons.first.wait_for(
                state="visible", timeout=5000
            )
        except Exception:
            self.search_rule("")
            return False
        self.delete_rule(0)
        self.search_rule("")
        return True

    def delete_rule(self, index: int = -1):
        """Delete a rule at the given index.

        Clicks the delete icon, then confirms the deletion.
        Default index -1 deletes the last rule in the list.
        """
        self.rule_delete_icons.first.wait_for(
            state="visible", timeout=10000
        )
        count = self.rule_delete_icons.count()
        target = count + index if index < 0 else index
        self.rule_delete_icons.nth(target).click()

        self.rule_delete_confirm.wait_for(state="visible", timeout=5000)
        self.rule_delete_confirm.click()
        # The confirm button disappearing is the signal the delete ran
        try:
            self.rule_delete_confirm.wait_for(state="hidden", timeout=15000)
        # best effort settle wait: the test caller asserts the row count
        # and the other caller is fixture cleanup
        except Exception:
            pass

    def mute_rule_notification(self, index: int = -1):
        """Click the mute notification icon for a rule.

        Default index -1 clicks the last mute icon.
        """
        self.mute_notification_icons.first.wait_for(
            state="visible", timeout=10000
        )
        count = self.mute_notification_icons.count()
        target = count + index if index < 0 else index
        self.mute_notification_icons.nth(target).click()
        # The icon's aria-label flips to Unmute once the mute lands, so
        # one fewer Mute icon is the applied signal (probe 08/25/2026)
        expect(self.mute_notification_icons).to_have_count(
            count - 1, timeout=10000
        )

    # --- Sites management ---

    def search_site(self, search_text: str):
        """Type in the site search input.

        Filtering has no completion signal (zero matches is a valid result),
        so this method does not wait. Callers wait on the card or row they
        need next, with a bounded timeout.
        """
        site_search = self.page.locator(
            "input[placeholder*='Search']"
        ).first
        site_search.wait_for(state="visible", timeout=10000)
        site_search.clear()
        site_search.fill(search_text)
        # Filtering has no completion signal (zero matches is valid);
        # callers wait on the card or row they need next

    def toggle_to_list_view(self):
        """Switch to list view on the Sites page."""
        self.list_view_toggle.wait_for(state="visible", timeout=10000)
        self.list_view_toggle.click()
        # The opposite toggle appearing is the signal the view switched
        self.grid_view_toggle.wait_for(state="visible", timeout=5000)

    def toggle_to_grid_view(self):
        """Switch to grid view on the Sites page."""
        self.grid_view_toggle.wait_for(state="visible", timeout=10000)
        self.grid_view_toggle.click()
        # The opposite toggle appearing is the signal the view switched
        self.list_view_toggle.wait_for(state="visible", timeout=5000)

    def get_site_statuses(self) -> list[dict]:
        """Return a list of {name, status} for all visible site cards.

        Looks for Online/Offline status icons adjacent to site names.
        """
        statuses = []
        online_count = self.online_status_icons.count()
        offline_count = self.offline_status_icons.count()
        statuses.append({
            "online": online_count,
            "offline": offline_count,
            "total": online_count + offline_count,
        })
        return statuses

    def get_site_versions(self) -> list[dict]:
        """Return a list of {name, version} for visible sites.

        Looks for Version: text near site name elements.
        """
        versions = []
        version_elements = self.page.locator(
            "p:has-text('Version:')"
        )
        for i in range(version_elements.count()):
            text = version_elements.nth(i).inner_text().strip()
            versions.append(text)
        return versions

    def click_site(self, site_name: str):
        """Click a site card to navigate into the site detail view.

        The detail signal is the Groups dropdown label: the redesigned
        detail has no div.site-card, and the URL does not change. A
        click that lands during list hydration is silently dropped,
        so the signal gets one retry.
        """
        # Same exact match as the old :text-is, but escaped: a site named
        # with an apostrophe returns no match instead of crashing the
        # selector parser (item 19 recipe).
        site = self.page.get_by_text(site_name, exact=True).and_(
            self.page.locator("p.MuiTypography-root")).first
        site.wait_for(state="visible", timeout=10000)
        site.click()
        detail = self.page.get_by_text("Groups:", exact=True).first
        try:
            detail.wait_for(state="visible", timeout=10000)
        except Exception:
            # Retry only while the list is still mounted (its Version
            # lines are list-only): re-clicking the site name on an
            # already-loaded detail would hit the breadcrumb instead
            if self.page.locator("p:has-text('Version:')").count() > 0:
                site.click()
            detail.wait_for(state="visible", timeout=15000)

    def get_camera_names(self) -> list[str]:
        """Camera names in the site detail list.

        The redesigned detail lists cameras as name + 'IP: <addr>'
        rows (div.site-card is gone); the name is the first line of
        the row that holds the IP line.
        """
        return self.page.evaluate(
            r"""() => [...document.querySelectorAll('body *')]
                .filter(e => e.children.length === 0
                        && e.getClientRects().length > 0
                        && /^IP: \d/.test((e.textContent || '').trim()))
                .map(e => {
                    let n = e;
                    for (let d = 0; d < 4 && n.parentElement; d++) {
                        n = n.parentElement;
                        const first = ((n.innerText || '')
                            .split('\n')[0] || '').trim();
                        if (first && !first.startsWith('IP:'))
                            return first;
                    }
                    return '';
                }).filter(Boolean)"""
        )

    def click_sort_az(self):
        """Click the A-Z sort icon.

        The sort control is one toggle icon: the list reorders on the
        click and the icon swaps to the other direction on the same
        tick (probe 08/25/2026), so the opposite icon is the signal.
        """
        self.sort_az_icon.wait_for(state="visible", timeout=10000)
        self.sort_az_icon.click()
        self.sort_za_icon.wait_for(state="visible", timeout=5000)

    def click_sort_za(self):
        """Click the Z-A sort icon (same toggle as click_sort_az)."""
        self.sort_za_icon.wait_for(state="visible", timeout=10000)
        self.sort_za_icon.click()
        self.sort_az_icon.wait_for(state="visible", timeout=5000)

    def delete_camera_group_by_name(self, name: str) -> bool:
        """Delete the group with the given name; False when not found.

        Scoped to the named row so cleanup never deletes someone
        else's group on the shared tenant.
        """
        row_anchor = self.page.get_by_text(name, exact=True).first
        try:
            row_anchor.wait_for(state="visible", timeout=5000)
        except Exception:
            return False
        icon = row_anchor.locator("xpath=../..").locator(
            "img[alt='delete']"
        ).first
        try:
            icon.wait_for(state="visible", timeout=5000)
        except Exception:
            return False
        icon.click()
        dialog_shown = True
        try:
            self.group_delete_confirm.wait_for(state="visible", timeout=3000)
        except Exception:
            dialog_shown = False
        if dialog_shown:
            self.group_delete_confirm.click()
            self.group_delete_confirm.wait_for(state="hidden", timeout=15000)
        return True

    def open_groups_dropdown(self):
        """Open the Groups dropdown on the site detail page.

        Since the 2026-08 redesign, group management (the group list
        and Create New) lives inside this dropdown.
        """
        try:
            self.create_new_button.first.wait_for(
                state="visible", timeout=2000
            )
            return  # already open
        # probe for an already-open dropdown: the click below opens it
        # and its wait raises if it never does
        except Exception:
            pass
        trigger = self.page.get_by_text("Groups:", exact=False).first
        trigger.locator("xpath=following-sibling::*[1]").click()
        self.create_new_button.first.wait_for(state="visible", timeout=10000)

    def create_camera_group(self, name: str, camera_search: str):
        """Create a new camera group.

        Opens the Groups dropdown, clicks Create New, fills the name,
        searches a camera, selects it, and clicks Create.
        """
        self.open_groups_dropdown()
        self.create_new_button.first.click()

        self.group_name_input.wait_for(state="visible", timeout=10000)
        self.group_name_input.fill(name)

        self.camera_search_input.wait_for(state="visible", timeout=10000)
        self.camera_search_input.fill(camera_search)

        # Wait for the filtered camera to appear instead of sleeping; a
        # zero-match search means the group would be created empty
        try:
            self.camera_checkbox.first.wait_for(state="attached", timeout=5000)
            self.camera_checkbox.first.click(force=True)
        except Exception:
            raise AssertionError(
                f"No camera matched '{camera_search}' in the group form "
                f"(or its checkbox could not be clicked); update "
                f"test_camera_name in config/env/ if the tenant renamed it"
            ) from None

        self.create_button.wait_for(state="visible", timeout=10000)
        try:
            self.create_button.click(timeout=15000)
        except Exception:
            # The MuiBox control occasionally stays inert to the
            # element click; the exact text node accepts it
            self.page.get_by_text("Create", exact=True).last.click()
        # The form closing is the signal the group was created
        self.group_name_input.wait_for(state="hidden", timeout=15000)

    def edit_camera_group_by_name(self, name: str, new_name: str) -> bool:
        """Rename the group with the given name; False when not found.

        Name-scoped so tests rename their own group, never a
        team-owned one on the shared tenant.
        """
        row_anchor = self.page.get_by_text(name, exact=True).first
        try:
            row_anchor.wait_for(state="visible", timeout=5000)
        except Exception:
            return False
        icon = row_anchor.locator("xpath=../..").locator(
            "img[alt='edit']"
        ).first
        icon.wait_for(state="visible", timeout=5000)
        icon.click()

        self.group_name_input.wait_for(state="visible", timeout=10000)
        self.group_name_input.clear()
        self.group_name_input.fill(new_name)

        # Exact text node: a :has-text MuiBox union matches ancestor
        # boxes and the click misses the control (same fix as Create New)
        update_btn = self.page.get_by_text("Update", exact=True)
        if update_btn.count() > 0:
            update_btn.first.click()
        else:
            self.create_button.click()
        # The form closing is the signal the update was accepted
        self.group_name_input.wait_for(state="hidden", timeout=15000)
        return True

    def delete_camera_group(self):
        """Delete the last camera group via its delete icon.

        A confirmation dialog is optional: the 2026-08 Groups dropdown
        deletes immediately when none appears. Callers assert on the
        group count, which is the real signal either way.
        """
        self.group_delete_icons.last.wait_for(
            state="visible", timeout=10000
        )
        self.group_delete_icons.last.click()

        # Only the dialog's absence is optional. Once it shows, the
        # click and the close must succeed or the failure surfaces.
        dialog_shown = True
        try:
            self.group_delete_confirm.wait_for(state="visible", timeout=3000)
        except Exception:
            dialog_shown = False  # no dialog: the delete applies immediately
        if dialog_shown:
            self.group_delete_confirm.click()
            self.group_delete_confirm.wait_for(state="hidden", timeout=15000)

    def search_inside_site(self, search_text: str):
        """Search for cameras within a site detail view.

        Filtering has no completion signal (zero matches is valid), so this
        method does not wait. Callers wait on the row they need next.
        """
        site_search = self.page.locator(
            "input[placeholder*='Search']"
        ).first
        site_search.wait_for(state="visible", timeout=10000)
        site_search.clear()
        site_search.fill(search_text)

    # --- Full rule creation wizard ---


    def _check_wizard_camera(self):
        """Filter to the configured camera on Select Devices and check it."""
        from config.base_config import config
        camera = config.get("test_camera_name")
        search = self.page.locator(
            "input[placeholder*='camera name']"
        ).first
        search.wait_for(state="visible", timeout=10000)
        # The device tree loads async after the step renders: wait for
        # it before filtering, so slow loads do not read as a missing
        # camera
        self.page.locator("input[type='checkbox']").first.wait_for(
            state="attached", timeout=20000
        )
        if camera:
            # The unfiltered tree stays up while the filter runs: the
            # checkbox count leaving its baseline is the re-rendered
            # signal (a one-camera tree never moves it, so a miss logs)
            boxes = self.page.locator("input[type='checkbox']")
            before = boxes.count()
            search.fill(camera)
            self._count_left_baseline(boxes, before, "wizard device filter")
        # The configured camera's own row, fail-fast: a silent fallback
        # to another checkbox would create the rule against an
        # arbitrary device and pass on wrong data
        if not camera:
            raise RuntimeError(
                "test_camera_name is not set for this ENV in config/env/."
            )
        # Exact and escaped (item 19): this pick decides which device the
        # rule is created against, so a substring landing 'main gate 2'
        # for 'main gate' would build the rule on the wrong camera. A
        # renamed camera now fails loud below with the on-screen names.
        row = self.page.get_by_text(camera, exact=True).first
        try:
            row.wait_for(state="visible", timeout=10000)
        except Exception:
            visible = self._wizard_leaf_texts()[:10]
            raise RuntimeError(
                f"Camera '{camera}' is not in the wizard device tree. "
                f"On-screen: {visible}. Update test_camera_name in "
                f"config/env/ if the tenant renamed it."
            ) from None
        box = row.locator(
            "xpath=ancestor::*[.//input[@type='checkbox']][1]"
        ).locator("input[type='checkbox']").first
        box.wait_for(state="attached", timeout=10000)
        box.evaluate("el => el.click()")
        # The input's checked state is the applied signal
        try:
            expect(box).to_be_checked(timeout=5000)
        except AssertionError:
            raise RuntimeError(
                f"Wizard camera checkbox for '{camera}' did not register: "
                f"the rule would be created against no device"
            ) from None

    def _draw_wizard_region(self):
        """Draw a region on the Set Rule canvas and confirm with Done.

        Only the fabric upper-canvas is the drawing surface: the page
        also renders a bare classless canvas in the header area, and
        clicking relative to that one lands on navigation (measured
        08/11/2026 - it exited the wizard).
        """
        canvas = self.page.locator("canvas.upper-canvas").last
        canvas.wait_for(state="visible", timeout=15000)
        # bounding_box is viewport-relative: a scrolled canvas would
        # send the clicks into whatever overlays those coordinates
        canvas.scroll_into_view_if_needed()
        box = canvas.bounding_box()
        if not box:
            print("[ADMIN] Region canvas has no bounding box")
            return
        cx = box["x"] + box["width"] / 2
        cy = box["y"] + box["height"] / 2
        # 4-point polygon with pacing: the canvas library reads no DOM
        # state a wait could target
        for ox, oy in ((-80, -80), (80, -80), (80, 80), (-80, 80)):
            self.page.mouse.click(cx + ox, cy + oy)
            self.page.wait_for_timeout(800)  # canvas pacing, no DOM signal
        self.page.wait_for_timeout(1500)  # polygon close settles, no signal
        done = self.page.locator("button.btn-done").first
        try:
            if done.is_visible():
                done.click()
                # The region modal closing takes Done with it; a modal
                # that stays lets Next advance the wizard unconfigured
                self._must_close(done, "Set Rule Done (region)")
        except Exception:
            raise AssertionError(
                "Set Rule Done was visible but the click failed - the "
                "drawn region was not confirmed"
            ) from None

    def complete_rule_wizard(
        self, rule_type: str, site_name: str, rule_name: str | None = None
    ) -> bool:
        """Complete the rule creation wizard end-to-end.

        2026-08 flow: Add New Rule opens a card-picker modal (pick the
        rule type, Next), then a full-page wizard with step tabs
        Select Devices > Set Rule > Configure > Schedule >
        Notification. The camera comes from config on Select Devices;
        canvas rules draw at Set Rule; the rule name is filled on
        whichever step shows a name input; Save finishes. Returns
        False only when the picker does not offer the rule type; a
        stalled walk raises.
        """
        # The caller opens the picker (click_add_new_rule); choose the
        # rule type card. A type the picker no longer offers is a
        # clean False, not an error.
        modal = self.page.locator(".customMuiModal")
        card = modal.get_by_text(rule_type, exact=True).first
        try:
            card.wait_for(state="visible", timeout=10000)
        except Exception:
            print(f"[ADMIN] Rule type card '{rule_type}' not in the picker")
            return False
        card.click()
        modal.get_by_text("Next", exact=True).first.click()

        # Select Devices: the step tabs mark the wizard page
        self.page.get_by_text("Select Devices").first.wait_for(
            state="visible", timeout=10000
        )
        self._check_wizard_camera()

        # Heat Map class rules configure Set Rule through the 'Use full
        # view' switch; the canvas rules draw a region. The Set Rule
        # modal shows BOTH texts for the full-view types, so the branch
        # keys on the rule type, not on which prompt happens to render.
        full_view_rules = {"Heat Map", "Loitering", "Occupancy"}

        # Walk the steps: handle the canvas and the name input where
        # they appear, advance on Next, finish on Save. Seven
        # iterations: the happy path uses five, and one slow render
        # must not exhaust the budget
        for step in range(7):
            full_view = self.page.get_by_text(
                "Use full view", exact=False
            ).first
            try:
                fv_visible = full_view.is_visible()
            except Exception:
                fv_visible = False
            region_prompt = self.page.get_by_text(
                "Create Region", exact=False
            ).first
            try:
                region_visible = region_prompt.is_visible()
            except Exception:
                region_visible = False

            if rule_type in full_view_rules and fv_visible:
                # The label text does not toggle the switch: JS-click
                # the input (zero-dimension MUI input pattern). The
                # toggle is verified, not fire-and-forget: Done arms
                # on the snapshot load regardless of the switch, so a
                # silently skipped toggle would walk through with the
                # step unconfigured.
                sw = full_view.locator(
                    "xpath=ancestor::label[1]"
                ).locator("input").first
                sw.wait_for(state="attached", timeout=5000)
                if not sw.evaluate("el => el.checked"):
                    sw.evaluate("el => el.click()")
                # The input's checked state is the applied signal
                try:
                    expect(sw).to_be_checked(timeout=5000)
                except AssertionError:
                    raise RuntimeError(
                        "The 'Use full view' switch did not turn on"
                    ) from None
                # Done arms only after the snapshot loads, and the
                # modal backdrop eats pointer clicks - wait for the
                # armed button, then click it through JS
                done = self.page.locator(
                    "button.btn-done:not([disabled])"
                ).first
                done.wait_for(state="visible", timeout=30000)
                done.evaluate("el => el.click()")
                # The Set Rule modal closing takes Done with it; a modal
                # that stays lets Next advance the wizard unconfigured
                self._must_close(done, "Set Rule Done (full view)")
            elif region_visible:
                self._draw_wizard_region()

            nxt = self.page.get_by_text("Next", exact=True).first
            before_step = self._wizard_step_texts()
            advanced = True
            try:
                nxt.wait_for(state="visible", timeout=5000)
                nxt.click(timeout=10000)
            except Exception as e:
                # A lingering invisible backdrop can eat pointer
                # clicks; a JS click is safe because a disabled Next
                # ignores it. Count-gated so a missing button does
                # not sit out an auto-wait inside the except.
                fallback = self.page.locator(
                    "button.btn-primary:has-text('Next')"
                )
                if fallback.count() > 0:
                    fallback.first.evaluate("el => el.click()")
                else:
                    advanced = False
                    print(f"[ADMIN] Wizard step {step}: Next not "
                          f"clickable: {str(e)[:80]}")
            # Steps re-render in place: the visible label set changing
            # is a settle; the next step's own element waits decide.
            # Nothing was clicked when Next is absent (the Save step)
            if advanced:
                self._wizard_step_changed(before_step, step)

            if rule_name:
                # Exclude the camera-search box, whose placeholder also
                # contains 'name'
                name_input = self.page.locator(
                    "input[placeholder*='name' i]"
                    ":not([placeholder*='camera' i]), "
                    "input[placeholder='Type here...']"
                ).first
                try:
                    if name_input.is_visible() and not name_input.input_value():
                        name_input.fill(rule_name)
                # probe of an optional per-step name input: the Name the
                # Rule prompt fill raises and the caller asserts the row
                # by name
                except Exception:
                    pass

            save = self.page.locator(
                "button:has-text('Save'), div.MuiBox-root:text-is('Save'), "
                "button:has-text('Finish'), button:has-text('Create')"
            ).first
            try:
                save_visible = save.is_visible()
            except Exception:
                save_visible = False
            if save_visible:
                save.click()
                # Save prompts 'Name the Rule' in a dialog: the name
                # lives THERE, not on any step (this is what rejected
                # the old flow). Only the prompt's ABSENCE is optional;
                # once it shows, the fill and confirm must succeed, and
                # a failure past Save raises rather than reading as
                # not-completed while the rule may exist server-side.
                prompt = self.page.get_by_text("Name the Rule").first
                prompt_shown = True
                try:
                    prompt.wait_for(state="visible", timeout=5000)
                except Exception:
                    prompt_shown = False  # no prompt: saved directly
                if prompt_shown:
                    name_box = self.page.locator(
                        ".customMuiModal input, "
                        "input[placeholder*='Type here']"
                    ).last
                    if rule_name:
                        name_box.fill(rule_name, timeout=10000)
                    confirm = self.page.locator(
                        ".customMuiModal button:has-text('Done'), "
                        ".customMuiModal button:has-text('Save'), "
                        "button.btn-done"
                    ).first
                    confirm.click(timeout=10000)
                # The wizard closing is the created signal
                self.page.get_by_text("Select Devices").first.wait_for(
                    state="hidden", timeout=15000
                )
                return True

        # A stall is a failure, not a False: every rule type is
        # expected to complete, and a False reads as a designed skip
        # at the call site (only the missing picker card returns False)
        raise RuntimeError(
            f"Rule wizard stalled walking '{rule_type}'; visible: "
            f"{self._wizard_leaf_texts()[:20]}"
        )

    def _count_left_baseline(self, locator, before: int, action: str,
                             timeout_s: float = 5.0) -> bool:
        """Wait for a locator count to move off a pre-action baseline.

        A filter replaces its list in place with no other signal; the
        count changing is the re-rendered sign. Logs and returns False
        on timeout so the caller's own wait decides.
        """
        try:
            expect(locator).not_to_have_count(before, timeout=int(timeout_s * 1000))
            return True
        except AssertionError:
            print(f"[ADMIN] {action}: count stayed at {before} for "
                  f"{timeout_s:.0f}s")
            return False

    def _must_close(self, locator, label: str, timeout: int = 5000) -> None:
        """A confirming control must leave with its modal, or the step
        was not confirmed."""
        try:
            locator.wait_for(state="hidden", timeout=timeout)
        except PlaywrightError:
            raise AssertionError(
                f"{label} stayed visible {timeout / 1000:.0f}s after the click: "
                f"the step was not confirmed"
            ) from None

    def _hidden_or_log(self, locator, label: str, timeout: int = 5000) -> bool:
        """Bounded hidden wait for a closing control; logs a miss.

        The close is a settle, not the oracle: callers verify the
        outcome (the rule row, the checked switch) on their own.
        """
        try:
            locator.wait_for(state="hidden", timeout=timeout)
            return True
        # a control that lingers is logged for the run report; the
        # caller's outcome check decides the test
        except PlaywrightError:
            print(f"[ADMIN] {label} still visible after "
                  f"{timeout / 1000:.0f}s")
            return False

    def _wizard_step_texts(self) -> frozenset:
        """Visible short leaf texts without digits: the step's label set.

        Counters and clocks change on their own, so digit-bearing
        texts stay out of the fingerprint.
        """
        return frozenset(
            t for t in self._wizard_leaf_texts()
            if not any(c.isdigit() for c in t)
        )

    def _wizard_step_changed(self, before: frozenset, step: int,
                             timeout_s: float = 8.0) -> bool:
        """Wait for the wizard's label set to leave its pre-Next state."""
        deadline = time.monotonic() + timeout_s
        while time.monotonic() < deadline:
            if self._wizard_step_texts() != before:
                return True
            self.page.wait_for_timeout(250)  # poll tick for the step re-render
        print(f"[ADMIN] Wizard step {step}: labels unchanged "
              f"{timeout_s:.0f}s after Next")
        return False

    def _wizard_leaf_texts(self):
        """Short visible leaf texts, nav chrome excluded (diagnostics)."""
        skip = {"Views", "Events", "Maps", "Insights", "Media", "Search",
                "LPR", "Admin", "Dashboard", "Sites", "Users",
                "Integrations", "Rules", "General", "Licenses", "JV"}
        # getClientRects, not offsetParent: fixed-position containers
        # (customMuiModal and friends) have no offsetParent even when
        # fully visible, and diagnostics must see them
        texts = self.page.evaluate(
            '() => [...document.querySelectorAll("body *")]'
            '.filter(e => e.children.length === 0 '
            '&& e.getClientRects().length)'
            '.map(e => (e.textContent || "").trim())'
            '.filter(t => t && t.length < 30)'
        )
        return [t for t in texts if t not in skip]
