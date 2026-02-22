"""QA Touch Test Run Manager.

Helps manage test runs and releases for the Playwright result upload pipeline.

Capabilities:
  1. List existing test runs and available users
  2. Create test runs via API (specific cases, by tag, by module, clone, or all)
  3. Create releases/milestones
  4. Create full release suites (milestone + smoke/sanity/regression runs)
  5. Upload results from a pytest JSON report
  6. Scaffold new test cases (create in QA Touch + add to mapping)

Usage:
  python tools/qatouch_run_manager.py list                              # list all test runs
  python tools/qatouch_run_manager.py users                             # list assignable users
  python tools/qatouch_run_manager.py modules                           # list all modules
  python tools/qatouch_run_manager.py create <NAME> <USER_KEY> <MILESTONE_KEY> [CASE_KEY...]
  python tools/qatouch_run_manager.py create-by-tag <NAME> <USER_KEY> <MILESTONE_KEY> <TAG>
  python tools/qatouch_run_manager.py clone <SOURCE_RUN_KEY> <NEW_NAME>
  python tools/qatouch_run_manager.py milestone <NAME>                  # create release/milestone
  python tools/qatouch_run_manager.py release <VERSION> <ENV> <USER_KEY> [--milestone-key KEY]
  python tools/qatouch_run_manager.py upload <RUN_KEY> <REPORT.json>    # upload results
  python tools/qatouch_run_manager.py dry-run <REPORT.json>             # preview upload
  python tools/qatouch_run_manager.py scaffold <NODEID> <MODULE> <TITLE>  # create case + map
  python tools/qatouch_run_manager.py scaffold-new [--dry-run]            # auto-scaffold unmapped
"""
from __future__ import annotations

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / '.env')

from tools.qatouch_client import QATouchClient, PYTEST_TO_QATOUCH

PROJECT_KEY = os.environ.get('QATOUCH_PROJECT_ID', 'JlW1')
MAPPING_PATH = ROOT / 'config' / 'qatouch_case_mapping.json'

# Release suite definitions - which tags to use for each run type
RELEASE_SUITES = {
    'smoke': {
        'tag': 'smoke',
        'description': 'Quick health check (~60 cases)',
    },
    'sanity': {
        'tag': 'sanity',
        'description': 'Happy-path coverage (~200 cases)',
    },
    'regression': {
        'description': 'Full regression (all cases)',
    },
}


def load_case_mapping() -> dict[str, str]:
    """Load nodeid -> case_key mapping."""
    if not MAPPING_PATH.exists():
        print(f'ERROR: Mapping file not found: {MAPPING_PATH}')
        print('Run: python tools/qatouch_mapper.py build')
        sys.exit(1)

    with open(MAPPING_PATH) as f:
        data = json.load(f)

    return {nodeid: info['case_key'] for nodeid, info in data.get('mappings', {}).items()}


def cmd_list():
    """List all test runs for the project."""
    client = QATouchClient()
    runs = client.list_test_runs(PROJECT_KEY)

    if not runs:
        print(f'No test runs found for project {PROJECT_KEY}.')
        print()
        print('Create one:')
        print(f'  python tools/qatouch_run_manager.py create "Run Name" <USER_KEY> <MILESTONE_KEY>')
        return

    print(f'Test runs for project {PROJECT_KEY}:')
    for run in runs:
        run_key = run.get('testrun_key', '?')
        name = run.get('Name', '?')
        status = run.get('Status', '?')
        assigned = run.get('Assigned_To', '?')
        release = run.get('Release Name', '')
        run_type = run.get('Type', '')
        print(f'  [{run_key}] {name}')
        print(f'           Status: {status} | Assigned: {assigned} | Release: {release} | Type: {run_type}')


def cmd_users():
    """List users available for test run assignment."""
    client = QATouchClient()
    users = client.list_available_users(PROJECT_KEY)

    if not users:
        print(f'No users found for project {PROJECT_KEY}.')
        return

    print(f'Available users for project {PROJECT_KEY}:')
    for user in users:
        print(f'  [{user["user_key"]}] {user["name"]} ({user["email"]})')


