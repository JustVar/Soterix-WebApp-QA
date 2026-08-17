"""
qa_xlsx_to_qatouch_csv.py
==========================

Supersedes ``tools/qa_xlsx_to_canonical_csv.py``. Same canonical 15-column
output, broader column-name alias coverage, converter-side HTML escaping for
the TR0028/TR0029 angle-bracket quirk, and the merged-cell Steps format
that the post-import step splitter consumes.

Convert a QA-authored xlsx (12-column author template OR any of the three known
"in the wild" variants - Family A "Scenario" sheets, Family B "Module" sheets,
Family C "Title" sheets) into the canonical 15-column QA Touch import CSV.

Header set changed 2026-06-26: emits VENDOR-CANONICAL slugs (section_name,
title, test_description, newtags, test_priority, test_mode, ...) instead of
the prior friendly Title-Case names. With vendor slugs, the QA Touch import
wizard auto-fills its 17 mapping dropdowns at upload time - no manual
mapping step. Historical canonical CSVs (sitedevice_canonical.csv,
distributor_canonical.csv, ldap_canonical.csv) used the old friendly
headers; re-importing them would require manual mapping. New runs of this
converter produce the auto-mapped format.

Why this script exists
----------------------
QA Touch's CSV importer has a half-dozen silent-data-loss quirks documented in
docs/local/qa_touch_integration.md:

  - Unknown `test_type` values are silently rewritten to `Regression` (§4).
  - `reference` (refLink) is silently dropped on import (§4) - Phase 4 backfill
    re-applies it via /v1/case/update.
  - A column literally named `description` maps to a hidden vendor field and is
    silently dropped (§7.A.1) - that's why we emit `test_description` instead,
    which populates the user-visible Description on import.
  - Tags not present in the per-project tag dictionary are silently dropped.
  - Multi-row Steps are collapsed into a merged Step 1 - handled in Phase 5.
  - Literal `<` and `>` characters in cell text break the CSV parser (the
    TR0028/TR0029 quirk) - converter HTML-escapes them in Steps/Expected/
    Test Data/Precondition/test_description.

This converter is the FIRST stage of a 5-phase pipeline (see
docs/qa_import_pipeline.md). It exists to:

  1. Emit ONLY known-good Type values so the silent-rewrite-to-Regression never
     fires; the metadata backfill can then recover from any case the importer
     still mishandled.
  2. Write Reference into the CSV (so the row's identity is captured) even
     though the importer will drop it - the metadata backfill re-applies via
     /v1/case/update keyed on Test Case Title.
  3. HTML-escape `<` and `>` in Steps/Expected_result/Test Data/Precondition/
     Description so the importer's parser does not corrupt rows. The ` > `
     hierarchy separator in Module_name is PRESERVED RAW because the importer
     needs it to nest modules.
  4. Merge "Expected Result" + "Acceptance Criteria" columns into the single
     Expected_result field (design requirement #1). Never drops either.
  5. Emit the merged-cell Steps format (one CSV row per case, all steps in one
     quoted cell with embedded \n newlines, expected result mirroring step
     count) - accepting the importer's collapse-to-Step-1 behavior rather than
     fighting it. The post-import step splitter then breaks the merged row into
     per-step rows via /v1/steps/save with the case-level expected_result on
     the LAST step and `-` on steps 1..N-1.
  6. FAIL LOUD if any of the 5 required fields can't be resolved via the alias
     tables - never silently skip rows when QA renames a column.

Stdlib + openpyxl only. No network calls. No requests/httpx.

CLI
---
    python tools/qa_xlsx_to_qatouch_csv.py \\
        --xlsx tests/data/<release>_<module>_authored.xlsx \\
        --out  tests/data/<release>_<module>_canonical.csv \\
        [--sheet NAME]              # restrict to one sheet
        [--module-prefix PREFIX]    # prepend to every Module_name (e.g. "C2C")
        [--reference-prefix PFX]    # default = sanitized sheet name
        [--created-by "QA Import"]
        [--dry-run]

Exit codes
----------
    0   success
    1   converter usage error (missing args, file not found)
    2   FAIL LOUD - sheet has no resolvable required-field headers
"""
from __future__ import annotations

import argparse
import csv
import os
import re
import sys
from collections import Counter
from dataclasses import dataclass, field

try:
    import openpyxl
except ImportError as exc:  # pragma: no cover
    print("ERROR: openpyxl not installed. Run: pip install openpyxl", file=sys.stderr)
    raise SystemExit(1) from exc


# --------------------------------------------------------------------------- #
# Canonical 15-column CSV header - VENDOR-CANONICAL slugs that match the QA
# Touch import wizard's 17 internal field names. With these exact headers,
# the wizard's column-mapping dropdowns auto-fill at upload time and the
# operator clicks Import once with zero manual mapping.
#
# Earlier revision used friendly Title-Case headers (Module_name, Test Case
# Title, Description, Tags, Priority, Mode, ...) - those import OK but the
# wizard's 17 dropdowns sit at "Skip" until the operator maps them by hand.
# Worse: a CSV column literally named "Description" maps to the vendor's
# `description` field which is silently dropped (not user-visible); only
# `test_description` populates the case detail's Description field. Without
# realizing it, the 5-phase pipeline was compensating via Phase 4 backfill.
# Renamed 2026-06-26 after the live import-API probe captured the canonical
# 17 slugs - see docs/local/qa_touch_integration.md §7.A.1.
#
# Vendor's 2 unused slugs (intentionally omitted):
#   - description - silently dropped (use test_description instead)
#   - heirarchy   - module-depth marker; we already nest via ` > ` in
#                   section_name, so heirarchy is redundant
# --------------------------------------------------------------------------- #

