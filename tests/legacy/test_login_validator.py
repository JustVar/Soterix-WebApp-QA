import time
import pytest
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager


class Testloginvalidator:
    def __init__(self, url):
        """Initialize the login validator with the login page URL."""
        self.url = url
        self.driver = None

    def setup(self, browser='chrome', detach=True, headless=False):
        """Set up the WebDriver based on the browser choice."""
        if browser.lower() == 'chrome':
            # Set up options to detach the browser if specified
            chrome_options = Options()
            if detach:
                chrome_options.add_experimental_option("detach", True)
            if headless:
                chrome_options.add_argument("--headless")

            # Use ChromeDriverManager for automatic driver management
            service = Service(ChromeDriverManager().install())
            self.driver = webdriver.Chrome(service=service, options=chrome_options)
        elif browser.lower() == 'firefox':
            self.driver = webdriver.Firefox()
        elif browser.lower() == 'edge':
            self.driver = webdriver.Edge()
        else:
            raise ValueError(f"Unsupported browser: {browser}")

        self.driver.maximize_window()

    def navigate_to_login(self):
        """Navigate to the login page."""
        self.driver.get(self.url)
        print(f"Navigated to: {self.url}")
        # Added wait time for page to fully load
        time.sleep(4)

    def navigate_to_logout(self):
        """Navigate to the log out."""
        self.driver.find_element(By.XPATH, '//*[@id="root"]/div/div/div/div[2]/div/div').click()
        self.driver.find_element(By.XPATH, '//*[@id="root"]/div/div[2]/div/div[3]/p').click()
        time.sleep(3)

    def attempt_login(self, username, password,
                      username_xpath='//*[@id=":r0:"]',
                      password_xpath='//*[@id=":r1:"]',
                      login_button_xpath='//*[@id="root"]/div/div/div/form/div/button',
                      capture_screenshot=False):
        """
        Attempt to login with the provided credentials using XPath selectors.

        Parameters:
        - username: The username to enter
        - password: The password to enter
        - username_xpath: XPath of the username input field
        - password_xpath: XPath of the password input field
        - login_button_xpath: XPath of the login button
        - capture_screenshot: Whether to capture a screenshot after login attempt

        Returns:
        - dict with login result and additional info
        """
        result = {
            "success": False,
            "error_message": None,
            "url_changed": False,
            "new_url": None,
            "exception": None
        }

        try:
            # Wait for the username field to be present
            username_field = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.XPATH, username_xpath))
            )
            username_field.click()
            username_field.clear()
            username_field.send_keys(username)
            time.sleep(1)

            # Enter password
            password_field = self.driver.find_element(By.XPATH, password_xpath)
            password_field.click()
            password_field.clear()
            password_field.send_keys(password)
            time.sleep(1)

            # Capture the current URL for later comparison
            start_url = self.driver.current_url

            # Click login button
            login_button = self.driver.find_element(By.XPATH, login_button_xpath)
            login_button.click()

            # Wait for page to change or error message to appear
            time.sleep(3)

            # Take screenshot if requested
            if capture_screenshot:
                timestamp = time.strftime("%Y%m%d-%H%M%S")
                filename = f"login_attempt_{timestamp}.png"
                self.driver.save_screenshot(filename)
                print(f"Screenshot saved as {filename}")

            # Check if URL changed (successful login) or remained the same (failed login)
            current_url = self.driver.current_url
            result["new_url"] = current_url

            if current_url != start_url:
                print(f"Login successful! Redirected to: {current_url}")
                result["success"] = True
                result["url_changed"] = True
            else:
                # Check for error messages that might indicate failed login
                try:
                    # Look for common error message elements - adjust selectors as needed
                    error_selectors = [
                        "//div[contains(@class, 'error')]",
                        "//div[contains(@class, 'alert')]",
                        "//p[contains(@class, 'error-text')]",
                        "//span[contains(@class, 'error')]",
                        "//div[contains(text(), 'Invalid')]",
                        "//p[contains(text(), 'Invalid')]"
                    ]

                    for selector in error_selectors:
                        error_elements = self.driver.find_elements(By.XPATH, selector)
                        if error_elements:
                            for element in error_elements:
                                if element.is_displayed() and element.text.strip():
                                    error_message = element.text
                                    print(f"Login failed. Error message: {error_message}")
                                    result["error_message"] = error_message
                                    return result

                    print("Login status unclear. URL didn't change but no error message found.")

                except Exception as e:
                    print(f"Error checking for login failure messages: {str(e)}")
                    result["exception"] = str(e)

        except Exception as e:
            print(f"An error occurred during login attempt: {str(e)}")
            result["exception"] = str(e)

        return result

    def check_field_validation(self, field_xpath, test_input, expected_error=True):
        """
        Test field validation by entering potentially invalid input.

        Parameters:
        - field_xpath: XPath selector for the input field
        - test_input: Input value to test (empty string, invalid format, etc.)
        - expected_error: Whether an error message is expected

        Returns:
        - dict with validation results
        """
        result = {
            "field": field_xpath,
            "input": test_input,
            "error_detected": False,
            "error_message": None,
            "exception": None
        }

        try:
            # Find and clear the field
            field = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.XPATH, field_xpath))
            )
            field.click()
            field.clear()

            # Enter test input if not empty
            if test_input:
                field.send_keys(test_input)

            # Click login button to trigger validation (more reliable than clicking elsewhere)
            try:
                login_button = self.driver.find_element(By.XPATH, '//*[@id="root"]/div/div/div/form/div/button')
                login_button.click()
            except:
                # Fallback to clicking body if button not found
                self.driver.find_element(By.XPATH, "//body").click()

            # Wait for validation messages to appear
            time.sleep(1)

            # Different approaches to find validation errors
            # 1. Look for error messages near the input field
            error_selectors = [
                # Direct siblings
                f"{field_xpath}/following-sibling::div[contains(@class, 'error') or contains(@class, 'validation') or contains(@class, 'invalid')]",
                f"{field_xpath}/following-sibling::span[contains(@class, 'error') or contains(@class, 'validation') or contains(@class, 'invalid')]",
                f"{field_xpath}/following-sibling::p[contains(@class, 'error') or contains(@class, 'validation') or contains(@class, 'invalid')]",

                # Parent's siblings
                f"{field_xpath}/parent::*/following-sibling::div[contains(@class, 'error') or contains(@class, 'validation') or contains(@class, 'invalid')]",
                f"{field_xpath}/parent::*/following-sibling::span[contains(@class, 'error') or contains(@class, 'validation') or contains(@class, 'invalid')]",
                f"{field_xpath}/parent::*/following-sibling::p[contains(@class, 'error') or contains(@class, 'validation') or contains(@class, 'invalid')]",

                # Ancestor's siblings
                f"{field_xpath}/ancestor::div[1]/following-sibling::div[contains(@class, 'error') or contains(@class, 'validation') or contains(@class, 'invalid')]",
                f"{field_xpath}/ancestor::div[1]/following-sibling::p[contains(@class, 'error') or contains(@class, 'validation') or contains(@class, 'invalid')]",

                # General form errors
                "//form//div[contains(@class, 'error') or contains(@class, 'validation') or contains(@class, 'invalid')]",
                "//form//p[contains(@class, 'error') or contains(@class, 'validation') or contains(@class, 'invalid')]",
                "//form//span[contains(@class, 'error') or contains(@class, 'validation') or contains(@class, 'invalid')]"
            ]

            # 2. Look for error messages by content
            content_selectors = [
                "//*[contains(text(), 'invalid') or contains(text(), 'Invalid')]",
                "//*[contains(text(), 'required') or contains(text(), 'Required')]",
                "//*[contains(text(), 'error') or contains(text(), 'Error')]",
                "//*[contains(text(), 'empty') or contains(text(), 'Empty')]",
                "//*[contains(text(), 'cannot') or contains(text(), 'Cannot')]",
                "//*[contains(text(), 'must') or contains(text(), 'Must')]"
            ]

            # Check all class-based selectors first
            for selector in error_selectors:
                try:
                    error_elements = self.driver.find_elements(By.XPATH, selector)
                    for element in error_elements:
                        if element.is_displayed() and element.text.strip():
                            result["error_detected"] = True
                            result["error_message"] = element.text.strip()
                            print(f"Field validation error: {element.text.strip()}")
                            break
                    if result["error_detected"]:
                        break
                except Exception as e:
                    print(f"Exception checking selector {selector}: {str(e)}")
                    continue

            # If no error found by class, check by content
            if not result["error_detected"]:
                for selector in content_selectors:
                    try:
                        error_elements = self.driver.find_elements(By.XPATH, selector)
                        for element in error_elements:
                            # Only consider visible elements that are nearby the field
                            if element.is_displayed() and element.text.strip():
                                # Try to determine if this error belongs to our field
                                # This is a heuristic approach - might need adjustment
                                parent_element = self.driver.find_element(By.XPATH, field_xpath)
                                field_rect = parent_element.rect
                                error_rect = element.rect

                                # Check if error is near the field (within reasonable distance)
                                vertical_proximity = abs(error_rect['y'] - field_rect['y']) < 100
                                horizontal_proximity = abs(error_rect['x'] - field_rect['x']) < 200

                                if vertical_proximity and horizontal_proximity:
                                    result["error_detected"] = True
                                    result["error_message"] = element.text.strip()
                                    print(f"Field validation error (by content): {element.text.strip()}")
                                    break
                        if result["error_detected"]:
                            break
                    except Exception as e:
                        print(f"Exception checking content selector {selector}: {str(e)}")
                        continue

            # 3. Check for input field class/attribute changes that indicate validation state
            try:
                field = self.driver.find_element(By.XPATH, field_xpath)
                # Check for common validation attributes
                for attr in ['aria-invalid', 'data-error', 'data-invalid']:
                    attr_value = field.get_attribute(attr)
                    if attr_value and attr_value.lower() in ['true', 'yes', '1']:
                        result["error_detected"] = True
                        result["error_message"] = f"Field validation failed (detected via {attr} attribute)"
                        print(f"Field validation error (by attribute): {attr}={attr_value}")
                        break

                # Check for error classes on the field itself or parent
                field_class = field.get_attribute("class")
                if field_class and any(
                        err_class in field_class for err_class in ['error', 'invalid', 'validation-error']):
                    result["error_detected"] = True
                    if not result["error_message"]:
                        result["error_message"] = "Field validation failed (detected via CSS class)"
                    print(f"Field validation error (by class): {field_class}")

                # Check parent element for error classes
                try:
                    parent = field.find_element(By.XPATH, "./..")
                    parent_class = parent.get_attribute("class")
                    if parent_class and any(
                            err_class in parent_class for err_class in ['error', 'invalid', 'validation-error']):
                        result["error_detected"] = True
                        if not result["error_message"]:
                            result["error_message"] = "Field validation failed (detected via parent CSS class)"
                        print(f"Field validation error (by parent class): {parent_class}")
                except:
                    pass
            except Exception as e:
                print(f"Exception checking field attributes: {str(e)}")

            # Report test results
            if expected_error and result["error_detected"]:
                print(f"✓ Validation test passed: Error detected for input '{test_input}'")
            elif not expected_error and not result["error_detected"]:
                print(f"✓ Validation test passed: No error for valid input '{test_input}'")
            elif expected_error and not result["error_detected"]:
                print(f"✗ Validation test failed: No error detected for invalid input '{test_input}'")
            else:
                print(f"✗ Validation test failed: Error detected for valid input '{test_input}'")

        except Exception as e:
            print(f"Error during field validation check: {str(e)}")
            result["exception"] = str(e)

        return result

    def teardown(self):
        """Close the browser and clean up resources."""
        if self.driver:
            self.driver.quit()
            self.driver = None


