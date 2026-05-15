# Bugasura Test Case Extraction - Session Continuation

## Current Progress
- **Total Extracted:** 543 test cases
- **Last Batch:** batch_save63.py
- **Last Test Case ID:** TES344 (Maps folder complete)

## Completed Folders
- ✅ Login
- ✅ Chats
- ✅ Notifications
- ✅ Logout
- ✅ Views
- ✅ Events
- ✅ Search (118 test cases)
- ✅ LPR (25 test cases)
- ✅ Maps (16 test cases)

## In Progress
- 🔄 **Insights** (37 test cases total, 0 extracted)
  - Visible: TES380-TES396
  - Subfolders: Widgets, My Dashboards

## Remaining Folders
- ⬜ Insights (37 test cases)

## Browser State
- Tab ID: 492638011
- URL: https://my.bugasura.io/testCases/120847/repos
- Currently viewing: Insights folder

## To Continue

### Command to Start New Session
```bash
tooling --dangerously-skip-permissions
```

### Startup Prompt (copy this entire block):
```
Continue Bugasura test case extraction from previous session.

CURRENT STATE:
- Total extracted: 543 test cases
- Last batch: batch_save63.py
- Completed: Login, Chats, Notifications, Logout, Views, Events, Search, LPR, Maps
- IN PROGRESS: Insights folder (37 test cases, starting from TES360)
- Browser Tab ID: 492638011

REQUIREMENTS:
- Auto-yes all confirmations
- Auto-save every 5-7 test cases
- Extract silently (no per-test-case commentary)
- Status updates only
- Use --dangerously-skip-permissions mode

EXTRACTION FORMAT:
Each test case needs: id, title, folder, subfolder, priority, tags, test_data, test_idea, test_conditions, acceptance_criteria, steps

FILES:
- Export JSON: C:\Users\JustinVarughese\QA-Automation\playwright-soterix-qa\testcases_export.json
- Batch scripts: C:\Users\JustinVarughese\QA-Automation\playwright-soterix-qa\batch_scripts\

ACTION: Open Insights folder in Bugasura (Tab 492638011) and extract all 37 test cases efficiently. Start with TES360 and work up to TES396.
```

## Test Case Structure
```python
{
    "id": "TESxxx",
    "title": "...",
    "folder": "Insights",
    "subfolder": "...",
    "priority": "High/Medium/Low/Critical",
    "tags": ["Functionality"],
    "test_data": [{"key": "...", "value": "..."}],
    "test_idea": "...",
    "test_conditions": "...",
    "acceptance_criteria": "...",
    "steps": ["Step 1", "Step 2", ...]
}
```

## Batch Script Template
```python
import json

new_test_cases = [
    # Add test cases here
]

with open(r'C:\Users\JustinVarughese\QA-Automation\playwright-soterix-qa\testcases_export.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

data['test_cases'].extend(new_test_cases)
data['total_count'] = len(data['test_cases'])

with open(r'C:\Users\JustinVarughese\QA-Automation\playwright-soterix-qa\testcases_export.json', 'w', encoding='utf-8') as f:
    json.dump(data, f, indent=2)

print(f"Added {len(new_test_cases)} test cases. Total: {data['total_count']}")
```

## Notes
- Insights folder has subfolders: Widgets, My Dashboards
- Test case IDs visible: TES360-TES396 (37 total)
- Next batch file: batch_save64.py