def cmd_create(name: str, user_key: str, milestone_key: str, *case_keys: str):
    """Create a test run with specific cases (or all if no case keys given)."""
    client = QATouchClient()

    if case_keys:
        print(f'Creating test run "{name}" with {len(case_keys)} specific cases...')
        result = client.create_test_run(
            project_key=PROJECT_KEY,
            name=name,
            assign_to=user_key,
            milestone_key=milestone_key,
            case_ids=list(case_keys),
        )
    else:
        print(f'Creating test run "{name}" with ALL cases (this may take a while)...')
        result = client.create_test_run_all(
            project_key=PROJECT_KEY,
            name=name,
            assign_to=user_key,
            milestone_key=milestone_key,
        )

    _print_run_result(result)


def cmd_create_by_tag(name: str, user_key: str, milestone_key: str, tag: str):
    """Create a test run with all cases matching a tag."""
    client = QATouchClient()
    print(f'Creating test run "{name}" with tag "{tag}"...')

    result = client.create_test_run_by_tag(
        project_key=PROJECT_KEY,
        name=name,
        assign_to=user_key,
        milestone_key=milestone_key,
        tag=tag,
    )

    _print_run_result(result)


def cmd_clone(source_key: str, new_name: str):
    """Clone an existing test run."""
    client = QATouchClient()
    print(f'Cloning run [{source_key}] as "{new_name}"...')

    result = client.clone_test_run(
        project_key=PROJECT_KEY,
        source_run_key=source_key,
        new_name=new_name,
    )

    msg = result.get('msg', '')
    print(f'Done! {msg}')


def cmd_milestone(name: str):
    """Create a new release/milestone."""
    client = QATouchClient()
    print(f'Creating milestone "{name}"...')

    result = client.create_milestone(
        project_key=PROJECT_KEY,
        name=name,
    )

    data = result.get('data', [])
    if data and isinstance(data, list):
        milestone_id = data[0].get('milestone_id', '?')
        print(f'Created! Milestone key: {milestone_id}')
        print(f'  Use in release: python tools/qatouch_run_manager.py release v1.x.0 Stage d6JZ --milestone-key {milestone_id}')
    else:
        print(f'Created! Response: {result}')