CANONICAL_COLUMNS = [
    "section_name",       # was: Module_name
    "title",              # was: Test Case Title
    "test_data",          # was: Test Data
    "estimate",           # was: Estimate
    "reference",          # was: Reference
    "precondition",       # was: Precondition
    "steps",              # was: Steps
    "expected_result",    # was: Expected_result
    "test_suite",         # was: Test Suite
    "newtags",            # was: Tags
    "test_description",   # was: Description (CRITICAL: vendor's `description` is silently dropped)
    "test_type",          # was: Type
    "test_priority",      # was: Priority
    "test_mode",          # was: Mode
    "created_by",         # was: Created By
]


# --------------------------------------------------------------------------- #
# Alias tables - logical-field -> set of accepted header variants.
# Normalization for matching: lower(strip(collapse-internal-whitespace)).
# Plural-tolerant for "Expected Result(s)" / "Precondition(s)".
# --------------------------------------------------------------------------- #

ALIASES: dict[str, list[str]] = {
    "title":           ["title", "test case title", "scenario", "summary", "case title"],
    "case_type":       ["case_type", "type", "testing type", "test type", "category"],
    "priority":        ["priority", "priorities"],
    "module":          ["module", "modulename", "module name", "module_name"],
    "precondition":    ["precondition", "preconditions", "test conditions",
                        "pre-condition", "pre condition", "setup"],
    "steps":           ["steps", "test steps", "test step", "procedure"],
    # Two expected-flavored aliases; the converter merges them if BOTH are present.
    "expected_result": ["expected_result", "expectedresult", "expected result",
                        "expected results"],
    "acceptance":      ["acceptance criteria", "acceptance"],
    "test_data":       ["test data", "data", "test inputs"],
    "tags":            ["tags", "new tags", "newtags", "labels", "suite tags"],
    "mode":            ["mode", "execution mode"],
    "test_idea":       ["test idea", "description", "rationale"],
    "severity":        ["severity"],
    # Family A only - special-case concatenation into Module_name.
    "feature_name":    ["feature name"],
    "sub_feature_name": ["sub feature name", "sub-feature name", "subfeature name"],
}

REQUIRED_LOGICAL_FIELDS = ["title", "case_type", "module", "steps", "expected_result"]

# When `case_type` is blank on a row AND the sheet name matches one of these
# (case-insensitive), use the sheet name as the type.
SHEET_NAME_TYPE_FALLBACK = {
    "functional":      "functional",
    "non-functional":  "performance",
    "performance":     "performance",
    "security":        "security",
    "api":             "functional",
    "regression":      "regression",
}

# QA Touch's canonical Type enum values (Title Case for CSV emission).
CANONICAL_TYPE_VALUES = {
    "functional", "negative", "security", "performance",
    "regression", "acceptance", "automation",
}

CASE_TYPE_TITLE = {
    "functional":  "Functional",
    "negative":    "Negative",
    "security":    "Security",
    "performance": "Performance",
    "regression":  "Regression",
    "acceptance":  "Acceptance",
    "automation":  "Automation",
}

# Tolerated input -> canonical lowercase for case_type.
CASE_TYPE_NORMALIZE = {
    "ui":              "functional",
    "functional":      "functional",
    "negative":        "negative",
    "ux":              "functional",
    "edge":            "functional",
    "compatibility":   "functional",
    "integration":     "functional",
    "api":             "functional",
    "regression":      "regression",
    "security":        "security",
    "performance":     "performance",
    "non-functional":  "performance",
    "acceptance":      "acceptance",
    "automation":      "automation",
    "automated":       "automation",
}

PRIORITY_TITLE = {"critical": "Critical", "high": "High",
                  "medium": "Medium", "low": "Low"}

MODE_TITLE = {"manual": "Manual", "automation": "Automation"}
MODE_NORMALIZE = {"manual": "manual", "automation": "automation",
                  "automated": "automation"}

VALID_TAGS = {"smoke", "sanity", "regression", "future"}

# LDAP-style column-shift detector - Family A "Testing Type" vs "Severity" swap.
SEVERITY_TOKENS = {"Critical", "High", "Medium", "Low"}
TESTING_TYPE_TOKENS = {
    "UI", "Functional", "Negative", "Security", "UX", "Edge",
    "Performance", "Integration", "Compatibility", "Non-Functional",
    "API", "Regression",
}

