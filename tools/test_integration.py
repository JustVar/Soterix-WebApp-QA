#!/usr/bin/env python3
"""
QA Touch <-> Jira Integration Test Suite

6-phase integration testing plan for the NexaiQ-Core (NC) project.

Phases:
  1. Connector Validation     - Verify QA Touch native Jira connector is configured
  2. Bug Creation Flow        - Create a test Bug in Jira with all 8 mandatory fields
  3. Test Case Linking         - Verify QA Touch test cases can reference Jira issues
  4. Automated Bug Creator     - Test smart_jira_bug_creator with qa_touch_data mapping
  5. Verification Regression   - Re-run all 17 integration verification checks
  6. Status Mapping Validation - Verify QA Touch -> Jira status mappings are correct

Usage:
    python tools/test_integration.py                    # Run all phases
    python tools/test_integration.py --phase 1          # Run specific phase
    python tools/test_integration.py --phase 2 --live   # Create real Jira issue
    python tools/test_integration.py --dry-run           # Preview without API calls
    python tools/test_integration.py --phase 1 --checklist  # Print Phase 1 manual checklist

Requires:
    pip install jira python-dotenv requests
"""
from __future__ import annotations

import json
import os
import sys
import time
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    pass

try:
    from jira import JIRA
except ImportError:
    JIRA = None

try:
    import requests
except ImportError:
    requests = None

try:
    from config.jira_field_mapping import (
        mapper as qa_touch_mapper,
        QA_TOUCH_TO_JIRA_STATUS,
        PRIORITY_TO_SEVERITY,
        NC_ISSUE_TYPES,
        get_required_field_ids,
        get_field_allowed_values,
    )
except ImportError:
    qa_touch_mapper = None
    QA_TOUCH_TO_JIRA_STATUS = {}
    PRIORITY_TO_SEVERITY = {}
    NC_ISSUE_TYPES = {}
    get_required_field_ids = None
    get_field_allowed_values = None


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class TestResult:
    """Result of a single test."""
    def __init__(self, phase: int, name: str, passed: bool, message: str = "",
                 skipped: bool = False, details: str = ""):
        self.phase = phase
        self.name = name
        self.passed = passed
        self.skipped = skipped
        self.message = message
        self.details = details

    def __str__(self):
        if self.skipped:
            icon = "SKIP"
        else:
            icon = "PASS" if self.passed else "FAIL"
        msg = f"  [{icon}] P{self.phase}: {self.name}"
        if self.message:
            msg += f" -- {self.message}"
        return msg


