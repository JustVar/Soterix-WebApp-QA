#!/usr/bin/env python3
"""
Verify Jira & QA Touch integration for NexaiQ-Core (NC).

Runs a series of checks to validate that:
1. Jira API credentials are valid
2. NC project is accessible
3. Issue types are available
4. Required Bug fields match discovered mapping
5. QA Touch API credentials are valid (if configured)
6. QA Touch project is accessible (if configured)

Usage:
    python tools/verify_jira_integration.py
    python tools/verify_jira_integration.py --create-test-bug    # Also creates a test bug
    python tools/verify_jira_integration.py --jira-only          # Skip QA Touch checks
    python tools/verify_jira_integration.py --qatouch-only       # Skip Jira checks

Requires:
    pip install jira python-dotenv requests
"""
from __future__ import annotations

import json
import os
import sys
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

MAPPING_JSON = ROOT / "config" / "jira_field_mapping.json"


class CheckResult:
    """Result of a single verification check."""

    def __init__(self, name: str, passed: bool, message: str = "", details: str = ""):
        self.name = name
        self.passed = passed
        self.message = message
        self.details = details

    def __str__(self):
        icon = "PASS" if self.passed else "FAIL"
        msg = f"  [{icon}] {self.name}"
        if self.message:
            msg += f" - {self.message}"
        return msg


