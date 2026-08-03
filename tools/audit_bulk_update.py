#!/usr/bin/env python3
"""Full audit of QATouch_BulkUpdate_Steps.xlsx against QA Touch export and Excel import."""

import io
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path

if sys.stdout.encoding != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding="utf-8", errors="replace")

import openpyxl

BULK_UPDATE = Path(r"C:\Users\JustinVarughese\Downloads\QATouch_BulkUpdate_Steps.xlsx")
QT_EXPORT = Path(r"C:\Users\JustinVarughese\Downloads\TestCases_06-03-26-15_23_43.xlsx\TestCases_06-03-26-15_23_43.xlsx")
EXCEL_IMPORT = Path(r"C:\Users\JustinVarughese\Downloads\Soterix_Testcases (1).xlsx")

COLS = {"scenario": 0, "acceptance": 9, "steps": 10}
COLS_OFFSET = {k: v + 1 for k, v in COLS.items()}


def norm(t):
    t = unicodedata.normalize("NFKD", str(t)).strip()
    t = re.sub(r"\s+", " ", t)
    t = t.replace("\u22ee", "...").replace("\u2026", "...")
    t = t.replace("\u2192", "-").replace("\u2190", "-")
    t = t.replace("\u2013", "-").replace("\u2014", "-")
    t = t.replace("\u201c", '"').replace("\u201d", '"')
    t = t.replace("\u2018", "'").replace("\u2019", "'")
    return t.lower().strip()


def load_xlsx_rows(path):
    wb = openpyxl.load_workbook(path, read_only=True)
    ws = wb["CasesSheet"]
    rows = list(ws.iter_rows(min_row=2, values_only=True))
    wb.close()
    return rows


def load_excel_import():
    wb = openpyxl.load_workbook(EXCEL_IMPORT, read_only=True, data_only=True)
    rows = []
    for sn in wb.sheetnames:
        ws = wb[sn]
        cols = COLS
        header = next(ws.iter_rows(min_row=1, max_row=1, values_only=True), None)
        if header and header[0] and "test case id" in str(header[0]).lower():
            cols = COLS_OFFSET
        for row in ws.iter_rows(min_row=2, values_only=True):
            sc_idx = cols["scenario"]
            if sc_idx >= len(row) or not row[sc_idx]:
                continue
            scenario = str(row[sc_idx]).strip()
            if not scenario:
                continue
            ac_idx, st_idx = cols["acceptance"], cols["steps"]
            acceptance = str(row[ac_idx]).strip() if ac_idx < len(row) and row[ac_idx] else ""
            steps = str(row[st_idx]).strip() if st_idx < len(row) and row[st_idx] else ""
            rows.append({"scenario": scenario, "acceptance": acceptance, "steps_text": steps, "sheet": sn})
    wb.close()
    return rows


