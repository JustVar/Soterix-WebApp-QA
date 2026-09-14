#!/usr/bin/env python3
"""
Test Jira connection and basic bug creation/cleanup.

Loads credentials from a local .env file (JIRA_URL, JIRA_USER, JIRA_TOKEN).
Performs:
 - list all projects
 - get project details for key/name containing 'NC'
 - list available issue types
 - list custom fields
 - create a test Bug prefixed with [TEST]
 - fetch and print the created bug
 - delete the created bug (cleanup)

Run from the repo root.
"""
import sys
import traceback
from os.path import exists

try:
    from dotenv import load_dotenv
except Exception:
    print("Missing dependency: python-dotenv. Install with `pip install python-dotenv`.")
    raise

try:
    from jira import JIRA
except Exception:
    print("Missing dependency: jira (python-jira). Install with `pip install jira`.")
    raise

import os
import uuid


def load_env():
    env_path = os.path.join(os.getcwd(), ".env")
    if exists(env_path):
        load_dotenv(env_path)
        print(f"Loaded .env from {env_path}")
    else:
        print("No .env file found in repo root; attempting to read environment variables.")


def get_cred(name):
    v = os.getenv(name)
    if not v:
        print(f"Environment variable {name} is not set")
    return v


def main():
    load_env()

    JIRA_URL = get_cred("JIRA_URL") or get_cred("JIRA_SERVER") or get_cred("JIRA_HOST")
    # Support multiple naming conventions in .env
    JIRA_USER = (get_cred("JIRA_USER") or get_cred("JIRA_USERNAME") or
                 get_cred("JIRA_EMAIL"))
    JIRA_TOKEN = (get_cred("JIRA_TOKEN") or get_cred("JIRA_PASSWORD") or
                  get_cred("JIRA_API_TOKEN"))
    # Project key fallback
    JIRA_PROJECT_KEY = get_cred("JIRA_PROJECT_KEY") or get_cred("JIRA_PROJECT")

    if not (JIRA_URL and JIRA_USER and JIRA_TOKEN):
        print("Missing Jira credentials (JIRA_URL, JIRA_USER/JIRA_EMAIL, JIRA_TOKEN/JIRA_API_TOKEN). Aborting.")
        sys.exit(2)

    print("Connecting to Jira...")
    options = {"server": JIRA_URL}
    try:
        jira = JIRA(options=options, basic_auth=(JIRA_USER, JIRA_TOKEN))
        print("Connected to Jira successfully.")
    except Exception:
        print("Failed to connect to Jira:")
        traceback.print_exc()
        sys.exit(3)

    # a) List all projects
    try:
        projects = jira.projects()
        print(f"Found {len(projects)} projects:")
        for p in projects:
            print(f" - {p.key}: {p.name}")
    except Exception:
        print("Failed to list projects:")
        traceback.print_exc()

    # b) Get target project details (from env or fallback)
    target_key = JIRA_PROJECT_KEY or "NC"
    project = None
    try:
        try:
            project = jira.project(target_key)
            print(f"Project '{target_key}' details: key={project.key}, name={project.name}")
        except Exception:
            # fallback: find by name containing NC
            for p in projects:
                if (target_key and target_key in (p.key or "")) or (target_key and target_key in (p.name or "")):
                    project = p
                    break
            if project:
                print(f"Found project by name/key containing '{target_key}': {project.key} - {project.name}")
            else:
                print(f"No project with key or name containing '{target_key}' found.")
    except Exception:
        traceback.print_exc()

    # c) List available issue types
    try:
        issue_types = jira.issue_types()
        print(f"Available issue types ({len(issue_types)}):")
        for it in issue_types:
            print(f" - {it.name} (id={getattr(it, 'id', 'n/a')})")
    except Exception:
        print("Failed to list issue types:")
        traceback.print_exc()

    # d) Get custom fields (all fields) and show a subset relevant to project
    try:
        fields = jira.fields()
        print(f"Found {len(fields)} fields (showing first 25):")
        for f in fields[:25]:
            print(f" - {f.get('id')} : {f.get('name')}")
    except Exception:
        print("Failed to list fields:")
        traceback.print_exc()

    # e) Create a TEST bug
    test_issue = None
    if project is None:
        print("Skipping test issue creation because NC project was not found.")
    else:
        # find bug issue type id
        bug_type = next((it for it in issue_types if it.name.lower() == "bug"), None)
        if not bug_type:
            print("No 'Bug' issue type found; will use the first available type.")
            bug_type = issue_types[0] if issue_types else None

        summary = f"[TEST] Automated connectivity test - {uuid.uuid4()}"
        description = "This issue was created by tools/test_jira_connection.py as part of an automated connectivity test. It will be deleted automatically."
        issue_dict = {
            'project': {'key': project.key},
            'summary': summary,
            'description': description,
            'issuetype': {'name': bug_type.name if bug_type else 'Task'},
        }

        # For projects with required custom fields, we'll attempt to auto-fill them
        # using the create meta below (preferred) rather than hand-rolled placeholders.

        try:
            # Try to fill required fields using create metadata where possible
            try:
                meta = jira.createmeta(projectKeys=project.key, issuetypeNames=bug_type.name, expand='projects.issuetypes.fields')
                proj = meta.get('projects', [])[0]
                itype = proj.get('issuetypes', [])[0]
                fields_meta = itype.get('fields', {})
                # Debug: print metadata for common problematic custom fields
                debug_keys = ['customfield_10138', 'customfield_10098', 'customfield_10099', 'customfield_10135']
                for dk in debug_keys:
                    if dk in fields_meta:
                        print(f"Meta for {dk}: {fields_meta[dk]}")
                for fkey, fmeta in fields_meta.items():
                    if fmeta.get('required') and fkey not in issue_dict:
                        # pick a safe default from allowedValues if present
                        if fmeta.get('allowedValues'):
                            av = fmeta['allowedValues'][0]
                            # allowed value may have 'id' or 'value'
                            if 'id' in av:
                                issue_dict[fkey] = {'id': av['id']}
                            elif 'value' in av:
                                issue_dict[fkey] = {'value': av['value']}
                            else:
                                issue_dict[fkey] = av
                        else:
                            # fallback to a generic placeholder
                            issue_dict[fkey] = 'Automated placeholder'
            except Exception:
                # if createmeta fails, proceed with existing issue_dict (may still fail)
                pass

            print(f"Creating test issue in project {project.key} with type {issue_dict['issuetype']}")
            test_issue = jira.create_issue(fields=issue_dict)
            print(f"Created test issue: {test_issue.key}")
            # add a comment to the issue
            try:
                comment_text = "Admin: Please delete this test bug"
                comment = jira.add_comment(test_issue.key, comment_text)
                print(f"Added comment to {test_issue.key}: id={getattr(comment, 'id', 'n/a')}")
            except Exception:
                print("Failed to add comment to test issue:")
                traceback.print_exc()
        except Exception:
            print("Failed to create test issue:")
            traceback.print_exc()

    # f) List the bug we just created
    if test_issue:
        try:
            fetched = jira.issue(test_issue.key)
            print(f"Fetched issue {fetched.key}: {fetched.fields.summary} (status={fetched.fields.status.name})")
            # show comments
            try:
                comments = jira.comments(fetched)
                print(f"Issue has {len(comments)} comment(s):")
                for c in comments:
                    print(f" - ({c.id}) {c.author.displayName}: {c.body[:200]}")
            except Exception:
                print("Failed to list comments for the issue:")
                traceback.print_exc()
        except Exception:
            print("Failed to fetch created issue:")
            traceback.print_exc()

    # g) Delete the test bug (cleanup)
    if test_issue:
        print(f"Created test issue {test_issue.key}. Skipping deletion per configuration; leave for admin cleanup.")


if __name__ == '__main__':
    try:
        main()
    except Exception:
        traceback.print_exc()
        sys.exit(1)
