#!/usr/bin/env python3
"""Import human-written test steps from Excel into QA Touch step JSON files.

Usage:
    python tools/excel_step_importer.py analyze [--excel PATH]
    python tools/excel_step_importer.py import [--dry-run] [--excel PATH]
    python tools/excel_step_importer.py validate
    python tools/excel_step_importer.py reset-checkpoint
"""

import argparse
import io
import json
import re
import sys
import unicodedata
from datetime import datetime
from pathlib import Path

# Force UTF-8 output on Windows
if sys.stdout.encoding != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import openpyxl

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
REPO = Path(__file__).resolve().parent.parent
SNAPSHOT_PATH = REPO / "config" / "qatouch_snapshots" / "snapshot_2026-02-20.json"
MANUAL_STEPS_DIR = REPO / "tests" / "steps" / "manual"
CHECKPOINT_PATH = REPO / "config" / "step_sync_checkpoint.json"
DEFAULT_EXCEL = Path(r"C:\path\to\downloads\Soterix_Testcases (1).xlsx")

# Standard column order (0-indexed) for most sheets
COLS = {
    "scenario": 0,
    "testing_type": 1,
    "severity": 2,
    "priority": 3,
    "feature": 4,
    "sub_feature": 5,
    "conditions": 6,
    "idea": 7,
    "data": 8,
    "acceptance": 9,
    "steps": 10,
}

# Admin-Licenses has an extra "Test Case ID" column at position 0
COLS_OFFSET = {k: v + 1 for k, v in COLS.items()}

# Verification verb prefixes for deriving expected results
VERIFY_PREFIXES = [
    "Verify that ", "Verify ", "Validate that ", "Validate ",
    "Confirm that ", "Confirm ", "Ensure that ", "Ensure ",
    "Check that ", "Check ",
]


# ---------------------------------------------------------------------------
# Excel parsing
# ---------------------------------------------------------------------------

def _norm(text: str) -> str:
    """Unicode NFKD normalize and strip."""
    if not text:
        return ""
    return unicodedata.normalize("NFKD", str(text)).strip()


def _cell_str(cell) -> str:
    """Extract string value from an openpyxl cell."""
    if cell is None or cell.value is None:
        return ""
    return _norm(str(cell.value))


def parse_excel(excel_path: Path) -> list[dict]:
    """Parse all sheets from the Excel file.

    Returns list of dicts with keys:
        scenario, feature, sub_feature, acceptance, steps_text, sheet_name
    """
    wb = openpyxl.load_workbook(excel_path, read_only=True, data_only=True)
    rows_out = []

    for sheet_name in wb.sheetnames:
        ws = wb[sheet_name]
        # Detect column offset (Admin-Licenses has extra col)
        cols = COLS
        header_row = next(ws.iter_rows(min_row=1, max_row=1, values_only=True), None)
        if header_row:
            header_strs = [_norm(str(h)) if h else "" for h in header_row]
            # If first column header looks like "Test Case ID", use offset
            if header_strs and "test case id" in header_strs[0].lower():
                cols = COLS_OFFSET

        for row in ws.iter_rows(min_row=2):  # skip header
            # Safe extraction with bounds checking
            def _get(key, row=row, cols=cols):  # bound per iteration, not at call time
                idx = cols[key]
                if idx < len(row):
                    return _cell_str(row[idx])
                return ""

            scenario = _get("scenario")
            if not scenario:
                continue

            steps_text = _get("steps")
            acceptance = _get("acceptance")
            feature = _get("feature")
            sub_feature = _get("sub_feature")

            rows_out.append({
                "scenario": scenario,
                "feature": feature,
                "sub_feature": sub_feature,
                "acceptance": acceptance,
                "steps_text": steps_text,
                "sheet_name": sheet_name,
            })

    wb.close()
    return rows_out


# ---------------------------------------------------------------------------
# Step parsing
# ---------------------------------------------------------------------------

