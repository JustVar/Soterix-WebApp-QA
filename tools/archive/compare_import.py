#!/usr/bin/env python3
"""
QA Touch Import Comparison Tool

Compares incoming Excel/CSV files against the QA Touch master CSV to identify:
- Matched test cases (exist in both files)
- New test cases (in incoming only)
- Missing test cases (in QA Touch only)
- Potential renames (similar titles)

Usage:
    python compare_import.py <incoming_file> <qa_touch_csv> [options]

Example:
    python compare_import.py new_tests.xlsx qa_touch_import.csv
    python compare_import.py updates.csv qa_touch_import.csv --incoming-title "Test Name"
"""

import argparse
import sys
from pathlib import Path

try:
    import pandas as pd
except ImportError:
    print("Error: pandas is not installed.")
    print("Run: pip install pandas openpyxl")
    sys.exit(1)


def normalize_title(title):
    """Normalize title for comparison (lowercase, strip whitespace)."""
    if pd.isna(title):
        return ""
    return str(title).lower().strip()


def similarity_ratio(s1, s2):
    """Calculate simple similarity ratio between two strings."""
    if not s1 or not s2:
        return 0.0

    s1_lower = s1.lower()
    s2_lower = s2.lower()

    # Exact match
    if s1_lower == s2_lower:
        return 1.0

    # Check if one contains the other
    if s1_lower in s2_lower or s2_lower in s1_lower:
        return 0.8

    # Word overlap
    words1 = set(s1_lower.split())
    words2 = set(s2_lower.split())

    if not words1 or not words2:
        return 0.0

    intersection = words1 & words2
    union = words1 | words2

    return len(intersection) / len(union) if union else 0.0


def load_file(filepath, title_col, module_col):
    """Load Excel or CSV file and return DataFrame."""
    filepath = Path(filepath)

    if not filepath.exists():
        print(f"Error: File not found: {filepath}")
        sys.exit(1)

    # Determine file type and load
    if filepath.suffix.lower() in ['.xlsx', '.xls']:
        try:
            df = pd.read_excel(filepath)
        except ImportError:
            print("Error: openpyxl is not installed for Excel support.")
            print("Run: pip install openpyxl")
            sys.exit(1)
    elif filepath.suffix.lower() == '.csv':
        df = pd.read_csv(filepath)
    else:
        print(f"Error: Unsupported file type: {filepath.suffix}")
        print("Supported types: .xlsx, .xls, .csv")
        sys.exit(1)

    print(f"\nLoading: {filepath.name}")
    print(f"  Rows: {len(df)}")
    print(f"  Columns: {list(df.columns)}")

    # Verify required columns exist
    if title_col not in df.columns:
        # Try case-insensitive match
        col_map = {c.lower(): c for c in df.columns}
        if title_col.lower() in col_map:
            title_col = col_map[title_col.lower()]
        else:
            print(f"\nError: Column '{title_col}' not found in {filepath.name}")
            print(f"Available columns: {list(df.columns)}")
            sys.exit(1)

    return df, title_col, module_col


def compare_files(incoming_df, qa_df, incoming_title_col, qa_title_col,
                  incoming_module_col, qa_module_col):
    """Compare two DataFrames and return comparison results."""

    # Normalize titles for comparison
    incoming_titles = {normalize_title(t): t for t in incoming_df[incoming_title_col]}
    qa_titles = {normalize_title(t): t for t in qa_df[qa_title_col]}

    incoming_normalized = set(incoming_titles.keys())
    qa_normalized = set(qa_titles.keys())

    # Find matches and differences
    matched = incoming_normalized & qa_normalized
    incoming_only = incoming_normalized - qa_normalized
    qa_only = qa_normalized - incoming_normalized

    # Find potential renames (high similarity but not exact match)
    potential_renames = []
    for inc_title in incoming_only:
        for qa_title in qa_only:
            ratio = similarity_ratio(inc_title, qa_title)
            if ratio >= 0.7:  # 70% similarity threshold
                potential_renames.append({
                    'incoming': incoming_titles[inc_title],
                    'qa_touch': qa_titles[qa_title],
                    'similarity': f"{ratio:.0%}"
                })

    return {
        'matched': [(incoming_titles[t], qa_titles[t]) for t in matched],
        'incoming_only': [incoming_titles[t] for t in incoming_only],
        'qa_only': [qa_titles[t] for t in qa_only],
        'potential_renames': sorted(potential_renames, key=lambda x: x['similarity'], reverse=True)
    }


