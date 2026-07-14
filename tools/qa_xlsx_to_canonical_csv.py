"""
qa_xlsx_to_canonical_csv.py
===========================

.. deprecated::
   SUPERSEDED by ``tools/qa_xlsx_to_qatouch_csv.py``. The new converter emits
   the same canonical 15-column CSV but with broader header-alias coverage
   (Family A "Scenario", Family B "Module", Family C "Title" all auto-resolve),
   converter-side HTML escaping for the TR0028/TR0029 angle-bracket quirk,
   the merged-cell Steps format that the post-import step splitter consumes,
   and stronger fail-loud diagnostics. This file is kept only for reference
   while older import logs still point to it; do not call it on new work.
   See ``docs/qa_import_pipeline.md`` for the current pipeline.

Convert QA-authored Excel files into our canonical QA Touch import CSV format.

Two known xlsx shapes are auto-detected:

(a) Single sheet, header at row 1
    Example: LDAP_Test_Cases.xlsx
    Sheets: 'LDAP Test Cases' (data) + 'Users' (ignored - no Scenario column)

(b) Multi-sheet, header at row 4 with banner rows above
    Example: Soterix_TestCases_SiteDevice_MultiType (1).xlsx,
             Soterix_TestCases_Distributor.xlsx
    Sheets: Functional, Non-Functional, Performance, Security, API, Regression
            + analysis sheets (Reports & Summary, Insights & Risks) which are skipped

Output canonical CSV columns (OTA-proven):
    Module_name, Test Case Title, Test Data, Estimate, Reference, Precondition,
    Steps, Expected_result, Test Suite, Tags, Description, Type, Priority, Mode,
    Created By

Usage:
    python tools/qa_xlsx_to_canonical_csv.py \
        --src <xlsx-path> \
        --out <csv-path> \
        --top-feature "<Parent module name>" \
        --reference-prefix <PREFIX> \
        [--include-sheets ...] \
        [--exclude-sheets "Reports & Summary,Insights & Risks"] \
        [--dry-run] \
        [--use-feature-name-as-parent]

Notes:
  * No QA Touch upload happens here - this only produces a CSV.
  * Smoke/sanity tag promotion and Mode=Automated overrides happen in later passes.
"""

from __future__ import annotations

import argparse
import csv
import os
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, field
from typing import Dict, Iterable, List, Optional, Tuple

try:
    import openpyxl
except ImportError as exc:  # pragma: no cover
    print("ERROR: openpyxl not installed. Run: pip install openpyxl", file=sys.stderr)
    raise SystemExit(1) from exc


# --------------------------------------------------------------------------- #
# Constants
# --------------------------------------------------------------------------- #

EXPECTED_HEADERS = [
    "Scenario",
    "Testing Type",
    "Severity",
    "Priority",
    "Feature Name",
    "Sub Feature Name",
    "Test Conditions",
    "Test Idea",
    "Test Data",
    "Acceptance Criteria",
    "Test Steps",
]

CANONICAL_COLUMNS = [
    "Module_name",
    "Test Case Title",
    "Test Data",
    "Estimate",
    "Reference",
    "Precondition",
    "Steps",
    "Expected_result",
    "Test Suite",
    "Tags",
    "Description",
    "Type",
    "Priority",
    "Mode",
    "Created By",
]

DEFAULT_EXCLUDE_SHEETS = {"Reports & Summary", "Insights & Risks", "Users"}

# Used to detect the LDAP rows-73..82 column-shift (Testing Type <-> Severity swapped).
SEVERITY_TOKENS = {"Critical", "High", "Medium", "Low"}
TESTING_TYPE_TOKENS = {
    "UI",
    "Functional",
    "Negative",
    "Security",
    "UX",
    "Edge",
    "Performance",
    "Integration",
    "Compatibility",
    "Non-Functional",
    "API",
    "Regression",
}

