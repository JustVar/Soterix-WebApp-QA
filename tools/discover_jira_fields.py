#!/usr/bin/env python3
"""
Discover Jira field IDs and required fields for the NexaiQ-Core (NC) project.

Connects to the Jira API and queries the createmeta endpoint for each issue type
to discover:
- Required fields and their custom field IDs
- Allowed values for select/dropdown fields
- Field types and schemas

Outputs:
- Human-readable report to stdout
- JSON mapping file to config/jira_field_mapping.json

Usage:
    python tools/discover_jira_fields.py
    python tools/discover_jira_fields.py --project NC
    python tools/discover_jira_fields.py --project NC --issue-type Bug

Requires:
    pip install jira python-dotenv
"""
from __future__ import annotations

import json
import os
import sys
import traceback
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

try:
    from dotenv import load_dotenv
    load_dotenv(ROOT / ".env")
except ImportError:
    print("Warning: python-dotenv not installed. Reading from environment only.")

try:
    from jira import JIRA
except ImportError:
    print("Missing dependency: jira (python-jira). Install with: pip install jira")
    sys.exit(1)


# Issue types to discover (all NC types)
DEFAULT_ISSUE_TYPES = ["Bug", "Story", "Task", "Hotfix", "Spike", "Epic", "Sub-task", "Child Bug"]

# Output path for JSON mapping
OUTPUT_JSON = ROOT / "config" / "jira_field_mapping.json"


def get_env(name: str, fallbacks: list[str] | None = None) -> str | None:
    """Get env var with fallback names."""
    val = os.getenv(name)
    if val:
        return val
    for fb in (fallbacks or []):
        val = os.getenv(fb)
        if val:
            return val
    return None


def connect_jira() -> JIRA:
    """Connect to Jira using .env credentials."""
    url = get_env("JIRA_URL", ["JIRA_SERVER", "JIRA_HOST"])
    user = get_env("JIRA_EMAIL", ["JIRA_USER", "JIRA_USERNAME"])
    token = get_env("JIRA_API_TOKEN", ["JIRA_TOKEN", "JIRA_PASSWORD"])

    if not all([url, user, token]):
        missing = []
        if not url:
            missing.append("JIRA_URL")
        if not user:
            missing.append("JIRA_EMAIL")
        if not token:
            missing.append("JIRA_API_TOKEN")
        print(f"Missing credentials: {', '.join(missing)}")
        print("Set these in your .env file or as environment variables.")
        sys.exit(2)

    print(f"Connecting to Jira at {url}...")
    jira = JIRA(options={"server": url}, basic_auth=(user, token))
    print("Connected successfully.\n")
    return jira


def discover_issue_type_fields(jira: JIRA, project_key: str, issue_type_name: str) -> dict | None:
    """Discover fields for a specific issue type in a project.

    Returns a dict with field info or None if the issue type doesn't exist.
    """
    try:
        meta = jira.createmeta(
            projectKeys=project_key,
            issuetypeNames=issue_type_name,
            expand="projects.issuetypes.fields"
        )
    except Exception as e:
        print(f"  Warning: createmeta failed for {issue_type_name}: {e}")
        return None

    projects = meta.get("projects", [])
    if not projects:
        return None

    issue_types = projects[0].get("issuetypes", [])
    if not issue_types:
        return None

    fields_meta = issue_types[0].get("fields", {})
    result = {
        "issue_type": issue_type_name,
        "issue_type_id": issue_types[0].get("id"),
        "fields": {}
    }

    for field_id, field_meta in fields_meta.items():
        field_info = {
            "name": field_meta.get("name", ""),
            "required": field_meta.get("required", False),
            "type": field_meta.get("schema", {}).get("type", "unknown"),
            "custom_type": field_meta.get("schema", {}).get("custom"),
            "has_default": field_meta.get("hasDefaultValue", False),
        }

        # Capture allowed values for select fields
        allowed = field_meta.get("allowedValues")
        if allowed:
            field_info["allowed_values"] = []
            for av in allowed[:50]:  # cap at 50 to keep output reasonable
                entry = {}
                if "id" in av:
                    entry["id"] = av["id"]
                if "value" in av:
                    entry["value"] = av["value"]
                if "name" in av:
                    entry["name"] = av["name"]
                field_info["allowed_values"].append(entry)
            if len(allowed) > 50:
                field_info["allowed_values_truncated"] = True
                field_info["total_allowed_values"] = len(allowed)

        result["fields"][field_id] = field_info

    return result


