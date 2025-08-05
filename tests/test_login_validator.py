import pytest

@pytest.mark.smoke
def test_login_page_field_validations(page, env_config):
    page.goto(env_config["base_url"] + "/auth/login")

    # Test empty form submission
    page.click("button[type='submit']")
    assert page.locator(".error-message").first.is_visible()

    # Test invalid email format
    page.fill("input[name='email']", "invalid@")
    page.fill("input[name='password']", "somepass")
    page.click("button[type='submit']")
    assert page.locator(".error-message").first.inner_text().lower().__contains__("invalid")

    # Test too short password
    page.fill("input[name='email']", "user@soterix.com")
    page.fill("input[name='password']", "123")
    page.click("button[type='submit']")
    assert page.locator(".error-message").first.is_visible()