def cmd_release(version: str, env: str, user_key: str, milestone_key: str = None):
    """Create a full release suite: milestone (optional) + smoke/sanity/regression runs.

    This is the main release automation command. It:
      1. Creates a milestone (if no --milestone-key provided)
      2. Creates a Smoke run (by tag)
      3. Creates a Sanity run (by tag)
      4. Creates a Regression run (all cases)

    All runs are linked to the milestone and assigned to the specified user.
    """
    client = QATouchClient()
    today = datetime.now(timezone.utc).strftime('%Y-%m-%d')
    release_name = f'{version} - {env}'

    print(f'=== Release Suite: {release_name} ===')
    print()

    # Step 1: Create or use existing milestone
    if milestone_key:
        print(f'Using existing milestone: {milestone_key}')
    else:
        print(f'Creating milestone "{release_name}"...')
        result = client.create_milestone(
            project_key=PROJECT_KEY,
            name=release_name,
        )
        data = result.get('data', [])
        if data and isinstance(data, list):
            milestone_key = data[0].get('milestone_id')
            print(f'  Milestone created: {milestone_key}')
        else:
            print(f'  WARNING: Could not extract milestone key from: {result}')
            print(f'  Continuing with response...')
            milestone_key = None

    if not milestone_key:
        print('ERROR: No milestone key available. Cannot create runs.')
        sys.exit(1)

    print()
    created_runs = {}

    # Step 2: Create Smoke run (by tag)
    smoke_name = f'Smoke - {env} - {version} - {today}'
    print(f'Creating Smoke run: "{smoke_name}" (tag: smoke)...')
    try:
        result = client.create_test_run_by_tag(
            project_key=PROJECT_KEY,
            name=smoke_name,
            assign_to=user_key,
            milestone_key=milestone_key,
            tag='smoke',
        )
        run_key = _extract_run_key(result)
        created_runs['smoke'] = run_key
        print(f'  Smoke run created: {run_key}')
    except Exception as e:
        print(f'  WARNING: Smoke run failed: {e}')
        print(f'  (Are cases tagged with "smoke" in QA Touch?)')

    # Step 3: Create Sanity run (by tag)
    sanity_name = f'Sanity - {env} - {version} - {today}'
    print(f'Creating Sanity run: "{sanity_name}" (tag: sanity)...')
    try:
        result = client.create_test_run_by_tag(
            project_key=PROJECT_KEY,
            name=sanity_name,
            assign_to=user_key,
            milestone_key=milestone_key,
            tag='sanity',
        )
        run_key = _extract_run_key(result)
        created_runs['sanity'] = run_key
        print(f'  Sanity run created: {run_key}')
    except Exception as e:
        print(f'  WARNING: Sanity run failed: {e}')
        print(f'  (Are cases tagged with "sanity" in QA Touch?)')

    # Step 4: Create Regression run (all cases)
    regression_name = f'Regression - {env} - {version} - {today}'
    print(f'Creating Regression run: "{regression_name}" (all cases, this may take a while)...')
    try:
        result = client.create_test_run_all(
            project_key=PROJECT_KEY,
            name=regression_name,
            assign_to=user_key,
            milestone_key=milestone_key,
        )
        run_key = _extract_run_key(result)
        created_runs['regression'] = run_key
        print(f'  Regression run created: {run_key}')
    except Exception as e:
        print(f'  WARNING: Regression run failed: {e}')

    # Summary
    print()
    print(f'=== Release Suite Summary ===')
    print(f'  Release:    {release_name}')
    print(f'  Milestone:  {milestone_key}')
    print(f'  Assigned:   {user_key}')
    print()
    for suite, run_key in created_runs.items():
        print(f'  {suite.upper():12s} run: {run_key}')
    print()

    if created_runs:
        print('Upload results with:')
        for suite, run_key in created_runs.items():
            print(f'  pytest --qatouch-upload --qatouch-run {run_key}  # {suite}')
    else:
        print('No runs were created. Check errors above.')
        sys.exit(1)


def _extract_run_key(result: dict) -> str:
    """Extract the run key from an API creation response."""
    data = result.get('data', [])
    if data and isinstance(data, list):
        return data[0].get('testrun_id', '?')
    # Clone responses have it in msg
    msg = result.get('msg', '')
    if 'Key -' in msg:
        return msg.split('Key -')[-1].strip()
    return '?'


def _print_run_result(result: dict):
    """Print the result of a test run creation."""
    run_key = _extract_run_key(result)
    if run_key != '?':
        print(f'Created! Run key: {run_key}')
        print(f'  Upload results: pytest --qatouch-upload --qatouch-run {run_key}')
    else:
        print(f'Created! Response: {result}')


def load_pytest_report(report_path: str) -> list[dict]:
    """Load results from a pytest JSON report.

    Supports the format produced by pytest-json-report plugin:
      pytest --json-report --json-report-file=report.json
    """
    with open(report_path) as f:
        data = json.load(f)

    results = []
    for test in data.get('tests', []):
        nodeid = test.get('nodeid', '')
        outcome = test.get('outcome', '')
        results.append({'nodeid': nodeid, 'outcome': outcome})

    return results