# Unicode hygiene - en-dash, em-dash, replacement char, arrows, NBSP, smart quotes.
UNICODE_FIXES = {
    "-": " - ",   # en-dash
    "-": " - ",   # em-dash
    "−": " - ",   # minus sign
    "�": " - ",   # replacement char (mojibake fallback)
    "->": " - ",   # right arrow
    " ": " ",     # nbsp
    "'": "'",     # left single quote
    "'": "'",     # right single quote
    """: '"',     # left double quote
    """: '"',     # right double quote
}


# --------------------------------------------------------------------------- #
# Data classes
# --------------------------------------------------------------------------- #

@dataclass
class HeaderMap:
    """Resolved header_index -> logical_field for one sheet.

    Stored as logical -> 1-indexed column number. Missing logicals are absent.
    """
    sheet: str
    header_row: int
    fields: dict[str, int]  # logical_field -> 1-based col index

    def has(self, logical: str) -> bool:
        return logical in self.fields

    def get(self, ws, row: int, logical: str) -> str:
        if logical not in self.fields:
            return ""
        return sanitize(ws.cell(row=row, column=self.fields[logical]).value)


@dataclass
class Warning:
    sheet: str
    row: int
    kind: str
    detail: str


@dataclass
class ConvertResult:
    rows_written: int = 0
    sheets_processed: list[str] = field(default_factory=list)
    sheets_skipped: list[str] = field(default_factory=list)
    warnings: list[Warning] = field(default_factory=list)
    sheet_row_counts: Counter = field(default_factory=Counter)
    rows_received_both_expected: int = 0
    rows_used_sheet_name_for_type: int = 0
    swaps_applied: int = 0
    output_format: str = "merged-steps"


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #

def sanitize(value) -> str:
    """Normalize unicode dashes / arrows / smart quotes; trim; coerce to str."""
    if value is None:
        return ""
    s = str(value)
    for bad, good in UNICODE_FIXES.items():
        s = s.replace(bad, good)
    # Collapse " -  -  - " cascade artefacts that occur when adjacent unicode
    # dashes all get rewritten in a single row of text.
    s = re.sub(r"(\s-\s){2,}", " - ", s)
    s = re.sub(r"\s+-\s+", " - ", s)
    s = re.sub(r"[ \t]{2,}", " ", s)
    return s.strip()


def header_key(s: str) -> str:
    """Normalize a header cell for alias lookup (lower, strip, collapse ws)."""
    return re.sub(r"\s+", " ", sanitize(s)).lower()


def detect_header_row(ws, max_scan: int = 5) -> tuple[int | None, dict[str, int]]:
    """Scan rows 1..max_scan; return (1-based row, logical->col map) for the
    first row where >=3 of the REQUIRED logical fields resolve via aliases.

    This is the explicit defense against Family A's banner-in-rows-1-3 layout
    AND against QA accidentally inserting a title row above the headers.
    """
    best_row = None
    best_map: dict[str, int] = {}
    best_score = 0

    # Build reverse alias map: header-key -> logical-field
    reverse: dict[str, str] = {}
    for logical, aliases in ALIASES.items():
        for a in aliases:
            reverse[header_key(a)] = logical

    for r in range(1, min(max_scan, ws.max_row) + 1):
        col_count = ws.max_column or 0
        if col_count == 0:
            continue
        seen: dict[str, int] = {}
        for c in range(1, col_count + 1):
            raw = ws.cell(row=r, column=c).value
            if raw is None:
                continue
            hk = header_key(raw)
            if hk in reverse and reverse[hk] not in seen:
                seen[reverse[hk]] = c

        score = sum(1 for f in REQUIRED_LOGICAL_FIELDS if f in seen)
        # Family A pattern: feature_name + sub_feature_name substitute for module.
        if "module" not in seen and "feature_name" in seen and "sub_feature_name" in seen:
            score += 1

        if score > best_score:
            best_score = score
            best_row = r
            best_map = seen

    if best_score >= 3:
        return best_row, best_map
    return None, {}


def maybe_swap_type_severity(case_type: str, severity: str) -> tuple[str, str, bool]:
    """LDAP rows-73..82 column-shift defense: if `case_type` cell holds a
    Severity token AND `severity` cell holds a Testing-Type token, swap them.
    """
    ct = (case_type or "").strip()
    sv = (severity or "").strip()
    if ct in SEVERITY_TOKENS and sv in TESTING_TYPE_TOKENS:
        return sv, ct, True
    return case_type, severity, False


def normalize_case_type(raw: str, sheet_name: str) -> tuple[str, bool]:
    """Return (canonical lowercase type, used_sheet_fallback)."""
    if raw:
        key = raw.strip().lower()
        if key in CASE_TYPE_NORMALIZE:
            return CASE_TYPE_NORMALIZE[key], False
        # Tolerate Title Case input that isn't in our normalize map.
        if key in CANONICAL_TYPE_VALUES:
            return key, False

    # Fallback to sheet name (case-insensitive)
    sk = (sheet_name or "").strip().lower()
    if sk in SHEET_NAME_TYPE_FALLBACK:
        return SHEET_NAME_TYPE_FALLBACK[sk], True

    # Safer-than-Regression default - we choose Functional so the importer's
    # silent rewrite-to-Regression quirk does not fire on our output. The
    # backfill can correct anything wrong.
    return "functional", False


