"""Unit tests for tools/health_summary.py.

Aggregation over fake summaries: the per-target window, pass rates,
mean durations, advisory counts, flaky candidates, newly failing tests,
the slowest tests, tolerance of summaries written before per-test
records existed, the page and the terminal table, and the CLI on a
temp archive. No browser, no network.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

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
    window = hs.select_window(RUNS, 2)
    assert [r['name'] for r in window] == [
        '2026-08-24_12-00-00__views', '2026-08-24_09-00-00__media', '2026-08-23_12-00-00__views']
    assert len(hs.select_window(RUNS, 20)) == 5
    assert hs.select_window([], 20) == []


def test_targets_aggregate_counts_including_old_summaries():
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
    agg = hs.aggregate(RUNS, 20)
    by_name = {m['module']: m for m in agg['modules']}
    views = by_name['ui/views/test_a.py']
    assert views['runs'] == 3  # only runs with records
    assert views['tests'] == 3
    assert (views['passed'], views['failed']) == (6, 2)
    assert views['pass_rate'] == 0.75
    assert views['mean_duration_s'] == 12.4
    assert views['advisories'] == 1
    media = by_name['ui/media/test_m.py']
    assert (media['runs'], media['tests'], media['mean_duration_s']) == (1, 1, 9.0)


def test_flaky_newly_failing_and_slowest():
    agg = hs.aggregate(RUNS, 20)
    flaky = [(f['nodeid'], f['passed'], f['failed']) for f in agg['flaky']]
    assert flaky == [(A, 2, 1), (B, 2, 1)]
    assert agg['flaky'][0]['last_outcome'] == 'failed'
    newly = [(n['nodeid'], n['run'], n['previous_run']) for n in agg['newly_failing']]
    assert newly == [(A, '2026-08-24_12-00-00__views', '2026-08-23_12-00-00__views')]
    slowest = [(s['nodeid'], s['mean_s'], s['max_s'], s['runs']) for s in agg['slowest']]
    assert slowest == [(A, 25.0, 30.0, 3), (M, 9.0, 9.0, 1), (B, 6.0, 7.0, 3), (C, 3.0, 4.0, 2)]


def test_window_changes_the_verdicts():
    """With only the newest run per target there is no history to flip."""
    agg = hs.aggregate(RUNS, 1)
    assert agg['flaky'] == []
    assert agg['newly_failing'] == []
    assert {t['slug']: t['runs'] for t in agg['targets']} == {'views': 1, 'media': 1}


def test_aggregate_tolerates_nothing_and_odd_summaries():
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
    page = hs.render_health(hs.aggregate(RUNS, 20), generated='2026-08-24T15:00:00')
    for heading in ('Targets (2)', 'Modules (2)', 'Flaky candidates (2)', 'Newly failing (1)',
                    'Slowest tests (4)'):
        assert heading in page
    assert 'href="2026-08-24_12-00-00__views/run.html"' in page
    assert '<td class="num">80%</td>' in page
    assert 'prefers-color-scheme: dark' in page
    assert 'href="index.html"' in page
    empty = hs.render_health(hs.aggregate([], 20))
    assert 'No archived runs yet' in empty


def test_format_table_is_compact():
    text = hs.format_table(hs.aggregate(RUNS, 20))
    lines = text.splitlines()
    assert lines[0].startswith('Health: newest 20 runs of each target, 5 runs')
    views = next(line for line in lines if line.startswith('tests/ui/views'))
    assert '80%' in views
    assert 'exit 1' in views
    assert f'Flaky candidates (2):\n  2/1 of 3  {A}' in text
    assert f'Newly failing (1):\n  {A}' in text
    assert 'Slowest (4):' in text


def test_cli_writes_health_html_and_links_it_from_the_index(tmp_path, capsys):
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
    assert hs.main(['--runs-dir', str(tmp_path / 'none')]) == 0
    assert 'No archived runs' in capsys.readouterr().out
    assert not (tmp_path / 'none' / 'health.html').exists()