def parse_steps_text(steps_text: str, acceptance: str = "") -> list[dict]:
    """Parse 'Step N: description' text into individual step dicts.

    Returns list of {"n": int, "action": str, "expected": str}.
    """
    if not steps_text or not steps_text.strip():
        return []

    # Split on "Step N:" pattern
    # Handle both "Step 1: ..." and "Step 1 : ..." and numbered without "Step"
    lines = re.split(r"\n(?=Step\s+\d+\s*:)", steps_text.strip())

    steps = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        # Remove "Step N:" prefix (may have nested prefix if Step 8 was empty)
        cleaned = re.sub(r"^Step\s+\d+\s*:\s*", "", line).strip()
        # Strip again in case of "Step 8:\nStep 9: text" merged into one line
        cleaned = re.sub(r"^Step\s+\d+\s*:\s*", "", cleaned).strip()
        if not cleaned:
            continue
        steps.append(cleaned)

    # If no "Step N:" pattern found, try splitting on plain newlines
    if not steps:
        for line in steps_text.strip().split("\n"):
            line = line.strip()
            if line:
                # Remove any leading numbering like "1." or "1)"
                cleaned = re.sub(r"^\d+[.)]\s*", "", line).strip()
                if cleaned:
                    steps.append(cleaned)

    if not steps:
        return []

    # Build step dicts with expected result logic
    result = []
    has_verify_step = any(_is_verify_step(s) for s in steps)

    for i, action_text in enumerate(steps, 1):
        expected = ""
        if _is_verify_step(action_text):
            expected = _derive_expected(action_text)
            # Last verify step: append acceptance criteria if available
            if i == len(steps) and acceptance and acceptance.strip():
                ac = acceptance.strip().rstrip(".")
                if expected and ac.lower() != expected.lower():
                    expected = f"{expected}. {ac}"
                elif not expected:
                    expected = ac
        elif i == len(steps) and not has_verify_step and acceptance and acceptance.strip():
            # All action-only steps: put acceptance on last step
            expected = acceptance.strip().rstrip(".")

        result.append({"n": i, "action": action_text, "expected": expected})

    return result


def _is_verify_step(text: str) -> bool:
    """Check if step text is a verification step."""
    lower = text.lower()
    return any(lower.startswith(p.lower()) for p in VERIFY_PREFIXES)


def _derive_expected(text: str) -> str:
    """Derive expected result from a verification step by stripping the verb prefix."""
    for prefix in VERIFY_PREFIXES:
        if text.lower().startswith(prefix.lower()):
            derived = text[len(prefix):].strip()
            if derived:
                # Capitalize first letter
                return derived[0].upper() + derived[1:]
    return ""


# ---------------------------------------------------------------------------
# QA Touch matching
# ---------------------------------------------------------------------------

def load_snapshot() -> list[dict]:
    """Load QA Touch snapshot cases."""
    with open(SNAPSHOT_PATH, encoding="utf-8") as f:
        data = json.load(f)
    return data["cases"]


def build_title_index(cases: list[dict]) -> dict:
    """Build normalized title -> case_key(s) index."""
    index = {}  # normalized_title -> list of case dicts
    for c in cases:
        title = _norm(c["case_title"])
        norm_title = title.lower().strip()
        if norm_title not in index:
            index[norm_title] = []
        index[norm_title].append(c)
    return index


def match_excel_to_qatouch(excel_rows: list[dict], qa_cases: list[dict]) -> dict:
    """Match Excel rows to QA Touch case_keys.

    Returns: {case_key: excel_row_dict} for matched cases.
    Also returns stats dict.
    """
    title_index = build_title_index(qa_cases)
    matched = {}  # case_key -> excel row
    unmatched_excel = []
    ambiguous = []

    # Track which QA Touch cases have been matched
    matched_keys = set()

    for row in excel_rows:
        scenario = row["scenario"]
        acceptance = row.get("acceptance", "")
        norm_scenario = _norm(scenario).lower().strip()

        case_key = None

        # Tier 1: Composite match "{Scenario} - {Acceptance Criteria}"
        if acceptance and acceptance.strip():
            composite = f"{_norm(scenario)} - {_norm(acceptance)}".lower().strip()
            hits = title_index.get(composite, [])
            unmatched_hits = [h for h in hits if h["case_key"] not in matched_keys]
            if len(unmatched_hits) == 1:
                case_key = unmatched_hits[0]["case_key"]
            elif len(unmatched_hits) > 1:
                # Take first unmatched
                case_key = unmatched_hits[0]["case_key"]

        # Tier 2: Plain scenario match
        if not case_key:
            hits = title_index.get(norm_scenario, [])
            unmatched_hits = [h for h in hits if h["case_key"] not in matched_keys]
            if len(unmatched_hits) == 1:
                case_key = unmatched_hits[0]["case_key"]
            elif len(unmatched_hits) > 1:
                # Multiple matches - try to narrow by module/feature
                case_key = None  # mark as ambiguous
                ambiguous.append({
                    "scenario": scenario,
                    "count": len(unmatched_hits),
                    "keys": [h["case_key"] for h in unmatched_hits[:5]],
                })

        # Tier 3: Prefix match (QA Touch title starts with scenario)
        if not case_key and len(norm_scenario) >= 20:
            for norm_title, cases_list in title_index.items():
                if norm_title.startswith(norm_scenario):
                    overlap = len(norm_scenario) / max(len(norm_title), 1)
                    if overlap >= 0.7:
                        unmatched_hits = [c for c in cases_list
                                          if c["case_key"] not in matched_keys]
                        if len(unmatched_hits) == 1:
                            case_key = unmatched_hits[0]["case_key"]
                            break

        if case_key and case_key not in matched_keys:
            matched[case_key] = row
            matched_keys.add(case_key)
        elif not case_key:
            unmatched_excel.append(row)

    stats = {
        "total_excel": len(excel_rows),
        "matched": len(matched),
        "unmatched_excel": len(unmatched_excel),
        "ambiguous": len(ambiguous),
        "ambiguous_details": ambiguous[:20],
    }

    return matched, stats