def normalize_priority(raw: str, severity: str = "") -> str:
    """Map raw priority OR severity to canonical lowercase priority."""
    for candidate in (raw, severity):
        if not candidate:
            continue
        k = candidate.strip().lower()
        if k in PRIORITY_TITLE:
            return k
        # Also tolerate P1/P2/P3 shorthand.
        ptok = candidate.strip().upper()
        if ptok == "P1": return "high"
        if ptok == "P2": return "medium"
        if ptok == "P3": return "low"
    return "medium"


def normalize_mode(raw: str) -> str:
    if not raw:
        return "manual"
    k = raw.strip().lower()
    return MODE_NORMALIZE.get(k, "manual")


def normalize_tags(raw: str) -> tuple[str, list[str]]:
    """Return (pipe-delimited known tags, dropped-tag list).

    The four canonical tags must already exist in the QA Touch per-project tag
    dictionary; unknown tags are silently dropped by the importer, so we warn.
    Accepts comma OR pipe separators in input.
    """
    if not raw:
        return "", []
    parts = re.split(r"[|,]", raw)
    kept: list[str] = []
    dropped: list[str] = []
    for p in parts:
        t = p.strip().lower()
        if not t:
            continue
        if t in VALID_TAGS:
            if t not in kept:
                kept.append(t)
        else:
            dropped.append(p.strip())
    return "|".join(kept), dropped


def html_escape_unsafe(text: str) -> str:
    """Replace literal `<` and `>` ONLY (TR0028/TR0029 defense). Do not touch
    `&` or `;` - csv.writer handles RFC-4180 quoting, and other special chars
    inside quoted cells are fine. Do NOT call this on Module_name (the ` > `
    hierarchy separator must stay raw so the importer can nest)."""
    if not text:
        return ""
    return text.replace("<", "&lt;").replace(">", "&gt;")


def parse_steps(raw: str) -> list[str]:
    """Split a free-form Steps cell into individual step texts.

    Strips leading `N. ` or `Step N:` numbering. Tolerates either LF, CRLF, or
    semicolon-separated input. Drops empty lines.
    """
    if not raw:
        return []
    # Tolerate semicolon "; " as a separator only if no newlines (some authors
    # paste a flat string). If newlines are present, prefer them.
    if "\n" in raw or "\r" in raw:
        lines = re.split(r"\r?\n", raw)
    else:
        # Heuristic: split on " ; " ONLY when the rest looks like multiple steps
        # (i.e. >=2 semicolons). Otherwise treat as a single step.
        if raw.count(";") >= 2:
            lines = [p for p in re.split(r"\s*;\s*", raw)]
        else:
            lines = [raw]

    out: list[str] = []
    for line in lines:
        s = line.strip()
        if not s:
            continue
        # Strip "1." / "1)" / "Step 1:" / "Step 1." prefixes.
        s = re.sub(r"^(step\s*)?\d+\s*[\.\):-]\s*", "", s, flags=re.IGNORECASE)
        if s:
            out.append(s)
    return out


def merge_expected(expected: str, acceptance: str) -> tuple[str, bool]:
    """Merge "Expected Result" + "Acceptance Criteria" per design requirement #1.

    Returns (merged_text, both_were_present).
    """
    e = (expected or "").strip()
    a = (acceptance or "").strip()
    both = bool(e) and bool(a)
    if both:
        return f"{e}\n\n{a}", True
    return (e or a), False


# --------------------------------------------------------------------------- #
# Per-row record builder
# --------------------------------------------------------------------------- #

@dataclass
class CanonicalRecord:
    module_name: str
    title: str
    test_data: str
    estimate: str
    reference: str
    precondition: str
    steps_merged: str
    expected_merged: str
    test_suite: str
    tags: str
    description: str
    case_type_title: str
    priority_title: str
    mode_title: str
    created_by: str
    # Per-step lists kept for Format B (migration-rows) emission.
    # steps_list is the N step texts (no "Step N: " prefix).
    # expected_list is the N expected texts, padded with "-" on
    # intermediate steps when only a single case-level expected was
    # provided (so the LAST step carries the assertion - matches
    # Format A's padding semantics so the two formats represent the
    # same case data identically modulo row layout).
    steps_list: list[str] = field(default_factory=list)
    expected_list: list[str] = field(default_factory=list)


