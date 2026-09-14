"""The NC Module a bug is filed under.

Module is a required field on an NC Bug, and it is a routing decision: the
wrong value sends the report to another team rather than leaving a blank
somebody fills in later. These pin the one rule that keeps it right.
"""
from __future__ import annotations

# The imports below run AFTER the repo root goes on sys.path, which they
# have to: tools/ is not importable otherwise.
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import pytest  # noqa: E402

from tools.smart_jira_bug_creator import _MODULE_MAP, _infer_module_from_nodeid  # noqa: E402


@pytest.mark.parametrize(('nodeid', 'expected'), [
    # The file path decides, not the test's own name. Measured across 819
    # collected UI tests, 29 were filed under the wrong module before this:
    # a search test inside admin went to Search rather than Admin.
    ('tests/ui/admin/test_admin_users.py::TestAdminUsers::test_search_user[chromium]', 'Admin'),
    ('tests/ui/admin/test_admin_rules.py::TestAdminRules::test_search_rule[chromium]', 'Admin'),
    ('tests/ui/lpr/test_lpr_navigation.py::T::test_navigate_from_search_results[chromium]', 'LPR'),
    ('tests/ui/views/test_views_basic.py::T::test_open_admin_panel[chromium]', 'Views'),
    # The FILE name beats the folder: an LPR suite living under admin/.
    ('tests/ui/admin/test_lpr_camera_selection.py::T::test_x[chromium]', 'LPR'),
    # With no keyword in the path at all, the test name is a better answer
    # than "Other".
    ('tests/ui/misc/test_thing.py::T::test_search_widget[chromium]', 'Search'),
    # Nothing anywhere.
    ('tests/ui/licenses/test_licenses.py::T::test_expiry[chromium]', 'Other'),
])
def test_module_comes_from_the_path_before_the_test_name(nodeid, expected):
    """The file a test lives in decides its module, not what the test does."""
    assert _infer_module_from_nodeid(nodeid) == expected


def test_every_module_we_can_produce_is_one_NC_accepts():
    """Module is a cascading select. A value NC does not know is rejected on
    create, or silently coerced to the first allowed value."""
    mapping = REPO_ROOT / 'config' / 'jira_field_mapping.json'
    if not mapping.exists():
        pytest.skip('config/jira_field_mapping.json absent; run '
                    'tools/discover_jira_fields.py')
    bug = json.loads(mapping.read_text(encoding='utf-8'))['issue_types']['Bug']['fields']
    field = next((f for f in bug.values()
                  if 'module' in str(f.get('name', '')).lower()), None)
    assert field, 'no Module field in the discovered NC Bug fields'
    allowed = {str(v.get('value') or v.get('name'))
               for v in field.get('allowed_values', [])}
    assert set(_MODULE_MAP.values()) <= allowed, (
        f'_MODULE_MAP produces values NC does not allow: '
        f'{sorted(set(_MODULE_MAP.values()) - allowed)}')