def map_results(report_results: list[dict], mapping: dict[str, str]) -> list[dict]:
    """Map pytest results to QA Touch case keys and status codes."""
    qt_results = []
    unmapped = []

    for result in report_results:
        nodeid = result['nodeid']
        outcome = result['outcome']

        # Try exact match, then without parameters
        case_key = mapping.get(nodeid)
        if not case_key and '[' in nodeid:
            base = nodeid.split('[')[0]
            case_key = mapping.get(base)

        if not case_key:
            unmapped.append(nodeid)
            continue

        status = PYTEST_TO_QATOUCH.get(outcome)
        if status is not None:
            qt_results.append({
                'case': case_key,
                'status': status,
                'nodeid': nodeid,
                'outcome': outcome,
            })

    return qt_results, unmapped


def cmd_upload(run_key: str, report_path: str):
    """Upload results from a pytest JSON report to a QA Touch test run."""
    mapping = load_case_mapping()
    report_results = load_pytest_report(report_path)
    print(f'Loaded {len(report_results)} test results from {report_path}')

    qt_results, unmapped = map_results(report_results, mapping)
    print(f'Mapped: {len(qt_results)} results')
    print(f'Unmapped: {len(unmapped)} tests')

    if not qt_results:
        print('No results to upload.')
        return

    # Build payload (dedupe by case key, keep worst status)
    by_case: dict[str, int] = {}
    for r in qt_results:
        existing = by_case.get(r['case'])
        if existing is not None:
            by_case[r['case']] = max(existing, r['status'])
        else:
            by_case[r['case']] = r['status']

    payload = [{'case': k, 'status': v} for k, v in by_case.items()]

    # Upload
    client = QATouchClient()
    timestamp = datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')
    comment = f'Uploaded from pytest report at {timestamp}'

    print(f'\nUploading {len(payload)} results to run {run_key}...')
    try:
        response = client.update_test_run_results(
            project_key=PROJECT_KEY,
            test_run_key=run_key,
            results=payload,
            comment=comment,
        )
        print(f'Upload successful!')
        passed = sum(1 for r in payload if r['status'] == 1)
        failed = sum(1 for r in payload if r['status'] == 5)
        blocked = sum(1 for r in payload if r['status'] == 3)
        print(f'  Passed: {passed}, Failed: {failed}, Blocked: {blocked}')
    except Exception as e:
        print(f'Upload failed: {e}')
        sys.exit(1)


def cmd_dry_run(report_path: str):
    """Preview what would be uploaded without actually uploading."""
    mapping = load_case_mapping()
    report_results = load_pytest_report(report_path)
    print(f'Loaded {len(report_results)} test results from {report_path}')

    qt_results, unmapped = map_results(report_results, mapping)

    print(f'\n=== Dry Run Preview ===')
    print(f'Would upload {len(qt_results)} results:')
    for r in sorted(qt_results, key=lambda x: x['case']):
        status_name = {1: 'PASSED', 3: 'BLOCKED', 5: 'FAILED'}.get(r['status'], '?')
        print(f'  {r["case"]}: {status_name}  ({r["nodeid"]})')

    if unmapped:
        print(f'\nUnmapped ({len(unmapped)} tests - no QA Touch case):')
        for nodeid in sorted(unmapped)[:20]:
            print(f'  {nodeid}')
        if len(unmapped) > 20:
            print(f'  ... and {len(unmapped) - 20} more')


def cmd_modules():
    """List all modules in the project with their section keys."""
    client = QATouchClient()
    modules = client.list_all_modules(PROJECT_KEY)

    if not modules:
        print(f'No modules found for project {PROJECT_KEY}.')
        return

    print(f'Modules for project {PROJECT_KEY} ({len(modules)} total):')
    for mod in sorted(modules, key=lambda m: m.get('section_name', '')):
        key = mod.get('section_key', '?')
        name = mod.get('section_name', '?')
        print(f'  [{key}] {name}')