def build_record(
    ws,
    row: int,
    hmap: HeaderMap,
    sheet_name: str,
    module_prefix: str,
    reference_prefix: str,
    index_in_sheet: int,
    created_by: str,
    result: ConvertResult,
) -> CanonicalRecord | None:
    """Return a CanonicalRecord for one row, or None if the row is unusable
    (empty title or empty steps after parsing)."""

    title = hmap.get(ws, row, "title")
    if not title:
        return None  # blank trailing row, skip silently

    # ----- module hierarchy -----
    if hmap.has("module"):
        module_raw = hmap.get(ws, row, "module")
    elif hmap.has("feature_name") and hmap.has("sub_feature_name"):
        fname = hmap.get(ws, row, "feature_name")
        sname = hmap.get(ws, row, "sub_feature_name")
        if fname and sname:
            module_raw = f"{fname} > {sname}"
        else:
            module_raw = fname or sname
    elif hmap.has("feature_name"):
        module_raw = hmap.get(ws, row, "feature_name")
    else:
        module_raw = ""

    if not module_raw:
        result.warnings.append(Warning(sheet_name, row, "missing_module",
                                       "row has no module/feature info; using sheet name"))
        module_raw = sheet_name

    module_name = f"{module_prefix} > {module_raw}" if module_prefix else module_raw
    # DO NOT html-escape Module_name - the importer needs raw ' > ' for nesting.

    # ----- case_type (with sheet-name fallback) -----
    raw_case_type = hmap.get(ws, row, "case_type")
    raw_severity = hmap.get(ws, row, "severity") if hmap.has("severity") else ""

    # LDAP column-shift defense
    raw_case_type, raw_severity, swapped = maybe_swap_type_severity(raw_case_type, raw_severity)
    if swapped:
        result.swaps_applied += 1
        result.warnings.append(Warning(sheet_name, row, "type_severity_swap",
                                       "case_type and severity columns appeared swapped"))

    norm_type, used_fallback = normalize_case_type(raw_case_type, sheet_name)
    if used_fallback:
        result.rows_used_sheet_name_for_type += 1
    case_type_title = CASE_TYPE_TITLE[norm_type]

    # ----- priority -----
    raw_priority = hmap.get(ws, row, "priority") if hmap.has("priority") else ""
    norm_priority = normalize_priority(raw_priority, raw_severity)
    priority_title = PRIORITY_TITLE[norm_priority]

    # ----- mode -----
    raw_mode = hmap.get(ws, row, "mode") if hmap.has("mode") else ""
    norm_mode = normalize_mode(raw_mode)
    mode_title = MODE_TITLE[norm_mode]

    # ----- tags -----
    raw_tags = hmap.get(ws, row, "tags") if hmap.has("tags") else ""
    tags_csv, dropped_tags = normalize_tags(raw_tags)
    for d in dropped_tags:
        result.warnings.append(Warning(sheet_name, row, "tag_dropped",
                                       f"tag '{d}' not in {sorted(VALID_TAGS)}"))

    # ----- steps -----
    raw_steps = hmap.get(ws, row, "steps")
    steps_list = parse_steps(raw_steps)
    if not steps_list:
        result.warnings.append(Warning(sheet_name, row, "missing_steps",
                                       "row has no parseable steps; skipping"))
        return None

    # ----- expected_result / acceptance_criteria merge -----
    raw_expected = hmap.get(ws, row, "expected_result") if hmap.has("expected_result") else ""
    raw_acceptance = hmap.get(ws, row, "acceptance") if hmap.has("acceptance") else ""
    merged_expected, both_present = merge_expected(raw_expected, raw_acceptance)
    if both_present:
        result.rows_received_both_expected += 1
        result.warnings.append(Warning(sheet_name, row, "both_expected_present",
                                       "Expected Result AND Acceptance Criteria merged"))

    if not merged_expected:
        # Required field missing on this row - record + skip.
        result.warnings.append(Warning(sheet_name, row, "missing_expected",
                                       "row has neither Expected Result nor Acceptance Criteria"))
        return None

    # ----- steps_merged / expected_merged emission -----
    # Canonical format proven by sitedevice_canonical.csv: ONE CSV row per case,
    # Steps cell is "Step 1: <text>\nStep 2: <text>\n...\nStep N: <text>" with
    # literal LF newlines embedded; csv.writer with QUOTE_MINIMAL handles the
    # RFC-4180 quoting. Expected_result mirrors line count: when the source has
    # only one expected blob, we pad steps 1..N-1 with "-" so the step splitter
    # (phase 5) recognizes "no per-step expected, last step carries the
    # assertion" semantics.
    safe_steps = [html_escape_unsafe(s) for s in steps_list]
    steps_merged = "\n".join(f"Step {i+1}: {s}" for i, s in enumerate(safe_steps))

    safe_expected = html_escape_unsafe(merged_expected)
    # Pad expected to step count with "-" sentinel on intermediate steps; place
    # the full merged expected on the LAST step. This matches design requirement
    # #2: last step is the assertion.
    if len(steps_list) == 1:
        expected_merged = safe_expected
        expected_per_step = [safe_expected]
    else:
        expected_per_step = ["-"] * (len(steps_list) - 1) + [safe_expected]
        expected_merged = "\n".join(expected_per_step)

    # ----- test_data / precondition / description -----
    raw_test_data = hmap.get(ws, row, "test_data") if hmap.has("test_data") else ""
    raw_precondition = hmap.get(ws, row, "precondition") if hmap.has("precondition") else ""
    raw_test_idea = hmap.get(ws, row, "test_idea") if hmap.has("test_idea") else ""

    test_data = html_escape_unsafe(raw_test_data)
    precondition = html_escape_unsafe(raw_precondition)
    description = html_escape_unsafe(raw_test_idea)

    # ----- reference (importer drops this; backfill re-applies via API) -----
    reference = f"{reference_prefix}_{case_type_title}_{index_in_sheet:03d}"

    return CanonicalRecord(
        module_name=module_name,
        title=title,
        test_data=test_data,
        estimate="",
        reference=reference,
        precondition=precondition,
        steps_merged=steps_merged,
        expected_merged=expected_merged,
        test_suite="",
        tags=tags_csv,
        description=description,
        case_type_title=case_type_title,
        priority_title=priority_title,
        mode_title=mode_title,
        created_by=created_by,
        steps_list=safe_steps,
        expected_list=expected_per_step,
    )


