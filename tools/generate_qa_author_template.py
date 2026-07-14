"""
generate_qa_author_template.py
==============================

One-shot generator for the QA author template xlsx that sits at the front of
the QA Touch import pipeline (see ``docs/qa_import_pipeline.md`` phase 1 and
``docs/qa_xlsx_import_template.md``).

Why this script exists
----------------------
The pipeline runbook tells QA to copy ``tools/templates/qa_author_template.xlsx``
to ``tests/data/<release>_<module>_authored.xlsx`` and start filling in rows.
Shipping a pre-built workbook with the canonical headers, a worked-example row,
and an INSTRUCTIONS sheet means a new QA author opens it and is productive in
under a minute - no "what columns do I need?" round-trip with Ops.

The workbook produced here uses the 15 friendly Title-Case column names
QA already knows (``Module_name``, ``Test Case Title``, ``Description``,
``Tags``, ``Priority``, ``Mode``, ...) - matching the convention in the
in-the-wild authoring files (Partner_portal_testcases.xlsx,
sitedevice_authored.xlsx, ldap_authored.xlsx, etc.). At conversion time,
``tools/qa_xlsx_to_qatouch_csv.py`` translates these to the vendor-
canonical CSV slugs the QA Touch import wizard expects (including
routing ``Description`` -> ``test_description`` to side-step the vendor's
silently-dropped ``description`` slot - see
``docs/qa_touch_integration.md`` §7.A.1). The converter also accepts a
wider set of header aliases per ``docs/qa_xlsx_import_template.md`` so
legacy authoring files still convert.

Conversion default (since 2026-06-26): ``--format=migration-rows`` emits
the Data Migration single-row-per-step layout. Upload via
``/v2/case/migration/import/p/{pid}`` to get step rows pre-split at
import - Phase 5 step splitter retired. See ``docs/qa_import_pipeline.md``
Phase 3 Format B for the full path.

Usage
-----
Run once whenever the template needs to be (re)built::

    python tools/generate_qa_author_template.py

Writes to ``tools/templates/qa_author_template.xlsx`` (creating the directory
if missing). Re-running overwrites in place - the file is regenerated from the
constants below, never hand-edited.

Output layout
-------------
Sheet 1 - ``Test Cases``:
    Row 1: the 15 canonical column headers (bold, filled, frozen).
    Rows 2-N: 3 worked-example rows showing one Functional, one Negative, and
    one Security case so QA sees realistic shape (steps numbered, expected as
    a final assertion, pipe-delimited tags, `>`-separated module hierarchy).

Sheet 2 - ``INSTRUCTIONS``:
    Plain-text guidance: per-column meaning, enum reference values for Type /
    Priority / Mode / Tags, dos-and-don'ts (matching the QA author guide).

Dependencies
------------
Requires ``openpyxl`` (already a project dependency via the existing xlsx
converters).
"""
from __future__ import annotations

import sys
from pathlib import Path

try:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter
    from openpyxl.worksheet.datavalidation import DataValidation
except ImportError:
    print("ERROR: openpyxl is required. pip install openpyxl", file=sys.stderr)
    sys.exit(1)


ROOT = Path(__file__).resolve().parent.parent
OUTPUT_PATH = ROOT / "tools" / "templates" / "qa_author_template.xlsx"

# QA-facing 15-column header - friendly Title-Case names matching the
# convention QA already uses in the wild (Partner_portal_testcases.xlsx,
# sitedevice_authored.xlsx, ldap_authored.xlsx, etc.). The converter's
# alias tables resolve these to the vendor-canonical slugs at conversion
# time, so QA never has to think about the vendor's internal field names
# - including the `description` vs `test_description` trap (the converter
# routes the QA-friendly "Description" column to the CSV's
# `test_description` slot, which is the one the QA Touch UI shows as
# Description). See docs/qa_xlsx_import_template.md for the alias table
# and docs/qa_touch_integration.md §7.A.1/§7.A.2 for the wizard internals.
CANONICAL_COLUMNS = [
    "Module_name",        # use ` > ` for module nesting
    "Test Case Title",
    "Test Data",
    "Estimate",
    "Reference",          # uniformly TESTCASES_<Type>_NNN or similar; converter re-emits
    "Precondition",
    "Steps",              # numbered lines, one step per line, single cell
    "Expected_result",    # the final assertion; the splitter places this on the last step
    "Test Suite",         # leave blank; Ops assigns at the project level
    "Tags",               # pipe-delimited (e.g. "smoke|regression")
    "Description",        # case body / rationale - converter writes to test_description (the
                          # CSV slot that populates the user-visible Description in QA Touch)
    "Type",
    "Priority",
    "Mode",
    "Created By",
]

