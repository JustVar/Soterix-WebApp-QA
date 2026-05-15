# QA Touch Import Comparison Tool Guide

## Purpose

This tool compares incoming Excel or CSV files against the QA Touch master CSV to ensure:
- All test cases are properly identified
- Test steps are mapped to the correct test cases
- No duplicates or missing entries exist

---

## Prerequisites

### 1. Python Installation

Check if Python is installed:
```bash
python --version
```

If not installed, download from: https://www.python.org/downloads/

### 2. Required Libraries

Open Command Prompt (Windows) or Terminal and run:
```bash
pip install pandas openpyxl
```

**What these do:**
- `pandas` - Reads and processes Excel/CSV files
- `openpyxl` - Enables Excel file support (.xlsx)

---

## File Locations

| File | Location |
|------|----------|
| compare_import.py | `C:\Users\JustinVarughese\QA-Automation\playwright-soterix-qa\` |
| qa_touch_import.csv | `C:\Users\JustinVarughese\QA-Automation\playwright-soterix-qa\tests\data\` |
| Incoming files | Place in same folder or provide full path |

---

## Step-by-Step Usage

### Step 1: Open Command Prompt

1. Press `Windows + R`
2. Type `cmd` and press Enter

### Step 2: Navigate to the Project Folder

```bash
cd C:\Users\JustinVarughese\QA-Automation\playwright-soterix-qa
```

### Step 3: Run the Comparison

**Basic command:**
```bash
python compare_import.py <incoming_file> tests/data/qa_touch_import.csv
```

**Example with an Excel file:**
```bash
python compare_import.py new_tests.xlsx tests/data/qa_touch_import.csv
```

**Example with a CSV file:**
```bash
python compare_import.py updated_tests.csv tests/data/qa_touch_import.csv
```

---

## Column Name Options

If your incoming file uses different column names, specify them:

```bash
python compare_import.py new_tests.xlsx tests/data/qa_touch_import.csv --incoming-title "Test Name" --incoming-module "Category"
```

### Available Options

| Option | Default | Description |
|--------|---------|-------------|
| `--incoming-title` | title | Column name for test case title in incoming file |
| `--incoming-module` | module | Column name for module in incoming file |
| `--qa-title` | title | Column name for title in QA Touch CSV |
| `--qa-module` | module | Column name for module in QA Touch CSV |
| `--export` / `-e` | (none) | Export results to Excel file |
| `--verbose` / `-v` | (off) | Show matched entries in output |

---

## Understanding the Output

### Sample Output

```
============================================================
QA TOUCH IMPORT COMPARISON TOOL
============================================================

Loading: new_tests.xlsx
  Rows: 150
  Columns: ['module', 'title', 'steps', 'expected_result']

Loading: qa_touch_import.csv
  Rows: 1550
  Columns: ['external_id', 'module', 'title', ...]

============================================================
COMPARISON RESULTS
============================================================

MATCHED:                  145 test cases
IN INCOMING ONLY:         5 test cases
IN QA TOUCH ONLY:         0 test cases

[!] 5 new test cases need to be added to QA Touch
```

### What Each Section Means

| Section | Meaning | Action Required |
|---------|---------|-----------------|
| **MATCHED** | Test cases exist in both files | None - these are aligned |
| **IN INCOMING ONLY** | New tests not in QA Touch yet | Import these to QA Touch |
| **IN QA TOUCH ONLY** | Tests missing from incoming file | Check if renamed or deleted |
| **POTENTIAL RENAMES** | Similar titles (>70% match) | Review for possible renames |

---

## Common Scenarios

### Scenario 1: Adding New Test Steps

You have an Excel file with test steps to add to existing test cases.

```bash
python compare_import.py test_steps_update.xlsx tests/data/qa_touch_import.csv
```

**Expected result:** High number of MATCHED entries. Any IN INCOMING ONLY entries need new test cases created first.

### Scenario 2: Validating Full Export

You exported all test cases from another system and want to verify completeness.

```bash
python compare_import.py full_export.xlsx tests/data/qa_touch_import.csv
```

**Expected result:** All entries should be MATCHED. Any discrepancies indicate missing or renamed tests.

### Scenario 3: Different Column Names

Your incoming file uses "Test Title" and "Feature" instead of "title" and "module".

```bash
python compare_import.py new_tests.xlsx tests/data/qa_touch_import.csv --incoming-title "Test Title" --incoming-module "Feature"
```

### Scenario 4: Export Results to Excel

Save detailed comparison results to an Excel file with separate sheets:

```bash
python compare_import.py new_tests.xlsx tests/data/qa_touch_import.csv --export comparison_results.xlsx
```

This creates an Excel file with sheets:
- **Matched** - All matched test cases
- **Incoming Only** - New tests not in QA Touch
- **QA Touch Only** - Tests missing from incoming
- **Potential Renames** - Similar titles that might be renames

---

## Troubleshooting

### Error: "Module not found: pandas"

**Solution:** Install the required library:
```bash
pip install pandas
```

### Error: "Module not found: openpyxl"

**Solution:** Install the required library:
```bash
pip install openpyxl
```

### Error: "Column 'title' not found in incoming file"

**Solution:** Check your incoming file's column names and use the `--incoming-title` option:
```bash
python compare_import.py file.xlsx tests/data/qa_touch_import.csv --incoming-title "Your Column Name"
```

### Error: "File not found"

**Solution:**
1. Check the file name is spelled correctly
2. Make sure you're in the correct folder
3. Use the full file path if needed:
```bash
python compare_import.py "C:\Full\Path\To\file.xlsx" tests/data/qa_touch_import.csv
```

### Output Shows Wrong Matches

**Possible causes:**
- Column names are incorrect
- Extra whitespace in titles
- Case sensitivity differences

**Solution:** The tool normalizes case and whitespace automatically. Check that column mapping is correct.

---

## Quick Reference

### Minimum Command
```bash
python compare_import.py incoming.xlsx tests/data/qa_touch_import.csv
```

### Full Command with All Options
```bash
python compare_import.py incoming.xlsx tests/data/qa_touch_import.csv --incoming-title "title" --incoming-module "module" --qa-title "title" --qa-module "module" --export results.xlsx --verbose
```

### Check Python Version
```bash
python --version
```

### Install Dependencies
```bash
pip install pandas openpyxl
```

---

## Version History

| Date | Version | Changes |
|------|---------|---------|
| 2026-02-02 | 1.0 | Initial creation |