# --------------------------------------------------------------------------- #
# Sheet driver
# --------------------------------------------------------------------------- #

def process_sheet(
    ws,
    sheet_name: str,
    module_prefix: str,
    reference_prefix: str,
    created_by: str,
    result: ConvertResult,
) -> list[CanonicalRecord]:
    header_row, field_map = detect_header_row(ws, max_scan=8)
    if header_row is None:
        # FAIL LOUD per design - record what we saw so QA can fix the sheet.
        seen_headers = []
        if ws.max_row >= 1 and ws.max_column:
            for c in range(1, ws.max_column + 1):
                v = ws.cell(row=1, column=c).value
                if v is not None:
                    seen_headers.append(str(v))
        raise SystemExit(
            f"FAIL: sheet '{sheet_name}' has no resolvable header row "
            f"(needed >=3 of {REQUIRED_LOGICAL_FIELDS}).\n"
            f"  Row 1 headers seen: {seen_headers}\n"
            f"  Accepted aliases per field:\n"
            + "\n".join(f"    {f}: {ALIASES.get(f, [])}" for f in REQUIRED_LOGICAL_FIELDS)
        )

    # Soft-check required fields. Module is satisfied EITHER by a `module`
    # alias OR by (feature_name + sub_feature_name).
    missing = []
    for req in REQUIRED_LOGICAL_FIELDS:
        if req == "module":
            if "module" not in field_map and not (
                "feature_name" in field_map and "sub_feature_name" in field_map
            ):
                missing.append(req)
            continue
        if req == "expected_result":
            # Expected_result is satisfied by `expected_result` OR `acceptance`.
            if "expected_result" not in field_map and "acceptance" not in field_map:
                missing.append(req)
            continue
        if req not in field_map:
            missing.append(req)

    if missing:
        raise SystemExit(
            f"FAIL: sheet '{sheet_name}' is missing required field(s): {missing}.\n"
            f"  Headers resolved: {sorted(field_map.keys())}\n"
            f"  Accepted aliases for missing fields:\n"
            + "\n".join(f"    {f}: {ALIASES.get(f, [])}" for f in missing)
        )

    hmap = HeaderMap(sheet=sheet_name, header_row=header_row, fields=field_map)

    # Coalesce continuation rows. The author template (since 2026-06-26)
    # ships in one-step-per-row layout: each case is a header row
    # carrying the metadata + Step 1, followed by N-1 continuation rows
    # where section_name + title are blank and only the steps column is
    # filled. This pass walks the rows in order, detects continuation
    # rows by their blank module/title cells, and merges their step text
    # into the case-header row's `steps` cell with newline separation.
    # Single-row authoring (one row per case with a multi-line Steps
    # cell) still works unchanged - those files simply have ZERO
    # continuation rows.
    case_header_rows = _coalesce_continuation_rows(ws, hmap)

    records: list[CanonicalRecord] = []
    for index_in_sheet, header_row_idx in enumerate(case_header_rows, start=1):
        rec = build_record(
            ws, header_row_idx, hmap, sheet_name,
            module_prefix=module_prefix,
            reference_prefix=reference_prefix,
            index_in_sheet=index_in_sheet,
            created_by=created_by,
            result=result,
        )
        if rec is not None:
            records.append(rec)
            result.sheet_row_counts[sheet_name] += 1

    return records


