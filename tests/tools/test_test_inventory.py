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
    # product | modules | files | functions | with steps | mapped
    assert '| NexaiQ-Camera 2 Cloud | 1 | 1 | 1 | 0 | 0 |' in page
    assert '| NexaiQ-Core | 1 | 1 | 2 | 1 | 1 |' in page
    assert '| **Total** | | **2** | **3** | **1** | **1** |' in page
    assert page.index('## NexaiQ-Camera 2 Cloud') < page.index('## NexaiQ-Core')
    assert '### views (2 tests in 1 file)' in page
    assert '### c2c (1 tests in 1 file)' in page
    assert ('| `test_views_basic.py::TestViews::test_open_saved_view` | Verify a saved view opens '
            '| yes | AAA111, BBB222 |') in page
    assert '| `test_c2c_auth.py::TestAuth::test_login (parametrized)` | Camera login accepts the admin password | - | - |' in page


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


# --- growth ledger --------------------------------------------------------------

def test_classify_names_the_product_for_every_layout_the_repos_have_had():
    """UI files split into Core and Camera 2 Cloud; API files of any era are the API; pins are nothing."""
    assert ti.classify('tests/ui/admin/test_admin_users.py') == ti.PRODUCT_CORE
    assert ti.classify('tests/ui/c2c/test_c2c_auth.py') == ti.PRODUCT_C2C
    for api_path in ('tests/api/test_events.py', 'tests/internal_api/test_camera_apis.py',
                     'tests/integration_api/test_auth.py', 'tests/smoke/test_endpoints.py'):
        assert ti.classify(api_path) == ti.PRODUCT_API, api_path
    for harness in ('tests/tools/test_x.py', 'tests/plugins/test_x.py', 'tests/helpers/test_x.py',
                    'tests/legacy/test_x.py', 'tests/shared/pages/x.py', 'tools/test_x.py'):
        assert ti.classify(harness) is None, harness


def test_counts_roll_up_by_product_and_module_and_ignore_the_harness():
    """File counts become per-product and per-module totals; harness files do not count."""
    products, modules = ti.counts_from_files({
        'tests/ui/admin/test_admin_users.py': 5, 'tests/ui/admin/test_lpr_grid.py': 4,
        'tests/ui/c2c/test_c2c_auth.py': 2, 'tests/api/test_events.py': 3,
        'tests/tools/test_convention_check.py': 40, 'tests/ui/maps/test_maps.py': 0,
    })
    assert products == {ti.PRODUCT_C2C: 2, ti.PRODUCT_CORE: 9, ti.PRODUCT_API: 3}
    assert modules == {'admin': 9, 'c2c': 2}


def row(date, commit, source='backfill', **functions):
    return ti.ledger_row(__import__('datetime').date.fromisoformat(date), commit, source, functions,
                         {'admin': functions.get(ti.PRODUCT_CORE, 0)})


def test_merge_record_replaces_appends_or_holds():
    """The same day's last row is replaced whatever its commit (the record carries Steps and
    mapping; two recordings in a day are one day's state), unchanged counts on a later day add
    nothing, moved counts append."""
    base = [row('2026-09-01', 'aaa1111', **{ti.PRODUCT_CORE: 400})]
    replaced, what = ti.merge_record(base, row('2026-09-01', 'aaa2222', 'record', **{ti.PRODUCT_CORE: 401}))
    assert (what, len(replaced), replaced[-1]['source'], replaced[-1]['commit']) == ('replaced', 1, 'record', 'aaa2222')
    same, what = ti.merge_record(base, row('2026-09-02', 'bbb2222', 'record', **{ti.PRODUCT_CORE: 400}))
    assert (what, same) == ('unchanged', base)
    grown, what = ti.merge_record(base, row('2026-09-02', 'bbb2222', 'record', **{ti.PRODUCT_CORE: 401}))
    assert (what, len(grown)) == ('appended', 2)


