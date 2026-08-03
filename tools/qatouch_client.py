"""QA Touch API client wrapper.

Endpoints (verified 2026-02-18):
  Read:
    GET  /api/v1/getAllProjects
    GET  /api/v1/getAllTestCases/{project_key}?page=N       (50/page)
    GET  /api/v1/getAllModules/{project_key}?page=N         (20/page)
    GET  /api/v1/getAllTestRuns/{project_key}                (20/page)
    GET  /api/v1/testRunResults/{project_key}/{run_key}     (100/page)
    GET  /api/v1/testRun/availableUsers/{project_key}
    GET  /api/v1/getAllRequirements/{project_key}
  Write - Test Runs:
    POST /api/v1/testRun                                    (all cases)
    POST /api/v1/testRun/specific                           (specific case IDs)
    POST /api/v1/testRun/specific/module/mode               (by module, optional mode filter)
    POST /api/v1/clone/testRun                              (clone existing run)
  Write - Entities:
    POST /api/v1/projects
    POST /api/v1/modules
    POST /api/v1/testCase                                (create case - verified 02/19)
    POST /api/v1/milestone                               (create release/milestone)
  Results:
    PATCH /api/v1/testRunResults/status/multiple
  Not Available via API:
    - Delete test cases or runs (UI only)
    - Update case title, type, mode, or tags (UI only)
    - List releases/milestones (creation works, but list endpoint returns empty)
  API Limitations on Case Creation:
    - Only reliably sets: projectKey, sectionKey, caseTitle, description, precondition
    - Type, Priority, Mode, Tags are IGNORED (default to Acceptance/Critical)
    - Response does NOT return case_key (must fetch from list to find it)
    - Set Mode=Automation and Tags via QA Touch UI after creation

Auth: headers api-token + domain.  Base URL: https://api.qatouch.com
Rate limit: 50 requests/minute (HTTP 429 on excess).
"""
from __future__ import annotations

import json as _json
import os
import sys

# Ensure repo root is on sys.path when run as a script
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from typing import Any

import requests

# QA Touch status codes for test run results
STATUS_PASSED = 1
STATUS_UNTESTED = 2
STATUS_BLOCKED = 3   # also used for skipped
STATUS_RETEST = 4
STATUS_FAILED = 5

PYTEST_TO_QATOUCH = {
    'passed': STATUS_PASSED,
    'failed': STATUS_FAILED,
    'skipped': STATUS_BLOCKED,
}


class QATouchError(Exception):
    pass