TESTING_TYPE_TO_CANONICAL = {
    "UI": "Functional",
    "Functional": "Functional",
    "Negative": "Functional",
    "UX": "Functional",
    "Edge": "Functional",
    "Compatibility": "Functional",
    "Integration": "Functional",
    "API": "Functional",
    "Regression": "Functional",
    "Security": "Security",
    "Performance": "Performance",
    "Non-Functional": "Performance",
}

SEVERITY_TO_PRIORITY = {
    "Critical": "Critical",
    "High": "High",
    "Medium": "Medium",
    "Low": "Low",
}

P_TOKEN_TO_PRIORITY = {
    "P1": "High",
    "P2": "Medium",
    "P3": "Low",
}

# Unicode characters QA's xlsx generator inserts that we want to normalise.
# en-dash, em-dash, replacement char, right-arrow, non-breaking space, smart quotes.
UNICODE_FIXES = {
    "-": " - ",   # en-dash
    "-": " - ",   # em-dash
    "−": " - ",   # minus sign
    "�": " - ",   # replacement char (mojibake fallback)
    "->": " - ",   # right arrow (Distributor file uses these)
    " ": " ",     # nbsp
    "'": "'",     # left single quote
    "'": "'",     # right single quote
    "“": '"',     # left double quote
    "”": '"',     # right double quote
}


# --------------------------------------------------------------------------- #
# Data classes
# --------------------------------------------------------------------------- #

@dataclass
class RawRow:
    sheet: str
    row_num: int  # 1-indexed worksheet row
    scenario: str
    testing_type: str
    severity: str
    priority: str
    feature_name: str
    sub_feature_name: str
    test_conditions: str
    test_idea: str
    test_data: str
    acceptance_criteria: str
    test_steps: str


@dataclass
class SkippedRow:
    sheet: str
    row_num: int
    reason: str


@dataclass
class ConversionResult:
    rows_written: int = 0
    skipped: List[SkippedRow] = field(default_factory=list)
    module_name_counts: Counter = field(default_factory=Counter)
    swaps_applied: int = 0
    sheets_processed: List[str] = field(default_factory=list)
    sheets_skipped: List[str] = field(default_factory=list)


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def sanitize(value) -> str:
    """Normalise unicode dashes / arrows / smart quotes; trim; coerce to str."""
    if value is None:
        return ""
    s = str(value)
    for bad, good in UNICODE_FIXES.items():
        s = s.replace(bad, good)
    # Collapse any " -  -  - " runs that may appear from cascaded substitutions.
    s = re.sub(r"(\s-\s){2,}", " - ", s)
    # Collapse multi-space artefacts left over from substitutions (e.g. " - " inserted
    # next to existing whitespace producing "  -  ").
    s = re.sub(r"\s+-\s+", " - ", s)
    s = re.sub(r"[ \t]{2,}", " ", s)
    # Strip stray surrounding whitespace.
    return s.strip()


def find_header_row(ws) -> Optional[int]:
    """Return 1-indexed row number containing 'Scenario' in col A within first 8 rows."""
    for r in range(1, min(9, ws.max_row + 1)):
        if ws.cell(row=r, column=1).value == "Scenario":
            return r
    return None


def map_testing_type_to_canonical_type(testing_type: str) -> str:
    if not testing_type:
        return "Functional"
    return TESTING_TYPE_TO_CANONICAL.get(testing_type.strip(), "Functional")


def map_to_priority(severity: str, priority_raw: str) -> str:
    """Prefer Priority column if populated; else Severity. Map P1/P2/P3 if used."""
    def _norm(val: str) -> Optional[str]:
        if not val:
            return None
        v = val.strip()
        if v in P_TOKEN_TO_PRIORITY:
            return P_TOKEN_TO_PRIORITY[v]
        if v in SEVERITY_TO_PRIORITY:
            return SEVERITY_TO_PRIORITY[v]
        # tolerate lower/upper variants
        title = v.title()
        if title in SEVERITY_TO_PRIORITY:
            return SEVERITY_TO_PRIORITY[title]
        return None

    p = _norm(priority_raw)
    if p:
        return p
    s = _norm(severity)
    if s:
        return s
    return "Medium"  # safe default