# ---------------------------------------------------------------------------
# Step JSON file operations
# ---------------------------------------------------------------------------

def load_step_files() -> dict:
    """Load all manual step JSON files.

    Returns: {file_path: json_data}
    """
    files = {}
    for p in sorted(MANUAL_STEPS_DIR.rglob("*.json")):
        if p.name == "generated_metadata.json":
            continue
        try:
            with open(p, encoding="utf-8") as f:
                data = json.load(f)
            if "tests" in data:
                files[p] = data
        except (json.JSONDecodeError, KeyError):
            print(f"  WARN: Could not parse {p}")
    return files


def update_step_files(matched: dict, dry_run: bool = False) -> dict:
    """Update step JSON files with Excel steps for matched cases.

    Returns stats dict.
    """
    step_files = load_step_files()
    updated_cases = 0
    preserved_cases = 0
    total_steps_written = 0
    skipped_no_steps = 0
    files_modified = 0

    for file_path, data in step_files.items():
        file_changed = False

        for case_key, test_data in data["tests"].items():
            if case_key in matched:
                excel_row = matched[case_key]
                steps = parse_steps_text(
                    excel_row["steps_text"],
                    excel_row.get("acceptance", ""),
                )
                if not steps:
                    skipped_no_steps += 1
                    preserved_cases += 1
                    continue

                if dry_run:
                    old_count = len(test_data.get("steps", []))
                    print(f"  [DRY] {case_key} ({test_data.get('title', '')[:60]}): "
                          f"{old_count} -> {len(steps)} steps")
                else:
                    test_data["steps"] = steps
                    test_data["source"] = "excel"
                    test_data["excel_imported_at"] = datetime.now().isoformat(
                        timespec="seconds"
                    )

                updated_cases += 1
                total_steps_written += len(steps)
                file_changed = True
            else:
                preserved_cases += 1

        if file_changed and not dry_run:
            files_modified += 1
            with open(file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
                f.write("\n")

    return {
        "updated_cases": updated_cases,
        "preserved_cases": preserved_cases,
        "total_steps_written": total_steps_written,
        "skipped_no_steps": skipped_no_steps,
        "files_modified": files_modified,
    }


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def validate_step_files() -> dict:
    """Run all validation checks on step JSON files.

    Returns dict with errors list and stats.
    """
    step_files = load_step_files()
    errors = []
    excel_cases = 0
    generated_cases = 0
    total_cases = 0

    for file_path, data in step_files.items():
        rel = file_path.relative_to(REPO)
        seen_keys = set()

        for case_key, test_data in data["tests"].items():
            total_cases += 1
            source = test_data.get("source", "generated")
            if source == "excel":
                excel_cases += 1
            else:
                generated_cases += 1

            # Check 1: No empty actions
            steps = test_data.get("steps", [])
            for s in steps:
                if not s.get("action", "").strip():
                    errors.append(f"EMPTY_ACTION: {case_key} step {s.get('n', '?')} in {rel}")

            # Check 2: Step numbering
            expected_nums = list(range(1, len(steps) + 1))
            actual_nums = [s.get("n", 0) for s in steps]
            if actual_nums != expected_nums:
                errors.append(f"BAD_NUMBERING: {case_key} in {rel}: {actual_nums}")

            # Check 3: No single-step blobs (Excel source should have parsed steps)
            if source == "excel" and len(steps) == 1:
                action = steps[0].get("action", "")
                if "Step " in action and "\n" in action:
                    errors.append(f"UNPARSED_BLOB: {case_key} in {rel}")

            # Check 4: No raw "Step N:" prefix in action
            for s in steps:
                action = s.get("action", "")
                if re.match(r"^Step\s+\d+\s*:", action):
                    errors.append(f"RAW_PREFIX: {case_key} step {s['n']} in {rel}: {action[:50]}")

            # Check 7: Duplicate case_key detection
            if case_key in seen_keys:
                errors.append(f"DUPLICATE_KEY: {case_key} in {rel}")
            seen_keys.add(case_key)

    return {
        "errors": errors,
        "total_cases": total_cases,
        "excel_cases": excel_cases,
        "generated_cases": generated_cases,
        "error_count": len(errors),
    }


# ---------------------------------------------------------------------------
# Checkpoint reset
# ---------------------------------------------------------------------------

def reset_checkpoint(matched_keys: set) -> dict:
    """Remove matched case_keys from the sync checkpoint."""
    if not CHECKPOINT_PATH.exists():
        return {"status": "no_checkpoint", "removed": 0}

    with open(CHECKPOINT_PATH, encoding="utf-8") as f:
        cp = json.load(f)

    old_keys = set(cp.get("synced_case_keys", []))
    to_remove = old_keys & matched_keys
    new_keys = sorted(old_keys - matched_keys)

    cp["synced_case_keys"] = new_keys
    cp["total_synced"] = len(new_keys)
    cp["last_updated"] = datetime.now().isoformat(timespec="seconds")

    with open(CHECKPOINT_PATH, "w", encoding="utf-8") as f:
        json.dump(cp, f, indent=2, ensure_ascii=False)
        f.write("\n")

    return {"removed": len(to_remove), "remaining": len(new_keys)}


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_analyze(args):
    """Parse Excel, match to QA Touch, print stats."""
    print(f"Loading Excel: {args.excel}")
    excel_rows = parse_excel(args.excel)
    print(f"  Parsed {len(excel_rows)} rows from Excel")

    # Stats on steps availability
    with_steps = sum(1 for r in excel_rows if r["steps_text"].strip())
    without_steps = len(excel_rows) - with_steps
    print(f"  With steps: {with_steps}, Without steps: {without_steps}")

    # Unique scenarios
    scenarios = set(r["scenario"] for r in excel_rows)
    print(f"  Unique scenarios: {len(scenarios)}")

    # Sheets breakdown
    sheets = {}
    for r in excel_rows:
        sheets.setdefault(r["sheet_name"], 0)
        sheets[r["sheet_name"]] += 1
    print(f"\n  Sheets ({len(sheets)}):")
    for name, count in sorted(sheets.items()):
        print(f"    {name}: {count} rows")

    print(f"\nLoading QA Touch snapshot: {SNAPSHOT_PATH.name}")
    qa_cases = load_snapshot()
    print(f"  {len(qa_cases)} QA Touch cases")

    print("\nMatching Excel -> QA Touch...")
    # Only match rows that have steps
    matchable = [r for r in excel_rows if r["steps_text"].strip()]
    matched, stats = match_excel_to_qatouch(matchable, qa_cases)

    print("\n  RESULTS:")
    print(f"  Total Excel rows with steps: {stats['total_excel']}")
    print(f"  Matched to QA Touch: {stats['matched']}")
    print(f"  Unmatched (Excel only): {stats['unmatched_excel']}")
    print(f"  Ambiguous (multiple matches): {stats['ambiguous']}")

    if stats["ambiguous_details"]:
        print("\n  Ambiguous details (first 20):")
        for a in stats["ambiguous_details"]:
            print(f"    '{a['scenario'][:60]}...' -> {a['count']} matches")

    # Check how many matched are in step files
    step_files = load_step_files()
    step_keys = set()
    for data in step_files.values():
        step_keys.update(data["tests"].keys())

    in_step_files = sum(1 for k in matched if k in step_keys)
    not_in_step_files = sum(1 for k in matched if k not in step_keys)

    print(f"\n  Of {len(matched)} matched:")
    print(f"    In step files (will update): {in_step_files}")
    print(f"    Not in step files (no update needed): {not_in_step_files}")
    print(f"    Step file cases NOT in Excel (preserved): {len(step_keys) - in_step_files}")

    # Sample matched steps
    print("\n  Sample matched cases (first 5 with steps):")
    shown = 0
    for ck, row in list(matched.items())[:20]:
        if not row["steps_text"].strip():
            continue
        steps = parse_steps_text(row["steps_text"], row.get("acceptance", ""))
        if steps:
            print(f"\n    [{ck}] {row['scenario'][:70]}")
            for s in steps[:4]:
                exp = f" -> {s['expected']}" if s["expected"] else ""
                print(f"      Step {s['n']}: {s['action'][:60]}{exp}")
            if len(steps) > 4:
                print(f"      ... and {len(steps) - 4} more steps")
            shown += 1
            if shown >= 5:
                break

    return matched


def cmd_import(args):
    """Update step JSON files with Excel steps."""
    print(f"Loading Excel: {args.excel}")
    excel_rows = parse_excel(args.excel)
    matchable = [r for r in excel_rows if r["steps_text"].strip()]

    print("Loading QA Touch snapshot...")
    qa_cases = load_snapshot()

    print(f"Matching {len(matchable)} Excel rows to {len(qa_cases)} QA Touch cases...")
    matched, stats = match_excel_to_qatouch(matchable, qa_cases)
    print(f"  Matched: {stats['matched']}")

    mode = "DRY RUN" if args.dry_run else "LIVE"
    print(f"\nUpdating step files ({mode})...")
    result = update_step_files(matched, dry_run=args.dry_run)

    print("\n  Results:")
    print(f"  Cases updated with Excel steps: {result['updated_cases']}")
    print(f"  Cases preserved (no match/no Excel steps): {result['preserved_cases']}")
    print(f"  Total steps written: {result['total_steps_written']}")
    print(f"  Skipped (matched but no Excel steps): {result['skipped_no_steps']}")
    if not args.dry_run:
        print(f"  Files modified: {result['files_modified']}")

    return matched


def cmd_validate(args):
    """Run validation checks on all step JSON files."""
    print("Validating step JSON files...")
    result = validate_step_files()

    print(f"\n  Total cases: {result['total_cases']}")
    print(f"  Excel-sourced: {result['excel_cases']}")
    print(f"  Generated: {result['generated_cases']}")
    print(f"  Errors: {result['error_count']}")

    if result["errors"]:
        print("\n  Error details:")
        for err in result["errors"][:50]:
            print(f"    {err}")
        if len(result["errors"]) > 50:
            print(f"    ... and {len(result['errors']) - 50} more")
        return False
    print("\n  ALL CHECKS PASSED")
    return True


def cmd_reset_checkpoint(args):
    """Clear checkpoint for Excel-updated cases."""
    print(f"Loading Excel: {args.excel}")
    excel_rows = parse_excel(args.excel)
    matchable = [r for r in excel_rows if r["steps_text"].strip()]

    print("Loading QA Touch snapshot...")
    qa_cases = load_snapshot()

    print("Matching...")
    matched, _stats = match_excel_to_qatouch(matchable, qa_cases)

    # Also check which matched keys are actually in step files with source=excel
    step_files = load_step_files()
    excel_keys = set()
    for data in step_files.values():
        for ck, td in data["tests"].items():
            if td.get("source") == "excel":
                excel_keys.add(ck)

    keys_to_reset = excel_keys & set(matched.keys())
    print(f"\n  Excel-sourced cases in step files: {len(excel_keys)}")
    print(f"  Keys to remove from checkpoint: {len(keys_to_reset)}")

    result = reset_checkpoint(keys_to_reset)
    print(f"  Removed: {result['removed']}")
    print(f"  Remaining in checkpoint: {result['remaining']}")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Import Excel test steps into QA Touch step files")
    parser.add_argument("--excel", type=Path, default=DEFAULT_EXCEL,
                        help="Path to Excel file")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("analyze", help="Parse Excel, match to QA Touch, print stats")

    imp = sub.add_parser("import", help="Update step JSON files with Excel steps")
    imp.add_argument("--dry-run", action="store_true", help="Preview changes only")

    sub.add_parser("validate", help="Validate step JSON files")
    sub.add_parser("reset-checkpoint", help="Clear checkpoint for updated cases")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    if args.command == "analyze":
        cmd_analyze(args)
    elif args.command == "import":
        cmd_import(args)
    elif args.command == "validate":
        cmd_validate(args)
    elif args.command == "reset-checkpoint":
        cmd_reset_checkpoint(args)


if __name__ == "__main__":
    main()