# Pytest implementation
@pytest.fixture(scope="class")
def login_validator(request):
    """Fixture to create and set up login validator."""
    url = request.config.getoption("--url")
    headless = request.config.getoption("--headless", False)

    validator = Testloginvalidator(url)
    validator.setup(browser='chrome', detach=False, headless=headless)

    yield validator

    # Teardown after tests
    validator.teardown()


def pytest_addoption(parser):
    """Add command-line options to pytest."""
    parser.addoption("--url", action="store", default="https://app.example.invalid/",
                     help="URL of the login page to test")
    parser.addoption("--headless", action="store_true", help="Run browser in headless mode")
    parser.addoption("--username", action="store", default="person@example.com",
                     help="Valid username for login tests")
    parser.addoption("--password", action="store", default="Admin@123",
                     help="Valid password for login tests")


@pytest.fixture(scope="class")
def login_credentials(params):
    """Fixture to provide login credentials."""
    return {
        "username": params['username'],
        "password": params['password']
    }

@pytest.fixture(scope="class")
def xpath_selectors():
    """Fixture to provide XPath selectors."""
    return {
        "username": '//*[@id=":r0:"]',
        "password": '//*[@id=":r1:"]',
        "login_button": '//*[@id="root"]/div/div/div/form/div/button'
    }