# Reference values that QA must use as-is (importer drops/rewrites unknowns).
TYPE_VALUES = [
    "Functional",
    "Negative",
    "Security",
    "Performance",
    "Regression",
    "Acceptance",
    "Automation",
]
PRIORITY_VALUES = ["Critical", "High", "Medium", "Low"]
MODE_VALUES = ["Manual", "Automation"]
TAG_VALUES = ["smoke", "sanity", "regression", "future"]

# Three worked examples - each a realistic case shape so a new QA author has a
# pattern to copy. Tags use pipe-delimiter. Module uses ` > ` nesting. Steps
# are numbered one-per-line (the converter strips the numbering). Expected is
# a single final assertion.
# Each case is a dict of metadata + a `steps_list` of (step_text, expected_text).
# The emission loop writes one row per step:
#   - The FIRST row carries the metadata + Step 1 + (Step 1's expected or blank).
#   - Subsequent rows have blank metadata, only Steps + Expected_result filled.
#   - The LAST row's Expected_result carries the case's final assertion.
# Intermediate Expected_result cells are left blank - the converter and
# QA Touch's data-migration importer apply the "last step is the
# assertion" convention. Authors can also write a per-step expected
# on every row if they want each step to carry its own.
EXAMPLE_CASES = [
    {
        "Module_name": "Customer Dashboard > KPI Summary",
        "Test Case Title": "Verify Customer Overview dashboard loads with KPI summary cards",
        "Test Data": "User: person@example.com",
        "Precondition": "User is logged in with valid credentials",
        "Tags": "smoke",
        "Description": (
            "Validate dashboard loads with Total Customers, Sites/Devices, and "
            "Total Licenses cards"
        ),
        "Type": "Functional",
        "Priority": "Critical",
        "Mode": "Manual",
        "Created By": "QA",
        "steps": [
            ("Launch the Soterix Partner Portal in a supported web browser.", ""),
            ("Log in with valid credentials and verify the Customer Overview dashboard is displayed.", ""),
            ("Verify the 'Total Customers' KPI card is displayed with a numeric count.", ""),
            ("Verify the 'Sites / Devices' KPI card is displayed with a numeric count.", ""),
            ("Verify the 'Total Licenses' KPI card is displayed with a numeric count.", ""),
            ("Verify each KPI card shows color-coded sub-metrics below the main count.",
             "Three KPI summary cards displayed with correct counts and color-coded status breakdowns"),
        ],
    },
    {
        "Module_name": "Login > Login Form > Negative Cases",
        "Test Case Title": "Verify login fails with invalid password and shows error message",
        "Test Data": "Email: adam.k@apex.com, Password: WrongPassword!",
        "Precondition": "Login page is displayed",
        "Tags": "regression",
        "Description": "Negative case covering password validation on Login form.",
        "Type": "Negative",
        "Priority": "Medium",
        "Mode": "Manual",
        "Created By": "QA",
        "steps": [
            ("Launch the Soterix Partner Portal in a supported web browser.", ""),
            ("Enter a valid email address in the Email field.", ""),
            ("Enter an incorrect password in the Password field.", ""),
            ("Click the Login button.", ""),
            ("Verify an error message is displayed near the form.",
             "Login is blocked. Inline error message 'Invalid email or password' appears; user remains on the login page; no session is created."),
        ],
    },
    {
        "Module_name": "Admin - Users > Edit User > Security",
        "Test Case Title": "Verify Admin password is never returned in user profile API",
        "Test Data": "Admin user already exists in the system",
        "Precondition": "Logged in as Admin. At least one user is configured.",
        "Tags": "smoke|regression",
        "Description": "Guard against accidental secret-leak via API serializers.",
        "Type": "Security",
        "Priority": "Critical",
        "Mode": "Manual",
        "Created By": "QA",
        "steps": [
            ("Open the Admin > Users page.", ""),
            ("Open browser devtools Network tab and reload.", ""),
            ("Inspect the user-list API response payload.", ""),
            ("Open one user's edit page and inspect the GET user-detail response.",
             "No response body contains the password field. Password is either omitted entirely or returned as a masked sentinel like '********'."),
        ],
    },
]


