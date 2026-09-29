"""The product roots of this repo, checked at the seam plugins/products.py
feeds them through.

The behaviour of soterix_qa_shared.reporting.products is tested in the
package. What cannot move there is this repo's own table: one root,
tests/ui, reporting to NexaiQ-Core, and the env-file key that re-points
it. A root or key that drifts sends a run's results to the wrong QA Touch
project.
"""
from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from config import products as roots  # noqa: E402
from config.base_config import config as env_settings  # noqa: E402
from plugins import products  # noqa: E402


def test_the_one_product_root_reports_to_core():
    """tests/ui is the only root, and its project is NexaiQ-Core."""
    assert roots.PRODUCT_ROOTS == {'tests/ui/': 'JlW1'}
    assert roots.SHARED_ROOT == 'tests/ui/'
    assert products.PRODUCTS['JlW1'] == 'NexaiQ-Core'
    assert roots.path_rules() == [('tests/ui/', 'JlW1')]
    assert roots.path_rules({}) == [('tests/ui/', 'JlW1')]


def test_an_env_file_re_points_the_root_at_its_project():
    """An env file that names a `qatouch_project` moves the root to that
    project for the run; a blank name leaves Core in place."""
    assert roots.path_rules({'qatouch_project': 'P0BK'}) == [('tests/ui/', 'P0BK')]
    assert roots.path_rules({'qatouch_project': ' '}) == [('tests/ui/', 'JlW1')]
    from config.env import neurosen
    assert neurosen.config['qatouch_project'] == 'P0BK'
    assert products.PRODUCTS['P0BK'] == 'NexaiQ-Neurosen'


def test_paths_resolve_against_the_root():
    """The root a path sits under, its home project for the mapping file, and its module."""
    assert roots.product_root('tests/ui/admin/test_users.py') == 'tests/ui/'
    assert roots.product_root('tests\\ui\\admin\\test_users.py') == 'tests/ui/'
    assert roots.product_root('tests/plugins/test_products.py') is None
    assert roots.home_project('tests/ui/admin/test_users.py') == 'JlW1'
    # outside the roots the mapping file's own default applies
    assert roots.home_project('tests/plugins/test_products.py') == 'JlW1'
    assert roots.area_of('tests/ui/admin/test_users.py') == 'admin'
    assert roots.area_of('tests/ui/test_x.py') == 'ui'
    assert roots.area_of('tests/plugins/test_x.py') is None


def test_the_shim_hands_the_package_this_repos_rules():
    """plugins/products.py configures the package with the rules from
    config/products.py for the active env, so a path under tests/ui
    archives under that env's project."""
    expected = dict(roots.path_rules(env_settings))['tests/ui/']
    nodeid = 'tests/ui/admin/test_users.py::TestUsers::test_add_user[chromium]'
    assert products.product_for(nodeid) == expected
