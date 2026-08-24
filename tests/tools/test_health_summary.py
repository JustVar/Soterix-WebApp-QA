"""Unit tests for tools/health_summary.py.

Aggregation over fake summaries: the per-target window, pass rates,
mean durations, advisory counts, the tests to watch with their history
strips and flaky rates, the verdict lines and target names, tolerance of
summaries written before per-test records existed, the page and the
terminal table, and the CLI on a temp archive. No browser, no network.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools import health_summary as hs  # noqa: E402

A = 'tests/ui/views/test_a.py::test_one'
B = 'tests/ui/views/test_a.py::test_two'
C = 'tests/ui/views/test_a.py::test_three'
M = 'tests/ui/media/test_m.py::test_m'


def _t(nodeid: str, outcome: str, seconds: float, module: str = 'ui/views/test_a.py') -> dict:
    return {'nodeid': nodeid, 'module': module, 'title': nodeid.rsplit('::', 1)[-1],
            'outcome': outcome, 'duration_s': seconds}


def _run(name: str, counts: dict, tests: list | None = None, advisories: list | None = None,
         duration: float = 100.0, exitstatus: int = 0, target: list | None = None) -> dict:
    summary = {'schema_version': 2, 'started': name[:19].replace('_', 'T'),
               'duration_s': duration, 'exitstatus': exitstatus, 'counts': counts,
               'target': target or ['tests/ui/views'], 'markexpr': '',
               'advisories': advisories or []}
    if tests is not None:
        summary['tests'] = tests
    return {'name': name, 'summary': summary}


RUNS = [
    _run('2026-08-24_12-00-00__views', {'passed': 2, 'failed': 1},
         tests=[_t(A, 'failed', 30), _t(B, 'passed', 5), _t(C, 'passed', 2)],
         advisories=[{'test': A, 'phase': 'call', 'line': '[VIEWS] x'}], exitstatus=1),
    _run('2026-08-23_12-00-00__views', {'passed': 3},
         tests=[_t(A, 'passed', 20), _t(B, 'passed', 6), _t(C, 'passed', 4)]),
    _run('2026-08-22_12-00-00__views', {'passed': 2, 'failed': 1},
         tests=[_t(A, 'passed', 25), _t(B, 'failed', 7)]),
    _run('2026-08-21_12-00-00__views', {'passed': 1}),  # schema 1: no per-test records
    _run('2026-08-24_09-00-00__media', {'passed': 4},
         tests=[_t(M, 'passed', 9, 'ui/media/test_m.py')], duration=50,
         target=['tests/ui/media']),
]


def test_window_keeps_the_newest_n_of_each_target():
    """The window keeps the newest N runs of each target, ordered newest first."""
    window = hs.select_window(RUNS, 2)
    assert [r['name'] for r in window] == [
        '2026-08-24_12-00-00__views', '2026-08-24_09-00-00__media', '2026-08-23_12-00-00__views']
    assert len(hs.select_window(RUNS, 20)) == 5
    assert hs.select_window([], 20) == []


def test_targets_aggregate_counts_including_old_summaries():
    """Per-target totals include runs from summaries without per-test records."""
    agg = hs.aggregate(RUNS, 20)
    by_slug = {t['slug']: t for t in agg['targets']}
    views = by_slug['views']
    assert views['target'] == 'tests/ui/views'
    assert views['runs'] == 4  # the schema-1 run counts here
    assert (views['passed'], views['failed']) == (8, 2)
    assert views['pass_rate'] == 0.8
    assert views['mean_duration_s'] == 100.0
    assert views['advisories'] == 1
    assert views['newest_run'] == '2026-08-24_12-00-00__views'
    assert views['newest_exit'] == 1
    media = by_slug['media']
    assert (media['runs'], media['pass_rate'], media['mean_duration_s']) == (1, 1.0, 50.0)
    assert agg['window'] == {'last_n': 20, 'runs': 5, 'newest': '2026-08-24_12-00-00__views',
                             'oldest': '2026-08-21_12-00-00__views'}


def test_modules_aggregate_per_test_records():
    """Per-module totals count only runs that carry per-test records."""
    agg = hs.aggregate(RUNS, 20)
    by_name = {m['module']: m for m in agg['modules']}
    views = by_name['ui/views/test_a.py']
    assert views['runs'] == 3  # only runs with records
    assert views['tests'] == 3
    assert (views['passed'], views['failed']) == (6, 2)
    assert views['pass_rate'] == 0.75
    assert views['mean_duration_s'] == 12.4
    assert 'advisories' not in views  # advisories are counted per target only
    media = by_name['ui/media/test_m.py']
    assert (media['runs'], media['tests'], media['mean_duration_s']) == (1, 1, 9.0)


def test_tests_to_watch_carry_strips_rates_and_last_failures():
    """Every test that failed in the window is listed with its history
    facts, sorted by flaky rate, and each target counts its own."""
    agg = hs.aggregate(RUNS, 20)
    watch = {w['nodeid']: w for w in agg['watch']}
    assert [w['nodeid'] for w in agg['watch']] == [A, B]
    a = watch[A]['facts']
    assert [b['outcome'] for b in a['blocks']] == ['passed', 'passed', 'failed']  # oldest first
    assert (a['runs'], a['passed'], a['failed'], a['flaky']) == (3, 2, 1, True)
    assert round(a['rate'], 3) == 0.333
    assert a['last_failure']['run'] == '2026-08-24_12-00-00__views'
    assert a['last_failure']['started'] == '2026-08-24T12-00-00'
    assert watch[A]['title'] == 'test_one'
    assert watch[A]['module'] == 'ui/views/test_a.py'
    b = watch[B]['facts']
    assert [x['outcome'] for x in b['blocks']] == ['failed', 'passed', 'passed']
    assert b['last_failure']['run'] == '2026-08-22_12-00-00__views'
    assert C not in watch  # never failed
    assert M not in watch
    assert {t['slug']: t['watch'] for t in agg['targets']} == {'views': 2, 'media': 0}
    assert {t['slug']: t['name'] for t in agg['targets']} == {'views': 'Views', 'media': 'Media'}
    for key in ('flaky', 'newly_failing', 'slowest'):
        assert key not in agg


def test_window_changes_the_verdicts():
    """With only the newest run per target, A's one failure is its whole
    history: a test to watch, but not flaky."""
    agg = hs.aggregate(RUNS, 1)
    assert [w['nodeid'] for w in agg['watch']] == [A]
    facts = agg['watch'][0]['facts']
    assert (facts['runs'], facts['rate'], facts['flaky']) == (1, 1.0, False)
    assert {t['slug']: t['runs'] for t in agg['targets']} == {'views': 1, 'media': 1}
    assert {t['slug']: t['watch'] for t in agg['targets']} == {'views': 1, 'media': 0}


@pytest.mark.parametrize(('label', 'name'), [
    ('tests/ui/views', 'Views'),
    ('tests/ui/views -m dragdrop', 'Views (dragdrop)'),
    ('tests/ui/admin/test_admin_sites.py', 'Admin (test_admin_sites.py)'),
    ('tests/ui/views/test_views_basic.py::TestViewsBasic::test_open[chromium]',
     'Views (test_views_basic.py::TestViewsBasic::test_open[chromium])'),
    ('tests/ui/media tests/ui/maps', 'Media + Maps'),
    ('tests/ui/lpr_search', 'Lpr search'),
    ('tests', 'All tests'),
    ('', 'All tests'),
    (' -m smoke', 'All tests (smoke)'),
    ('other/path.py', 'Other (path.py)'),
])
def test_target_name_reads_as_words(label, name):
    """A target label reads as a name a stakeholder recognises."""
    assert hs.target_name(label) == name


def test_health_verdict_one_line_per_target():
    """One exact sentence per target; none reads 'No archived runs yet.'"""
    assert hs.health_verdict(hs.aggregate(RUNS, 20)) == [
        'Media: 100% pass rate over 1 run, 0 tests to watch.',
        'Views: 80% pass rate over 4 runs, 2 tests to watch.']
    assert hs.health_verdict(hs.aggregate([], 20)) == ['No archived runs yet.']
    odd = hs.aggregate([{'name': '2026-08-01_10-00-00__x', 'summary': {}}], 20)
    assert hs.health_verdict(odd) == ['X: no results over 1 run, 0 tests to watch.']
    # Failures in runs without per-test records cannot name a test: say so, never "0".
    old = hs.aggregate([_run('2026-08-01_10-00-00__old', {'passed': 3, 'failed': 1}),
                        _run('2026-08-02_10-00-00__old', {'passed': 4},
                             tests=[_t(A, 'passed', 1)])], 20)
    assert hs.health_verdict(old) == [
        'Views: 88% pass rate over 2 runs, tests to watch unknown (1 run without per-test records).']
    assert old['targets'][0]['runs_without_records'] == 1
    assert {t['slug']: t['runs_without_records'] for t in hs.aggregate(RUNS, 20)['targets']} == \
        {'views': 1, 'media': 0}


def test_aggregate_tolerates_nothing_and_odd_summaries():
    """Aggregation returns empty results for no runs and None rates for malformed summaries."""
    empty = hs.aggregate([], 20)
    assert empty['targets'] == []
    assert empty['modules'] == []
    assert empty['window']['runs'] == 0
    odd = hs.aggregate([{'name': '2026-08-01_10-00-00__x', 'summary': {'counts': 'no',
                        'tests': 'no', 'advisories': 'no'}}], 20)
    assert odd['targets'][0]['pass_rate'] is None
    assert odd['targets'][0]['mean_duration_s'] is None
    assert odd['targets'][0]['target'] == 'x'


def test_render_health_has_every_section_and_run_links():
    """The health page shows every section, links each run and handles an empty archive."""
    page = hs.render_health(hs.aggregate(RUNS, 20), generated='2026-08-24T15:00:00')
    for heading in ('Targets (2)', 'Modules (2)', 'Tests to watch (2)'):
        assert heading in page
    for gone in ('Flaky candidates', 'Newly failing', 'Slowest tests'):
        assert gone not in page
    # The verdict leads the page, one line per target.
    assert page.index('<ul class="verdict">') < page.index('id="targets"')
    assert '<li>Views: 80% pass rate over 4 runs, 2 tests to watch.</li>' in page
    assert 'href="2026-08-24_12-00-00__views/run.html"' in page
    assert '<td class="num">80%</td>' in page
    # The advisory count links the newest run's advisories; a zero count does not link.
    assert '<a href="2026-08-24_12-00-00__views/run.html#advisories">1</a>' in page
    assert '#advisories">0</a>' not in page
    # The watch table: strip blocks linked to their runs, the rate, the last failure.
    watch = page[page.index('id="watch"'):]
    assert ('<a class="blk failed" href="2026-08-24_12-00-00__views/run.html" '
            'title="Aug 24, 12:00 PM: failed"></a>') in watch
    assert '33% (1 of 3 failed) <span class="chip delta flaky">flaky</span>' in watch
    assert '<a href="2026-08-22_12-00-00__views/run.html">Aug 22, 12:00 PM</a>' in watch
    assert 'passed 2/3' not in watch  # the strip text is the rate column's job here
    assert 'prefers-color-scheme: dark' in page
    assert 'href="index.html"' in page
    empty = hs.render_health(hs.aggregate([], 20))
    assert 'No archived runs yet' in empty
    assert 'None: no test failed in the window.' in empty
    # Failures in record-less runs: the empty table says why it names nothing.
    old = hs.render_health(hs.aggregate(
        [_run('2026-08-01_10-00-00__old', {'passed': 3, 'failed': 1})], 20))
    assert ('No test named: the failures in this window are in 1 run archived without '
            'per-test records.') in old
    assert 'None: no test failed' not in old


def test_format_table_is_compact():
    """The terminal table shows the window, per-target rates and the verdict lists."""
    text = hs.format_table(hs.aggregate(RUNS, 20))
    lines = text.splitlines()
    assert lines[0].startswith('Health: newest 20 runs of each target, 5 runs')
    assert lines[1:3] == ['Media: 100% pass rate over 1 run, 0 tests to watch.',
                          'Views: 80% pass rate over 4 runs, 2 tests to watch.']
    views = next(line for line in lines if line.startswith('tests/ui/views'))
    assert '80%' in views
    assert 'exit 1' in views
    assert f'Tests to watch (2):\n   33%  1/3 failed  last 2026-08-24T12-00-00  {A}' in text
    assert 'Slowest' not in text
    assert 'Flaky candidates' not in text


def test_cli_writes_health_html_and_links_it_from_the_index(tmp_path, capsys):
    """The CLI writes health.html into the archive and links it from index.html."""
    runs = tmp_path / 'runs'
    for run in RUNS:
        folder = runs / run['name']
        folder.mkdir(parents=True)
        (folder / 'summary.json').write_text(json.dumps(run['summary']), encoding='utf-8')
    (runs / 'index.html-not-a-run').mkdir()
    assert hs.main(['--runs-dir', str(runs), '--last', '3']) == 0
    out = capsys.readouterr().out
    assert 'Health: newest 3 runs of each target, 4 runs' in out
    assert str(runs / 'health.html') in out
    assert (runs / 'health.html').is_file()
    assert 'href="health.html"' in (runs / 'index.html').read_text(encoding='utf-8')


def test_cli_without_runs_writes_nothing(tmp_path, capsys):
    """The CLI writes no health page when the archive has no runs."""
    assert hs.main(['--runs-dir', str(tmp_path / 'none')]) == 0
    assert 'No archived runs' in capsys.readouterr().out
    assert not (tmp_path / 'none' / 'health.html').exists()
