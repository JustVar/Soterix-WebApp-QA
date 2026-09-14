#!/usr/bin/env python3
"""
Regenerate QA Touch Import CSV with newline-separated steps.

The original CSV used pipe (|) as step separator, but QA Touch
misinterpreted this during import. This script regenerates the CSV
with newline (\n) separated steps instead.
"""

import csv
import json
from pathlib import Path


def load_full_steps_data(json_path):
    """Load testcases_export.json with full steps."""
    with open(json_path, encoding='utf-8') as f:
        data = json.load(f)

    test_cases = data.get('test_cases', [])

    # Build lookup by title
    lookup = {}
    for tc in test_cases:
        title = tc.get('title', '').strip()
        if title:
            # Handle steps as array
            steps = tc.get('steps', [])
            step_texts = []
            for i, s in enumerate(steps, 1):
                if isinstance(s, dict):
                    step_texts.append(f"{i}. {s.get('action', str(s))}")
                else:
                    # Already numbered in source
                    step_texts.append(str(s))

            lookup[title.lower()] = {
                'title': title,
                'folder': tc.get('folder', ''),
                'subFolder': tc.get('subFolder', ''),
                'preconditions': tc.get('testConditions', ''),
                'steps': '\n'.join(step_texts),  # Newline separated
                'expected_result': tc.get('acceptanceCriteria', ''),
                'tags': ', '.join(tc.get('tags', [])) if tc.get('tags') else ''
            }

    return lookup


def load_bugasura_json_files(data_dir):
    """Load all bugasura_*.json files for high-level test cases."""
    test_cases = []

    for json_file in data_dir.glob('bugasura_*.json'):
        with open(json_file, encoding='utf-8') as f:
            data = json.load(f)

        folder = data.get('folder', '')
        for tc in data.get('test_cases', []):
            test_cases.append({
                'id': tc.get('id', ''),
                'title': tc.get('title', ''),
                'folder': folder,
                'subfolder': tc.get('subfolder', ''),
                'priority': tc.get('priority', '')
            })

    return test_cases


def main():
    project_root = Path(__file__).parent
    data_dir = project_root / 'tests' / 'data'

    print("=" * 60)
    print("REGENERATING QA TOUCH IMPORT CSV")
    print("Using newline (\\n) separated steps instead of pipe (|)")
    print("=" * 60)

    # Load full steps data
    full_steps = load_full_steps_data(project_root / 'testcases_export.json')
    print(f"\nLoaded {len(full_steps)} test cases with full steps")

    # Load high-level test cases
    bugasura_tcs = load_bugasura_json_files(data_dir)
    print(f"Loaded {len(bugasura_tcs)} high-level test cases from bugasura files")

    # Module mapping
    module_map = {
        'Login': 'Core Features > Login',
        'Logout': 'Core Features > Logout',
        'Views': 'Core Features > Views',
        'Search': 'Core Features > Search',
        'Maps': 'Core Features > Maps',
        'LPR': 'Core Features > LPR',
        'Insights': 'Core Features > Insights',
        'Media': 'Core Features > Media',
        'Notifications': 'Core Features > Notifications',
        'Chats': 'Core Features > Chats',
        'Audio': 'Core Features > Audio',
        'Events': 'Core Features > Events',
        'Admin-Dashboard': 'Admin > Dashboard',
        'Admin-Sites': 'Admin > Sites',
        'Admin -Sites': 'Admin > Sites',
        'Admin-Users&Roles': 'Admin > Users & Roles',
        'Admin-Maps': 'Admin > Maps',
        'Admin-Rules': 'Admin > Rules',
        'Admin-General': 'Admin > General',
        'Admin-LPR': 'Admin > LPR',
        'Admin-Licences': 'Admin > Licences',
        'Admin-Integrations': 'Admin > Integrations',
    }

    # Build output rows
    rows = []
    seen_titles = set()

    # First add all full steps test cases
    for _title_key, tc in full_steps.items():
        title = tc['title']
        if title.lower() in seen_titles:
            continue
        seen_titles.add(title.lower())

        folder = tc['folder']
        module = module_map.get(folder, f"Core Features > {folder}")

        rows.append({
            'external_id': '',
            'module': module,
            'title': title,
            'preconditions': tc['preconditions'],
            'steps': tc['steps'],
            'expected_result': tc['expected_result'],
            'tags': tc['tags'],
            'data_quality': 'Full'
        })

    # Then add high-level test cases not already included
    for tc in bugasura_tcs:
        title = tc['title']
        if title.lower() in seen_titles:
            continue
        seen_titles.add(title.lower())

        folder = tc['folder']
        module = module_map.get(folder, f"Admin > {folder.replace('Admin-', '')}")

        rows.append({
            'external_id': tc['id'],
            'module': module,
            'title': title,
            'preconditions': '',
            'steps': '',
            'expected_result': '',
            'tags': '',
            'data_quality': 'Title Only'
        })

    # Write CSV
    output_path = data_dir / 'qa_touch_import_v2.csv'

    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=[
            'external_id', 'module', 'title', 'preconditions',
            'steps', 'expected_result', 'tags', 'data_quality'
        ])
        writer.writeheader()
        writer.writerows(rows)

    # Count stats
    full_count = sum(1 for r in rows if r['data_quality'] == 'Full')
    title_only = sum(1 for r in rows if r['data_quality'] == 'Title Only')

    print(f"\n{'=' * 60}")
    print(f"OUTPUT: {output_path}")
    print(f"{'=' * 60}")
    print(f"Total test cases:     {len(rows)}")
    print(f"With full steps:      {full_count}")
    print(f"Title only:           {title_only}")
    print("\nStep format: Newline separated (\\n)")
    print("\nReady for QA Touch import!")


if __name__ == '__main__':
    main()