def maybe_swap_testing_type_severity(testing_type: str, severity: str) -> Tuple[str, str, bool]:
    """
    Detect & fix the LDAP rows-73..82 column-shift bug:
        Testing Type cell holds a Severity token AND Severity cell holds a Testing Type token.
    """
    tt = testing_type.strip() if testing_type else ""
    sv = severity.strip() if severity else ""
    if tt in SEVERITY_TOKENS and sv in TESTING_TYPE_TOKENS:
        return sv, tt, True
    return testing_type, severity, False


def build_module_hierarchy(
    sub_features: List[str],
    top_feature: str,
) -> Dict[str, str]:
    """
    Group sub-features by ' - ' prefix into a 2-level hierarchy.

    Rule:
      * If sub_feature contains ' - ', split at the FIRST ' - ': left=group, right=leaf.
      * If 2+ sub-features share the same group prefix, use the group as a hierarchy level:
            top > group > leaf
      * Otherwise (only 1 occurrence of that group), collapse to: top > leaf
      * If no ' - ' in sub_feature, use: top > sub_feature
      * Empty sub_feature -> top_feature alone.
    """
    group_counts: Counter = Counter()
    parsed: Dict[str, Tuple[Optional[str], str]] = {}

    for sf in sub_features:
        sfn = sanitize(sf)
        if not sfn:
            parsed[sf] = (None, "")
            continue
        if " - " in sfn:
            group, _, leaf = sfn.partition(" - ")
            group = group.strip()
            leaf = leaf.strip()
            parsed[sf] = (group, leaf)
            group_counts[group] += 1
        else:
            parsed[sf] = (None, sfn)

    result: Dict[str, str] = {}
    for sf, (group, leaf) in parsed.items():
        if not leaf and not group:
            result[sf] = top_feature
            continue
        if group and group_counts[group] >= 2:
            result[sf] = f"{top_feature} > {group} > {leaf}"
        elif group:
            # Singleton group: skip the intermediate level
            result[sf] = f"{top_feature} > {leaf}"
        else:
            result[sf] = f"{top_feature} > {leaf}"
    return result


# --------------------------------------------------------------------------- #
# Core extraction
# --------------------------------------------------------------------------- #

def extract_rows_from_sheet(ws, sheet_name: str) -> Tuple[List[RawRow], List[SkippedRow], int]:
    """Return (raw_rows, skipped, swaps_applied) for one worksheet."""
    raw: List[RawRow] = []
    skipped: List[SkippedRow] = []
    swaps = 0

    header_row = find_header_row(ws)
    if header_row is None:
        return raw, [SkippedRow(sheet_name, 0, "no 'Scenario' header found in first 8 rows")], 0

    # Verify the header looks right (cols A-K should match EXPECTED_HEADERS)
    actual_header = [
        sanitize(ws.cell(row=header_row, column=c).value)
        for c in range(1, len(EXPECTED_HEADERS) + 1)
    ]
    if actual_header[:len(EXPECTED_HEADERS)] != EXPECTED_HEADERS:
        return raw, [SkippedRow(
            sheet_name, header_row,
            f"header mismatch: expected {EXPECTED_HEADERS} got {actual_header}"
        )], 0

    for r in range(header_row + 1, ws.max_row + 1):
        cells = [ws.cell(row=r, column=c).value for c in range(1, 12)]
        scenario = sanitize(cells[0])
        if not scenario:
            # blank trailing row - skip silently (not an error)
            continue

        testing_type_raw = sanitize(cells[1])
        severity_raw = sanitize(cells[2])
        testing_type, severity, swapped = maybe_swap_testing_type_severity(
            testing_type_raw, severity_raw
        )
        if swapped:
            swaps += 1

        feature_name = sanitize(cells[4])
        if not feature_name:
            skipped.append(SkippedRow(sheet_name, r, "missing Feature Name"))
            continue

        raw.append(RawRow(
            sheet=sheet_name,
            row_num=r,
            scenario=scenario,
            testing_type=testing_type,
            severity=severity,
            priority=sanitize(cells[3]),
            feature_name=feature_name,
            sub_feature_name=sanitize(cells[5]),
            test_conditions=sanitize(cells[6]),
            test_idea=sanitize(cells[7]),
            test_data=sanitize(cells[8]),
            acceptance_criteria=sanitize(cells[9]),
            test_steps=sanitize(cells[10]),
        ))

    return raw, skipped, swaps