def _coalesce_continuation_rows(ws, hmap: HeaderMap) -> list[int]:
    """Walk the data rows of a sheet, detect continuation rows belonging
    to the most-recent case, and mutate the case-header row's `steps`
    and `expected_result` cells in-memory to include the merged text.

    Returns the list of row indices that are case-header rows (one per
    case) - caller builds CanonicalRecords from these only.

    A row is a CASE HEADER if it has a non-empty module/section value
    AND a non-empty title.

    A row is a CONTINUATION if both module/section AND title are blank
    AND the row has at least one non-empty cell (typically `steps`).

    For QA convenience, the expected_result is allowed on the LAST
    continuation row only (or on the case-header row if there is just
    one step). If multiple continuation rows carry expected text, they
    are joined with newlines - the existing builder then places the
    joined blob on the last step per the design intent
    "last step is the assertion".
    """
    def _row_module(r: int) -> str:
        if hmap.has("module"):
            return (hmap.get(ws, r, "module") or "").strip()
        if hmap.has("feature_name") or hmap.has("sub_feature_name"):
            fn = (hmap.get(ws, r, "feature_name") or "").strip() if hmap.has("feature_name") else ""
            sfn = (hmap.get(ws, r, "sub_feature_name") or "").strip() if hmap.has("sub_feature_name") else ""
            return f"{fn}|{sfn}"  # any non-empty join counts as "module present"
        return ""

    def _row_title(r: int) -> str:
        return (hmap.get(ws, r, "title") or "").strip() if hmap.has("title") else ""

    def _row_steps(r: int) -> str:
        return (hmap.get(ws, r, "steps") or "").strip() if hmap.has("steps") else ""

    def _row_expected(r: int) -> str:
        if hmap.has("expected_result"):
            v = (hmap.get(ws, r, "expected_result") or "").strip()
            if v:
                return v
        if hmap.has("acceptance"):
            v = (hmap.get(ws, r, "acceptance") or "").strip()
            if v:
                return v
        return ""

    case_header_rows: list[int] = []
    current_header: int | None = None
    current_steps: list[str] = []
    current_expecteds: list[str] = []

    def _flush_into_header():
        if current_header is None or not current_steps:
            return
        joined_steps = "\n".join(current_steps)
        if hmap.has("steps"):
            ws.cell(row=current_header, column=hmap.fields["steps"]).value = joined_steps
        joined_exp = "\n".join(s for s in current_expecteds if s)
        if joined_exp:
            target = "expected_result" if hmap.has("expected_result") else "acceptance"
            if hmap.has(target):
                ws.cell(row=current_header, column=hmap.fields[target]).value = joined_exp

    for r in range(hmap.header_row + 1, ws.max_row + 1):
        # Skip fully empty rows
        if all(ws.cell(row=r, column=c).value in (None, "")
               for c in range(1, (ws.max_column or 0) + 1)):
            continue

        module = _row_module(r)
        title = _row_title(r)
        is_header = bool(module and title and module != "|")

        if is_header:
            _flush_into_header()
            current_header = r
            case_header_rows.append(r)
            current_steps = [_row_steps(r)] if _row_steps(r) else []
            current_expecteds = [_row_expected(r)] if _row_expected(r) else []
        else:
            # Continuation row - only meaningful if a header is open
            if current_header is None:
                continue
            steps_val = _row_steps(r)
            exp_val = _row_expected(r)
            if steps_val:
                current_steps.append(steps_val)
            if exp_val:
                current_expecteds.append(exp_val)

    _flush_into_header()
    return case_header_rows


# --------------------------------------------------------------------------- #
# Workbook driver + CSV writer
# --------------------------------------------------------------------------- #