def test_growth_table_lists_rows_newest_first_with_a_column_per_product():
    """Every product ever recorded gets a column; a row without it shows '-'; totals sum the row."""
    history = [row('2026-02-21', 'c000001', **{ti.PRODUCT_CORE: 348, ti.PRODUCT_API: 16}),
               row('2026-09-08', 'c000002', **{ti.PRODUCT_CORE: 405, ti.PRODUCT_C2C: 32, ti.PRODUCT_API: 71})]
    history[1]['products'][ti.PRODUCT_CORE].update(steps=168, mapped=348)
    history[1]['source'] = 'record'
    lines = ti.render_growth(history)
    header = next(line for line in lines if line.startswith('| Date'))
    assert header == ('| Date | Commit | NexaiQ-Camera 2 Cloud | NexaiQ-Core | NexaiQ-Core API '
                      '| Total | Files | With Steps | Mapped | Source |')
    rows = [line for line in lines if line.startswith('| 2026')]
    # rows made without file counts (older ledgers) show '-' in Files
    assert rows[0] == '| 2026-09-08 | c000002 | 32 | 405 | 71 | 508 | - | 168 | 348 | record |'
    assert rows[1] == '| 2026-02-21 | c000001 | - | 348 | 16 | 364 | - | - | - | backfill |'
    assert 'No ledger yet' in ' '.join(ti.render_growth([]))


def test_files_are_counted_per_product_and_carried_in_the_ledger():
    """A product's file count is the number of its files holding tests; the ledger row keeps it."""
    files = ti.files_by_product({'tests/ui/admin/test_a.py': 3, 'tests/ui/admin/test_b.py': 0,
                                 'tests/ui/c2c/test_c.py': 1, 'tests/tools/test_t.py': 9})
    assert files == {ti.PRODUCT_C2C: 1, ti.PRODUCT_CORE: 1}
    import datetime
    row = ti.ledger_row(datetime.date(2026, 9, 8), 'abc1234', 'record',
                        {ti.PRODUCT_CORE: 405}, {'admin': 108}, files={ti.PRODUCT_CORE: 59})
    assert row['products'][ti.PRODUCT_CORE]['files'] == 59
    line = next(ln for ln in ti.render_growth([row]) if ln.startswith('| 2026'))
    assert line == '| 2026-09-08 | abc1234 | 405 | 405 | 59 | - | - | record |'


# --- harness and other tests ---------------------------------------------------

def test_other_kinds_account_for_every_non_product_file():
    """Known harness dirs get their description; a stranger is flagged unclassified; product files are skipped."""
    kinds = {k['where']: k for k in ti.other_kinds({
        'tests/tools/test_convention_check.py': 40, 'tests/tools/test_run_cli.py': 5,
        'tests/plugins/test_shims.py': 12, 'tests/helpers/test_search_job.py': 17,
        'tests/legacy/test_login_validator.py': 30, 'legacy-selenium-tests/test_old.py': 8,
        'tests/experiments/test_new_idea.py': 2,
        'tests/ui/admin/test_admin_users.py': 9, 'tests/shared/pages/admin_page.py': 0,
    }, siblings=[('soterix-qa-shared', {'tests/test_a.py': 600, 'tests/test_b.py': 37}, 'Pins for the package.', 'in soterix-qa-shared')])}
    assert kinds['tests/tools/']['files'] == 2
    assert kinds['tests/tools/']['functions'] == 45
    assert kinds['tests/plugins/']['collected'] == 'yes'
    assert kinds['tests/legacy/']['collected'] == 'no'
    assert kinds['legacy-selenium-tests/']['functions'] == 8
    stranger = kinds['unclassified: tests/experiments/']
    assert (stranger['files'], stranger['functions'], stranger['collected']) == (1, 2, 'yes')
    assert 'add a rule' in stranger['what']
    assert kinds['soterix-qa-shared'] == {'where': 'soterix-qa-shared', 'files': 2, 'functions': 637,
                                          'what': 'Pins for the package.', 'collected': 'in soterix-qa-shared'}
    assert 'tests/ui/admin/' not in ' '.join(kinds)
    page = ti.render_other(list(kinds.values()))
    assert '| `unclassified: tests/experiments/` **(unclassified)** | 1 | 2 | yes |' in ' '.join(page)
    assert '| **This repo** | **7** | **114** | | |' in page
