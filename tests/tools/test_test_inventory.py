"""Pins for tools/test_inventory.py: the page lists every product test once,
grouped by product and module, with its title, Steps flag and case keys."""
from __future__ import annotations

from tools import test_inventory as ti
from tools.qatouch_cases_from_tests import TestInfo


def info(nodeid, docstring, *, parametrized=False):
    file, _, rest = nodeid.partition('::')
    cls, _, func = rest.rpartition('::')
    return TestInfo(nodeid=nodeid, file=file, area=file.split('/')[2], class_name=cls,
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
    'tests/ui/c2c/test_c2c_auth.py::TestAuth::test_login': info(
        'tests/ui/c2c/test_c2c_auth.py::TestAuth::test_login', 'Camera login accepts the admin password.',
        parametrized=True),
}
MAPPING = {
    'tests/ui/views/test_views_basic.py::TestViews::test_open_saved_view': {'case_key': 'AAA111'},
    'tests/ui/views/test_views_basic.py::TestViews::test_open_saved_view[chromium-b]': {'case_key': 'BBB222'},
}


def test_rows_carry_product_module_title_steps_and_keys():
    """Each test becomes one row; keys collect across its parametrizations."""
    rows = ti.inventory_rows(TESTS, MAPPING)
    assert [r.module for r in rows] == ['c2c', 'views', 'views']
    assert rows[0].product == 'NexaiQ-Camera 2 Cloud'
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
    assert '| NexaiQ-Camera 2 Cloud | 1 | 1 | 0 | 0 |' in page
    assert '| NexaiQ-Core | 1 | 2 | 1 | 1 |' in page
    assert '| **Total** | | **3** | **1** | **1** |' in page
    assert page.index('## NexaiQ-Camera 2 Cloud') < page.index('## NexaiQ-Core')
    assert '### views (2 tests)' in page
    assert ('| `test_views_basic.py::TestViews::test_open_saved_view` | Verify a saved view opens '
            '| yes | AAA111, BBB222 |') in page
    assert '| `test_c2c_auth.py::TestAuth::test_login (parametrized)` | Camera login accepts the admin password | - | - |' in page


def test_check_mode_tells_a_stale_page_from_a_current_one(tmp_path, monkeypatch, capsys):
    """--check exits 1 when the file differs from a fresh render, 0 when it matches."""
    monkeypatch.setattr(ti, 'build', lambda: 'fresh\n')
    out = tmp_path / 'inv.md'
    assert ti.main(['--out', str(out)]) == 0
    assert out.read_text(encoding='utf-8') == 'fresh\n'
    assert ti.main(['--check', '--out', str(out)]) == 0
    out.write_text('stale\n', encoding='utf-8')
    assert ti.main(['--check', '--out', str(out)]) == 1
    assert 'is stale' in capsys.readouterr().out