def discover_all(jira: JIRA, project_key: str, issue_types: list[str]) -> dict:
    """Discover fields for all issue types."""
    discovered = {
        "metadata": {
            "project_key": project_key,
            "discovered_at": datetime.now().isoformat(),
            "jira_url": jira.server_url if hasattr(jira, 'server_url') else str(jira._options.get("server", "")),
        },
        "issue_types": {},
        "field_index": {},  # Reverse index: field_id -> {name, used_by_types, required_by_types}
    }

    for it_name in issue_types:
        print(f"Discovering fields for: {it_name}...")
        result = discover_issue_type_fields(jira, project_key, it_name)
        if result is None:
            print(f"  Skipped (not found or no access)")
            continue

        discovered["issue_types"][it_name] = result
        total = len(result["fields"])
        required = sum(1 for f in result["fields"].values() if f["required"])
        print(f"  Found {total} fields ({required} required)")

        # Build reverse index
        for field_id, field_info in result["fields"].items():
            if field_id not in discovered["field_index"]:
                discovered["field_index"][field_id] = {
                    "name": field_info["name"],
                    "used_by_types": [],
                    "required_by_types": [],
                }
            discovered["field_index"][field_id]["used_by_types"].append(it_name)
            if field_info["required"]:
                discovered["field_index"][field_id]["required_by_types"].append(it_name)

    return discovered


def print_report(discovered: dict) -> None:
    """Print a human-readable report of discovered fields."""
    print("\n" + "=" * 80)
    print(f"JIRA FIELD DISCOVERY REPORT -- Project: {discovered['metadata']['project_key']}")
    print(f"Discovered: {discovered['metadata']['discovered_at']}")
    print("=" * 80)

    for it_name, it_data in discovered["issue_types"].items():
        print(f"\n{'-' * 60}")
        print(f"Issue Type: {it_name} (ID: {it_data['issue_type_id']})")
        print(f"{'-' * 60}")

        # Separate required and optional
        required_fields = {k: v for k, v in it_data["fields"].items() if v["required"]}
        optional_fields = {k: v for k, v in it_data["fields"].items() if not v["required"]}

        if required_fields:
            print(f"\n  REQUIRED FIELDS ({len(required_fields)}):")
            for fid, finfo in sorted(required_fields.items(), key=lambda x: x[1]["name"]):
                custom_marker = " [CUSTOM]" if fid.startswith("customfield_") else ""
                print(f"    {fid:<30} {finfo['name']:<40} type={finfo['type']}{custom_marker}")
                if finfo.get("allowed_values"):
                    vals = [av.get("value") or av.get("name") or av.get("id") for av in finfo["allowed_values"][:10]]
                    print(f"      Allowed: {', '.join(str(v) for v in vals)}")
                    if len(finfo.get("allowed_values", [])) > 10:
                        print(f"      ... and {len(finfo['allowed_values']) - 10} more")

        print(f"\n  Optional fields: {len(optional_fields)} (not shown - see JSON output for details)")

    # Print custom field index (required fields only)
    print(f"\n{'=' * 80}")
    print("CUSTOM FIELD REFERENCE (Required across any issue type)")
    print(f"{'=' * 80}")

    for fid, finfo in sorted(discovered["field_index"].items()):
        if finfo["required_by_types"] and fid.startswith("customfield_"):
            types_str = ", ".join(finfo["required_by_types"])
            print(f"  {fid:<30} {finfo['name']:<40} Required by: {types_str}")


def save_json(discovered: dict, output_path: Path) -> None:
    """Save discovered mappings to JSON file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(discovered, f, indent=2, ensure_ascii=False)
    print(f"\nJSON mapping saved to: {output_path}")


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Discover Jira field IDs for NexaiQ-Core")
    parser.add_argument("--project", default=None, help="Jira project key (default: JIRA_PROJECT_KEY env or NC)")
    parser.add_argument("--issue-type", default=None, help="Single issue type to discover (default: all)")
    parser.add_argument("--output", default=None, help="Output JSON path (default: config/jira_field_mapping.json)")
    parser.add_argument("--no-save", action="store_true", help="Print report only, don't save JSON")
    args = parser.parse_args()

    project_key = args.project or get_env("JIRA_PROJECT_KEY", ["JIRA_PROJECT"]) or "NC"
    issue_types = [args.issue_type] if args.issue_type else DEFAULT_ISSUE_TYPES
    output_path = Path(args.output) if args.output else OUTPUT_JSON

    jira = connect_jira()

    # Verify project exists
    try:
        project = jira.project(project_key)
        print(f"Project: {project.key} - {project.name}\n")
    except Exception:
        print(f"Project '{project_key}' not found or not accessible.")
        sys.exit(3)

    # Discover fields
    discovered = discover_all(jira, project_key, issue_types)

    # Print report
    print_report(discovered)

    # Save JSON
    if not args.no_save:
        save_json(discovered, output_path)

    print("\nDone.")


if __name__ == "__main__":
    try:
        main()
    except Exception:
        traceback.print_exc()
        sys.exit(1)
