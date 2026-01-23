"""QA Touch project setup script.

Creates project, modules, sections, and custom fields needed for test mapping.
Saves discovered project id to .env as `QATOUCH_PROJECT_ID`.
"""
from __future__ import annotations

import os
import sys
import json
import time
from typing import List, Dict, Any

# Ensure repo root is on sys.path when run directly
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from tools.qatouch_client import QATouchClient, QATouchError


PROJECT_NAME = 'Soterix AI VSAAS'
PROJECT_KEY = 'VSAAS'
MODULES = [
    'Authentication', 'Views', 'Events', 'Media', 'Maps', 'Insights', 'Search', 'LPR', 'Admin', 'Partner Admin Tools'
]
SECTIONS = ['Smoke Tests', 'Sanity Tests', 'Regression Tests']
CUSTOM_FIELDS = [
    ('environment', 'select'),
    ('test_type', 'select'),
    ('automation_status', 'select'),
    ('playwright_test_path', 'text'),
    ('jira_story_link', 'text'),
    ('priority', 'select'),
]


def find_or_create_project(client: QATouchClient, name: str, code: str) -> Dict[str, Any]:
    projects = client.list_projects()
    # Attempt to find by name or code
    for p in projects:
        if str(p.get('name')) == name or str(p.get('code')) == code or str(p.get('key')) == code:
            return p
    # create
    return client.create_project(name, code, description='Automated project for Playwright tests')


def save_project_id_to_env(project_id: int, env_file: str = '.env') -> None:
    lines = []
    if os.path.exists(env_file):
        with open(env_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
    key = 'QATOUCH_PROJECT_ID'
    found = False
    for i, ln in enumerate(lines):
        if ln.strip().startswith(key + '='):
            lines[i] = f'{key}={project_id}\n'
            found = True
            break
    if not found:
        lines.append(f'{key}={project_id}\n')
    with open(env_file, 'w', encoding='utf-8') as f:
        f.writelines(lines)


def main():
    base_url = os.environ.get('QATOUCH_URL')
    api_key = os.environ.get('QATOUCH_API_KEY')
    if not base_url or not api_key:
        raise SystemExit('Please set QATOUCH_URL and QATOUCH_API_KEY in the environment')

    client = QATouchClient(base_url=base_url, api_key=api_key)

    print('Checking projects...')
    project = None
    try:
        project = find_or_create_project(client, PROJECT_NAME, PROJECT_KEY)
    except QATouchError as e:
        print('Project lookup/creation failed:', e)
        raise

    project_id = int(project.get('id') or project.get('project_id') or project.get('pk') or 0)
    if not project_id:
        print('Could not determine project id from response:', project)
        raise SystemExit(1)

    print('Using project id:', project_id)

    created_modules = []
    for mod in MODULES:
        try:
            m = client.create_module(project_id, mod)
            mid = int(m.get('id') or m.get('module_id') or 0)
            print(f'Created module {mod} -> id {mid}')
            created_modules.append({'name': mod, 'id': mid})
            # create sections under module
            for sec in SECTIONS:
                try:
                    s = client.create_module(project_id, sec, parent_id=mid)
                    sid = int(s.get('id') or s.get('module_id') or 0)
                    print(f'  Created section {sec} -> id {sid}')
                except Exception as se:
                    print(f'  Failed to create section {sec}:', se)
        except Exception as e:
            print(f'Failed to create module {mod}:', e)

    # Create custom fields (best-effort)
    created_fields = []
    for key, ftype in CUSTOM_FIELDS:
        try:
            cf = client.create_custom_field(project_id, key, field_type=ftype)
            print(f'Created custom field {key}:', cf.get('id') or cf.get('field_id') or cf)
            created_fields.append(key)
        except Exception as e:
            print(f'Failed to create custom field {key}:', e)

    # Save project id to .env
    save_project_id_to_env(project_id)

    report = {
        'project': {'name': PROJECT_NAME, 'id': project_id},
        'modules': created_modules,
        'custom_fields': created_fields,
    }

    print('\nSetup report:')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