def main():
    errors = []
    warnings = []

    print("=" * 70)
    print("  FULL AUDIT: Bulk Update vs QA Touch Export vs Excel Import")
    print("=" * 70)

    # ---------------------------------------------------------------
    # 1. Load all three sources
    # ---------------------------------------------------------------
    print("\n[1] Loading data sources...")
    bu_rows = load_xlsx_rows(BULK_UPDATE)
    qt_rows = load_xlsx_rows(QT_EXPORT)
    excel_rows = load_excel_import()

    print(f"  Bulk Update:  {len(bu_rows)} cases")
    print(f"  QA Touch:     {len(qt_rows)} cases")
    print(f"  Excel Import: {len(excel_rows)} rows")

    if len(bu_rows) != len(qt_rows):
        errors.append(f"CASE COUNT MISMATCH: Bulk Update has {len(bu_rows)}, QA Touch has {len(qt_rows)}")

    # ---------------------------------------------------------------
    # 2. Row-by-row comparison: case keys and order
    # ---------------------------------------------------------------
    print("\n[2] Verifying case keys and order...")
    bu_keys = [r[0] for r in bu_rows]
    qt_keys = [r[0] for r in qt_rows]

    if bu_keys == qt_keys:
        print("  PASS: All case keys match in same order")
    else:
        bu_set = set(bu_keys)
        qt_set = set(qt_keys)
        missing = qt_set - bu_set
        extra = bu_set - qt_set
        if missing:
            errors.append(f"MISSING CASES: {len(missing)} QA Touch cases not in Bulk Update: {list(missing)[:5]}")
        if extra:
            errors.append(f"EXTRA CASES: {len(extra)} cases in Bulk Update not in QA Touch: {list(extra)[:5]}")
        if bu_set == qt_set:
            warnings.append("Case keys match but ORDER differs")

    # ---------------------------------------------------------------
    # 3. Metadata preservation: tags, mode, type, priority, module
    # ---------------------------------------------------------------
    print("\n[3] Verifying metadata preservation (tags, mode, type, priority, module)...")
    # Columns: 0=Key, 4=Module, 6=Type, 7=Priority, 15=Mode, 16=Tags, 17=NewTags, 18=TestSuite
    metadata_cols = {
        "Module": 4,
        "Type": 6,
        "Priority": 7,
        "Mode": 15,
        "Tags": 16,
        "NewTags": 17,
        "TestSuite": 18,
        "Description": 19,
    }

    qt_by_key = {r[0]: r for r in qt_rows}
    bu_by_key = {r[0]: r for r in bu_rows}

    meta_changes = {}
    for col_name, col_idx in metadata_cols.items():
        changed = 0
        for key in bu_keys:
            bu_val = str(bu_by_key[key][col_idx]) if bu_by_key[key][col_idx] else ""
            qt_val = str(qt_by_key[key][col_idx]) if qt_by_key[key][col_idx] else ""
            if bu_val != qt_val:
                changed += 1
                if changed <= 2:
                    warnings.append(f"  {col_name} changed for [{key}]: '{qt_val[:30]}' -> '{bu_val[:30]}'")
        meta_changes[col_name] = changed

    for col_name, count in meta_changes.items():
        if count == 0:
            print(f"  PASS: {col_name} - no changes")
        else:
            errors.append(f"METADATA CHANGED: {col_name} changed for {count} cases")

    # ---------------------------------------------------------------
    # 4. Title changes audit
    # ---------------------------------------------------------------
    print("\n[4] Auditing title changes...")
    title_changes = []
    for key in bu_keys:
        bu_title = str(bu_by_key[key][5]) if bu_by_key[key][5] else ""
        qt_title = str(qt_by_key[key][5]) if qt_by_key[key][5] else ""
        if bu_title != qt_title:
            title_changes.append({
                "key": key,
                "module": str(bu_by_key[key][4]) if bu_by_key[key][4] else "",
                "old": qt_title,
                "new": bu_title,
            })

    print(f"  Title changes: {len(title_changes)}")
    if title_changes:
        for tc in title_changes:
            print(f"    [{tc['key']}] [{tc['module']}]")
            print(f"      OLD: {tc['old'][:70]}")
            print(f"      NEW: {tc['new'][:70]}")

    # ---------------------------------------------------------------
    # 5. Steps changes audit
    # ---------------------------------------------------------------
    print("\n[5] Auditing step changes...")
    steps_changed = 0
    steps_unchanged = 0
    steps_added = 0  # had no steps before
    step_count_changes = []

    for key in bu_keys:
        bu_steps = str(bu_by_key[key][11]) if bu_by_key[key][11] else ""
        qt_steps = str(qt_by_key[key][11]) if qt_by_key[key][11] else ""
        bu_exp = str(bu_by_key[key][12]) if bu_by_key[key][12] else ""
        qt_exp = str(qt_by_key[key][12]) if qt_by_key[key][12] else ""

        if bu_steps == qt_steps and bu_exp == qt_exp:
            steps_unchanged += 1
        else:
            steps_changed += 1
            bu_count = len([l for l in bu_steps.split("\n") if l.strip()])
            qt_count = len([l for l in qt_steps.split("\n") if l.strip()])
            if qt_count == 0:
                steps_added += 1
            step_count_changes.append({
                "key": key,
                "old_count": qt_count,
                "new_count": bu_count,
                "title": str(bu_by_key[key][5])[:50] if bu_by_key[key][5] else "",
            })

    print(f"  Steps changed: {steps_changed}")
    print(f"  Steps unchanged: {steps_unchanged}")
    print(f"  Steps added (had none): {steps_added}")

    # Distribution of step count changes
    if step_count_changes:
        increases = sum(1 for s in step_count_changes if s["new_count"] > s["old_count"])
        decreases = sum(1 for s in step_count_changes if s["new_count"] < s["old_count"])
        same_count = sum(1 for s in step_count_changes if s["new_count"] == s["old_count"])
        print(f"  Step count increased: {increases}")
        print(f"  Step count decreased: {decreases}")
        print(f"  Step count same (content changed): {same_count}")

        # Cases where steps decreased significantly (potential issue)
        big_decreases = [s for s in step_count_changes if s["old_count"] - s["new_count"] >= 5]
        if big_decreases:
            print(f"\n  WARNING: {len(big_decreases)} cases with 5+ fewer steps:")
            for s in big_decreases[:10]:
                print(f"    [{s['key']}] {s['title']} ({s['old_count']} -> {s['new_count']})")

    # ---------------------------------------------------------------
    # 6. Cross-reference: verify Excel steps land on correct cases
    # ---------------------------------------------------------------
    print("\n[6] Cross-referencing Excel steps to Bulk Update cases...")

    # For a sample of cases, verify the steps in bulk update match the Excel source
    # Pick 20 random cases that were changed
    import random
    random.seed(42)
    changed_keys = [s["key"] for s in step_count_changes]
    sample_keys = random.sample(changed_keys, min(20, len(changed_keys)))

    # Build Excel title->steps map for validation
    excel_by_norm_title = {}
    for er in excel_rows:
        nt = norm(er["scenario"])
        excel_by_norm_title.setdefault(nt, []).append(er)

    mismatches = 0
    for key in sample_keys:
        bu_row = bu_by_key[key]
        bu_title = norm(str(bu_row[5]) if bu_row[5] else "")
        bu_steps_raw = str(bu_row[11]) if bu_row[11] else ""
        bu_step1 = bu_steps_raw.split("\n")[0].strip() if bu_steps_raw else ""

        # Find matching Excel row
        # Try exact title match first, then prefix
        excel_match = None
        for et, ers in excel_by_norm_title.items():
            if et == bu_title or bu_title.startswith(et) or et.startswith(bu_title):
                for er in ers:
                    # Check if step 1 matches
                    er_steps = er["steps_text"]
                    er_step1 = ""
                    if er_steps:
                        cleaned = re.sub(r"^Step\s+\d+\s*:\s*", "", er_steps.split("\n")[0]).strip()
                        cleaned = re.sub(r"^Step\s+\d+\s*:\s*", "", cleaned).strip()
                        cleaned = re.sub(r"^\d+[.)]\s*", "", cleaned).strip()
                        er_step1 = cleaned

                    if er_step1 and bu_step1 and er_step1[:30] == bu_step1[:30]:
                        excel_match = er
                        break
                if excel_match:
                    break

        if not excel_match:
            mismatches += 1
            warnings.append(f"Could not verify Excel source for [{key}] {bu_title[:50]}")

    print(f"  Spot-checked {len(sample_keys)} cases: {len(sample_keys) - mismatches} verified, {mismatches} unverifiable")

    # ---------------------------------------------------------------
    # 7. Check for empty/malformed steps
    # ---------------------------------------------------------------
    print("\n[7] Checking for empty or malformed steps...")
    empty_steps = 0
    single_step = 0
    raw_prefix = 0
    step_exp_mismatch = 0

    for key in bu_keys:
        bu_steps = str(bu_by_key[key][11]) if bu_by_key[key][11] else ""
        bu_exp = str(bu_by_key[key][12]) if bu_by_key[key][12] else ""
        step_lines = bu_steps.split("\n")
        exp_lines = bu_exp.split("\n")

        # Empty steps
        non_empty = [l for l in step_lines if l.strip()]
        if not non_empty:
            empty_steps += 1
            continue

        # Single step (potential unparsed blob)
        if len(non_empty) == 1 and "Step " in non_empty[0]:
            raw_prefix += 1

        # Step/Expected count mismatch
        if len(step_lines) != len(exp_lines) and bu_exp.strip():
            step_exp_mismatch += 1

        # Check for raw "Step N:" prefix
        for sl in non_empty:
            if re.match(r"^Step\s+\d+\s*:", sl):
                raw_prefix += 1
                break

    print(f"  Empty steps: {empty_steps}")
    print(f"  Raw 'Step N:' prefix in steps: {raw_prefix}")
    print(f"  Step/Expected line count mismatch: {step_exp_mismatch}")

    if empty_steps:
        errors.append(f"EMPTY STEPS: {empty_steps} cases have no steps")
    if raw_prefix:
        warnings.append(f"RAW PREFIX: {raw_prefix} cases have 'Step N:' prefix in step text")
    if step_exp_mismatch:
        warnings.append(f"STEP/EXP MISMATCH: {step_exp_mismatch} cases have different step/expected line counts")

    # ---------------------------------------------------------------
    # 8. Duplicate title check (post-rename)
    # ---------------------------------------------------------------
    print("\n[8] Checking for remaining duplicate titles after renames...")
    bu_titles = [str(r[5]).lower().strip() if r[5] else "" for r in bu_rows]
    title_counts = Counter(bu_titles)
    dupes = {t: c for t, c in title_counts.items() if c > 1}
    if dupes:
        warnings.append(f"REMAINING DUPLICATES: {len(dupes)} duplicate title groups after renames")
        for t, c in sorted(dupes.items(), key=lambda x: -x[1]):
            cases = [r for r in bu_rows if str(r[5]).lower().strip() == t]
            modules = set(str(r[4]) for r in cases)
            print(f"  {c}x: '{t[:60]}' in modules: {modules}")
    else:
        print("  PASS: No duplicate titles remain")

    # ---------------------------------------------------------------
    # 9. Summary
    # ---------------------------------------------------------------
    print("\n" + "=" * 70)
    print("  AUDIT SUMMARY")
    print("=" * 70)
    print(f"\n  Cases in Bulk Update: {len(bu_rows)}")
    print(f"  Cases in QA Touch:    {len(qt_rows)}")
    print(f"  Steps updated:        {steps_changed}")
    print(f"  Steps preserved:      {steps_unchanged}")
    print(f"  Titles renamed:       {len(title_changes)}")

    print(f"\n  ERRORS:   {len(errors)}")
    for e in errors:
        print(f"    [ERROR] {e}")

    print(f"\n  WARNINGS: {len(warnings)}")
    for w in warnings:
        print(f"    [WARN]  {w}")

    if not errors:
        print("\n  RESULT: PASS - Safe to import")
    else:
        print("\n  RESULT: FAIL - Fix errors before importing")

    # ---------------------------------------------------------------
    # 10. Renamed titles detail
    # ---------------------------------------------------------------
    print("\n" + "=" * 70)
    print("  RENAMED TITLES (Original -> New)")
    print("=" * 70)
    for tc in title_changes:
        print(f"\n  [{tc['key']}] Module: {tc['module']}")
        print(f"    ORIGINAL: {tc['old']}")
        print(f"    RENAMED:  {tc['new']}")


if __name__ == "__main__":
    main()