def convert(
    xlsx_path: str,
    out_path: str,
    sheet_filter: str | None,
    module_prefix: str,
    reference_prefix_override: str | None,
    created_by: str,
    dry_run: bool,
    output_format: str = "merged-steps",
) -> ConvertResult:
    result = ConvertResult()
    wb = openpyxl.load_workbook(xlsx_path, data_only=True)

    all_records: list[CanonicalRecord] = []

    for sheet_name in wb.sheetnames:
        # Skip the hidden INSTRUCTIONS sheet that ships with the template.
        if sheet_name.upper() in {"INSTRUCTIONS", "README", "USERS",
                                  "REPORTS & SUMMARY", "INSIGHTS & RISKS"}:
            result.sheets_skipped.append(sheet_name)
            continue
        if sheet_filter and sheet_name != sheet_filter:
            result.sheets_skipped.append(sheet_name)
            continue

        ws = wb[sheet_name]
        reference_prefix = reference_prefix_override or re.sub(
            r"[^A-Za-z0-9]+", "", sheet_name).upper() or "SHEET"

        records = process_sheet(
            ws=ws,
            sheet_name=sheet_name,
            module_prefix=module_prefix,
            reference_prefix=reference_prefix,
            created_by=created_by,
            result=result,
        )
        all_records.extend(records)
        result.sheets_processed.append(sheet_name)

    wb.close()

    if not dry_run:
        os.makedirs(os.path.dirname(os.path.abspath(out_path)) or ".", exist_ok=True)
        with open(out_path, "w", newline="", encoding="utf-8") as fh:
            # newline="" so csv.writer controls line terminators; QUOTE_MINIMAL
            # so embedded LF newlines inside the Steps/Expected_result cells
            # cause the field to be wrapped in double quotes per RFC 4180.
            writer = csv.writer(fh, quoting=csv.QUOTE_MINIMAL, lineterminator="\r\n")
            writer.writerow(CANONICAL_COLUMNS)
            if output_format == "migration-rows":
                # Format B: one HEADER row per case carrying the metadata + Step
                # 1 + Expected 1, then (N-1) continuation rows with only
                # `steps` and `expected_result` filled. The QA Touch Data
                # Migration wizard at /v2/case/migration/import/p/{pid} treats
                # the blank-section_name continuation rows as additional step
                # rows of the most-recent case and creates them pre-split (each
                # CSV step-row becomes its own step row with its own
                # expected_result - no post-import step splitter needed; see
                # docs/local/qa_touch_integration.md §7.A.2).
                for rec in all_records:
                    n_steps = len(rec.steps_list)
                    if n_steps == 0:
                        continue  # build_record already warned + skipped
                    # Row 1 of this case: full metadata + Step 1 / Expected 1
                    writer.writerow([
                        rec.module_name,
                        rec.title,
                        rec.test_data,
                        rec.estimate,
                        rec.reference,
                        rec.precondition,
                        rec.steps_list[0],
                        rec.expected_list[0],
                        rec.test_suite,
                        rec.tags,
                        rec.description,
                        rec.case_type_title,
                        rec.priority_title,
                        rec.mode_title,
                        rec.created_by,
                    ])
                    # Rows 2..N: blank metadata, only steps/expected_result filled.
                    # 17 columns total; steps is col index 6, expected col index 7.
                    for i in range(1, n_steps):
                        row = [""] * len(CANONICAL_COLUMNS)
                        row[6] = rec.steps_list[i]
                        row[7] = rec.expected_list[i]
                        writer.writerow(row)
            else:
                # Format A: Format A (default) - one CSV row per case, merged
                # multi-line steps + expected. Standard import wizard at
                # /v2/case/import/p/{pid} ingests this; multi-line steps land
                # as a single merged "Step 1" row that the §5 step splitter
                # re-creates as N step rows post-import.
                for rec in all_records:
                    writer.writerow([
                        rec.module_name,
                        rec.title,
                        rec.test_data,
                        rec.estimate,
                        rec.reference,
                        rec.precondition,
                        rec.steps_merged,
                        rec.expected_merged,
                        rec.test_suite,
                        rec.tags,
                        rec.description,
                        rec.case_type_title,
                        rec.priority_title,
                        rec.mode_title,
                        rec.created_by,
                    ])

    result.rows_written = len(all_records)
    result.output_format = output_format
    return result


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description="Convert a QA-authored xlsx to the canonical QA Touch CSV.",
    )
    p.add_argument("--xlsx", required=True, help="Source .xlsx path")
    p.add_argument("--out", required=True, help="Output canonical .csv path")
    p.add_argument("--sheet", default=None,
                   help="Process only this sheet name (default: all eligible)")
    p.add_argument("--module-prefix", default="",
                   help="Optional prefix to prepend to every Module_name "
                        "(e.g. 'C2C'). Joined with ' > '.")
    p.add_argument("--reference-prefix", default=None,
                   help="Reference id prefix; default is the sanitized sheet name. "
                        "Format: {prefix}_{Type}_{index:03d}")
    p.add_argument("--created-by", default="QA Import",
                   help="Value written to the Created By column (default 'QA Import')")
    p.add_argument("--dry-run", action="store_true",
                   help="Parse + report stats; do not write the CSV")
    p.add_argument(
        "--format",
        dest="output_format",
        choices=["merged-steps", "migration-rows"],
        default="merged-steps",
        help="Output CSV layout. 'merged-steps' (default) = one row per case "
             "with newline-merged Steps and Expected_result cells, for the "
             "standard import wizard at /v2/case/import/p/{pid} (requires the "
             "Phase 5 step splitter after import). 'migration-rows' = header "
             "row per case + one continuation row per additional step, for "
             "the Data Migration wizard at /v2/case/migration/import/p/{pid} "
             "(steps land pre-split, no Phase 5 splitter needed). See "
             "docs/local/qa_touch_integration.md §7.A.2 for the Format B contract.",
    )
    return p.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)

    if not os.path.isfile(args.xlsx):
        print(f"ERROR: xlsx not found: {args.xlsx}", file=sys.stderr)
        return 1

    try:
        result = convert(
            xlsx_path=args.xlsx,
            out_path=args.out,
            sheet_filter=args.sheet,
            module_prefix=args.module_prefix,
            reference_prefix_override=args.reference_prefix,
            created_by=args.created_by,
            dry_run=args.dry_run,
            output_format=args.output_format,
        )
    except SystemExit as e:
        # FAIL LOUD messages route here.
        print(str(e), file=sys.stderr)
        return 2

    # ---- manifest (input contract for the backfill + step splitter) ----
    print("=" * 72)
    print(f"Source:           {args.xlsx}")
    print(f"Output:           {args.out}{'  (DRY RUN)' if args.dry_run else ''}")
    print(f"Output format:    {result.output_format}")
    print(f"Sheets processed: {result.sheets_processed}")
    print(f"Sheets skipped:   {result.sheets_skipped}")
    print(f"Cases written:    {result.rows_written}")
    print("Per-sheet row counts:")
    for s, n in result.sheet_row_counts.items():
        print(f"  {n:4d}  {s}")
    print(f"Rows with both Expected+Acceptance merged: {result.rows_received_both_expected}")
    print(f"Rows that used sheet-name for case_type:   {result.rows_used_sheet_name_for_type}")
    print(f"Type/Severity column-shift swaps applied:  {result.swaps_applied}")

    # Group warnings by kind for readability.
    by_kind: dict[str, list[Warning]] = {}
    for w in result.warnings:
        by_kind.setdefault(w.kind, []).append(w)
    if by_kind:
        print("Warnings:")
        for kind, ws_ in sorted(by_kind.items()):
            print(f"  [{kind}] x{len(ws_)}")
            for w in ws_[:10]:
                print(f"    {w.sheet} R{w.row}: {w.detail}")
            if len(ws_) > 10:
                print(f"    ...and {len(ws_) - 10} more")
    print("=" * 72)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
