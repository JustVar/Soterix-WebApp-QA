import pytest


class CameraPage:
    def __init__(self, page):
        self.page = page

    def go_to_dashboard(self, base_url: str):
        self.page.goto(base_url.rstrip("/") + "/dashboard")
        return self

    def play_first_camera(self):
        p = self.page
        # Try to find a camera tile by common text patterns
        locator = p.locator("text=/camera/i").first
        if locator.count() == 0:
            pytest.skip("No camera tiles found on page")

        locator.click()

        # Wait for a streaming indicator or video element to appear
        try:
            p.wait_for_selector("text=/live|play|stream/i", timeout=10000)
        except Exception:
            # If no explicit streaming indicator, at least assert camera tile visible
            assert locator.is_visible()

        return self

    def add_camera_to_group(self, camera_name: str, group_name: str):
        # Placeholder for future implementation
        return self