def convert_workbook(
    src_path: str,
    out_path: str,
    top_feature: Optional[str],
    reference_prefix: str,
    include_sheets: Optional[Iterable[str]] = None,
    exclude_sheets: Optional[Iterable[str]] = None,
    dry_run: bool = False,
    use_feature_name_as_parent: bool = False,
    created_by: str = "QA",
    default_tag: str = "regression",
    default_mode: str = "Manual",
) -> ConversionResult:
    """Convert one xlsx file to canonical CSV."""
    result = ConversionResult()
    excl = set(exclude_sheets or [])
    excl |= DEFAULT_EXCLUDE_SHEETS
    incl = set(include_sheets) if include_sheets else None

    wb = openpyxl.load_workbook(src_path, data_only=True)

    # 1) Gather raw rows from every eligible sheet
    raw_rows: List[RawRow] = []
    for sheet_name in wb.sheetnames:
        if sheet_name in excl:
            result.sheets_skipped.append(sheet_name)
            continue
        if incl is not None and sheet_name not in incl:
            result.sheets_skipped.append(sheet_name)
            continue
        ws = wb[sheet_name]
        if find_header_row(ws) is None:
            # Not a test-case sheet (e.g. 'Users')
            result.sheets_skipped.append(sheet_name)
            continue

        rows, skipped, swaps = extract_rows_from_sheet(ws, sheet_name)
        result.sheets_processed.append(sheet_name)
        result.skipped.extend(skipped)
        result.swaps_applied += swaps
        raw_rows.extend(rows)

    wb.close()

    # 2) Build module hierarchy per (parent, sub_feature_name)
    #    Group rows by their effective parent (top_feature OR row.feature_name).
    grouped: Dict[str, List[RawRow]] = defaultdict(list)
    for rr in raw_rows:
        parent = sanitize(rr.feature_name) if use_feature_name_as_parent else (top_feature or "")
        if not parent:
            parent = sanitize(rr.feature_name) or "Uncategorised"
        grouped[parent].append(rr)

    sub_feature_to_module: Dict[Tuple[str, str], str] = {}
    for parent, rows in grouped.items():
        sub_features = sorted({rr.sub_feature_name for rr in rows})
        mapping = build_module_hierarchy(sub_features, parent)
        for sf, module in mapping.items():
            sub_feature_to_module[(parent, sf)] = module

    # 3) Build canonical rows
    out_records: List[Dict[str, str]] = []
    ref_counter: Counter = Counter()
    for rr in raw_rows:
        parent = sanitize(rr.feature_name) if use_feature_name_as_parent else (top_feature or "")
        if not parent:
            parent = sanitize(rr.feature_name) or "Uncategorised"
        module_name = sub_feature_to_module.get((parent, rr.sub_feature_name), parent)
        result.module_name_counts[module_name] += 1

        ref_counter[rr.sheet] += 1
        sheet_slug = re.sub(r"[^A-Za-z0-9]+", "", rr.sheet) or "Sheet"
        reference = f"{reference_prefix}_{sheet_slug}_{ref_counter[rr.sheet]:03d}"

        canonical_type = map_testing_type_to_canonical_type(rr.testing_type)
        canonical_priority = map_to_priority(rr.severity, rr.priority)

        description_parts = []
        if rr.test_idea:
            description_parts.append(f"Test Idea: {rr.test_idea}")
        if rr.testing_type:
            description_parts.append(f"Testing Type: {rr.testing_type}")
        description = " | ".join(description_parts)

        out_records.append({
            "Module_name": module_name,
            "Test Case Title": rr.scenario,
            "Test Data": rr.test_data,
            "Estimate": "",
            "Reference": reference,
            "Precondition": rr.test_conditions,
            "Steps": rr.test_steps,
            "Expected_result": rr.acceptance_criteria,
            "Test Suite": "",
            "Tags": default_tag,
            "Description": description,
            "Type": canonical_type,
            "Priority": canonical_priority,
            "Mode": default_mode,
            "Created By": created_by,
        })

    # 4) Emit CSV (unless dry-run)
    if not dry_run:
        os.makedirs(os.path.dirname(os.path.abspath(out_path)) or ".", exist_ok=True)
        with open(out_path, "w", newline="", encoding="utf-8") as fh:
            writer = csv.DictWriter(fh, fieldnames=CANONICAL_COLUMNS)
            writer.writeheader()
            for rec in out_records:
                writer.writerow(rec)

    result.rows_written = len(out_records)
    return result


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def parse_args(argv: Optional[List[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Convert QA-authored Excel to canonical QA Touch import CSV."
    )
    p.add_argument("--src", required=True, help="Path to source .xlsx")
    p.add_argument("--out", required=True, help="Output canonical .csv path")
    p.add_argument(
        "--top-feature",
        default=None,
        help="Top-level parent Module_name (e.g. 'LDAP'). "
             "Omit when --use-feature-name-as-parent is set.",
    )
    p.add_argument(
        "--reference-prefix",
        required=True,
        help="Stable reference id prefix (e.g. LDAP, SITEDEV, DIST).",
    )
    p.add_argument(
        "--include-sheets",
        nargs="*",
        default=None,
        help="Only process these sheet names.",
    )
    p.add_argument(
        "--exclude-sheets",
        default="",
        help="Comma-separated sheet names to skip (in addition to defaults).",
    )
    p.add_argument(
        "--use-feature-name-as-parent",
        action="store_true",
        help="Use each row's 'Feature Name' column as the top-level parent "
             "(use for files with multiple modules per workbook, e.g. Distributor).",
    )
    p.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse and report stats but do not write the CSV.",
    )
    p.add_argument("--created-by", default="QA")
    p.add_argument("--default-tag", default="regression")
    p.add_argument("--default-mode", default="Manual")
    return p.parse_args(argv)


def main(argv: Optional[List[str]] = None) -> int:
    args = parse_args(argv)

    if not args.use_feature_name_as_parent and not args.top_feature:
        print("ERROR: must pass --top-feature OR --use-feature-name-as-parent",
              file=sys.stderr)
        return 2

    exclude = [s.strip() for s in args.exclude_sheets.split(",") if s.strip()]

    result = convert_workbook(
        src_path=args.src,
        out_path=args.out,
        top_feature=args.top_feature,
        reference_prefix=args.reference_prefix,
        include_sheets=args.include_sheets,
        exclude_sheets=exclude,
        dry_run=args.dry_run,
        use_feature_name_as_parent=args.use_feature_name_as_parent,
        created_by=args.created_by,
        default_tag=args.default_tag,
        default_mode=args.default_mode,
    )

    # Report
    print(f"Source:                 {args.src}")
    print(f"Output:                 {args.out}{' (DRY RUN - not written)' if args.dry_run else ''}")
    print(f"Sheets processed:       {result.sheets_processed}")
    print(f"Sheets skipped:         {result.sheets_skipped}")
    print(f"Rows written:           {result.rows_written}")
    print(f"Column-shift swaps:     {result.swaps_applied}")
    print(f"Skipped rows:           {len(result.skipped)}")
    for sk in result.skipped:
        print(f"  - [{sk.sheet} R{sk.row_num}] {sk.reason}")
    print(f"Distinct Module_names:  {len(result.module_name_counts)}")
    for mod, cnt in sorted(result.module_name_counts.items()):
        print(f"  {cnt:4d}  {mod}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
