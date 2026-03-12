#!/usr/bin/env python3
"""Generate step definition stub JSON files from test source files.

Scans test files using AST parsing, extracts class + method names,
and creates skeleton JSON step files in tests/steps/.

Usage:
    # Generate stubs for all test files
    python tools/generate_step_stubs.py

    # Generate for specific files
    python tools/generate_step_stubs.py tests/ui/admin/test_admin_audit_trail.py

    # Overwrite existing step files (normally skipped)
    python tools/generate_step_stubs.py --overwrite

    # Show what would be generated (dry run)
    python tools/generate_step_stubs.py --dry-run
"""
from __future__ import annotations

import argparse
import ast
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TESTS_DIR = ROOT / 'tests'
STEPS_DIR = ROOT / 'tests' / 'steps'


def extract_test_methods(file_path: Path) -> list[dict]:
    """Parse a Python test file and extract test classes/methods.

    Returns list of dicts:
        [{class_name, method_name, docstring, markers}, ...]
    """
    try:
        source = file_path.read_text(encoding='utf-8')
        tree = ast.parse(source, filename=str(file_path))
    except (SyntaxError, OSError) as e:
        print(f'  Warning: Could not parse {file_path}: {e}')
        return []

    results = []

    for node in ast.walk(tree):
        if not isinstance(node, ast.ClassDef):
            continue
        if not node.name.startswith('Test'):
            continue

        class_name = node.name
        class_docstring = ast.get_docstring(node) or ''

        for item in node.body:
            if not isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            if not item.name.startswith('test_'):
                continue

            # Extract markers from decorators
            markers = []
            for dec in item.decorator_list:
                if isinstance(dec, ast.Attribute) and isinstance(dec.value, ast.Attribute):
                    # @pytest.mark.smoke
                    if hasattr(dec.value, 'attr') and dec.value.attr == 'mark':
                        markers.append(dec.attr)
                elif isinstance(dec, ast.Call) and isinstance(dec.func, ast.Attribute):
                    # @pytest.mark.flaky(reruns=1)
                    if hasattr(dec.func, 'value') and isinstance(dec.func.value, ast.Attribute):
                        if dec.func.value.attr == 'mark':
                            markers.append(dec.func.attr)

            docstring = ast.get_docstring(item) or ''

            results.append({
                'class_name': class_name,
                'class_docstring': class_docstring,
                'method_name': item.name,
                'docstring': docstring,
                'markers': markers,
            })

    return results


def generate_stub(file_path: Path, methods: list[dict]) -> dict:
    """Generate a step definition stub dict for a test file."""
    # Determine the relative test path
    try:
        relative = file_path.relative_to(TESTS_DIR)
    except ValueError:
        relative = file_path

    # Group by class
    class_name = methods[0]['class_name'] if methods else 'Unknown'

    tests = {}
    for m in methods:
        # Create a placeholder step from the docstring
        doc = m['docstring']
        title = doc.split('\n')[0].strip() if doc else m['method_name'].replace('_', ' ').title()

        tests[m['method_name']] = {
            'title': title,
            'steps': [
                {
                    'n': 1,
                    'action': '',
                    'expected': '',
                }
            ],
        }

    return {
        'test_file': f'tests/{relative}'.replace('\\', '/'),
        'class': class_name,
        'tests': tests,
    }


def process_file(file_path: Path, overwrite: bool = False, dry_run: bool = False) -> bool:
    """Process a single test file. Returns True if a stub was generated."""
    # Compute output path
    try:
        relative = file_path.relative_to(TESTS_DIR)
    except ValueError:
        print(f'  Skipping {file_path}: not under tests/ directory')
        return False

    output_path = STEPS_DIR / relative.with_suffix('.json')

    # Skip if exists (unless overwrite)
    if output_path.exists() and not overwrite:
        print(f'  Skip (exists): {output_path.relative_to(ROOT)}')
        return False

    # Extract test methods
    methods = extract_test_methods(file_path)
    if not methods:
        print(f'  Skip (no test methods): {file_path.relative_to(ROOT)}')
        return False

    # Generate stub
    stub = generate_stub(file_path, methods)

    if dry_run:
        print(f'  Would create: {output_path.relative_to(ROOT)} '
              f'({len(methods)} tests)')
        return True

    # Write the file
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(stub, f, indent=2, ensure_ascii=False)
        f.write('\n')

    print(f'  Created: {output_path.relative_to(ROOT)} ({len(methods)} tests)')
    return True


def find_test_files(paths: list[str] | None = None) -> list[Path]:
    """Find test files to process."""
    if paths:
        result = []
        for p in paths:
            path = Path(p)
            if not path.is_absolute():
                path = ROOT / path
            if path.is_file():
                result.append(path)
            elif path.is_dir():
                result.extend(sorted(path.rglob('test_*.py')))
        return result

    # Default: all test files under tests/ui/ and tests/api/
    test_dirs = [TESTS_DIR / 'ui', TESTS_DIR / 'api']
    result = []
    for d in test_dirs:
        if d.exists():
            result.extend(sorted(d.rglob('test_*.py')))
    return result


def main():
    parser = argparse.ArgumentParser(
        description='Generate step definition stub JSON files from test source files.')
    parser.add_argument('files', nargs='*', help='Specific test files or directories')
    parser.add_argument('--overwrite', action='store_true',
                        help='Overwrite existing step files')
    parser.add_argument('--dry-run', action='store_true',
                        help='Show what would be generated without writing files')
    parser.add_argument('--summary', action='store_true',
                        help='Print coverage summary after generation')
    args = parser.parse_args()

    test_files = find_test_files(args.files or None)
    if not test_files:
        print('No test files found.')
        sys.exit(1)

    print(f'Processing {len(test_files)} test files...')
    created = 0
    for tf in test_files:
        if process_file(tf, overwrite=args.overwrite, dry_run=args.dry_run):
            created += 1

    print(f'\nDone: {created} step files {"would be " if args.dry_run else ""}generated.')

    if args.summary or not args.dry_run:
        # Print coverage summary
        from tests.steps.step_registry import get_step_coverage
        coverage = get_step_coverage()
        print(f'\nStep Coverage:')
        print(f'  Files:            {coverage["total_files"]}')
        print(f'  Total tests:      {coverage["total_tests"]}')
        print(f'  With steps:       {coverage["tests_with_steps"]}')
        print(f'  Need steps:       {coverage["tests_without_steps"]}')


if __name__ == '__main__':
    main()