INSTRUCTIONS_BLOCKS = [
    ("Header", "QA Test Case Author Template"),
    ("Body", (
        "Each test case spans MULTIPLE ROWS in the 'Test Cases' sheet:\n"
        "  - The first row carries the metadata (Module_name, Test Case "
        "Title, Type, Priority, etc.) plus Step 1.\n"
        "  - Each additional step is its own row underneath, with the "
        "metadata columns LEFT BLANK and only the Steps cell filled.\n"
        "  - The LAST step row also gets the Expected_result (the final "
        "outcome of the test). Intermediate step rows leave "
        "Expected_result blank.\n"
        "A new test case begins when a row has a Module_name and Test "
        "Case Title filled in again."
    )),
    ("Header", "How to use the template"),
    ("Body", (
        "1. Save your own copy of this file (rename it for the release or "
        "module you are authoring).\n"
        "2. Replace the 3 example rows with your real test cases.\n"
        "3. Hand the finished xlsx to Ops for import."
    )),
    ("Header", "Required vs Optional columns"),
    ("Body", (
        "REQUIRED - every row must have these filled:\n"
        "    Module_name, Test Case Title, Steps, Expected_result, Type, Priority\n"
        "RECOMMENDED - fill when they apply:\n"
        "    Precondition, Test Data, Tags, Mode, Description\n"
        "LEAVE BLANK - Ops fills these in:\n"
        "    Estimate, Reference, Test Suite, Created By"
    )),
    ("Header", "Type - allowed values"),
    ("Body", ", ".join(TYPE_VALUES) + (
        ".\nUse only these seven values. Anything else gets silently "
        "rewritten on import."
    )),
    ("Header", "Priority - allowed values"),
    ("Body", ", ".join(PRIORITY_VALUES) + "."),
    ("Header", "Mode - allowed values"),
    ("Body", ", ".join(MODE_VALUES) + ".\nDefault is 'Manual' if blank."),
    ("Header", "Tags - allowed values"),
    ("Body", ", ".join(TAG_VALUES) + (
        ".\nFor multiple tags, separate with a pipe (e.g. 'smoke|regression') "
        "or a comma (e.g. 'smoke, regression'). Tags outside this list are "
        "ignored on import."
    )),
    ("Header", "Module_name - nesting"),
    ("Body", (
        "Use ' > ' (space-greater-than-space) to nest modules. Each segment "
        "becomes a sub-module. Example:\n"
        "    Customer Dashboard > KPI Summary\n"
        "    Login > Login Form > Negative Cases\n"
        "    Admin - Users > Edit User > Security"
    )),
    ("Header", "Steps - one step per row"),
    ("Body", (
        "Each step gets its own row underneath the case header. Write the "
        "step text in the Steps column - no numbering needed.\n"
        "Example layout for one case (3 steps):\n"
        "    Row N   : <all metadata filled> | Steps='Launch the portal'         | Expected_result=''\n"
        "    Row N+1 : <metadata blank>      | Steps='Log in with valid creds'   | Expected_result=''\n"
        "    Row N+2 : <metadata blank>      | Steps='Verify dashboard renders'  | Expected_result='Dashboard renders without errors'\n"
        "A new case starts when Module_name + Test Case Title are filled "
        "again on a row."
    )),
    ("Header", "Expected_result - on the last step row only"),
    ("Body", (
        "Write the case's final outcome on the LAST step row of that case. "
        "Leave the Expected_result cell BLANK on every earlier step row. "
        "QA Touch shows the final outcome on the last step; intermediate "
        "steps display '-' (single dash) by design."
    )),
    ("Header", "Description (the body field)"),
    ("Body", (
        "Use the Description column for the case's body or rationale. Just "
        "write what you mean - the import pipeline handles the field-name "
        "routing under the hood so the text shows up correctly in QA Touch."
    )),
    ("Header", "DON'T"),
    ("Body", (
        "- Do not type literal '<' or '>' inside Steps, Expected_result, "
        "Test Data, Precondition, or Description. The ' > ' separator "
        "inside Module_name is fine - it is the nesting marker.\n"
        "- Do not re-fill the metadata columns on continuation step rows. "
        "Leave them blank - that's how the importer knows the row belongs "
        "to the case above.\n"
        "- Do not use tags outside smoke / sanity / regression / future.\n"
        "- Do not leave Test Case Title blank or use duplicates - titles "
        "must be unique within the file."
    )),
]


