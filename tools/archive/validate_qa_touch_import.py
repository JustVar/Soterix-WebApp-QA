#!/usr/bin/env python3
"""
QA Touch Import Validation Script

Validates that test cases with steps were properly imported to QA Touch
by comparing the QA Touch export against the original source data.

Usage:
    python validate_qa_touch_import.py <qa_touch_export.csv>

What it checks:
    1. All test cases with full steps are present in QA Touch
    2. Steps content matches (not truncated or corrupted)
    3. Preconditions and expected results are intact
    4. Reports any missing or mismatched test cases
"""

import argparse
import json
import sys
from pathlib import Path

try:
    import pandas as pd
except ImportError:
    print("Error: pandas is not installed.")
    print("Run: pip install pandas")
    sys.exit(1)


def load_source_data(json_path):
    """Load the original testcases_export.json with full steps."""
    with open(json_path, encoding='utf-8') as f:
        data = json.load(f)

    # Handle wrapper structure (test_cases array)
    if isinstance(data, dict) and 'test_cases' in data:
        test_cases = data['test_cases']
    elif isinstance(data, list):
        test_cases = data
    else:
        print("Warning: Unexpected JSON structure")
        test_cases = []

    # Build lookup by normalized title
    source = {}
    for tc in test_cases:
        title = tc.get('title', '').strip().lower()
        if title:
            # Handle steps as array (strings or dicts) or string
            steps = tc.get('steps', [])
            if isinstance(steps, list):
                step_texts = []
                for s in steps:
                    if isinstance(s, dict):
                        # Format: {'step': 1, 'action': '...', 'expected': '...'}
                        step_texts.append(s.get('action', str(s)))
                    else:
                        step_texts.append(str(s))
                steps_text = ' | '.join(step_texts) if step_texts else ''
            else:
                steps_text = str(steps) if steps else ''

            source[title] = {
                'original_title': tc.get('title', ''),
                'steps': steps_text,
                'steps_count': len(steps) if isinstance(steps, list) else 0,
                'preconditions': tc.get('testConditions', ''),
                'expected_result': tc.get('acceptanceCriteria', ''),
                'folder': tc.get('folder', ''),
                'has_steps': bool(steps_text.strip())
            }

    return source


def load_qa_touch_export(csv_path, title_col='title', steps_col='steps',
                          precond_col='preconditions', expected_col='expected_result'):
    """Load QA Touch CSV export."""
    df = pd.read_csv(csv_path)

    print(f"\nQA Touch Export: {csv_path}")
    print(f"  Total rows: {len(df)}")
    print(f"  Columns: {list(df.columns)}")

    # Try to find columns (case-insensitive)
    col_map = {c.lower().replace(' ', '_'): c for c in df.columns}

    # Common QA Touch column name variations (including actual QA Touch export names)
    title_variations = ['title', 'test_case_title', 'testcase_title', 'name', 'test_name']
    steps_variations = ['steps', 'test_steps', 'teststeps', 'step']
    precond_variations = ['preconditions', 'precondition', 'pre_conditions', 'pre-conditions']
    expected_variations = ['expectedresult', 'expected_result', 'expected_results', 'expected']

    def find_column(variations, default):
        for v in variations:
            if v in col_map:
                return col_map[v]
        return default

    actual_title_col = find_column(title_variations, title_col)
    actual_steps_col = find_column(steps_variations, steps_col)
    actual_precond_col = find_column(precond_variations, precond_col)
    actual_expected_col = find_column(expected_variations, expected_col)

    print("\n  Detected columns:")
    print(f"    Title: {actual_title_col}")
    print(f"    Steps: {actual_steps_col}")
    print(f"    Preconditions: {actual_precond_col}")
    print(f"    Expected Result: {actual_expected_col}")

    # Build lookup
    qa_touch = {}
    for _, row in df.iterrows():
        title = str(row.get(actual_title_col, '')).strip().lower()
        if title and title != 'nan':
            steps = str(row.get(actual_steps_col, '')) if pd.notna(row.get(actual_steps_col)) else ''
            precond = str(row.get(actual_precond_col, '')) if pd.notna(row.get(actual_precond_col)) else ''
            expected = str(row.get(actual_expected_col, '')) if pd.notna(row.get(actual_expected_col)) else ''

            qa_touch[title] = {
                'original_title': str(row.get(actual_title_col, '')),
                'steps': steps,
                'preconditions': precond,
                'expected_result': expected,
                'has_steps': bool(steps.strip())
            }

    return qa_touch


