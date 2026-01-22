class DashboardPage:
    def __init__(self, page):
        self.page = page

    def goto(self, base_url: str):
        self.page.goto(base_url.rstrip("/") + "/dashboard")
        return self

    def open_tab(self, tab_name: str):
        p = self.page
        # Prefer role-based links/buttons
        if p.get_by_role("link", name=tab_name).count():
            p.get_by_role("link", name=tab_name).click()
        elif p.get_by_text(tab_name).count():
            p.get_by_text(tab_name).first.click()
        else:
            # fallback: click element with matching text
            p.locator(f"text={tab_name}").first.click()
        return self
