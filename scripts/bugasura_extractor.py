"""
Bugasura Test Case Extractor
Extracts test cases from Bugasura web interface using Playwright
"""

import json
import time
from datetime import datetime
from playwright.sync_api import sync_playwright, Page

# Configuration
BUGASURA_URL = "https://my.bugasura.io/testCases/120847/repos"
OUTPUT_FILE = "testcases_export.json"
PROGRESS_FILE = "extraction_progress.json"

def load_existing_data():
    """Load existing export data if available"""
    try:
        with open(OUTPUT_FILE, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {
            "project": "NEXAIQ_VSAAS",
            "export_date": datetime.now().strftime("%Y-%m-%d"),
            "total_count": 0,
            "test_cases": []
        }

def save_data(data):
    """Save export data to file"""
    with open(OUTPUT_FILE, 'w') as f:
        json.dump(data, f, indent=2)
    print(f"Saved {data['total_count']} test cases to {OUTPUT_FILE}")

def load_progress():
    """Load extraction progress"""
    try:
        with open(PROGRESS_FILE, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {
            "completed_folders": [],
            "current_folder": None,
            "total_extracted": 0,
            "last_test_id": None
        }

def save_progress(progress):
    """Save extraction progress"""
    progress["last_updated"] = datetime.now().isoformat()
    with open(PROGRESS_FILE, 'w') as f:
        json.dump(progress, f, indent=2)

def extract_test_case_details(page: Page) -> dict:
    """Extract details from an open test case modal"""
    test_case = {}

    # Wait for modal to be fully loaded
    page.wait_for_selector('[class*="modal"]', timeout=5000)
    time.sleep(0.5)

    # Extract title (from the modal header)
    try:
        title_el = page.query_selector('h1, h2, [class*="title"]')
        test_case["title"] = title_el.inner_text().strip() if title_el else ""
    except:
        test_case["title"] = ""

    # Extract folder tags (breadcrumb-like elements)
    try:
        folder_tags = page.query_selector_all('[class*="tag"], [class*="chip"], [class*="badge"]')
        if len(folder_tags) >= 2:
            test_case["folder"] = folder_tags[0].inner_text().strip()
            test_case["subFolder"] = folder_tags[1].inner_text().strip()
        elif len(folder_tags) == 1:
            test_case["folder"] = folder_tags[0].inner_text().strip()
            test_case["subFolder"] = ""
        else:
            test_case["folder"] = ""
            test_case["subFolder"] = ""
    except:
        test_case["folder"] = ""
        test_case["subFolder"] = ""

    # Extract priority
    try:
        priority_el = page.query_selector('[class*="priority"], [class*="HIGH"], [class*="MEDIUM"], [class*="LOW"], [class*="CRITICAL"]')
        test_case["priority"] = priority_el.inner_text().strip() if priority_el else "Medium"
    except:
        test_case["priority"] = "Medium"

    # Extract tags
    try:
        tags_container = page.query_selector('[class*="Functionality"], [class*="Security"], [class*="Usability"]')
        test_case["tags"] = [tags_container.inner_text().strip()] if tags_container else []
    except:
        test_case["tags"] = []

    # Extract Test Idea
    try:
        test_idea_section = page.query_selector('text=Test Idea')
        if test_idea_section:
            parent = test_idea_section.evaluate('el => el.parentElement')
            next_p = page.query_selector('text=Test Idea >> .. >> p, text=Test Idea >> .. >> div')
            test_case["testIdea"] = next_p.inner_text().strip() if next_p else ""
    except:
        test_case["testIdea"] = ""

    # Extract Test Conditions
    try:
        conditions_text = page.locator('text=Test Conditions').first
        test_case["testConditions"] = ""
    except:
        test_case["testConditions"] = ""

    # Extract Acceptance Criteria
    try:
        test_case["acceptanceCriteria"] = ""
    except:
        test_case["acceptanceCriteria"] = ""

    # Extract Steps
    try:
        steps = []
        step_elements = page.query_selector_all('[class*="step"], [class*="Step"]')
        for step_el in step_elements:
            step_text = step_el.inner_text().strip()
            if step_text and not step_text.startswith("Step"):
                steps.append(step_text)
        test_case["steps"] = steps
    except:
        test_case["steps"] = []

    return test_case

def extract_all_test_cases(page: Page, folder_name: str, data: dict, progress: dict):
    """Extract all test cases from the current folder view"""

    # Get all test case rows
    test_rows = page.query_selector_all('[class*="test-case-row"], tr[class*="row"]')

    for row in test_rows:
        try:
            # Click on the test case title to open modal
            title_link = row.query_selector('a, [class*="title"]')
            if title_link:
                title_link.click()
                time.sleep(1)

                # Extract details
                test_case = extract_test_case_details(page)
                test_case["folder"] = folder_name

                # Add to data if not duplicate
                existing_titles = [tc["title"] for tc in data["test_cases"]]
                if test_case["title"] and test_case["title"] not in existing_titles:
                    data["test_cases"].append(test_case)
                    data["total_count"] = len(data["test_cases"])
                    save_data(data)
                    print(f"Extracted: {test_case['title']}")

                # Close modal
                close_btn = page.query_selector('[class*="close"], button:has-text("Cancel"), button:has-text("×")')
                if close_btn:
                    close_btn.click()
                else:
                    page.keyboard.press("Escape")
                time.sleep(0.5)
        except Exception as e:
            print(f"Error extracting test case: {e}")
            page.keyboard.press("Escape")
            time.sleep(0.5)

def main():
    print("=" * 60)
    print("Bugasura Test Case Extractor")
    print("=" * 60)

    # Load existing data
    data = load_existing_data()
    progress = load_progress()

    print(f"Existing test cases: {data['total_count']}")

    with sync_playwright() as p:
        # Launch browser (use headed mode so you can login if needed)
        browser = p.chromium.launch(headless=False)
        context = browser.new_context()
        page = context.new_page()

        # Navigate to Bugasura
        print(f"Navigating to {BUGASURA_URL}")
        page.goto(BUGASURA_URL)

        # Wait for user to login if needed
        print("\n" + "=" * 60)
        print("MANUAL STEP REQUIRED:")
        print("1. If not logged in, please login to Bugasura")
        print("2. Navigate to the Test Cases page")
        print("3. Press ENTER in this terminal when ready to start extraction")
        print("=" * 60)
        input("\nPress ENTER to start extraction...")

        # Get list of folders from sidebar
        folder_elements = page.query_selector_all('[class*="folder"], [class*="tree-item"]')
        folders = []
        for f in folder_elements:
            name = f.inner_text().strip()
            if name:
                folders.append(name)

        print(f"\nFound {len(folders)} folders")

        # Extract from each folder
        for folder_name in folders:
            if folder_name in progress.get("completed_folders", []):
                print(f"Skipping {folder_name} (already completed)")
                continue

            print(f"\nExtracting from folder: {folder_name}")
            progress["current_folder"] = folder_name
            save_progress(progress)

            # Click on folder
            folder_link = page.query_selector(f'text="{folder_name}"')
            if folder_link:
                folder_link.click()
                time.sleep(1)

                # Extract test cases
                extract_all_test_cases(page, folder_name, data, progress)

                # Mark folder as complete
                if "completed_folders" not in progress:
                    progress["completed_folders"] = []
                progress["completed_folders"].append(folder_name)
                progress["total_extracted"] = data["total_count"]
                save_progress(progress)

        print("\n" + "=" * 60)
        print(f"Extraction complete! Total test cases: {data['total_count']}")
        print(f"Output saved to: {OUTPUT_FILE}")
        print("=" * 60)

        browser.close()

if __name__ == "__main__":
    main()
