"""Step definition registry - loads JSON step files for tests.

Provides a unified interface for all consumers:
  - Verification plugin (per-step screenshot capture)
  - QA Touch sync (sync-steps command)
  - QA Ops Hub (evidence review display)

Step files live alongside tests, mirroring the test directory structure:
  tests/steps/ui/admin/test_admin_audit_trail.json   (Playwright tests)
  tests/steps/manual/admin/licenses.json             (generated/manual cases)
  etc.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)

# Root of the steps directory (tests/steps/)
STEPS_ROOT = Path(__file__).resolve().parent
# Manual/generated step files directory
MANUAL_ROOT = STEPS_ROOT / 'manual'


def load_steps(test_nodeid: str) -> list[dict[str, Any]] | None:
    """Load step definitions for a test by its pytest nodeid.

    Args:
        test_nodeid: Full pytest nodeid, e.g.
            'tests/ui/admin/test_admin_audit_trail.py::TestAdminAuditTrail::test_page_loads'
            May include browser suffix like '[chromium]'.

    Returns:
        List of step dicts [{n, action, expected}, ...] or None if no steps defined.
    """
    # Strip browser parameter suffix
    nodeid = test_nodeid.split('[')[0] if '[' in test_nodeid else test_nodeid

    # Parse nodeid: file_path::ClassName::method_name
    parts = nodeid.split('::')
    if len(parts) < 2:
        return None

    file_path = parts[0]  # e.g. tests/ui/admin/test_admin_audit_trail.py
    method_name = parts[-1]  # e.g. test_page_loads
    class_name = parts[1] if len(parts) == 3 else None

    # Map test file path to step JSON path
    # tests/ui/admin/test_admin_audit_trail.py -> tests/steps/ui/admin/test_admin_audit_trail.json
    if file_path.startswith('tests/'):
        relative = file_path[len('tests/'):]
    else:
        relative = file_path

    json_path = STEPS_ROOT / relative.replace('.py', '.json')

    if not json_path.exists():
        return None

    try:
        with open(json_path, encoding='utf-8') as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        log.warning('Failed to load step file %s: %s', json_path, e)
        return None

    # Look up the test method's steps
    tests = data.get('tests', {})
    test_data = tests.get(method_name)
    if test_data is None:
        return None

    steps = test_data.get('steps', [])
    return steps if steps else None


def load_steps_by_case_key(case_key: str) -> list[dict[str, Any]] | None:
    """Load step definitions for a test case by its QA Touch case key.

    Searches manual/generated step files where tests are keyed by case_key.

    Args:
        case_key: QA Touch case key, e.g. 'kpZW3B'.

    Returns:
        List of step dicts [{n, action, expected}, ...] or None if not found.
    """
    if not MANUAL_ROOT.exists():
        return None

    for json_path in MANUAL_ROOT.rglob('*.json'):
        if json_path.name == 'generated_metadata.json':
            continue
        try:
            with open(json_path, encoding='utf-8') as f:
                data = json.load(f)
        # one unreadable sidecar must not hide the others; the scan
        # continues and returns none when no file has the key
        except (json.JSONDecodeError, OSError):
            continue

        tests = data.get('tests', {})
        if case_key in tests:
            steps = tests[case_key].get('steps', [])
            return steps if steps else None

    return None


def load_step_file(json_path: Path) -> dict[str, Any] | None:
    """Load and return the full step definition file contents."""
    if not json_path.exists():
        return None
    try:
        with open(json_path, encoding='utf-8') as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError) as e:
        log.warning('Failed to load step file %s: %s', json_path, e)
        return None


def get_all_step_files(include_manual: bool = True) -> list[Path]:
    """List all step definition JSON files.

    Args:
        include_manual: If True, also include manual/generated step files.
    """
    files = sorted(
        f for f in STEPS_ROOT.rglob('*.json')
        if not f.is_relative_to(MANUAL_ROOT) and f.name != 'generated_metadata.json'
    )
    if include_manual and MANUAL_ROOT.exists():
        manual_files = sorted(
            f for f in MANUAL_ROOT.rglob('*.json')
            if f.name != 'generated_metadata.json'
        )
        files.extend(manual_files)
    return files


def get_step_coverage(include_manual: bool = True) -> dict[str, Any]:
    """Return a summary of step definition coverage.

    Args:
        include_manual: If True, also include manual/generated step files.

    Returns:
        Dict with total_files, total_tests, tests_with_steps, tests_without_steps,
        and separate counts for playwright vs manual.
    """
    files = get_all_step_files(include_manual=include_manual)
    total_tests = 0
    tests_with_steps = 0
    tests_without_steps = 0
    playwright_tests = 0
    manual_tests = 0

    for fp in files:
        data = load_step_file(fp)
        if not data:
            continue
        is_manual = fp.is_relative_to(MANUAL_ROOT) if MANUAL_ROOT.exists() else False
        tests = data.get('tests', {})
        for method_name, test_data in tests.items():
            total_tests += 1
            if is_manual:
                manual_tests += 1
            else:
                playwright_tests += 1
            steps = test_data.get('steps', [])
            if steps and any(s.get('action') for s in steps):
                tests_with_steps += 1
            else:
                tests_without_steps += 1

    return {
        'total_files': len(files),
        'total_tests': total_tests,
        'tests_with_steps': tests_with_steps,
        'tests_without_steps': tests_without_steps,
        'playwright_tests': playwright_tests,
        'manual_tests': manual_tests,
    }