def cmd_scaffold(nodeid: str, module_name: str, title: str,
                 description: str = '', precondition: str = ''):
    """Create a test case in QA Touch and add it to the Playwright mapping.

    This is the main automation backfill command. It:
      1. Resolves module name to section_key
      2. Creates the test case via API
      3. Finds the case_key by title match
      4. Adds the mapping to qatouch_case_mapping.json

    After running, set Mode=Automation and Tags in QA Touch UI.
    """
    client = QATouchClient()

    # Step 1: Resolve module name to section_key
    print(f'Resolving module "{module_name}"...')
    modules = client.list_all_modules(PROJECT_KEY)
    section_key = None
    for mod in modules:
        if mod.get('section_name', '').lower() == module_name.lower():
            section_key = mod.get('section_key')
            break

    if not section_key:
        # Try partial match
        candidates = [m for m in modules
                      if module_name.lower() in m.get('section_name', '').lower()]
        if len(candidates) == 1:
            section_key = candidates[0]['section_key']
            module_name = candidates[0]['section_name']
            print(f'  Partial match: "{module_name}" [{section_key}]')
        elif candidates:
            print(f'  AMBIGUOUS: "{module_name}" matches {len(candidates)} modules:')
            for c in candidates:
                print(f'    [{c["section_key"]}] {c["section_name"]}')
            print('  Use the exact disambiguated name (e.g. "Search - Insights").')
            sys.exit(1)
        else:
            print(f'  Module "{module_name}" not found. Use "modules" command to list all.')
            sys.exit(1)
    else:
        # Check for duplicate names - warn if other modules share this name
        dupes = [m for m in modules
                 if m.get('section_name', '').lower() == module_name.lower()
                 and m.get('section_key') != section_key]
        if dupes:
            print(f'  WARNING: "{module_name}" has {len(dupes) + 1} modules with '
                  f'the same name! Consider renaming to avoid confusion.')
            print(f'  Target: [{section_key}] {module_name}')
            for d in dupes:
                print(f'  Duplicate: [{d["section_key"]}] {d["section_name"]}')
        else:
            print(f'  Found: [{section_key}] {module_name}')

    # Step 2: Check if case already exists (avoid duplicates)
    print(f'Checking for existing case with same title...')
    existing = client.find_case_by_title(PROJECT_KEY, title, section_key=section_key)
    if existing:
        case_key = existing['case_key']
        print(f'  Case already exists: [{case_key}] "{title[:60]}"')
        print(f'  Skipping creation, adding mapping only.')
    else:
        # Step 3: Create the case
        print(f'Creating test case in QA Touch...')
        result = client.create_test_case(
            project_key=PROJECT_KEY,
            section_key=section_key,
            title=title,
            description=description,
            precondition=precondition,
        )
        print(f'  Created! Finding case_key...')

        # Step 4: Find the case_key
        case = client.find_case_by_title(PROJECT_KEY, title, section_key=section_key)
        if not case:
            print(f'  WARNING: Could not find case_key for "{title[:60]}"')
            print(f'  Case was created but mapping was NOT added.')
            print(f'  Run "modules" and check QA Touch UI, then add mapping manually.')
            sys.exit(1)

        case_key = case['case_key']
        print(f'  Found: [{case_key}]')

    # Step 5: Add to mapping
    print(f'Adding to mapping...')
    with open(MAPPING_PATH) as f:
        mapping_data = json.load(f)

    if nodeid in mapping_data.get('mappings', {}):
        old_key = mapping_data['mappings'][nodeid]['case_key']
        print(f'  WARNING: {nodeid} already mapped to [{old_key}]. Overwriting.')

    mapping_data['mappings'][nodeid] = {
        'case_key': case_key,
        'case_title': title,
        'score': 1.0,
        'module': module_name,
        'auto_matched': False,
    }
    mapping_data['total_mapped'] = len(mapping_data['mappings'])

    with open(MAPPING_PATH, 'w') as f:
        json.dump(mapping_data, f, indent=2)
        f.write('\n')

    print(f'  Mapping added: {nodeid} -> [{case_key}]')
    print()
    print(f'Done! Next steps (QA Touch UI):')
    print(f'  1. Set Mode = Automation')
    print(f'  2. Add tags (SMOKE, SANITY, etc.) as appropriate')
    print(f'  3. Set correct Priority if needed (defaults to Critical)')