class QATouchClient:
    # QA Touch API requires: base URL = https://api.qatouch.com
    # Headers: api-token (API key) + domain (subdomain, e.g. 'soterixsystems')
    API_BASE = 'https://api.qatouch.com'

    def __init__(self, api_key: str | None = None, domain: str | None = None,
                 base_url: str | None = None, timeout: int = 30):
        self.api_key = api_key or os.environ.get('QATOUCH_API_KEY')
        self.domain = domain or os.environ.get('QATOUCH_DOMAIN')
        # Legacy: accept base_url for backward compatibility but prefer API_BASE
        self.base_url = base_url or self.API_BASE
        if not self.api_key:
            raise QATouchError('QATOUCH_API_KEY must be provided (env or arg)')
        if not self.domain:
            raise QATouchError('QATOUCH_DOMAIN must be provided (env or arg, e.g. "soterixsystems")')
        self.timeout = timeout
        self.session = requests.Session()
        self.session.headers.update({
            'Content-Type': 'application/json',
            'api-token': self.api_key,
            'domain': self.domain,
        })

    def _url(self, path: str) -> str:
        return self.base_url.rstrip('/') + path

    # ------------------------------------------------------------------ #
    #  Projects
    # ------------------------------------------------------------------ #

    def list_projects(self) -> list[dict[str, Any]]:
        url = self._url('/api/v1/getAllProjects')
        resp = self.session.get(url, timeout=self.timeout)
        if resp.status_code != 200:
            raise QATouchError(f'list_projects failed: {resp.status_code} {resp.text}')
        return resp.json()

    def create_project(self, name: str, code: str, description: str = '') -> dict[str, Any]:
        url = self._url('/api/v1/projects')
        payload = {'name': name, 'code': code, 'description': description}
        resp = self.session.post(url, json=payload, timeout=self.timeout)
        if resp.status_code not in (200, 201):
            raise QATouchError(f'create_project failed: {resp.status_code} {resp.text}')
        return resp.json()

    # ------------------------------------------------------------------ #
    #  Modules
    # ------------------------------------------------------------------ #

    def create_module(self, project_id: int, name: str, parent_id: int | None = None) -> dict[str, Any]:
        url = self._url('/api/v1/modules')
        payload = {'project_id': project_id, 'name': name}
        if parent_id:
            payload['parent_id'] = parent_id
        resp = self.session.post(url, json=payload, timeout=self.timeout)
        if resp.status_code not in (200, 201):
            raise QATouchError(f'create_module failed: {resp.status_code} {resp.text}')
        return resp.json()

    def list_modules(self, project_key: str, page: int = 1) -> dict[str, Any]:
        """Return one page (20 items) of modules.

        Each module has: section_name, section_key.
        """
        url = self._url(f'/api/v1/getAllModules/{project_key}?page={page}')
        resp = self.session.get(url, timeout=self.timeout)
        if resp.status_code != 200:
            raise QATouchError(f'list_modules failed: {resp.status_code} {resp.text}')
        return resp.json()

    def list_all_modules(self, project_key: str) -> list[dict[str, Any]]:
        """Paginate through ALL modules in the project."""
        all_modules: list[dict[str, Any]] = []
        page = 1
        while True:
            data = self.list_modules(project_key, page=page)
            batch = data.get('data', [])
            if not batch:
                break
            all_modules.extend(batch)
            page += 1
        return all_modules

    # ------------------------------------------------------------------ #
    #  Test Cases
    # ------------------------------------------------------------------ #

    def create_test_case(
        self,
        project_key: str,
        section_key: str,
        title: str,
        description: str = '',
        precondition: str = '',
    ) -> dict[str, Any]:
        """Create a new test case in QA Touch.

        Args:
            project_key: Project key, e.g. "JlW1"
            section_key: Module/section key (from list_all_modules), e.g. "X4x9a"
            title: Test case title
            description: Optional description
            precondition: Optional precondition text

        Returns:
            API response dict. Note: does NOT contain case_key.
            Use find_case_by_title() after creation to get the key.

        Limitations:
            Type, Priority, Mode, and Tags cannot be set via API.
            They must be updated in the QA Touch UI after creation.
        """
        url = self._url('/api/v1/testCase')
        payload = {
            'projectKey': project_key,
            'sectionKey': section_key,
            'caseTitle': title,
        }
        if description:
            payload['description'] = description
        if precondition:
            payload['precondition'] = precondition
        resp = self.session.post(url, json=payload, timeout=self.timeout)
        if resp.status_code not in (200, 201):
            raise QATouchError(f'create_test_case failed: {resp.status_code} {resp.text}')
        data = resp.json()
        if not data.get('success', True):
            raise QATouchError(f'create_test_case error: {data.get("error_msg", data)}')
        return data

    def find_case_by_title(
        self,
        project_key: str,
        title: str,
        section_key: str | None = None,
    ) -> dict[str, Any] | None:
        """Find a test case by exact title match. Returns the case dict or None.

        Searches from the last page backwards (newest cases first) for efficiency
        since newly created cases appear at the end.
        """
        # Get total count from first page meta
        first_page = self.list_test_cases(project_key, page=1)
        meta = first_page.get('meta', {})
        total = meta.get('total', 0)
        per_page = 50
        last_page = (total + per_page - 1) // per_page if total else 1

        # Search backwards from last page
        for page_num in range(last_page, max(last_page - 3, 0), -1):
            data = self.list_test_cases(project_key, page=page_num)
            for case in data.get('data', []):
                if case.get('case_title') == title:
                    if section_key and case.get('module_key') != section_key:
                        continue
                    return case
        return None

    def list_test_cases(self, project_key: str, page: int = 1) -> dict[str, Any]:
        """Return one page (50 items) of test cases.

        Response: {"link": ..., "meta": {"total": N, ...}, "data": [...]}
        Each case has: case_title, case_key, module_key, module name,
        Priority, Type, NewTags, created date, etc.
        """
        url = self._url(f'/api/v1/getAllTestCases/{project_key}?page={page}')
        resp = self.session.get(url, timeout=self.timeout)
        if resp.status_code != 200:
            raise QATouchError(f'list_test_cases failed: {resp.status_code} {resp.text}')
        return resp.json()

    def list_all_test_cases(self, project_key: str) -> list[dict[str, Any]]:
        """Paginate through ALL test cases in the project. Returns flat list."""
        all_cases: list[dict[str, Any]] = []
        page = 1
        while True:
            data = self.list_test_cases(project_key, page=page)
            batch = data.get('data', [])
            if not batch:
                break
            all_cases.extend(batch)
            page += 1
        return all_cases

    # ------------------------------------------------------------------ #
    #  Users
    # ------------------------------------------------------------------ #

    def list_available_users(self, project_key: str) -> list[dict[str, Any]]:
        """List users available for test run assignment in a project.

        Returns list of: {"user_key": "d6JZ", "name": "...", "email": "..."}
        The user_key is required for assignTo in test run creation.
        """
        url = self._url(f'/api/v1/testRun/availableUsers/{project_key}')
        resp = self.session.get(url, timeout=self.timeout)
        if resp.status_code != 200:
            raise QATouchError(f'list_available_users failed: {resp.status_code} {resp.text}')
        data = resp.json()
        return data.get('data', [])

    # ------------------------------------------------------------------ #
    #  Test Runs - read
    # ------------------------------------------------------------------ #

    def list_test_runs(self, project_key: str) -> list[dict[str, Any]]:
        """List all test runs for a project. Returns list (may be empty).

        Each run has: testrun_key, Name, Description, Version, Type,
        Assigned_To, Browser, Release Name, Status, Created Date, Updated Date.
        """
        url = self._url(f'/api/v1/getAllTestRuns/{project_key}')
        resp = self.session.get(url, timeout=self.timeout)
        if resp.status_code != 200:
            raise QATouchError(f'list_test_runs failed: {resp.status_code} {resp.text}')
        data = resp.json()
        # API returns {"msg": "No Test Run(s) found..."} when empty
        if isinstance(data, dict) and 'msg' in data and 'data' not in data:
            return []
        return data.get('data', data if isinstance(data, list) else [])

    def get_test_run_results(self, project_key: str, run_key: str,
                             page: int = 1) -> dict[str, Any]:
        """Get test case results for a specific test run (100/page).

        Each result has: run_key, case_id, title, status, Created Date,
        assigned_user, code.
        """
        url = self._url(f'/api/v1/testRunResults/{project_key}/{run_key}?page={page}')
        resp = self.session.get(url, timeout=self.timeout)
        if resp.status_code != 200:
            raise QATouchError(
                f'get_test_run_results failed: {resp.status_code} {resp.text}')
        return resp.json()

    def get_all_test_run_results(self, project_key: str,
                                 run_key: str) -> list[dict[str, Any]]:
        """Paginate through ALL results for a test run. Returns flat list."""
        all_results: list[dict[str, Any]] = []
        page = 1
        while True:
            data = self.get_test_run_results(project_key, run_key, page=page)
            batch = data.get('data', [])
            if not batch:
                break
            all_results.extend(batch)
            page += 1
        return all_results

    # ------------------------------------------------------------------ #
    #  Milestones / Releases
    # ------------------------------------------------------------------ #

    def create_milestone(
        self,
        project_key: str,
        name: str,
    ) -> dict[str, Any]:
        """Create a new milestone (release) in QA Touch.

        Args:
            project_key: Project key, e.g. "JlW1"
            name: Milestone name, e.g. "v1.7.0 - Stage"

        Returns:
            {"success": true, "data": [{"milestone_id": "vqQM", ...}]}
        """
        url = self._url('/api/v1/milestone')
        payload = {
            'projectKey': project_key,
            'milestone': name,
        }
        resp = self.session.post(url, json=payload, timeout=self.timeout)
        if resp.status_code not in (200, 201):
            raise QATouchError(f'create_milestone failed: {resp.status_code} {resp.text}')
        data = resp.json()
        if not data.get('success', True):
            raise QATouchError(f'create_milestone error: {data.get("error_msg", data)}')
        return data

    # ------------------------------------------------------------------ #
    #  Test Runs - create
    # ------------------------------------------------------------------ #

    def create_test_run_all(
        self,
        project_key: str,
        name: str,
        assign_to: str,
        milestone_key: str,
    ) -> dict[str, Any]:
        """Create a test run with ALL test cases in the project.

        WARNING: Slow for large projects (2,800+ cases can take >60s).

        Args:
            project_key: Project key, e.g. "JlW1"
            name: Test run name, e.g. "Regression - Stage - v1.6.0 - 2026-02-20"
            assign_to: User key from list_available_users(), e.g. "d6JZ"
            milestone_key: Release/milestone key from QA Touch UI, e.g. "Dmn7"

        Returns:
            {"success": true, "data": [{"testrun_id": "...", ...}]}
        """
        url = self._url('/api/v1/testRun')
        payload = {
            'projectKey': project_key,
            'assignTo': assign_to,
            'milestoneKey': milestone_key,
            'testRun': name,
        }
        resp = self.session.post(url, json=payload, timeout=120)
        if resp.status_code not in (200, 201):
            raise QATouchError(f'create_test_run_all failed: {resp.status_code} {resp.text}')
        data = resp.json()
        if not data.get('success', True):
            raise QATouchError(f'create_test_run_all error: {data.get("error_msg", data)}')
        return data

    def create_test_run(
        self,
        project_key: str,
        name: str,
        assign_to: str,
        milestone_key: str,
        case_ids: list[str],
    ) -> dict[str, Any]:
        """Create a test run with specific test cases.

        Args:
            project_key: Project key, e.g. "JlW1"
            name: Test run name, e.g. "Smoke - Stage - v1.6.0 - 2026-02-20"
            assign_to: User key from list_available_users(), e.g. "d6JZ"
            milestone_key: Release/milestone key, e.g. "Dmn7"
            case_ids: List of test case keys, e.g. ["5BRMnj", "21zWnm"]

        Returns:
            {"success": true, "data": [{"testrun_id": "XGbg0", ...}]}
        """
        url = self._url('/api/v1/testRun/specific')
        payload = {
            'projectKey': project_key,
            'assignTo': assign_to,
            'milestoneKey': milestone_key,
            'testRun': name,
            'caseId': case_ids,
        }
        resp = self.session.post(url, json=payload, timeout=120)
        if resp.status_code not in (200, 201):
            raise QATouchError(f'create_test_run failed: {resp.status_code} {resp.text}')
        data = resp.json()
        if not data.get('success', True):
            raise QATouchError(f'create_test_run error: {data.get("error_msg", data)}')
        return data

    def create_test_run_by_tag(
        self,
        project_key: str,
        name: str,
        assign_to: str,
        milestone_key: str,
        tag: str,
    ) -> dict[str, Any]:
        """Create a test run with all cases matching a tag.

        Args:
            project_key: Project key, e.g. "JlW1"
            name: Test run name, e.g. "Smoke - Stage - v1.6.0"
            assign_to: User key from list_available_users(), e.g. "d6JZ"
            milestone_key: Release/milestone key, e.g. "Dmn7"
            tag: Tag name as a string, e.g. "smoke"
                 IMPORTANT: Must be a string, NOT an array. Array causes 500 error.

        Returns:
            {"success": true, "data": [{"testrun_id": "...", ...}]}
        """
        url = self._url('/api/v1/testRun/specific')
        payload = {
            'projectKey': project_key,
            'assignTo': assign_to,
            'milestoneKey': milestone_key,
            'testRun': name,
            'tags': tag,  # Must be string, not array
        }
        resp = self.session.post(url, json=payload, timeout=120)
        if resp.status_code not in (200, 201):
            raise QATouchError(f'create_test_run_by_tag failed: {resp.status_code} {resp.text}')
        data = resp.json()
        if not data.get('success', True):
            raise QATouchError(f'create_test_run_by_tag error: {data.get("error_msg", data)}')
        return data

    def create_test_run_by_module(
        self,
        project_key: str,
        name: str,
        assign_to: str,
        milestone_key: str,
        module_keys: list[str],
        mode: str | None = None,
    ) -> dict[str, Any]:
        """Create a test run with all cases from specific modules.

        Args:
            project_key: Project key, e.g. "JlW1"
            name: Test run name
            assign_to: User key from list_available_users()
            milestone_key: Release/milestone key
            module_keys: List of module section_key values
            mode: Optional filter -- "automation" or "manual"

        Returns:
            {"success": true, "data": [{"testrun_id": "...", ...}]}
        """
        url = self._url('/api/v1/testRun/specific/module/mode')
        payload = {
            'projectKey': project_key,
            'assignTo': assign_to,
            'milestoneKey': milestone_key,
            'testRun': name,
            'moduleKey': module_keys,
        }
        if mode:
            payload['mode'] = mode
        resp = self.session.post(url, json=payload, timeout=120)
        if resp.status_code not in (200, 201):
            raise QATouchError(
                f'create_test_run_by_module failed: {resp.status_code} {resp.text}')
        data = resp.json()
        if not data.get('success', True):
            raise QATouchError(
                f'create_test_run_by_module error: {data.get("error_msg", data)}')
        return data

    def clone_test_run(
        self,
        project_key: str,
        source_run_key: str,
        new_name: str,
    ) -> dict[str, Any]:
        """Clone an existing test run. All cases in the new run start as Untested.

        Args:
            project_key: Project key, e.g. "JlW1"
            source_run_key: Key of the run to clone, e.g. "vaXdn"
            new_name: Name for the cloned run

        Returns:
            {"success": true, "msg": "Test run cloned Successfully. Your new Testrun Key - zvXw9"}
        """
        url = self._url('/api/v1/clone/testRun')
        payload = {
            'projectKey': project_key,
            'testrunKey': source_run_key,
            'testrunName': new_name,
        }
        resp = self.session.post(url, json=payload, timeout=60)
        if resp.status_code not in (200, 201):
            raise QATouchError(f'clone_test_run failed: {resp.status_code} {resp.text}')
        data = resp.json()
        if not data.get('success', True):
            raise QATouchError(f'clone_test_run error: {data.get("error_msg", data)}')
        return data

    # ------------------------------------------------------------------ #
    #  Test run result updates
    # ------------------------------------------------------------------ #

    def update_test_run_results(
        self,
        project_key: str,
        test_run_key: str,
        results: list[dict[str, Any]],
        comment: str = '',
    ) -> dict[str, Any]:
        """Bulk-update test run results.

        Args:
            project_key: e.g. "JlW1"
            test_run_key: e.g. "vaXdn"
            results: list of {"case": "<case_key>", "status": <int>}
                     Status codes: 1=passed, 2=untested, 3=blocked/skipped,
                                   4=retest, 5=failed
            comment: optional comment to attach

        Uses: PATCH /api/v1/testRunResults/status/multiple
        """
        url = self._url('/api/v1/testRunResults/status/multiple')
        params = {
            'project': project_key,
            'test_run': test_run_key,
            'result': _json.dumps(results),
        }
        if comment:
            params['comment'] = comment
        resp = self.session.patch(url, params=params, timeout=self.timeout)
        if resp.status_code != 200:
            raise QATouchError(
                f'update_test_run_results failed: {resp.status_code} {resp.text}'
            )
        data = resp.json()
        if not data.get('success', True):
            raise QATouchError(
                f'update_test_run_results API error: {data.get("error_msg", data)}'
            )
        return data