@pytest.mark.usefixtures("login_validator", "login_credentials", "xpath_selectors")
class TestLoginValidation:

    def test_empty_fields(self, login_validator):
        """Test login with empty username and password."""
        login_validator.navigate_to_login()
        result = login_validator.attempt_login("", "")
        assert not result["success"], "Empty fields should not allow login"
        assert result["error_message"] is not None or not result["url_changed"], "Empty fields should show error or not change URL"

    def test_empty_username(self, login_validator):
        """Test login with empty username only."""
        login_validator.navigate_to_login()
        result = login_validator.attempt_login("", "password123")
        assert not result["success"], "Empty username should not allow login"

    def test_empty_password(self, login_validator):
        """Test login with empty password only."""
        login_validator.navigate_to_login()
        result = login_validator.attempt_login("user@example.com", "")
        assert not result["success"], "Empty password should not allow login"

    def test_invalid_email_format(self, login_validator):
        """Test login with invalid email format."""
        login_validator.navigate_to_login()
        result = login_validator.attempt_login("invalid-email", "password123")
        assert not result["success"], "Invalid email format should not allow login"

    def test_sql_injection_attempt(self, login_validator):
        """Test login with SQL injection attempt."""
        login_validator.navigate_to_login()
        result = login_validator.attempt_login("' OR 1=1 --", "password123")
        assert not result["success"], "SQL injection should not allow login"

    def test_xss_attempt(self, login_validator):
        """Test login with XSS attempt."""
        login_validator.navigate_to_login()
        result = login_validator.attempt_login("<script>alert('XSS')</script>", "password123")
        assert not result["success"], "XSS attempt should not allow login"

    def test_valid_credentials(self, login_validator, login_credentials):
        """Test login with valid credentials."""
        login_validator.navigate_to_login()
        result = login_validator.attempt_login(login_credentials["username"], login_credentials["password"])
        assert result["success"], "Valid credentials should allow login"
        assert result["url_changed"], "URL should change after successful login"

    def test_logout(self, login_validator, login_credentials):
        """Test logout functionality after login."""
        #login_validator.navigate_to_login()
        #login_result = login_validator.attempt_login(login_credentials["username"], login_credentials["password"])
        #assert login_result["success"], "Could not login before testing logout"
        #try:
        login_validator.navigate_to_logout()
            # After logout we should be back at login page or a different page from the logged-in state
            #assert login_validator.driver.current_url != login_result["new_url"], "Logout failed, still on same page"
        #except Exception as e:
            #pytest.fail(f"Exception during logout test: {str(e)}")

    def test_password_too_short(self, login_validator, login_credentials):
        """Test login with password that's too short."""
        login_validator.navigate_to_login()
        result = login_validator.attempt_login(login_credentials["username"], "123")
        assert not result["success"], "Too short password should not allow login"

    def test_wrong_credentials(self, login_validator):
        """Test login with valid format but wrong credentials."""
        login_validator.navigate_to_login()
        result = login_validator.attempt_login("valid@example.com", "wrongPassword123")
        assert not result["success"], "Wrong credentials should not allow login"

    def test_email_field_validation(self, login_validator, xpath_selectors):
        """Test email field validation."""
        login_validator.navigate_to_login()

        # Test empty email
        empty_result = login_validator.check_field_validation(xpath_selectors["username"], "", expected_error=True)
        assert empty_result["error_detected"], "Empty email should trigger validation error"

        # Test invalid format
        invalid_result = login_validator.check_field_validation(xpath_selectors["username"], "invalid-email",
                                                                expected_error=True)
        assert invalid_result["error_detected"], "Invalid email format should trigger validation error"

        # Test valid format
        valid_result = login_validator.check_field_validation(xpath_selectors["username"], "test@example.com",
                                                              expected_error=False)
        assert not valid_result["error_detected"], "Valid email format should not trigger validation error"

    def test_password_field_validation(self, login_validator, xpath_selectors):
        """Test password field validation."""
        login_validator.navigate_to_login()

        # Test empty password
        empty_result = login_validator.check_field_validation(xpath_selectors["password"], "", expected_error=True)
        assert empty_result["error_detected"], "Empty password should trigger validation error"

        # Test too short password (if site has minimum length requirement)
        short_result = login_validator.check_field_validation(xpath_selectors["password"], "123", expected_error=True)
        # This assertion may vary based on site requirements

        # Test valid format password
        valid_result = login_validator.check_field_validation(xpath_selectors["password"], "password123",
                                                              expected_error=False)
        assert not valid_result["error_detected"], "Valid password should not trigger validation error"

    @pytest.mark.slow
    def test_brute_force_protection(self, login_validator):
        """Test if login has brute force protection."""
        login_validator.navigate_to_login()

        # Try multiple failed login attempts
        protection_detected = False
        captcha_detected = False
        timeout_detected = False

        for i in range(5):
            result = login_validator.attempt_login("test@example.com", f"wrongpassword{i}")

            # Check for captcha
            try:
                captcha_elements = login_validator.driver.find_elements(By.XPATH,
                                                                        "//*[contains(@class, 'captcha') or contains(@class, 'recaptcha') or contains(@id, 'captcha')]")
                if any(el.is_displayed() for el in captcha_elements):
                    captcha_detected = True
                    protection_detected = True
                    break
            except:
                pass

            # Check for timeout messages
            try:
                timeout_texts = ["too many", "try again", "timeout", "wait", "locked"]
                for text in timeout_texts:
                    timeout_elements = login_validator.driver.find_elements(By.XPATH,
                                                                            f"//*[contains(text(), '{text}')]")
                    if any(el.is_displayed() for el in timeout_elements):
                        timeout_detected = True
                        protection_detected = True
                        break
            except:
                pass

            time.sleep(1)

        # This is not a strict assertion - some sites may not have protection
        # Just log the result for information
        if protection_detected:
            print("✓ Brute force protection detected")
        else:
            print("No obvious brute force protection detected within 5 attempts")

    def test_password_reset(self, login_validator):
        """Test password reset functionality."""
        login_validator.navigate_to_login()

        reset_link_found = False
        reset_selectors = [
            "//a[contains(text(), 'Forgot')]",
            "//a[contains(text(), 'Reset')]",
            "//span[contains(text(), 'Forgot')]",
            "//button[contains(text(), 'Forgot')]",
            "//div[contains(text(), 'Forgot')]",
            "//p[contains(text(), 'Forgot')]",
            "//a[contains(@href, 'forgot')]",
            "//a[contains(@href, 'reset')]"
        ]

        start_url = login_validator.driver.current_url

        for selector in reset_selectors:
            try:
                reset_elements = login_validator.driver.find_elements(By.XPATH, selector)
                for element in reset_elements:
                    if element.is_displayed():
                        reset_link_found = True
                        # Just check if link exists, don't click as we don't want to trigger real password resets
                        break
            except:
                continue

            if reset_link_found:
                break

        # Just log finding, don't enforce as a requirement
        if reset_link_found:
            print("✓ Password reset link found")
        else:
            print("No password reset link found")

'''
if __name__ == "__main__":
    # This allows the file to be both importable and executable
    print("This module is designed to be run with pytest.")
    print("Example: pytest test_login_validator.py --url https://app.example.invalid/")
'''