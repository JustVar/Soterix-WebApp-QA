"""Admin Page Object Model.

Shared page object for Admin section navigation, user management,
rules management, and sites/camera group management.
Used by Admin Users, Admin Sites, and Admin Rules test modules.
"""
import datetime
from playwright.sync_api import Page, expect


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
        self.delete_icon = page.locator("img[src*='delete-icon']")
        self.delete_confirm = page.locator(
            "button:has-text('Delete'), div.MuiBox-root:text-is('Delete')"
        )

        # User status toggle
        self.user_switch = page.locator(".MuiSwitch-root")

        # Role filter
        self.role_filter_dropdown = page.locator("div[role='combobox']")
        self.role_options = page.locator("li.MuiMenuItem-root")

        # Rules management
        self.add_new_rule_button = page.locator(
            "#topRightBox button:has-text('Add New Rule')"
        )
        self.next_button = page.locator(
            "button:has-text('Next')"
        )
        self.save_rule_button = page.locator("button:has-text('Save')")
        self.rule_search_input = page.locator(
            "input.input-search-bar[placeholder*='Rule Type']"
        )
        self.rule_edit_icons = page.locator("img[aria-label='Edit']")
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
        self.site_checkbox_wizard = page.locator(
            "input[type='checkbox']"
        )

        # Sites management
        self.list_view_toggle = page.locator("img[alt='tableIcon']")
        self.grid_view_toggle = page.locator("img[src*='icon-grid']")
        self.online_status_icons = page.locator("img[alt='Online']")
        self.offline_status_icons = page.locator("img[alt='Offline']")
        self.sort_az_icon = page.locator("img[src*='a-to-z-sort']")
        self.sort_za_icon = page.locator("img[src*='z-to-a-sort']")
        self.accordion_icon = page.locator(
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

    def delete_user(self):
        """Delete the first user shown in the current view.

        Assumes search has already been performed to filter to the target user.
        Clicks options icon > delete icon > confirm delete.
        """
        self.options_icon.first.wait_for(state="visible", timeout=10000)
        self.options_icon.first.click()

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
            # text that holds a switch is that user's card
            switch = self.page.get_by_text(user_text).first.locator(
                "xpath=ancestor::*[.//*[contains(@class,'MuiSwitch-root')]][1]"
            ).locator(".MuiSwitch-root").first
        else:
            switch = self.user_switch.first
        switch.wait_for(state="visible", timeout=10000)
        switch.click()
        self.page.wait_for_timeout(1000)  # server ack has no DOM signal

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
                "() => document.querySelectorAll('li.MuiMenuItem-root').length > 1",
                timeout=10000,
            )
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

    def select_site_checkbox(self):
        """Toggle the first site checkbox in the rule wizard."""
        self.site_checkbox_wizard.first.wait_for(
            state="visible", timeout=10000
        )
        self.site_checkbox_wizard.first.click()

    def fill_rule_name(self, name: str):
        """Fill the rule name input in the wizard."""
        rule_name_input = self.page.locator(
            "input[placeholder*='name'], input[placeholder*='Name']"
        )
        rule_name_input.wait_for(state="visible", timeout=10000)
        rule_name_input.fill(name)

    def save_rule(self):
        """Click the Save button to save the rule.

        Waits for the wizard to close; tolerates it staying open so the
        caller's own assertion reports the failure.
        """
        self.save_rule_button.click()
        try:
            self.save_rule_button.wait_for(state="hidden", timeout=15000)
        except Exception:
            pass

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
        # The modal's primary button is the signal that it opened
        try:
            self.update_and_close_button.wait_for(state="visible", timeout=15000)
        except Exception:
            pass

    def click_notification_tab(self):
        """Switch to the Notification tab in the rule edit modal."""
        self.notification_tab.wait_for(state="visible", timeout=15000)
        self.notification_tab.scroll_into_view_if_needed()
        self.notification_tab.click()
        # The notification checkboxes are the signal that the tab rendered
        try:
            self.popup_checkbox.wait_for(state="attached", timeout=10000)
        except Exception:
            pass

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
        try:
            self.update_and_close_button.wait_for(state="hidden", timeout=15000)
        except Exception:
            pass

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
        self.page.wait_for_timeout(1000)  # mute ack has no DOM signal

    def draw_line_on_canvas(self, start: tuple, end: tuple):
        """Draw a line on the canvas element using mouse actions.

        Args:
            start: (x_offset, y_offset) from canvas center
            end: (x_offset, y_offset) from canvas center
        """
        box = self.canvas.bounding_box()
        if not box:
            return
        cx = box["x"] + box["width"] / 2
        cy = box["y"] + box["height"] / 2
        self.page.mouse.move(cx + start[0], cy + start[1])
        self.page.mouse.down()
        self.page.mouse.move(cx + end[0], cy + end[1])
        self.page.mouse.up()
        self.page.wait_for_timeout(1000)  # canvas draw settle, no DOM signal

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
        try:
            self.grid_view_toggle.wait_for(state="visible", timeout=5000)
        except Exception:
            pass

    def toggle_to_grid_view(self):
        """Switch to grid view on the Sites page."""
        self.grid_view_toggle.wait_for(state="visible", timeout=10000)
        self.grid_view_toggle.click()
        # The opposite toggle appearing is the signal the view switched
        try:
            self.list_view_toggle.wait_for(state="visible", timeout=5000)
        except Exception:
            pass

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
        """Click a site card to navigate into the site detail view."""
        site = self.page.locator(
            f"p.MuiTypography-root:text-is('{site_name}')"
        )
        site.wait_for(state="visible", timeout=10000)
        site.click()
        # The site-card content is the signal the detail view rendered
        try:
            self.page.locator("div.site-card").first.wait_for(
                state="visible", timeout=10000
            )
        except Exception:
            pass

    def get_camera_names(self) -> list[str]:
        """Return a list of camera names visible in the site detail view."""
        camera_elements = self.page.locator(
            "div.site-card .MuiTypography-root"
        )
        if camera_elements.count() == 0:
            return []
        camera_elements.first.wait_for(state="visible", timeout=10000)
        names = []
        for i in range(camera_elements.count()):
            text = camera_elements.nth(i).inner_text().strip()
            if text:
                names.append(text)
        return names

    def click_sort_az(self):
        """Click the A-Z sort icon."""
        self.sort_az_icon.wait_for(state="visible", timeout=10000)
        self.sort_az_icon.click()
        self.page.wait_for_timeout(1000)  # in-place reorder has no DOM signal

    def click_sort_za(self):
        """Click the Z-A sort icon."""
        self.sort_za_icon.wait_for(state="visible", timeout=10000)
        self.sort_za_icon.click()
        self.page.wait_for_timeout(1000)  # in-place reorder has no DOM signal

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
        # zero-match search legitimately times out and skips the click
        try:
            self.camera_checkbox.first.wait_for(state="attached", timeout=5000)
            self.camera_checkbox.first.click(force=True)
        except Exception:
            pass

        self.create_button.wait_for(state="visible", timeout=10000)
        self.create_button.click()
        # The form closing is the signal the group was created
        try:
            self.group_name_input.wait_for(state="hidden", timeout=15000)
        except Exception:
            pass

    def edit_camera_group(self, new_name: str):
        """Edit the last camera group's name.

        Clicks last edit icon, clears name, fills new name, and submits.
        """
        self.group_edit_icons.last.wait_for(
            state="visible", timeout=10000
        )
        self.group_edit_icons.last.click()

        self.group_name_input.wait_for(state="visible", timeout=10000)
        self.group_name_input.clear()
        self.group_name_input.fill(new_name)

        # Click Update button (same position as Create button)
        update_btn = self.page.locator(
            "div.MuiBox-root:has-text('Update')"
        )
        if update_btn.count() > 0:
            update_btn.first.click()
        else:
            self.create_button.click()
        # The form closing is the signal the update was accepted
        try:
            self.group_name_input.wait_for(state="hidden", timeout=15000)
        except Exception:
            pass

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

    CANVAS_RULES = {"Entry-Exit", "Line Crossing"}
    NON_CANVAS_RULES = {
        "Heat Map", "Intrusion Detection", "Loitering", "Occupancy",
    }

    def select_site_for_rule(self, site_name: str):
        """Select a site from the MuiSelect dropdown in the rule wizard.

        Falls back to the first available option if site_name is not found.
        """
        # Check if site already shown
        site_text = self.page.locator(
            f"text=/{site_name}/i"
        )
        if site_text.count() > 0 and site_text.first.is_visible():
            return

        dropdown = self.page.locator(".MuiSelect-select").first
        dropdown.wait_for(state="visible", timeout=10000)
        dropdown.click()

        # The option list is the signal the dropdown opened
        options = self.page.locator("li[role='option']")
        options.first.wait_for(state="visible", timeout=10000)

        # Try named site first, fall back to first available option
        site_option = self.page.locator(
            f"li:has-text('{site_name}'), "
            f"div:text-is('{site_name}'), "
            f"span:text-is('{site_name}')"
        ).first
        if site_option.count() > 0 and site_option.is_visible():
            site_option.click()
        else:
            options.first.click()
        # The list closing is the signal the selection was applied
        try:
            options.first.wait_for(state="hidden", timeout=5000)
        except Exception:
            pass

    def wait_for_snapshots(self, timeout: int = 60000):
        """Wait for camera snapshot images to load in the rule wizard."""
        self.page.locator("img[src*='data:image']").first.wait_for(
            state="visible", timeout=timeout
        )
        # The canvas overlay initializes after the snapshot with no DOM signal
        self.page.wait_for_timeout(2000)

    def maximize_snapshot(self):
        """Click the maximize button on a camera snapshot."""
        maximize_btn = self.page.locator("img[alt='maximize']")
        maximize_btn.wait_for(state="visible", timeout=10000)
        maximize_btn.click()

        # Wait for the enlarged snapshot (at least 2 data:image elements)
        try:
            self.page.wait_for_function(
                "() => document.querySelectorAll(\"img[src*='data:image']\").length >= 2",
                timeout=30000,
            )
        except Exception:
            pass

    def draw_zone_on_canvas(self):
        """Draw a 4-point polygon zone on the canvas element.

        Uses mouse click offsets from canvas center to create a closed polygon,
        then Tab×4 + Enter to confirm the zone.
        """
        # Use the last (largest) canvas - there may be multiple upper-canvas elements
        canvas = self.page.locator("canvas.upper-canvas").last
        canvas.wait_for(state="visible", timeout=10000)
        box = canvas.bounding_box()
        if not box:
            return

        cx = box["x"] + box["width"] / 2
        cy = box["y"] + box["height"] / 2

        # 4-point polygon clicks with pauses. The pauses are canvas-library
        # pacing (fabric.js reads no DOM state a wait could target)
        offsets = [(-100, -150), (100, 20), (10, -20), (-10, 20)]
        for ox, oy in offsets:
            self.page.mouse.click(cx + ox, cy + oy)
            self.page.wait_for_timeout(1000)

        self.page.wait_for_timeout(3000)  # polygon close settles, no DOM signal

        # Confirm the zone: Tab×4 then Enter
        for _ in range(4):
            self.page.keyboard.press("Tab")
        self.page.wait_for_timeout(1000)  # focus traversal settles, no DOM signal
        self.page.keyboard.press("Enter")
        self.page.wait_for_timeout(2000)  # zone commit settles, no DOM signal

    def toggle_mui_switch(self):
        """Toggle the MuiSwitch checkbox used in non-canvas rule types."""
        switch_input = self.page.locator(
            "input[type='checkbox'].MuiSwitch-input, "
            "input[aria-label='ant design']"
        ).first
        switch_input.wait_for(state="attached", timeout=10000)
        switch_input.click(force=True)
        self.page.wait_for_timeout(1000)  # switch state applies with no DOM signal

    def click_ripple_button(self):
        """Click the MUI ripple button that appears after MuiSwitch toggle (optional)."""
        button = self.page.locator(
            "button.MuiButtonBase-root:not([disabled])"
        ).first
        try:
            button.wait_for(state="visible", timeout=5000)
            button.click()
            self.page.wait_for_timeout(1000)  # ripple ack has no DOM signal
        except Exception:
            pass

    def _check_wizard_camera(self):
        """Filter to the configured camera on Select Devices and check it."""
        from config.base_config import config
        camera = config.get("test_camera_name")
        search = self.page.locator(
            "input[placeholder*='camera name']"
        ).first
        search.wait_for(state="visible", timeout=10000)
        if camera:
            search.fill(camera)
            # The tree filter re-renders with no completion signal
            self.page.wait_for_timeout(1000)
        # Prefer the configured camera's own row; fall back to the
        # deepest checkbox. JS click covers the zero-dimension MUI
        # input pattern.
        box = None
        if camera:
            row = self.page.get_by_text(camera, exact=False).first
            try:
                row.wait_for(state="visible", timeout=5000)
                box = row.locator(
                    "xpath=ancestor::*[.//input[@type='checkbox']][1]"
                ).locator("input[type='checkbox']").first
            except Exception:
                box = None
        if box is None or box.count() == 0:
            box = self.page.locator("input[type='checkbox']").last
        box.wait_for(state="attached", timeout=10000)
        box.evaluate("el => el.click()")
        # Checked state is the applied signal
        self.page.wait_for_timeout(500)  # state propagates, no DOM signal
        try:
            if not box.is_checked():
                print("[ADMIN] Wizard camera checkbox did not register")
        except Exception:
            pass

    def _draw_wizard_region(self):
        """Draw a region on the Set Rule canvas and confirm with Done.

        Only the fabric upper-canvas is the drawing surface: the page
        also renders a bare classless canvas in the header area, and
        clicking relative to that one lands on navigation (measured
        08/11/2026 - it exited the wizard).
        """
        canvas = self.page.locator("canvas.upper-canvas").last
        canvas.wait_for(state="visible", timeout=15000)
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
                self.page.wait_for_timeout(1000)  # commit, no signal
        except Exception:
            pass

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
        False with a diagnostic print when the walk stalls.
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

        # Walk the steps: handle the canvas and the name input where
        # they appear, advance on Next, finish on Save
        for step in range(6):
            # Set Rule blocks Next until configured: canvas rules draw
            # a region; Heat Map class rules offer 'Use full view'
            region_prompt = self.page.get_by_text(
                "Create Region", exact=False
            ).first
            try:
                region_visible = region_prompt.is_visible()
            except Exception:
                region_visible = False
            if region_visible:
                self._draw_wizard_region()
            else:
                full_view = self.page.get_by_text(
                    "Use full view", exact=False
                ).first
                try:
                    if full_view.is_visible():
                        # The label text does not toggle its checkbox:
                        # JS-click the input beside it (zero-dimension
                        # MUI input pattern)
                        cb = full_view.locator(
                            "xpath=ancestor::*[.//input][1]"
                        ).locator("input").first
                        if cb.count() > 0:
                            cb.evaluate("el => el.click()")
                        else:
                            full_view.click()
                        self.page.wait_for_timeout(500)  # state, no signal
                        done = self.page.locator("button.btn-done").first
                        if done.is_visible():
                            done.click()
                            # Commit has no DOM signal
                            self.page.wait_for_timeout(1000)
                except Exception:
                    pass

            nxt = self.page.get_by_text("Next", exact=True).first
            try:
                nxt.wait_for(state="visible", timeout=5000)
                nxt.click(timeout=10000)
            except Exception as e:
                print(f"[ADMIN] Wizard step {step}: Next not clickable: "
                      f"{str(e)[:80]}")
            # Step transitions re-render in place with no signal
            self.page.wait_for_timeout(1500)

            if rule_name:
                name_input = self.page.locator(
                    "input[placeholder*='name' i], "
                    "input[placeholder='Type here...']"
                ).first
                try:
                    if name_input.is_visible() and not name_input.input_value():
                        name_input.fill(rule_name)
                except Exception:
                    pass

            save = self.page.locator(
                "button:has-text('Save'), div.MuiBox-root:text-is('Save'), "
                "button:has-text('Finish'), button:has-text('Create')"
            ).first
            try:
                if save.is_visible():
                    save.click()
                    # Save prompts 'Name the Rule' in a dialog: the
                    # name lives THERE, not on any step (this is what
                    # rejected the old flow). Fill it and confirm.
                    prompt = self.page.get_by_text("Name the Rule").first
                    try:
                        prompt.wait_for(state="visible", timeout=5000)
                        name_box = self.page.locator(
                            ".customMuiModal input, "
                            "input[placeholder*='Type here']"
                        ).last
                        if rule_name:
                            name_box.fill(rule_name)
                        confirm = self.page.locator(
                            ".customMuiModal button:has-text('Done'), "
                            ".customMuiModal button:has-text('Save'), "
                            "button.btn-done"
                        ).first
                        confirm.click()
                    except Exception:
                        pass  # no prompt: saved directly
                    # The wizard closing is the created signal
                    self.page.get_by_text("Select Devices").first.wait_for(
                        state="hidden", timeout=15000
                    )
                    return True
            except Exception:
                pass

        print(f"[ADMIN] Rule wizard stalled; visible: "
              f"{self._wizard_leaf_texts()[:20]}")
        return False

    def _wizard_leaf_texts(self):
        """Short visible leaf texts, nav chrome excluded (diagnostics)."""
        skip = {"Views", "Events", "Maps", "Insights", "Media", "Search",
                "LPR", "Admin", "Dashboard", "Sites", "Users",
                "Integrations", "Rules", "General", "Licenses", "JV"}
        texts = self.page.evaluate(
            '() => [...document.querySelectorAll("body *")]'
            '.filter(e => e.children.length === 0 && e.offsetParent !== null)'
            '.map(e => (e.textContent || "").trim())'
            '.filter(t => t && t.length < 30)'
        )
        return [t for t in texts if t not in skip]