# Module resolution: test directory path -> best QA Touch module name
# IMPORTANT: Use disambiguated names (not bare "Search", "Media", etc.)
# to avoid creating duplicate modules. Check QA Touch UI if unsure.
_DIR_TO_MODULE = {
    'login': 'Login UI',
    'views': 'Views',
    'events': 'Events',
    'search': 'Search',  # Will warn if ambiguous - specify manually
    'insights': 'Insights',
    'media': 'Media',  # Will warn if ambiguous - specify manually
    'admin': 'Admin',
    'notifications': 'Notifications',
    'sequences': 'Camera Sequence - Fullscreen',
    'maps': 'Maps',
    'chats': 'Chat',
}


def _guess_module(nodeid: str) -> str:
    """Guess QA Touch module from test node ID directory."""
    parts = nodeid.split('/')
    if len(parts) >= 3 and parts[1] in ('ui', 'api'):
        d = parts[2]
    elif len(parts) >= 2:
        d = parts[1]
    else:
        d = 'other'
    return _DIR_TO_MODULE.get(d, d.replace('_', ' ').title())


def _title_from_nodeid(nodeid: str) -> str:
    """Generate a human-readable title from a test node ID."""
    # Extract function name: last :: segment, strip [params]
    func = nodeid.split('::')[-1].split('[')[0]
    words = func.replace('test_', '').replace('_', ' ')
    return f'Verify {words}'


def cmd_scaffold_new(dry_run: bool = False, delay: float = 2.0):
    """Find all unmapped Playwright tests and scaffold them in batch.

    Runs pytest --collect-only to discover tests, compares against the mapping,
    and scaffolds each unmapped test with auto-resolved module and title.

    Args:
        dry_run: If True, only print what would be scaffolded (no API calls).
        delay: Seconds to wait between API calls to avoid rate limiting.
    """
    import subprocess
    import time
    import re

    # Step 1: Collect all tests
    print('Collecting Playwright tests...')
    result = subprocess.run(
        [sys.executable, '-m', 'pytest', '--collect-only'],
        capture_output=True, text=True, cwd=str(ROOT),
    )
    actual_tests = []
    for line in result.stdout.strip().split('\n'):
        line = line.strip()
        if '::' in line and line.startswith('tests/'):
            actual_tests.append(line)
    print(f'  Found {len(actual_tests)} tests')

    # Step 2: Load mapping
    with open(MAPPING_PATH) as f:
        mapping_data = json.load(f)
    mapped = set(mapping_data.get('mappings', {}).keys())
    print(f'  Mapping has {len(mapped)} entries')

    # Step 3: Find unmapped (exclude API smoke infra tests)
    unmapped = [t for t in actual_tests
                if t not in mapped and '/api/smoke/' not in t]

    if not unmapped:
        print('\n  All tests are already mapped!')
        return

    print(f'\n  {len(unmapped)} unmapped tests found:')
    for t in unmapped:
        module = _guess_module(t)
        title = _title_from_nodeid(t)
        print(f'    [{module}] {t}')
        print(f'      Title: {title}')

    if dry_run:
        print(f'\nDry run - no cases created. Remove --dry-run to scaffold.')
        return

    # Step 4: Scaffold each one
    print(f'\nScaffolding {len(unmapped)} tests (with {delay}s delay between calls)...')
    created = 0
    failed = []
    for i, nodeid in enumerate(unmapped, 1):
        module = _guess_module(nodeid)
        title = _title_from_nodeid(nodeid)
        print(f'\n[{i}/{len(unmapped)}] {nodeid}')
        try:
            cmd_scaffold(nodeid, module, title)
            created += 1
        except SystemExit:
            print(f'  FAILED - could not resolve module or create case')
            failed.append(nodeid)
        except Exception as e:
            print(f'  ERROR: {e}')
            failed.append(nodeid)

        # Rate limit protection
        if i < len(unmapped):
            time.sleep(delay)

    print(f'\n{"="*60}')
    print(f'Scaffold complete: {created} created, {len(failed)} failed')
    if failed:
        print(f'\nFailed tests (scaffold manually):')
        for t in failed:
            module = _guess_module(t)
            title = _title_from_nodeid(t)
            print(f'  python tools/qatouch_run_manager.py scaffold '
                  f'"{t}" "{module}" "{title}"')

    print(f'\nNext steps (QA Touch UI):')
    print(f'  Set Mode=Automation + Tags on all {created} new cases')


