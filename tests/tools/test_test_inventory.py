"""Pins for tools/test_inventory.py: the page lists every product test once,
grouped by product and module, with its title, Steps flag and case keys."""
from __future__ import annotations

from config.products import area_of
from tools import test_inventory as ti
from tools.qatouch_cases_from_tests import TestInfo


def info(nodeid, docstring, *, parametrized=False):
    file, _, rest = nodeid.partition('::')
    cls, _, func = rest.rpartition('::')
    return TestInfo(nodeid=nodeid, file=file, area=area_of(file), class_name=cls,
                    func_name=func, docstring=docstring, skipped=False,
                    param_ids=None, parametrized=parametrized)


STEPPED = """Verify a saved view opens.

Steps:
1. Open Views and click a saved view.
   Expected: Its tiles fill the grid.
"""

TESTS = {
    'tests/ui/views/test_views_basic.py::TestViews::test_open_saved_view': info(
        'tests/ui/views/test_views_basic.py::TestViews::test_open_saved_view', STEPPED),
    'tests/ui/views/test_views_basic.py::TestViews::test_no_doc': info(
        'tests/ui/views/test_views_basic.py::TestViews::test_no_doc', ''),
    'tests/ui/admin/test_admin_users.py::TestUsers::test_add_user': info(
        'tests/ui/admin/test_admin_users.py::TestUsers::test_add_user', 'Verify a user can be added.',
        parametrized=True),
}
MAPPING = {
    'tests/ui/views/test_views_basic.py::TestViews::test_open_saved_view': {'case_key': 'AAA111'},
    'tests/ui/views/test_views_basic.py::TestViews::test_open_saved_view[chromium-b]': {'case_key': 'BBB222'},
}


def test_rows_carry_product_module_title_steps_and_keys():
    """Each test becomes one row; keys collect across its parametrizations."""
    rows = ti.inventory_rows(TESTS, MAPPING)
    assert [r.module for r in rows] == ['admin', 'views', 'views']
    assert rows[0].product == 'NexaiQ-Core'
    assert rows[0].parametrized is True
    saved = next(r for r in rows if r.nodeid.endswith('test_open_saved_view'))
    assert saved.product == 'NexaiQ-Core'
    # parse_docstring drops the closing period: the title is a QA Touch case name
    assert saved.title == 'Verify a saved view opens'
    assert saved.has_steps is True
    assert saved.case_keys == ('AAA111', 'BBB222')
    bare = next(r for r in rows if r.nodeid.endswith('test_no_doc'))
    # a docstring-less test is titled after its function, as QA Touch would title it
    assert (bare.title, bare.has_steps, bare.case_keys) == ('No doc', False, ())


def test_page_totals_headings_and_rows():
    """The page opens with per-product totals and holds one table per module."""
    page = ti.render(ti.inventory_rows(TESTS, MAPPING))
    # product | modules | files | functions | with steps | mapped
    assert '| NexaiQ-Core | 2 | 2 | 3 | 1 | 1 |' in page
    assert '| **Total** | | **2** | **3** | **1** | **1** |' in page
    assert page.index('### admin (1 tests in 1 file)') < page.index('### views (2 tests in 1 file)')
    assert ('| `test_views_basic.py::TestViews::test_open_saved_view` | Verify a saved view opens '
            '| yes | AAA111, BBB222 |') in page
    assert '| `test_admin_users.py::TestUsers::test_add_user (parametrized)` | Verify a user can be added | - | - |' in page
    assert 'Growth' not in page


def test_check_mode_tells_a_stale_page_from_a_current_one(tmp_path, monkeypatch, capsys):
    """--check exits 1 when the file differs from a fresh render, 0 when it matches."""
    monkeypatch.setattr(ti, 'build', lambda *_: 'fresh\n')
    out = tmp_path / 'inv.md'
    assert ti.main(['--out', str(out)]) == 0
    assert out.read_text(encoding='utf-8') == 'fresh\n'
    assert ti.main(['--check', '--out', str(out)]) == 0
    out.write_text('stale\n', encoding='utf-8')
    assert ti.main(['--check', '--out', str(out)]) == 1
    assert 'is stale' in capsys.readouterr().out


# --- harness and other tests ---------------------------------------------------

def test_product_files_are_the_ones_under_a_product_root():
    """A file under a product root is a product test; a pin, a page object or a file outside tests/ is not."""
    assert ti.is_product_file('tests/ui/admin/test_admin_users.py') is True
    for harness in ('tests/tools/test_x.py', 'tests/plugins/test_x.py', 'tests/helpers/test_x.py',
                    'tests/shared/pages/x.py', 'tools/test_x.py'):
        assert ti.is_product_file(harness) is False, harness


def test_other_kinds_account_for_every_non_product_file():
    """Known harness dirs get their description; a stranger is flagged unclassified; product files are skipped."""
    kinds = {k['where']: k for k in ti.other_kinds({
        'tests/tools/test_convention_check.py': 40, 'tests/tools/test_run_cli.py': 5,
        'tests/plugins/test_shims.py': 12, 'tests/helpers/test_search_job.py': 17,
        'tests/experiments/test_new_idea.py': 2,
        'tests/ui/admin/test_admin_users.py': 9, 'tests/shared/pages/admin_page.py': 0,
    })}
    assert kinds['tests/tools/']['files'] == 2
    assert kinds['tests/tools/']['functions'] == 45
    assert kinds['tests/plugins/']['collected'] == 'yes'
    stranger = kinds['unclassified: tests/experiments/']
    assert (stranger['files'], stranger['functions'], stranger['collected']) == (1, 2, 'yes')
    assert 'add a rule' in stranger['what']
    assert 'tests/ui/admin/' not in ' '.join(kinds)
    page = ti.render_other(list(kinds.values()))
    assert '| `unclassified: tests/experiments/` **(unclassified)** | 1 | 2 | yes |' in ' '.join(page)
    assert '| **This repo** | **5** | **76** | | |' in page
