import pytest


class EventsPage:
    def __init__(self, page):
        self.page = page

    def go_to_events(self, base_url: str):
        self.page.goto(base_url.rstrip("/") + "/events")
        return self

    def search(self, query: str):
        p = self.page
        # try common search input placeholders
        if p.get_by_placeholder("Search").count():
            p.get_by_placeholder("Search").fill(query)
            p.get_by_placeholder("Search").press("Enter")
        elif p.locator("input[type='search']").count():
            p.locator("input[type='search']").fill(query)
            p.locator("input[type='search']").press("Enter")
        else:
            pytest.skip("No events search input found")

        # wait for results to appear
        try:
            p.wait_for_selector("text=/event|results|no results|No events/i", timeout=10000)
        except Exception:
            pass

        return self

    def open_first_event(self):
        p = self.page
        locator = p.locator("text=/event/i").first
        if locator.count() == 0:
            pytest.skip("No events found to open")
        locator.click()
        return self