USAGE = """\
QA Touch Test Run Manager

Usage:
  python tools/qatouch_run_manager.py list
  python tools/qatouch_run_manager.py users
  python tools/qatouch_run_manager.py modules
  python tools/qatouch_run_manager.py create <NAME> <USER_KEY> <MILESTONE_KEY> [CASE_KEY...]
  python tools/qatouch_run_manager.py create-by-tag <NAME> <USER_KEY> <MILESTONE_KEY> <TAG>
  python tools/qatouch_run_manager.py clone <SOURCE_RUN_KEY> <NEW_NAME>
  python tools/qatouch_run_manager.py milestone <NAME>
  python tools/qatouch_run_manager.py release <VERSION> <ENV> <USER_KEY> [--milestone-key KEY]
  python tools/qatouch_run_manager.py upload <RUN_KEY> <REPORT.json>
  python tools/qatouch_run_manager.py dry-run <REPORT.json>
  python tools/qatouch_run_manager.py scaffold <NODEID> <MODULE> <TITLE> [--desc TEXT] [--pre TEXT]
  python tools/qatouch_run_manager.py scaffold-new [--dry-run]

Commands:
  list          List all test runs for the project
  users         List assignable users (shows user_key needed for create/release)
  modules       List all modules with section keys (needed for scaffold)
  create        Create a run with specific cases (or all if no case keys given)
  create-by-tag Create a run with all cases matching a tag (e.g. "smoke")
  clone         Clone an existing test run (all results reset to Untested)
  milestone     Create a new release/milestone in QA Touch
  release       Create a full release suite (milestone + smoke + sanity + regression)
  upload        Upload results from a pytest JSON report to a run
  dry-run       Preview what would be uploaded without uploading
  scaffold      Create a QA Touch case and add Playwright mapping in one step
  scaffold-new  Auto-scaffold ALL unmapped tests in one batch (with rate limiting)

Examples:
  # List runs, users, and modules
  python tools/qatouch_run_manager.py list
  python tools/qatouch_run_manager.py users
  python tools/qatouch_run_manager.py modules

  # Scaffold a new test case (create in QA Touch + add mapping)
  python tools/qatouch_run_manager.py scaffold \\
    "tests/ui/login/test_login.py::TestLogin::test_valid_login[chromium]" \\
    "Login UI" \\
    "Verify user can log in with valid credentials"

  # Scaffold with description and precondition
  python tools/qatouch_run_manager.py scaffold \\
    "tests/ui/dashboard/test_alerts.py::TestAlerts::test_dismiss_alert[chromium]" \\
    "Dashboard" \\
    "Verify user can dismiss alert notifications" \\
    --desc "Tests alert dismissal across all alert types" \\
    --pre "User is logged in as admin, alerts are present"

  # Create a run with specific cases
  python tools/qatouch_run_manager.py create "Smoke - Stage - v1.6.0" d6JZ Dmn7 5BRMnj 21zWnm

  # Create a run with ALL cases
  python tools/qatouch_run_manager.py create "Regression - Stage - v1.6.0" d6JZ Dmn7

  # Create a run from a tag
  python tools/qatouch_run_manager.py create-by-tag "Smoke - Stage - v1.6.0" d6JZ Dmn7 smoke

  # Clone an existing run
  python tools/qatouch_run_manager.py clone vaXdn "Smoke - Stage - v1.7.0"

  # Create a milestone
  python tools/qatouch_run_manager.py milestone "v1.7.0 - Stage"

  # Create a full release suite (creates milestone + 3 runs)
  python tools/qatouch_run_manager.py release v1.7.0 Stage d6JZ

  # Create release with existing milestone
  python tools/qatouch_run_manager.py release v1.7.0 Stage d6JZ --milestone-key Dmn7

  # Upload results
  python tools/qatouch_run_manager.py upload vaXdn report.json
"""

