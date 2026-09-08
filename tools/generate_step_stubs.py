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

    # Rebuild title + steps FROM THE DOCSTRINGS, keeping each case_key
    python tools/generate_step_stubs.py --from-docstrings tests/ui/chats/test_chats.py

--from-docstrings is the sidecar sync (docs/TEST_REPAIRS.md item 5).
A test's docstring is its QA Touch case: the first line is the title,
the "Steps:" block holds the tester steps and each "Expected:" line
what the tester sees. This mode copies exactly that into the sidecar
and keeps the existing case_key. It never invents a step: a test with
no "Steps:" block keeps whatever entry it had and is listed as
"needs steps", because writing those lines is a human's job. A test
that left the file loses its entry (the mapping file is the canonical
key store, so nothing is lost).
"""
from __future__ import annotations

import argparse
import ast
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
# run as a script, tools/ is on sys.path and the repo root is not
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
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


def merge_from_docstrings(existing: dict | None, parsed: dict) -> tuple[dict, list[str], list[str]]:
    """Pure: the sidecar rebuilt from parsed docstrings.

    existing  the sidecar file as loaded (None when there is none)
    parsed    func_name -> ParsedDoc (qatouch_cases_from_tests.parse_docstring)

    Returns (tests, needs_steps, dropped). A parsed doc with a Steps
    block replaces the entry's title and steps and keeps its case_key;
    one without keeps the old entry untouched and is named in
    needs_steps; a name in the old file but not in parsed is dropped
    and named.
    """
    old = dict((existing or {}).get('tests') or {})
    tests: dict = {}
    needs: list[str] = []
    for name, doc in parsed.items():
        entry = dict(old.get(name) or {})
        if doc.ok:
            entry['title'] = doc.title
            entry['steps'] = [
                {'n': i, 'action': st.text, 'expected': st.expected}
                for i, st in enumerate(doc.steps, 1)
            ]
        else:
            needs.append(f'{name}: {doc.problem}')
            entry.setdefault('title', doc.title)
            entry.setdefault('steps', [])
        entry.setdefault('case_key', '')
        tests[name] = {'title': entry['title'], 'steps': entry['steps'],
                       'case_key': entry['case_key']}
    dropped = [n for n in old if n not in parsed]
    return tests, needs, dropped


def process_from_docstrings(file_path: Path, dry_run: bool = False) -> bool:
    """Rebuild one sidecar from its test file's docstrings."""
    from tools.qatouch_cases_from_tests import parse_docstring, scan_file
    relative = file_path.relative_to(TESTS_DIR)
    output_path = STEPS_DIR / relative.with_suffix('.json')
    infos = scan_file(file_path, ROOT)
    if not infos:
        print(f'  Skip (no tests): {relative}')
        return False
    parsed = {info.func_name: parse_docstring(info.docstring, nodeid)
              for nodeid, info in infos.items()}
    existing = None
    if output_path.exists():
        with open(output_path, encoding='utf-8') as f:
            existing = json.load(f)
    tests, needs, dropped = merge_from_docstrings(existing, parsed)
    first = next(iter(infos.values()))
    stub = {
        'test_file': (existing or {}).get('test_file') or file_path.relative_to(ROOT).as_posix(),
        'class': (existing or {}).get('class') or first.class_name,
        'tests': tests,
    }
    rebuilt = len(tests) - len(needs)
    verb = 'Would rebuild' if dry_run else 'Rebuilt'
    print(f'  {verb}: {output_path.relative_to(ROOT)} '
          f'({rebuilt} from docstrings, {len(needs)} kept as-is, {len(dropped)} dropped)')
    for line in needs:
        print(f'    needs steps  {line}')
    for name in dropped:
        print(f'    dropped      {name} (not in the test file any more)')
    if dry_run:
        return True
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(stub, f, indent=2, ensure_ascii=False)
        f.write('\n')
    return True


def main():
    parser = argparse.ArgumentParser(
        description='Generate step definition stub JSON files from test source files.')
    parser.add_argument('files', nargs='*', help='Specific test files or directories')
    parser.add_argument('--overwrite', action='store_true',
                        help='Overwrite existing step files')
    parser.add_argument('--from-docstrings', action='store_true',
                        help='rebuild title and steps from the test docstrings, '
                             'keeping each case_key (the sidecar sync)')
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
        if args.from_docstrings:
            ok = process_from_docstrings(tf, dry_run=args.dry_run)
        else:
            ok = process_file(tf, overwrite=args.overwrite, dry_run=args.dry_run)
        if ok:
            created += 1

    print(f'\nDone: {created} step files {"would be " if args.dry_run else ""}generated.')

    if args.summary or not args.dry_run:
        # Print coverage summary
        from tests.steps.step_registry import get_step_coverage
        coverage = get_step_coverage()
        print('\nStep Coverage:')
        print(f'  Files:            {coverage["total_files"]}')
        print(f'  Total tests:      {coverage["total_tests"]}')
        print(f'  With steps:       {coverage["tests_with_steps"]}')
        print(f'  Need steps:       {coverage["tests_without_steps"]}')


if __name__ == '__main__':
    main()