def print_results(results, verbose=False):
    """Print comparison results."""

    print("\n" + "=" * 60)
    print("COMPARISON RESULTS")
    print("=" * 60)

    matched_count = len(results['matched'])
    incoming_only_count = len(results['incoming_only'])
    qa_only_count = len(results['qa_only'])

    # Summary
    print(f"\n{'MATCHED:':<25} {matched_count} test cases")
    print(f"{'IN INCOMING ONLY:':<25} {incoming_only_count} test cases")
    print(f"{'IN QA TOUCH ONLY:':<25} {qa_only_count} test cases")

    # Status indicators
    if incoming_only_count == 0 and qa_only_count == 0:
        print("\n[OK] All test cases are aligned between files!")
    else:
        if incoming_only_count > 0:
            print(f"\n[!] {incoming_only_count} new test cases need to be added to QA Touch")
        if qa_only_count > 0:
            print(f"\n[!] {qa_only_count} test cases in QA Touch not found in incoming file")

    # Details for incoming only
    if results['incoming_only']:
        print("\n" + "-" * 60)
        print("TEST CASES IN INCOMING FILE ONLY (new)")
        print("-" * 60)
        for i, title in enumerate(results['incoming_only'][:20], 1):
            print(f"  {i}. {title[:70]}{'...' if len(str(title)) > 70 else ''}")
        if len(results['incoming_only']) > 20:
            print(f"  ... and {len(results['incoming_only']) - 20} more")

    # Details for QA Touch only
    if results['qa_only']:
        print("\n" + "-" * 60)
        print("TEST CASES IN QA TOUCH ONLY (missing from incoming)")
        print("-" * 60)
        for i, title in enumerate(results['qa_only'][:20], 1):
            print(f"  {i}. {title[:70]}{'...' if len(str(title)) > 70 else ''}")
        if len(results['qa_only']) > 20:
            print(f"  ... and {len(results['qa_only']) - 20} more")

    # Potential renames
    if results['potential_renames']:
        print("\n" + "-" * 60)
        print("POTENTIAL RENAMES (similar titles)")
        print("-" * 60)
        for item in results['potential_renames'][:10]:
            print(f"\n  Similarity: {item['similarity']}")
            print(f"  Incoming:  {item['incoming'][:60]}...")
            print(f"  QA Touch:  {item['qa_touch'][:60]}...")
        if len(results['potential_renames']) > 10:
            print(f"\n  ... and {len(results['potential_renames']) - 10} more potential matches")

    # Matched details (only if verbose)
    if verbose and results['matched']:
        print("\n" + "-" * 60)
        print("MATCHED TEST CASES")
        print("-" * 60)
        for i, (inc, qa) in enumerate(results['matched'][:50], 1):
            print(f"  {i}. {inc[:70]}{'...' if len(str(inc)) > 70 else ''}")
        if len(results['matched']) > 50:
            print(f"  ... and {len(results['matched']) - 50} more")

    print("\n" + "=" * 60)


def export_results(results, output_path):
    """Export comparison results to CSV."""

    # Create DataFrames for each category
    matched_df = pd.DataFrame(results['matched'], columns=['Incoming Title', 'QA Touch Title'])
    matched_df['Status'] = 'Matched'

    incoming_only_df = pd.DataFrame({'Title': results['incoming_only']})
    incoming_only_df['Status'] = 'Incoming Only (New)'

    qa_only_df = pd.DataFrame({'Title': results['qa_only']})
    qa_only_df['Status'] = 'QA Touch Only (Missing)'

    renames_df = pd.DataFrame(results['potential_renames'])
    if not renames_df.empty:
        renames_df['Status'] = 'Potential Rename'

    # Save to file
    with pd.ExcelWriter(output_path, engine='openpyxl') as writer:
        matched_df.to_excel(writer, sheet_name='Matched', index=False)
        incoming_only_df.to_excel(writer, sheet_name='Incoming Only', index=False)
        qa_only_df.to_excel(writer, sheet_name='QA Touch Only', index=False)
        if not renames_df.empty:
            renames_df.to_excel(writer, sheet_name='Potential Renames', index=False)

    print(f"\nResults exported to: {output_path}")


def main():
    parser = argparse.ArgumentParser(
        description='Compare incoming test case file against QA Touch master CSV',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python compare_import.py new_tests.xlsx qa_touch_import.csv
  python compare_import.py updates.csv qa_touch_import.csv --incoming-title "Test Name"
  python compare_import.py file.xlsx qa_touch_import.csv --export results.xlsx
        """
    )

    parser.add_argument('incoming_file', help='Incoming Excel or CSV file to compare')
    parser.add_argument('qa_touch_csv', help='QA Touch master CSV file')

    parser.add_argument('--incoming-title', default='title',
                        help='Column name for test title in incoming file (default: title)')
    parser.add_argument('--incoming-module', default='module',
                        help='Column name for module in incoming file (default: module)')
    parser.add_argument('--qa-title', default='title',
                        help='Column name for title in QA Touch CSV (default: title)')
    parser.add_argument('--qa-module', default='module',
                        help='Column name for module in QA Touch CSV (default: module)')

    parser.add_argument('--export', '-e', metavar='FILE',
                        help='Export results to Excel file')
    parser.add_argument('--verbose', '-v', action='store_true',
                        help='Show detailed output including matched entries')

    args = parser.parse_args()

    print("=" * 60)
    print("QA TOUCH IMPORT COMPARISON TOOL")
    print("=" * 60)

    # Load files
    incoming_df, incoming_title_col, incoming_module_col = load_file(
        args.incoming_file, args.incoming_title, args.incoming_module
    )

    qa_df, qa_title_col, qa_module_col = load_file(
        args.qa_touch_csv, args.qa_title, args.qa_module
    )

    # Compare
    results = compare_files(
        incoming_df, qa_df,
        incoming_title_col, qa_title_col,
        incoming_module_col, qa_module_col
    )

    # Print results
    print_results(results, verbose=args.verbose)

    # Export if requested
    if args.export:
        export_results(results, args.export)

    # Return exit code based on results
    if results['incoming_only'] or results['qa_only']:
        return 1  # Differences found
    return 0  # All matched


if __name__ == '__main__':
    sys.exit(main())