if __name__ == '__main__':
    if len(sys.argv) < 2 or sys.argv[1] in ('-h', '--help'):
        print(USAGE)
        sys.exit(0 if sys.argv[1:] == ['--help'] else 1)

    cmd = sys.argv[1]
    args = sys.argv[2:]

    if cmd == 'list':
        cmd_list()
    elif cmd == 'users':
        cmd_users()
    elif cmd == 'modules':
        cmd_modules()
    elif cmd == 'scaffold':
        if len(args) < 3:
            print('Error: scaffold requires at least 3 args: <NODEID> <MODULE> <TITLE> [--desc TEXT] [--pre TEXT]')
            sys.exit(1)
        nodeid = args[0]
        module_name = args[1]
        title = args[2]
        description = ''
        precondition = ''
        if '--desc' in args:
            idx = args.index('--desc')
            if idx + 1 < len(args):
                description = args[idx + 1]
        if '--pre' in args:
            idx = args.index('--pre')
            if idx + 1 < len(args):
                precondition = args[idx + 1]
        cmd_scaffold(nodeid, module_name, title,
                     description=description, precondition=precondition)
    elif cmd == 'scaffold-new':
        dry_run = '--dry-run' in args
        cmd_scaffold_new(dry_run=dry_run)
    elif cmd == 'create':
        if len(args) < 3:
            print('Error: create requires at least 3 args: <NAME> <USER_KEY> <MILESTONE_KEY> [CASE_KEY...]')
            sys.exit(1)
        cmd_create(args[0], args[1], args[2], *args[3:])
    elif cmd == 'create-by-tag':
        if len(args) < 4:
            print('Error: create-by-tag requires 4 args: <NAME> <USER_KEY> <MILESTONE_KEY> <TAG>')
            sys.exit(1)
        cmd_create_by_tag(args[0], args[1], args[2], args[3])
    elif cmd == 'clone':
        if len(args) < 2:
            print('Error: clone requires 2 args: <SOURCE_RUN_KEY> <NEW_NAME>')
            sys.exit(1)
        cmd_clone(args[0], args[1])
    elif cmd == 'milestone':
        if len(args) < 1:
            print('Error: milestone requires 1 arg: <NAME>')
            sys.exit(1)
        cmd_milestone(args[0])
    elif cmd == 'release':
        if len(args) < 3:
            print('Error: release requires at least 3 args: <VERSION> <ENV> <USER_KEY> [--milestone-key KEY]')
            sys.exit(1)
        version = args[0]
        env = args[1]
        user_key = args[2]
        milestone_key = None
        if '--milestone-key' in args:
            idx = args.index('--milestone-key')
            if idx + 1 < len(args):
                milestone_key = args[idx + 1]
            else:
                print('Error: --milestone-key requires a value')
                sys.exit(1)
        cmd_release(version, env, user_key, milestone_key=milestone_key)
    elif cmd == 'upload':
        if len(args) < 2:
            print('Error: upload requires 2 args: <RUN_KEY> <REPORT.json>')
            sys.exit(1)
        cmd_upload(args[0], args[1])
    elif cmd == 'dry-run':
        if len(args) < 1:
            print('Error: dry-run requires 1 arg: <REPORT.json>')
            sys.exit(1)
        cmd_dry_run(args[0])
    else:
        print(f'Unknown command: {cmd}')
        print(USAGE)
        sys.exit(1)