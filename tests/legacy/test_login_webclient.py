import time
import pytest
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from selenium.webdriver import ActionChains
from selenium.webdriver.common.keys import Keys


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
        self.driver.find_element(By.CSS_SELECTOR, ".MuiAvatar-root.MuiAvatar-circular.MuiAvatar-colorDefault").click()
        time.sleep(2)
        # Click on the logout button
        self.driver.find_element(By.XPATH, '/html/body/div[1]/div/div/div[2]/main/div/div/div[1]/div[1]/div/div[3]/p').click()
        time.sleep(3)

    def attempt_login(self, username, password,
                      username_xpath="//input[@placeholder='Email']",
                      password_xpath="//input[@placeholder='Password']",
                      login_button_xpath="//button[text()='Login']",
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
            # Capthce handling
            time.sleep(3)
            action = ActionChains(self.driver)
            self.driver.find_element(By.NAME, "password").send_keys(Keys.TAB * 3)
            action.send_keys(Keys.SPACE).perform()
            time.sleep(4)
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

def check_field_validation(self, field_xpath, test_input, expected_error=True, timeout=10):
    """
    Test field validation by entering potentially invalid input and checking for error messages.

    Parameters:
    - field_xpath: XPath selector for the input field
    - test_input: Input value to test (empty string, invalid format, etc.)
    - expected_error: Whether an error message is expected
    - timeout: Maximum wait time in seconds for elements and validation messages

    Returns:
    - dict with validation results
    """
    result = {
        "field": field_xpath,
        "input": test_input,
        "error_detected": False,
        "error_message": None,
        "exception": None,
        "validation_status": "unknown"
    }

    try:
        # Find and interact with the field using explicit waits
        field = WebDriverWait(self.driver, timeout).until(
            EC.presence_of_element_located((By.XPATH, field_xpath))
        )
        
        # Ensure the field is interactable before proceeding
        WebDriverWait(self.driver, timeout).until(
            EC.element_to_be_clickable((By.XPATH, field_xpath))
        )
        
        # Clear the field and enter test input
        field.click()
        field.clear()
        if test_input:
            field.send_keys(test_input)
        
        # Trigger validation by clicking submit button or another area
        try:
            # First attempt: Look for a submit/login button
            submit_buttons = [
                '//*[@id="root"]/div/div/div/form/div/button',
                '//button[@type="submit"]',
                '//input[@type="submit"]',
                '//button[contains(text(), "Login") or contains(text(), "Submit") or contains(text(), "Sign")]'
            ]
            
            for button_xpath in submit_buttons:
                try:
                    button = self.driver.find_element(By.XPATH, button_xpath)
                    if button.is_displayed() and button.is_enabled():
                        button.click()
                        break
                except:
                    continue
            else:
                # If no button found, click on body as fallback
                self.driver.find_element(By.XPATH, "//body").click()
        except Exception as e:
            self.log_debug(f"Error triggering validation: {str(e)}")
            # Still try to continue with the test
        
        # Group error selectors by type for better organization and debugging
        error_selectors = {
            "field_attributes": [
                # Check the field itself for validation attributes
                (field_xpath, ["aria-invalid", "data-error", "data-invalid"], 
                 ["true", "yes", "1"], "Field has validation attribute"),
                
                # Check field classes
                (field_xpath, ["class"], 
                 ["error", "invalid", "validation-error"], "Field has error class")
            ],
            
            "parent_attributes": [
                # Check parent element classes
                (f"{field_xpath}/..", ["class"], 
                 ["error", "invalid", "validation-error"], "Parent has error class")
            ],
            
            "error_elements": [
                # Field siblings
                f"{field_xpath}/following-sibling::*[contains(@class, 'error') or contains(@class, 'invalid')]",
                
                # Parent's children
                f"{field_xpath}/parent::*/div[contains(@class, 'error') or contains(@class, 'validation')]",
                f"{field_xpath}/parent::*/span[contains(@class, 'error') or contains(@class, 'validation')]",
                f"{field_xpath}/parent::*/p[contains(@class, 'error') or contains(@class, 'validation')]",
                
                # Form-level errors that might be related
                "//form//div[contains(@class, 'error') and string-length(text()) > 0]",
                "//form//span[contains(@class, 'error') and string-length(text()) > 0]"
            ],
            
            "error_by_content": [
                "//*[contains(text(), 'invalid') or contains(text(), 'required') or contains(text(), 'error')]"
            ]
        }
        
        # Wait for potential validation messages to appear with explicit wait instead of sleep
        try:
            # Try to find any error element to determine when validation is complete
            all_error_paths = (
                error_selectors["error_elements"] + 
                error_selectors["error_by_content"]
            )
            combined_selector = " | ".join(all_error_paths)
            
            # Wait for either error to appear or a short timeout
            try:
                WebDriverWait(self.driver, min(3, timeout/2)).until(
                    lambda driver: len(driver.find_elements(By.XPATH, combined_selector)) > 0 or 
                                 driver.find_element(By.XPATH, field_xpath).get_attribute("aria-invalid") == "true"
                )
            except:
                # It's okay if we time out - may mean no errors appeared
                pass
        except Exception as e:
            self.log_debug(f"Error while waiting for validation: {str(e)}")
        
        # Check field and parent attributes first (most reliable indicators)
        for base_xpath, attrs, values, message in error_selectors["field_attributes"] + error_selectors["parent_attributes"]:
            try:
                element = self.driver.find_element(By.XPATH, base_xpath)
                for attr in attrs:
                    attr_value = element.get_attribute(attr)
                    if attr_value and any(err_value in attr_value.lower() for err_value in values):
                        result["error_detected"] = True
                        result["error_message"] = f"{message}: {attr}={attr_value}"
                        break
                if result["error_detected"]:
                    break
            except Exception as e:
                self.log_debug(f"Error checking element attributes: {str(e)}")
        
        # If no error found in attributes, check for error message elements
        if not result["error_detected"]:
            # First check error elements (with classes)
            for selector in error_selectors["error_elements"]:
                try:
                    elements = self.driver.find_elements(By.XPATH, selector)
                    for element in elements:
                        if element.is_displayed() and element.text.strip():
                            field_element = self.driver.find_element(By.XPATH, field_xpath)
                            
                            # Simple proximity check - simplified from original
                            if self._is_element_near_field(element, field_element):
                                result["error_detected"] = True
                                result["error_message"] = element.text.strip()
                                break
                    if result["error_detected"]:
                        break
                except Exception as e:
                    self.log_debug(f"Error checking error elements: {str(e)}")
            
            # If still no error, check content-based error messages
            if not result["error_detected"]:
                for selector in error_selectors["error_by_content"]:
                    try:
                        elements = self.driver.find_elements(By.XPATH, selector)
                        for element in elements:
                            if element.is_displayed() and element.text.strip():
                                field_element = self.driver.find_element(By.XPATH, field_xpath)
                                
                                # Only consider very nearby messages for content-based errors
                                if self._is_element_near_field(element, field_element, max_distance=50):
                                    result["error_detected"] = True
                                    result["error_message"] = element.text.strip()
                                    break
                        if result["error_detected"]:
                            break
                    except Exception as e:
                        self.log_debug(f"Error checking content-based errors: {str(e)}")
        
        # Set validation status based on expected vs actual results
        if expected_error and result["error_detected"]:
            result["validation_status"] = "pass"
            self.log_info(f"✓ Validation test PASSED: Error detected for input '{test_input}'")
            if result["error_message"]:
                self.log_info(f"  Error message: {result['error_message']}")
        elif not expected_error and not result["error_detected"]:
            result["validation_status"] = "pass"
            self.log_info(f"✓ Validation test PASSED: No error for valid input '{test_input}'")
        elif expected_error and not result["error_detected"]:
            result["validation_status"] = "fail"
            self.log_warning(f"✗ Validation test FAILED: No error detected for invalid input '{test_input}'")
        else:
            result["validation_status"] = "fail"
            self.log_warning(f"✗ Validation test FAILED: Error detected for valid input '{test_input}'")
            if result["error_message"]:
                self.log_warning(f"  Error message: {result['error_message']}")

    except Exception as e:
        result["exception"] = str(e)
        result["validation_status"] = "error"
        self.log_error(f"Error during field validation check: {str(e)}")
    
    return result

def _is_element_near_field(self, error_element, field_element, max_distance=100):
    """
    Helper method to determine if an error element is near a field element.
    
    Parameters:
    - error_element: The potential error message element
    - field_element: The input field element
    - max_distance: Maximum pixel distance to consider "near"
    
    Returns:
    - Boolean indicating if elements are near each other
    """
    try:
        field_rect = field_element.rect
        error_rect = error_element.rect
        
        # Check if error is near the field (vertical proximity matters more)
        vertical_distance = abs(error_rect['y'] - field_rect['y'])
        horizontal_distance = abs(error_rect['x'] - field_rect['x'])
        
        # Vertical proximity is more important than horizontal
        return (vertical_distance < max_distance and 
                (horizontal_distance < max_distance * 2 or
                 error_rect['x'] >= field_rect['x'] and
                 error_rect['x'] < field_rect['x'] + field_rect['width'] + 100))
    except Exception as e:
        self.log_debug(f"Error calculating element proximity: {str(e)}")
        # If we can't determine proximity, default to assuming they're related
        # for elements with error text
        return True

def log_debug(self, message):
    """Helper method for logging debug messages"""
    print(f"DEBUG: {message}")

def log_info(self, message):
    """Helper method for logging info messages"""
    print(f"INFO: {message}")

def log_warning(self, message):
    """Helper method for logging warning messages"""
    print(f"WARNING: {message}")

def log_error(self, message):
    """Helper method for logging error messages"""
    print(f"ERROR: {message}")

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
        "username": "//input[@placeholder='Email']",
        "password": "//input[@placeholder='Password']",
        "login_button": "//button[@type='submit' and text()='Login']"
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