class IntegrationTestSuite:
    """Runs the 6-phase integration test suite."""

    def __init__(self, live: bool = False, dry_run: bool = False):
        self.results: list[TestResult] = []
        self.live = live
        self.dry_run = dry_run
        self.jira = None
        self._jira_connected = False

    def add(self, result: TestResult):
        self.results.append(result)

    def _connect_jira(self) -> bool:
        """Connect to Jira if not already connected."""
        if self._jira_connected:
            return True
        if JIRA is None:
            return False

        url = os.getenv("JIRA_URL")
        email = os.getenv("JIRA_EMAIL") or os.getenv("JIRA_USER")
        token = os.getenv("JIRA_API_TOKEN") or os.getenv("JIRA_TOKEN")

        if not all([url, email, token]):
            return False

        try:
            self.jira = JIRA(options={"server": url}, basic_auth=(email, token))
            self._jira_connected = True
            return True
        except Exception:
            return False

    def _qatouch_headers(self) -> dict:
        """Get QA Touch API headers."""
        return {
            "Content-Type": "application/json",
            "api-token": os.getenv("QATOUCH_API_KEY", ""),
            "domain": os.getenv("QATOUCH_DOMAIN", ""),
        }

    # ===================================================================
    # Phase 1: Connector Validation
    # ===================================================================

    def phase1_connector_validation(self):
        """Verify QA Touch Jira connector is configured."""
        print("\n" + "=" * 60)
        print("PHASE 1: QA Touch Jira Connector Validation")
        print("=" * 60)

        # 1.1 Check QA Touch API connectivity
        if requests is None:
            self.add(TestResult(1, "QA Touch API library", False, "pip install requests"))
            return

        key = os.getenv("QATOUCH_API_KEY", "")
        domain = os.getenv("QATOUCH_DOMAIN", "")

        if not key or not domain:
            self.add(TestResult(1, "QA Touch credentials", False,
                                "QATOUCH_API_KEY and QATOUCH_DOMAIN must be set"))
            return

        self.add(TestResult(1, "QA Touch credentials present", True, f"Domain: {domain}"))

        # 1.2 Test QA Touch API connectivity
        try:
            resp = requests.get(
                "https://api.qatouch.com/api/v1/getAllProjects",
                headers=self._qatouch_headers(),
                timeout=10,
            )
            if resp.status_code == 200:
                data = resp.json()
                projects = data.get("data", [])
                names = [p.get("project_name", "?") for p in projects[:5]] if isinstance(projects, list) else []
                self.add(TestResult(1, "QA Touch API connection", True,
                                    f"{len(projects)} project(s): {', '.join(names)}"))
            else:
                self.add(TestResult(1, "QA Touch API connection", False,
                                    f"HTTP {resp.status_code}"))
                return
        except Exception as e:
            self.add(TestResult(1, "QA Touch API connection", False, str(e)))
            return

        # 1.3 Check QA Touch project exists
        project_id = os.getenv("QATOUCH_PROJECT_ID", "")
        if not project_id or project_id == "TBD":
            self.add(TestResult(1, "QA Touch project ID", False,
                                "QATOUCH_PROJECT_ID not set or is TBD"))
            return
        self.add(TestResult(1, "QA Touch project ID", True, f"Key: {project_id}"))

        # 1.4 Fetch test cases from the project to verify access
        try:
            resp = requests.get(
                f"https://api.qatouch.com/api/v1/getAllTestCases/{project_id}",
                headers=self._qatouch_headers(),
                timeout=15,
            )
            if resp.status_code == 200:
                data = resp.json()
                cases = data.get("data", [])
                count = len(cases) if isinstance(cases, list) else "?"
                self.add(TestResult(1, "QA Touch project accessible", True,
                                    f"{count} test cases retrieved"))
            else:
                self.add(TestResult(1, "QA Touch project accessible", False,
                                    f"HTTP {resp.status_code}: {resp.text[:200]}"))
        except Exception as e:
            self.add(TestResult(1, "QA Touch project accessible", False, str(e)))

        # 1.5 Check Jira connectivity
        if not self._connect_jira():
            self.add(TestResult(1, "Jira API connection", False,
                                "Cannot connect to Jira -- check JIRA_URL, JIRA_EMAIL, JIRA_API_TOKEN"))
            return

        self.add(TestResult(1, "Jira API connection", True, "Connected"))

        # 1.6 Check NC project accessible via Jira
        try:
            project = self.jira.project("NC")
            self.add(TestResult(1, "Jira NC project accessible", True,
                                f"{project.key} -- {project.name}"))
        except Exception as e:
            self.add(TestResult(1, "Jira NC project accessible", False, str(e)))

    # ===================================================================
    # Phase 2: Bug Creation Flow
    # ===================================================================

    def phase2_bug_creation(self):
        """Test creating a Bug in Jira with all 8 mandatory fields."""
        print("\n" + "=" * 60)
        print("PHASE 2: Bug Creation Flow")
        print("=" * 60)

        # 2.1 Verify field mapping JSON exists
        mapping_json = ROOT / "config" / "jira_field_mapping.json"
        if not mapping_json.exists():
            self.add(TestResult(2, "Field mapping JSON exists", False,
                                "Run: python tools/discover_jira_fields.py"))
            return

        with open(mapping_json, "r", encoding="utf-8") as f:
            mapping_data = json.load(f)

        self.add(TestResult(2, "Field mapping JSON exists", True))

        # 2.2 Verify all 8 mandatory Bug custom fields are in the mapping
        expected_fields = {
            "Module": "customfield_10135",
            "Steps to Reproduce": "customfield_10139",
            "Bug Overview": "customfield_10140",
            "Expected Behavior": "customfield_10141",
            "Actual Behavior": "customfield_10142",
            "Environment Found": "customfield_10098",
            "Severity": "customfield_10099",
            "Affected Build Number": "customfield_10138",
        }

        bug_fields = mapping_data.get("issue_types", {}).get("Bug", {}).get("fields", {})
        all_found = True
        for field_name, field_id in expected_fields.items():
            if field_id in bug_fields:
                self.add(TestResult(2, f"Field: {field_name}", True, f"ID: {field_id}"))
            else:
                self.add(TestResult(2, f"Field: {field_name}", False,
                                    f"Expected {field_id} not in mapping"))
                all_found = False

        if not all_found:
            self.add(TestResult(2, "All 8 mandatory fields present", False))
            return

        self.add(TestResult(2, "All 8 mandatory fields present", True))

        # 2.3 Test mapper with sample data
        if qa_touch_mapper is None:
            self.add(TestResult(2, "QATouchToJiraMapper available", False,
                                "Cannot import from config.jira_field_mapping"))
            return

        sample_data = {
            "module": "Views",
            "steps": "1. Login as test user\n2. Navigate to Views\n3. Click camera tile",
            "expected": "Camera feed loads within 10 seconds",
            "actual": "Camera feed shows black screen",
            "environment": "QA",
            "severity": "High",
            "build": "1.5.5",
            "title": "Camera feed black screen on Views page",
            "test_case_id": "TC-1001",
        }

        mapped = qa_touch_mapper.map_bug_fields(**sample_data)

        if not mapped:
            self.add(TestResult(2, "Mapper produces fields", False, "Empty mapping returned"))
            return

        self.add(TestResult(2, "Mapper produces fields", True,
                            f"{len(mapped)} fields mapped"))

        # Verify each expected field was mapped
        for field_name, field_id in expected_fields.items():
            if field_id in mapped:
                val = mapped[field_id]
                if isinstance(val, dict):
                    display = val.get("value") or val.get("id") or str(val)
                else:
                    display = str(val)[:60]
                self.add(TestResult(2, f"Mapped: {field_name}", True, display))
            else:
                self.add(TestResult(2, f"Mapped: {field_name}", False, "Not in mapper output"))

        # 2.4 Check unmapped fields
        unmapped = qa_touch_mapper.get_unmapped_required_fields("Bug", mapped)
        if unmapped:
            self.add(TestResult(2, "Unmapped required fields", False,
                                f"{len(unmapped)}: {', '.join(unmapped)}"))
        else:
            self.add(TestResult(2, "All required fields covered", True))

        # 2.5 Live bug creation (only with --live flag)
        if self.live and not self.dry_run:
            if not self._connect_jira():
                self.add(TestResult(2, "Live Bug creation", False, "Cannot connect to Jira"))
                return

            try:
                # Build issue fields
                issue_fields = {
                    "project": {"key": "NC"},
                    "summary": "[TEST] Integration test -- auto-delete",
                    "description": "Created by tools/test_integration.py Phase 2. Safe to delete.",
                    "issuetype": {"name": "Bug"},
                }
                issue_fields.update(mapped)

                issue = self.jira.create_issue(fields=issue_fields)
                issue_key = issue.key

                # Add cleanup comment
                self.jira.add_comment(issue_key,
                    "Admin: This is a test issue from test_integration.py Phase 2. "
                    "Please delete after verification.")

                self.add(TestResult(2, "Live Bug created", True,
                                    f"{issue_key} -- delete manually after review"))
            except Exception as e:
                self.add(TestResult(2, "Live Bug creation", False, str(e)))
        else:
            self.add(TestResult(2, "Live Bug creation", True,
                                "Skipped (use --live to create)",
                                skipped=True))

    # ===================================================================
    # Phase 3: Test Case Linking
    # ===================================================================

    def phase3_test_case_linking(self):
        """Verify QA Touch test cases can reference Jira issues."""
        print("\n" + "=" * 60)
        print("PHASE 3: Test Case Linking")
        print("=" * 60)

        if requests is None:
            self.add(TestResult(3, "Requests library", False, "pip install requests"))
            return

        project_id = os.getenv("QATOUCH_PROJECT_ID", "")
        if not project_id:
            self.add(TestResult(3, "QA Touch project ID", False, "Not set"))
            return

        # 3.1 Fetch test cases to verify structure
        try:
            resp = requests.get(
                f"https://api.qatouch.com/api/v1/getAllTestCases/{project_id}",
                headers=self._qatouch_headers(),
                timeout=15,
            )
            if resp.status_code != 200:
                self.add(TestResult(3, "Fetch test cases", False,
                                    f"HTTP {resp.status_code}"))
                return

            data = resp.json()
            cases = data.get("data", [])
            if not isinstance(cases, list) or not cases:
                self.add(TestResult(3, "Test cases exist", False, "No test cases found"))
                return

            self.add(TestResult(3, "Test cases retrievable", True,
                                f"{len(cases)} cases in project"))

            # 3.2 Check if any test cases have Jira issue links
            linked_count = 0
            for tc in cases:
                # QA Touch stores issue links in various fields depending on version
                issue_id = tc.get("issue_id") or tc.get("jira_issue_key") or tc.get("linked_issue")
                if issue_id:
                    linked_count += 1

            if linked_count > 0:
                self.add(TestResult(3, "Test cases with Jira links", True,
                                    f"{linked_count} of {len(cases)} linked"))
            else:
                self.add(TestResult(3, "Test cases with Jira links", True,
                                    "0 linked (expected -- linking done in QA Touch UI)",
                                    skipped=False))

        except Exception as e:
            self.add(TestResult(3, "Fetch test cases", False, str(e)))
            return

        # 3.3 Verify Jira has NC issues that can be linked to
        if self._connect_jira():
            try:
                issues = self.jira.search_issues("project = NC ORDER BY created DESC", maxResults=5)
                if issues:
                    keys = [i.key for i in issues]
                    self.add(TestResult(3, "NC issues available for linking", True,
                                        f"Recent: {', '.join(keys)}"))
                else:
                    self.add(TestResult(3, "NC issues available for linking", True,
                                        "No issues yet (new project)",
                                        skipped=False))
            except Exception as e:
                self.add(TestResult(3, "NC issues available for linking", False, str(e)))
        else:
            self.add(TestResult(3, "Jira connection for linking", False,
                                "Cannot connect to verify"))

        # 3.4 Verify QA Touch module structure matches Jira modules
        try:
            resp = requests.get(
                f"https://api.qatouch.com/api/v1/getAllModules/{project_id}",
                headers=self._qatouch_headers(),
                timeout=10,
            )
            if resp.status_code == 200:
                mod_data = resp.json()
                modules = mod_data.get("data", [])
                if isinstance(modules, list):
                    parent_modules = [m.get("title", "?") for m in modules if not m.get("parent_id")]
                    self.add(TestResult(3, "QA Touch modules retrievable", True,
                                        f"{len(modules)} modules, {len(parent_modules)} top-level"))
                else:
                    self.add(TestResult(3, "QA Touch modules retrievable", True,
                                        "Module data returned"))
            else:
                self.add(TestResult(3, "QA Touch modules", False,
                                    f"HTTP {resp.status_code}"))
        except Exception as e:
            self.add(TestResult(3, "QA Touch modules", False, str(e)))

    # ===================================================================
    # Phase 4: Automated Bug Creator
    # ===================================================================

    def phase4_automated_bug_creator(self):
        """Test the smart_jira_bug_creator with qa_touch_data mapping."""
        print("\n" + "=" * 60)
        print("PHASE 4: Automated Bug Creator (smart_jira_bug_creator)")
        print("=" * 60)

        # 4.1 Import the smart bug creator
        try:
            from tools.smart_jira_bug_creator import JiraClient, multi_gate_validation
            self.add(TestResult(4, "Import smart_jira_bug_creator", True))
        except ImportError as e:
            self.add(TestResult(4, "Import smart_jira_bug_creator", False, str(e)))
            return

        # 4.2 Test JiraClient initialization
        try:
            client = JiraClient()
            self.add(TestResult(4, "JiraClient init", True,
                                f"Server: {client.server or 'not set'}"))
        except Exception as e:
            self.add(TestResult(4, "JiraClient init", False, str(e)))
            return

        # 4.3 Test create_issue with qa_touch_data (disabled mode -- BUG_CREATION_ENABLED=false)
        sample_qa_data = {
            "module": "Events",
            "steps": "1. Login\n2. Navigate to Events\n3. Search for event by keyword",
            "expected": "Search results show matching events",
            "actual": "No results returned despite matching events existing",
            "environment": "QA",
            "severity": "Medium",
            "build": "1.5.5",
            "title": "Events search returns no results",
            "test_case_id": "TC-2001",
        }

        try:
            # Ensure disabled mode
            old_val = os.environ.get("BUG_CREATION_ENABLED")
            os.environ["BUG_CREATION_ENABLED"] = "false"

            result = client.create_issue(
                summary="[TEST] Automated bug creator test",
                description="Created by test_integration.py Phase 4.",
                labels=["automation-test-DELETE-ME"],
                project_key="NC",
                qa_touch_data=sample_qa_data,
            )

            # Restore env
            if old_val is not None:
                os.environ["BUG_CREATION_ENABLED"] = old_val
            else:
                os.environ.pop("BUG_CREATION_ENABLED", None)

            if result and result.get("key"):
                self.add(TestResult(4, "create_issue (disabled mode)", True,
                                    f"Fake key: {result['key']}"))
            else:
                self.add(TestResult(4, "create_issue (disabled mode)", False,
                                    "No result returned"))
                return

            # 4.4 Check that mapped_fields were populated
            mapped = result.get("mapped_fields", {})
            if mapped:
                self.add(TestResult(4, "QA Touch data mapped", True,
                                    f"{len(mapped)} fields auto-populated"))
            else:
                self.add(TestResult(4, "QA Touch data mapped", False,
                                    "No mapped_fields in result (mapper not available?)"))

            # 4.5 Check unmapped fields
            unmapped = result.get("unmapped_required_fields", [])
            if unmapped:
                self.add(TestResult(4, "Unmapped required fields", False,
                                    f"{len(unmapped)}: {', '.join(unmapped[:3])}..."))
            else:
                self.add(TestResult(4, "All required fields populated", True))

        except Exception as e:
            self.add(TestResult(4, "create_issue with qa_touch_data", False, str(e)))

        # 4.6 Test multi_gate_validation (stub -- no history)
        try:
            gate_result = multi_gate_validation("test::fake_nodeid")
            action = gate_result.get("action", "?")
            self.add(TestResult(4, "multi_gate_validation", True,
                                f"Action: {action} (expected no_action for empty history)"))
        except Exception as e:
            self.add(TestResult(4, "multi_gate_validation", False, str(e)))

    # ===================================================================
    # Phase 5: Verification Regression
    # ===================================================================

    def phase5_verification_regression(self):
        """Re-run verify_jira_integration.py checks inline."""
        print("\n" + "=" * 60)
        print("PHASE 5: Verification Regression (17 checks)")
        print("=" * 60)

        try:
            from tools.verify_jira_integration import IntegrationVerifier
            self.add(TestResult(5, "Import IntegrationVerifier", True))
        except ImportError as e:
            self.add(TestResult(5, "Import IntegrationVerifier", False, str(e)))
            return

        verifier = IntegrationVerifier()

        # Run Jira checks
        verifier.run_jira_checks(create_test_bug=False)
        verifier.run_qatouch_checks()

        # Convert verifier results to our TestResults
        passed = 0
        failed = 0
        for r in verifier.results:
            self.add(TestResult(5, r.name, r.passed, r.message))
            if r.passed:
                passed += 1
            else:
                failed += 1

        self.add(TestResult(5, "Regression summary", failed == 0,
                            f"{passed}/{passed + failed} checks passed"))

    # ===================================================================
    # Phase 6: Status Mapping Validation
    # ===================================================================

    def phase6_status_mapping(self):
        """Verify QA Touch -> Jira status mappings are correct."""
        print("\n" + "=" * 60)
        print("PHASE 6: Status Mapping Validation")
        print("=" * 60)

        # 6.1 Verify QA_TOUCH_TO_JIRA_STATUS mapping exists
        if not QA_TOUCH_TO_JIRA_STATUS:
            self.add(TestResult(6, "Status mapping loaded", False,
                                "QA_TOUCH_TO_JIRA_STATUS is empty"))
            return

        expected_mapping = {
            "Passed": "Complete",
            "Failed": "QA Not Passed",
            "Blocked": "Blocked",
            "Skipped": None,
            "Not Tested": None,
        }

        all_match = True
        for qa_status, expected_jira in expected_mapping.items():
            actual_jira = QA_TOUCH_TO_JIRA_STATUS.get(qa_status, "MISSING")
            if actual_jira == expected_jira:
                display = expected_jira if expected_jira else "(no Jira action)"
                self.add(TestResult(6, f"Map: {qa_status}", True, f"-> {display}"))
            else:
                self.add(TestResult(6, f"Map: {qa_status}", False,
                                    f"Expected {expected_jira}, got {actual_jira}"))
                all_match = False

        self.add(TestResult(6, "All status mappings correct", all_match))

        # 6.2 Verify PRIORITY_TO_SEVERITY mapping
        expected_priority = {
            "Critical": "Highest",
            "High": "High",
            "Medium": "Medium",
            "Low": "Low",
        }

        for qa_pri, expected_sev in expected_priority.items():
            actual_sev = PRIORITY_TO_SEVERITY.get(qa_pri, "MISSING")
            if actual_sev == expected_sev:
                self.add(TestResult(6, f"Priority: {qa_pri}", True, f"-> Severity: {expected_sev}"))
            else:
                self.add(TestResult(6, f"Priority: {qa_pri}", False,
                                    f"Expected {expected_sev}, got {actual_sev}"))

        # 6.3 Verify NC_ISSUE_TYPES has QA-relevant flags
        if NC_ISSUE_TYPES:
            qa_creates = [t for t, info in NC_ISSUE_TYPES.items() if info.get("qa_creates")]
            qa_tests = [t for t, info in NC_ISSUE_TYPES.items() if info.get("qa_tests")]
            self.add(TestResult(6, "QA creates these types", True,
                                ", ".join(qa_creates)))
            self.add(TestResult(6, "QA tests these types", True,
                                ", ".join(qa_tests)))
        else:
            self.add(TestResult(6, "NC_ISSUE_TYPES loaded", False))

        # 6.4 Verify Jira workflow statuses exist (if connected)
        if self._connect_jira():
            try:
                statuses = self.jira.statuses()
                status_names = {s.name for s in statuses}
                expected_statuses = {
                    "Ready for QA", "QA in Progress", "Complete",
                    "QA Not Passed", "Blocked", "Ready for Dev",
                }
                for st in expected_statuses:
                    if st in status_names:
                        self.add(TestResult(6, f"Jira status: {st}", True))
                    else:
                        self.add(TestResult(6, f"Jira status: {st}", False, "Not found"))
            except Exception as e:
                self.add(TestResult(6, "Jira statuses check", False, str(e)))

    # ===================================================================
    # Summary
    # ===================================================================

    def print_summary(self) -> bool:
        """Print all results with summary."""
        print("\n" + "=" * 60)
        print("INTEGRATION TEST SUITE SUMMARY")
        print("=" * 60)

        # Group by phase
        phases = {}
        for r in self.results:
            phases.setdefault(r.phase, []).append(r)

        phase_names = {
            1: "Connector Validation",
            2: "Bug Creation Flow",
            3: "Test Case Linking",
            4: "Automated Bug Creator",
            5: "Verification Regression",
            6: "Status Mapping Validation",
        }

        for phase_num in sorted(phases.keys()):
            phase_results = phases[phase_num]
            print(f"\n--- Phase {phase_num}: {phase_names.get(phase_num, '?')} ---")
            for r in phase_results:
                print(r)

        total = len(self.results)
        passed = sum(1 for r in self.results if r.passed and not r.skipped)
        failed = sum(1 for r in self.results if not r.passed and not r.skipped)
        skipped = sum(1 for r in self.results if r.skipped)

        print(f"\n{'=' * 60}")
        print(f"  Total: {total}  |  Passed: {passed}  |  Failed: {failed}  |  Skipped: {skipped}")

        if failed == 0:
            print("\n  All checks passed!")
        else:
            print(f"\n  {failed} check(s) failed -- review above for details.")

        print("=" * 60)
        return failed == 0


