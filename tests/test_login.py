def test_login(page, base_url, tenant_login):
    page.goto(base_url + "/auth/login")
    page.fill("input[name='email']", tenant_login["username"])
    page.fill("input[name='password']", tenant_login["password"])
    page.click("button[type='submit']")
    page.wait_for_url(base_url + tenant_login["expected_landing"])