def build_test_cases_sheet(ws) -> None:
    """Write the Test Cases sheet: bold/frozen header row + 3 example rows."""
    ws.title = "Test Cases"

    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="305496", end_color="305496", fill_type="solid")
    header_align = Alignment(horizontal="center", vertical="center", wrap_text=True)

    for col_idx, name in enumerate(CANONICAL_COLUMNS, start=1):
        cell = ws.cell(row=1, column=col_idx, value=name)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = header_align

    # Reasonable starting column widths. Multi-line cells use wrap_text.
    widths = {
        "Module_name": 36,
        "Test Case Title": 50,
        "Test Data": 30,
        "Estimate": 10,
        "Reference": 14,
        "Precondition": 30,
        "Steps": 50,
        "Expected_result": 50,
        "Test Suite": 14,
        "Tags": 18,
        "Description": 36,
        "Type": 14,
        "Priority": 12,
        "Mode": 12,
        "Created By": 14,
    }
    for col_idx, name in enumerate(CANONICAL_COLUMNS, start=1):
        ws.column_dimensions[get_column_letter(col_idx)].width = widths.get(name, 18)

    # Write one row per step. Row 1 of a case carries the metadata + Step 1;
    # subsequent rows have blank metadata and only Steps + Expected_result.
    wrap_align = Alignment(vertical="top", wrap_text=True)
    col_index = {name: i + 1 for i, name in enumerate(CANONICAL_COLUMNS)}
    next_row = 2
    for case in EXAMPLE_CASES:
        steps = case["steps"]
        for step_idx, (step_text, expected_text) in enumerate(steps):
            is_header = step_idx == 0
            for col_idx, col_name in enumerate(CANONICAL_COLUMNS, start=1):
                if col_name == "Steps":
                    value = step_text
                elif col_name == "Expected_result":
                    value = expected_text
                elif is_header:
                    value = case.get(col_name, "")
                else:
                    value = ""
                cell = ws.cell(row=next_row, column=col_idx, value=value)
                cell.alignment = wrap_align
            ws.row_dimensions[next_row].height = 22
            next_row += 1

    ws.freeze_panes = "A2"

    # Click-to-select dropdowns on the enum columns. The CSV importer silently
    # rewrites unknown Type values to "Regression" and silently drops unknown
    # tags, so eliminating typos at author time prevents the most common
    # silent-failure mode. Tags column is intentionally NOT dropdown-restricted
    # because tags are pipe-delimited multi-select (smoke|regression) - see
    # INSTRUCTIONS sheet for accepted values.
    enum_columns = {
        "Type": TYPE_VALUES,
        "Priority": PRIORITY_VALUES,
        "Mode": MODE_VALUES,
    }
    col_index = {name: i + 1 for i, name in enumerate(CANONICAL_COLUMNS)}
    for col_name, values in enum_columns.items():
        col_letter = get_column_letter(col_index[col_name])
        # Quote-wrap each value so commas inside values (unlikely but defensive)
        # don't break the formula1 list. Cap range at row 1001 - generous for a
        # typical authoring batch.
        formula = '"' + ",".join(values) + '"'
        dv = DataValidation(
            type="list",
            formula1=formula,
            allow_blank=True,
            showDropDown=False,  # openpyxl quirk: False here MEANS "show the arrow"
            showErrorMessage=True,
            errorTitle="Invalid value",
            error=f"Pick one of: {', '.join(values)}",
        )
        ws.add_data_validation(dv)
        dv.add(f"{col_letter}2:{col_letter}1001")


def build_instructions_sheet(ws) -> None:
    """Write a plain-text INSTRUCTIONS sheet, no fancy styling beyond bold headers."""
    ws.title = "INSTRUCTIONS"
    ws.column_dimensions["A"].width = 110

    header_font = Font(bold=True, size=12, color="305496")
    body_align = Alignment(vertical="top", wrap_text=True)

    row = 1
    for kind, text in INSTRUCTIONS_BLOCKS:
        cell = ws.cell(row=row, column=1, value=text)
        cell.alignment = body_align
        if kind == "Header":
            cell.font = header_font
            ws.row_dimensions[row].height = 22
        else:
            # Body - height scales with line count, capped.
            line_count = max(1, text.count("\n") + 1)
            ws.row_dimensions[row].height = min(15 * line_count + 8, 220)
        row += 1


def generate(output_path: Path = OUTPUT_PATH) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    wb = Workbook()
    build_test_cases_sheet(wb.active)
    build_instructions_sheet(wb.create_sheet("INSTRUCTIONS"))
    wb.save(output_path)
    return output_path


def main() -> int:
    path = generate()
    print(f"Wrote QA author template: {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