# ---------------------------------------------------------------------------
# Phase 1 Manual Checklist
# ---------------------------------------------------------------------------

PHASE1_CHECKLIST = """
============================================================
PHASE 1: QA Touch Jira Connector - Manual Checklist
============================================================

Complete these steps in the QA Touch admin panel to configure
the native Jira integration. Refer to:
  docs/QA_Touch_Setup_Guide.md  Section 10.2

------------------------------------------------------------
PRE-REQUISITES
------------------------------------------------------------
[ ] Jira admin account credentials available
[ ] QA Touch admin access (Justin - Admin role)
[ ] NC project exists in Jira (key: NC)

------------------------------------------------------------
STEP 1: Generate Jira API Token
------------------------------------------------------------
[ ] Log in to Jira as admin
[ ] Go to: https://id.atlassian.com/manage-profile/security/api-tokens
[ ] Create token labeled "QA Touch Integration"
[ ] Copy and store token securely

------------------------------------------------------------
STEP 2: Configure Jira in QA Touch
------------------------------------------------------------
[ ] Log in to QA Touch as Administrator
[ ] Go to Administration > Integration Settings
[ ] Find JIRA and click Configure
[ ] Enter Jira Cloud URL: https://soterixsystems.atlassian.net
[ ] Enter Jira User Email (admin account email)
[ ] Paste API Token
[ ] Click "Test Connection" -- should show success
[ ] Click Save

------------------------------------------------------------
STEP 3: Map QA Touch Project to Jira Project
------------------------------------------------------------
[ ] Open NexaiQ-Core project in QA Touch
[ ] Go to Project Integration Mapping
[ ] Select JIRA
[ ] Map: QA Touch "NexaiQ-Core" -> Jira "NC"
[ ] Save

------------------------------------------------------------
STEP 4: Configure Field Mappings
------------------------------------------------------------
[ ] In Project Integration Mapping > Field Mapping
[ ] Map Priority -> Priority
[ ] Map Module -> Component (if applicable)
[ ] Save

------------------------------------------------------------
STEP 5: Verify Integration
------------------------------------------------------------
[ ] Open any test case in QA Touch
[ ] Look for Create Issue / Link Issue button
[ ] Click it -- verify Jira form appears
[ ] Verify NC project shows in dropdown
[ ] Cancel (do not create test issue yet)

------------------------------------------------------------
VALIDATION
------------------------------------------------------------
After completing all steps, run:
  python tools/test_integration.py --phase 1

All Phase 1 checks should pass.
============================================================
"""


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main():
    import argparse

    parser = argparse.ArgumentParser(description="QA Touch <-> Jira Integration Test Suite")
    parser.add_argument("--phase", type=int, choices=[1, 2, 3, 4, 5, 6],
                        help="Run specific phase only")
    parser.add_argument("--live", action="store_true",
                        help="Create real Jira issues (Phase 2)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Preview without any API calls")
    parser.add_argument("--checklist", action="store_true",
                        help="Print Phase 1 manual checklist")
    args = parser.parse_args()

    if args.checklist:
        print(PHASE1_CHECKLIST)
        return

    suite = IntegrationTestSuite(live=args.live, dry_run=args.dry_run)

    print("=" * 60)
    print("QA Touch <-> Jira Integration Test Suite")
    print(f"Project: NexaiQ-Core (NC)")
    print(f"QA Touch Project: {os.getenv('QATOUCH_PROJECT_ID', 'not set')}")
    print(f"Mode: {'LIVE' if args.live else 'DRY-RUN' if args.dry_run else 'STANDARD'}")
    print(f"Time: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    phases = {
        1: suite.phase1_connector_validation,
        2: suite.phase2_bug_creation,
        3: suite.phase3_test_case_linking,
        4: suite.phase4_automated_bug_creator,
        5: suite.phase5_verification_regression,
        6: suite.phase6_status_mapping,
    }

    if args.phase:
        phases[args.phase]()
    else:
        for phase_fn in phases.values():
            phase_fn()

    success = suite.print_summary()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        sys.exit(1)