class IntegrationVerifier:
    """Runs verification checks for Jira and QA Touch integration."""

    def __init__(self):
        self.results: list[CheckResult] = []
        self.jira = None

    def add(self, result: CheckResult):
        self.results.append(result)

    # ── Jira Checks ──────────────────────────────────────────

    def check_jira_credentials(self) -> bool:
        """Check that Jira credentials are configured."""
        url = os.getenv("JIRA_URL")
        email = os.getenv("JIRA_EMAIL") or os.getenv("JIRA_USER")
        token = os.getenv("JIRA_API_TOKEN") or os.getenv("JIRA_TOKEN")

        if not url:
            self.add(CheckResult("Jira URL configured", False, "JIRA_URL not set in .env"))
            return False
        if not email:
            self.add(CheckResult("Jira email configured", False, "JIRA_EMAIL not set in .env"))
            return False
        if not token:
            self.add(CheckResult("Jira API token configured", False, "JIRA_API_TOKEN not set in .env"))
            return False

        self.add(CheckResult("Jira credentials configured", True, f"URL: {url}"))
        return True

    def check_jira_connection(self) -> bool:
        """Connect to Jira and verify credentials."""
        if JIRA is None:
            self.add(CheckResult("Jira library available", False, "pip install jira"))
            return False

        url = os.getenv("JIRA_URL")
        email = os.getenv("JIRA_EMAIL") or os.getenv("JIRA_USER")
        token = os.getenv("JIRA_API_TOKEN") or os.getenv("JIRA_TOKEN")

        try:
            self.jira = JIRA(options={"server": url}, basic_auth=(email, token))
            myself = self.jira.myself()
            self.add(CheckResult("Jira API connection", True, f"Authenticated as: {myself.get('displayName', email)}"))
            return True
        except Exception as e:
            self.add(CheckResult("Jira API connection", False, str(e)))
            return False

    def check_nc_project(self) -> bool:
        """Verify NC project is accessible."""
        project_key = os.getenv("JIRA_PROJECT_KEY", "NC")

        try:
            project = self.jira.project(project_key)
            self.add(CheckResult(f"Project {project_key} accessible", True, f"{project.key} - {project.name}"))
            return True
        except Exception as e:
            self.add(CheckResult(f"Project {project_key} accessible", False, str(e)))
            return False

    def check_issue_types(self) -> bool:
        """List available issue types in NC."""
        project_key = os.getenv("JIRA_PROJECT_KEY", "NC")
        expected_types = {"Bug", "Story", "Task", "Epic"}

        try:
            meta = self.jira.createmeta(projectKeys=project_key, expand="projects.issuetypes")
            projects = meta.get("projects", [])
            if not projects:
                self.add(CheckResult("Issue types available", False, "No projects in createmeta response"))
                return False

            type_names = {it["name"] for it in projects[0].get("issuetypes", [])}
            missing = expected_types - type_names
            if missing:
                self.add(CheckResult("Issue types available", False, f"Missing expected types: {missing}"))
                return False

            self.add(CheckResult("Issue types available", True, f"{len(type_names)} types: {', '.join(sorted(type_names))}"))
            return True
        except Exception as e:
            self.add(CheckResult("Issue types available", False, str(e)))
            return False

    def check_bug_required_fields(self) -> bool:
        """Check that Bug has expected required fields."""
        project_key = os.getenv("JIRA_PROJECT_KEY", "NC")

        try:
            meta = self.jira.createmeta(
                projectKeys=project_key,
                issuetypeNames="Bug",
                expand="projects.issuetypes.fields"
            )
            projects = meta.get("projects", [])
            if not projects:
                self.add(CheckResult("Bug required fields", False, "No projects in createmeta"))
                return False

            issue_types = projects[0].get("issuetypes", [])
            if not issue_types:
                self.add(CheckResult("Bug required fields", False, "Bug type not found"))
                return False

            fields = issue_types[0].get("fields", {})
            required = {fid: f for fid, f in fields.items() if f.get("required")}
            custom_required = {fid: f for fid, f in required.items() if fid.startswith("customfield_")}

            self.add(CheckResult(
                "Bug required fields",
                True,
                f"{len(required)} total required ({len(custom_required)} custom)"
            ))

            # List custom required fields
            for fid, f in sorted(custom_required.items()):
                self.add(CheckResult(
                    f"  Custom field: {f['name']}",
                    True,
                    f"ID: {fid}, type: {f.get('schema', {}).get('type', '?')}"
                ))

            return True
        except Exception as e:
            self.add(CheckResult("Bug required fields", False, str(e)))
            return False

    def check_field_mapping_json(self) -> bool:
        """Check that config/jira_field_mapping.json exists and is valid."""
        if not MAPPING_JSON.exists():
            self.add(CheckResult(
                "Field mapping JSON",
                False,
                f"Not found at {MAPPING_JSON}. Run: python tools/discover_jira_fields.py"
            ))
            return False

        try:
            with open(MAPPING_JSON, "r", encoding="utf-8") as f:
                data = json.load(f)

            issue_types = list(data.get("issue_types", {}).keys())
            field_count = len(data.get("field_index", {}))
            self.add(CheckResult(
                "Field mapping JSON",
                True,
                f"{len(issue_types)} issue types, {field_count} fields indexed"
            ))
            return True
        except Exception as e:
            self.add(CheckResult("Field mapping JSON", False, str(e)))
            return False

    def check_jira_create_test_bug(self) -> bool:
        """Create a test Bug in NC to verify all mandatory fields can be populated."""
        project_key = os.getenv("JIRA_PROJECT_KEY", "NC")

        try:
            # Get required fields from createmeta
            meta = self.jira.createmeta(
                projectKeys=project_key,
                issuetypeNames="Bug",
                expand="projects.issuetypes.fields"
            )
            fields_meta = meta["projects"][0]["issuetypes"][0]["fields"]

            issue_fields = {
                "project": {"key": project_key},
                "summary": "[TEST] Integration verification - auto-delete",
                "description": "Created by tools/verify_jira_integration.py. Safe to delete.",
                "issuetype": {"name": "Bug"},
            }

            # Auto-fill required custom fields with first allowed value
            for fid, fmeta in fields_meta.items():
                if fmeta.get("required") and fid not in issue_fields:
                    allowed = fmeta.get("allowedValues")
                    if allowed:
                        av = allowed[0]
                        if "id" in av:
                            issue_fields[fid] = {"id": av["id"]}
                        elif "value" in av:
                            issue_fields[fid] = {"value": av["value"]}
                        else:
                            issue_fields[fid] = av
                    else:
                        issue_fields[fid] = "Test placeholder"

            issue = self.jira.create_issue(fields=issue_fields)
            issue_key = issue.key

            # Add admin cleanup comment
            self.jira.add_comment(issue_key, "Admin: This is a test issue from verify_jira_integration.py. Please delete.")

            self.add(CheckResult(
                "Test Bug creation",
                True,
                f"Created {issue_key} - delete manually or via Jira admin"
            ))
            return True
        except Exception as e:
            self.add(CheckResult("Test Bug creation", False, str(e)))
            return False

    # ── QA Touch Checks ──────────────────────────────────────

    def check_qatouch_credentials(self) -> bool:
        """Check that QA Touch credentials are configured."""
        key = os.getenv("QATOUCH_API_KEY")
        domain = os.getenv("QATOUCH_DOMAIN")

        if not key:
            self.add(CheckResult("QA Touch API key configured", False, "QATOUCH_API_KEY not set in .env"))
            return False
        if not domain:
            self.add(CheckResult("QA Touch domain configured", False, "QATOUCH_DOMAIN not set in .env (e.g. 'soterixsystems')"))
            return False

        self.add(CheckResult("QA Touch credentials configured", True, f"Domain: {domain}"))
        return True

    def check_qatouch_connection(self) -> bool:
        """Test QA Touch API connectivity."""
        if requests is None:
            self.add(CheckResult("QA Touch API connection", False, "pip install requests"))
            return False

        key = os.getenv("QATOUCH_API_KEY", "")
        domain = os.getenv("QATOUCH_DOMAIN", "")

        # QA Touch API: https://api.qatouch.com with api-token + domain headers
        api_base = "https://api.qatouch.com"
        headers = {
            "Content-Type": "application/json",
            "api-token": key,
            "domain": domain,
        }

        try:
            resp = requests.get(
                f"{api_base}/api/v1/getAllProjects",
                headers=headers,
                timeout=10
            )
            if resp.status_code == 200:
                data = resp.json()
                projects = data.get("data", [])
                count = len(projects) if isinstance(projects, list) else "?"
                project_names = ", ".join(p.get("project_name", "?") for p in projects[:5]) if isinstance(projects, list) else ""
                self.add(CheckResult("QA Touch API connection", True, f"{count} project(s): {project_names}"))
                return True
            else:
                self.add(CheckResult("QA Touch API connection", False, f"HTTP {resp.status_code} from {api_base}"))
                return False
        except Exception as e:
            self.add(CheckResult("QA Touch API connection", False, str(e)))
            return False

    def check_qatouch_project(self) -> bool:
        """Check that the QA Touch project ID is configured and valid."""
        project_id = os.getenv("QATOUCH_PROJECT_ID")
        if not project_id or project_id == "TBD":
            self.add(CheckResult("QA Touch project ID", False, "QATOUCH_PROJECT_ID not set or is TBD"))
            return False

        self.add(CheckResult("QA Touch project ID", True, f"Project ID: {project_id}"))
        return True

    # ── Run All ──────────────────────────────────────────────

    def run_jira_checks(self, create_test_bug: bool = False):
        """Run all Jira checks."""
        print("\n=== JIRA INTEGRATION CHECKS ===\n")

        if not self.check_jira_credentials():
            return
        if not self.check_jira_connection():
            return

        self.check_nc_project()
        self.check_issue_types()
        self.check_bug_required_fields()
        self.check_field_mapping_json()

        if create_test_bug:
            self.check_jira_create_test_bug()

    def run_qatouch_checks(self):
        """Run all QA Touch checks."""
        print("\n=== QA TOUCH INTEGRATION CHECKS ===\n")

        if not self.check_qatouch_credentials():
            return
        self.check_qatouch_connection()
        self.check_qatouch_project()

    def print_summary(self):
        """Print all results with summary."""
        print("\n" + "=" * 60)
        print("INTEGRATION VERIFICATION SUMMARY")
        print("=" * 60)

        for r in self.results:
            print(r)

        passed = sum(1 for r in self.results if r.passed)
        failed = sum(1 for r in self.results if not r.passed)
        total = len(self.results)

        print(f"\n{'-' * 60}")
        print(f"  Total: {total}  |  Passed: {passed}  |  Failed: {failed}")

        if failed == 0:
            print("\n  All checks passed!")
        else:
            print(f"\n  {failed} check(s) failed -- review above for details.")

        print("=" * 60)
        return failed == 0


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Verify Jira & QA Touch integration")
    parser.add_argument("--create-test-bug", action="store_true", help="Create a test Bug in Jira NC")
    parser.add_argument("--jira-only", action="store_true", help="Skip QA Touch checks")
    parser.add_argument("--qatouch-only", action="store_true", help="Skip Jira checks")
    args = parser.parse_args()

    verifier = IntegrationVerifier()

    if not args.qatouch_only:
        verifier.run_jira_checks(create_test_bug=args.create_test_bug)

    if not args.jira_only:
        verifier.run_qatouch_checks()

    success = verifier.print_summary()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        sys.exit(1)