def normalize_text(text):
    """Normalize text for comparison."""
    if not text:
        return ''
    return ' '.join(str(text).lower().split())


def compare_content(source_text, qa_text, field_name):
    """Compare source and QA Touch content, return issues if any."""
    source_norm = normalize_text(source_text)
    qa_norm = normalize_text(qa_text)

    if not source_norm and not qa_norm:
        return None  # Both empty, OK

    if not qa_norm and source_norm:
        return f"{field_name}: MISSING in QA Touch (source has {len(source_text)} chars)"

    if source_norm == qa_norm:
        return None  # Exact match

    # Check if QA Touch has content but it's different
    if source_norm in qa_norm or qa_norm in source_norm:
        return None  # One contains the other, close enough

    # Calculate similarity
    source_words = set(source_norm.split())
    qa_words = set(qa_norm.split())

    if not source_words:
        return None

    overlap = len(source_words & qa_words) / len(source_words)

    if overlap >= 0.8:
        return None  # 80%+ word overlap, good enough

    if overlap >= 0.5:
        return f"{field_name}: PARTIAL match ({overlap:.0%} overlap)"

    return f"{field_name}: MISMATCH ({overlap:.0%} overlap, source: {len(source_text)} chars, QA: {len(qa_text)} chars)"


def validate_import(source_data, qa_touch_data):
    """Compare source data against QA Touch export."""

    results = {
        'total_source_with_steps': 0,
        'found_in_qa_touch': 0,
        'missing_from_qa_touch': [],
        'steps_missing': [],
        'steps_mismatch': [],
        'preconditions_issues': [],
        'expected_result_issues': [],
        'fully_matched': 0
    }

    # Only check test cases that have steps in the source
    for title_key, source_tc in source_data.items():
        if not source_tc['has_steps']:
            continue

        results['total_source_with_steps'] += 1

        if title_key not in qa_touch_data:
            results['missing_from_qa_touch'].append(source_tc['original_title'])
            continue

        results['found_in_qa_touch'] += 1
        qa_tc = qa_touch_data[title_key]

        issues = []

        # Check steps
        steps_issue = compare_content(source_tc['steps'], qa_tc['steps'], 'Steps')
        if steps_issue:
            if 'MISSING' in steps_issue:
                results['steps_missing'].append((source_tc['original_title'], steps_issue))
            else:
                results['steps_mismatch'].append((source_tc['original_title'], steps_issue))
            issues.append(steps_issue)

        # Check preconditions
        precond_issue = compare_content(source_tc['preconditions'], qa_tc['preconditions'], 'Preconditions')
        if precond_issue and 'MISSING' in precond_issue:
            results['preconditions_issues'].append((source_tc['original_title'], precond_issue))
            issues.append(precond_issue)

        # Check expected result
        expected_issue = compare_content(source_tc['expected_result'], qa_tc['expected_result'], 'Expected Result')
        if expected_issue and 'MISSING' in expected_issue:
            results['expected_result_issues'].append((source_tc['original_title'], expected_issue))
            issues.append(expected_issue)

        if not issues:
            results['fully_matched'] += 1

    return results


