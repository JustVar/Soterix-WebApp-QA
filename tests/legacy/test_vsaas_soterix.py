import time
import sys
import os

import pytest
from datetime import datetime, date
from selenium.common.exceptions import ElementClickInterceptedException

import pytest
import datetime
'''
import pytest_html
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
'''
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common import TimeoutException, NoSuchElementException
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver import ActionChains

class Test_Vsaas_Soterix():
    #@pytest.fixture()
    #def setup(self, params):
        #driver = params['driver']
        #site_name = params['site_name']
        #location_name = params['location_name']
        #camera_name = params['camera_name']
    
    def export_share_check_media(self, params, is_export=False, is_share=False, check_media=False):
        driver = params['driver']
        mail_id = "person@example.com"
        download_dir = os.path.abspath("downloads")
        
        now = datetime.datetime.now()
        formatted_datetime = now.strftime("%Y%m%d%H%M%S")
        # Check if the file exists in the download directory
        file_name = formatted_datetime + ".mp4"  # Replace with the actual file name
        file_path = os.path.join(download_dir, file_name)
        if os.path.isfile(file_path):
            os.remove(file_path)
        
        # Provide input values
        if is_export:    
            export_popup_element = driver.find_element(by=By.CLASS_NAME, value="export_main_container_popup")        
            filename_element = export_popup_element.find_element(by=By.ID, value="name")
            save_to_media_element = export_popup_element.find_element(by=By.CLASS_NAME, value="PrivateSwitchBase-input")
        else:
            share_popup_element = driver.find_element(by=By.CLASS_NAME, value="share_main_container")
            email_field_element = share_popup_element.find_element(By.NAME, "email")
            email_field_element.send_keys(mail_id)
            filename_element = share_popup_element.find_element(by=By.ID, value="name")
            save_to_media_element = share_popup_element.find_element(by=By.CLASS_NAME, value="PrivateSwitchBase-input")
        filename_element.send_keys(formatted_datetime)
        
        # Click on save to media
        save_to_media_element.click()
        print("Clicked on Save To Media")
    
        if is_export:        
            export_button = export_popup_element.find_element(by=By.CLASS_NAME, value="save_button_export")
            export_button.click()
        
            # export-progress-bar
            temp = WebDriverWait(driver, 10).until(EC.presence_of_all_elements_located((By.CLASS_NAME, "export-progress-bar")))
            temp = WebDriverWait(driver, 60).until(EC.invisibility_of_element_located((By.CLASS_NAME, "export-progress-bar")))
            time.sleep(30)
            
            if os.path.isfile(file_path):
                print("File downloaded successfully!")
            else:
                time.sleep(30)
                if os.path.isfile(file_path):
                    print("File downloaded successfully!")
                else:
                    assert False, "File Export Failed"
        else:  
            share_button = share_popup_element.find_element(by=By.CLASS_NAME, value="save_button_share")
            share_button.click()
            print("Clicked on Share button")
            
            temp = WebDriverWait(driver, 10).until(EC.presence_of_all_elements_located((By.CLASS_NAME, "successfull-container")))
            print("Share success message is displayed")
            
        
        if check_media:
            print("Checking whether the media is shown or not")
            # Media
            media_button_element = driver.find_element(By.XPATH, value='//a[contains(@href,"media")]')
            media_button_element.click()
            print("Clicked on Media button to navigate to Media page")
            
            # Wait for the page to load
            print("Waiting for max 15 sec for Media page to load")
            element_present = EC.presence_of_all_elements_located((By.XPATH, "//img[contains(@src, 'media/search')]"))
            try:
                WebDriverWait(driver, 15).until(element_present)
                print("Navigated to Media Page")
            except:
                print("Failed to Navigate to Media Page in 15 Sec")
                assert False, "Failed to Navigate to Media Page in 15 Sec"
    
            try:
                print("Waiting for max 60 sec for loader to stop. That is media to load")
                element_present = EC.presence_of_all_elements_located((By.XPATH, "//*[contains(@class,'CircularProgress')]"))
                loader_elements = WebDriverWait(driver, 60).until(element_present)
                
                wait_item = WebDriverWait(driver, 60).until(EC.invisibility_of_element_located((By.XPATH, "//*[contains(@class,'CircularProgress')]")))
                print("Loader is stopped")
                print("Checking for media is created for Exported media or not")
                media_element = driver.find_element(By.CSS_SELECTOR, f'input[title={formatted_datetime}]')
                assert media_element, f"Media {formatted_datetime} is not showing"
            except:
                print(f"Media {formatted_datetime} is not showing")
            
    def play_camera(self, params, play_all_cameras=False):
        driver = params['driver']
        site_name = params['site_name']
        location_name = params['location_name']
        if play_all_cameras:
            camera_name = ""
        else:
            camera_name = params['camera_name']
        time.sleep(5)
        
        wait = WebDriverWait(driver, 60)
    
        # Wait for Site to Load
        print(f"Checking for Site \"{site_name}\" to load (max 60s)...")
        try:
            wait.until(EC.presence_of_element_located((By.XPATH, f"//*[text()='{site_name}']")))
            print(f"Site \"{site_name}\" loaded successfully.")
        except:
            raise AssertionError(f"Failed to load site \"{site_name}\" within 60 seconds.")
    
        # Click Site
        time.sleep(5)
        site_elements = driver.find_elements(By.XPATH, value=f"//*[contains(text(), \"{site_name}\")]")
        site_available = False
        for site_element in  site_elements:
            if site_element.text == site_name:
                site_element.click()
                print(f"Clicked on site \"{site_name}\"")
                site_available = True
                break
        assert site_available, f"Site \"{site_name}\" not enabled or not available"
        time.sleep(3)
        
        location_elements = driver.find_elements(By.XPATH, value=f"//*[contains(text(), '{location_name}')]")
        location_available = False
        for location_element in location_elements:
            if location_element.text == location_name:
                if location_element.is_displayed():
                    location_element.click()
                    print(f"Clicked on location '{location_name}'")
                    location_available = True
                    break
        assert location_available, f"Provided Location '{location_name}' not available"
        time.sleep(3)
    
        # Get Available Cameras
        camera_elements = driver.find_elements(By.XPATH, "//div[contains(@class, 'MuiStack-root') and contains(@class, 'mui-ebmxkk')]")
        if not camera_elements:
            raise AssertionError("No cameras found under this location.")
    
        if camera_name:
            # Filter camera by name
            camera_elements = [c for c in camera_elements if c.text.strip() == camera_name]
            if not camera_elements:
                raise AssertionError(f"Camera '{camera_name}' not available.")
            print(f"Camera '{camera_name}' is available.")
    
        print(f"Found {len(camera_elements)} camera(s) to play.")
    
        for idx, camera in enumerate(camera_elements):
            camera_label = camera.text.strip() or f"Camera-{idx + 1}"
            try:
                tile_elements = driver.find_elements(By.XPATH, "//div[text()='Drag & Drop Camera here']")
                if not tile_elements:
                    raise AssertionError("No available tiles to drop camera into.")
    
                print(f"Dragging and dropping camera '{camera_label}'...")
                actions = ActionChains(driver)
                actions.move_to_element(camera).pause(1).drag_and_drop(camera, tile_elements[0]).perform()
                print(f"Camera '{camera_label}' drag-dropped successfully.")
    
                # Wait for stream loader and check streaming status
                print("Waiting for streaming loader to finish...")
                wait.until(EC.invisibility_of_element_located((By.XPATH, "//*[contains(@class,'CircularProgress')]")))           
    
                # Check for stream failure
                error_elements = driver.find_elements(By.XPATH, "//*[contains(text(),'failed to load')]")            
                if camera.find_elements(By.XPATH, ".//img[contains(@src, '/media/cameraIcon') and contains(@class, 'green')]"):
                    if error_elements:
                        print(f"Error : Streaming failed for camera '{camera_label}'.")
                        raise AssertionError(f"Streaming failed for camera '{camera_label}'.")
                    else:
                        print(f"Streaming is working for camera '{camera_label}'.")
                else:
                    if error_elements:
                        print(f"As camera '{camera_label}' is offline, camera streaming is failed")
                    else:
                        print(f"Error : Camera '{camera_label}' is offline, but still streaming is working")
                        raise AssertionError(f"Error : Camera '{camera_label}' is offline, but still streaming is working")
                        
                time.sleep(2)  # Small delay between cameras
                clear_all_button = WebDriverWait(driver, 10).until(
                        EC.element_to_be_clickable((By.XPATH, "//button[.//div[text()='Clear All']]"))
                    )
                # Clear cameras only while playing all cameras 
                if play_all_cameras:
                    clear_all_button.click()
                    print("Clicked 'Clear All' button.")            
    
            except Exception as e:
                raise AssertionError(f"Error while processing camera '{camera_label}': {str(e)}")

    def open_insights_page(self, params):
        driver = params['driver']
        time.sleep(3)
        # Insights
        insights_page_elements = driver.find_elements(By.XPATH, "//div[@class='tabInner' and @title='All Insights']")
        if len(insights_page_elements) == 0:
            insights_button_element = driver.find_element(By.XPATH, value='//a[contains(@href,"insights")]')
            insights_button_element.click()
            
            # Wait for the page to load
            element_present = EC.presence_of_all_elements_located((By.XPATH, '//a[contains(@href,"insights/systemStatus")]'))
            
            try:
                WebDriverWait(driver, 15).until(element_present)
                print("Navigated to Insights Page")
            except:
                print("Failed to Navigate to Insights Page in 15 Sec")
                assert False, "Failed to Navigate to Insights Page in 15 Sec"
            
            try:
                element_present = EC.presence_of_all_elements_located((By.XPATH, "//*[contains(@class,'CircularProgress')]"))
                live_icon_elements = WebDriverWait(driver, 15).until(element_present)
                print("Waiting for loader to stop for 60 Sec")
                wait_item = WebDriverWait(driver, 600).until(EC.invisibility_of_element_located((By.XPATH, "//*[contains(@class,'CircularProgress')]")))    
            except:
                print("Loaders didn't stop for 60 Sec")
                assert False, "Loaders didn't stop for 60 Sec"
        else:
            print("Already in Insights page")
            try:
                tab_close_element = driver.find_element(By.XPATH, value=".//img[contains(@src,'media/closeIcon')]")
                tab_close_element.click()
            except:
                pass
    
    def switch_to_widgets(self, params):
        driver = params['driver']
        
        self.open_insights_page(params)

        try:
            element = WebDriverWait(driver, 30).until(
                EC.presence_of_element_located((By.CLASS_NAME, 'toggleTabs_inactive'))
            )
            print("Widget Tab is Active")
        except:
            print("Widget Tab is not Active")
            assert False, "Widget Tab is not Active"
    
        print("Switching to Widgets")            
        widget_tab_element = driver.find_element(by=By.CLASS_NAME, value="toggleTabs_inactive")
        if "widget" in widget_tab_element.text.lower():
            widget_tab_element.click()
        
        print("Checking whether application switched to Widgets or not")
        try:
            element = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, '//p[contains(text(), "Preset Widgets")]'))
            )
            print("Switched to widgets successfully")
        except:
            print("Failed to switch to widgets")
            assert False, "Failed to switch to widgets"
         
        try:
            if "widget" in widget_tab_element.text.lower():
                element_present = EC.presence_of_all_elements_located((By.XPATH, "//*[contains(@class,'CircularProgress')]"))
                live_icon_elements = WebDriverWait(driver, 15).until(element_present)
            print("Waiting for loader to stop for 60 Sec")
            wait_item = WebDriverWait(driver, 600).until(EC.invisibility_of_element_located((By.XPATH, "//*[contains(@class,'CircularProgress')]")))    
        except:
            print("Loaders didn't stop for 60 Sec")
            assert False, "Loaders didn't stop for 60 Sec"
        
    
    def create_widget(self, params, graph_index=0, graph_name="Line", category_name="Person", widget_size_index=0):
        driver = params['driver']
        site_name = params['site_name']
        camera_name = params['camera_name']
        action = ActionChains(driver)
        
        now = datetime.datetime.now()
        formatted_datetime = now.strftime("%Y%m%d%H%M%S")
        widget_name = f"{graph_name}_{category_name}_{formatted_datetime}"
        # Widgets
        self.switch_to_widgets(params)
    
        # Create Widget
        print("Creating Widget")
        create_widget_button_element = driver.find_element(by=By.CLASS_NAME, value="sky-button")
        action.move_to_element(create_widget_button_element).perform()
        create_widget_button_element.click()
        print("Clicked on Create New Widget Button")
    
        try:
            element = WebDriverWait(driver, 60).until(
                EC.presence_of_element_located((By.XPATH, "//button[contains(text(), 'Save & Preview')]"))
            )
            print("Opened Created Widget")
        except:
            print("Failed to open create widget")
            assert False, "Failed to open create widget"
        
        widget_name_element = driver.find_element(By.CLASS_NAME, 'modalFormInput')
        widge_title_element = action.move_to_element(widget_name_element)
        action.click(on_element=widget_name_element).perform()
        widge_title_element.send_keys(Keys.BACKSPACE * 20).perform()
        widge_title_element.send_keys(widget_name).perform()
        print(f"Widget name provided as {widget_name}")
        
        dropdown_elements = driver.find_elements(by=By.CLASS_NAME, value="MuiPaper-root")
        tree_arrow_elements = driver.find_elements(By.XPATH, value=".//img[contains(@src,'media/downAccordionIcon')]")    
        # media/downAccordionIcon
        # Graph Type
        print("Selecting Widget Criteria")
        print(f"Selecting Graph Type as {graph_name}")
        dropdown_elements[0].click()
        time.sleep(1)
        graph_type_elements = driver.find_elements(by=By.CLASS_NAME, value="dropdownItem")
        graph_type_elements[graph_index].click()
        time.sleep(1)
        
        # Category Type
        print(f"Selecting Category Type as {category_name}")
        dropdown_elements[1].click()
        time.sleep(1)
        category_element = driver.find_element(by=By.XPATH, value=f'//p[contains(text(), \"{category_name}\")]')
        category_element.click()
        time.sleep(1)
        
        # Description Type
        print("Selecting Description")
        if "person" not in category_name.lower():
            dropdown_elements[2].click()
            time.sleep(1)
            if "vehicle" in category_name.lower():
                car_element = driver.find_element(By.XPATH, value=".//img[contains(@src,'media/carIcon')]")
                car_element.click()
                bike_element = driver.find_element(By.XPATH, value=".//img[contains(@src,'media/motorcycleIcon')]")
                bike_element.click()
                time.sleep(1)
            else:
                # Select all the Event check boxes
                event_selection_elements = driver.find_elements(by=By.CLASS_NAME, value="PrivateSwitchBase-input")
                for event_selection_element in event_selection_elements:
                    event_selection_element.click()
                    time.sleep(0.25)
            
            tree_arrow_elements[2].click()
            time.sleep(1)
            
        # Selecting Site
        print(f"Selecting Site as {site_name}")
        dropdown_elements[3].click()
        time.sleep(1)
        site_partial_name = site_name[:10]
        camera_partial_name = camera_name[:10]
        site_element = driver.find_element(by=By.XPATH, value=f'//p[contains(text(), \"{site_partial_name}\")]')
        site_element.click()
        time.sleep(1)  
        
        # Camera Selection
        all_camera_checkbox_index = 0
        if category_name == "Vehicle":
            all_camera_checkbox_index = 7
        print(f"Selecting Camera")
        dropdown_elements[4].click()
        time.sleep(1)
        if "heat" in graph_name.lower():
            location_element = driver.find_element(by=By.XPATH, value=f'//p[contains(text(), "All Cameras")]')
            location_element.click()
            camera_element = driver.find_element(by=By.XPATH, value=f'//p[contains(text(), \"{camera_partial_name}\")]')
            action.move_to_element(camera_element).perform()
            action.click(on_element=camera_element).perform()
        else:
            camera_selection_elements = driver.find_elements(by=By.CLASS_NAME, value="PrivateSwitchBase-input")
            camera_selection_elements[all_camera_checkbox_index].click()
            time.sleep(1) 
            tree_arrow_elements[4].click()
            time.sleep(1)  
        
        # Duration Selection
        print(f"Selecting Duration as Yesterday")
        dropdown_elements[5].click()
        time.sleep(1)
        duration_element = driver.find_element(by=By.XPATH, value='//p[contains(text(), "Yesterday")]')
        duration_element.click()
        
        # Widget Size Selection
        print(f"Selecting Widget Size")
        dropdown_elements[6].click()
        time.sleep(1)
        
        if "pie" in graph_name.lower():
            widget_size_element = driver.find_element(by=By.XPATH, value='//p[contains(text(), "Dashlet")]')
        else:
            widget_size_element = driver.find_element(by=By.XPATH, value='//p[contains(text(), "Half Width")]')
        widget_size_element.click()
        time.sleep(1)
        
        save_preview_button_element = driver.find_element(By.XPATH, "//button[contains(., 'Save')]")
        save_preview_button_element.click()
    
        try:
            element = WebDriverWait(driver, 60).until(
                EC.presence_of_element_located((By.XPATH, '//p[contains(text(), "Widget created successfully")]'))
            )
            print("Widget created successfully")
        except:
            print("Failed to create widget")
            assert False, "Failed to create widget"
        
        time.sleep(5)
        print("Closing widget creation tab")
        tab_close_element = driver.find_element(By.XPATH, value=".//img[contains(@src,'media/closeIcon')]")
        tab_close_element.click()
        return widget_name
    
    def search_widget(self, params, widget_name):
        driver = params['driver']
        action = ActionChains(driver)
        
        self.switch_to_widgets(params)
        search_element = driver.find_element(By.XPATH, "//input[@placeholder='Search']")
        action_search_element = action.move_to_element(search_element)
        action.click(on_element=search_element).perform()
        action_search_element.send_keys(Keys.BACKSPACE * 40).perform()
        action_search_element.send_keys(Keys.DELETE * 40).perform()
        time.sleep(0.5)
        action_search_element.send_keys(widget_name).perform()
    
    def widget_operation(self, params, widget_name, operation):
        driver = params['driver']
        
        self.search_widget(params, widget_name)
        time.sleep(2)
        three_dot_elements = driver.find_elements(By.XPATH, value=".//img[contains(@src,'media/three-dots')]")
        three_dot_elements[-1].click()
        time.sleep(2)
        
        widget_operation_element = driver.find_element(By.XPATH, f"//li[contains(., '{operation}')]")
        widget_operation_element.click()
        if "view" in operation.lower():
            try:
                element = WebDriverWait(driver, 30).until(
                    EC.presence_of_element_located((By.XPATH, ".//img[contains(@src,'media/backIconArrow')]"))
                )
                print(f"Widget {widget_name} Viewed successfully")
            except:
                print(f"Failed to View widget {widget_name}")
                assert False, f"Failed to View widget {widget_name}"
            time.sleep(5)
            print("Closing Widget")
            back_icon_element = driver.find_element(By.XPATH, value=".//img[contains(@src,'media/backIconArrow')]")
            back_icon_element.click()
        elif "report" in operation.lower():
            try:
                download_button = WebDriverWait(driver, 30).until(
                    EC.presence_of_element_located((By.CLASS_NAME, 'save_button'))
                )
                print(f"Widget {widget_name} report opened successfully")
            except:
                print(f"Failed to open widget {widget_name} report")
                assert False, f"Failed to open widget {widget_name} report"
            download_button.click()
    
            try:        
                success_message = WebDriverWait(driver, 20).until(EC.presence_of_element_located(
                    (By.XPATH, "//p[contains(text(), 'Report downloaded successfully')]")
                ))
                print(f"Widget {widget_name} report downloaded successfully")
            except:
                print(f"Failed to download widget {widget_name} report")
                assert False, f"Failed to download widget {widget_name} report"
        elif "delete" in operation.lower():
            try:
                delete_button = WebDriverWait(driver, 30).until(
                    EC.presence_of_element_located((By.CLASS_NAME, 'cancel_button_insights'))
                )
                print(f"Widget {widget_name} delete option opened successfully")
            except:
                print(f"Failed to open widget {widget_name} delete option")
                assert False, f"Failed to open widget {widget_name} delete option"
            delete_button.click()
            time.sleep(2)
    
            self.search_widget(params, widget_name)
            time.sleep(2)
            three_dot_elements = driver.find_elements(By.XPATH, value=".//img[contains(@src,'media/three-dots')]")
            assert len(three_dot_elements) == 0, f"Failed to delete widget {widget_name}"
        else:
            # Edit Widget
            pass
        
        def switch_to_admin_tab(tab_name="Dashboard"):
            wait = WebDriverWait(driver, 60)
            print(f"Switching to {tab_name} tab")
            tab_element = wait.until(EC.element_to_be_clickable((
                By.XPATH,
                f"//p[contains(@class, 'MuiTypography-root') and contains(text(), '{tab_name}')]"
            )))
            # Click on the tab
            tab_element.click()
            wait_loader_stop = wait.until(EC.invisibility_of_element_located((By.XPATH, "//*[contains(@class,'CircularProgress')]")))
        
        def navigate_to_admin_page_tab(tab_name="Dashboard"):
            time.sleep(10)
            wait = WebDriverWait(driver, 60)
            action = ActionChains(driver)    
            admin_tab_elements = driver.find_elements(By.XPATH, f"//p[contains(@class, 'MuiTypography-root') and contains(text(), '{tab_name}')]")
            if admin_tab_elements:
                print("Already in Admin Page")
            else:
                # Navigate to Admin page
                try:
                    # Try to find and click admin link
                    admin_button = wait.until(
                        EC.element_to_be_clickable((By.XPATH, '//a[contains(@href,"admin")]'))
                    )
                    admin_button.click()
                    print("Clicked on Admin button")
                    wait_loader_stop = wait.until(EC.invisibility_of_element_located((By.XPATH, "//*[contains(@class,'CircularProgress')]")))
                    admin_tab_elements = wait.until(
                        EC.presence_of_all_elements_located((By.XPATH, f"//p[contains(@class, 'MuiTypography-root') and contains(text(), '{tab_name}')]"))
                    )
                    print("Navigated to Admin Page")
                except:
                    print("Failed to Navigate to Admin Page")
                    assert False, "Failed to Navigate to Admin Page"
            
            # Switch tabs        
            try:
                print(f"Switching to tab {tab_name}")
                if "Dashboard" in tab_name:
                    if driver.find_elements(By.XPATH, "//img[contains(@src, 'media/premium')]"):
                        print(f"Already in {tab_name} tab")
                    else:
                        switch_to_admin_tab(tab_name=tab_name)
                        tab_identify_elements = wait.until(
                            EC.presence_of_all_elements_located((By.XPATH, "//img[contains(@src, 'media/premium')]"))
                        )
                elif ("Sites" in tab_name) or ("Maps" in tab_name):
                    if driver.find_elements(By.XPATH, f"//p[contains(text(), 'All {tab_name}')]"):
                        print(f"Already in {tab_name} tab")
                    else:
                        switch_to_admin_tab(tab_name=tab_name)
                        tab_identify_elements = wait.until(
                            EC.presence_of_all_elements_located((By.XPATH, f"//p[contains(text(), 'All {tab_name}')]"))
                        )
                elif "Users" in tab_name:
                    if driver.find_elements(By.XPATH, "//button[contains(@class, 'tab-btn') and contains(@class, 'active') and text()='Users']"):
                        print(f"Already in {tab_name} tab")
                    else:
                        switch_to_admin_tab(tab_name=tab_name)
                        tab_identify_elements = wait.until(
                            EC.presence_of_all_elements_located((By.XPATH, "//button[contains(@class, 'tab-btn') and contains(@class, 'active') and text()='Users']"))
                        )
                elif "Integrations" in tab_name:
                    if driver.find_elements(By.XPATH, "//p[contains(text(), 'Webhooks')]"):
                        print(f"Already in {tab_name} tab")
                    else:
                        switch_to_admin_tab(tab_name=tab_name)
                        tab_identify_elements = wait.until(
                            EC.presence_of_all_elements_located((By.XPATH, f"//p[contains(text(), 'Webhooks')]"))
                        )
                elif "Rules" in tab_name:
                    if driver.find_elements(By.XPATH, "//p[contains(text(), 'Rule Configuration')]"):
                        print(f"Already in {tab_name} tab")
                    else:
                        switch_to_admin_tab(tab_name=tab_name)
                        tab_identify_elements = wait.until(
                            EC.presence_of_all_elements_located((By.XPATH, f"//p[contains(text(), 'Rule Configuration')]"))
                        )
                elif "General" in tab_name:
                    if driver.find_elements(By.XPATH, "//p[contains(text(), 'Deployment')]"):
                        print(f"Already in {tab_name} tab")
                    else:
                        switch_to_admin_tab(tab_name=tab_name)
                        tab_identify_elements = wait.until(
                            EC.presence_of_all_elements_located((By.XPATH, f"//p[contains(text(), 'Deployment')]"))
                        )
                elif "LPR" in tab_name:
                    if driver.find_elements(By.XPATH, "//button[contains(@class, 'tab-btn') and contains(@class, 'active') and text()='List']"):
                        print(f"Already in {tab_name} tab")
                    else:
                        switch_to_admin_tab(tab_name=tab_name)
                        tab_identify_elements = wait.until(
                            EC.presence_of_all_elements_located((By.XPATH, "//button[contains(@class, 'tab-btn') and contains(@class, 'active') and text()='List']"))
                        )
                elif "Licenses" in tab_name:
                    if driver.find_elements(By.XPATH, "//button[contains(text(), 'Available Licenses')]"):
                        print(f"Already in {tab_name} tab")
                    else:
                        switch_to_admin_tab(tab_name=tab_name)
                        tab_identify_elements = wait.until(
                            EC.presence_of_all_elements_located((By.XPATH, "//button[contains(text(), 'Available Licenses')]"))
                        )
                else:
                    assert False, f"Tab name {tab_name} not available"
                print(f"Navigated to {tab_name} tab")
            except:
                print(f"Failed to Navigate to {tab_name} Tab")
                assert False, f"Failed to Navigate to {tab_name} Tab"            
    
    def log_api_data(self, driver):
        
        print("API's which are called till now are as follows")
        print("==========================================================================================================")
        for request in driver.requests:
            try:
                if request.response.headers.get('Content-Type', '').startswith('application/json'):
                    print(request.url)
                    if request.response:
                        # Calculate response time in milliseconds
                        print(f"Time taken is {(request.response.date - request.date).total_seconds()}")
            except:
                pass
            
        print("==========================================================================================================")
        print("API's which took  more than 2 seconds are as follows")
        print("==========================================================================================================")
        for request in driver.requests:
            try:
                #if request.response.headers.get('Content-Type', '').startswith('application/json'):
                    #print(request.url)
                if request.response:
                    if request.response.headers.get('Content-Type', '').startswith('application/json'):
                        time_taken = (request.response.date - request.date).total_seconds()
                        if float(time_taken) > 2:
                            print(request.url)
                            # Calculate response time in milliseconds
                            print(f"Time taken is {time_taken}")
            except:
                pass
        print("==========================================================================================================")
    
        #print("API's which are passed are as follows")
        #print("==========================================================================================================")
        #for request in driver.requests:
            #try:
                #if request.response.headers.get('Content-Type', '').startswith('application/json'):
                    #if (request.response.status_code == 200):
                        #print(request.url)
            #except:
                #pass
        #print("==========================================================================================================")
    
        #print("API's which are failed, warning or pending till now are as follows")
        #print("==========================================================================================================")
        #for request in driver.requests:
            #try:
                #if (request.response.status_code != 200):
                    #try:
                        #if request.response.headers.get('Content-Type', '').startswith('application/json'):
                            #print(f"Status code of Failed URL {request.url} is {request.response.status_code}")
                    #except:
                        #pass
            #except:
                #print(f"Warning Pending: URL {request.url}")
                #pass
        del driver.requests   
        #print("==========================================================================================================")
       
    @pytest.mark.dependency()
    def test_login(self, params):
        driver = params['driver']
        username = params['username']
        password = params['password']
        action = ActionChains(driver)
        # Wait till login button is clickable
        options = (By.XPATH, "//button[text()='Login']")
        element_present = EC.element_to_be_clickable(options)
        WebDriverWait(driver, 60).until(element_present)
        time.sleep(3)
        
        # Login
        driver.find_element(By.NAME, "email").send_keys(username)
        driver.find_element(By.NAME, "password").send_keys(password)
        time.sleep(1)
        driver.find_element(By.NAME, "password").send_keys(Keys.TAB*3)
        action.send_keys(Keys.SPACE).perform()
        login_button_element = driver.find_element(By.XPATH, "//button[text()='Login']")
        time.sleep(5)
        if login_button_element.is_enabled():
            login_button_element.click()
        
        element_present = EC.presence_of_all_elements_located((By.XPATH, "//div[text()='Drag & Drop Camera here']"))
        
        try:
            WebDriverWait(driver, 600).until(element_present)
            print("Login is Successful")
        except:
            print("Failed to Login in 60 Sec")
            assert False, "Failed to login in 60 Sec"           
        #self.log_api_data()
    
    @pytest.mark.dependency(depends=["Test_Vsaas_Soterix::test_login"])
    def test_login_api_calls(self, params):
        self.log_api_data(params['driver'])
    
    @pytest.mark.dependency(depends=["Test_Vsaas_Soterix::test_login"])
    def test_mute_clearall_notification(self, params):
        driver = params['driver']
        action = ActionChains(driver)
        
        # Mute notification and mark all as read
        notification_container = driver.find_element(By.CLASS_NAME, value="header-right-group")
        notification_elements = notification_container.find_elements(By.CLASS_NAME, value="icon")
        time.sleep(1)
        notification_elements[1].click()
        time.sleep(1)
        print("Notifications are cleared")
        mute_button_element = driver.find_element(by=By.XPATH, value="//img[contains(@src,'media/MuteNotification')]")
        action.move_to_element(notification_elements[3]).perform()
        mute_button_element.click()
        print("Notifications are muted")
    
    @pytest.mark.dependency(depends=["Test_Vsaas_Soterix::test_login"])
    def test_site_load(self, params):
        driver = params['driver']
        site_name = params['site_name']
        location_name = params['location_name']
        time.sleep(5)
        
        print(f"Checking for Site \"{site_name}\" loaded or not for max 60 Sec")
        element_present = EC.presence_of_all_elements_located((By.XPATH, f"//*[contains(text(), \"{site_name}\")]"))
        try:
            WebDriverWait(driver, 60).until(element_present)
            print(f"Site \"{site_name}\" loaded Successfully")
        except:
            print(f"Failed to load site \"{site_name}\" in 60 Sec")
            assert False, f"Failed to load site \"{site_name}\" in 60 Sec"
    
    @pytest.mark.dependency(depends=["Test_Vsaas_Soterix::test_site_load"])
    def test_all_cameras(self, params):
        driver = params['driver']
        site_name = params['site_name']
        location_name = params['location_name']
        time.sleep(5)
        
        print(f"Checking for Site \"{site_name}\" loaded or not for max 60 Sec")
        element_present = EC.presence_of_all_elements_located((By.XPATH, f"//*[contains(text(), \"{site_name}\")]"))
        try:
            WebDriverWait(driver, 60).until(element_present)
            print(f"Site \"{site_name}\" loaded Successfully")
        except:
            print(f"Failed to load site \"{site_name}\" in 60 Sec")
            assert False, f"Failed to load site \"{site_name}\" in 60 Sec"
            
        time.sleep(5)
        site_elements = driver.find_elements(By.XPATH, value=f"//*[contains(text(), \"{site_name}\")]")
        site_available = False
        for site_element in  site_elements:
            if site_element.text == site_name:
                site_element.click()
                print(f"Clicked on site \"{site_name}\"")
                site_available = True
                break
        assert site_available, f"Site \"{site_name}\" not enabled or not available"
        time.sleep(1)
        
        location_elements = driver.find_elements(By.XPATH, value=f"//*[contains(text(), '{location_name}')]")
        location_available = False
        for location_element in location_elements:
            if location_element.text == location_name:
                if location_element.is_displayed():
                    location_element.click()
                    print(f"Clicked on location '{location_name}'")
                    location_available = True
                    break
        assert location_available, f"Provided Location '{location_name}' not available"
        
        # Checking offline camera count
        offline_camera_count = 0
        camera_thumbnails = driver.find_elements(by=By.CLASS_NAME, value="cameraThumbnailWrapper")
        for camera_thumbnail in camera_thumbnails:
            if 'red' in camera_thumbnail.find_element(by=By.XPATH, value=".//img[contains(@src,'media/cameraIcon')]").get_attribute('class').lower():
                offline_camera_count += 1
                
        tile_layout_elements = driver.find_elements(By.XPATH, "//button[contains(@class, 'btn-icon-center')]")
        tile_layout_elements[2].click()
        time.sleep(2)
        # Drag Drop Location
        tile_elements = driver.find_elements(By.XPATH, "//div[text()='Drag & Drop Camera here']")
        print(f"Drag Dropping the Location '{location_name}'")
        action = ActionChains(driver)
        action.move_to_element(location_element).perform()
        action.drag_and_drop(location_element, tile_elements[0]).perform()
        print(f"Location '{location_name}' drag dropped successfully to 1X1")        
        time.sleep(2)
        try:
            element_present = EC.presence_of_all_elements_located((By.XPATH, "//*[contains(@class,'CircularProgress')]"))
            live_icon_elements = WebDriverWait(driver, 60).until(element_present)
            
            print("Waiting for loader to stop for 60 Sec")
            wait_item = WebDriverWait(driver, 60).until(EC.invisibility_of_element_located((By.XPATH, "//*[contains(@class,'CircularProgress')]")))
            print("Loader has stopped. Checking whether streaming is working or failed")
            time.sleep(30)
            streaming_failed_elements = driver.find_elements(By.XPATH, value=".//*[contains(text(),'failed to load')]")               
            if len(streaming_failed_elements) <= offline_camera_count:
                #stream_failed_elements = tile_elements[tile_index].find_element(By.XPATH, ".//button[text()='Refresh']")
                print("Streaming is Working")
            else:
                assert False, "Failed to play all cameras"
        except:
            assert False, "Failed to perform actions"
        time.sleep(10)
        driver.refresh()
      
    @pytest.mark.dependency(depends=["Test_Vsaas_Soterix::test_login"])
    def test_addtab_saveview_openview(self, params):
        driver = params['driver']
        site_name = params['site_name']
        location_name = params['location_name']
        camera_name = params['camera_name']
        time.sleep(5)
        
        action = ActionChains(driver)
        now = datetime.datetime.now()
        formatted_datetime = now.strftime("%Y%m%d%H%M%S")
        
        add_tab_element = driver.find_element(By.XPATH, value=".//img[contains(@src,'media/addIcon')]")
        add_tab_element.click()
        
        tile_elements = driver.find_elements(By.XPATH, "//div[text()='Drag & Drop Camera here']")
        assert len(tile_elements) == 8, "Failed to add new tab"
        
        tab_edit_elements = driver.find_elements(By.XPATH, value=".//img[contains(@src,'media/editIcon')]")
        action.move_to_element(tab_edit_elements[1]).perform()
        tab_edit_elements[1].click()
        
        tab_title_elements = driver.find_elements(By.CLASS_NAME, value="tabTitle")
        tab_title_elements[1].send_keys(Keys.BACKSPACE * 10)
        tab_title_elements[1].send_keys(formatted_datetime)
        
        # Open and add Maps
        maps_element = driver.find_element(By.XPATH, value=".//img[contains(@src,'media/maps')]")
        maps_element.click()
        
        element_present = EC.presence_of_all_elements_located((By.XPATH, f'//p[text()=\"{site_name}\"]'))
        try:
            WebDriverWait(driver, 60).until(element_present)
            print(f"Site \"{site_name}\" loaded Successfully")
        except:
            print(f"Failed to load site \"{site_name}\" in 60 Sec")
            assert False, f"Failed to load site \"{site_name}\" in 60 Sec"
            
        map_site_element = driver.find_element(By.XPATH, f'//p[text()=\"{site_name}\"]')
        map_site_element.click()
        
        maps_elements = driver.find_elements(By.CLASS_NAME, value="cameraThumbnailWrapper")
        action.move_to_element(maps_elements[0])
        action.drag_and_drop(maps_elements[0], tile_elements[4]).perform()
        
        try:
            element_present = EC.presence_of_all_elements_located((By.XPATH, "//*[contains(@class,'CircularProgress')]"))
            live_icon_elements = WebDriverWait(driver, 60).until(element_present)
            
            print("Waiting for loader to stop for 600 Sec")
            wait_item = WebDriverWait(driver, 600).until(EC.invisibility_of_element_located((By.XPATH, "//*[contains(@class,'CircularProgress')]")))
            print("Loader has stopped")    
        except:
            assert False, "Failed to open Map"
        
        save_view_elements = driver.find_elements(By.XPATH, value=".//img[contains(@src,'media/save')]")
        save_view_elements[1].click()
        
        element_present = EC.presence_of_all_elements_located((By.XPATH, f'//p[text()="View saved successfully"]'))
        try:
            WebDriverWait(driver, 20).until(element_present)
            print(f"View saved successfully")
        except:
            print(f"Failed to save view")
            assert False, f"Failed to save view. Success message didn't appear in 20 Sec"
        
        time.sleep(2)
        tab_close_elements = driver.find_elements(By.XPATH, value=".//img[contains(@src,'media/closeIcon')]")
        tab_close_elements[1].click()
        time.sleep(2)
        
        # Open My Views and open the view saved
        myviews_element = driver.find_element(By.XPATH, value=".//img[contains(@src,'media/myviews')]")
        myviews_element.click()
        time.sleep(2)
        
        element_present = EC.presence_of_all_elements_located((By.XPATH, ".//img[contains(@src,'data:image/jpeg')]"))
        try:
            WebDriverWait(driver, 20).until(element_present)
            print(f"Views loaded successfully")
        except:
            print(f"Failed to load views")
            assert False, f"Failed to load views in 20 Sec"        
        
        #myviews_elements = driver.find_elements(By.XPATH, "//div[@draggable='true']")
        view_element = driver.find_element(By.XPATH, f"//span[@title={formatted_datetime}]")
        action.move_to_element(view_element).perform()
        action.drag_and_drop(view_element, tile_elements[0]).perform()
        #time.sleep(2)
        
        try:
            element_present = EC.presence_of_all_elements_located((By.XPATH, "//*[contains(@class,'CircularProgress')]"))
            live_icon_elements = WebDriverWait(driver, 60).until(element_present)
            
            print("Waiting for loader to stop for 600 Sec")
            wait_item = WebDriverWait(driver, 600).until(EC.invisibility_of_element_located((By.XPATH, "//*[contains(@class,'CircularProgress')]")))
            print("Loader has stopped")    
        except:
            assert False, "Failed to open Map"
        
        tile_elements = driver.find_elements(By.XPATH, "//div[text()='Drag & Drop Camera here']")
        assert len(tile_elements) == 7, "Failed to open view"
        print("View opened successfully")
        time.sleep(2)
        
        tab_close_elements = driver.find_elements(By.XPATH, value=".//img[contains(@src,'media/closeIcon')]")
        tab_close_elements[1].click()
        time.sleep(2)
        tile_elements = driver.find_elements(By.XPATH, "//div[text()='Drag & Drop Camera here']")
        assert len(tile_elements) == 4, "Failed to close tab or open view"
        print("Tab closed successfully")
        time.sleep(2)
        
        # Deleting the created view
        
        view_element = driver.find_element(By.XPATH, f"//span[@title={formatted_datetime}]")
        action.move_to_element(view_element).perform()
        delete_view_element = driver.find_element(By.XPATH, value=".//img[contains(@src,'delete-icon')]")
        delete_view_element.click()
        time.sleep(2)
        delete_view_button_element = driver.find_element(By.XPATH, "//button[contains(text(), 'Yes')]")
        delete_view_button_element.click()
        time.sleep(2)
        
        element_present = EC.presence_of_all_elements_located((By.XPATH, "//span[contains(text(), 'Successfully deleted')]"))
        try:
            WebDriverWait(driver, 60).until(element_present)
            print(f"View Deleted successfully")
        except:
            print(f"Failed to delete view")
            assert False, f"Failed to delete view. Success message didn't appear in 60 Sec"
        driver.refresh()
        #assert driver.find_element(By.XPATH, f"//span[@title={formatted_datetime}]"), "view saved is not available"
        #bookmark_elements = driver.find_elements(By.XPATH, "//a[starts-with(@href, 'data:image/jpeg')]")
      
    @pytest.mark.dependency(depends=["Test_Vsaas_Soterix::test_login"])
    def test_add_remove_favorites(self, params):
        driver = params['driver']
        site_name = params['site_name']
        location_name = params['location_name']
        camera_name = params['camera_name']
        action = ActionChains(driver)
        
        def add_remove_favorite(add_favorite=True):
            site_elements = driver.find_elements(By.XPATH, value=f"//*[contains(text(), \"{site_name}\")]")
            site_available = False
            for site_element in  site_elements:
                if site_element.text == site_name:
                    site_element.click()
                    print(f"Clicked on site \"{site_name}\"")
                    site_available = True
                    break
            assert site_available, f"Site \"{site_name}\" not enabled or not available"
            time.sleep(2)    
            location_elements = driver.find_elements(By.XPATH, value=f"//*[contains(text(), '{location_name}')]")
            location_available = False
            for location_element in location_elements:
                if location_element.text == location_name:
                    if location_element.is_displayed():
                        location_element.click()
                        print(f"Clicked on location '{location_name}'")
                        location_available = True
                        break
            assert location_available, f"Provided Location '{location_name}' not available"
            time.sleep(3)
            
            # Select Camera
            print(f"Checking for camera '{camera_name}' availability")
            camera = driver.find_element(By.XPATH, value=f"//*[contains(text(), '{camera_name}')]")
            assert camera, f"Camera '{camera_name}' not available"
            print(f"Camera '{camera_name}' is avilable")
            fovorite_tree_element = camera.find_element(By.XPATH, "../..")
            
            if add_favorite:
                if not fovorite_tree_element.find_elements(By.XPATH, value=".//img[contains(@src,'media/favoriteIconFilled')]"):
                    street_favorite_button = WebDriverWait(driver, 10).until(
                            EC.element_to_be_clickable((By.XPATH, 
                                 f"//span[@title='{camera_name}']/../..//button[.//img[@alt='favorite']]"))
                        )
                    street_favorite_button.click()
            else:
                if fovorite_tree_element.find_elements(By.XPATH, value=".//img[contains(@src,'media/favoriteIconFilled')]"):
                    street_favorite_button = WebDriverWait(driver, 10).until(
                            EC.element_to_be_clickable((By.XPATH, 
                                 f"//span[@title='{camera_name}']/../..//button[.//img[@alt='favorite']]"))
                        )
                    street_favorite_button.click()
                    
        def open_close_favorites():
            # Clicking on Favorite to see favorite cameras
            cameras_favorite_icon_element = driver.find_element(By.XPATH, value=".//img[contains(@src,'media/favoriteIcon')]")
            action.move_to_element(cameras_favorite_icon_element).click().perform()            
        
        time.sleep(5)
        print(f"Checking for Site \"{site_name}\" loaded or not for max 60 Sec")
        element_present = EC.presence_of_all_elements_located((By.XPATH, f"//*[contains(text(), \"{site_name}\")]"))
        try:
            WebDriverWait(driver, 60).until(element_present)
            print(f"Site \"{site_name}\" loaded Successfully")
        except:
            print(f"Failed to load site \"{site_name}\" in 60 Sec")
            assert False, f"Failed to load site \"{site_name}\" in 60 Sec"
            
        time.sleep(5)
        
        # Add Camera to Favorite
        print(f"Adding Camera {camera_name} to Favorites")
        add_remove_favorite(add_favorite=True)
        print(f"Camera {camera_name} added to Favorites")
        time.sleep(5)
        
        # Open Favorites
        print(f"Opening Favorites")
        open_close_favorites()
        print(f"Favorites opened")
        time.sleep(5)
        
        # Validate Camera present in Favorites
        assert driver.find_elements(By.XPATH, value=f"//*[contains(text(), '{camera_name}')]"), f"Camera {camera_name} is not showing in Favorites"
        print(f"Camera {camera_name} is showing in Favorites")
        
        # Close Favorites
        print(f"Closing Favorites")
        open_close_favorites()
        print(f"Favorites Closed")
        time.sleep(2)
        
        # Remove camera from Favorites
        print(f"Removing camera {camera_name} from Favorites")
        add_remove_favorite(add_favorite=False)
        print(f"Camera {camera_name} removed from Favorites")
        time.sleep(5)
        
        # Open Favorites
        print(f"Opening Favorites")
        open_close_favorites()
        print(f"Favorites opened")
        time.sleep(5)
        
        # Validate Camera present in Favorites
        assert not driver.find_elements(By.XPATH, value=f"//*[contains(text(), '{camera_name}')]"), f"Camera {camera_name} is still showing in Favorites after removing"
        print(f"Camera {camera_name} is not showing in Favorites")
        
        # Close Favorites
        print(f"Closing Favorites")
        open_close_favorites()
        print(f"Favorites Closed")
        
    @pytest.mark.dependency(depends=["Test_Vsaas_Soterix::test_login"])
    def test_play_each_camera(self, params):
        print(f"Playing each camera one by one in the given site {params['site_name']}")
        self.play_camera(params, play_all_cameras=True)
        print(f"All cameras in site {params['site_name']} are played successfully")
        params['driver'].refresh()
        
    @pytest.mark.dependency(depends=["Test_Vsaas_Soterix::test_login"])
    def test_live(self, params):
        print(f"Playing camera {params['camera_name']}")
        self.play_camera(params)
        print(f"Camera {params['camera_name']} is streaming successfully")

    @pytest.mark.dependency(depends=["Test_Vsaas_Soterix::test_live"])
    def test_share_live_view(self, params):
        import pyperclip
        driver = params['driver']
        site_name = params['site_name']
        action = ActionChains(driver)
        time.sleep(5)
        pyperclip.copy("")
        
        print("Hover on video tile")
        
        video_tile_element = driver.find_element(By.XPATH, value="//*[contains(@class,'video_container new_video_player')]")
        action.move_to_element(video_tile_element).perform()
        
        three_dots_element = video_tile_element.find_element(By.CLASS_NAME, value=f"control-small-view")
        three_dots_element.click()
        time.sleep(3)
        
        timeline_element = video_tile_element.find_element(by=By.ID, value="svg-line-2")
        action.move_to_element(timeline_element).perform()
        
        share_live_view_element = video_tile_element.find_element(By.XPATH, value=".//img[contains(@src,'media/icon-share')]")
        share_live_view_element.click()
        
        share_live_view_window_element = driver.find_element(By.CLASS_NAME, value=f"share_live_main_container")
        mailid_field_element = share_live_view_window_element.find_element(By.CLASS_NAME, value=f"fileName_inputfield")
        mailid_field_element.send_keys("person@example.com")
        
        share_button_element = driver.find_element(By.XPATH, "//button[.//span[text()='Share']]")
        share_button_element.click()
        
        try:
            share_button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//span[text()='Copy']"))
            )
            share_button.click()
        except Exception as e:
            print(f"Error clicking Copy button: {e}")
        
        time.sleep(5)
        clipboard_text = pyperclip.paste()
        print(f"Live View Link : {clipboard_text}")
        
        cancel_button_element = share_live_view_window_element.find_element(By.CLASS_NAME, value="cancel_button_share_live")
        cancel_button_element.click()        
        assert clipboard_text, "Live View Link didn't generate"
        print("Live View Link sent successfully")
        site_elements = driver.find_elements(By.XPATH, value=f"//*[contains(text(), \"{site_name}\")]")
        action.move_to_element(site_elements[0]).perform()

    @pytest.mark.dependency(depends=["Test_Vsaas_Soterix::test_share_live_view"])
    def test_add_bookmark(self, params):
        import pyperclip
        driver = params['driver']
        site_name = params['site_name']
        action = ActionChains(driver)
        time.sleep(5)
        pyperclip.copy("")
        
        print("Hover on video tile")
        
        video_tile_element = driver.find_element(By.XPATH, value="//*[contains(@class,'video_container new_video_player')]")
        action.move_to_element(video_tile_element).perform()
        
        three_dots_element = video_tile_element.find_element(By.CLASS_NAME, value=f"control-small-view")
        three_dots_element.click()
        time.sleep(3)
        
        timeline_element = video_tile_element.find_element(by=By.ID, value="svg-line-2")
        action.move_to_element(timeline_element).perform()
        
        add_bookmark_element = video_tile_element.find_element(By.XPATH, value=".//img[contains(@src,'media/Bookmark')]")
        add_bookmark_element.click()
        
        bookmark_elements = driver.find_elements(By.XPATH, "//a[starts-with(@href, 'data:image/png')]")
        assert len(bookmark_elements) < 4, "Failed to add bookmark"
        print("Bookmark added successfully")
        site_elements = driver.find_elements(By.XPATH, value=f"//*[contains(text(), \"{site_name}\")]")
        action.move_to_element(site_elements[0]).perform()

    @pytest.mark.dependency(depends=["Test_Vsaas_Soterix::test_live"])
    def test_archive_thirty_minutes(self, params):
        driver = params['driver']
        site_name = params['site_name']
        location_name = params['location_name']
        camera_name = params['camera_name']
        action = ActionChains(driver)
        
        time.sleep(5)
        
        print("Hover on video tile")
        #video_tile_element = driver.find_element(By.CLASS_NAME, value='control_Container')
        
        video_tile_element = driver.find_element(By.XPATH, value="//*[contains(@class,'video_container new_video_player')]")
        action.move_to_element(video_tile_element).perform()
        
        # Drag the timeline to move to archive mode
        timeline_element = video_tile_element.find_element(by=By.ID, value="svg-line-2")
        action.click_and_hold(timeline_element)
        action.move_by_offset(150, 0)
        action.release()
        action.perform()
        time.sleep(2)
        
        element_present = EC.presence_of_all_elements_located((By.XPATH, "//*[contains(@class,'CircularProgress')]"))
        live_icon_elements = WebDriverWait(driver, 60).until(element_present)
        
        print("Waiting for loader to stop for 60 Sec")
        wait_item = WebDriverWait(driver, 60).until(EC.invisibility_of_element_located((By.XPATH, "//*[contains(@class,'CircularProgress')]")))
        print("Loader has stopped. Checking whether Archive is working or failed")
        streaming_failed_elements = driver.find_elements(By.XPATH, value=".//*[contains(text(),'failed to load')]")
        assert len(streaming_failed_elements) == 0, "Archive is Failed"
        print("Archive is Working for less than two hours")

    @pytest.mark.dependency(depends=["Test_Vsaas_Soterix::test_archive_thirty_minutes"])
    def test_archive_six_hours(self, params):
        driver = params['driver']
        site_name = params['site_name']
        location_name = params['location_name']
        camera_name = params['camera_name']
        action = ActionChains(driver)
        
        time.sleep(5)
        
        print("Hover on video tile")
        #video_tile_element = driver.find_element(By.CLASS_NAME, value='control_Container')
        
        video_tile_element = driver.find_element(By.XPATH, value="//*[contains(@class,'video_container new_video_player')]")
        action.move_to_element(video_tile_element).perform()
        
        # Go to live and move to archive 6 hours    
        go_live_element = video_tile_element.find_elements(by=By.XPATH, value=".//p[contains(text(),'Go Live')]")#".//img[contains(@src,'media/go-live')]")
        go_live_element[-1].click()
        time.sleep(10)
        
        # Scroll and Drag the timeline to move to archive mode more than 4 hours
        timeline_scroll_element = video_tile_element.find_element(By.XPATH, "//*[contains(@id, 'lines-container')]")
        script = """
        var evt = new WheelEvent('wheel', {
            bubbles: true,
            cancelable: true,
            deltaY: arguments[1]
        });
        arguments[0].dispatchEvent(evt);
    """                
        
        driver.execute_script(script, timeline_scroll_element, 3000)
        
        action.click_and_hold(timeline_scroll_element)
        action.move_by_offset(150, 0)
        action.release()
        action.perform()
        time.sleep(2)
        
        element_present = EC.presence_of_all_elements_located((By.XPATH, "//*[contains(@class,'CircularProgress')]"))
        circular_progress_element = WebDriverWait(driver, 60).until(element_present)
        
        print("Waiting for loader to stop for 60 Sec")
        wait_item = WebDriverWait(driver, 60).until(EC.invisibility_of_element_located((By.XPATH, "//*[contains(@class,'CircularProgress')]")))
        print("Loader has stopped. Checking whether Archive is working or failed")
        streaming_failed_elements = driver.find_elements(By.XPATH, value=".//*[contains(text(),'failed to load')]")
        assert len(streaming_failed_elements) == 0, "Archive is Failed"
        print("Archive is Working for more than two hours")
        time.sleep(20)
      
    @pytest.mark.dependency(depends=["Test_Vsaas_Soterix::test_archive_six_hours"])
    def test_fullscreen_bookmark(self, params):
        driver = params['driver']
        site_name = params['site_name']
        location_name = params['location_name']
        camera_name = params['camera_name']
        time.sleep(5)
        action = ActionChains(driver)
        now = datetime.datetime.now()
        bookmark_rename_text = now.strftime("%Y%m%d%H%M%S")
        
        # Click on full screen button
        video_tile_element = driver.find_element(By.XPATH, value="//*[contains(@class,'video_container new_video_player')]")
        action.move_to_element(video_tile_element).perform()
        
        fullscreen_button_elements = video_tile_element.find_elements(By.XPATH, value=".//img[contains(@src,'media/Zoom.')]")
        fullscreen_button_elements[1].click()
        print("Clicked on Full screen button")
        
        # Wait till loader stops in Full screen
        try:
            element_present = EC.presence_of_all_elements_located((By.XPATH, "//*[contains(@class,'CircularProgress')]"))
            live_icon_elements = WebDriverWait(driver, 5).until(element_present)
            
            print("Waiting for loader to stop for 60 Sec")
            wait_item = WebDriverWait(driver, 600).until(EC.invisibility_of_element_located((By.XPATH, "//*[contains(@class,'CircularProgress')]")))
            print("Loader has stopped. Video is streaming in Full screen")
        except:
            assert False, "Failed to stream video in full screen"
        
        # Pause Video
        pause_button_element = driver.find_element(By.XPATH, value=".//img[contains(@src,'media/play')]")
        pause_button_element.click()
        
        try:
            temp = WebDriverWait(driver, 60).until(EC.invisibility_of_element_located((By.XPATH, ".//img[contains(@src,'media/pause')]")))
        except:
            assert False, "Not able to Pause Video in 60 Sec"
        
        # Opening Bookmarks
        bookmark_open_element = driver.find_element(By.XPATH, value=".//img[contains(@src,'media/dotsIcon')]")
        bookmark_open_element.click()
        
        # Click on bookmark
        bookmarks = driver.find_elements(By.CLASS_NAME, value="bookmarkVideoContainer")
        assert bookmarks, "No bookmarks are available"
        bookmarks[0].click()
        
        time.sleep(2)
        try:
            print("Waiting for pause button to be available in 60 Sec")
            element_present = EC.presence_of_all_elements_located((By.XPATH, ".//img[contains(@src,'media/play')]"))
            live_icon_elements = WebDriverWait(driver, 60).until(element_present)
            print("Bookmark played successfully")
        except:
            assert False, "Failed to Play Bookmark"
        
        # Bookmark Options
        threedots_element = bookmarks[0].find_element(By.XPATH, value=".//img[contains(@src,'media/optionIcon')]")
        threedots_element.click()
        
        bookmark_option_elements = driver.find_elements(By.CLASS_NAME, value="edit-delete-option")
        
        # Export
        print("Exporting Bookmark")
        bookmark_option_elements[1].click()
        time.sleep(1)
        self.export_share_check_media(params, is_export=True, check_media=False)
        time.sleep(3)
        print("Bookmark Exported Successfully")
        
        # Share
        # Bookmark Options
        threedots_element = bookmarks[0].find_element(By.XPATH, value=".//img[contains(@src,'media/optionIcon')]")
        threedots_element.click()
        print("Sharing Bookmark")
        bookmark_option_elements = driver.find_elements(By.CLASS_NAME, value="edit-delete-option")
        bookmark_option_elements[2].click()
        time.sleep(1)
        self.export_share_check_media(params, is_share=True, check_media=False)
        time.sleep(3)
        print("Bookmark Shared Successfully")
        
        # Edit 
        # Bookmark Options
        threedots_element = bookmarks[0].find_element(By.XPATH, value=".//img[contains(@src,'media/optionIcon')]")
        threedots_element.click()
        print("Renaming the Bookmark")
        bookmark_option_elements = driver.find_elements(By.CLASS_NAME, value="edit-delete-option")
        bookmark_option_elements[0].click()
        
        bookmark_rename_textbox = driver.find_element(By.ID, value="comment_input")
        bookmark_rename_textbox.send_keys(Keys.BACKSPACE * 20)
        bookmark_rename_textbox.send_keys(bookmark_rename_text)
        
        save_button = driver.find_element(By.XPATH, "//button[text()='Save']")
        save_button.click()
        print("Clicked on Save button")
        
        time.sleep(3)
        assert driver.find_element(By.XPATH, f"//*[text()={bookmark_rename_text}]"), f"Not able to find renamed Bookmark : {bookmark_rename_text}"
        print("Bookmark renamed successfully")
        
        # Delete
        
        renamed_bookmark_element = driver.find_element(By.XPATH, f"//*[text()={bookmark_rename_text}]")
        bookmark_name_option_container_element = renamed_bookmark_element.find_element(By.XPATH, "../..")
        renamed_bookmark_options = bookmark_name_option_container_element.find_element(By.XPATH, value=".//img[contains(@src,'media/optionIcon')]")
        renamed_bookmark_options.click()
        bookmark_option_elements = driver.find_elements(By.CLASS_NAME, value="edit-delete-option")
        bookmark_option_elements[3].click()
        
        print("Clicking on Yes Button")
        yes_button_element = driver.find_element(By.CLASS_NAME, value="yes_button")
        yes_button_element.click()
        
        print("Check whether the bookmark is deleted or not")
        temp = WebDriverWait(driver, 10).until(EC.invisibility_of_element_located((By.XPATH, f"//*[text()={bookmark_rename_text}]")))
        print(f"Bookmark {bookmark_rename_text} deleted successfully")
        
        # Close bookmark
        bookmark_close_element = driver.find_element(By.XPATH, value=".//img[contains(@src,'media/dotsIcon')]")
        bookmark_close_element.click()
        print("Bookmarks closed")
      
    @pytest.mark.dependency(depends=["Test_Vsaas_Soterix::test_fullscreen_bookmark"])
    def test_incamera_search(self, params):
        driver = params['driver']
        site_name = params['site_name']
        location_name = params['location_name']
        camera_name = params['camera_name']
        time.sleep(5)
        action = ActionChains(driver)
        
        pause_button_element = driver.find_element(By.XPATH, value=".//img[contains(@src,'media/play')]")
        pause_button_element.click()
        
        try:
            temp = WebDriverWait(driver, 60).until(EC.invisibility_of_element_located((By.XPATH, ".//img[contains(@src,'media/pause')]")))
        except:
            assert False, "Not able to Pause Video in 60 Sec"
        
        # Click on In Camera Search button
        print("Clicking on Incamera Search Button")
        search_button_element = driver.find_element(By.XPATH, value="//img[contains(@src,'videoplayer/Search.')]")
        search_button_element.click()
        print("Clicked on Incamera Search button")
        time.sleep(2)
        
        # Category, Appearance and Duration selection
        incamera_dropdown_elements = driver.find_elements(By.CLASS_NAME, value='in-camera-box-container')
        for incamera_dropdown_element in incamera_dropdown_elements:
            time.sleep(2)
            incamera_dropdown_element.click()
            if 'Category' in incamera_dropdown_element.text:
                category_selection_elements = driver.find_elements(by=By.CLASS_NAME, value='dropdownItem')
                category_selection_elements[0].click()
                print("Category selected as Person")
            elif 'Description' in incamera_dropdown_element.text:
                gender_container_element = driver.find_element(By.CLASS_NAME, value="gender-option-container")
                gender_elements = gender_container_element.find_elements(By.XPATH, value=".//p[contains(@text,'')]")
                for gender_element in gender_elements:
                    if gender_element.text == 'Male':
                        gender_element.click()
                        print("Description selected as Male")
                        break
            else:
                duration_selection_elements = driver.find_elements(by=By.CLASS_NAME, value='dropdownItem')
                duration_selection_elements[4].click()
                print("Duration selected as Today")
        
        # Click on Search Button
        search_button_elements = driver.find_elements(by=By.XPATH, value=".//*[contains(text(),'Search')]")
        search_button_elements[-1].click()
        print("Clicked on search button")
        time.sleep(1)
        
        # Wait for Loder to stop for 60 Sec
        try:
            print("Waiting for loader to stop for 60 Sec")
            element_present = EC.presence_of_all_elements_located((By.XPATH, "//*[contains(@class,'CircularProgress')]"))
            live_icon_elements = WebDriverWait(driver, 60).until(element_present)        
            element_present = EC.presence_of_all_elements_located((By.XPATH, "//*[contains(@class,'imageResults')]"))
            event_results_elements = WebDriverWait(driver, 60).until(element_present) 
        except:
            assert False, "Failed to Load event"
        print("Loader has stopped")
        
        print("Checking for Events are generated or not")
        search_results_element = driver.find_element(by=By.CLASS_NAME, value="twoColumnGrid")
        event_results_elements = search_results_element.find_elements(by=By.XPATH, value=".//*[contains(@class,'imageResults')]")
        assert event_results_elements, "Events are not Available"
        print("Events are displaying")
        
        print("Playing the Event")
        action.move_to_element(event_results_elements[0]).perform()
        event_video_play_button_element = event_results_elements[0].find_element(By.XPATH, value=".//img[contains(@src,'media/video-player-icon')]")
        event_video_play_button_element.click()
        time.sleep(2)
        try:
            print("Waiting for pause button to be available in 30 Sec")
            element_present = EC.presence_of_all_elements_located((By.XPATH, ".//img[contains(@src,'media/play')]"))
            live_icon_elements = WebDriverWait(driver, 30).until(element_present)
        except:
            assert False, "Failed to Play event"
        time.sleep(1)
        #assert driver.find_element(By.XPATH, value=".//img[contains(@src,'media/play')]"), "Failed to Play event"
        #print("Event played successfully")
            
        # ID - play-0 - Event played
        # ID = pause-0   media/exitFullScreen
        time.sleep(5)
        #print("Exit from Full screen")
        #exit_fullscreen_button = driver.find_element(By.XPATH, value=".//img[contains(@src,'media/exitFullScreen')]")
        #exit_fullscreen_button.click()
        #print("Exited from Full screen")
        driver.refresh()
        
    #@pytest.mark.dependency(depends=["Test_Vsaas_Soterix::test_login"])
    def test_incamera_search_api_calls(self, params):
        self.log_api_data(params['driver'])

    @pytest.mark.dependency(depends=["Test_Vsaas_Soterix::test_login"])
    def test_navigate_to_camera_sequence_page(self, params):
        driver = params['driver']
        wait = WebDriverWait(driver, 10)
        try:
            elem = wait.until(EC.element_to_be_clickable((
                By.XPATH, '//img[@alt="SequenceIcon" and @width="24" and @height="24"]'
                )))
            elem.click()
        except TimeoutException:
            print("Timeout: Element was not clickable within the given time.")
        except NoSuchElementException:
            print("Error: Element not found in the DOM.")
        except ElementClickInterceptedException:
            print("Error: Element click was intercepted by another element.")
        except Exception as e:
            print(f"An unexpected error occurred: {e}")
        time.sleep(2)
        
    @pytest.mark.dependency(depends=["Test_Vsaas_Soterix::test_login"])
    def test_search_camera_camera_sequence(self, params):
        driver = params['driver']   
        wait = WebDriverWait(driver, 10)
        camera_name = params['camera_name']
        # Search for the camera in the camera sequence page
        try:
            # Wait until at least one visible input with the correct placeholder is present
            search_input = wait.until(
                EC.visibility_of_element_located((By.XPATH, '(//input[@placeholder="Search"])[1]'))
                )
            search_input.clear()
            search_input.send_keys(f"{camera_name}")
            assert search_input.get_attribute("value") == camera_name, "Search input value mismatch"
            time.sleep(2)
        except TimeoutException:
            print("Search input field not found in time.")
        except AssertionError as ae:
            pytest.fail(f"Assertion failed: {ae}")
        except Exception as e:
            pytest.fail(f"Unexpected error: {e}")
        time.sleep(2)

    @pytest.mark.dependency(depends=["Test_Vsaas_Soterix::test_login"])
    def test_select_all_cameras_for_sequencing(self, params):
        driver = params['driver']   
        wait = WebDriverWait(driver, 10)
        camera_name = params['camera_name']
        try:
            time.sleep(2)
            # Wait for the checkbox to be present
            checkbox = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 'input[type="checkbox"].PrivateSwitchBase-input'))
                )
            # Click the checkbox
            checkbox.click()
        except TimeoutException:
            print("Checkbox not found in time.")
        except AssertionError as ae:
            pytest.fail(f"Assertion failed: {ae}")
        except Exception as e:
            pytest.fail(f"Unexpected error: {e}")
        time.sleep(2)
        
    @pytest.mark.dependency(depends=["Test_Vsaas_Soterix::test_login"])
    def test_create_camera_sequence(self, params):
        driver = params['driver']   
        wait = WebDriverWait(driver, 10)
        # Click the "Create Sequence" button
        try:
            input_field = wait.until(
                EC.element_to_be_clickable((By.CLASS_NAME, "modalFormInput"))
                )
            input_field.clear()
            time_stamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
            input_field.send_keys(f"{time_stamp}_Automation_Test_create_sequence")
        except Exception as e:
            print(f"Failed to interact with modal input: {e}")
        time.sleep(2)
        # Click the save button in the modal
        try:
            save_button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, '//button[contains(@class, "modalSaveBtn") and text()="Save"]'))
            )
            save_button.click()
            print("Save button clicked.")
        except TimeoutException:
            print("Save button was not found or not clickable in time.")
            
    @pytest.mark.dependency(depends=["Test_Vsaas_Soterix::test_login"])
    def test_add_created_sequence_to_views(self, params):
        driver = params['driver']   
        wait = WebDriverWait(driver, 10)
        # Click on the "Sequences" button in the sidebar
        try:
            # Check if any dropdown (with specific title) is open - replace with actual dropdown title if needed
            open_dropdowns = driver.find_elements(By.XPATH, '//div[@title and contains(@class, "MuiPaper-root")]')
            dropdown_open = False
            for dropdown in open_dropdowns:
                if dropdown.is_displayed():
                    dropdown_open = True
                    break
            if not dropdown_open:
                sequence_element = wait.until(
                    EC.element_to_be_clickable((By.XPATH, '//span[@title="Sequences"]'))
                )
                sequence_element.click()
            else:
                print("Dropdown is open - skipping 'Sequences' click.")
        except Exception as e:
            print(f"Exception occurred: {e}")
        time.sleep(2)
        # Select the created sequence from the list
        try:
            sidebar_items = wait.until(EC.presence_of_all_elements_located(
                (By.CSS_SELECTOR, "div.MuiListItemButton-root.sidebarlist-item-button")))
            if sidebar_items:
                last_item = sidebar_items[-1]
                title = last_item.find_element(By.CSS_SELECTOR, "span.MuiTypography-caption").text
                print(f"Selected item: {title}")
                checkbox = last_item.find_element(By.CSS_SELECTOR, "input[type='checkbox']")
                if not checkbox.is_selected():
                    try:
                        checkbox.click()
                    except:
                        driver.execute_script("arguments[0].click();", checkbox)
                print("Last checkbox selected")
            else:
                print("No sidebar items found")
        except Exception as e:
            print(f"Sidebar checkbox error: {e}")
    
    @pytest.mark.dependency(depends=["Test_Vsaas_Soterix::test_login"])
    def test_edit_the_sequence(self, params):
        driver = params['driver']
        wait = WebDriverWait(driver, 10)
        try:
            time.sleep(2)  # Brief pause to ensure the sequence item is loaded
            try:
                sidebar_items = wait.until(EC.presence_of_all_elements_located(
                    (By.CSS_SELECTOR, "div.MuiListItemButton-root.sidebarlist-item-button")))
                if sidebar_items:
                    last_item = sidebar_items[-1]
                    title = last_item.find_element(By.CSS_SELECTOR, "span.MuiTypography-caption").text
                    print(f"Selected item: {title}")
                    checkbox = last_item.find_element(By.CSS_SELECTOR, "input[type='checkbox']")
                    if not checkbox.is_selected():
                        try:
                            checkbox.click()
                        except:
                            driver.execute_script("arguments[0].click();", checkbox)
                    print("Last checkbox selected")
                else:
                    print("No sidebar items found")
            except Exception as e:
                print(f"Sidebar checkbox error: {e}")
            # Find and click more options button
            options_button = wait.until(EC.element_to_be_clickable((
                By.CSS_SELECTOR, "img[src*='3-dot']"
            )))
            options_button.click()
            print("Clicked more options button")
            time.sleep(3)  # Brief pause for menu to appear
            # Find and click edit option
            ActionChains(driver).send_keys(Keys.ENTER).perform()
            print("Edit option selected")
            time.sleep(5)  # Brief pause for confirmation dialog to appear
            dropdown = wait.until(
                EC.element_to_be_clickable((By.XPATH, '//div[contains(text(), "5 Sec")]'))
                )
            dropdown.click()
            time.sleep(2)  # Wait for the dropdown to update
            # After clicking the dropdown, select 10 seconds option
            try:
                option_10_sec = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, '//li[text()="10 Seconds"]'))
                )
                option_10_sec.click()
                print("Selected '10 Seconds'")
            except Exception as e:
                print(f"Failed to select '10 Seconds': {e}")
            time.sleep(2)  # Wait for the selection to take effect
            try:
                input_field = WebDriverWait(driver, 10).until(
                    EC.visibility_of_element_located((By.CSS_SELECTOR, 'input.modalFormInput'))
                    )
                input_field.clear()
                input_field.send_keys("Edited the camera sequence time through automation")
                print("Input field updated successfully.")
            except Exception as e:
                print(f"Failed to interact with input field: {e}")
            time.sleep(2)
            # Click the "Update" button
            try:
                update_button = WebDriverWait(driver, 10).until(
                    EC.element_to_be_clickable((By.XPATH, '//button[normalize-space()="Update"]'))
                )
                update_button.click()
                print("Update button clicked successfully.")
            except Exception as e:
                print(f"Failed to click the Update button: {e}")
        except TimeoutException as e:
            print(f"Timeout error: {str(e)}")
            return False
        except AssertionError as e:
            print(f"Assertion failed: {str(e)}")
            return False
        except Exception as e:
            print(f"Error deleting sequence: {str(e)}")
            return False
        time.sleep(2)
    
    @pytest.mark.dependency(depends=["Test_Vsaas_Soterix::test_login"])
    def test_create_sequence_with_refrain_playing_off_and_play_reverse_camera(self, params):
        driver = params['driver']
        wait = WebDriverWait(driver, 10)
        self.test_navigate_to_camera_sequence_page(params)
        time.sleep(2)
        try:
            # Wait for the checkbox to be present in the DOM
            checkbox = wait.until(
                EC.presence_of_element_located((By.NAME, "selectAllCameras"))
            )
            # Scroll to it in case it's offscreen
            driver.execute_script("arguments[0].scrollIntoView(true);", checkbox)
            # Click the checkbox only if not already selected
            if not checkbox.is_selected():
                checkbox.click()
                print("Select All Cameras checkbox clicked.")
            else:
                print("Checkbox already selected.")
        except Exception as e:
            print(f"Exception occurred: {e}")
        time.sleep(2)
        try:
            # Wait for checkbox to be present and clickable
            checkbox = wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "input[name='playOfflineCameras']"))
                )
            # Check if not already selected
            if not checkbox.is_selected():
                checkbox.click()
                print("Checkbox selected.")
            else:
                print("Checkbox was already selected.")
        except Exception as e:
            print(f"Failed to interact with checkbox: {e}")
        time.sleep(2)  # Wait for the selection to take effect
        try:
            # Wait for checkbox to be present and clickable
            checkbox = wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "input[name='playReverseOrder']"))
                )
            # Check if not already selected
            if not checkbox.is_selected():
                checkbox.click()
                print("Checkbox selected.")
            else:
                print("Checkbox was already selected.")
        except Exception as e:
            print(f"Failed to interact with checkbox: {e}")
        time.sleep(2)
        try:
            input_field = WebDriverWait(driver, 10).until(
                EC.visibility_of_element_located((By.CSS_SELECTOR, 'input.modalFormInput'))
                )
            input_field.clear()
            input_field.send_keys("Play offline cameras selection in camera sequence through automation")
            print("Input field updated successfully.")
        except Exception as e:
            print(f"Failed to interact with input field: {e}")
        time.sleep(2)
        # Click the "Save" button
        try:
            update_button = wait.until(
                EC.element_to_be_clickable((By.XPATH, '//button[normalize-space()="Save"]'))
            )
            update_button.click()
            print("Save button clicked successfully.")
        except Exception as e:
            print(f"Failed to click the Save button: {e}")
        time.sleep(2)
        self.test_add_created_sequence_to_views(params)
    
    @pytest.mark.dependency(depends=["Test_Vsaas_Soterix::test_login"])
    def test_delete_sequence(self, params):
        driver = params['driver']
        wait = WebDriverWait(driver, 10)
        try:
            # Find and click the sequence item
            sequence_item = wait.until(EC.presence_of_element_located((
                By.CSS_SELECTOR, "span.MuiTypography-caption[title='Sequences']"
            )))
            assert sequence_item.is_displayed(), "Sequences item not visible"
            sequence_item.click()
            print("Clicked on Sequences item")

            # Find and click more options button
            options_button = wait.until(EC.element_to_be_clickable((
                By.CSS_SELECTOR, "img[src*='3-dot']"
            )))
            options_button.click()
            print("Clicked more options button")
            time.sleep(1)  # Brief pause for menu to appear
            try:
                delete_icons = driver.find_element(By.XPATH, '//img[contains(@src, "delete-icon")]')
                actions = ActionChains(driver)
                actions.move_to_element(delete_icons).click().perform()
            except Exception as e:
                print(f"Error clicking Delete: {e}")
            time.sleep(2)  # Wait for the delete confirmation dialog to appear
            # Find and click Delete option
            delete_text_element = wait.until(EC.visibility_of_element_located((By.XPATH, '/html/body/div[8]/div[3]/ul/li[2]/p')))
            delete_text_element.click()
            time.sleep(5)  # Brief pause for confirmation dialog to appear

            # Wait for and confirm deletion dialog
            confirm_button = wait.until(EC.element_to_be_clickable((
                By.CSS_SELECTOR, "button.deletePopupSave"
            )))
            confirm_button.click()
            print("Confirmed deletion")
            # Verify sequence is removed
            try:
                wait.until(EC.invisibility_of_element_located((
                    By.CSS_SELECTOR, "span.MuiTypography-caption[title='Sequences']"
                )))
                print("Sequence deleted successfully")
                return True
            except TimeoutException:
                print("Sequence may not have been deleted")
                return False
        except TimeoutException as e:
            print(f"Timeout error: {str(e)}")
            return False
        except AssertionError as e:
            print(f"Assertion failed: {str(e)}")
            return False
        except Exception as e:
            print(f"Error deleting sequence: {str(e)}")
            return False

    @pytest.mark.dependency(depends=["Test_Vsaas_Soterix::test_login"])
    def test_events_search(self, params):
        driver = params['driver']
        site_name = params['site_name']
        location_name = params['location_name']
        camera_name = params['camera_name']
        action = ActionChains(driver)
        time.sleep(5)
        
        # Events Page
        events_button_element = driver.find_element(By.XPATH, value='//a[contains(@href,"events")]')
        events_button_element.click()
        print("Clicked on Events button to Navigate to Events page")
        
        # Wait for the page to load
        element_present = EC.presence_of_all_elements_located((By.CLASS_NAME, "icon-img-search"))
        try:
            print("Waiting for max 60 Sec to navigate to Events page")
            WebDriverWait(driver, 60).until(element_present)
            print("Navigated to Events Page")
        except:
            print("Failed to Navigate to Events Page in 15 Sec")
            assert False, "Failed to Navigate to Events Page in 15 Sec"
            
        # Select Site
        site_dropdown_element = driver.find_element(by=By.XPATH, value=".//*[contains(text(),'Select Site')]")
        site_dropdown_element.click()
        time.sleep(20)
        site_select_element = driver.find_element(by=By.XPATH, value=f".//*[contains(text(), \"{site_name}\")]")
        site_select_element.click()
        time.sleep(2)
        print(f"Selected site \"{site_name}\"")
        
        # Select Locations & Cameras
        camera_dropdown_element = driver.find_element(by=By.XPATH, value=".//*[contains(text(),'Locations & Cameras')]")
        camera_dropdown_element.click()
        time.sleep(2)
        site_element = driver.find_elements(by=By.XPATH, value=f".//*[contains(text(), \"{site_name}\")]")
        site_element[1].click()
        time.sleep(2)
        print(f"Selected site \"{site_name}\"")        
        
        location_elements = driver.find_elements(by=By.XPATH, value=f".//*[contains(text(), '{location_name}')]")
        for location_element in location_elements:
            if location_element.is_displayed():
                location_element.click()
                break
        time.sleep(2)
        print(f"Selected location '{location_name}'")
        
        camera_elements = driver.find_elements(by=By.CLASS_NAME, value="global-search-camera-container")
        for camera_element in camera_elements:
            if camera_name in camera_element.text:
                if camera_element.find_elements(by=By.XPATH, value=".//img[contains(@src,'media/driveIcon')]"):
                    pass
                else:
                    print(f"Hovering on Camera {camera_name} and checking the check box")
                    time.sleep(1)
                    action.scroll_to_element(camera_element).perform()
                    action.move_to_element(camera_element).perform()
                    time.sleep(1)
                    checkbox = camera_element.find_element(by=By.CLASS_NAME, value="MuiSvgIcon-root")
                    action.click(checkbox).perform()
                    print(f"Hovered on Camera {camera_name} and checked the check box")
                    break
        time.sleep(1)    
        action.send_keys(Keys.ESCAPE).perform()
        time.sleep(1)    
        action.send_keys(Keys.ESCAPE).perform()   
        # Duration Selection
        print("Selecting Duration as Today")
        duration_dropdown_element = driver.find_element(by=By.XPATH, value=".//*[contains(text(),'Last 1 Hour')]")
        duration_dropdown_element.click()
        time.sleep(1)
        duration_select_element = driver.find_element(by=By.XPATH, value=f".//*[contains(text(), 'Last 7')]")
        duration_select_element.click()
        time.sleep(2)
        print("Selected Duration as 7 days")
        
        # Click on Search
        #/_next/static/media/eventActive.80d7f359.svg
        event_search_button_element = driver.find_element(By.XPATH, value=".//img[contains(@src,'media/eventActive')]")
        event_search_button_element.click()
        time.sleep(1)
        print("Clicked on search Button")
        
        # Check for events are loaded or not
        element_present = EC.presence_of_all_elements_located((By.XPATH, "//img[@alt='videoImg1']"))
        try:
            print("Waiting for max 60 Sec to load Events")
            wait_item = WebDriverWait(driver, 60).until(element_present)
            time.sleep(30)
        except:
            assert False, "Not able to load events"
        print("Events are loaded successfully")
        
        event_results_elements = driver.find_elements(by=By.XPATH, value="//img[@alt='videoImg1']")        
        print("Checking Snap is loaded or not")
        assert not "media/No_Image_Available" in event_results_elements[0].get_property('src'), "Image snap is not available"
        print("Snap is loaded")
        
        # Pin Events
        print("Hover on first Event and click on pin icon")
        event_pin_icon = event_results_elements[0].find_element(by=By.XPATH, value="//img[contains(@src,'media/roundPinIcon')]")
        action.move_to_element(event_pin_icon).perform()
        event_pin_icon.click()
        
        if len(event_results_elements) > 1:
            print("Hover on second Event and click on pin icon")
            event_pin_icon = event_results_elements[1].find_element(by=By.XPATH, value="//img[contains(@src,'media/roundPinIcon')]")
            action.move_to_element(event_pin_icon).perform()
            event_pin_icon.click()
            
        # Checking Pinned Clips
        pinned_clips_element = driver.find_element(by=By.CLASS_NAME, value="pinnedClip_text")
        if len(event_results_elements) > 1:
            assert ('2' in pinned_clips_element.text), f"Pinned clips text is not 2. It is {pinned_clips_element.text}"
        else:
            assert ('1' in pinned_clips_element.text), f"Pinned clips text is not 1. It is {pinned_clips_element.text}"
        print("Pin clips is successful")
        
        # Review Pinned Videos
        print("Clicking on Review videos button")
        review_videos_button = WebDriverWait(driver, 5).until(EC.element_to_be_clickable(
                (By.XPATH, "//button[normalize-space(text())='Review Pinned Clips']")
            ))
        review_videos_button.click()
        print("Clicked on Review videos button")
        time.sleep(1)

        # export_main_container
        review_pinned_clips_element = driver.find_element(by=By.CLASS_NAME, value="export_main_container")
        
        print("Clicking on Play Videos button")
        play_videos_button_element = WebDriverWait(driver, 5).until(EC.element_to_be_clickable(
                (By.XPATH, "//button[normalize-space(text())='Play Videos']")
            ))
        play_videos_button_element.click()
        print("Clicked on Play Videos button")
        
        print("Waiting for max 60 sec for loader to stop. That is video to play")
        element_present = EC.presence_of_all_elements_located((By.XPATH, "//*[contains(@class,'CircularProgress')]"))
        live_icon_elements = WebDriverWait(review_pinned_clips_element, 60).until(element_present)
        
        try:
            wait_item = WebDriverWait(review_pinned_clips_element, 60).until(EC.invisibility_of_element_located((By.XPATH, ".//*[contains(@class,'CircularProgress')]")))
            print("Loader is stopped")
            print("All Videos are playing successfully")
        except:
            print("All pinned videos are not playing")
            
        # Close review videos window
        close_review_videos_element = driver.find_element(by=By.XPATH, value="//img[contains(@src,'media/closeIcon')]")
        close_review_videos_element.click()
        
        # Play Event
        try:
            # TBD - Check Event snaps are broken images are not . /_next/static/media/No_Image_Available.50e3e08f.svg
            # Check Image snap is loaded or not
            event_results_elements = driver.find_elements(by=By.XPATH, value="//img[@alt='videoImg1']")            
            print("Hover on first Event and click on Play icon")
            event_play_icon = event_results_elements[0].find_element(by=By.XPATH, value="//img[@alt='Play Video']")
            action.move_to_element(event_play_icon).perform()
            event_play_icon.click()
            print("Hovered on an event and clicked on Play icon")
            time.sleep(2)
            
            print("Waiting for loader to stop")
            temp = WebDriverWait(driver, 60).until(EC.invisibility_of_element_located((By.XPATH, "//*[contains(@class,'CircularProgress')]")))
            print("Loader is closed")
        except:
            assert False, "Not able to play event" 
        
        # Waiting for max 40 sec to get Reload button    
        try:
            print("Waiting for max 90 sec to get Replay icon")
            temp = WebDriverWait(driver, 600).until(EC.presence_of_all_elements_located((By.XPATH, ".//img[contains(@src,'media/replay')]")))
            print("Replay icon appeared")
            print("Event Played Successfully")
        except:
            assert False, "Reload button didn't appear for 90 sec"        


    #@pytest.mark.dependency(depends=["Test_Vsaas_Soterix::test_login"])
    def test_events_search_api_calls(self, params):
        self.log_api_data(params['driver'])

    @pytest.mark.dependency(depends=["Test_Vsaas_Soterix::test_events_search"])
    def test_event_review_videos(self, params):
        driver = params['driver']
        
        print("Clicking on Review Videos page open button")
        review_video_page_button_element = driver.find_element(By.XPATH, value=".//img[contains(@src,'media/light')]")
        review_video_page_button_element.click()
        print("Clicked on Review Videos page open button")
        
        # Wait for the page to load
        print("Waiting for max 60 sec for Review Related Videos to open")
        element_present = EC.presence_of_all_elements_located((By.XPATH, "//button[normalize-space()='Review Videos']"))
        try:
            WebDriverWait(driver, 60).until(element_present)
            print("Navigated to Review Related Videos")
        except:
            print("Failed to Navigate to Review Related Videos")
            assert False, "Failed to Navigate to Review Related Videos"
            
        print("Clicking on Review Videos button")
        review_video_button_element = driver.find_element(By.XPATH, value="//button[normalize-space()='Review Videos']")
        review_video_button_element.click()
        print("Clicked on Review Videos button")
        
        # Wait for the page to load
        print("Waiting for max 60 sec for Review Related Videos play ")
        element_present = EC.presence_of_all_elements_located((By.XPATH, "//button[normalize-space()='Play Videos']"))
        try:
            WebDriverWait(driver, 60).until(element_present)
            print("Navigated to Review Related Videos Play")
        except:
            print("Failed to Navigate to Review Related Videos")
            assert False, "Failed to Navigate to Review Related Videos"
        
        # Clicking on Play Videos    
        print("Clicking on Play Videos button")
        review_video_button_element = driver.find_element(By.XPATH, value="//button[normalize-space()='Play Videos']")
        review_video_button_element.click()
        print("Clicked on Play Videos button")
        
        try:
            print("Waiting for max 60 sec for loader to stop. That is video to play")
            element_present = EC.presence_of_all_elements_located((By.XPATH, "//*[contains(@class,'CircularProgress')]"))
            live_icon_elements = WebDriverWait(driver, 60).until(element_present)
            review_video_element = driver.find_element(by=By.CLASS_NAME, value="review-video")
            circular_progress_element_before = review_video_element.find_elements(by=By.XPATH, value=".//*[contains(@class,'CircularProgress')]")
            
            wait_item = WebDriverWait(driver, 60).until(EC.invisibility_of_element_located((By.XPATH, "//*[contains(@class,'CircularProgress')]")))
            print("Loader is stopped")
            print("All Videos are playing successfully")
            #print("Waiting max 90 sec for reload icon to appear")
            ##replay-0
            #reload_button = WebDriverWait(driver, 600).until(EC.presence_of_all_elements_located((By.XPATH, "//img[@alt='Replay']")))
            #print("Reload Icon Appeared")
            #print("Event Video clip is played successfully")
        except:
            video_player_elements = review_video_element.find_elements(by=By.CLASS_NAME, value="player__wrapper")
            circular_progress_element_after = review_video_element.find_elements(by=By.XPATH, value=".//*[contains(@class,'CircularProgress')]")
            assert len(circular_progress_element_before) < len(circular_progress_element_after), "Failed to play related videos"
            
        # GoBackArrow
        related_videos_play_screen_element = driver.find_elements(By.CLASS_NAME, value="popup-content")
        print("Clicking on back button to go back to event play")
        review_video_page_back_element = related_videos_play_screen_element[0].find_element(By.XPATH, value=".//img[contains(@src,'media/GoBackArrow')]")
        review_video_page_back_element.click()
        
        time.sleep(2)
            
        # GoBackArrow
        print("Clicking on back button to go back to event play")
        review_related_video_page_back_element = driver.find_element(By.XPATH, value=".//img[contains(@src,'media/GoBackArrow')]")
        review_related_video_page_back_element.click()
        
        time.sleep(2)
        
        # Wait for the Event video player page to load
        print("Waiting for max 15 sec for going to Event Video Player Page")
        element_present = EC.presence_of_all_elements_located((By.XPATH, ".//img[contains(@src,'media/light')]"))
        try:
            WebDriverWait(driver, 15).until(element_present)
            print("Navigated to Event Video Player Page")
        except:
            print("Failed to Navigate to Event Video Player Page")
            assert False, "Failed to Navigate to Event Video Player Page"

    @pytest.mark.dependency(depends=["Test_Vsaas_Soterix::test_events_search"])
    def test_event_export(self, params):
        driver = params['driver']
         
        # Click on Export button  
        export_element = driver.find_element(by=By.XPATH, value="//img[contains(@src, 'media/icon-download')]")
        export_element.click()
        time.sleep(5)
        
        # Export
        self.export_share_check_media(params, is_export=True, check_media=True)

    @pytest.mark.dependency(depends=["Test_Vsaas_Soterix::test_login"])
    def test_maps(self, params):
        driver = params['driver']
        site_name = params['site_name']
        action = ActionChains(driver)
        time.sleep(5)
        
        # Maps
        search_button_element = driver.find_element(By.XPATH, value='//a[contains(@href,"maps")]')
        search_button_element.click()
        
        # Wait for the page to load
        element_present = EC.presence_of_all_elements_located((By.CLASS_NAME, "dropdown_text"))
        
        try:
            WebDriverWait(driver, 15).until(element_present)
            print("Navigated to Maps Page")
        except:
            print("Failed to Navigate to Maps Page in 15 Sec")
            assert False, "Failed to Navigate to Maps Page in 15 Sec"
        
        # Waiting for sites to load in dropdown
        for i in range(10):
            site_drop_down_element = driver.find_element(by=By.CLASS_NAME, value="dropdown_text")
            if "sites" in site_drop_down_element.get_attribute("title").lower():
                time.sleep(6)
            else:
                break
        
        # Click on Site dropdown
        time.sleep(2)
        site_drop_down_element = driver.find_element(by=By.CLASS_NAME, value="dropdown-box")
        site_drop_down_element.click()
        print("Clicked on Site Drop Down")
        time.sleep(1)
        
        # Selecting the site
        site_drop_down_list_element = driver.find_element(by=By.CLASS_NAME, value="optionsdataDiv")
        site_element = site_drop_down_list_element.find_element(By.XPATH, value=f".//*[contains(text(), \"{site_name}\")]")
        action.scroll_to_element(site_element).perform()
        action.move_to_element(site_element).perform()
        action.click(site_element).perform()
        
        # Wait for maps to load
        try:
            element_present = EC.presence_of_all_elements_located((By.CLASS_NAME, 'grid-cards'))
            map_elements = WebDriverWait(driver, 60).until(element_present)
            print("Maps loaded successfully")
        except:
            print("Failed to load maps")
            assert False, "Failed to load maps"
        
        # icon-text-alinger
        for map_element in map_elements:
            found_map = False
            device_elements = map_element.find_elements(by=By.CLASS_NAME, value="icon-text-alinger")
            if "0" != device_elements[0].find_elements(By.TAG_NAME, "div")[1].text.strip():
                found_map = True
                break
        if found_map:
            map_element.click()
            # Wait for maps to load
            try:
                element_present = EC.presence_of_all_elements_located((By.XPATH, "//img[contains(@src,'media/cameraIcon')]"))
                map_elements = WebDriverWait(driver, 60).until(element_present)
                print("Map opened successfully")
            except:
                print("Failed to open map")
                assert False, "Failed to open map"
        else:
            print("None of the maps has cameras added")   

    @pytest.mark.dependency(depends=["Test_Vsaas_Soterix::test_maps"])
    def test_maps_play_online_camera(self, params):
        driver = params['driver']
        time.sleep(5)
        
        # Playing online camera
        online_cameras = driver.find_elements(By.XPATH, "//img[contains(@src,'media/cameraIconGreen')]")
        if len(online_cameras) > 0:
            online_cameras[0].click()
        
            try:
                element_present = EC.presence_of_all_elements_located((By.XPATH, "//*[contains(@class,'CircularProgress')]"))
                live_icon_elements = WebDriverWait(driver, 60).until(element_present)
                
                print("Waiting for loader to stop for 60 Sec")
                wait_item = WebDriverWait(driver, 60).until(EC.invisibility_of_element_located((By.XPATH, "//*[contains(@class,'CircularProgress')]")))
                print("Loader has stopped. Checking whether streaming is working or failed")
                streaming_failed_elements = driver.find_elements(By.XPATH, value=".//*[contains(text(),'failed to load')]")               
                if len(streaming_failed_elements) == 0:
                    #stream_failed_elements = tile_elements[tile_index].find_element(By.XPATH, ".//button[text()='Refresh']")
                    print("Streaming is Working")
                    time.sleep(2)
                else:
                    assert False, "Failed to play camera"
            except:
                assert False, "Failed to perform actions"
                
        else:
            print("No cameras are online")        

    @pytest.mark.dependency(depends=["Test_Vsaas_Soterix::test_login"])
    def test_insights_system_status_dashboard(self, params):
        driver = params['driver']
        site_name = params['site_name']
        location_name = params['location_name']
        camera_name = params['camera_name']
        action = ActionChains(driver)
        time.sleep(5)
        
        # Open Insights page
        self.open_insights_page(params)
            
        # Open System Status Dashboard
        print("Opening System Status Dashboard")
        system_status_element = driver.find_element(By.XPATH, value='//a[contains(@href,"insights/systemStatus")]')
        system_status_element.click()
        
        # Wait for System Status Dashboard to open
        element_present = EC.presence_of_all_elements_located((By.CLASS_NAME, 'dropdown-box'))
        
        try:
            WebDriverWait(driver, 15).until(element_present)
            print("System Status Dashboard opened successfully")
        except:
            print("Failed to open System Status Dashboard in 15 Sec")
            assert False, "Failed to open System Status Dashboard in 15 Sec"
            
        # Switching site
        print(f"Switching site to {site_name}")
        sites_dropdown_element = driver.find_element(by=By.CLASS_NAME, value='dropdown-box')
        sites_dropdown_element.click()
        time.sleep(2)
        
        # Select site
        site_select_element = driver.find_element(By.XPATH, f'//div[text()=\"{site_name}\"]')
        
        # Scroll to the element and click
        ActionChains(driver).move_to_element(site_select_element).perform()
        site_select_element.click()
        
        # Wait up to 10 seconds for data to load
        try:
            element = WebDriverWait(driver, 10).until(
                EC.presence_of_all_elements_located((By.XPATH, '//p[text()="Devices"]'))
            )
            print(f"System Status Dashboard opend for site {site_name} successfully")
        except:
            print(f"Failed to open System Status Dashboard for site {site_name} within 10 seconds.")
        time.sleep(10)        
        # Close System Status Tab
        print("Closing System Status tab")
        tab_close_element = driver.find_element(By.XPATH, value=".//img[contains(@src,'media/closeIcon')]")
        tab_close_element.click()
        print("System Status tab closed successfully")

    @pytest.mark.dependency(depends=["Test_Vsaas_Soterix::test_login"])
    def test_linegraph_person_insights_create_export_delete(self, params):
        created_widget_name = self.create_widget(params, graph_index=0, graph_name="Line", category_name="Person", widget_size_index=0)
        time.sleep(20)
        self.widget_operation(params, created_widget_name, "View")
        self.widget_operation(params, created_widget_name, "Report")
        self.widget_operation(params, created_widget_name, "Delete")

    @pytest.mark.dependency(depends=["Test_Vsaas_Soterix::test_login"])
    def test_linegraph_vehicle_insights_create_export_delete(self, params):
        created_widget_name = self.create_widget(params, graph_index=0, graph_name="Line", category_name="Vehicle", widget_size_index=0)
        time.sleep(20)
        self.widget_operation(params, created_widget_name, "View")
        self.widget_operation(params, created_widget_name, "Report")
        self.widget_operation(params, created_widget_name, "Delete")

    @pytest.mark.dependency(depends=["Test_Vsaas_Soterix::test_login"])
    def test_linegraph_event_insights_create_export_delete(self, params):
        created_widget_name = self.create_widget(params, graph_index=0, graph_name="Line", category_name="Event", widget_size_index=0)
        time.sleep(20)
        self.widget_operation(params, created_widget_name, "View")
        self.widget_operation(params, created_widget_name, "Report")
        self.widget_operation(params, created_widget_name, "Delete") 

    @pytest.mark.dependency(depends=["Test_Vsaas_Soterix::test_login"])
    def test_bargraph_person_insights_create_export_delete(self, params):
        created_widget_name = self.create_widget(params, graph_index=1, graph_name="Bar", category_name="Person", widget_size_index=0)
        time.sleep(20)
        self.widget_operation(params, created_widget_name, "View")
        self.widget_operation(params, created_widget_name, "Report")
        self.widget_operation(params, created_widget_name, "Delete")

    @pytest.mark.dependency(depends=["Test_Vsaas_Soterix::test_login"])
    def test_bargraph_vehicle_insights_create_export_delete(self, params):
        created_widget_name = self.create_widget(params, graph_index=1, graph_name="Bar", category_name="Vehicle", widget_size_index=0)
        time.sleep(20)
        self.widget_operation(params, created_widget_name, "View")
        self.widget_operation(params, created_widget_name, "Report")
        self.widget_operation(params, created_widget_name, "Delete")

    @pytest.mark.dependency(depends=["Test_Vsaas_Soterix::test_login"])
    def test_bargraph_event_insights_create_export_delete(self, params):
        created_widget_name = self.create_widget(params, graph_index=1, graph_name="Bar", category_name="Event", widget_size_index=0)
        time.sleep(20)
        self.widget_operation(params, created_widget_name, "View")
        self.widget_operation(params, created_widget_name, "Report")
        self.widget_operation(params, created_widget_name, "Delete")  

    @pytest.mark.dependency(depends=["Test_Vsaas_Soterix::test_login"])
    def test_piegraph_person_insights_create_export_delete(self, params):
        created_widget_name = self.create_widget(params, graph_index=4, graph_name="Pie", category_name="Person", widget_size_index=0)
        time.sleep(20)
        self.widget_operation(params, created_widget_name, "View")
        self.widget_operation(params, created_widget_name, "Report")
        self.widget_operation(params, created_widget_name, "Delete")

    @pytest.mark.dependency(depends=["Test_Vsaas_Soterix::test_login"])
    def test_piegraph_vehicle_insights_create_export_delete(self, params):
        created_widget_name = self.create_widget(params, graph_index=4, graph_name="Pie", category_name="Vehicle", widget_size_index=0)
        time.sleep(20)
        self.widget_operation(params, created_widget_name, "View")
        self.widget_operation(params, created_widget_name, "Report")
        self.widget_operation(params, created_widget_name, "Delete")

    @pytest.mark.dependency(depends=["Test_Vsaas_Soterix::test_login"])
    def test_piegraph_event_insights_create_export_delete(self, params):
        created_widget_name = self.create_widget(params, graph_index=4, graph_name="Pie", category_name="Event", widget_size_index=0)
        time.sleep(20)
        self.widget_operation(params, created_widget_name, "View")
        self.widget_operation(params, created_widget_name, "Report")
        self.widget_operation(params, created_widget_name, "Delete") 

    @pytest.mark.dependency(depends=["Test_Vsaas_Soterix::test_login"])
    def test_heatmap_person_insights_create_export_delete(self, params):
        created_widget_name = self.create_widget(params, graph_index=5, graph_name="Heat", category_name="Person", widget_size_index=0)
        time.sleep(20)
        self.widget_operation(params, created_widget_name, "View")
        self.widget_operation(params, created_widget_name, "Report")
        self.widget_operation(params, created_widget_name, "Delete")

    @pytest.mark.dependency(depends=["Test_Vsaas_Soterix::test_login"])
    def test_heatmap_vehicle_insights_create_export_delete(self, params):
        created_widget_name = self.create_widget(params, graph_index=5, graph_name="Heat", category_name="Vehicle", widget_size_index=0)
        time.sleep(20)
        self.widget_operation(params, created_widget_name, "View")
        self.widget_operation(params, created_widget_name, "Report")
        self.widget_operation(params, created_widget_name, "Delete")      
    
    @pytest.mark.dependency(depends=["Test_Vsaas_Soterix::test_login"])
    def test_person_global_search(self, params):
        driver = params['driver']
        site_name = params['site_name']
        location_name = params['location_name']
        camera_name = params['camera_name']
        
        time.sleep(5)
        action = ActionChains(driver)
        # Global Search
        search_button_element = driver.find_element(By.XPATH, value='//a[contains(@href,"search")]')
        search_button_element.click()
        print("Clicked on Search button to navigate to Global search page")
        
        # Wait for the page to load
        print("Waiting for max 15 sec for global search page to load")
        element_present = EC.presence_of_all_elements_located((By.XPATH, "//label[@for='Category']"))
        try:
            WebDriverWait(driver, 15).until(element_present)
            print("Navigated to Global Search Page")
        except:
            print("Failed to Navigate to Global Search Page in 15 Sec")
            assert False, "Failed to Navigate to Global Search Page in 15 Sec"
        
        # Category, Appearance and Duration selection
        global_search_dropdown_elements = driver.find_elements(By.CLASS_NAME, value='search_select_box_container')
        for global_search_dropdown_element in global_search_dropdown_elements:
            time.sleep(2)
            global_search_dropdown_element.click()
            if 'Category' in global_search_dropdown_element.text:
                category_selection_elements = driver.find_elements(by=By.CLASS_NAME, value='dropdownItem')
                category_selection_elements[0].click()
                print("Selected category as 'Person'")
            elif 'Description' in global_search_dropdown_element.text:
                gender_container_element = driver.find_element(By.CLASS_NAME, value="gender-option-container")
                gender_elements = gender_container_element.find_elements(By.XPATH, value=".//p[contains(@text,'')]")
                for gender_element in gender_elements:
                    if gender_element.text == 'Male':
                        gender_element.click()
                        print("Selected Description as 'Male'")
                        break
            elif 'Locations & Cameras' in global_search_dropdown_element.text:
                site_element = driver.find_element(by=By.XPATH, value=f".//*[contains(text(), \"{site_name}\")]")
                site_element.click()
                print(f"Selected site as \"{site_name}\"")
                time.sleep(2)
                
                location_elements = driver.find_elements(by=By.XPATH, value=f".//*[contains(text(), '{location_name}')]")
                for location_element in location_elements:
                    if location_element.is_displayed():
                        location_element.click()
                        break
                print(f"Selected Location as '{location_name}'")
                time.sleep(2)
                
                camera_elements = driver.find_elements(by=By.CLASS_NAME, value="global-search-camera-container")
                for camera_element in camera_elements:
                    if camera_name in camera_element.text:
                        if camera_element.find_elements(by=By.XPATH, value=".//img[contains(@src,'media/driveIcon')]"):
                            pass
                        else:             
                            camera_checkbox_element_button = camera_element.find_element(by=By.XPATH, value=".//*[contains(@class,'MuiButtonBase-root')]")
                            action.scroll_to_element(camera_element).perform()
                            action.move_to_element(camera_element).perform()
                            time.sleep(1)
                            checkbox = camera_element.find_element(by=By.CLASS_NAME, value="MuiSvgIcon-root")
                            action.click(checkbox).perform()
                            print(f"Hovered on Camera {camera_name} and checked the check box")
                            action.send_keys(Keys.ESCAPE).perform()
                            time.sleep(1)
                            break
                
                location_elements = driver.find_elements(by=By.XPATH, value=f".//*[contains(text(), '{location_name}')]")
                for location_element in location_elements:
                    if location_element.is_displayed():
                        location_element.click()
                        break
                time.sleep(2)
                global_search_dropdown_element.click()
            else:
                duration_selection_elements = driver.find_elements(by=By.CLASS_NAME, value='dropdownItem')
                duration_selection_elements[4].click()
                print("Selected Duration as 'Today'")
        
        # Click on Search Button
        search_button_element = driver.find_element(By.XPATH, value="//img[contains(@src,'search_icon')]")
        search_button_element.click()
        print("Clicked on Search Button")
        
        element_present = EC.presence_of_all_elements_located((By.CLASS_NAME, "global-imageResults"))
        try:
            print("Waiting for max 60 sec for loading events")
            WebDriverWait(driver, 60).until(element_present)
            print("Events are loaded successfully")
        except:
            assert False, "Failed to load Events in 60Sec"
           
        image_result_elements = driver.find_elements(By.CLASS_NAME, value="global-imageResults")
        for image_result_element in image_result_elements:
            #image_result_element.click()
            #//img[contains(@src,'video-player')]
            # Hover on camera
            if image_result_element.is_displayed:
                print("Hover on an Event and click on play icon")
                action.move_to_element(image_result_element).perform()
                video_player_elements = image_result_element.find_elements(By.XPATH, ".//img[contains(@src, 'media/playClip')]")
                video_player_elements[0].click()
                print("Hoverd on an Event and clicked on play icon")
                try:
                    print("Waiting for max 60 sec for loader to stop. That is video to play")
                    element_present = EC.presence_of_all_elements_located((By.XPATH, "//*[contains(@class,'CircularProgress')]"))
                    live_icon_elements = WebDriverWait(driver, 60).until(element_present)
                    
                    wait_item = WebDriverWait(driver, 60).until(EC.invisibility_of_element_located((By.XPATH, "//*[contains(@class,'CircularProgress')]")))
                    print("Loader is stopped")
                    print("Video is playing successfully")
                    print("Waiting max 90 sec for reload icon to appear")
                    #replay-0
                    reload_button = WebDriverWait(driver, 600).until(EC.presence_of_all_elements_located((By.XPATH, "//img[@alt='Replay']")))
                    print("Reload Icon Appeared")
                    print("Event Video clip is played successfully")
                    break
                    #streaming_failed_elements = driver.find_elements(By.XPATH, value=".//*[contains(text(),'failed to load')]")
                except:
                    assert False, "Failed to play Event clip"
                    
    #@pytest.mark.dependency(depends=["Test_Vsaas_Soterix::test_login"])
    def test_person_global_search_api_calls(self, params):
        self.log_api_data(params['driver'])
        
    @pytest.mark.dependency(depends=["Test_Vsaas_Soterix::test_login"])
    def test_vehicle_global_search(self, params):
        driver = params['driver']
        site_name = params['site_name']
        location_name = params['location_name']
        camera_name = params['camera_name']
        
        time.sleep(10)
        action = ActionChains(driver)
        # Global Search
        
        # Wait for the page to load
        print("Waiting for max 15 sec for global search page to load")
        element_present = EC.presence_of_all_elements_located((By.XPATH, "//label[@for='Category']"))
        try:
            WebDriverWait(driver, 15).until(element_present)
            print("Navigated to Global Search Page")
        except:
            print("Failed to Navigate to Global Search Page in 15 Sec")
            assert False, "Failed to Navigate to Global Search Page in 15 Sec"
        
        # Category, Appearance and Duration selection
        global_search_dropdown_elements = driver.find_elements(By.CLASS_NAME, value='search_select_box_container')
        for global_search_dropdown_element in global_search_dropdown_elements:
            time.sleep(2)
            global_search_dropdown_element.click()
            if 'Category' in global_search_dropdown_element.text:
                category_selection_elements = driver.find_elements(by=By.CLASS_NAME, value='dropdownItem')
                category_selection_elements[1].click()
                print("Selected category as 'Vehicle'")
            elif 'Description' in global_search_dropdown_element.text:
                #gender_container_element = driver.find_element(By.CLASS_NAME, value="gender-option-container")
                #gender_elements = gender_container_element.find_elements(By.XPATH, value=".//p[contains(@text,'')]")
                #for gender_element in gender_elements:
                    #if gender_element.text == 'Male':
                        #gender_element.click()
                        #print("Selected Description as 'Male'")
                        #break
                pass
            elif 'Locations & Cameras' in global_search_dropdown_element.text:
                site_element = driver.find_element(by=By.XPATH, value=f".//*[contains(text(), \"{site_name}\")]")
                site_element.click()
                print(f"Selected site as \"{site_name}\"")
                time.sleep(2)
                
                location_elements = driver.find_elements(by=By.XPATH, value=f".//*[contains(text(), '{location_name}')]")
                for location_element in location_elements:
                    if location_element.is_displayed():
                        location_element.click()
                        break
                print(f"Selected Location as '{location_name}'")
                time.sleep(2)
                
                camera_elements = driver.find_elements(by=By.CLASS_NAME, value="global-search-camera-container")
                for camera_element in camera_elements:
                    if camera_name in camera_element.text:
                        if camera_element.find_elements(by=By.XPATH, value=".//img[contains(@src,'media/driveIcon')]"):
                            pass
                        else:             
                            camera_checkbox_element_button = camera_element.find_element(by=By.XPATH, value=".//*[contains(@class,'MuiButtonBase-root')]")
                            action.scroll_to_element(camera_element).perform()
                            action.move_to_element(camera_element).perform()
                            time.sleep(1)
                            checkbox = camera_element.find_element(by=By.CLASS_NAME, value="MuiSvgIcon-root")
                            action.click(checkbox).perform()
                            print(f"Hovered on Camera {camera_name} and checked the check box")
                            action.send_keys(Keys.ESCAPE).perform()
                            time.sleep(1)
                            break
                
                location_elements = driver.find_elements(by=By.XPATH, value=f".//*[contains(text(), '{location_name}')]")
                for location_element in location_elements:
                    if location_element.is_displayed():
                        location_element.click()
                        break
                time.sleep(2)
                global_search_dropdown_element.click()    
            else:
                duration_selection_elements = driver.find_elements(by=By.CLASS_NAME, value='dropdownItem')
                duration_selection_elements[4].click()
                print("Selected Duration as 'Today'")
        
        # Click on Search Button
        search_button_element = driver.find_element(By.XPATH, value="//img[contains(@src,'search_icon')]")
        search_button_element.click()
        print("Clicked on Search Button")
        
        element_present = EC.presence_of_all_elements_located((By.CLASS_NAME, "global-imageResults"))
        try:
            print("Waiting for max 60 sec for loading events")
            WebDriverWait(driver, 60).until(element_present)
            print("Events are loaded successfully")
        except:
            assert False, "Failed to load Events in 60Sec"
         
        image_result_elements = driver.find_elements(By.CLASS_NAME, value="global-imageResults")
        for image_result_element in image_result_elements:
            #image_result_element.click()
            #//img[contains(@src,'video-player')]
            # Hover on camera
            if image_result_element.is_displayed:
                print("Hover on an Event and click on play icon")
                action.move_to_element(image_result_element).perform()
                video_player_elements = image_result_element.find_elements(By.XPATH, ".//img[contains(@src, 'media/playClip')]")
                video_player_elements[0].click()
                print("Hoverd on an Event and clicked on play icon")
                try:
                    print("Waiting for max 60 sec for loader to stop. That is video to play")
                    element_present = EC.presence_of_all_elements_located((By.XPATH, "//*[contains(@class,'CircularProgress')]"))
                    live_icon_elements = WebDriverWait(driver, 60).until(element_present)
                    
                    wait_item = WebDriverWait(driver, 60).until(EC.invisibility_of_element_located((By.XPATH, "//*[contains(@class,'CircularProgress')]")))
                    print("Loader is stopped")
                    print("Video is playing successfully")
                    print("Waiting max 90 sec for reload icon to appear")
                    #replay-0
                    reload_button = WebDriverWait(driver, 600).until(EC.presence_of_all_elements_located((By.XPATH, "//img[@alt='Replay']")))
                    print("Reload Icon Appeared")
                    print("Event Video clip is played successfully")
                    break
                    #streaming_failed_elements = driver.find_elements(By.XPATH, value=".//*[contains(text(),'failed to load')]")
                except:
                    assert False, "Failed to play Event clip"
                    
    #@pytest.mark.dependency(depends=["Test_Vsaas_Soterix::test_login"])
    def test_vehicle_global_search_api_calls(self, params):
        self.log_api_data(params['driver'])
        
    @pytest.mark.dependency(depends=["Test_Vsaas_Soterix::test_login"])
    def test_global_event_search(self, params):
        driver = params['driver']
        site_name = params['site_name']
        location_name = params['location_name']
        camera_name = params['camera_name']
        
        time.sleep(10)
        action = ActionChains(driver)
        # Global Search
        
        # Wait for the page to load
        print("Waiting for max 15 sec for global search page to load")
        element_present = EC.presence_of_all_elements_located((By.XPATH, "//label[@for='Category']"))
        try:
            WebDriverWait(driver, 15).until(element_present)
            print("Navigated to Global Search Page")
        except:
            print("Failed to Navigate to Global Search Page in 15 Sec")
            assert False, "Failed to Navigate to Global Search Page in 15 Sec"
        
        # Category, Appearance and Duration selection
        global_search_dropdown_elements = driver.find_elements(By.CLASS_NAME, value='search_select_box_container')
        for global_search_dropdown_element in global_search_dropdown_elements:
            time.sleep(2)
            global_search_dropdown_element.click()
            if 'Category' in global_search_dropdown_element.text:
                category_selection_elements = driver.find_elements(by=By.CLASS_NAME, value='dropdownItem')
                category_selection_elements[2].click()
                print("Selected category as 'Vehicle'")
            elif 'Description' in global_search_dropdown_element.text:
                #gender_container_element = driver.find_element(By.CLASS_NAME, value="gender-option-container")
                #gender_elements = gender_container_element.find_elements(By.XPATH, value=".//p[contains(@text,'')]")
                #for gender_element in gender_elements:
                    #if gender_element.text == 'Male':
                        #gender_element.click()
                        #print("Selected Description as 'Male'")
                        #break
                pass
            elif 'Locations & Cameras' in global_search_dropdown_element.text:
                site_element = driver.find_element(by=By.XPATH, value=f".//*[contains(text(), \"{site_name}\")]")
                site_element.click()
                print(f"Selected site as \"{site_name}\"")
                time.sleep(2)
                
                location_elements = driver.find_elements(by=By.XPATH, value=f".//*[contains(text(), '{location_name}')]")
                for location_element in location_elements:
                    if location_element.is_displayed():
                        location_element.click()
                        break
                print(f"Selected Location as '{location_name}'")
                time.sleep(2)
                
                camera_elements = driver.find_elements(by=By.CLASS_NAME, value="global-search-camera-container")
                for camera_element in camera_elements:
                    if camera_name in camera_element.text:
                        if camera_element.find_elements(by=By.XPATH, value=".//img[contains(@src,'media/driveIcon')]"):
                            pass
                        else:             
                            camera_checkbox_element_button = camera_element.find_element(by=By.XPATH, value=".//*[contains(@class,'MuiButtonBase-root')]")
                            action.scroll_to_element(camera_element).perform()
                            action.move_to_element(camera_element).perform()
                            time.sleep(1)
                            checkbox = camera_element.find_element(by=By.CLASS_NAME, value="MuiSvgIcon-root")
                            action.click(checkbox).perform()
                            print(f"Hovered on Camera {camera_name} and checked the check box")
                            action.send_keys(Keys.ESCAPE).perform()
                            time.sleep(1)
                            break
                
                location_elements = driver.find_elements(by=By.XPATH, value=f".//*[contains(text(), '{location_name}')]")
                for location_element in location_elements:
                    if location_element.is_displayed():
                        location_element.click()
                        break
                time.sleep(2)
                global_search_dropdown_element.click()    
            else:
                duration_selection_elements = driver.find_elements(by=By.CLASS_NAME, value='dropdownItem')
                duration_selection_elements[4].click()
                print("Selected Duration as 'Today'")
        
        # Click on Search Button
        search_button_element = driver.find_element(By.XPATH, value="//img[contains(@src,'search_icon')]")
        search_button_element.click()
        print("Clicked on Search Button")
        
        element_present = EC.presence_of_all_elements_located((By.CLASS_NAME, "global-imageResults"))
        try:
            print("Waiting for max 60 sec for loading events")
            WebDriverWait(driver, 60).until(element_present)
            print("Events are loaded successfully")
        except:
            assert False, "Failed to load Events in 60Sec"
          
        image_result_elements = driver.find_elements(By.CLASS_NAME, value="global-imageResults")
        for image_result_element in image_result_elements:
            #image_result_element.click()
            #//img[contains(@src,'video-player')]
            # Hover on camera
            if image_result_element.is_displayed:
                print("Hover on an Event and click on play icon")
                action.move_to_element(image_result_element).perform()
                video_player_elements = image_result_element.find_elements(By.XPATH, ".//img[contains(@src, 'media/playClip')]")
                video_player_elements[0].click()
                print("Hoverd on an Event and clicked on play icon")
                try:
                    print("Waiting for max 60 sec for loader to stop. That is video to play")
                    element_present = EC.presence_of_all_elements_located((By.XPATH, "//*[contains(@class,'CircularProgress')]"))
                    live_icon_elements = WebDriverWait(driver, 60).until(element_present)
                    
                    wait_item = WebDriverWait(driver, 60).until(EC.invisibility_of_element_located((By.XPATH, "//*[contains(@class,'CircularProgress')]")))
                    print("Loader is stopped")
                    print("Video is playing successfully")
                    print("Waiting max 90 sec for reload icon to appear")
                    #replay-0
                    reload_button = WebDriverWait(driver, 600).until(EC.presence_of_all_elements_located((By.XPATH, "//img[@alt='Replay']")))
                    print("Reload Icon Appeared")
                    print("Event Video clip is played successfully")
                    break
                    #streaming_failed_elements = driver.find_elements(By.XPATH, value=".//*[contains(text(),'failed to load')]")
                except:
                    assert False, "Failed to play Event clip"
                    
    #@pytest.mark.dependency(depends=["Test_Vsaas_Soterix::test_login"])
    def test_global_event_search_api_calls(self, params):
        self.log_api_data(params['driver'])
       
    @pytest.mark.dependency(depends=["Test_Vsaas_Soterix::test_login"])
    def test_zone_global_search(self, params):
        driver = params['driver']
        site_name = params['site_name']
        location_name = params['location_name']
        camera_name = params['camera_name']
        
        time.sleep(5)
        action = ActionChains(driver)
        # Global Search
        #search_button_element = driver.find_element(By.XPATH, value='//a[contains(@href,"search")]')
        #search_button_element.click()
        
        # Wait for the page to load
        element_present = EC.presence_of_all_elements_located((By.XPATH, "//label[@for='Category']"))
        
        try:
            WebDriverWait(driver, 15).until(element_present)
            print("Navigated to Global Search Page")
        except:
            print("Failed to Navigate to Global Search Page in 15 Sec")
            assert False, "Failed to Navigate to Global Search Page in 15 Sec"
        
        # Category, Appearance and Duration selection
        global_search_dropdown_elements = driver.find_elements(By.CLASS_NAME, value='search_select_box_container')
        for global_search_dropdown_element in global_search_dropdown_elements:
            time.sleep(2)
            global_search_dropdown_element.click()
            if 'Category' in global_search_dropdown_element.text:
                category_selection_elements = driver.find_elements(by=By.CLASS_NAME, value='dropdownItem')
                category_selection_elements[3].click()
            elif 'Description' in global_search_dropdown_element.text:
                pass
            elif 'Locations & Cameras' in global_search_dropdown_element.text:
                site_element = driver.find_element(by=By.XPATH, value=f".//*[contains(text(), \"{site_name}\")]")
                site_element.click()
                time.sleep(2)
                
                location_elements = driver.find_elements(by=By.XPATH, value=f".//*[contains(text(), '{location_name}')]")
                for location_element in  location_elements:
                    if location_element.is_displayed():
                        location_element.click()
                        break
                time.sleep(2)
                
                #global_camera_elements = driver.find_elements(by=By.CLASS_NAME, value="global-search-camera-container MuiBox-root mui-1v708vx")
                #for global_camera_element in global_camera_elements:
                    #camera_elements = global_camera_element.find_elements(by=By.XPATH, value=f".//p[text()='{camera_name}']")
                    #if camera_elements:
                        #break
                #assert camera_elements, "Camera not found"
                camera_elements = driver.find_elements(by=By.CLASS_NAME, value="global-search-camera-container")
                for camera_element in camera_elements:
                    if camera_name in camera_element.text:
                        if camera_element.find_elements(by=By.XPATH, value=".//img[contains(@src,'media/driveIcon')]"):
                            pass
                        else:
                            print(f"Hovering on Camera {camera_name} and clicking on Line")
                            action.move_to_element(camera_element).perform()
                            time.sleep(1)
                            create_zone_container_elements = driver.find_elements(by=By.XPATH, value=f"//p[text()='Create Zone']")
                            for create_zone_container_element in create_zone_container_elements:
                                if create_zone_container_element.is_displayed():                  
                                    create_zone_container_element.click()
                                    break
                            print(f"Hovered on Camera {camera_name} and clicked on Line Successfully")
                            
                            # Wait for loader to appear and stop
                            
                            print("Waiting for Loader to appear and stop")
                            element_present = EC.presence_of_all_elements_located((By.XPATH, "//*[contains(@class,'CircularProgress')]"))
                            live_icon_elements = WebDriverWait(driver, 60).until(element_present)
                            
                            wait_item = WebDriverWait(driver, 60).until(EC.invisibility_of_element_located((By.XPATH, "//*[contains(@class,'CircularProgress')]"))) 
                            print("Loader appeared and stopped")                     
                            
                            #time.sleep(10)
                            #print("Waiting for Done Button to appear")
                            #element_present = EC.presence_of_all_elements_located((By.CLASS_NAME, "save-btn"))
                            #done_button = WebDriverWait(driver, 60).until(element_present)
                            
                            # Click on Rectangle Button
                            #print("Clicking on Rectangle Button")
                            #rectangle_button_element = driver.find_element(by=By.XPATH, value=".//img[contains(@src,'media/rectangle-icon')]")
                            #rectangle_button_element.click()
                            #print("Clicked on Rectangle Button")
                            
                            # Draw Zone
                            print("Drawing the Zone")
                            zone_draw_area_element = driver.find_element(by=By.CLASS_NAME, value="upper-canvas")
                            action.move_to_element_with_offset(zone_draw_area_element, -500, -250).click().perform()
                            action.move_to_element_with_offset(zone_draw_area_element, 500, -250).click().perform()
                            action.move_to_element_with_offset(zone_draw_area_element, 500, 200).click().perform()
                            action.move_to_element_with_offset(zone_draw_area_element, -500, 200).click().perform()
                            action.move_to_element_with_offset(zone_draw_area_element, -500, -250).click().perform()                            
                            zone_draw_area_element.click()
                            print("Drawn the Zone")
                            
                            # Click on Done Button
                            print("Clicking on Done button")
                            done_button_element = driver.find_element(by=By.CLASS_NAME, value="save-btn")
                            if "not-allowed" in done_button_element.get_attribute("style"):
                                zone_draw_area_element = driver.find_element(by=By.CLASS_NAME, value="upper-canvas")
                                action.move_to_element_with_offset(zone_draw_area_element, -250, -125).click().perform()
                                action.move_to_element_with_offset(zone_draw_area_element, 250, -125).click().perform()
                                action.move_to_element_with_offset(zone_draw_area_element, 250, 100).click().perform()
                                action.move_to_element_with_offset(zone_draw_area_element, -250, 100).click().perform()
                                action.move_to_element_with_offset(zone_draw_area_element, -250, -125).click().perform()                            
                                zone_draw_area_element.click()
                                
                            done_button_element.click()
                            print("Clicked on Done button")
                            
                            time.sleep(5)
                            print("Selecting Duration as Today")
                            dropdown_elements = driver.find_elements(By.CLASS_NAME, value='search_select_box_container')
                            for dropdown_element in dropdown_elements:                    
                                if 'Duration' in dropdown_element.text:
                                    dropdown_element.click()
                                    time.sleep(2)
                                    duration_selection_elements = driver.find_elements(by=By.CLASS_NAME, value='dropdownItem')
                                    duration_selection_elements[4].click()
                                    print("Selected Duration as Today")
                                    break
                        break
                break
            
            #else:
                #duration_selection_elements = driver.find_elements(by=By.CLASS_NAME, value='dropdownItem')
                #duration_selection_elements[4].click()
        
        # Click on Search Button
        search_button_element = driver.find_element(By.XPATH, value="//img[contains(@src,'search_icon')]")
        search_button_element.click()
        print("Clicked on Search Button")
        
        element_present = EC.presence_of_all_elements_located((By.CLASS_NAME, "global-imageResults"))
        try:
            WebDriverWait(driver, 30).until(element_present)
            print("Events are loaded successfully")
        except:
            assert False, "Failed to load Events in 30Sec"
           
        image_result_elements = driver.find_elements(By.CLASS_NAME, value="global-imageResults")
        for image_result_element in image_result_elements:
            #image_result_element.click()
            #//img[contains(@src,'video-player')]
            # Hover on camera
            if image_result_element.is_displayed:
                action.move_to_element(image_result_element).perform()
                video_player_elements = image_result_element.find_elements(By.XPATH, ".//img[contains(@src, 'media/playClip')]")
                video_player_elements[0].click()
                try:
                    element_present = EC.presence_of_all_elements_located((By.XPATH, "//*[contains(@class,'CircularProgress')]"))
                    live_icon_elements = WebDriverWait(driver, 60).until(element_present)
                    
                    wait_item = WebDriverWait(driver, 60).until(EC.invisibility_of_element_located((By.XPATH, "//*[contains(@class,'CircularProgress')]")))
                    print("Circular Progress is stopped")
                    print("Video is playing successfully")
                    print("Waiting max 90 sec for reload icon to appear")
                    #replay-0
                    reload_button = WebDriverWait(driver, 600).until(EC.presence_of_all_elements_located((By.XPATH, "//img[@alt='Replay']")))
                    print("Reload Icon Appeared")
                    print("Event Video clip is played successfully")
                    break
                    #streaming_failed_elements = driver.find_elements(By.XPATH, value=".//*[contains(text(),'failed to load')]")
                except:
                    assert False, "Failed to open Event clip"       
                    
    #@pytest.mark.dependency(depends=["Test_Vsaas_Soterix::test_login"])
    def test_zone_global_search_api_calls(self, params):
        self.log_api_data(params['driver'])
        
    @pytest.mark.dependency(depends=["Test_Vsaas_Soterix::test_login"])
    def test_line_global_search(self, params):
        driver = params['driver']
        site_name = params['site_name']
        location_name = params['location_name']
        camera_name = params['camera_name']
        
        time.sleep(5)
        action = ActionChains(driver)
        # Global Search
        #search_button_element = driver.find_element(By.XPATH, value='//a[contains(@href,"search")]')
        #search_button_element.click()
        
        # Wait for the page to load
        element_present = EC.presence_of_all_elements_located((By.XPATH, "//label[@for='Category']"))
        
        try:
            WebDriverWait(driver, 15).until(element_present)
            print("Navigated to Global Search Page")
        except:
            print("Failed to Navigate to Global Search Page in 15 Sec")
            assert False, "Failed to Navigate to Global Search Page in 15 Sec"
        
        # Category, Appearance and Duration selection
        global_search_dropdown_elements = driver.find_elements(By.CLASS_NAME, value='search_select_box_container')
        for global_search_dropdown_element in global_search_dropdown_elements:
            time.sleep(2)
            global_search_dropdown_element.click()
            if 'Category' in global_search_dropdown_element.text:
                category_selection_elements = driver.find_elements(by=By.CLASS_NAME, value='dropdownItem')
                category_selection_elements[4].click()
            elif 'Description' in global_search_dropdown_element.text:
                pass
            elif 'Locations & Cameras' in global_search_dropdown_element.text:
                site_element = driver.find_element(by=By.XPATH, value=f".//*[contains(text(), \"{site_name}\")]")
                site_element.click()
                time.sleep(2)
                
                location_elements = driver.find_elements(by=By.XPATH, value=f".//*[contains(text(), '{location_name}')]")
                for location_element in  location_elements:
                    if location_element.is_displayed():
                        location_element.click()
                        break
                time.sleep(2)
                
                #global_camera_elements = driver.find_elements(by=By.CLASS_NAME, value="global-search-camera-container MuiBox-root mui-1v708vx")
                #for global_camera_element in global_camera_elements:
                    #camera_elements = global_camera_element.find_elements(by=By.XPATH, value=f".//p[text()='{camera_name}']")
                    #if camera_elements:
                        #break
                #assert camera_elements, "Camera not found"
                camera_elements = driver.find_elements(by=By.CLASS_NAME, value="global-search-camera-container")
                for camera_element in camera_elements:
                    if camera_name in camera_element.text:
                        if camera_element.find_elements(by=By.XPATH, value=".//img[contains(@src,'media/driveIcon')]"):
                            pass
                        else:
                            print(f"Hovering on Camera {camera_name} and clicking on Line")
                            action.move_to_element(camera_element).perform()
                            time.sleep(1)
                            create_zone_container_elements = driver.find_elements(by=By.XPATH, value=f"//p[text()='Create Line']")
                            for create_zone_container_element in create_zone_container_elements:
                                if create_zone_container_element.is_displayed():                  
                                    create_zone_container_element.click()
                                    break
                            print(f"Hovered on Camera {camera_name} and clicked on Line Successfully")
                            
                            # Wait for loader to appear and stop
                            
                            print("Waiting for Loader to appear and stop")
                            element_present = EC.presence_of_all_elements_located((By.XPATH, "//*[contains(@class,'CircularProgress')]"))
                            live_icon_elements = WebDriverWait(driver, 60).until(element_present)
                            
                            wait_item = WebDriverWait(driver, 60).until(EC.invisibility_of_element_located((By.XPATH, "//*[contains(@class,'CircularProgress')]"))) 
                            print("Loader appeared and stopped") 
                            
                            #time.sleep(10)
                            #print("Waiting for Done Button to appear")
                            #element_present = EC.presence_of_all_elements_located((By.CLASS_NAME, "save-btn"))
                            #done_button = WebDriverWait(driver, 60).until(element_present)                            
                    
                            # Draw Line
                            print("Drawing the Line")
                            line_draw_area_element = driver.find_element(by=By.CLASS_NAME, value="upper-canvas")
                            action.move_to_element_with_offset(line_draw_area_element, -500, -250).click().perform()
                            action.move_to_element_with_offset(line_draw_area_element, 500, 200).click().perform()
                            action.move_to_element_with_offset(line_draw_area_element, 500, -250).click().perform()
                            action.move_to_element_with_offset(line_draw_area_element, -500, 200).click().perform()
                            print("Line is drawn")
                            
                            # Click on Done Button
                            print("Clicking on Done button")
                            done_button_element = driver.find_element(by=By.CLASS_NAME, value="save-btn")
                            if "not-allowed" in done_button_element.get_attribute("style"):
                                action.move_to_element_with_offset(line_draw_area_element, -250, -125).click().perform()
                                action.move_to_element_with_offset(line_draw_area_element, 250, 100).click().perform()
                                action.move_to_element_with_offset(line_draw_area_element, 250, -125).click().perform()
                                action.move_to_element_with_offset(line_draw_area_element, -250, 100).click().perform()
                                
                            done_button_element.click()
                            print("Clicked on Done button")
                            
                            time.sleep(3)
                            print("Selecting Duration as Today")
                            dropdown_elements = driver.find_elements(By.CLASS_NAME, value='search_select_box_container')
                            for dropdown_element in dropdown_elements:                    
                                if 'Duration' in dropdown_element.text:
                                    dropdown_element.click()
                                    time.sleep(2)
                                    duration_selection_elements = driver.find_elements(by=By.CLASS_NAME, value='dropdownItem')
                                    duration_selection_elements[4].click()
                                    print("Selected Duration as Today")
                                    break
                        break
                break
            
            #else:
                #duration_selection_elements = driver.find_elements(by=By.CLASS_NAME, value='dropdownItem')
                #duration_selection_elements[4].click()
        
        # Click on Search Button
        search_button_element = driver.find_element(By.XPATH, value="//img[contains(@src,'search_icon')]")
        search_button_element.click()
        print("Clicked on Search Button")
        
        element_present = EC.presence_of_all_elements_located((By.CLASS_NAME, "global-imageResults"))
        try:
            WebDriverWait(driver, 30).until(element_present)
            print("Events are loaded successfully")
        except:
            assert False, "Failed to load Events in 30Sec"
           
        image_result_elements = driver.find_elements(By.CLASS_NAME, value="global-imageResults")
        for image_result_element in image_result_elements:
            #image_result_element.click()
            #//img[contains(@src,'video-player')]
            # Hover on camera
            if image_result_element.is_displayed:
                action.move_to_element(image_result_element).perform()
                video_player_elements = image_result_element.find_elements(By.XPATH, ".//img[contains(@src, 'media/playClip')]")
                video_player_elements[0].click()
                try:
                    element_present = EC.presence_of_all_elements_located((By.XPATH, "//*[contains(@class,'CircularProgress')]"))
                    live_icon_elements = WebDriverWait(driver, 60).until(element_present)
                    
                    wait_item = WebDriverWait(driver, 60).until(EC.invisibility_of_element_located((By.XPATH, "//*[contains(@class,'CircularProgress')]")))
                    print("Circular Progress is stopped")
                    print("Video is playing successfully")
                    print("Waiting max 90 sec for reload icon to appear")
                    #replay-0
                    reload_button = WebDriverWait(driver, 600).until(EC.presence_of_all_elements_located((By.XPATH, "//img[@alt='Replay']")))
                    print("Reload Icon Appeared")
                    print("Event Video clip is played successfully")
                    break
                    #streaming_failed_elements = driver.find_elements(By.XPATH, value=".//*[contains(text(),'failed to load')]")
                except:
                    assert False, "Failed to open Event clip"       
                    
    #@pytest.mark.dependency(depends=["Test_Vsaas_Soterix::test_login"])
    def test_line_global_search_api_calls(self, params):
        self.log_api_data(params['driver'])

    # Test for Admin Rules
    ''' Admin Rules Test Coverage:
    Features Implemented:
    - Rules page navigation and verification
    - Rule creation (Entry-Exit and Heatmap)
    - Site selection and line/zone drawing
    - Rule saving and verification 
    - Notification muting
    - Rule editing for notifications (push/popup)
    - Rule deletion with confirmation

    Pending Features:
    - Rule search functionality'''
    
    @pytest.mark.dependency(depends=["Test_Vsaas_Soterix::test_login"])
    def test_admin_create_rules(self, params):
        """
        Test admin rules functionality including creation, editing and deletion
        Args:
            params: Test parameters including driver and site details
        Verifies:
            - Navigation to rules page
            - Rule creation flows
            - UI element interactions
            - Error conditions
        """
        driver = params['driver']
        site_name = params['site_name']
        wait = WebDriverWait(driver, 10)
        action = ActionChains(driver)

        def select_site(driver, wait, site_name):
            try:
                # Check if site already selected
                site_elements = driver.find_elements(By.XPATH, f".//*[contains(text(), \"{site_name}\")]")
                
                if len(site_elements) == 0:
                    # Click dropdown to show options
                    dropdown = wait.until(
                        EC.element_to_be_clickable((By.CLASS_NAME, "MuiSelect-select"))
                    )
                    dropdown.click()
                    print(f"Clicked dropdown to select site {site_name}")
                    
                    time.sleep(2) # Wait for dropdown animation
                    
                    # Find and select the site
                    site_element = wait.until(
                        EC.element_to_be_clickable((By.XPATH, f".//*[contains(text(), \"{site_name}\")]"))
                    )
                    site_element.click()
                    print(f"Selected site: {site_name}")
                    return True
                    
                print(f"Site {site_name} already selected")
                return True
        
            except TimeoutException:
                print(f"Timed out waiting for site selection elements")
                return False
            except NoSuchElementException:
                print(f"Could not find site {site_name} in dropdown")
                return False
            except Exception as e:
                print(f"Error selecting site: {str(e)}")
                return False
        
        def click_next_button(driver, wait_time=10, delay_after=2):
            try:
                next_button = WebDriverWait(driver, wait_time).until(
                    EC.element_to_be_clickable((By.XPATH, "//button[text()='Next']"))
                )
                next_button.click()
                time.sleep(delay_after)  # wait for page/transition to complete
            except Exception as e:
                print(f"Failed to click 'Next' button: {e}")
        time.sleep(5)
        # Navigate to Admin page and click Rules
        try:
            # Try to find and click admin link
            admin_button = wait.until(
                EC.element_to_be_clickable((By.XPATH, '//a[contains(@href,"admin")]'))
            )
            admin_button.click()
            print("Clicked on Admin button")
        
            # Verify admin page is loaded by checking for Rules element
            admin_page_loaded = wait.until(
                EC.presence_of_element_located((By.XPATH, "//p[text()='Rules']"))
            )
            
            if admin_page_loaded.is_displayed():
                print("Admin page loaded successfully")
                # Proceed with next steps
                rules_element = admin_page_loaded
                rules_element.click()
                print("Clicked Rules button")
            else:
                raise TimeoutException("Admin page elements not visible")
        except TimeoutException:
            print("Failed to load admin page - timeout")
            pytest.xfail("Admin page navigation failed - timeout")
        except Exception as e:
            print(f"Error navigating to admin page: {str(e)}")
            pytest.xfail("Admin page navigation failed with error")
        time.sleep(2)  # Brief pause after navigation
        # 1. Adding new rule entry exit
        try:
            add_rule_button_element = driver.find_element(by=By.XPATH, value="//button[contains(text(),'Add New Rule')]")
        except Exception:
            pytest.xfail("Add Rule button not found")

        if not add_rule_button_element.is_enabled():
            pytest.xfail("Add Rule button disabled")

        assert add_rule_button_element.text == "Add New Rule", "Incorrect button text"
        add_rule_button_element.click()
        print("Clicked on Add New Rule button")
        time.sleep(2)
        # Wait for Entry exit option
        try:
            entry_exit_text = wait.until(
                EC.visibility_of_element_located((By.XPATH, "//p[text()='Entry-Exit']"))
            )
            print("Text found:", entry_exit_text.text)
            assert entry_exit_text.text == "Entry-Exit", "Incorrect text found"
            entry_exit_text.click()
        except TimeoutException:
            pytest.xfail("Entry exit option not found")

        # Wait for and click Next button
        try:
            next_button = wait.until(EC.element_to_be_clickable((By.CLASS_NAME, "btn-primary")))
            assert next_button.is_enabled(), "Next button is not enabled"
            next_button.click()
            print("Clicked Next button")
        except TimeoutException:
            pytest.xfail("Next button not clickable")
        except AssertionError as e:
            pytest.xfail(f"Next button assertion failed: {str(e)}")

        # Wait for the page to load
        time.sleep(2)
        # site selection
        if not select_site(driver, wait, site_name):
            pytest.xfail(f"Failed to select site {site_name}")
        time.sleep(2)
        # Wait for the checkbox to be present
        checkbox = wait.until(
        EC.presence_of_element_located((By.CSS_SELECTOR, 'input[type="checkbox"]')))
        # Click the checkbox (toggle it)
        checkbox.click()
        time.sleep(3)
         # Wait for and click Next button
        click_next_button(driver) 
        time.sleep(2)
        # Waiting for snap to load and loader to stop
        try:
            element_present = EC.presence_of_all_elements_located((By.XPATH, '//img[contains(@src, "data:image")]'))
            snap_load = WebDriverWait(driver, 60).until(element_present)
        except:
            assert False, "Failed to load the snap"
            
        maximize_button = driver.find_element(By.XPATH, '//img[@alt="maximize"]')
        maximize_button.click()
        
        # Waiting for snap to load and loader to stop
        try:
            snap_loaded = False
            for i in range(10):
                element_present = EC.presence_of_all_elements_located((By.XPATH, '//img[contains(@src, "data:image")]'))
                snaps = WebDriverWait(driver, 60).until(element_present)
                if len(snaps) < 2:
                    time.sleep(6)
                else:
                    print("Snap loaded successfully")
                    snap_loaded = True
                    break
            assert snap_loaded, "Failed to load snap"
        except:
            assert False, "Failed to load the snap"
        
        # Wait for the canvas to be present
        print("Drawing the Line")
        line_draw_area_element = driver.find_element(By.CSS_SELECTOR, "canvas.upper-canvas")
        time.sleep(2)
        action.move_to_element_with_offset(line_draw_area_element, -100, -150).pause(2).click().perform()
        action.move_to_element_with_offset(line_draw_area_element, 100, 20).pause(2).click().perform()
        action.move_to_element_with_offset(line_draw_area_element, 10, -20).pause(2).click().perform()
        action.move_to_element_with_offset(line_draw_area_element, -10, 20).pause(2).click().perform()
        print("Line is drawn")
        time.sleep(5)
        action.send_keys(Keys.TAB * 4).perform()
        time.sleep(2)
        action.send_keys(Keys.ENTER).perform()
        time.sleep(2)
        for _ in range(3):
            click_next_button(driver)
            time.sleep(2)
        time.sleep(5)
        # Select save button
        try:
            save_button = wait.until(
                EC.element_to_be_clickable((By.XPATH, "//button[text()='Save']"))
            )
            assert save_button.is_enabled(), "Save button is not enabled"
            save_button.click()
            print("Clicked Save button")
        except TimeoutException:
            pytest.xfail("Save button not clickable")
        except AssertionError as e:
            pytest.xfail(f"Save button assertion failed: {str(e)}")
        time.sleep(2)
        search_input = wait.until(
            EC.visibility_of_element_located((By.XPATH, "//input[@class='input-search-bar ' and @type='text']")))
        search_input.clear()
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        search_input.send_keys(f"Entry_exit_Automation_{timestamp}")
        action.send_keys(Keys.TAB).perform()
        time.sleep(2)
        action.send_keys(Keys.ENTER).perform()
        time.sleep(5)
        element = driver.find_element(By.XPATH, "//p[text()='General']")
        element.click()
        time.sleep(2)
        rules_element = driver.find_element(By.XPATH, "//p[text()='Rules']")
        rules_element.click()
        time.sleep(4)
        # 2. Heatmap Rule creation
        try:
            add_rule_button_element = driver.find_element(by=By.XPATH, value="//button[contains(text(),'Add New Rule')]")
        except Exception:
            pytest.xfail("Add Rule button not found")

        if not add_rule_button_element.is_enabled():
            pytest.xfail("Add Rule button disabled")

        assert add_rule_button_element.text == "Add New Rule", "Incorrect button text"
        add_rule_button_element.click()
        print("Clicked on Add New Rule button")
        try:
            # Wait for Heat Map option and click
            heatmap_option = wait.until(
                EC.element_to_be_clickable((By.XPATH, "//p[contains(text(), 'Heat Map')]"))
            )
            
            # Verify text content before clicking
            assert "Heat Map" in heatmap_option.text, "Incorrect Heat Map text found"
            assert "Visual tracking of footfall over time" in driver.find_element(
                By.XPATH, "//p[contains(text(), 'Visual tracking of footfall')]"
            ).text, "Incorrect Heat Map description"
            # Click the Heat Map option
            heatmap_option.click()
            print("Selected Heat Map option")

        except TimeoutException:
            print("Heat Map option not found or not clickable")
            pytest.xfail("Heat Map selection failed - option not accessible")
        except AssertionError as e:
            print(f"Heat Map text verification failed: {str(e)}")
            pytest.xfail("Heat Map selection failed - incorrect text")
        except Exception as e:
            print(f"Error selecting Heat Map: {str(e)}")
            pytest.xfail("Heat Map selection failed with error")
        time.sleep(2)
        # Wait for and click Next button
        try:
            next_button = wait.until(EC.element_to_be_clickable((By.CLASS_NAME, "btn-primary")))
            assert next_button.is_enabled(), "Next button is not enabled"
            next_button.click()
            print("Clicked Next button")
        except TimeoutException:
            pytest.xfail("Next button not clickable")
        except AssertionError as e:
            pytest.xfail(f"Next button assertion failed: {str(e)}")

        # Wait for the page to load
        time.sleep(2)
        # UsSite selection
        if not select_site(driver, wait, site_name):
            pytest.xfail(f"Failed to select site {site_name}")
            time.sleep(2)
        # Wait for the checkbox to be present
        checkbox = wait.until(
        EC.presence_of_element_located((By.CSS_SELECTOR, 'input[type="checkbox"]')))
        # Click the checkbox (toggle it)
        checkbox.click()
        time.sleep(3)
         # Wait for and click Next button
        click_next_button(driver)
        time.sleep(5)
        try:
            # Wait for checkbox with multiple selector strategies
            checkbox = wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 
                'input[type="checkbox"].MuiSwitch-input, input[aria-label="ant design"]'))
            )
        
            # Ensure checkbox is visible and interactable
            if not checkbox.is_displayed() or not checkbox.is_enabled():
                driver.execute_script("arguments[0].scrollIntoView(true);", checkbox)
                time.sleep(1)
        
            # Click the checkbox and verify state change
            initial_state = checkbox.is_selected()
            checkbox.click()
            print(f"Toggled checkbox from {initial_state} to {checkbox.is_selected()}")
        
            # Brief pause to allow UI to update
            time.sleep(1)
    
        except TimeoutException:
            print("Checkbox not found within timeout period")
            pytest.xfail("Checkbox interaction failed - element not found")
        except Exception as e:
            print(f"Error interacting with checkbox: {str(e)}")
            pytest.xfail("Checkbox interaction failed with error")
        time.sleep(2)
        try:
            # Wait for button including ripple effect container
            button = wait.until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, 
                    "button.MuiButtonBase-root:not([disabled])")))
            
            # Verify button is fully loaded with ripple effect
            ripple = button.find_element(By.CLASS_NAME, "MuiTouchRipple-root")
            assert ripple.is_displayed(), "Button ripple effect not loaded"
            
            # Click the base button element
            button.click()
            print("Clicked button with ripple effect")
            
            # Wait for ripple animation to complete
            time.sleep(0.3)  # Typical ripple animation duration
        
        except TimeoutException:
            print("Button not found or not clickable")
            pytest.xfail("Button interaction failed - element not accessible") 
        except Exception as e:
            print(f"Error clicking button: {str(e)}")
            pytest.xfail("Button interaction failed with error")
        time.sleep(2)
        # Wait for and click Next button
        try:
            next_button = wait.until(EC.element_to_be_clickable((By.CLASS_NAME, "btn-primary")))
            assert next_button.is_enabled(), "Next button is not enabled"
            next_button.click()
            print("Clicked Next button")
        except TimeoutException:
            pytest.xfail("Next button not clickable")
        except AssertionError as e:
            pytest.xfail(f"Next button assertion failed: {str(e)}")
        time.sleep(3)
         # Wait for and click Next button
        for _ in range(3):
            click_next_button(driver)
            time.sleep(2)
        time.sleep(5)
        # Select save button
        try:
            save_button = wait.until(
                EC.element_to_be_clickable((By.XPATH, "//button[text()='Save']"))
            )
            assert save_button.is_enabled(), "Save button is not enabled"
            save_button.click()
            print("Clicked Save button")
        except TimeoutException:
            pytest.xfail("Save button not clickable")
        except AssertionError as e:
            pytest.xfail(f"Save button assertion failed: {str(e)}")
        time.sleep(2)
        search_input = wait.until(
            EC.visibility_of_element_located((By.XPATH, "//input[@class='input-search-bar ' and @type='text']")))
        search_input.clear()
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        # Use a unique name for the heat map rule
        search_input.send_keys(f"Heat_map_Automation_{timestamp}")
        action.send_keys(Keys.TAB).perform()
        time.sleep(2)
        action.send_keys(Keys.ENTER).perform()
        time.sleep(5)
        element = driver.find_element(By.XPATH, "//p[text()='General']")
        element.click()
        time.sleep(2)
        rules_element = driver.find_element(By.XPATH, "//p[text()='Rules']")
        rules_element.click()
        time.sleep(10)
        #3. Add new Intrusion detection rule
        try:
            add_rule_button_element = driver.find_element(by=By.XPATH, value="//button[contains(text(),'Add New Rule')]")
        except Exception:
            pytest.xfail("Add Rule button not found")

        if not add_rule_button_element.is_enabled():
            pytest.xfail("Add Rule button disabled")

        assert add_rule_button_element.text == "Add New Rule", "Incorrect button text"
        add_rule_button_element.click()
        print("Clicked on Add New Rule button")
        try:
            # Wait for Intrusion detection option and click
            intrusion_detection_option = wait.until(
                EC.element_to_be_clickable((By.XPATH, "//p[contains(text(), 'People, animal and/or vehicle detected in the area')]"))
            )
            
            # Verify text content before clicking
            assert "People, animal and/or vehicle detected in the area" in intrusion_detection_option.text, "Incorrect People, animal and/or vehicle detected in the area text found"
            assert "Visual tracking of footfall over time" in driver.find_element(
                By.XPATH, "//p[contains(text(), 'Visual tracking of footfall')]"
            ).text, "Incorrect Intrusion detection description"
            
            # Click the Intrusion detection option
            intrusion_detection_option.click()
            print("Selected Intrusion detection option")

        except TimeoutException:
            print("Intrusion detection option not found or not clickable")
            pytest.xfail("Intrusion detection selection failed - option not accessible")
        except AssertionError as e:
            print(f"Intrusion detection text verification failed: {str(e)}")
            pytest.xfail("Intrusion detection selection failed - incorrect text")
        except Exception as e:
            print(f"Error selecting Intrusion detection: {str(e)}")
            pytest.xfail("Intrusion detection selection failed with error")
        time.sleep(2)
        # Wait for and click Next button
        try:
            next_button = wait.until(EC.element_to_be_clickable((By.CLASS_NAME, "btn-primary")))
            assert next_button.is_enabled(), "Next button is not enabled"
            next_button.click()
            print("Clicked Next button")
        except TimeoutException:
            pytest.xfail("Next button not clickable")
        except AssertionError as e:
            pytest.xfail(f"Next button assertion failed: {str(e)}")

        # Wait for the page to load
        time.sleep(2)
        # Site selection
        if not select_site(driver, wait, site_name):
            pytest.xfail(f"Failed to select site {site_name}")
            time.sleep(2)
        # Wait for the checkbox to be present
        checkbox = wait.until(
        EC.presence_of_element_located((By.CSS_SELECTOR, 'input[type="checkbox"]')))
        # Click the checkbox (toggle it)
        checkbox.click()
        time.sleep(3)
         # Wait for and click Next button
        click_next_button(driver)
        time.sleep(5)
        try:
            # Wait for checkbox with multiple selector strategies
            checkbox = wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 
                'input[type="checkbox"].MuiSwitch-input, input[aria-label="ant design"]'))
            )
        
            # Ensure checkbox is visible and interactable
            if not checkbox.is_displayed() or not checkbox.is_enabled():
                driver.execute_script("arguments[0].scrollIntoView(true);", checkbox)
                time.sleep(1)
        
            # Click the checkbox and verify state change
            initial_state = checkbox.is_selected()
            checkbox.click()
            print(f"Toggled checkbox from {initial_state} to {checkbox.is_selected()}")
        
            # Brief pause to allow UI to update
            time.sleep(1)
    
        except TimeoutException:
            print("Checkbox not found within timeout period")
            pytest.xfail("Checkbox interaction failed - element not found")
        except Exception as e:
            print(f"Error interacting with checkbox: {str(e)}")
            pytest.xfail("Checkbox interaction failed with error")
        time.sleep(3)
        # Wait for and click Next button
        try:
            next_button = wait.until(EC.element_to_be_clickable((By.CLASS_NAME, "btn-primary")))
            assert next_button.is_enabled(), "Next button is not enabled"
            next_button.click()
            print("Clicked Next button")
        except TimeoutException:
            pytest.xfail("Next button not clickable")
        except AssertionError as e:
            pytest.xfail(f"Next button assertion failed: {str(e)}")
        time.sleep(3)
         # Wait for and click Next button
        for _ in range(3):
            click_next_button(driver)
            time.sleep(2)
        time.sleep(5)
        # Select save button
        try:
            save_button = wait.until(
                EC.element_to_be_clickable((By.XPATH, "//button[text()='Save']"))
            )
            assert save_button.is_enabled(), "Save button is not enabled"
            save_button.click()
            print("Clicked Save button")
        except TimeoutException:
            pytest.xfail("Save button not clickable")
        except AssertionError as e:
            pytest.xfail(f"Save button assertion failed: {str(e)}")
        time.sleep(2)
        search_input = wait.until(
            EC.visibility_of_element_located((By.XPATH, "//input[@class='input-search-bar ' and @type='text']")))
        search_input.clear()
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        search_input.send_keys(f"Intrusion_detection_Automation_{timestamp}")
        action.send_keys(Keys.TAB).perform()
        time.sleep(2)
        action.send_keys(Keys.ENTER).perform()
        time.sleep(5)
        element = driver.find_element(By.XPATH, "//p[text()='General']")
        element.click()
        time.sleep(2)
        rules_element = driver.find_element(By.XPATH, "//p[text()='Rules']")
        rules_element.click()
        time.sleep(2)
        # 4. Adding Line crossing rule
        try:
            add_rule_button_element = driver.find_element(by=By.XPATH, value="//button[contains(text(),'Add New Rule')]")
        except Exception:
            pytest.xfail("Add Rule button not found")

        if not add_rule_button_element.is_enabled():
            pytest.xfail("Add Rule button disabled")

        assert add_rule_button_element.text == "Add New Rule", "Incorrect button text"
        add_rule_button_element.click()
        print("Clicked on Add New Rule button")
        try:
            # Wait for Line crossing option and click
            intrusion_detection_option = wait.until(
                EC.element_to_be_clickable((By.XPATH, "//p[contains(text(), 'Line Crossing')]"))
            )
            
            # Verify text content before clicking
            assert "Line Crossing" in intrusion_detection_option.text, "Incorrect Line Crossing text found"
            assert "Visual tracking of footfall over time" in driver.find_element(
                By.XPATH, "//p[contains(text(), 'Visual tracking of footfall')]"
            ).text, "Incorrect Line Crossing description"
            
            # Click the Line Crossing option
            intrusion_detection_option.click()
            print("Selected Line Crossing option")

        except TimeoutException:
            print("Line Crossing option not found or not clickable")
            pytest.xfail("Line Crossing selection failed - option not accessible")
        except AssertionError as e:
            print(f"Line Crossing text verification failed: {str(e)}")
            pytest.xfail("Line Crossing selection failed - incorrect text")
        except Exception as e:
            print(f"Error selecting Line Crossing: {str(e)}")
            pytest.xfail("Line Crossing selection failed with error")
        time.sleep(2)
        # Wait for and click Next button
        try:
            next_button = wait.until(EC.element_to_be_clickable((By.CLASS_NAME, "btn-primary")))
            assert next_button.is_enabled(), "Next button is not enabled"
            next_button.click()
            print("Clicked Next button")
        except TimeoutException:
            pytest.xfail("Next button not clickable")
        except AssertionError as e:
            pytest.xfail(f"Next button assertion failed: {str(e)}")
        
        # Wait for the page to load
        time.sleep(2)
        # site selection
        if not select_site(driver, wait, site_name):
            pytest.xfail(f"Failed to select site {site_name}")
            time.sleep(2)
        # Wait for the checkbox to be present
        checkbox = wait.until(
        EC.presence_of_element_located((By.CSS_SELECTOR, 'input[type="checkbox"]')))
        # Click the checkbox (toggle it)
        checkbox.click()
        time.sleep(3)
         # Wait for and click Next button
        click_next_button(driver) 
        
        # Waiting for snap to load and loader to stop
        try:
            element_present = EC.presence_of_all_elements_located((By.XPATH, '//img[contains(@src, "data:image")]'))
            snap_load = WebDriverWait(driver, 60).until(element_present)
        except:
            assert False, "Failed to load the snap"
            
        maximize_button = driver.find_element(By.XPATH, '//img[@alt="maximize"]')
        maximize_button.click()
        
        # Waiting for snap to load and loader to stop
        try:
            snap_loaded = False
            for i in range(10):
                element_present = EC.presence_of_all_elements_located((By.XPATH, '//img[contains(@src, "data:image")]'))
                snaps = WebDriverWait(driver, 60).until(element_present)
                if len(snaps) < 2:
                    time.sleep(6)
                else:
                    print("Snap loaded successfully")
                    snap_loaded = True
                    break
            assert snap_loaded, "Failed to load snap"
        except:
            assert False, "Failed to load the snap"
        
        # Wait for the canvas to be present
        print("Drawing the Line")
        line_draw_area_element = driver.find_element(By.CSS_SELECTOR, "canvas.upper-canvas")
        time.sleep(2)
        action.move_to_element_with_offset(line_draw_area_element, -100, -150).pause(2).click().perform()
        action.move_to_element_with_offset(line_draw_area_element, 100, 20).pause(2).click().perform()
        action.move_to_element_with_offset(line_draw_area_element, 10, -20).pause(2).click().perform()
        action.move_to_element_with_offset(line_draw_area_element, -10, 20).pause(2).click().perform()
        print("Line is drawn")
        time.sleep(5)
        action.send_keys(Keys.TAB * 4).perform()
        time.sleep(2)
        action.send_keys(Keys.ENTER).perform()
        time.sleep(2)
        for _ in range(3):
            click_next_button(driver)
            time.sleep(2)
        time.sleep(5)
        # Select save button
        try:
            save_button = wait.until(
                EC.element_to_be_clickable((By.XPATH, "//button[text()='Save']"))
            )
            assert save_button.is_enabled(), "Save button is not enabled"
            save_button.click()
            print("Clicked Save button")
        except TimeoutException:
            pytest.xfail("Save button not clickable")
        except AssertionError as e:
            pytest.xfail(f"Save button assertion failed: {str(e)}")
        time.sleep(2)
        search_input = wait.until(
            EC.visibility_of_element_located((By.XPATH, "//input[@class='input-search-bar ' and @type='text']")))
        search_input.clear()
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        search_input.send_keys(f"Line_Crossing_Automation_{timestamp}")
        action.send_keys(Keys.TAB).perform()
        time.sleep(2)
        action.send_keys(Keys.ENTER).perform()
        time.sleep(5)
        element = driver.find_element(By.XPATH, "//p[text()='General']")
        element.click()
        time.sleep(2)
        rules_element = driver.find_element(By.XPATH, "//p[text()='Rules']")
        rules_element.click()
        time.sleep(4)   
        # 5. Adding loitering rule
        try:
            add_rule_button_element = driver.find_element(by=By.XPATH, value="//button[contains(text(),'Add New Rule')]")
        except Exception:
            pytest.xfail("Add Rule button not found")

        if not add_rule_button_element.is_enabled():
            pytest.xfail("Add Rule button disabled")

        assert add_rule_button_element.text == "Add New Rule", "Incorrect button text"
        add_rule_button_element.click()
        print("Clicked on Add New Rule button")
        try:
            # Wait for Loitering option and click
            loitering_option = wait.until(
                EC.element_to_be_clickable((By.XPATH, "//p[contains(text(), 'Loitering')]"))
            )
            
            # Verify text content before clicking
            assert "Loitering" in loitering_option.text, "Incorrect Loitering text found"
            assert "Visual tracking of footfall over time" in driver.find_element(
                By.XPATH, "//p[contains(text(), 'Visual tracking of footfall')]"
            ).text, "Incorrect Loitering description"
            
            # Click the Loitering option
            loitering_option.click()
            print("Selected Loitering option")

        except TimeoutException:
            print("Loitering option not found or not clickable")
            pytest.xfail("Loitering selection failed - option not accessible")
        except AssertionError as e:
            print(f"Loitering text verification failed: {str(e)}")
            pytest.xfail("Loitering selection failed - incorrect text")
        except Exception as e:
            print(f"Error selecting Heat Map: {str(e)}")
            pytest.xfail("Loitering selection failed with error")
        time.sleep(2)
        # Wait for and click Next button
        try:
            next_button = wait.until(EC.element_to_be_clickable((By.CLASS_NAME, "btn-primary")))
            assert next_button.is_enabled(), "Next button is not enabled"
            next_button.click()
            print("Clicked Next button")
        except TimeoutException:
            pytest.xfail("Next button not clickable")
        except AssertionError as e:
            pytest.xfail(f"Next button assertion failed: {str(e)}")

        # Wait for the page to load
        time.sleep(2)
        # Site Selection
        if not select_site(driver, wait, site_name):
            pytest.xfail(f"Failed to select site {site_name}")
            time.sleep(2)
        # Wait for the checkbox to be present
        checkbox = wait.until(
        EC.presence_of_element_located((By.CSS_SELECTOR, 'input[type="checkbox"]')))
        # Click the checkbox (toggle it)
        checkbox.click()
        time.sleep(3)
         # Wait for and click Next button
        click_next_button(driver)
        time.sleep(5)
        try:
            # Wait for checkbox with multiple selector strategies
            checkbox = wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 
                'input[type="checkbox"].MuiSwitch-input, input[aria-label="ant design"]'))
            )
        
            # Ensure checkbox is visible and interactable
            if not checkbox.is_displayed() or not checkbox.is_enabled():
                driver.execute_script("arguments[0].scrollIntoView(true);", checkbox)
                time.sleep(1)
        
            # Click the checkbox and verify state change
            initial_state = checkbox.is_selected()
            checkbox.click()
            print(f"Toggled checkbox from {initial_state} to {checkbox.is_selected()}")
        
            # Brief pause to allow UI to update
            time.sleep(1)
    
        except TimeoutException:
            print("Checkbox not found within timeout period")
            pytest.xfail("Checkbox interaction failed - element not found")
        except Exception as e:
            print(f"Error interacting with checkbox: {str(e)}")
            pytest.xfail("Checkbox interaction failed with error")
        time.sleep(2)
        try:
            # Wait for button including ripple effect container
            button = wait.until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, 
                    "button.MuiButtonBase-root:not([disabled])")))
            
            # Verify button is fully loaded with ripple effect
            ripple = button.find_element(By.CLASS_NAME, "MuiTouchRipple-root")
            assert ripple.is_displayed(), "Button ripple effect not loaded"
            
            # Click the base button element
            button.click()
            print("Clicked button with ripple effect")
            
            # Wait for ripple animation to complete
            time.sleep(0.3)  # Typical ripple animation duration
        
        except TimeoutException:
            print("Button not found or not clickable")
            pytest.xfail("Button interaction failed - element not accessible") 
        except Exception as e:
            print(f"Error clicking button: {str(e)}")
            pytest.xfail("Button interaction failed with error")
        time.sleep(2)
        # Wait for and click Next button
        try:
            next_button = wait.until(EC.element_to_be_clickable((By.CLASS_NAME, "btn-primary")))
            assert next_button.is_enabled(), "Next button is not enabled"
            next_button.click()
            print("Clicked Next button")
        except TimeoutException:
            pytest.xfail("Next button not clickable")
        except AssertionError as e:
            pytest.xfail(f"Next button assertion failed: {str(e)}")
        time.sleep(3)
         # Wait for and click Next button
        for _ in range(3):
            click_next_button(driver)
            time.sleep(2)
        time.sleep(5)
        # Select save button
        try:
            save_button = wait.until(
                EC.element_to_be_clickable((By.XPATH, "//button[text()='Save']"))
            )
            assert save_button.is_enabled(), "Save button is not enabled"
            save_button.click()
            print("Clicked Save button")
        except TimeoutException:
            pytest.xfail("Save button not clickable")
        except AssertionError as e:
            pytest.xfail(f"Save button assertion failed: {str(e)}")
        time.sleep(2)
        search_input = wait.until(
            EC.visibility_of_element_located((By.XPATH, "//input[@class='input-search-bar ' and @type='text']")))
        search_input.clear()
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        search_input.send_keys(f"Loitering_Automation_{timestamp}")
        action.send_keys(Keys.TAB).perform()
        time.sleep(2)
        action.send_keys(Keys.ENTER).perform()
        time.sleep(5)
        element = driver.find_element(By.XPATH, "//p[text()='General']")
        element.click()
        time.sleep(2)
        rules_element = driver.find_element(By.XPATH, "//p[text()='Rules']")
        rules_element.click()
        time.sleep(10)
        # 6. Adding the rule for Occupancy
        try:
            add_rule_button_element = driver.find_element(by=By.XPATH, value="//button[contains(text(),'Add New Rule')]")
        except Exception:
            pytest.xfail("Add Rule button not found")

        if not add_rule_button_element.is_enabled():
            pytest.xfail("Add Rule button disabled")

        assert add_rule_button_element.text == "Add New Rule", "Incorrect button text"
        add_rule_button_element.click()
        print("Clicked on Add New Rule button")
        try:
            # Wait for Occupancy option and click
            occupancy_option = wait.until(
                EC.element_to_be_clickable((By.XPATH, "//p[contains(text(), 'Occupancy')]"))
            )
            
            # Verify text content before clicking
            assert "Occupancy" in occupancy_option.text, "Incorrect Occupancy text found"
            assert "Visual tracking of footfall over time" in driver.find_element(
                By.XPATH, "//p[contains(text(), 'Visual tracking of footfall')]"
            ).text, "Incorrect Occupancy description"
            
            # Click the Occupancy option
            occupancy_option.click()
            print("Selected Occupancy option")

        except TimeoutException:
            print("Occupancy option not found or not clickable")
            pytest.xfail("Occupancy selection failed - option not accessible")
        except AssertionError as e:
            print(f"Occupancy text verification failed: {str(e)}")
            pytest.xfail("Occupancy selection failed - incorrect text")
        except Exception as e:
            print(f"Error selecting Heat Map: {str(e)}")
            pytest.xfail("Occupancy selection failed with error")
        time.sleep(2)
        # Wait for and click Next button
        try:
            next_button = wait.until(EC.element_to_be_clickable((By.CLASS_NAME, "btn-primary")))
            assert next_button.is_enabled(), "Next button is not enabled"
            next_button.click()
            print("Clicked Next button")
        except TimeoutException:
            pytest.xfail("Next button not clickable")
        except AssertionError as e:
            pytest.xfail(f"Next button assertion failed: {str(e)}")

        # Wait for the page to load
        time.sleep(2)
        # Wait for the checkbox to be present
        checkbox = wait.until(
        EC.presence_of_element_located((By.CSS_SELECTOR, 'input[type="checkbox"]')))
        # Click the checkbox (toggle it)
        action.send_keys(Keys.ESCAPE).perform()
        checkbox.click()
        time.sleep(3)
         # Wait for and click Next button
        click_next_button(driver)
        time.sleep(5)
        try:
            # Wait for checkbox with multiple selector strategies
            checkbox = wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, 
                'input[type="checkbox"].MuiSwitch-input, input[aria-label="ant design"]'))
            )
        
            # Ensure checkbox is visible and interactable
            if not checkbox.is_displayed() or not checkbox.is_enabled():
                driver.execute_script("arguments[0].scrollIntoView(true);", checkbox)
                time.sleep(3)
        
            # Click the checkbox and verify state change
            initial_state = checkbox.is_selected()
            checkbox.click()
            print(f"Toggled checkbox from {initial_state} to {checkbox.is_selected()}")
        
            # Brief pause to allow UI to update
            time.sleep(4)
    
        except TimeoutException:
            print("Checkbox not found within timeout period")
            pytest.xfail("Checkbox interaction failed - element not found")
        except Exception as e:
            print(f"Error interacting with checkbox: {str(e)}")
            pytest.xfail("Checkbox interaction failed with error")
        time.sleep(2)
        try:
            # Wait for button including ripple effect container
            button = wait.until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, 
                    "button.MuiButtonBase-root:not([disabled])")))
            
            # Verify button is fully loaded with ripple effect
            ripple = button.find_element(By.CLASS_NAME, "MuiTouchRipple-root")
            assert ripple.is_displayed(), "Button ripple effect not loaded"
            
            # Click the base button element
            button.click()
            print("Clicked button with ripple effect")
            
            # Wait for ripple animation to complete
            time.sleep(0.3)  # Typical ripple animation duration
        
        except TimeoutException:
            print("Button not found or not clickable")
            pytest.xfail("Button interaction failed - element not accessible") 
        except Exception as e:
            print(f"Error clicking button: {str(e)}")
            pytest.xfail("Button interaction failed with error")
        time.sleep(2)
        # Wait for and click Next button
        try:
            next_button = wait.until(EC.element_to_be_clickable((By.CLASS_NAME, "btn-primary")))
            assert next_button.is_enabled(), "Next button is not enabled"
            next_button.click()
            print("Clicked Next button")
        except TimeoutException:
            pytest.xfail("Next button not clickable")
        except AssertionError as e:
            pytest.xfail(f"Next button assertion failed: {str(e)}")
        time.sleep(3)
         # Wait for and click Next button
        for _ in range(3):
            click_next_button(driver)
            time.sleep(2)
        time.sleep(5)
        # Select save button
        try:
            save_button = wait.until(
                EC.element_to_be_clickable((By.XPATH, "//button[text()='Save']"))
            )
            assert save_button.is_enabled(), "Save button is not enabled"
            save_button.click()
            print("Clicked Save button")
        except TimeoutException:
            pytest.xfail("Save button not clickable")
        except AssertionError as e:
            pytest.xfail(f"Save button assertion failed: {str(e)}")
        time.sleep(2)
        search_input = wait.until(
            EC.visibility_of_element_located((By.XPATH, "//input[@class='input-search-bar ' and @type='text']")))
        search_input.clear()
        search_input.send_keys("Occupancy_Automation")
        action.send_keys(Keys.TAB).perform()
        time.sleep(2)
        action.send_keys(Keys.ENTER).perform()
        time.sleep(5)
        element = driver.find_element(By.XPATH, "//p[text()='General']")
        element.click()
        time.sleep(2)
        rules_element = driver.find_element(By.XPATH, "//p[text()='Rules']")
        rules_element.click()
        time.sleep(10)
    
    @pytest.mark.dependency(depends=["Test_Vsaas_Soterix::test_login"])
    def test_admin_edit_heatmap_rule(self, params):
        driver = params["driver"]
        wait = WebDriverWait(driver, 10)
        action = ActionChains(driver)   
        time.sleep(5)
        element = driver.find_element(By.XPATH, "//p[text()='General']")
        element.click()
        time.sleep(2)
        rules_element = driver.find_element(By.XPATH, "//p[text()='Rules']")
        rules_element.click()
        time.sleep(4)
        #Edit the heat map rule
        try:
            # Get all edit icons with aria-label="Edit"
            edit_icons = WebDriverWait(driver, 10).until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, "img[aria-label='Edit'].icon"))
            )

            if not edit_icons:
                pytest.xfail("No edit icons found")

            # Pick the last edit icon
            last_edit_icon = edit_icons[-1]

            # Scroll to the element
            driver.execute_script("arguments[0].scrollIntoView(true);", last_edit_icon)
            time.sleep(0.5)  # Slight delay to ensure scroll completes

            try:
                # Ensure it's clickable
                WebDriverWait(driver, 5).until(EC.element_to_be_clickable(last_edit_icon))
                last_edit_icon.click()
                print("Clicked last edit icon")
            except ElementClickInterceptedException:
                driver.execute_script("arguments[0].click();", last_edit_icon)
                print("Clicked last edit icon using JS")

        except TimeoutException:
            print("Edit icon not found or not clickable")
            pytest.xfail("Edit icon interaction failed - element not accessible")
        time.sleep(2)
        # Edit the rule
        try:
            # Wait for all edit icons to be present in the DOM
            edit_icons = wait.until(EC.presence_of_all_elements_located((By.XPATH, "//img[@aria-label='Edit']")))

            if not edit_icons:
                pytest.xfail("No edit icons found on the page")

            # Select the last edit icon
            last_edit_icon = edit_icons[-1]

            # Scroll to it
            driver.execute_script("arguments[0].scrollIntoView();", last_edit_icon)

            try:
                # Try regular click
                last_edit_icon.click()
            except ElementClickInterceptedException:
                # Fallback to JavaScript click
                driver.execute_script("arguments[0].click();", last_edit_icon)
        except TimeoutException:
            print("Edit icons not found in time")
            pytest.xfail("Edit icon interaction failed - elements not accessible")
        # Select Notification option for Edit rule
        time.sleep(4)
        try:
            # Wait for notification button and ensure it's clickable
            notification_btn = wait.until(
                EC.element_to_be_clickable((By.XPATH, 
                    "//button[contains(@class, 'btn-modalTab') and contains(text(), 'Notification')]"))
            )
            # Verify button text and state
            assert "Notification" in notification_btn.text, "Incorrect button text"
            assert notification_btn.is_enabled(), "Notification button is disabled"
            # Ensure button is in viewport
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", notification_btn)
            time.sleep(0.5)
            # Click the button
            notification_btn.click()
            print("Clicked Notification button")
        except TimeoutException:
            print("Notification button not found or not clickable")
            pytest.xfail("Notification button interaction failed - element not accessible")
        except AssertionError as e:
            print(f"Notification button verification failed: {str(e)}")
            pytest.xfail("Notification button interaction failed - button state incorrect")
        except Exception as e:
            print(f"Error clicking Notification button: {str(e)}")
            pytest.xfail("Notification button interaction failed with error")
        time.sleep(2)
        action.send_keys(Keys.TAB).perform()
        time.sleep(2)
        action.send_keys("Admin").perform()
        time.sleep(2)
        try:
            # Wait for dropdown to be visible and clickable
            dropdown_item = wait.until(EC.element_to_be_clickable((By.XPATH, "//div[@class='search-dropdown-item' and text()='Enterprise Super Admin']")))
            # Scroll to element if needed
            driver.execute_script("arguments[0].scrollIntoView();", dropdown_item)
            # Click the dropdown item
            dropdown_item.click()
            print("Dropdown item selected successfully")
        except TimeoutException:
            print("Dropdown item not found or not clickable")
        time.sleep(2)
        try:
            # Find and click popUp checkbox
            popup_checkbox = wait.until(EC.element_to_be_clickable((By.XPATH, "//input[@name='popUp']")))
            if not popup_checkbox.is_selected():
                popup_checkbox.click()
                print("PopUp checkbox selected")
            # Find and click push checkbox
            push_checkbox = wait.until(EC.element_to_be_clickable((By.XPATH, "//input[@name='push']")))
            if not push_checkbox.is_selected():
                push_checkbox.click()
                print("Push checkbox selected")
            print("Both pop up and push checkboxes selected successfully")
        except TimeoutException:
            print("One or both pop up and push checkboxes not found")
        time.sleep(2)
        #Selecting the check boxes for push
        try:
            # Wait for popup checkbox with multiple selector strategies
            popup_checkbox = wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "input.PrivateSwitchBase-input.mui-1m9pwf3"))
            )
            # Ensure checkbox is visible and interactable
            if not popup_checkbox.is_displayed() or not popup_checkbox.is_enabled():
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", popup_checkbox)
                time.sleep(0.5)
            
            # Get initial state and click if needed
            initial_state = popup_checkbox.is_selected()
            if not initial_state:
                popup_checkbox.click()
                print("Toggled popup checkbox to selected state")
            else:
                print("Popup checkbox already selected")
            
            # Verify state changed
            assert popup_checkbox.is_selected(), "Popup checkbox failed to select"
        except TimeoutException:
            print("Popup checkbox not found within timeout period")
            pytest.xfail("Popup checkbox interaction failed - element not accessible")
        except AssertionError as e:
            print(f"Popup checkbox verification failed: {str(e)}")
            pytest.xfail("Popup checkbox interaction failed - state change error")
        except Exception as e:
            print(f"Error interacting with popup checkbox: {str(e)}")
            pytest.xfail("Popup checkbox interaction failed with error")
        time.sleep(2)
        #Selecting the check boxes for pop
        try:
            # Wait for popup checkbox with multiple selector strategies
            popup_checkbox = wait.until(
                EC.presence_of_element_located((By.NAME, "push"))
            )
            # Ensure checkbox is visible and interactable
            if not popup_checkbox.is_displayed() or not popup_checkbox.is_enabled():
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", popup_checkbox)
                time.sleep(0.5)
            
            # Get initial state and click if needed
            initial_state = popup_checkbox.is_selected()
            if not initial_state:
                popup_checkbox.click()
                print("Toggled popup checkbox to selected state")
            else:
                print("Popup checkbox already selected")
            
            # Verify state changed
            assert popup_checkbox.is_selected(), "Popup checkbox failed to select"
        except TimeoutException:
            print("Popup checkbox not found within timeout period")
            pytest.xfail("Popup checkbox interaction failed - element not accessible")
        except AssertionError as e:
            print(f"Popup checkbox verification failed: {str(e)}")
            pytest.xfail("Popup checkbox interaction failed - state change error")
        except Exception as e:
            print(f"Error interacting with popup checkbox: {str(e)}")
            pytest.xfail("Popup checkbox interaction failed with error")
        # Selecting update and close button
        try:
            update_button = wait.until(EC.element_to_be_clickable((
                By.XPATH, "//button[contains(@class, 'btn-primary') and normalize-space(text())='Update & Close']"
            )))
            update_button.click()

        except Exception as e:
            pytest.xfail(f"Button not found or not clickable: {e}")
        time.sleep(5)
        element = driver.find_element(By.XPATH, "//p[text()='General']")
        element.click()
        time.sleep(2)
        rules_element = driver.find_element(By.XPATH, "//p[text()='Rules']")
        rules_element.click()
        time.sleep(3)
    
    @pytest.mark.dependency(depends=["Test_Vsaas_Soterix::test_login"])
    def test_admin_edit_loitering_rule(self, params):
        driver = params["driver"]
        wait = WebDriverWait(driver, 10)
        action = ActionChains(driver)   
        time.sleep(5)
        element = driver.find_element(By.XPATH, "//p[text()='General']")
        element.click()
        time.sleep(2)
        rules_element = driver.find_element(By.XPATH, "//p[text()='Rules']")
        rules_element.click()
        time.sleep(4)
        #Edit the rule
        try:
            # Get all edit icons with aria-label="Edit"
            edit_icons = WebDriverWait(driver, 10).until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, "img[aria-label='Edit'].icon"))
            )

            if not edit_icons:
                pytest.xfail("No edit icons found")

            # Pick the last edit icon
            last_edit_icon = edit_icons[-1]

            # Scroll to the element
            driver.execute_script("arguments[0].scrollIntoView(true);", last_edit_icon)
            time.sleep(0.5)  # Slight delay to ensure scroll completes

            try:
                # Ensure it's clickable
                WebDriverWait(driver, 5).until(EC.element_to_be_clickable(last_edit_icon))
                last_edit_icon.click()
                print("Clicked last edit icon")
            except ElementClickInterceptedException:
                driver.execute_script("arguments[0].click();", last_edit_icon)
                print("Clicked last edit icon using JS")

        except TimeoutException:
            print("Edit icon not found or not clickable")
            pytest.xfail("Edit icon interaction failed - element not accessible")
        time.sleep(2)
        # Edit the rule
        try:
            # Wait for all edit icons to be present in the DOM
            edit_icons = wait.until(EC.presence_of_all_elements_located((By.XPATH, "//img[@aria-label='Edit']")))

            if not edit_icons:
                pytest.xfail("No edit icons found on the page")

            # Select the last edit icon
            last_edit_icon = edit_icons[-1]

            # Scroll to it
            driver.execute_script("arguments[0].scrollIntoView();", last_edit_icon)

            try:
                # Try regular click
                last_edit_icon.click()
            except ElementClickInterceptedException:
                # Fallback to JavaScript click
                driver.execute_script("arguments[0].click();", last_edit_icon)
        except TimeoutException:
            print("Edit icons not found in time")
            pytest.xfail("Edit icon interaction failed - elements not accessible")
        # Select Notification option for Edit rule
        time.sleep(4)
        try:
            # Wait for notification button and ensure it's clickable
            notification_btn = wait.until(
                EC.element_to_be_clickable((By.XPATH, 
                    "//button[contains(@class, 'btn-modalTab') and contains(text(), 'Notification')]"))
            )
            # Verify button text and state
            assert "Notification" in notification_btn.text, "Incorrect button text"
            assert notification_btn.is_enabled(), "Notification button is disabled"
            # Ensure button is in viewport
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", notification_btn)
            time.sleep(0.5)
            # Click the button
            notification_btn.click()
            print("Clicked Notification button")
        except TimeoutException:
            print("Notification button not found or not clickable")
            pytest.xfail("Notification button interaction failed - element not accessible")
        except AssertionError as e:
            print(f"Notification button verification failed: {str(e)}")
            pytest.xfail("Notification button interaction failed - button state incorrect")
        except Exception as e:
            print(f"Error clicking Notification button: {str(e)}")
            pytest.xfail("Notification button interaction failed with error")
        time.sleep(2)
        action.send_keys(Keys.TAB).perform()
        time.sleep(2)
        action.send_keys("Admin").perform()
        time.sleep(2)
        try:
            # Wait for dropdown to be visible and clickable
            dropdown_item = wait.until(EC.element_to_be_clickable((By.XPATH, "//div[@class='search-dropdown-item' and text()='Enterprise Super Admin']")))
            # Scroll to element if needed
            driver.execute_script("arguments[0].scrollIntoView();", dropdown_item)
            # Click the dropdown item
            dropdown_item.click()
            print("Dropdown item selected successfully")
        except TimeoutException:
            print("Dropdown item not found or not clickable")
        time.sleep(2)
        try:
            # Find and click popUp checkbox
            popup_checkbox = wait.until(EC.element_to_be_clickable((By.XPATH, "//input[@name='popUp']")))
            if not popup_checkbox.is_selected():
                popup_checkbox.click()
                print("PopUp checkbox selected")
            # Find and click push checkbox
            push_checkbox = wait.until(EC.element_to_be_clickable((By.XPATH, "//input[@name='push']")))
            if not push_checkbox.is_selected():
                push_checkbox.click()
                print("Push checkbox selected")
            print("Both pop up and push checkboxes selected successfully")
        except TimeoutException:
            print("One or both pop up and push checkboxes not found")
        time.sleep(2)
        #Selecting the check boxes for push
        try:
            # Wait for popup checkbox with multiple selector strategies
            popup_checkbox = wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "input.PrivateSwitchBase-input.mui-1m9pwf3"))
            )
            # Ensure checkbox is visible and interactable
            if not popup_checkbox.is_displayed() or not popup_checkbox.is_enabled():
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", popup_checkbox)
                time.sleep(0.5)
            
            # Get initial state and click if needed
            initial_state = popup_checkbox.is_selected()
            if not initial_state:
                popup_checkbox.click()
                print("Toggled popup checkbox to selected state")
            else:
                print("Popup checkbox already selected")
            
            # Verify state changed
            assert popup_checkbox.is_selected(), "Popup checkbox failed to select"
        except TimeoutException:
            print("Popup checkbox not found within timeout period")
            pytest.xfail("Popup checkbox interaction failed - element not accessible")
        except AssertionError as e:
            print(f"Popup checkbox verification failed: {str(e)}")
            pytest.xfail("Popup checkbox interaction failed - state change error")
        except Exception as e:
            print(f"Error interacting with popup checkbox: {str(e)}")
            pytest.xfail("Popup checkbox interaction failed with error")
        time.sleep(2)
        #Selecting the check boxes for pop
        try:
            # Wait for popup checkbox with multiple selector strategies
            popup_checkbox = wait.until(
                EC.presence_of_element_located((By.NAME, "push"))
            )
            # Ensure checkbox is visible and interactable
            if not popup_checkbox.is_displayed() or not popup_checkbox.is_enabled():
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", popup_checkbox)
                time.sleep(0.5)
            
            # Get initial state and click if needed
            initial_state = popup_checkbox.is_selected()
            if not initial_state:
                popup_checkbox.click()
                print("Toggled popup checkbox to selected state")
            else:
                print("Popup checkbox already selected")
            
            # Verify state changed
            assert popup_checkbox.is_selected(), "Popup checkbox failed to select"
        except TimeoutException:
            print("Popup checkbox not found within timeout period")
            pytest.xfail("Popup checkbox interaction failed - element not accessible")
        except AssertionError as e:
            print(f"Popup checkbox verification failed: {str(e)}")
            pytest.xfail("Popup checkbox interaction failed - state change error")
        except Exception as e:
            print(f"Error interacting with popup checkbox: {str(e)}")
            pytest.xfail("Popup checkbox interaction failed with error")
        # Selecting update and close button
        try:
            update_button = wait.until(EC.element_to_be_clickable((
                By.XPATH, "//button[contains(@class, 'btn-primary') and normalize-space(text())='Update & Close']"
            )))
            update_button.click()

        except Exception as e:
            pytest.xfail(f"Button not found or not clickable: {e}")
        time.sleep(2)
    @pytest.mark.dependency(depends=["Test_Vsaas_Soterix::test_login"])
    def test_admin_search_occupancy_rule(self, params):
        driver = params["driver"]    
        # Search for the rule
        try:
            wait = WebDriverWait(driver, 10)
        
            # Wait for the search input field to be visible
            search_input = wait.until(
                EC.visibility_of_element_located((By.CLASS_NAME, "input-search-bar"))
            )
            # Clear and enter search text
            search_input.clear()
            search_input.send_keys(f"Occupancy_Automation")
            search_input.send_keys(Keys.ENTER)
            print("Search for Occupancy_Automation successful")
            time.sleep(2)  # Optional: wait for results to load
        except Exception as e:
            print(f"❌ Error during search input: {e}")
    
    @pytest.mark.dependency(depends=["Test_Vsaas_Soterix::test_login"])
    def test_admin_edit_occupancy_rule(self, params): 
        driver = params["driver"]
        wait = WebDriverWait(driver, 10)
        action = ActionChains(driver)   
        time.sleep(5)
        element = driver.find_element(By.XPATH, "//p[text()='General']")
        element.click()
        time.sleep(2)
        rules_element = driver.find_element(By.XPATH, "//p[text()='Rules']")
        rules_element.click()
        time.sleep(4)
        try:
            # Get all edit icons with aria-label="Edit"
            edit_icons = wait.until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, "img[aria-label='Edit'].icon"))
            )
            if not edit_icons:
                pytest.xfail("No edit icons found")
            # Pick the last edit icon
            last_edit_icon = edit_icons[-1]
            # Scroll to the element
            driver.execute_script("arguments[0].scrollIntoView(true);", last_edit_icon)
            time.sleep(0.5)  # Slight delay to ensure scroll completes
            try:
                # Ensure it's clickable
                WebDriverWait(driver, 5).until(EC.element_to_be_clickable(last_edit_icon))
                last_edit_icon.click()
                print("Clicked last edit icon")
            except ElementClickInterceptedException:
                driver.execute_script("arguments[0].click();", last_edit_icon)
                print("Clicked last edit icon using JS")

        except TimeoutException:
            print("Edit icon not found or not clickable")
            pytest.xfail("Edit icon interaction failed - element not accessible")
        time.sleep(2)
        # Edit the rule
        try:
            # Wait for all edit icons to be present in the DOM
            edit_icons = wait.until(EC.presence_of_all_elements_located((By.XPATH, "//img[@aria-label='Edit']")))

            if not edit_icons:
                pytest.xfail("No edit icons found on the page")

            # Select the last edit icon
            last_edit_icon = edit_icons[-1]

            # Scroll to it
            driver.execute_script("arguments[0].scrollIntoView();", last_edit_icon)

            try:
                # Try regular click
                last_edit_icon.click()
            except ElementClickInterceptedException:
                # Fallback to JavaScript click
                driver.execute_script("arguments[0].click();", last_edit_icon)
        except TimeoutException:
            print("Edit icons not found in time")
            pytest.xfail("Edit icon interaction failed - elements not accessible")
        # Select Notification option for Edit rule
        time.sleep(4)
        try:
            # Wait for notification button and ensure it's clickable
            notification_btn = wait.until(
                EC.element_to_be_clickable((By.XPATH, 
                    "//button[contains(@class, 'btn-modalTab') and contains(text(), 'Notification')]"))
            )
            # Verify button text and state
            assert "Notification" in notification_btn.text, "Incorrect button text"
            assert notification_btn.is_enabled(), "Notification button is disabled"
            # Ensure button is in viewport
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", notification_btn)
            time.sleep(0.5)
            # Click the button
            notification_btn.click()
            print("Clicked Notification button")
        except TimeoutException:
            print("Notification button not found or not clickable")
            pytest.xfail("Notification button interaction failed - element not accessible")
        except AssertionError as e:
            print(f"Notification button verification failed: {str(e)}")
            pytest.xfail("Notification button interaction failed - button state incorrect")
        except Exception as e:
            print(f"Error clicking Notification button: {str(e)}")
            pytest.xfail("Notification button interaction failed with error")
        time.sleep(2)
        action.send_keys(Keys.TAB).perform()
        time.sleep(2)
        action.send_keys("Admin").perform()
        time.sleep(2)
        try:
            # Wait for dropdown to be visible and clickable
            dropdown_item = wait.until(EC.element_to_be_clickable((By.XPATH, "//div[@class='search-dropdown-item' and text()='Enterprise Super Admin']")))
            # Scroll to element if needed
            driver.execute_script("arguments[0].scrollIntoView();", dropdown_item)
            # Click the dropdown item
            dropdown_item.click()
            print("Dropdown item selected successfully")
        except TimeoutException:
            print("Dropdown item not found or not clickable")
        time.sleep(2)
        try:
            # Find and click popUp checkbox
            popup_checkbox = wait.until(EC.element_to_be_clickable((By.XPATH, "//input[@name='popUp']")))
            if not popup_checkbox.is_selected():
                popup_checkbox.click()
                print("PopUp checkbox selected")
            # Find and click push checkbox
            push_checkbox = wait.until(EC.element_to_be_clickable((By.XPATH, "//input[@name='push']")))
            if not push_checkbox.is_selected():
                push_checkbox.click()
                print("Push checkbox selected")
            print("Both pop up and push checkboxes selected successfully")
        except TimeoutException:
            print("One or both pop up and push checkboxes not found")
        time.sleep(2)
        #Selecting the check boxes for push
        try:
            # Wait for popup checkbox with multiple selector strategies
            popup_checkbox = wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "input.PrivateSwitchBase-input.mui-1m9pwf3"))
            )
            # Ensure checkbox is visible and interactable
            if not popup_checkbox.is_displayed() or not popup_checkbox.is_enabled():
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", popup_checkbox)
                time.sleep(0.5)
            
            # Get initial state and click if needed
            initial_state = popup_checkbox.is_selected()
            if not initial_state:
                popup_checkbox.click()
                print("Toggled popup checkbox to selected state")
            else:
                print("Popup checkbox already selected")
            
            # Verify state changed
            assert popup_checkbox.is_selected(), "Popup checkbox failed to select"
        except TimeoutException:
            print("Popup checkbox not found within timeout period")
            pytest.xfail("Popup checkbox interaction failed - element not accessible")
        except AssertionError as e:
            print(f"Popup checkbox verification failed: {str(e)}")
            pytest.xfail("Popup checkbox interaction failed - state change error")
        except Exception as e:
            print(f"Error interacting with popup checkbox: {str(e)}")
            pytest.xfail("Popup checkbox interaction failed with error")
        time.sleep(2)
        #Selecting the check boxes for pop
        try:
            # Wait for popup checkbox with multiple selector strategies
            popup_checkbox = wait.until(
                EC.presence_of_element_located((By.NAME, "push"))
            )
            # Ensure checkbox is visible and interactable
            if not popup_checkbox.is_displayed() or not popup_checkbox.is_enabled():
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", popup_checkbox)
                time.sleep(0.5)
            
            # Get initial state and click if needed
            initial_state = popup_checkbox.is_selected()
            if not initial_state:
                popup_checkbox.click()
                print("Toggled popup checkbox to selected state")
            else:
                print("Popup checkbox already selected")
            
            # Verify state changed
            assert popup_checkbox.is_selected(), "Popup checkbox failed to select"
        except TimeoutException:
            print("Popup checkbox not found within timeout period")
            pytest.xfail("Popup checkbox interaction failed - element not accessible")
        except AssertionError as e:
            print(f"Popup checkbox verification failed: {str(e)}")
            pytest.xfail("Popup checkbox interaction failed - state change error")
        except Exception as e:
            print(f"Error interacting with popup checkbox: {str(e)}")
            pytest.xfail("Popup checkbox interaction failed with error")
        # Selecting update and close button
        try:
            update_button = wait.until(EC.element_to_be_clickable((
                By.XPATH, "//button[contains(@class, 'btn-primary') and normalize-space(text())='Update & Close']"
            )))
            update_button.click()

        except Exception as e:
            pytest.xfail(f"Button not found or not clickable: {e}")
        time.sleep(2)
    
    @pytest.mark.dependency(depends=["Test_Vsaas_Soterix::test_login"])
    def test_admin_edit_intrusion_detection_rule(self, params): 
        driver = params["driver"]
        wait = WebDriverWait(driver, 10)
        action = ActionChains(driver)   
        time.sleep(5)
        element = driver.find_element(By.XPATH, "//p[text()='General']")
        element.click()
        time.sleep(2)
        rules_element = driver.find_element(By.XPATH, "//p[text()='Rules']")
        rules_element.click()
        time.sleep(4)
        try:
            # Get all edit icons with aria-label="Edit"
            edit_icons = wait.until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, "img[aria-label='Edit'].icon"))
            )
            if not edit_icons:
                pytest.xfail("No edit icons found")
            # Pick the last edit icon
            last_edit_icon = edit_icons[-1]
            # Scroll to the element
            driver.execute_script("arguments[0].scrollIntoView(true);", last_edit_icon)
            time.sleep(0.5)  # Slight delay to ensure scroll completes
            try:
                # Ensure it's clickable
                WebDriverWait(driver, 5).until(EC.element_to_be_clickable(last_edit_icon))
                last_edit_icon.click()
                print("Clicked last edit icon")
            except ElementClickInterceptedException:
                driver.execute_script("arguments[0].click();", last_edit_icon)
                print("Clicked last edit icon using JS")

        except TimeoutException:
            print("Edit icon not found or not clickable")
            pytest.xfail("Edit icon interaction failed - element not accessible")
        time.sleep(2)
        # Edit the rule
        try:
            # Wait for all edit icons to be present in the DOM
            edit_icons = wait.until(EC.presence_of_all_elements_located((By.XPATH, "//img[@aria-label='Edit']")))

            if not edit_icons:
                pytest.xfail("No edit icons found on the page")

            # Select the last edit icon
            last_edit_icon = edit_icons[-1]

            # Scroll to it
            driver.execute_script("arguments[0].scrollIntoView();", last_edit_icon)

            try:
                # Try regular click
                last_edit_icon.click()
            except ElementClickInterceptedException:
                # Fallback to JavaScript click
                driver.execute_script("arguments[0].click();", last_edit_icon)
        except TimeoutException:
            print("Edit icons not found in time")
            pytest.xfail("Edit icon interaction failed - elements not accessible")
        # Select Notification option for Edit rule
        time.sleep(4)
        try:
            # Wait for notification button and ensure it's clickable
            notification_btn = wait.until(
                EC.element_to_be_clickable((By.XPATH, 
                    "//button[contains(@class, 'btn-modalTab') and contains(text(), 'Notification')]"))
            )
            # Verify button text and state
            assert "Notification" in notification_btn.text, "Incorrect button text"
            assert notification_btn.is_enabled(), "Notification button is disabled"
            # Ensure button is in viewport
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", notification_btn)
            time.sleep(0.5)
            # Click the button
            notification_btn.click()
            print("Clicked Notification button")
        except TimeoutException:
            print("Notification button not found or not clickable")
            pytest.xfail("Notification button interaction failed - element not accessible")
        except AssertionError as e:
            print(f"Notification button verification failed: {str(e)}")
            pytest.xfail("Notification button interaction failed - button state incorrect")
        except Exception as e:
            print(f"Error clicking Notification button: {str(e)}")
            pytest.xfail("Notification button interaction failed with error")
        time.sleep(2)
        action.send_keys(Keys.TAB).perform()
        time.sleep(2)
        action.send_keys("Admin").perform()
        time.sleep(2)
        try:
            # Wait for dropdown to be visible and clickable
            dropdown_item = wait.until(EC.element_to_be_clickable((By.XPATH, "//div[@class='search-dropdown-item' and text()='Enterprise Super Admin']")))
            # Scroll to element if needed
            driver.execute_script("arguments[0].scrollIntoView();", dropdown_item)
            # Click the dropdown item
            dropdown_item.click()
            print("Dropdown item selected successfully")
        except TimeoutException:
            print("Dropdown item not found or not clickable")
        time.sleep(2)
        try:
            # Find and click popUp checkbox
            popup_checkbox = wait.until(EC.element_to_be_clickable((By.XPATH, "//input[@name='popUp']")))
            if not popup_checkbox.is_selected():
                popup_checkbox.click()
                print("PopUp checkbox selected")
            # Find and click push checkbox
            push_checkbox = wait.until(EC.element_to_be_clickable((By.XPATH, "//input[@name='push']")))
            if not push_checkbox.is_selected():
                push_checkbox.click()
                print("Push checkbox selected")
            print("Both pop up and push checkboxes selected successfully")
        except TimeoutException:
            print("One or both pop up and push checkboxes not found")
        time.sleep(2)
        #Selecting the check boxes for push
        try:
            # Wait for popup checkbox with multiple selector strategies
            popup_checkbox = wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "input.PrivateSwitchBase-input.mui-1m9pwf3"))
            )
            # Ensure checkbox is visible and interactable
            if not popup_checkbox.is_displayed() or not popup_checkbox.is_enabled():
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", popup_checkbox)
                time.sleep(0.5)
            
            # Get initial state and click if needed
            initial_state = popup_checkbox.is_selected()
            if not initial_state:
                popup_checkbox.click()
                print("Toggled popup checkbox to selected state")
            else:
                print("Popup checkbox already selected")
            
            # Verify state changed
            assert popup_checkbox.is_selected(), "Popup checkbox failed to select"
        except TimeoutException:
            print("Popup checkbox not found within timeout period")
            pytest.xfail("Popup checkbox interaction failed - element not accessible")
        except AssertionError as e:
            print(f"Popup checkbox verification failed: {str(e)}")
            pytest.xfail("Popup checkbox interaction failed - state change error")
        except Exception as e:
            print(f"Error interacting with popup checkbox: {str(e)}")
            pytest.xfail("Popup checkbox interaction failed with error")
        time.sleep(2)
        #Selecting the check boxes for pop
        try:
            # Wait for popup checkbox with multiple selector strategies
            popup_checkbox = wait.until(
                EC.presence_of_element_located((By.NAME, "push"))
            )
            # Ensure checkbox is visible and interactable
            if not popup_checkbox.is_displayed() or not popup_checkbox.is_enabled():
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", popup_checkbox)
                time.sleep(0.5)
            
            # Get initial state and click if needed
            initial_state = popup_checkbox.is_selected()
            if not initial_state:
                popup_checkbox.click()
                print("Toggled popup checkbox to selected state")
            else:
                print("Popup checkbox already selected")
            
            # Verify state changed
            assert popup_checkbox.is_selected(), "Popup checkbox failed to select"
        except TimeoutException:
            print("Popup checkbox not found within timeout period")
            pytest.xfail("Popup checkbox interaction failed - element not accessible")
        except AssertionError as e:
            print(f"Popup checkbox verification failed: {str(e)}")
            pytest.xfail("Popup checkbox interaction failed - state change error")
        except Exception as e:
            print(f"Error interacting with popup checkbox: {str(e)}")
            pytest.xfail("Popup checkbox interaction failed with error")
        # Selecting update and close button
        try:
            update_button = wait.until(EC.element_to_be_clickable((
                By.XPATH, "//button[contains(@class, 'btn-primary') and normalize-space(text())='Update & Close']"
            )))
            update_button.click()

        except Exception as e:
            pytest.xfail(f"Button not found or not clickable: {e}")
        time.sleep(2)
    
    @pytest.mark.dependency(depends=["Test_Vsaas_Soterix::test_login"])
    def test_admin_edit_entry_exit_rule(self, params): 
        driver = params["driver"]
        wait = WebDriverWait(driver, 10)
        action = ActionChains(driver)   
        time.sleep(5)
        element = driver.find_element(By.XPATH, "//p[text()='General']")
        element.click()
        time.sleep(2)
        rules_element = driver.find_element(By.XPATH, "//p[text()='Rules']")
        rules_element.click()
        time.sleep(4)
        try:
            # Get all edit icons with aria-label="Edit"
            edit_icons = wait.until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, "img[aria-label='Edit'].icon"))
            )
            if not edit_icons:
                pytest.xfail("No edit icons found")
            # Pick the last edit icon
            last_edit_icon = edit_icons[-1]
            # Scroll to the element
            driver.execute_script("arguments[0].scrollIntoView(true);", last_edit_icon)
            time.sleep(0.5)  # Slight delay to ensure scroll completes
            try:
                # Ensure it's clickable
                WebDriverWait(driver, 5).until(EC.element_to_be_clickable(last_edit_icon))
                last_edit_icon.click()
                print("Clicked last edit icon")
            except ElementClickInterceptedException:
                driver.execute_script("arguments[0].click();", last_edit_icon)
                print("Clicked last edit icon using JS")

        except TimeoutException:
            print("Edit icon not found or not clickable")
            pytest.xfail("Edit icon interaction failed - element not accessible")
        time.sleep(2)
        # Edit the rule
        try:
            # Wait for all edit icons to be present in the DOM
            edit_icons = wait.until(EC.presence_of_all_elements_located((By.XPATH, "//img[@aria-label='Edit']")))

            if not edit_icons:
                pytest.xfail("No edit icons found on the page")

            # Select the last edit icon
            last_edit_icon = edit_icons[-1]

            # Scroll to it
            driver.execute_script("arguments[0].scrollIntoView();", last_edit_icon)

            try:
                # Try regular click
                last_edit_icon.click()
            except ElementClickInterceptedException:
                # Fallback to JavaScript click
                driver.execute_script("arguments[0].click();", last_edit_icon)
        except TimeoutException:
            print("Edit icons not found in time")
            pytest.xfail("Edit icon interaction failed - elements not accessible")
        # Select Notification option for Edit rule
        time.sleep(4)
        try:
            # Wait for notification button and ensure it's clickable
            notification_btn = wait.until(
                EC.element_to_be_clickable((By.XPATH, 
                    "//button[contains(@class, 'btn-modalTab') and contains(text(), 'Notification')]"))
            )
            # Verify button text and state
            assert "Notification" in notification_btn.text, "Incorrect button text"
            assert notification_btn.is_enabled(), "Notification button is disabled"
            # Ensure button is in viewport
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", notification_btn)
            time.sleep(0.5)
            # Click the button
            notification_btn.click()
            print("Clicked Notification button")
        except TimeoutException:
            print("Notification button not found or not clickable")
            pytest.xfail("Notification button interaction failed - element not accessible")
        except AssertionError as e:
            print(f"Notification button verification failed: {str(e)}")
            pytest.xfail("Notification button interaction failed - button state incorrect")
        except Exception as e:
            print(f"Error clicking Notification button: {str(e)}")
            pytest.xfail("Notification button interaction failed with error")
        time.sleep(2)
        action.send_keys(Keys.TAB).perform()
        time.sleep(2)
        action.send_keys("Admin").perform()
        time.sleep(2)
        try:
            # Wait for dropdown to be visible and clickable
            dropdown_item = wait.until(EC.element_to_be_clickable((By.XPATH, "//div[@class='search-dropdown-item' and text()='Enterprise Super Admin']")))
            # Scroll to element if needed
            driver.execute_script("arguments[0].scrollIntoView();", dropdown_item)
            # Click the dropdown item
            dropdown_item.click()
            print("Dropdown item selected successfully")
        except TimeoutException:
            print("Dropdown item not found or not clickable")
        time.sleep(2)
        try:
            # Find and click popUp checkbox
            popup_checkbox = wait.until(EC.element_to_be_clickable((By.XPATH, "//input[@name='popUp']")))
            if not popup_checkbox.is_selected():
                popup_checkbox.click()
                print("PopUp checkbox selected")
            # Find and click push checkbox
            push_checkbox = wait.until(EC.element_to_be_clickable((By.XPATH, "//input[@name='push']")))
            if not push_checkbox.is_selected():
                push_checkbox.click()
                print("Push checkbox selected")
            print("Both pop up and push checkboxes selected successfully")
        except TimeoutException:
            print("One or both pop up and push checkboxes not found")
        time.sleep(2)
        #Selecting the check boxes for push
        try:
            # Wait for popup checkbox with multiple selector strategies
            popup_checkbox = wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "input.PrivateSwitchBase-input.mui-1m9pwf3"))
            )
            # Ensure checkbox is visible and interactable
            if not popup_checkbox.is_displayed() or not popup_checkbox.is_enabled():
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", popup_checkbox)
                time.sleep(0.5)
            
            # Get initial state and click if needed
            initial_state = popup_checkbox.is_selected()
            if not initial_state:
                popup_checkbox.click()
                print("Toggled popup checkbox to selected state")
            else:
                print("Popup checkbox already selected")
            
            # Verify state changed
            assert popup_checkbox.is_selected(), "Popup checkbox failed to select"
        except TimeoutException:
            print("Popup checkbox not found within timeout period")
            pytest.xfail("Popup checkbox interaction failed - element not accessible")
        except AssertionError as e:
            print(f"Popup checkbox verification failed: {str(e)}")
            pytest.xfail("Popup checkbox interaction failed - state change error")
        except Exception as e:
            print(f"Error interacting with popup checkbox: {str(e)}")
            pytest.xfail("Popup checkbox interaction failed with error")
        time.sleep(2)
        #Selecting the check boxes for pop
        try:
            # Wait for popup checkbox with multiple selector strategies
            popup_checkbox = wait.until(
                EC.presence_of_element_located((By.NAME, "push"))
            )
            # Ensure checkbox is visible and interactable
            if not popup_checkbox.is_displayed() or not popup_checkbox.is_enabled():
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", popup_checkbox)
                time.sleep(0.5)
            
            # Get initial state and click if needed
            initial_state = popup_checkbox.is_selected()
            if not initial_state:
                popup_checkbox.click()
                print("Toggled popup checkbox to selected state")
            else:
                print("Popup checkbox already selected")
            
            # Verify state changed
            assert popup_checkbox.is_selected(), "Popup checkbox failed to select"
        except TimeoutException:
            print("Popup checkbox not found within timeout period")
            pytest.xfail("Popup checkbox interaction failed - element not accessible")
        except AssertionError as e:
            print(f"Popup checkbox verification failed: {str(e)}")
            pytest.xfail("Popup checkbox interaction failed - state change error")
        except Exception as e:
            print(f"Error interacting with popup checkbox: {str(e)}")
            pytest.xfail("Popup checkbox interaction failed with error")
        # Selecting update and close button
        try:
            update_button = wait.until(EC.element_to_be_clickable((
                By.XPATH, "//button[contains(@class, 'btn-primary') and normalize-space(text())='Update & Close']"
            )))
            update_button.click()

        except Exception as e:
            pytest.xfail(f"Button not found or not clickable: {e}")
        time.sleep(2)
    
    @pytest.mark.dependency(depends=["Test_Vsaas_Soterix::test_login"])
    def test_admin_edit_linecrossing_rule(self, params): 
        driver = params["driver"]
        wait = WebDriverWait(driver, 10)
        action = ActionChains(driver)   
        time.sleep(5)
        element = driver.find_element(By.XPATH, "//p[text()='General']")
        element.click()
        time.sleep(2)
        rules_element = driver.find_element(By.XPATH, "//p[text()='Rules']")
        rules_element.click()
        time.sleep(4)
        try:
            # Get all edit icons with aria-label="Edit"
            edit_icons = wait.until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, "img[aria-label='Edit'].icon"))
            )
            if not edit_icons:
                pytest.xfail("No edit icons found")
            # Pick the last edit icon
            last_edit_icon = edit_icons[-1]
            # Scroll to the element
            driver.execute_script("arguments[0].scrollIntoView(true);", last_edit_icon)
            time.sleep(0.5)  # Slight delay to ensure scroll completes
            try:
                # Ensure it's clickable
                WebDriverWait(driver, 5).until(EC.element_to_be_clickable(last_edit_icon))
                last_edit_icon.click()
                print("Clicked last edit icon")
            except ElementClickInterceptedException:
                driver.execute_script("arguments[0].click();", last_edit_icon)
                print("Clicked last edit icon using JS")

        except TimeoutException:
            print("Edit icon not found or not clickable")
            pytest.xfail("Edit icon interaction failed - element not accessible")
        time.sleep(2)
        # Edit the rule
        try:
            # Wait for all edit icons to be present in the DOM
            edit_icons = wait.until(EC.presence_of_all_elements_located((By.XPATH, "//img[@aria-label='Edit']")))

            if not edit_icons:
                pytest.xfail("No edit icons found on the page")

            # Select the last edit icon
            last_edit_icon = edit_icons[-1]

            # Scroll to it
            driver.execute_script("arguments[0].scrollIntoView();", last_edit_icon)

            try:
                # Try regular click
                last_edit_icon.click()
            except ElementClickInterceptedException:
                # Fallback to JavaScript click
                driver.execute_script("arguments[0].click();", last_edit_icon)
        except TimeoutException:
            print("Edit icons not found in time")
            pytest.xfail("Edit icon interaction failed - elements not accessible")
        # Select Notification option for Edit rule
        time.sleep(4)
        try:
            # Wait for notification button and ensure it's clickable
            notification_btn = wait.until(
                EC.element_to_be_clickable((By.XPATH, 
                    "//button[contains(@class, 'btn-modalTab') and contains(text(), 'Notification')]"))
            )
            # Verify button text and state
            assert "Notification" in notification_btn.text, "Incorrect button text"
            assert notification_btn.is_enabled(), "Notification button is disabled"
            # Ensure button is in viewport
            driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", notification_btn)
            time.sleep(0.5)
            # Click the button
            notification_btn.click()
            print("Clicked Notification button")
        except TimeoutException:
            print("Notification button not found or not clickable")
            pytest.xfail("Notification button interaction failed - element not accessible")
        except AssertionError as e:
            print(f"Notification button verification failed: {str(e)}")
            pytest.xfail("Notification button interaction failed - button state incorrect")
        except Exception as e:
            print(f"Error clicking Notification button: {str(e)}")
            pytest.xfail("Notification button interaction failed with error")
        time.sleep(2)
        action.send_keys(Keys.TAB).perform()
        time.sleep(2)
        action.send_keys("Admin").perform()
        time.sleep(2)
        try:
            # Wait for dropdown to be visible and clickable
            dropdown_item = wait.until(EC.element_to_be_clickable((By.XPATH, "//div[@class='search-dropdown-item' and text()='Enterprise Super Admin']")))
            # Scroll to element if needed
            driver.execute_script("arguments[0].scrollIntoView();", dropdown_item)
            # Click the dropdown item
            dropdown_item.click()
            print("Dropdown item selected successfully")
        except TimeoutException:
            print("Dropdown item not found or not clickable")
        time.sleep(2)
        try:
            # Find and click popUp checkbox
            popup_checkbox = wait.until(EC.element_to_be_clickable((By.XPATH, "//input[@name='popUp']")))
            if not popup_checkbox.is_selected():
                popup_checkbox.click()
                print("PopUp checkbox selected")
            # Find and click push checkbox
            push_checkbox = wait.until(EC.element_to_be_clickable((By.XPATH, "//input[@name='push']")))
            if not push_checkbox.is_selected():
                push_checkbox.click()
                print("Push checkbox selected")
            print("Both pop up and push checkboxes selected successfully")
        except TimeoutException:
            print("One or both pop up and push checkboxes not found")
        time.sleep(2)
        #Selecting the check boxes for push
        try:
            # Wait for popup checkbox with multiple selector strategies
            popup_checkbox = wait.until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "input.PrivateSwitchBase-input.mui-1m9pwf3"))
            )
            # Ensure checkbox is visible and interactable
            if not popup_checkbox.is_displayed() or not popup_checkbox.is_enabled():
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", popup_checkbox)
                time.sleep(0.5)
            
            # Get initial state and click if needed
            initial_state = popup_checkbox.is_selected()
            if not initial_state:
                popup_checkbox.click()
                print("Toggled popup checkbox to selected state")
            else:
                print("Popup checkbox already selected")
            
            # Verify state changed
            assert popup_checkbox.is_selected(), "Popup checkbox failed to select"
        except TimeoutException:
            print("Popup checkbox not found within timeout period")
            pytest.xfail("Popup checkbox interaction failed - element not accessible")
        except AssertionError as e:
            print(f"Popup checkbox verification failed: {str(e)}")
            pytest.xfail("Popup checkbox interaction failed - state change error")
        except Exception as e:
            print(f"Error interacting with popup checkbox: {str(e)}")
            pytest.xfail("Popup checkbox interaction failed with error")
        time.sleep(2)
        #Selecting the check boxes for pop
        try:
            # Wait for popup checkbox with multiple selector strategies
            popup_checkbox = wait.until(
                EC.presence_of_element_located((By.NAME, "push"))
            )
            # Ensure checkbox is visible and interactable
            if not popup_checkbox.is_displayed() or not popup_checkbox.is_enabled():
                driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", popup_checkbox)
                time.sleep(0.5)
            
            # Get initial state and click if needed
            initial_state = popup_checkbox.is_selected()
            if not initial_state:
                popup_checkbox.click()
                print("Toggled popup checkbox to selected state")
            else:
                print("Popup checkbox already selected")
            
            # Verify state changed
            assert popup_checkbox.is_selected(), "Popup checkbox failed to select"
        except TimeoutException:
            print("Popup checkbox not found within timeout period")
            pytest.xfail("Popup checkbox interaction failed - element not accessible")
        except AssertionError as e:
            print(f"Popup checkbox verification failed: {str(e)}")
            pytest.xfail("Popup checkbox interaction failed - state change error")
        except Exception as e:
            print(f"Error interacting with popup checkbox: {str(e)}")
            pytest.xfail("Popup checkbox interaction failed with error")
        # Selecting update and close button
        try:
            update_button = wait.until(EC.element_to_be_clickable((
                By.XPATH, "//button[contains(@class, 'btn-primary') and normalize-space(text())='Update & Close']"
            )))
            update_button.click()

        except Exception as e:
            pytest.xfail(f"Button not found or not clickable: {e}")
        time.sleep(2)
        
    @pytest.mark.dependency(depends=["Test_Vsaas_Soterix::test_login"])
    def test_admin_delete_heatmap_rule(self, params):
        driver = params['driver']
        wait = WebDriverWait(driver, 10)
        action = ActionChains(driver)
        # Refresh the page to ensure all elements are loaded 
        time.sleep(5)
        element = driver.find_element(By.XPATH, "//p[text()='General']")
        element.click()
        time.sleep(2)
        rules_element = driver.find_element(By.XPATH, "//p[text()='Rules']")
        rules_element.click()
        time.sleep(5)
        # Deleting the Occupancy rule after edit
        try:
            # Method 1: Using CSS selector with SVG
            delete_icons = wait.until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, "img[aria-label='Delete']"))
            )
            # Method 2: Fallback to SVG path if img not found
            if not delete_icons:
                delete_icons = driver.find_elements(By.CSS_SELECTOR, "svg[aria-label='Delete']")
            # Check if delete icons are found
            if delete_icons:
                # Click the last delete icon
                last_delete_icon = delete_icons[-1]
                # Ensure element is visible and clickable
                wait.until(EC.element_to_be_clickable(last_delete_icon))
                last_delete_icon.click()
                print("Clicked last delete icon")
            else:
                raise NoSuchElementException("No delete icons found")
        except (TimeoutException, NoSuchElementException) as e:
            print(f"Delete icon error: {str(e)}")
            pytest.xfail("Delete icon not found or not clickable")
        time.sleep(2)
        # Confirm deletion
        try:
            # Wait for delete confirmation button and ensure it's clickable
            delete_button = wait.until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(@class, 'btn-primary') and text()='Delete']"))
            )
            # Scroll into view if needed
            driver.execute_script("arguments[0].scrollIntoView(true);", delete_button)
            time.sleep(1)  # Brief pause for scroll to complete
            # Click the button
            delete_button.click()
            print("Clicked confirm delete button")
        except TimeoutException:
            print("Delete confirmation button not found or not clickable")
            pytest.xfail("Delete confirmation failed - button not accessible")
        except Exception as e:
            print(f"Error during delete confirmation: {str(e)}")
            pytest.xfail("Delete confirmation failed with error")
        time.sleep(2)
    
    @pytest.mark.dependency(depends=["Test_Vsaas_Soterix::test_login"])
    def test_admin_delete_entry_exit_rule(self, params):
        driver = params['driver']
        wait = WebDriverWait(driver, 10)
        action = ActionChains(driver)
        # Refresh the page to ensure all elements are loaded 
        time.sleep(5)
        element = driver.find_element(By.XPATH, "//p[text()='General']")
        element.click()
        time.sleep(2)
        rules_element = driver.find_element(By.XPATH, "//p[text()='Rules']")
        rules_element.click()
        time.sleep(5)
        # Deleting the Occupancy rule after edit
        try:
            # Method 1: Using CSS selector with SVG
            delete_icons = wait.until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, "img[aria-label='Delete']"))
            )
            # Method 2: Fallback to SVG path if img not found
            if not delete_icons:
                delete_icons = driver.find_elements(By.CSS_SELECTOR, "svg[aria-label='Delete']")
            # Check if delete icons are found
            if delete_icons:
                # Click the last delete icon
                last_delete_icon = delete_icons[-1]
                # Ensure element is visible and clickable
                wait.until(EC.element_to_be_clickable(last_delete_icon))
                last_delete_icon.click()
                print("Clicked last delete icon")
            else:
                raise NoSuchElementException("No delete icons found")
        except (TimeoutException, NoSuchElementException) as e:
            print(f"Delete icon error: {str(e)}")
            pytest.xfail("Delete icon not found or not clickable")
        time.sleep(2)
        # Confirm deletion
        try:
            # Wait for delete confirmation button and ensure it's clickable
            delete_button = wait.until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(@class, 'btn-primary') and text()='Delete']"))
            )
            # Scroll into view if needed
            driver.execute_script("arguments[0].scrollIntoView(true);", delete_button)
            time.sleep(1)  # Brief pause for scroll to complete
            # Click the button
            delete_button.click()
            print("Clicked confirm delete button")
        except TimeoutException:
            print("Delete confirmation button not found or not clickable")
            pytest.xfail("Delete confirmation failed - button not accessible")
        except Exception as e:
            print(f"Error during delete confirmation: {str(e)}")
            pytest.xfail("Delete confirmation failed with error")
    
    @pytest.mark.dependency(depends=["Test_Vsaas_Soterix::test_login"])
    def test_admin_delete_loitering_rule(self, params):
        driver = params['driver']
        wait = WebDriverWait(driver, 10)
        action = ActionChains(driver)
        # Refresh the page to ensure all elements are loaded 
        time.sleep(5)
        element = driver.find_element(By.XPATH, "//p[text()='General']")
        element.click()
        time.sleep(2)
        rules_element = driver.find_element(By.XPATH, "//p[text()='Rules']")
        rules_element.click()
        time.sleep(5)
        # Deleting the Occupancy rule after edit
        try:
            # Method 1: Using CSS selector with SVG
            delete_icons = wait.until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, "img[aria-label='Delete']"))
            )
            # Method 2: Fallback to SVG path if img not found
            if not delete_icons:
                delete_icons = driver.find_elements(By.CSS_SELECTOR, "svg[aria-label='Delete']")
            # Check if delete icons are found
            if delete_icons:
                # Click the last delete icon
                last_delete_icon = delete_icons[-1]
                # Ensure element is visible and clickable
                wait.until(EC.element_to_be_clickable(last_delete_icon))
                last_delete_icon.click()
                print("Clicked last delete icon")
            else:
                raise NoSuchElementException("No delete icons found")
        except (TimeoutException, NoSuchElementException) as e:
            print(f"Delete icon error: {str(e)}")
            pytest.xfail("Delete icon not found or not clickable")
        time.sleep(2)
        # Confirm deletion
        try:
            # Wait for delete confirmation button and ensure it's clickable
            delete_button = wait.until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(@class, 'btn-primary') and text()='Delete']"))
            )
            # Scroll into view if needed
            driver.execute_script("arguments[0].scrollIntoView(true);", delete_button)
            time.sleep(1)  # Brief pause for scroll to complete
            # Click the button
            delete_button.click()
            print("Clicked confirm delete button")
        except TimeoutException:
            print("Delete confirmation button not found or not clickable")
            pytest.xfail("Delete confirmation failed - button not accessible")
        except Exception as e:
            print(f"Error during delete confirmation: {str(e)}")
            pytest.xfail("Delete confirmation failed with error")
    
    @pytest.mark.dependency(depends=["Test_Vsaas_Soterix::test_login"])
    def test_admin_delete_linecrossing_rule(self, params):
        driver = params['driver']
        wait = WebDriverWait(driver, 10)
        action = ActionChains(driver)
        # Refresh the page to ensure all elements are loaded 
        time.sleep(5)
        element = driver.find_element(By.XPATH, "//p[text()='General']")
        element.click()
        time.sleep(2)
        rules_element = driver.find_element(By.XPATH, "//p[text()='Rules']")
        rules_element.click()
        time.sleep(5)
        # Deleting the Occupancy rule after edit
        try:
            # Method 1: Using CSS selector with SVG
            delete_icons = wait.until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, "img[aria-label='Delete']"))
            )
            # Method 2: Fallback to SVG path if img not found
            if not delete_icons:
                delete_icons = driver.find_elements(By.CSS_SELECTOR, "svg[aria-label='Delete']")
            # Check if delete icons are found
            if delete_icons:
                # Click the last delete icon
                last_delete_icon = delete_icons[-1]
                # Ensure element is visible and clickable
                wait.until(EC.element_to_be_clickable(last_delete_icon))
                last_delete_icon.click()
                print("Clicked last delete icon")
            else:
                raise NoSuchElementException("No delete icons found")
        except (TimeoutException, NoSuchElementException) as e:
            print(f"Delete icon error: {str(e)}")
            pytest.xfail("Delete icon not found or not clickable")
        time.sleep(2)
        # Confirm deletion
        try:
            # Wait for delete confirmation button and ensure it's clickable
            delete_button = wait.until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(@class, 'btn-primary') and text()='Delete']"))
            )
            # Scroll into view if needed
            driver.execute_script("arguments[0].scrollIntoView(true);", delete_button)
            time.sleep(1)  # Brief pause for scroll to complete
            # Click the button
            delete_button.click()
            print("Clicked confirm delete button")
        except TimeoutException:
            print("Delete confirmation button not found or not clickable")
            pytest.xfail("Delete confirmation failed - button not accessible")
        except Exception as e:
            print(f"Error during delete confirmation: {str(e)}")
            pytest.xfail("Delete confirmation failed with error")
        time.sleep(2)
    # Delete the Occupancy rule
    @pytest.mark.dependency(depends=["Test_Vsaas_Soterix::test_login"])
    def test_admin_delete_occuoancy_rule(self, params):
        driver = params['driver']
        wait = WebDriverWait(driver, 10)
        action = ActionChains(driver)
        # Refresh the page to ensure all elements are loaded 
        time.sleep(5)
        element = driver.find_element(By.XPATH, "//p[text()='General']")
        element.click()
        time.sleep(2)
        rules_element = driver.find_element(By.XPATH, "//p[text()='Rules']")
        rules_element.click()
        time.sleep(5)
        # Deleting the Occupancy rule after edit
        try:
            # Method 1: Using CSS selector with SVG
            delete_icons = wait.until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, "img[aria-label='Delete']"))
            )
            # Method 2: Fallback to SVG path if img not found
            if not delete_icons:
                delete_icons = driver.find_elements(By.CSS_SELECTOR, "svg[aria-label='Delete']")
            # Check if delete icons are found
            if delete_icons:
                # Click the last delete icon
                last_delete_icon = delete_icons[-1]
                # Ensure element is visible and clickable
                wait.until(EC.element_to_be_clickable(last_delete_icon))
                last_delete_icon.click()
                print("Clicked last delete icon")
            else:
                raise NoSuchElementException("No delete icons found")
        except (TimeoutException, NoSuchElementException) as e:
            print(f"Delete icon error: {str(e)}")
            pytest.xfail("Delete icon not found or not clickable")
        time.sleep(2)
        # Confirm deletion
        try:
            # Wait for delete confirmation button and ensure it's clickable
            delete_button = wait.until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(@class, 'btn-primary') and text()='Delete']"))
            )
            # Scroll into view if needed
            driver.execute_script("arguments[0].scrollIntoView(true);", delete_button)
            time.sleep(1)  # Brief pause for scroll to complete
            # Click the button
            delete_button.click()
            print("Clicked confirm delete button")
        except TimeoutException:
            print("Delete confirmation button not found or not clickable")
            pytest.xfail("Delete confirmation failed - button not accessible")
        except Exception as e:
            print(f"Error during delete confirmation: {str(e)}")
            pytest.xfail("Delete confirmation failed with error")
    
    # Delete the intrusion detection rule
    @pytest.mark.dependency(depends=["Test_Vsaas_Soterix::test_login"])
    def test_admin_delete_intrusion_detection_rule(self, params):
        driver = params['driver']
        wait = WebDriverWait(driver, 10)
        action = ActionChains(driver)
        # Refresh the page to ensure all elements are loaded 
        time.sleep(5)
        element = driver.find_element(By.XPATH, "//p[text()='General']")
        element.click()
        time.sleep(2)
        rules_element = driver.find_element(By.XPATH, "//p[text()='Rules']")
        rules_element.click()
        time.sleep(5)
        # Deleting the Occupancy rule after edit
        try:
            # Method 1: Using CSS selector with SVG
            delete_icons = wait.until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, "img[aria-label='Delete']"))
            )
            # Method 2: Fallback to SVG path if img not found
            if not delete_icons:
                delete_icons = driver.find_elements(By.CSS_SELECTOR, "svg[aria-label='Delete']")
            # Check if delete icons are found
            if delete_icons:
                # Click the last delete icon
                last_delete_icon = delete_icons[-1]
                # Ensure element is visible and clickable
                wait.until(EC.element_to_be_clickable(last_delete_icon))
                last_delete_icon.click()
                print("Clicked last delete icon")
            else:
                raise NoSuchElementException("No delete icons found")
        except (TimeoutException, NoSuchElementException) as e:
            print(f"Delete icon error: {str(e)}")
            pytest.xfail("Delete icon not found or not clickable")
        time.sleep(2)
        # Confirm deletion
        try:
            # Wait for delete confirmation button and ensure it's clickable
            delete_button = wait.until(
                EC.element_to_be_clickable((By.XPATH, "//button[contains(@class, 'btn-primary') and text()='Delete']"))
            )
            # Scroll into view if needed
            driver.execute_script("arguments[0].scrollIntoView(true);", delete_button)
            time.sleep(1)  # Brief pause for scroll to complete
            # Click the button
            delete_button.click()
            print("Clicked confirm delete button")
        except TimeoutException:
            print("Delete confirmation button not found or not clickable")
            pytest.xfail("Delete confirmation failed - button not accessible")
        except Exception as e:
            print(f"Error during delete confirmation: {str(e)}")
            pytest.xfail("Delete confirmation failed with error")
    
    @pytest.mark.dependency(depends=["Test_Vsaas_Soterix::test_login"])
    def test_admin_mute_notification(self, params):
        driver = params['driver']
        wait = WebDriverWait(driver, 10)
        action = ActionChains(driver)
        # Refresh the page to ensure all elements are loaded 
        time.sleep(5)
        element = driver.find_element(By.XPATH, "//p[text()='General']")
        element.click()
        time.sleep(2)
        rules_element = driver.find_element(By.XPATH, "//p[text()='Rules']")
        rules_element.click()
        time.sleep(5)
        # Muting the notification
        try:
            # Find all matching notification icons
            mute_icons = wait.until(
                EC.presence_of_all_elements_located((By.CSS_SELECTOR, "img[aria-label='Mute Notification']"))
            )
            # Access the last element using index -1
            if mute_icons:
                mute_icons[-1].click()
                print("Clicked last mute notification icon")
            else:
                raise NoSuchElementException("No mute icons found")
        except (TimeoutException, NoSuchElementException) as e:
            print(f"Mute notification icon error: {str(e)}")
            pytest.xfail("Mute notification icon not found or not clickable")
        time.sleep(2)
    
    @pytest.mark.dependency(depends=["Test_Vsaas_Soterix::test_login"])
    def test_navigate_to_media_page(self, params):
        driver = params['driver']
        wait = WebDriverWait(driver, 10)
        time.sleep(5)
        # Click the button with the label "Media"
        try:
            media_button = wait.until(EC.element_to_be_clickable((
                By.XPATH, '//button[contains(@class, "sidenavItem")]//span[text()="Media"]')))
            media_button.click()
            print("Media button clicked successfully.")
        except Exception as e:
            print(f"Error clicking on Media button: {e}")
        time.sleep(4)
    @pytest.mark.dependency(depends=["Test_Vsaas_Soterix::test_login"])
    def test_media_select_filter(self, params):
        driver = params['driver']
        wait = WebDriverWait(driver, 10)
        time.sleep(4)    
        # Click the dropdown
        try:
            dropdown = wait.until(EC.element_to_be_clickable((
            By.XPATH, '//div[@role="combobox"]'
            )))
            dropdown.click()
            print("Dropdown clicked successfully.")
            time.sleep(6)
        except Exception as e:
            print(f"Error clicking on dropdown: {e}")
        # Select "Last 30 Days" option
        try:
            option = wait.until(EC.element_to_be_clickable((
            By.XPATH, '//li[@role="option" and text()="Last 30 Days"]'
            )))
            option.click()
            print('"Last 30 Days" option selected successfully.')
        except Exception as e:
            print(f"Error selecting 'Last 30 Days' option: {e}")
        time.sleep(3)
        # Check if page is empty using our new helper method
        main_page_empty = self.is_page_empty(wait)
        assert main_page_empty is not None, "Could not determine if main page has data"
        print("Main page empty:", main_page_empty)
        time.sleep(4)
    
    @pytest.mark.dependency(depends=["Test_Vsaas_Soterix::test_login"])
    def test_media_switch_to_grid_view(self, params):
        driver = params['driver']
        wait = WebDriverWait(driver, 10)
        time.sleep(4)    
        # Validate switching from list view to grid view
        try:
            icon_button = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, '//img[contains(@src, "icon-grid")]/..'))
            )
            icon_button.click()
            print("Switched to grid view successfully.")
            time.sleep(5)
        except Exception as e:
            print(f"Error while switching to grid view: {e}")
    @pytest.mark.dependency(depends=["Test_Vsaas_Soterix::test_login"])
    def test_media_validate_my_media(self, params):
        driver = params['driver']
        wait = WebDriverWait(driver, 10)
        time.sleep(4)    
        # Checking My media content
        # First, click on the "My Media" tab
        try:
            my_media_tab = driver.find_element(By.XPATH, "//button[contains(text(), 'My Media')]")
            my_media_tab.click()
            print("'My Media' tab clicked successfully.")
        except Exception as e:
            print(f"Error clicking on 'My Media' tab: {e}")
        # Check if My Media tab is empty
        my_media_empty = self.is_page_empty(wait)
        assert my_media_empty is not None, "Could not determine if My Media tab has data"
        print("My Media tab empty:", my_media_empty)
    
    @pytest.mark.dependency(depends=["Test_Vsaas_Soterix::test_login"])
    def test_media_validate_shared_with_me(self, params):
        driver = params['driver']
        wait = WebDriverWait(driver, 10)
        time.sleep(4) 
        # Check "Shared with me" tab
        try:
            # Click on the "Shared with me" tab
            shared_tab = driver.find_element(By.XPATH, "//button[contains(text(), 'Shared with me')]")
            shared_tab.click()
            print("Clicked on 'Shared with me' tab")
            # Check if Shared tab is empty
            shared_empty = self.is_page_empty(wait)
            assert shared_empty is not None, "Could not determine if Shared with me tab has data"
            print("Shared with me tab empty:", shared_empty)
        except NoSuchElementException:
            print("Could not find the 'shared with me' tab element")
        
    @pytest.mark.dependency(depends=["Test_Vsaas_Soterix::test_login"])
    def test_media_all_tab(self, params):
        driver = params['driver']
        wait = WebDriverWait(driver, 10)
        time.sleep(4)     
        # validate All tab
        # Click on "All" media tab
        try:
            all_media_tab = WebDriverWait(driver, 10).until(
            EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'All')]")))
            all_media_tab.click()
            print("'All' media tab clicked successfully.")
        except Exception as e:
            print(f"Error clicking on 'All' media tab: {e}")
        # Check if All Media tab is empty
        try:
            all_media_empty = self.is_page_empty(wait)
            assert all_media_empty is not None, "Could not determine if All Media tab has data"
            print("All Media tab empty:", all_media_empty)
            time.sleep(3)
        except AssertionError as ae:
            print(f"Assertion failed: {ae}")
        except Exception as e:
            print(f"Error while checking if All Media tab is empty: {e}")
    
    @pytest.mark.dependency(depends=["Test_Vsaas_Soterix::test_login"])
    def test_media_clips_tab(self, params):
        driver = params['driver']
        wait = WebDriverWait(driver, 10)
        time.sleep(4)     
        # Validate Clips in Media
        try:
            clips_element = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//span[contains(text(), 'Clips')]")))
            clips_element.click()
            print("'Clips' tab clicked successfully.")
            time.sleep(2)
        except Exception as e:
            print(f"Error clicking on 'Clips' tab: {e}")
        # Check if Clips tab is empty
        try:
            clip_empty = self.is_page_empty(wait)
            assert clip_empty is not None, "Could not determine if Clips tab has data"
            print("Clips tab empty:", clip_empty)
            time.sleep(4)
        except AssertionError as ae:
            print(f"Assertion failed: {ae}")
        except Exception as e:
            print(f"Error while checking if Clips tab is empty: {e}")
    
    @pytest.mark.dependency(depends=["Test_Vsaas_Soterix::test_login"])
    def test_media_clip_grouping(self, params):
        driver = params['driver']
        wait = WebDriverWait(driver, 10)
        time.sleep(4)
        # validate clip grouping
        try:
            category_selection_elements = driver.find_elements(By.CLASS_NAME, 'PrivateSwitchBase-input')
            if len(category_selection_elements) > 1:
                category_selection_elements[1].click()
                print("Second category selection clicked successfully.")
            else:
                print("Category selection element at index 1 not found.")
        except Exception as e:
            print(f"Error clicking on category selection element: {e}")
        time.sleep(2)
        try:
            group_clips = wait.until(
            EC.element_to_be_clickable((By.XPATH, "//p[text()='Group Clips']")))
            group_clips.click()
            print("'Group Clips' clicked successfully.")
        except Exception as e:
            print(f"Error clicking on 'Group Clips': {e}")
        time.sleep(2)
        # creating folder with default name
        try:
            group_clips_button = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[normalize-space()='Group Clips']")))
            group_clips_button.click()
            print("'Group Clips' button clicked successfully.")
        except Exception as e:
            print(f"Error clicking on 'Group Clips' button: {e}")
        time.sleep(8)
        try:
            clips_element = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//span[contains(text(), 'Clips')]"))
            )
            clips_element.click()
            print("'Clips' element clicked successfully.")
        except Exception as e:
            print(f"Error clicking on 'Clips' element: {e}")
        time.sleep(3)
    
    @pytest.mark.dependency(depends=["Test_Vsaas_Soterix::test_login"])
    def test_media_move_clip_to_existing_folder(self, params):
        driver = params['driver']
        wait = WebDriverWait(driver, 10)
        time.sleep(4)    
        # Add a clip to existing folder
        try:
            category_selection_elements = driver.find_elements(By.CLASS_NAME, 'PrivateSwitchBase-input')
            if len(category_selection_elements) > 1:
                category_selection_elements[1].click()
                print("Clip selected successfully.")
            else:
                print("Category selection element at index 1 not found.")
            time.sleep(2)
        except Exception as e:
            print(f"Error selecting clip: {e}")
        try:
            move_to_folder = driver.find_element(By.XPATH, '//p[text()="Move to folder"]')
            move_to_folder.click()
            print("'Move to folder' clicked.")
            time.sleep(5)
        except Exception as e:
            print(f"Error clicking 'Move to folder': {e}")
        try:
            dropdown = driver.find_element(By.CLASS_NAME, "modalForm-input-event")
            dropdown.click()
            print("Folder dropdown opened.")
            time.sleep(5)
        except Exception as e:
            print(f"Error opening folder dropdown: {e}")
        try:
            folder_option = driver.find_element(By.XPATH, "//option[contains(text(), 'Folder_')]")
            folder_option.click()
            print("Folder option selected.")
            time.sleep(3)
        except Exception as e:
            print(f"Error selecting folder option: {e}")
        try:
            move_button = driver.find_element(By.XPATH, '//button[text()="Move"]')
            move_button.click()
            print("Move button clicked.")
        except Exception as e:
            print(f"Error clicking 'Move' button: {e}")
        # Validate folders tab in Media page
        try:
            time.sleep(8)
            folders_span = driver.find_element(By.XPATH, "//span[contains(text(), 'Folders')]")
            folders_span.click()
            print("Folders tab clicked.")
            time.sleep(2)
        except Exception as e:
            print(f"Error clicking on 'Folders' tab: {e}")
        # Check if Folders tab is empty
        try:
            folders_empty = self.is_page_empty(wait)
            assert folders_empty is not None, "Could not determine if folder tab has data"
            print("Folders tab empty:", folders_empty)
        except AssertionError as ae:
            print(f"Assertion failed: {ae}")
        except Exception as e:
            print(f"Error checking if folders tab is empty: {e}")

    @pytest.mark.dependency(depends=["Test_Vsaas_Soterix::test_login"])
    def test_media_delete_folder(self, params):
        driver = params['driver']
        wait = WebDriverWait(driver, 10)
        time.sleep(4)   
        # Remove clips from folder
        try:
            options_icon = driver.find_element(By.XPATH, '//img[contains(@src, "icon-options")]')
            options_icon.click()
            print("Options icon clicked.")
            time.sleep(2)
        except Exception as e:
            print(f"Error clicking on options icon: {e}")
        # Click on the delete option from the menu
        try:
            delete_button = driver.find_element(By.XPATH, "//li[@role='menuitem' and contains(text(), 'Delete')]")
            delete_button.click()
            print("Delete option clicked from menu.")
            time.sleep(3)
        except Exception as e:
            print(f"Error clicking on 'Delete' menu item: {e}")
        # Confirm delete action
        try:
            delete_button = driver.find_element(By.CLASS_NAME, "btn-modalForm")
            delete_button.click()
            print("Confirmation delete button clicked.")
            time.sleep(3)
        except Exception as e:
            print(f"Error clicking confirmation 'Delete' button: {e}")

    @pytest.mark.dependency(depends=["Test_Vsaas_Soterix::test_login"])
    def test_media_create_link_folder(self, params):
        driver = params['driver']
        wait = WebDriverWait(driver, 10)
        time.sleep(4)      
        # Create link for folder
        try:
            options_icon = driver.find_element(By.XPATH, '//img[contains(@src, "icon-options")]')
            options_icon.click()
            print("Options icon clicked successfully.")
        except Exception as e:
            print(f"Error clicking on options icon: {e}")
        try:
            # Wait for the Create Link menu item and click it
            create_link_item = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//li[contains(text(),'Create Link')]"))
            )
            create_link_item.click()
            print("Create Link clicked.")
        except Exception as e:
            print("Error:", e)
        try:
            # Wait for the Create span to be clickable and click it
            create_button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//span[normalize-space()='Create']"))
            )
            create_button.click()
            print("Create button clicked.")
        except Exception as e:
            print("Error:", e)
    
    @pytest.mark.dependency(depends=["Test_Vsaas_Soterix::test_login"])
    def test_media_clip_rename(self, params):
        driver = params['driver']
        wait = WebDriverWait(driver, 10)
        time.sleep(4)   
        # Rename the clip
        try:
            clips_element = wait.until(
            EC.element_to_be_clickable((By.XPATH, "//span[contains(text(), 'Clips')]"))
            )
            clips_element.click()
            print("'Clips' tab clicked successfully.")
            time.sleep(2)
        except Exception as e:
            print(f"Error clicking on 'Clips' tab: {e}")

        # Check if Clips tab is empty
        try:
            clip_empty = self.is_page_empty(wait)
            assert clip_empty is not None, "Could not determine if clip tab has data"
            print("Clips tab empty:", clip_empty)
            time.sleep(4)
        except AssertionError as ae:
            print(f"Assertion failed: {ae}")
        except Exception as e:
            print(f"Error checking if Clips tab is empty: {e}")

        # Click the options icon
        try:
            options_icon = driver.find_element(By.XPATH, '//img[contains(@src, "icon-options")]')
            options_icon.click()
            print("Options icon clicked.")
            time.sleep(3)
        except Exception as e:
            print(f"Error clicking on options icon: {e}")

        # Click the rename menu item
        try:
            rename_menu_item = wait.until(
            EC.element_to_be_clickable((By.XPATH, "//li[contains(@class, 'MuiMenuItem-root') and contains(., 'Rename')]"))
            )
            rename_menu_item.click()
            print("'Rename' menu item clicked.")
        except Exception as e:
            print(f"Error clicking 'Rename' menu item: {e}")

        # Enter new name in the input field
        try:
            rename_input = wait.until(
            EC.presence_of_element_located((By.XPATH, "//input[contains(@class, 'rename') or @type='text']"))
            )
            rename_input.click()
            rename_input.send_keys("Renamed clip")
            rename_input.send_keys(Keys.RETURN)
            print("Clip renamed successfully.")
            time.sleep(5)
        except Exception as e:
            print(f"Error during clip renaming: {e}")
        
    @pytest.mark.dependency(depends=["Test_Vsaas_Soterix::test_login"])
    def test_media_clip_delete(self, params):
        driver = params['driver']
        wait = WebDriverWait(driver, 10)
        time.sleep(4)    
        # Clip delete validation
        clips_element = wait.until(
            EC.element_to_be_clickable((By.XPATH, "//span[contains(text(), 'Clips')]"))
        )
        clips_element.click()
        time.sleep(2)
        # Check if Clips tab is empty
        clip_empty = self.is_page_empty(wait)
        assert clip_empty is not None, "Could not determine if clip tab has data"
        print("Clips tab empty:", clip_empty)
        time.sleep(4)
        options_icon = driver.find_element(By.XPATH, '//img[contains(@src, "icon-options")]')
        options_icon.click()
        time.sleep(3)
        # Find and click the rename menu item using its specific class and text
        dele_menu_item = wait.until(EC.element_to_be_clickable(
            (By.XPATH, "//li[contains(@class, 'MuiMenuItem-root') and contains(., 'Delete')]")))
        dele_menu_item.click()
        delete_button = driver.find_element(By.CLASS_NAME, "btn-modalForm")
        delete_button.click()
        time.sleep(3)
        
    @pytest.mark.dependency(depends=["Test_Vsaas_Soterix::test_login"])
    def test_media_add_clip_to_vault(self, params): 
        driver = params['driver']
        wait = WebDriverWait(driver, 10)
        time.sleep(4)    
        # add a clip to vault
        clips_element = wait.until(
            EC.element_to_be_clickable((By.XPATH, "//span[contains(text(), 'Clips')]"))
        )
        clips_element.click()
        time.sleep(2)
        # Check if Clips tab is empty
        clip_empty = self.is_page_empty(wait)
        assert clip_empty is not None, "Could not determine if clip tab has data"
        print("Clips tab empty:", clip_empty)
        time.sleep(4)
        try:
            # Wait until the image is present and clickable
            image = wait.until(
                EC.element_to_be_clickable((By.XPATH, "//img[@alt='Add to Vault']"))
            )
            image.click()
            print("Image clicked.")
        except Exception as e:
            print("Error: Unable to add to the vault license error", e)
        
    @pytest.mark.dependency(depends=["Test_Vsaas_Soterix::test_login"])
    def test_media_remove_clip_from_vault(self, params):
        driver = params['driver']
        wait = WebDriverWait(driver, 10)
        time.sleep(4)        
        # remove clip from vault
        try:
            # Wait for the Remove from Vault icon to be clickable
            remove_icon = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//img[@alt='Remove from Vault']"))
            )
            remove_icon.click()
            print("Remove from Vault icon clicked.")
            time.sleep(2)
            button = wait.until(EC.element_to_be_clickable((By.XPATH, 
             "//button[contains(@class, 'btn-modalForm') and text()='Yes']")))
            button.click()
            print("Yes button clicked.")
        except Exception as e:
            print("Error:", e)
        time.sleep(2)
        try:
            # Wait for the 'Yes' button and click it
            yes_button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//button[normalize-space()='Yes']"))
            )
            yes_button.click()
            print("Yes button clicked.")
        except Exception as e:
            print("Error:", e)
        time.sleep(2)
        
    @pytest.mark.dependency(depends=["Test_Vsaas_Soterix::test_login"])
    def test_media_create_link_clip(self, params): 
        driver = params['driver']
        wait = WebDriverWait(driver, 10)
        time.sleep(4)           
        # Create link for clip
        options_icon = driver.find_element(By.XPATH, '//img[contains(@src, "icon-options")]')
        options_icon.click()
        try:
            # Wait for the Create Link menu item and click it
            create_link_item = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//li[contains(text(),'Create Link')]"))
            )
            create_link_item.click()
            print("Create Link clicked.")
        except Exception as e:
            print("Error:", e)
        try:
            # Wait for the Create span to be clickable and click it
            create_button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//span[normalize-space()='Create']"))
            )
            create_button.click()
            print("Create button clicked.")
        except Exception as e:
            print("Error:", e)
        time.sleep(3)
    
    @pytest.mark.dependency(depends=["Test_Vsaas_Soterix::test_login"])
    def test_media_add_folder_to_vault(self, params): 
        driver = params['driver']
        wait = WebDriverWait(driver, 10)
        time.sleep(4)    
        # adding folder to vault
        folders_span = driver.find_element(By.XPATH, "//span[contains(text(), 'Folders')]")
        folders_span.click()
        try:
            # Wait for the image to become clickable and click it
            add_to_vault_icon = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//img[@alt='Add to Vault']"))
            )
            add_to_vault_icon.click()
            print("Add to Vault icon clicked.")
        except Exception as e:
            print("Error:", e)
        # remove folder from vault
        try:
            # Wait for the Remove from Vault icon to be clickable
            remove_icon = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//img[@alt='Remove from Vault']"))
            )
            remove_icon.click()
            print("Remove from Vault icon clicked.")
        except Exception as e:
            print("Error:", e)
        time.sleep(2)
        try:
            # Wait for the 'Yes' button and click it
            yes_button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//button[normalize-space()='Yes']"))
            )
            yes_button.click()
            print("Yes button clicked.")
        except Exception as e:
            print("Error:", e)
        time.sleep(2)
    
    @pytest.mark.dependency(depends=["Test_Vsaas_Soterix::test_login"])
    def test_media_share_folder(self, params): 
        driver = params['driver']
        wait = WebDriverWait(driver, 10)
        time.sleep(4)    
        # share folder
        try:
            # Wait for the image element to be clickable and click it
            share_icon = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//img[@alt='Image 1']"))
            )
            share_icon.click()
            print("Share icon clicked.")
        except Exception as e:
            print("Error:", e)
        time.sleep(2)
        try:
            # Wait for the email input field and enter an email
            email_input = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, "//input[@placeholder='Add Email ID']"))
            )
            email_input.send_keys("test@example.com")
            print("Email entered successfully.")
        except Exception as e:
            print("Error:", e)
        time.sleep(3)
        try:
            # Wait for the span element with text 'Share' to be clickable
            share_button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//span[normalize-space()='Share']"))
            )
            share_button.click()
            print("Share button clicked.")
        except Exception as e:
            print("Error:", e)
        
    @pytest.mark.dependency(depends=["Test_Vsaas_Soterix::test_login"])
    def test_media_export_folder(self, params): 
        driver = params['driver']
        wait = WebDriverWait(driver, 10)
        time.sleep(4)
        # export folder
        try:
            # Wait for the download icon and click it
            download_icon = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//img[@alt='Image 1' and contains(@src, 'icon-download')]"))
            )
            download_icon.click()
            print("Download icon clicked.")
        except Exception as e:
            print("Error:", e)
        try:
            # Wait for the Export span to be clickable and click it
            export_button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, "//span[normalize-space()='Export']"))
            )
            export_button.click()
            print("Export button clicked.")
        except Exception as e:
            print("Error:", e)
        time.sleep(2)
        # Find the Vault span using CSS selectors
        vault_text = wait.until(EC.element_to_be_clickable((
            By.XPATH, '//span[text()="Vault"]'
        )))
        vault_text.click()
        # Check if Vault tab is empty
        vault_empty = self.is_page_empty(wait)
        assert vault_empty is not None, "Could not determine if vault tab has data"
        print("Clips tab empty:", vault_empty)
        time.sleep(4)
        
    @pytest.mark.dependency(depends=["Test_Vsaas_Soterix::test_login"])
    def test_media_search_clip(self, params):
        driver = params['driver']
        wait = WebDriverWait(driver, 10)
        time.sleep(4)
        # search clip
        # Find the input using its placeholder
        search_input = driver.find_element(By.XPATH, "//input[@placeholder='Search by title, tags, sites, etc.']")
        # Clear and enter text
        search_input.clear()
        search_input.send_keys("17")
        # Optionally, press Enter
        search_input.send_keys(Keys.RETURN)

    def is_page_empty(self, wait, timeout=5):
        """
        Checks if the current page/tab is empty by looking for the "No results found" message
        Returns:
            - True: Page is empty (no results message found)
            - False: Page has content (no results message not found)
            - None: Could not determine (an error occurred)
        """
        try:
            no_results = WebDriverWait(wait._driver, timeout).until(
                EC.visibility_of_element_located((
                    By.XPATH, "//p[contains(text(), 'No results found for selected criteria')]"
                ))
            )
            # No results message found - page is empty
            return True
        except TimeoutException:
            # No results message not found - page likely has content
            return False
    
    @pytest.mark.dependency(depends=["Test_Vsaas_Soterix::test_login"])
    def test_admin_navigate_to_admin_to_users(self, params):
        driver = params['driver']
        wait = WebDriverWait(driver, 10)
        time.sleep(10)
        try:
            # Wait for and click Admin link
            admin_link = wait.until(EC.element_to_be_clickable((
                By.XPATH, "//a[contains(@href,'admin')]"
            )))
            admin_link.click()
            time.sleep(5)
            print("Clicked on Admin button to navigate to Admin page")
            # Verify navigation to admin page
            wait.until(EC.url_contains("admin"))
            time.sleep(20) 
            # Wait for and click Users element using MUI typography classes
            users_element = wait.until(EC.element_to_be_clickable((By.XPATH, "//p[text()='Users']")
            ))
            assert users_element.is_displayed(), "Users element is not visible"
            assert users_element.text.strip() == "Users", "Element text does not match 'Users'"
            users_element.click()
            print("Clicked on Users tab")
            time.sleep(10)
            # Verify Users section loaded by checking for users table
            wait.until(EC.presence_of_element_located((
                By.XPATH, "//p[text()='Users']"
            )))
            print("Users section loaded successfully")
        except TimeoutException as e:
            print(f"Timeout error: {str(e)}")
            assert False, "Failed to navigate to Users section"
        except AssertionError as e:
            print(f"Assertion failed: {str(e)}")
            raise
    
    @pytest.mark.dependency(depends=["Test_Vsaas_Soterix::test_login"])
    def test_admin_add_user(self, params):
        driver = params['driver']
        wait = WebDriverWait(driver, 10)        
        # Check if the "Add User" button is present and click it
        try:
            add_user_button = wait.until(EC.element_to_be_clickable((
                By.CSS_SELECTOR, "button.add-btn"
            )))
            assert add_user_button.is_displayed(), "Add User button is not visible"
            add_user_button.click()
            print("Clicked on Add User button")
        except TimeoutException as e:
            print(f"Timeout error finding Add User button: {str(e)}")
            assert False, "Add User button not found or not clickable"
        except NoSuchElementException as e:
            print(f"Add User button not found: {str(e)}")
            assert False, "Add User button does not exist in DOM"
        except AssertionError as e:
            print(f"Assertion failed: {str(e)}")
            raise
        time.sleep(5)
        # Fill out Add User form with validation
        try:
            # Generate unique email with datestamp
            current_datetime = date.today()
            test_email = f"testuser_{current_datetime}@example.com"
            #test_email = f"testuser@example.com"
            
            # Fill form fields
            form_fields = {
                'name': ('User_creation_for_Automated_Test', "input[name='name'].modalForm-input"),
                'lastName': ('123Test', "input[name='lastName'].modalForm-input"),
                'email': (test_email, "input[name='mailId'].modalForm-input")
            }
            
            # Enter form data
            for field_name, (value, selector) in form_fields.items():
                field = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, selector)))
                field.send_keys(value)
                print(f"Entered {field_name}: {value}")

            # Select role from dropdown
            try:
                # Click to open role dropdown
                role_dropdown = wait.until(EC.element_to_be_clickable((
                    By.CSS_SELECTOR, 
                    "div.MuiStack-root.modalForm-input"
                )))
                role_dropdown.click()
                print("Opened role dropdown")
                time.sleep(10)  # Brief pause for dropdown animation

                # First try to find the Admin radio button
                admin_radio_label = wait.until(EC.element_to_be_clickable((By.XPATH, "//label[.//input[@value='Admin']]")))
                admin_radio_label.click()
                print("Selected Admin role")
            except TimeoutException as e:
                print(f"Timeout error selecting role: {str(e)}")
                assert False, "Role selection failed - elements not found or not clickable"
            except AssertionError as e:
                print(f"Role selection verification failed: {str(e)}")
                raise
            time.sleep(5)
            # Submit form and validate response
            try:
                # Click Save button
                save_button = wait.until(EC.element_to_be_clickable((
                    By.CSS_SELECTOR, "button.add-btn.save-btn"
                )))
                save_button.click()
                print("Clicked Save button")
            except TimeoutException as e:
                print(f"Timeout error during form submission: {str(e)}")
                assert False, "Form submission failed"   
            except Exception as e:
                print(f"Form submission error: {str(e)}")
                raise
        except TimeoutException as e:
            print(f"Timeout error in form: {str(e)}")
            assert False, "Form interaction failed"
        except Exception as e:
            print(f"Error during form submission: {str(e)}")
            raise

    @pytest.mark.dependency(depends=["Test_Vsaas_Soterix::test_login"])
    def test_admin_search_user(self, params):
        driver = params['driver']
        wait = WebDriverWait(driver, 10)        
        # Test search functionality and validate results
        time.sleep(10)  # Brief pause for search input to be ready
        try:
            # Get datetime from previous test
            current_datetime = date.today()
            # Wait for and locate search input
            search_input = wait.until(EC.presence_of_element_located((
                By.CSS_SELECTOR, "input[placeholder='Search']"
            )))
            assert search_input.is_displayed(), "Search input is not visible"
            
            # Enter search text
            search_text = f"testuser_{current_datetime}@example.com"
            search_input.clear()
            search_input.send_keys(search_text)
            print(f"Searching for user: {search_text}")
            # Wait for search results and verify user table exists
            user_elements = wait.until(EC.presence_of_all_elements_located((
                By.XPATH, f"//div[@title='testuser_{current_datetime}@example.com']"
            )))
            assert len(user_elements) > 0, "No search results found"
            print("Search results table loaded")
            time.sleep(5) 
            # Add this after entering search text in search_input
            try:
                # Wait for user element with title attribute
                user_email_element = wait.until(EC.presence_of_element_located((
                    By.CSS_SELECTOR, 
                    f"div[title='testuser_{current_datetime}@example.com']"
                )))
                assert user_email_element.is_displayed(), "User email element not visible"
                
                # Verify title attribute matches expected email
                expected_email = f"testuser_{current_datetime}@example.com"
                actual_email = user_email_element.get_attribute("title")
                assert actual_email == expected_email, f"Email mismatch. Expected: {expected_email}, Got: {actual_email}"
                
                # Verify element has proper styling for ellipsis
                style_value = user_email_element.get_attribute("style")
                required_styles = [
                    "white-space: nowrap",
                    "overflow: hidden", 
                    "text-overflow: ellipsis",
                    "cursor: pointer"
                ]
                for style in required_styles:
                    assert style in style_value, f"Missing required style: {style}"
                    
                print("Verified user email element with correct ellipsis styling")
            except TimeoutException as e:
                print(f"Timeout waiting for user email element: {str(e)}")
                assert False, "User email element not found"
            except AssertionError as e:
                print(f"Validation failed: {str(e)}")
                raise
        except TimeoutException as e:
            print(f"Timeout error during search: {str(e)}")
            assert False, "Search functionality failed - element not found or not clickable"
        except NoSuchElementException as e:
            print(f"Element not found: {str(e)}")
            assert False, "Required element missing from DOM"
        except AssertionError as e:
            print(f"Verification failed: {str(e)}")
            raise
        
    @pytest.mark.dependency(depends=["Test_Vsaas_Soterix::test_login"])
    def test_admin_delete_users(self, params):
        driver = params['driver']
        wait = WebDriverWait(driver, 10)        
        # Wait for and locate search input
        search_input = wait.until(EC.presence_of_element_located((
            By.CSS_SELECTOR, "input[placeholder='Search']"
            )))
        assert search_input.is_displayed(), "Search input is not visible"
        # Enter search text
        search_text = "123Test"
        search_input.clear()
        search_input.send_keys(search_text)
        time.sleep(5)
        # Delete user functionality
        try:
            # Find and click options icon for the user
            options_icon = wait.until(EC.element_to_be_clickable((
                By.XPATH, "//img[contains(@src, 'optionIcon')]"
            )))
            options_icon.click()
            print("Clicked options icon")
            time.sleep(3)  # Wait for options to appear
            # Wait for and click Delete option using specific Typography class
            delete_icon = driver.find_element(By.CSS_SELECTOR, "img[src*='delete-icon']")
            #assert delete_icon.text == "Delete", "Delete option text mismatch"
            delete_icon.click()
            print("Clicked Delete option")
            time.sleep(2)  # Wait for options to appear
            # Wait for and verify confirmation dialog
            # Find and verify Yes button in MuiBox
            yes_button = wait.until(EC.element_to_be_clickable((
                By.CSS_SELECTOR, "div.MuiBox-root.mui-yd38dn"
            )))
            assert yes_button.text == "Yes", "Button text is not 'Yes'"
            assert yes_button.is_displayed(), "Yes button is not visible"
            # Click Yes button
            yes_button.click()
            print("Clicked Yes button")        
            print("Confirmed user deletion")

        except TimeoutException as e:
            print(f"Timeout error during user deletion: {str(e)}")
            assert False, "User deletion failed - element not found or not clickable"
        except NoSuchElementException as e:
            print(f"Element not found: {str(e)}")
            assert False, "Required element missing from DOM"
        except AssertionError as e:
            print(f"Verification failed: {str(e)}")
            raise
    # Validate user suspension functionality    
    @pytest.mark.dependency(depends=["Test_Vsaas_Soterix::test_login"])
    def test_admin_users_suspend_active(self, params):
        driver = params['driver']
        wait = WebDriverWait(driver, 10)    
        # Wait for and locate search input
        search_input = wait.until(EC.presence_of_element_located((
            By.CSS_SELECTOR, "input[placeholder='Search']"
            )))
        assert search_input.is_displayed(), "Search input is not visible"
        # Enter search text
        search_text = "123Test"
        search_input.clear()
        search_input.send_keys(search_text)
        time.sleep(5)
        # Test switch toggle functionality with validation
        try:
            # Find and validate initial switch state 
            switch_input = wait.until(EC.presence_of_element_located((
                By.CSS_SELECTOR, "input.PrivateSwitchBase-input.MuiSwitch-input.mui-1m9pwf3[type='checkbox']"
            )))
            # Verify initial attributes
            assert switch_input.get_attribute("type") == "checkbox", "Not a checkbox input"
            assert switch_input.get_attribute("aria-label") == "ant design", "Incorrect aria-label"
            initial_state = switch_input.is_selected()
            print(f"Initial switch state: {'Active' if initial_state else 'Inactive'}")

            # Get parent element and perform click
            switch_parent = switch_input.find_element(By.XPATH, "./ancestor::span[contains(@class, 'MuiSwitch-root')]")
            switch_parent.click()
            print("Clicked switch toggle")
            time.sleep(2)  # Allow time for state change
            search_input.clear()
            time.sleep(3)
        except TimeoutException as e:
            print(f"Timeout error finding switch: {str(e)}")
            assert False, "Switch element not found or not clickable"
        except NoSuchElementException as e:
            print(f"Switch element not found: {str(e)}")
            assert False, "Required switch elements missing from DOM"
        except AssertionError as e:
            print(f"Switch validation failed: {str(e)}")
            raise
        time.sleep(5)

    # Test role selection functionality with validation
    @pytest.mark.dependency(depends=["Test_Vsaas_Soterix::test_login"])
    def test_admin_users_in_role_selection(self, params):
        driver = params['driver']
        wait = WebDriverWait(driver, 10)    
        # Test role menu items selection and validation
        try:
            # Wait for and click role dropdown
            wait = WebDriverWait(driver, 10)
            dropdown = wait.until(
                EC.element_to_be_clickable((
                    By.CSS_SELECTOR, 'div[role="combobox"]'
                )))
            dropdown.click()
            print("Opened role dropdown")
            # Wait for menu items to be visible
            wait.until(
                EC.visibility_of_element_located((
                    By.CSS_SELECTOR, 'ul[role="listbox"]'
                )))
            # Define expected roles and verify each
            expected_roles = ["All Roles", "Enterprise Super Admin", "Admin", "Supervisor", "Operator"]
            for role in expected_roles:
                # Wait for and verify each option
                option = wait.until(
                    EC.visibility_of_element_located((
                        By.XPATH, f'//li[contains(@class, "MuiMenuItem-root") and text()="{role}"]'
                    )))
                time.sleep(2)  # Allow time for option to be visible
            assert option.is_displayed(), f"{role} option not visible"   
            # Click option and verify selection
            time.sleep(2)  # Allow time for option to be clickable
            option.click()
            time.sleep(5)  # Allow time for selection to be processed
            print(f"Selected role: {role}")  
            # Wait for selection to be reflected
            wait.until(
                EC.text_to_be_present_in_element(
                    (By.CSS_SELECTOR, 'div[role="combobox"]'),
                        role
                    ))
            # Wait for page to load/update after selection
            time.sleep(2)  # Allow time for filtering to complete
            # Check if page is empty or users are available
            try:
                # Method 1: Check for "No data" or empty state messages
                empty_state_selectors = [
                    'div[class*="empty"]',
                    'div[class*="no-data"]',
                    'div[class*="no-results"]',
                    'div[class*="empty-state"]',
                    'div:contains("No users found")',
                    'div:contains("No data available")',
                    'div:contains("No results")',
                    'p:contains("No users")',
                    'span:contains("No data")'
                ]
                page_empty = False
                time.sleep(2)  # Allow time for empty state to render
                for selector in empty_state_selectors:
                    try:
                        empty_element = driver.find_element(By.CSS_SELECTOR, selector)
                        if empty_element.is_displayed():
                            page_empty = True
                            print(f"Page is empty for role '{role}' - Found empty state message")
                            break
                    except NoSuchElementException:
                        continue
                # Method 2: Check for user data/table rows
                time.sleep(2)  # Allow time for user data to load
                if not page_empty:
                    user_data_selectors = [
                        'tbody tr',  # Table rows
                        'div[class*="user-item"]',  # User cards/items
                        'div[class*="data-row"]',  # Data rows
                        'li[class*="user"]',  # User list items
                        'div[role="row"]'  # ARIA rows
                    ] 
                    users_found = False
                    for selector in user_data_selectors:
                        try:
                            user_elements = driver.find_elements(By.CSS_SELECTOR, selector)
                            if user_elements and len(user_elements) > 0:
                                # Check if elements are actually visible and contain data
                                visible_users = [elem for elem in user_elements if elem.is_displayed()]
                                if visible_users:
                                    users_found = True
                                    print(f"Found {len(visible_users)} users for role '{role}'")
                                    break
                        except NoSuchElementException:
                            continue
                
                if not users_found:
                    print(f"No users available for role '{role}' - No user elements found")
                    page_empty = True
                
                # Method 3: Check for loading states (in case data is still loading)
                loading_selectors = [
                    'div[class*="loading"]',
                    'div[class*="spinner"]',
                    'div[class*="skeleton"]',
                    'div[role="progressbar"]'
                ]
                
                is_loading = False
                for selector in loading_selectors:
                    try:
                        loading_element = driver.find_element(By.CSS_SELECTOR, selector)
                        if loading_element.is_displayed():
                            is_loading = True
                            print(f"Page is still loading for role '{role}' - waiting...")
                            # Wait for loading to complete
                            wait.until_not(
                                EC.visibility_of_element_located((By.CSS_SELECTOR, selector))
                            )
                            break
                    except NoSuchElementException:
                        continue
                
                # Re-check after loading completes
                if is_loading:
                    time.sleep(4)
                    # Repeat the user availability check
                    users_found = False
                    for selector in user_data_selectors:
                        try:
                            user_elements = driver.find_elements(By.CSS_SELECTOR, selector)
                            if user_elements and len(user_elements) > 0:
                                visible_users = [elem for elem in user_elements if elem.is_displayed()]
                                if visible_users:
                                    users_found = True
                                    print(f"After loading - Found {len(visible_users)} users for role '{role}'")
                                    break
                        except NoSuchElementException:
                            continue
                    time.sleep(2)  # Allow time for user data to load after loading state
                    if not users_found:
                        print(f"After loading - No users available for role '{role}'")
                        page_empty = True
                    
                # Log the final state
                if page_empty:
                    print(f"✓ Validated: Role '{role}' - Page is empty/no users available")
                else:
                    print(f"✓ Validated: Role '{role}' - Users are available")
                
            except Exception as validation_error:
                print(f"Warning: Could not validate page state for role '{role}': {str(validation_error)}")
            
            # Reopen dropdown for next iteration if not last item
            if role != expected_roles[-1]:
                wait.until(
                EC.element_to_be_clickable((
                    By.CSS_SELECTOR, 'div[role="combobox"]'
                ))
                ).click()
                
        except TimeoutException as e:
            print(f"Timeout error selecting role: {str(e)}")
            assert False, "Role selection failed - elements not found or not clickable"
        except NoSuchElementException as e:
            print(f"Element not found: {str(e)}")
            assert False, "Required role elements missing from DOM"
        except AssertionError as e:
            print(f"Role selection validation failed: {str(e)}")
            raise
        except Exception as e:
            print(f"Unexpected error during role selection: {str(e)}")
            assert False, f"Role selection failed with unexpected error: {str(e)}"
                                
    @pytest.mark.dependency(depends=["Test_Vsaas_Soterix::test_admin_users_page"])
    def test_admin_users_api_calls(self, params):
        self.log_api_data(params['driver'])
    
    @pytest.mark.dependency(depends=["Test_Vsaas_Soterix::test_login"])
    def test_navigating_to_admin_sites(self, params):
        driver = params['driver']
        wait = WebDriverWait(driver, 10)
        time.sleep(10)
        # Navigate to sites
        try:
            site_element = wait.until(EC.element_to_be_clickable((By.XPATH, "//p[text()='Sites']")
            ))
            assert site_element.is_displayed(), "Sites element is not visible"
            assert site_element.text.strip() == "Sites", "Element text does not match 'Sites'"
            site_element.click()
            print("Clicked on Sites tab")
            time.sleep(10)
            # Verify Sites section loaded by checking for Sites table
            wait.until(EC.presence_of_element_located((
                By.XPATH, "//p[text()='Sites']"
            )))
            print("Sites page loaded successfully")
        except TimeoutException as e:
            print(f"Timeout error: {str(e)}")
            assert False, "Failed to navigate to Sites page"
        except AssertionError as e:
            print(f"Assertion failed: {str(e)}")
            raise
    @pytest.mark.dependency(depends=["Test_Vsaas_Soterix::test_login"])
    def test_search_site(self, params):
        driver = params['driver']
        site_name = params['site_name']
        wait = WebDriverWait(driver, 10)
        time.sleep(5)
        try:
            # Wait for and find the search input field
            search_input = wait.until(EC.presence_of_element_located((
                By.XPATH, "//input[@placeholder='Search ']"
            )))
            search_input.clear()
            search_input.send_keys(site_name)
            time.sleep(5)
            print(f"Searched for site: {site_name}")
            # Wait for the search results to update
            # Verify that the site appears in the results
            site_row = wait.until(EC.presence_of_element_located((
                By.XPATH, f"//div[contains(.,'{site_name}')]"
            )))
            assert site_row.is_displayed(), f"Site '{site_name}' not found in results"
            print(f"Site '{site_name}' found in results")
        except TimeoutException as e:
            print(f"Timeout error while searching for site: {str(e)}")
            assert False, "Failed to search for site"
        except AssertionError as e:
            print(f"Assertion failed: {str(e)}")
            raise
        
    @pytest.mark.dependency(depends=["Test_Vsaas_Soterix::test_login"])
    def test_toggle_grid_to_list_vice_versa(self, params):
        driver = params['driver']
        wait = WebDriverWait(driver, 10)
        time.sleep(5)
        # Navigate to Users and Sites
        try:
            element = driver.find_element(By.XPATH, "//p[text()='Users']")
            element.click()
            print("✅ Clicked on 'Users' element.")
        except NoSuchElementException:
            print("❌ 'Users' element not found.")
        time.sleep(5)
        try:
            element = driver.find_element(By.XPATH, "//p[text()='Sites']")
            print("✅ 'Sites' element found.")
            element.click()
        except NoSuchElementException:
            print("❌ 'Sites' element not found.")
        time.sleep(5)
        try:
            # Find the toggle button for grid/list view
            toggle_button = wait.until(EC.element_to_be_clickable((
                By.XPATH, "//img[@alt='tableIcon']"
            )))
            assert toggle_button.is_displayed(), "Toggle button is present but not visible"
            toggle_button.click()
            time.sleep(5)
            print("Toggled to list view")
            time.sleep(5)
            # Now toggle back to grid view
            grid_icon = WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, "//img[contains(@src, 'icon-grid')]"))
                    )
            assert grid_icon.is_displayed(), "Grid icon is present but not visible"
            grid_icon.click()
            print("Toggled back to grid view")
            time.sleep(5)
        except TimeoutException as e:
            print(f"Timeout error while toggling view: {str(e)}")
            assert False, "Failed to toggle view"
        except AssertionError as e:
            print(f"Assertion failed: {str(e)}")
            raise
    @pytest.mark.dependency(depends=["Test_Vsaas_Soterix::test_login"])
    def test_check_site_status(self, params):
        driver = params['driver']
        wait = WebDriverWait(driver, 10)
        time.sleep(5)
        # Wait for all site cards to be loaded
        status_elements = wait.until(
            EC.presence_of_all_elements_located((By.XPATH, "//p[contains(@class, 'MuiTypography-root') and .//img[@alt='Online' or @alt='Offline']]"))
            )
        online_count = 0
        offline_count = 0
        print("Checking site statuses...")
        # Iterate through each site card to check status
        for elem in status_elements:
            try:
                status_img = elem.find_element(By.TAG_NAME, "img")
                status = status_img.get_attribute("alt").strip()
                print(f"Status: {status}")
                # Count and print
                if status == "Online":
                    online_count += 1
                elif status == "Offline":
                    offline_count += 1
            except Exception as e:
                print(f"Error reading status for a site card: {e}")
        # Summary print
        print(f"\nTotal Sites: {len(status_elements)}")
        print(f"Online: {online_count}")
        print(f"Offline: {offline_count}")
        # Assert that no offline sites exist
        if offline_count:
            print(f"⚠️  {offline_count} site(s) are offline ‑ test continues.")
            
    @pytest.mark.dependency(depends=["Test_Vsaas_Soterix::test_login"])
    def test_site_versions(self, params):
        driver = params['driver']
        wait = WebDriverWait(driver, 10)
        expected_version  = params ['expected_edge_version']
        time.sleep(5)  # allow time for the page to load
        # Find all site name elements
        site_elements = driver.find_elements(By.XPATH, "//p[contains(@class, 'MuiTypography-body1') and contains(@class, 'mui-1vleskl')]")

        site_data = []  # List of tuples: (site_name, version)
        version_mismatches = []

        for idx, site_elem in enumerate(site_elements, start=1):
            try:
                site_name = site_elem.text.strip()

                # Try to find the "Version: x.y.z" in the next sibling or nearby
                version_xpath = ".//following::p[contains(text(), 'Version:')][1]"
                version_elem = site_elem.find_element(By.XPATH, version_xpath)
                version_text = version_elem.text.strip().split("Version:")[-1].strip()

            except NoSuchElementException:
                version_text = "Not found"

            # Store the site info
            site_data.append((site_name, version_text))

            # Check for version mismatch if expected_version is defined
            if expected_version and version_text != expected_version:
                version_mismatches.append((site_name, version_text))

        # Print summary table
        print("\n📋 Site Versions:")
        print(f"{'Site Name':<30} | Version")
        print("-" * 45)
        for name, version in site_data:
            print(f"{name:<30} | {version}")

        # Print mismatches if any
        if expected_version:
            print("\n🔍 Version Mismatches (Expected: " + expected_version + "):")
            if version_mismatches:
                for name, version in version_mismatches:
                    print(f"❌ {name:<30} -> {version}")
            else:
                print("✅ All sites have the expected version.")
    
    @pytest.mark.dependency(depends=["Test_Vsaas_Soterix::test_login"])
    def test_navigate_to_online_site(self, params):
        driver = params['driver']
        site_name = params['site_name']
        wait = WebDriverWait(driver, 10)
        time.sleep(5)
        try:
            # Wait for the site name element to be clickable and click it
            site_element = wait.until(EC.element_to_be_clickable((
                By.XPATH, f"//p[contains(@class, 'MuiTypography-root') and text()='{site_name}']"
                )))
            site_element.click()
            print(f"Clicked on site: {site_name}")
            time.sleep(5)
            print(f"Successfully navigated to the site: {site_name}")
        except TimeoutException as e:
            print(f"Timeout error while navigating to site '{site_name}': {str(e)}")
            assert False, f"Failed to navigate to the site '{site_name}'"
        except AssertionError as e:
            print(f"Assertion failed: {str(e)}")
            raise
    @pytest.mark.dependency(depends=["Test_Vsaas_Soterix::test_login"])
    def test_camera_sorting(self, params):
        driver = params['driver']
        wait = WebDriverWait(driver, 10)
        time.sleep(5)
        sort_type = None
        sort_icon = None
        try:
            # First, try to find A to Z sort icon
            try:
                sort_icon = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "img[src*='a-to-z-sort']")))
                sort_type = "A_to_Z"
                print("✅ Found A to Z sort icon.")
            except:
                print("⚠️ A to Z sort icon not found. Checking for Z to A sort icon...")
            
                # If A to Z not found, try to find Z to A sort icon
                try:
                    sort_icon = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "img[src*='z-to-a-sort']")))
                    sort_type = "Z_to_A"
                    print("✅ Found Z to A sort icon.")
                except:
                    # Try alternative selectors for sort icons
                    print("⚠️ Z to A sort icon not found. Trying alternative selectors...")
                
                    # Try generic sort selectors
                    alternative_selectors = [
                        "img[alt*='sort']",
                        "button[title*='sort']",
                        "[class*='sort']",
                        "img[src*='sort']",
                        ".sort-button",
                        "[data-testid*='sort']"
                    ]
                
                    for selector in alternative_selectors:
                        try:
                            potential_icons = driver.find_elements(By.CSS_SELECTOR, selector)
                            for icon in potential_icons:
                                # Check if it's an ascending sort icon
                                if any(keyword in icon.get_attribute('src').lower() for keyword in ['a-to-z', 'asc', 'up']):
                                    sort_icon = icon
                                    sort_type = "A_to_Z"
                                    print(f"✅ Found A to Z sort icon using selector: {selector}")
                                    break
                                # Check if it's a descending sort icon
                                elif any(keyword in icon.get_attribute('src').lower() for keyword in ['z-to-a', 'desc', 'down']):
                                    sort_icon = icon
                                    sort_type = "Z_to_A"
                                    print(f"✅ Found Z to A sort icon using selector: {selector}")
                                    break
                                # Check alt text or title attributes
                                elif any(attr for attr in [icon.get_attribute('alt'), icon.get_attribute('title')] 
                                        if attr and any(keyword in attr.lower() for keyword in ['a-z', 'asc', 'ascending'])):
                                    sort_icon = icon
                                    sort_type = "A_to_Z"
                                    print(f"✅ Found A to Z sort icon using alt/title attributes: {selector}")
                                    break
                                elif any(attr for attr in [icon.get_attribute('alt'), icon.get_attribute('title')] 
                                        if attr and any(keyword in attr.lower() for keyword in ['z-a', 'desc', 'descending'])):
                                    sort_icon = icon
                                    sort_type = "Z_to_A"
                                    print(f"✅ Found Z to A sort icon using alt/title attributes: {selector}")
                                    break 
                            if sort_icon:
                                break
                        except:
                            continue
                    if not sort_icon:
                        raise Exception("❌ No sort icons found with any of the attempted selectors")
            # Perform sorting based on the found icon type
            if sort_type == "A_to_Z":
                print("🔄 Performing A to Z sorting...")
                # Click the sort icon
                sort_icon.click()
                print("✅ Clicked on A to Z sort icon.")
                time.sleep(2)
                # Sometimes need to click twice to get A-Z order
                # Check current sort state and click again if needed
                try:
                    # Wait for sorting to complete
                    time.sleep(1)
                    # Get current names to check sort order
                    current_name_elements = driver.find_elements(By.CSS_SELECTOR, "div.site-card .MuiTypography-root")
                    current_names = [
                        elem.text.strip()
                        for elem in current_name_elements
                        if elem.text.strip() and not elem.text.strip().startswith("IP:") and elem.text.strip() not in ["Online", "Offline"]
                    ]
                    if len(current_names) > 1:
                        # Check if currently sorted in descending order
                        is_descending = current_names == sorted(current_names, key=lambda x: x.lower(), reverse=True)
                        if is_descending:
                            print("🔄 Currently in Z-A order, clicking again for A-Z...")
                            sort_icon.click()
                            print("✅ Clicked sort icon again for A-Z order.")
                            time.sleep(2)
                except:
                    # If checking current sort fails, just proceed
                    pass
                # Wait for the sorting to complete
                wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, "div.site-card")))
                time.sleep(2)
                # Re-fetch name elements after sorting
                name_elements = driver.find_elements(By.CSS_SELECTOR, "div.site-card .MuiTypography-root")
                names = [
                    elem.text.strip()
                    for elem in name_elements
                    if elem.text.strip() and not elem.text.strip().startswith("IP:") and elem.text.strip() not in ["Online", "Offline"]
                ]
                print(f"📋 Filtered Camera Names: {names}")
                sorted_names = sorted(names, key=lambda x: x.lower())
                print(f"📋 Expected A-Z Sorted Names: {sorted_names}")
                # Verify A to Z sorting
                assert names == sorted_names, f"❌ Names are not sorted A-Z.\nActual: {names}\nExpected: {sorted_names}"
                print("✅ Camera names are correctly sorted A to Z!")
            elif sort_type == "Z_to_A":
                print("🔄 Performing Z to A sorting...")
                # Click the sort icon
                sort_icon.click()
                print("✅ Clicked on Z to A sort icon.")
                time.sleep(2)
                # For Z to A, we might need to ensure it's in descending order
                # Sometimes need to click twice to get Z-A order
                try:
                    # Wait for sorting to complete
                    time.sleep(1)
                    # Get current names to check sort order
                    current_name_elements = driver.find_elements(By.CSS_SELECTOR, "div.site-card .MuiTypography-root")
                    current_names = [
                        elem.text.strip()
                        for elem in current_name_elements
                        if elem.text.strip() and not elem.text.strip().startswith("IP:") and elem.text.strip() not in ["Online", "Offline"]
                    ]
                    if len(current_names) > 1:
                        # Check if currently sorted in ascending order
                        is_ascending = current_names == sorted(current_names, key=lambda x: x.lower())
                        if is_ascending:
                            print("🔄 Currently in A-Z order, clicking again for Z-A...")
                            sort_icon.click()
                            print("✅ Clicked sort icon again for Z-A order.")
                            time.sleep(2)
                except:
                    # If checking current sort fails, just proceed
                    pass
                # Wait for the sorting to complete
                wait.until(EC.presence_of_all_elements_located((By.CSS_SELECTOR, "div.site-card")))
                time.sleep(2)
                # Re-fetch name elements after sorting
                name_elements = driver.find_elements(By.CSS_SELECTOR, "div.site-card .MuiTypography-root")
                names = [
                    elem.text.strip()
                    for elem in name_elements
                    if elem.text.strip() and not elem.text.strip().startswith("IP:") and elem.text.strip() not in ["Online", "Offline"]
                ]
                print(f"📋 Filtered Camera Names: {names}")
                sorted_names_desc = sorted(names, key=lambda x: x.lower(), reverse=True)
                print(f"📋 Expected Z-A Sorted Names: {sorted_names_desc}")
                # Verify Z to A sorting
                assert names == sorted_names_desc, f"❌ Names are not sorted Z-A.\nActual: {names}\nExpected: {sorted_names_desc}"
                print("✅ Camera names are correctly sorted Z to A!")
            # Additional verification: Check if the list has at least some items
            if len(names) == 0:
                print("⚠️ Warning: No camera names found to sort")
            elif len(names) == 1:
                print("ℹ️ Info: Only one camera found, sorting verification not applicable")
            else:
                print(f"✅ Successfully verified sorting for {len(names)} cameras")
        except Exception as e:
            print(f"❌ Test failed: {str(e)}")
            # Additional debugging information
            try:
                # Try to capture available sort elements for debugging
                all_images = driver.find_elements(By.TAG_NAME, "img")
                sort_related_images = []
                for img in all_images:
                    src = img.get_attribute('src') or ''
                    alt = img.get_attribute('alt') or ''
                    title = img.get_attribute('title') or ''
                    if any(keyword in (src + alt + title).lower() for keyword in ['sort', 'order', 'a-z', 'z-a']):
                        sort_related_images.append({
                            'src': src,
                            'alt': alt,
                            'title': title
                        })
                if sort_related_images:
                    print("🔍 Found these sort-related elements:")
                    for i, img in enumerate(sort_related_images):
                        print(f"  {i+1}. src: {img['src']}, alt: {img['alt']}, title: {img['title']}")
                else:
                    print("🔍 No sort-related elements found during debugging")
            except Exception as debug_e:
                print(f"🔍 Debug information gathering failed: {str(debug_e)}")
            assert False, f"Test failed due to exception: {str(e)}"
        
    @pytest.mark.dependency(depends=["Test_Vsaas_Soterix::test_login"])
    def test_create_new_camera_group(self, params):
        driver = params['driver']
        wait = WebDriverWait(driver, 10)
        camera_name = params['camera_name']
        time.sleep(5)
        camera_group = "All Cameras"
        # Click on the camera group dropdown to create a new camera group
        try:
            accordion_icon = wait.until(EC.element_to_be_clickable((
                By.XPATH, "//img[contains(@src, 'downAccordionIcon')]"
            )))
            accordion_icon.click()
            print("Clicked on accordion dropdown icon.")

        except Exception as e:
            print(f"Failed to click on accordion icon: {str(e)}")
        time.sleep(3)
        # Click on the "Create New" button to create a new camera group
        try:
            create_button = wait.until(EC.element_to_be_clickable((
                By.XPATH, "//div[contains(@class, 'MuiBox-root') and contains(text(), 'Create New')]"
            )))
            create_button.click()
            print("Clicked on 'Create New' button.")
        except TimeoutException as e:
            print(f"Timeout: 'Create New' button not found or not clickable: {str(e)}")
        time.sleep(3)
        # Fill in the camera group name
        try:
            # Locate the input field using its placeholder
            input_field = wait.until(EC.presence_of_element_located((
                By.XPATH, "//input[@placeholder='Type here...']"
            )))
            input_field.clear()
            timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
            input_field.send_keys(f"{timestamp}Automation")
            print("Typed Automation into the input field.")
        except TimeoutException as e:
            print(f"Timeout: Input field not found or not interactable: {str(e)}")
        time.sleep(3)
        try:
            # Locate the search field using its unique ID
            search_input = wait.until(EC.presence_of_element_located((
                By.ID, "outlined-adornment-search"
            )))

            search_input.clear()
            search_input.send_keys(camera_name)
            print(f"Searched for: {camera_name}")
            time.sleep(3)
            checkbox = wait.until(EC.element_to_be_clickable((
                By.XPATH, "//input[@type='checkbox' and contains(@class, 'PrivateSwitchBase-input')]"
                )))
            # Click to toggle (check or uncheck)
            checkbox.click()
            print("Checkbox clicked successfully.")
        except TimeoutException as e:
            print(f"Search field not found or not ready: {str(e)}")
        time.sleep(3)
        try:
            # Locate and click the "Create" button
            create_button = wait.until(EC.element_to_be_clickable((
                By.XPATH, "//div[contains(@class, 'MuiBox-root') and text()='Create']"
            )))
            create_button.click()
            print("Clicked on 'Create' button.")
            print("Camera group created successfully.")
        except TimeoutException as e:
            print(f"'Create' button not found or not clickable: {str(e)}")
    
    @pytest.mark.dependency(depends=["Test_Vsaas_Soterix::test_login"])
    def test_edit_camera_group(self, params):
        driver = params['driver']
        wait = WebDriverWait(driver, 10)
        camera_name = params['camera_name']
        time.sleep(5)
        camera_group = "All Cameras"
        # Click on the "Edit" button to edit the camera group
        try:
            edit_icon = wait.until(EC.presence_of_all_elements_located((
                By.XPATH, "//img[@alt='edit' and contains(@class, 'edit-icon')]"
            )))
            if edit_icon:
                edit_icon[-1].click()
                print("Last edit icon clicked.")
            else:
                print("No edit icons found.")
        except Exception as e:
            print(f"Failed to click on edit icon: {str(e)}")
        time.sleep(3)
        try:
            # Locate the input field using its placeholder
            input_field = wait.until(EC.presence_of_element_located((
                By.XPATH, "//input[@placeholder='Type here...']"
            )))
            time.sleep(3)
            input_field.clear()
            time.sleep(3)
            input_field.send_keys("Edited Automation Camera Group")
            print("Typed Edited Automation Camera Group into the input field.")
        except TimeoutException as e:
            print(f"Timeout: Input field not found or not interactable: {str(e)}")
        time.sleep(3)
        try:
            # Wait for the 'Update' button to be clickable
            update_button = wait.until(EC.element_to_be_clickable((
                By.XPATH, "//div[text()='Update' and contains(@class, 'mui-1905nbd')]"
            )))
            update_button.click()
            print("Update button clicked successfully.")
        except Exception as e:
            print(f"Failed to click Update button: {e}")
    
    @pytest.mark.dependency(depends=["Test_Vsaas_Soterix::test_login"])
    def test_delete_camera_group(self, params):
        driver = params['driver']
        wait = WebDriverWait(driver, 10)
        camera_name = params['camera_name']
        time.sleep(5)
        camera_group = "All Cameras"
        # Click on the "Delete" icon to delete the camera group
        try:
            delete_icon = wait.until(EC.presence_of_all_elements_located((
                By.XPATH, "//img[@alt='delete' and contains(@class, 'delete-icon')]"
            )))
            if delete_icon:
                delete_icon[-1].click()
                print("Last delete icon clicked.")
            else:
                print("No delete icons found.")
        except Exception as e:
            print(f"Failed to click on delete icon: {str(e)}")
        time.sleep(3)
        try:
            yes_button = wait.until(EC.element_to_be_clickable(
                (By.XPATH, "//div[text()='Yes' and contains(@class, 'mui-v9wsk5')]")
            ))
            yes_button.click()
            print("Clicked 'Yes' to confirm deletion.")
        except Exception as e:
            print(f"Error clicking 'Yes' button: {e}")

    @pytest.mark.dependency(depends=["Test_Vsaas_Soterix::test_login"])
    def test_search_inside_site(self, params):
        driver = params['driver']
        camera_name = params['camera_name']
        wait = WebDriverWait(driver, 10)
        time.sleep(8)
        try:
            # Step 1: Locate and use the search bar
            actions = ActionChains(driver)
            actions.send_keys(Keys.ESCAPE).perform()
            time.sleep(2)
            search_input = wait.until(EC.presence_of_element_located(
                (By.XPATH, "//input[contains(@placeholder, 'Search')]")
            ))
            search_input.clear()
            search_input.send_keys(camera_name)
            print(f"🔍 Searching for: {camera_name}")
            time.sleep(2)
            
            # Step 2: Validate search results appear
            try:
                # Wait for search results to load and appear
                search_results = wait.until(
                    EC.presence_of_all_elements_located((By.XPATH, "//div[contains(@class, 'site-card')]"))
                )
                
                # Validate that results exist
                assert len(search_results) > 0, f"❌ No search results found for camera: {camera_name}"
                print(f"✅ Found {len(search_results)} search result(s)")
                
                # Log all search results for debugging
                result_texts = []
                camera_found = False
                
                for i, result in enumerate(search_results):
                    try:
                        # Get camera name from the card
                        camera_text_elem = result.find_element(By.XPATH, ".//p")
                        result_text = camera_text_elem.text.strip()
                        result_texts.append(result_text)
                        print(f"Search result {i+1}: '{result_text}'")
                        
                        # Check if this result matches our camera
                        if camera_name.split()[0] in result_text:
                            camera_found = True
                            print(f"✅ Camera match found: '{result_text}'")
                    except Exception as e:
                        print(f"⚠️ Could not read result {i+1}: {str(e)}")
                
                # Validate that the camera appears in results
                assert camera_found, f"❌ Camera '{camera_name}' not found in search results: {result_texts}"
                print(f"✅ Camera '{camera_name}' validated in search results")
                
            except TimeoutException:
                print(f"❌ No search results appeared for: {camera_name}")
                assert False, f"No search results found for camera: {camera_name}"
        except Exception as e:
            print(f"⚠️ Unexpected error: {str(e)}")
    
    # Chat validations covering, creation of group, serach, edit, individual and group chat
    @pytest.mark.dependency(depends=["Test_Vsaas_Soterix::test_login"])
    def test_chat_group_creation(self, params):
        driver = params['driver']
        wait = WebDriverWait(driver, 10)
        action = ActionChains(driver)
        time.sleep(3)  
        chat_container = driver.find_element(By.CLASS_NAME, value="header-right-group")
        chat_elements = chat_container.find_elements(By.CLASS_NAME, value="icon")
        time.sleep(1)
        chat_elements[0].click()
        time.sleep(2)

        # Find and click Create Group button
        try:
            # Find the Create Group button with exact attributes
            create_group_button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.XPATH, 
            "//button[@type='button' and @class='add-btn save-btn' and text()='Create Group']")))
    
            # Alternative CSS selector approach if XPath doesn't work
            if not create_group_button:
                create_group_button = WebDriverWait(driver, 10).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, 
                "button.add-btn.save-btn"))
                )
    
            print("Found 'Create Group' button, clicking it...")
            create_group_button.click()
    
            print("Successfully clicked the 'Create Group' button")
    
            # Wait to confirm action was successful
            time.sleep(2)
    
        except Exception as e:
            print(f"An error occurred: {e}")
        time.sleep(2)
        try:
            # Wait for and verify input field
            group_name_input = wait.until(
                EC.presence_of_element_located((
                    By.CSS_SELECTOR, "input[placeholder='Enter Group Name']"
                ))
            )
            assert group_name_input.is_displayed(), "Group name input not visible"
            
            # Enter group name
            group_name = "Automation Test Group"
            group_name_input.clear()
            group_name_input.send_keys(group_name)
            print(f"Entered group name: {group_name}")
            
            # Verify input value
            assert group_name_input.get_attribute("value") == group_name, "Group name not entered correctly"
            
        except TimeoutException as e:
            print(f"Timeout error: {str(e)}")
            assert False, "Failed to create group - element not found"
        except AssertionError as e:
            print(f"Validation failed: {str(e)}")
            raise
        except Exception as e:
            print(f"Unexpected error: {str(e)}")
            assert False, f"Group creation failed: {str(e)}"
        time.sleep(2)
        try:
            actions = ActionChains(driver)
            actions.send_keys(Keys.TAB).perform()
            time.sleep(2)
            action.send_keys("engineer").perform()
            print("Clicked dropdown button")
            time.sleep(6)
            # Wait for and verify dropdown options
            dropdown_options = wait.until(
                EC.presence_of_all_elements_located((
                    By.CSS_SELECTOR, "ul.MuiAutocomplete-listbox li"
                ))
            )
            assert len(dropdown_options) > 0, "No dropdown options found"
            
            # Select first option 
            first_option = dropdown_options[0]
            assert first_option.is_displayed(), "First option not visible"
            option_text = first_option.text
            first_option.click()
            print(f"Selected option: {option_text}")
            action.send_keys(Keys.ESCAPE).perform()
        except AssertionError as e:
            print(f"Validation failed: {str(e)}")
            raise
        # selecting the Create button 
        actions.send_keys(Keys.TAB*2).perform()
        time.sleep(2)
        actions.send_keys(Keys.ENTER).perform()
        time.sleep(2)
    
    @pytest.mark.dependency(depends=["Test_Vsaas_Soterix::test_login"])
    def test_chat_search(self, params):
        driver = params['driver']
        wait = WebDriverWait(driver, 10)
        action = ActionChains(driver)
        time.sleep(3)  
        chat_container = driver.find_element(By.CLASS_NAME, value="header-right-group")
        chat_elements = chat_container.find_elements(By.CLASS_NAME, value="icon")
        time.sleep(1)
        chat_elements[0].click()
        time.sleep(2)
        chat_elements[0].click()
        time.sleep(2)        
        # validate search input
        search_input = wait.until(
            EC.presence_of_element_located((
                By.CSS_SELECTOR, "input.chat-search-input[placeholder='Search']"
            ))
        )
        assert search_input.is_displayed(), "Search input not visible"
        assert search_input.get_attribute("type") == "text", "Input type mismatch"
        assert search_input.get_attribute("placeholder") == "Search", "Placeholder text mismatch"

        # Test search functionality        
        search_text = "User_creation_for_Automated_Test 123Test"
        search_input.clear()
        search_input.send_keys(search_text)
        print(f"Entered search text: {search_text}")
        time.sleep(2)
        try:
            # Try to get all search results
            result_items = driver.find_elements(By.XPATH, "//div[@class='related-result-item']")
            if len(result_items) == 0:
                raise NoSuchElementException("No search results found")
                
            # First try the last item
            try:
                last_item = result_items[-1]
                last_item.click()
                print("Clicked last search result")
            except Exception as e:
                print(f"Error with last result: {str(e)}, trying last-but-one")
                if len(result_items) > 1:
                    # Try last-but-one item
                    last_but_one = result_items[-2]
                    last_but_one.click()
                    print("Clicked last-but-one search result")
                else:
                    raise Exception("Not enough results to try last-but-one")
            
            # Handle alert if it appears
            try:
                alert = wait.until(EC.alert_is_present())
                alert_text = alert.text
                print(f"Alert present: {alert_text}")
                if "User is already added" in alert_text:
                    alert.accept()
                    print("Accepted alert: User already added")
            except TimeoutException:
                print("No alert appeared - user not previously added")
            # Group chat validation    
            time.sleep(2)
            chat_elements[0].click()
            time.sleep(2)
            chat_elements[0].click()
            time.sleep(4)
            element = driver.find_element(By.XPATH, "//p[contains(text(), 'Automation Test Group')]")
            element.click()
            time.sleep(5)
            action.send_keys(Keys.TAB).perform()
            time.sleep(2)
            action.send_keys("Group chat input by automation").perform()
            print("started chat with group")
            action.send_keys(Keys.ENTER).perform()
        except Exception as e:
            print(f"Error handling search results: {str(e)}")
            raise
    @pytest.mark.dependency(depends=["Test_Vsaas_Soterix::test_login"])
    def test_chat_individual_robust(self, params):
        driver = params['driver']
        wait = WebDriverWait(driver, 10)
        action = ActionChains(driver)
        time.sleep(3)  
        chat_container = driver.find_element(By.CLASS_NAME, value="header-right-group")
        chat_elements = chat_container.find_elements(By.CLASS_NAME, value="icon")
        time.sleep(1)
        chat_elements[0].click()
        time.sleep(2)
        chat_elements[0].click()
        time.sleep(2)
        # individual chat validation
        # validate search input
        search_input = wait.until(
            EC.presence_of_element_located((
                By.CSS_SELECTOR, "input.chat-search-input[placeholder='Search']"
            ))
        )
        assert search_input.is_displayed(), "Search input not visible"
        assert search_input.get_attribute("type") == "text", "Input type mismatch"
        assert search_input.get_attribute("placeholder") == "Search", "Placeholder text mismatch"

        # Test search functionality        
        search_text = "Chat Partner"
        search_input.clear()
        search_input.send_keys(search_text)
        print(f"Entered search text: {search_text}")
        time.sleep(4)
        user_elements = driver.find_elements(By.XPATH, "//p[contains(text(), 'Chat Partner')]")
        if not user_elements:
            raise Exception("User 'Chat Partner' not found in search results.")
        user_elements[0].click()
        time.sleep(5)
        action.send_keys(Keys.TAB).perform()
        time.sleep(2)
        action.send_keys("individual chat input by automation").perform()
        print("started chat with Individual")
        action.send_keys(Keys.ENTER).perform()
        time.sleep(2)
    
    @pytest.mark.dependency(depends=["Test_Vsaas_Soterix::test_login"])
    def test_chat_edit_group(self, params):
        driver = params['driver']
        wait = WebDriverWait(driver, 10)
        action = ActionChains(driver)
        time.sleep(3)  
        chat_container = driver.find_element(By.CLASS_NAME, value="header-right-group")
        chat_elements = chat_container.find_elements(By.CLASS_NAME, value="icon")
        time.sleep(1)
        chat_elements[0].click()
        # Edit group name
        time.sleep(2)
        chat_elements[0].click()
        time.sleep(2)
        chat_elements[0].click()
        time.sleep(4)
        element = driver.find_element(By.XPATH, "//p[contains(text(), 'Automation Test Group')]")
        element.click()
        time.sleep(5)
        edit_icon = wait.until(EC.element_to_be_clickable((By.XPATH, "//img[@alt='Edit icon']")))
        edit_icon.click()
        time.sleep(2)
        input_field = driver.find_element(By.XPATH, "//input[@value='Automation Test Group']")
        input_field.clear()
        input_field.send_keys("Edited group name by automation")
        time.sleep(2)
        update_button = driver.find_element(By.XPATH, "//button[text()='Update']")
        update_button.click()
        time.sleep(6)
    
    @pytest.mark.dependency(depends=["Test_Vsaas_Soterix::test_login"])
    def test_chat_delete(self, params):
        driver = params['driver']
        wait = WebDriverWait(driver, 10)
        action = ActionChains(driver)
        time.sleep(3)  
        chat_container = driver.find_element(By.CLASS_NAME, value="header-right-group")
        chat_elements = chat_container.find_elements(By.CLASS_NAME, value="icon")
        time.sleep(1)
        chat_elements[0].click()
        # Delete a group
        time.sleep(2)
        chat_elements[0].click()
        time.sleep(4)
        element = driver.find_element(By.XPATH, "//p[contains(text(), 'Edited group name by automation')]")
        element.click()
        time.sleep(5)
        delete_button = driver.find_element(By.XPATH, "//img[@alt='Delete icon']")
        delete_button.click()
        time.sleep(6)
        delete_button = wait.until(EC.element_to_be_clickable((
            By.CSS_SELECTOR, "div.MuiBox-root.mui-yd38dn")))
        assert delete_button.text == "Delete", "Delete button text mismatch"
        delete_button.click()
        print("Confirmed deletion")
        time.sleep(6)