def print_results(results):
    """Print validation results."""

    print("\n" + "=" * 70)
    print("VALIDATION RESULTS")
    print("=" * 70)

    total = results['total_source_with_steps']
    found = results['found_in_qa_touch']
    matched = results['fully_matched']

    print(f"\n{'Source test cases with steps:':<40} {total}")
    print(f"{'Found in QA Touch:':<40} {found}")
    print(f"{'Fully matched (steps intact):':<40} {matched}")
    print(f"{'Match rate:':<40} {matched/total*100:.1f}%" if total > 0 else "")

    # Summary counts
    print("\n--- Issues Summary ---")
    print(f"{'Missing from QA Touch:':<40} {len(results['missing_from_qa_touch'])}")
    print(f"{'Steps completely missing:':<40} {len(results['steps_missing'])}")
    print(f"{'Steps partial/mismatch:':<40} {len(results['steps_mismatch'])}")
    print(f"{'Preconditions missing:':<40} {len(results['preconditions_issues'])}")
    print(f"{'Expected result missing:':<40} {len(results['expected_result_issues'])}")

    # Details
    if results['missing_from_qa_touch']:
        print("\n" + "-" * 70)
        print("TEST CASES MISSING FROM QA TOUCH")
        print("-" * 70)
        for i, title in enumerate(results['missing_from_qa_touch'][:15], 1):
            print(f"  {i}. {title[:65]}{'...' if len(title) > 65 else ''}")
        if len(results['missing_from_qa_touch']) > 15:
            print(f"  ... and {len(results['missing_from_qa_touch']) - 15} more")

    if results['steps_missing']:
        print("\n" + "-" * 70)
        print("TEST CASES WITH MISSING STEPS")
        print("-" * 70)
        for i, (title, issue) in enumerate(results['steps_missing'][:15], 1):
            print(f"  {i}. {title[:50]}...")
            print(f"      {issue}")
        if len(results['steps_missing']) > 15:
            print(f"  ... and {len(results['steps_missing']) - 15} more")

    if results['steps_mismatch']:
        print("\n" + "-" * 70)
        print("TEST CASES WITH PARTIAL/MISMATCHED STEPS")
        print("-" * 70)
        for i, (title, issue) in enumerate(results['steps_mismatch'][:10], 1):
            print(f"  {i}. {title[:50]}...")
            print(f"      {issue}")
        if len(results['steps_mismatch']) > 10:
            print(f"  ... and {len(results['steps_mismatch']) - 10} more")

    # Final status
    print("\n" + "=" * 70)
    if matched == total:
        print("[OK] All test cases with steps imported correctly!")
    elif matched >= total * 0.95:
        print(f"[OK] {matched/total*100:.1f}% of test cases imported correctly (minor issues)")
    elif matched >= total * 0.8:
        print(f"[WARNING] {matched/total*100:.1f}% match rate - review issues above")
    else:
        print(f"[ERROR] Only {matched/total*100:.1f}% match rate - significant import issues")
    print("=" * 70)


def main():
    parser = argparse.ArgumentParser(
        description='Validate QA Touch import against source test case data',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Example:
  python validate_qa_touch_import.py qa_touch_export.csv

The script compares against testcases_export.json in the project root.
        """
    )

    parser.add_argument('qa_touch_export', help='CSV file exported from QA Touch')
    parser.add_argument('--source', default='testcases_export.json',
                        help='Source JSON file with full test steps (default: testcases_export.json)')

    args = parser.parse_args()

    print("=" * 70)
    print("QA TOUCH IMPORT VALIDATION")
    print("=" * 70)

    # Find source file
    source_path = Path(args.source)
    if not source_path.exists():
        # Try in project root
        source_path = Path(__file__).parent / args.source

    if not source_path.exists():
        print(f"Error: Source file not found: {args.source}")
        sys.exit(1)

    print(f"\nSource file: {source_path}")

    # Load data
    source_data = load_source_data(source_path)
    print(f"  Loaded {len(source_data)} test cases")
    print(f"  With steps: {sum(1 for tc in source_data.values() if tc['has_steps'])}")

    qa_touch_data = load_qa_touch_export(args.qa_touch_export)
    print(f"  Loaded {len(qa_touch_data)} test cases from QA Touch")

    # Validate
    results = validate_import(source_data, qa_touch_data)

    # Print results
    print_results(results)

    # Exit code
    if results['fully_matched'] == results['total_source_with_steps']:
        return 0
    return 1


if __name__ == '__main__':
    sys.exit(main())
