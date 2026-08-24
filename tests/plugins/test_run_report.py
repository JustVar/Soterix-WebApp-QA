"""Unit tests for plugins/run_report.py.

Pure-part coverage on temp folders: file-name parsing, test-to-file
matching (exact, digest-shortened, prefix, slugified), the trace digest
on a synthetic trace.zip, the three result sources and their merge, the
page's section order and evidence links, tolerance of missing files and
keys, and the CLI. No browser, no network.

Living under tests/plugins/ to be picked up by the default discovery without
needing to add a new test root or update pytest collection config.
"""
from __future__ import annotations

import hashlib
import html
import json
import re
import sys
import zipfile
from pathlib import Path

import pytest

# Ensure the repo root is importable so `plugins.run_report` resolves
# the same way pytest itself loads it during a real run.
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from plugins import run_report as rr  # noqa: E402

NODEID = 'tests/ui/views/test_views_basic.py::TestViews::test_open[chromium]'
SAFE = 'tests-ui-views-test_views_basic.py-TestViews-test_open-chromium'


def _digest(stem: str) -> str:
    return hashlib.sha256(stem.encode('utf-8')).hexdigest()[:8]


def _shorten(stem: str, keep_head: int, tail: int = 20) -> str:
    """Rebuild run_archive._fit_dest's shape: <head>-<digest>-<tail>."""
    return f'{stem[:keep_head]}-{_digest(stem)}-{stem[-tail:]}'


# ---------------------------------------------------------------------------
# Names
# ---------------------------------------------------------------------------

def test_safe_name_matches_the_report_media_sanitizer():
    assert rr._safe_name(NODEID, rr.SAFE_NAME_MAX) == SAFE
    long = 'tests/' + 'x' * 300
    assert len(rr._safe_name(long, rr.SAFE_NAME_MAX)) == 120
    assert len(rr._safe_name(long, rr.TRACE_NAME_MAX)) == 150
    assert rr._safe_name(long, 120) == re.sub(r'[^\w.-]+', '-', long).strip('-')[:120]


@pytest.mark.parametrize(('stem', 'suffix', 'label', 'index'), [
    (f'{SAFE}__PASSED', 'PASSED', None, None),
    (f'{SAFE}__FAILED', 'FAILED', None, None),
    (f'{SAFE}__SETUP_FAILED', 'SETUP_FAILED', None, None),
    (f'{SAFE}__FAILED__mid-drag-2', 'FAILED', 'mid-drag', '2'),
    (f'{SAFE}__SKIPPED__mid-drag-1', 'SKIPPED', 'mid-drag', '1'),
])
def test_parse_screenshot_name(stem, suffix, label, index):
    parsed = rr.parse_screenshot_name(stem)
    assert parsed == {'test': SAFE, 'suffix': suffix, 'label': label, 'index': index}


def test_parse_screenshot_name_rejects_unlabeled_stems():
    assert rr.parse_screenshot_name('random-image') is None
    assert rr.parse_screenshot_name(SAFE) is None


@pytest.mark.parametrize(('relpath', 'test', 'kind', 'nested'), [
    (f'{SAFE}-trace.zip', SAFE, 'trace', False),
    (f'{SAFE}-video.webm', SAFE, 'video', False),
    (f'{SAFE}-login-failure-trace.zip', SAFE, 'login-failure-trace', False),
    ('tests-ui-views-test-views-basic-py-testviews-test-open-chromium/trace.zip',
     'tests-ui-views-test-views-basic-py-testviews-test-open-chromium', 'trace', True),
    ('some-dir/video.webm', 'some-dir', 'video', True),
    ('some-dir/test-failed-1.png', 'some-dir', 'screenshot', True),
])
def test_parse_artifact_name(relpath, test, kind, nested):
    assert rr.parse_artifact_name(relpath) == {'test': test, 'kind': kind, 'nested': nested}


def test_parse_artifact_name_rejects_other_files():
    assert rr.parse_artifact_name('notes.txt') is None
    assert rr.parse_artifact_name('plain.zip') is None


# ---------------------------------------------------------------------------
# Matching
# ---------------------------------------------------------------------------

TWIN_A = 'tests/ui/c2c/test_cams.py::TestCams::test_reboot[camera-3]'
TWIN_B = 'tests/ui/c2c/test_cams.py::TestCams::test_reboot[camera-4]'


def _safes(*nodeids: str, cap: int = rr.SAFE_NAME_MAX) -> dict[str, str]:
    return {rr._safe_name(n, cap): n for n in nodeids}


def test_match_exact():
    assert rr.match_test(SAFE, _safes(NODEID, TWIN_A)) == NODEID


def test_match_digest_shortened_screenshot_tells_twins_apart():
    """Twins differ only past the cut; the recomputed digest picks the right one."""
    safes = _safes(TWIN_A, TWIN_B)
    for nodeid in (TWIN_A, TWIN_B):
        full = f'{rr._safe_name(nodeid, 120)}__PASSED'
        stem = _shorten(full, 30)
        parsed = rr.parse_screenshot_name(stem)
        assert parsed is not None
        assert rr.match_test(parsed['test'], safes,
                             lambda safe, s=parsed['suffix']: f'{safe}__{s}') == nodeid


def test_match_digest_shortened_mid_drag_frame():
    safes = _safes(NODEID)
    full = f'{SAFE}__PASSED__mid-drag-1'
    parsed = rr.parse_screenshot_name(_shorten(full, 40))
    assert parsed is not None
    assert parsed['label'] == 'mid-drag'
    frame = f"__{parsed['label']}-{parsed['index']}"
    assert rr.match_test(parsed['test'], safes,
                         lambda safe, s=parsed['suffix'], f=frame: f'{safe}__{s}{f}') == NODEID


def test_match_digest_shortened_trace():
    safes = _safes(TWIN_A, TWIN_B, cap=rr.TRACE_NAME_MAX)
    full = f'{rr._safe_name(TWIN_B, 150)}-trace'
    parsed = rr.parse_artifact_name(_shorten(full, 30) + '.zip')
    assert parsed is not None
    assert rr.match_test(parsed['test'], safes, lambda safe: f'{safe}-trace') == TWIN_B


def test_match_stale_digest_falls_back_to_head_and_tail():
    """A digest from another layout still resolves when only one test fits."""
    safes = _safes(NODEID, TWIN_A)
    stem = f'{SAFE[:30]}-00000000-{SAFE[-5:]}'
    assert rr.match_test(stem, safes, lambda safe: safe) == NODEID


def test_match_longest_common_prefix():
    safes = _safes(NODEID, TWIN_A)
    assert rr.match_test(SAFE[:40], safes) == NODEID
    assert rr.match_test(f'{SAFE}-extra-suffix', safes) == NODEID


def test_match_slugified_folder_name():
    """pytest-playwright names its per-test folder with python-slugify."""
    slug = 'tests-ui-views-test-views-basic-py-testviews-test-open-chromium'
    assert rr.match_test(slug, _safes(NODEID, TWIN_A)) == NODEID


def test_match_none_when_nothing_is_related():
    assert rr.match_test('zzz-unrelated', _safes(NODEID, TWIN_A)) is None
    assert rr.match_test('anything', {}) is None


# ---------------------------------------------------------------------------
# Trace digest
# ---------------------------------------------------------------------------

def _trace_events() -> list[dict]:
    events = [{'type': 'context-options', 'version': 8}]
    for i in range(1, 21):
        events.append({'type': 'before', 'callId': f'call@{i}', 'class': 'Frame',
                       'method': 'click', 'params': {'selector': f'#btn-{i}'}})
        events.append({'type': 'after', 'callId': f'call@{i}'})
    events.append({'type': 'frame-snapshot',
                   'snapshot': {'frameUrl': 'https://app.example/views'}})
    events.append({'type': 'before', 'callId': 'call@99', 'apiName': 'locator.click',
                   'params': {'selector': 'button.dots-menu'}})
    events.append({'type': 'log', 'callId': 'call@99', 'message': 'waiting for locator'})
    events.append({'type': 'log', 'callId': 'call@99', 'message': 'retrying click action'})
    events.append({'type': 'after', 'callId': 'call@99',
                   'error': {'message': 'Timeout 30000ms exceeded.\nCall log:', 'name': 'TimeoutError'}})
    events.append({'type': 'console', 'messageType': 'error', 'text': 'Failed to load resource'})
    events.append({'type': 'console', 'messageType': 'warning', 'text': 'not an error'})
    events.append({'type': 'event', 'method': 'console',
                   'params': {'type': 'error', 'text': 'Uncaught TypeError'}})
    return events


def _write_trace_zip(path: Path, events: list[dict] | None = None) -> Path:
    events = _trace_events() if events is None else events
    with zipfile.ZipFile(path, 'w') as zf:
        zf.writestr('trace.trace', '\n'.join(json.dumps(e) for e in events) + '\nnot json\n')
        zf.writestr('trace.network', '')
        zf.writestr('resources/page.jpeg', b'jpeg')
    return path


def test_digest_trace_reads_a_synthetic_zip(tmp_path):
    digest = rr.digest_trace(_write_trace_zip(tmp_path / 't-trace.zip'))
    assert digest['files'] == 3
    assert digest['url'] == 'https://app.example/views'
    assert digest['errors'] == ['Timeout 30000ms exceeded.']
    assert digest['console'] == ['Failed to load resource', 'Uncaught TypeError']
    # The window ends at the failing action and holds LAST_ACTIONS before it.
    assert len(digest['actions']) == rr.LAST_ACTIONS + 1
    last = digest['actions'][-1]
    assert last['name'] == 'locator.click'
    assert last['params'] == 'selector=button.dots-menu'
    assert last['error'].startswith('Timeout 30000ms')
    assert last['log'] == ['waiting for locator', 'retrying click action']
    assert digest['actions'][0]['name'] == 'Frame.click'
    assert digest['actions'][0]['log'] == []


def test_digest_trace_without_a_failure_keeps_the_last_actions(tmp_path):
    events = [e for e in _trace_events() if e.get('callId') != 'call@99']
    digest = rr.digest_trace(_write_trace_zip(tmp_path / 't-trace.zip', events))
    assert digest['errors'] == []
    assert len(digest['actions']) == rr.LAST_ACTIONS
    assert digest['actions'][-1]['params'] == 'selector=#btn-20'


def test_digest_trace_tolerates_a_bad_zip(tmp_path):
    bad = tmp_path / 'bad-trace.zip'
    bad.write_bytes(b'not a zip')
    digest = rr.digest_trace(bad)
    assert digest['actions'] == []
    assert len(digest['errors']) == 1
    assert digest['errors'][0].startswith('could not open trace')
    assert rr.digest_trace(tmp_path / 'missing.zip')['errors']


# ---------------------------------------------------------------------------
# Sources
# ---------------------------------------------------------------------------

FAILED_LOG = ('self = <TestViews object>\n\n    def test_open(self):\n>       page.click()\n'
              'E   playwright._impl._errors.TimeoutError: Locator.click: Timeout 30000ms exceeded.\n'
              'E   Call log:\n'
              "E     - waiting for locator(\"button.dots-menu\")\n"
              '\ntests/ui/views/test_views_basic.py:12: TimeoutError\n'
              '--- Captured stdout setup ---\n[AUTH] Cached session is valid\n')


def _report_html(rows: dict[str, list[dict]]) -> str:
    """A pytest-html 4 shaped report: the results live in data-jsonblob."""
    blob = {'environment': {}, 'tests': rows, 'renderCollapsed': [], 'title': 'report'}
    return ('<!doctype html><html><body><div id="data-container" data-jsonblob="'
            + html.escape(json.dumps(blob), quote=True) + '"></div></body></html>')


def _row(result: str, log: str = '', duration: str = '00:00:05') -> dict:
    return {'result': result, 'duration': duration, 'log': html.escape(log), 'extras': []}


def test_load_report_results_reads_the_jsonblob(tmp_path):
    (tmp_path / 'report.html').write_text(_report_html({
        NODEID: [_row('Failed', FAILED_LOG, '00:01:41')],
        TWIN_A: [_row('Passed')],
        TWIN_B: [_row('Rerun'), _row('Skipped')],
    }), encoding='utf-8')
    rows = rr.load_report_results(tmp_path)
    assert rows[NODEID]['outcome'] == 'failed'
    assert rows[NODEID]['duration'] == '00:01:41'
    assert 'locator("button.dots-menu")' in rows[NODEID]['log']  # unescaped twice
    assert rows[TWIN_A]['outcome'] == 'passed'
    assert rows[TWIN_B]['outcome'] == 'skipped'  # the rerun row is not a verdict


def test_load_report_results_tolerates_missing_or_odd_report(tmp_path):
    assert rr.load_report_results(tmp_path) == {}
    (tmp_path / 'report.html').write_text('<html>no blob</html>', encoding='utf-8')
    assert rr.load_report_results(tmp_path) == {}
    (tmp_path / 'report.html').write_text('<div data-jsonblob="{broken"></div>', encoding='utf-8')
    assert rr.load_report_results(tmp_path) == {}


def test_load_results_json_accepts_both_shapes(tmp_path):
    (tmp_path / 'last_run_results.json').write_text(json.dumps({
        'results': [{'nodeid': NODEID, 'outcome': 'failed'},
                    {'nodeid': TWIN_A, 'outcome': 'passed'},
                    {'nodeid': '', 'outcome': 'passed'}]}), encoding='utf-8')
    assert rr.load_results_json(tmp_path) == {NODEID: 'failed', TWIN_A: 'passed'}
    (tmp_path / 'last_run_results.json').write_text(json.dumps({NODEID: 'skipped'}),
                                                    encoding='utf-8')
    assert rr.load_results_json(tmp_path) == {NODEID: 'skipped'}
    (tmp_path / 'last_run_results.json').write_text('[]', encoding='utf-8')
    assert rr.load_results_json(tmp_path) == {}


def test_load_summary_tolerates_missing_file(tmp_path):
    assert rr.load_summary(tmp_path) == {}


# ---------------------------------------------------------------------------
# Collect + render on a synthetic run folder
# ---------------------------------------------------------------------------

def _make_run(tmp_path: Path, *, report: bool = True, results_json: bool = False) -> Path:
    run = tmp_path / '2026-08-24_10-00-00__tests-ui-views'
    (run / 'screenshots').mkdir(parents=True)
    (run / 'traces').mkdir()
    (run / 'summary.json').write_text(json.dumps({
        'started': '2026-08-24T10:00:00', 'duration_s': 101.8, 'exitstatus': 1,
        'counts': {'passed': 1, 'failed': 1, 'skipped': 1, 'errors': 0},
        'target': ['tests/ui/views'],
        'advisories': [{'test': TWIN_A, 'phase': 'call',
                        'line': '[VIEWS] view drag: mouse drag did not consume a tile'}],
    }), encoding='utf-8')
    if report:
        (run / 'report.html').write_text(_report_html({
            NODEID: [_row('Failed', FAILED_LOG, '00:01:41')],
            TWIN_A: [_row('Passed')],
            TWIN_B: [_row('Skipped')],
        }), encoding='utf-8')
    if results_json:
        (run / 'last_run_results.json').write_text(json.dumps({'results': [
            {'nodeid': NODEID, 'outcome': 'failed'},
            {'nodeid': TWIN_A, 'outcome': 'passed'},
            {'nodeid': TWIN_B, 'outcome': 'skipped'},
        ]}), encoding='utf-8')
    shots = run / 'screenshots'
    (shots / f'{SAFE}__FAILED.png').write_bytes(b'png')
    (shots / f'{SAFE}__FAILED__mid-drag-1.png').write_bytes(b'png')
    twin_full = f'{rr._safe_name(TWIN_A, 120)}__PASSED'
    (shots / f'{_shorten(twin_full, 30)}.png').write_bytes(b'png')
    (shots / f'{rr._safe_name(TWIN_B, 120)}__SKIPPED__mid-drag-1.png').write_bytes(b'png')
    _write_trace_zip(run / 'traces' / f'{SAFE}-trace.zip')
    (run / 'traces' / f'{SAFE}-video.webm').write_bytes(b'webm')
    return run


def test_collect_attaches_every_file_to_its_test(tmp_path):
    run = _make_run(tmp_path)
    tests, unattached = rr.collect_tests(run)
    assert unattached == []
    failed = tests[NODEID]
    assert failed.outcome == 'failed'
    assert failed.screenshots == [f'screenshots/{SAFE}__FAILED.png']
    assert failed.frames == [f'screenshots/{SAFE}__FAILED__mid-drag-1.png']
    assert failed.traces == [f'traces/{SAFE}-trace.zip']
    assert failed.videos == [f'traces/{SAFE}-video.webm']
    assert 'Timeout 30000ms' in failed.log
    passed = tests[TWIN_A]
    assert passed.outcome == 'passed'
    assert len(passed.screenshots) == 1
    assert '__PASSED' in passed.screenshots[0]
    assert passed.advisories == ['[VIEWS] view drag: mouse drag did not consume a tile']
    skipped = tests[TWIN_B]
    assert skipped.outcome == 'skipped'
    assert len(skipped.frames) == 1


def test_collect_falls_back_to_results_json(tmp_path):
    run = _make_run(tmp_path, report=False, results_json=True)
    tests, _ = rr.collect_tests(run)
    assert {n: t.outcome for n, t in tests.items()} == {
        NODEID: 'failed', TWIN_A: 'passed', TWIN_B: 'skipped'}
    assert tests[NODEID].log == ''


def test_collect_derives_tests_from_file_names_alone(tmp_path):
    """Neither report.html nor results JSON: the names are the witnesses."""
    run = _make_run(tmp_path, report=False)
    (run / 'summary.json').unlink()
    tests, _ = rr.collect_tests(run)
    assert tests[SAFE].outcome == 'failed'
    assert tests[SAFE].traces == [f'traces/{SAFE}-trace.zip']
    assert tests[SAFE].videos == [f'traces/{SAFE}-video.webm']
    outcomes = sorted(t.outcome for t in tests.values())
    assert outcomes == ['failed', 'passed', 'skipped']


def test_collect_keeps_the_worse_outcome_and_lists_strays(tmp_path):
    run = _make_run(tmp_path)
    # report.html says passed, but a kept trace says the test failed.
    _write_trace_zip(run / 'traces' / f'{rr._safe_name(TWIN_A, 150)}-trace.zip')
    (run / 'screenshots' / 'stray.png').write_bytes(b'png')
    (run / 'traces' / 'notes.txt').write_text('x', encoding='utf-8')
    tests, unattached = rr.collect_tests(run)
    assert tests[TWIN_A].outcome == 'failed'
    assert unattached == ['screenshots/stray.png']


def test_build_run_report_orders_sections_and_links_evidence(tmp_path):
    run = _make_run(tmp_path)
    page = rr.build_run_report(run)
    # Failures first, then advisories, passed, skipped.
    assert (page.index('id="failures"') < page.index('id="advisories"')
            < page.index('id="passed"') < page.index('id="skipped"'))
    assert 'Failures (1)' in page
    # Header facts and links.
    for fact in ('tests/ui/views', '101.8', 'report.html', '../index.html'):
        assert fact in page
    for key, value in (('passed', '1'), ('failed', '1'), ('skipped', '1'), ('errors', '0')):
        assert f'class="chip {key}">{key}: {value}</span>' in page
    # The failure card: message, call log, actions, console, evidence.
    card = page[page.index('<div class="card failed"'):page.index('id="advisories"')]
    assert 'Locator.click: Timeout 30000ms exceeded.' in card
    assert 'waiting for locator' in card
    for fact in ('class="failing"', 'locator.click', 'Console errors (2)', 'Uncaught TypeError'):
        assert fact in card
    assert f'src="screenshots/{SAFE}__FAILED.png"' in card
    assert f'src="screenshots/{SAFE}__FAILED__mid-drag-1.png"' in card
    assert f'<video controls preload="metadata" src="traces/{SAFE}-video.webm">' in card
    assert f'href="traces/{SAFE}-trace.zip"' in card
    assert 'python -m playwright show-trace "' in card
    assert str(run / 'traces' / f'{SAFE}-trace.zip') in card.replace('&#x27;', "'")
    assert 'Full traceback and captured output' in card
    # Advisories carry the test and the line.
    assert '[VIEWS] view drag: mouse drag did not consume a tile' in page
    # Passed and skipped are collapsed lists with thumbnails.
    assert '<summary>Passed (1)</summary>' in page
    assert '<summary>Skipped (1)</summary>' in page
    assert page.count('<img ') == 4
    assert 'prefers-color-scheme: dark' in page


def test_build_run_report_survives_an_empty_folder(tmp_path):
    run = tmp_path / '2026-08-24_10-00-00__all'
    run.mkdir()
    page = rr.build_run_report(run)
    assert 'Failures (0)' in page
    assert 'No failures in this run.' in page
    assert 'Duration: - s' in page
    assert 'Exit status: -' in page
    assert '<summary>Passed (0)</summary>' in page
    assert 'all' in page  # the target from the folder name


def test_build_run_report_escapes_test_names(tmp_path):
    run = _make_run(tmp_path)
    (run / 'report.html').write_text(_report_html({
        'tests/x.py::test_a[<b>bold</b>]': [_row('Failed', 'E   assert 1 == 2')]}),
        encoding='utf-8')
    page = rr.build_run_report(run)
    assert '<b>bold</b>' not in page
    assert '&lt;b&gt;bold&lt;/b&gt;' in page


def test_failure_card_without_trace_or_video_says_so(tmp_path):
    run = _make_run(tmp_path)
    (run / 'traces' / f'{SAFE}-trace.zip').unlink()
    (run / 'traces' / f'{SAFE}-video.webm').unlink()
    page = rr.build_run_report(run)
    assert 'No trace kept for this test.' in page
    assert 'No video kept for this test.' in page
    assert 'show-trace' not in page


def test_headline_takes_the_first_error_block():
    assert rr._headline(FAILED_LOG).splitlines()[0] == (
        'playwright._impl._errors.TimeoutError: Locator.click: Timeout 30000ms exceeded.')
    assert rr._headline('no error lines') == ''


# ---------------------------------------------------------------------------
# Titles, modules, change chips
# ---------------------------------------------------------------------------

def test_readable_title_takes_the_docstring_first_line():
    doc = '\n    Verify the view opens.\n\n    Longer text nobody needs in a list.\n    '
    assert rr.readable_title(NODEID, doc) == 'Verify the view opens.'


@pytest.mark.parametrize(('nodeid', 'title'), [
    (NODEID, 'Open'),
    ('tests/ui/x.py::test_drag_camera_to_tile', 'Drag camera to tile'),
    ('tests/ui/x.py::TestA::test_open_my_views[chromium-site-3]', 'Open my views'),
    ('tests/ui/x.py::testSomething', 'Something'),
])
def test_readable_title_falls_back_to_the_function_name(nodeid, title):
    assert rr.readable_title(nodeid) == title
    assert rr.readable_title(nodeid, '   \n\n') == title  # a blank docstring is no title


def test_module_of_is_the_path_under_tests():
    assert rr.module_of(NODEID) == 'ui/views/test_views_basic.py'
    assert rr.module_of('tests\\ui\\x.py::test_a') == 'ui/x.py'
    assert rr.module_of('other/y.py::test_b') == 'other/y.py'
    assert rr.module_of(SAFE) == SAFE  # a file-name stand-in has no path to strip


def test_format_seconds():
    assert rr.format_seconds(12.34) == '12.3 s'
    assert rr.format_seconds(0) == '0.0 s'
    assert rr.format_seconds(101.8) == '1 min 42 s'


def test_compute_deltas_labels_every_change():
    previous = {'a': 'passed', 'b': 'failed', 'c': 'failed', 'd': 'skipped',
                'e': 'passed', 'f': 'error', 'h': 'skipped'}
    current = {'a': 'failed', 'b': 'passed', 'c': 'error', 'd': 'failed',
               'e': 'passed', 'f': 'skipped', 'g': 'passed', 'h': 'passed'}
    assert rr.compute_deltas(current, previous) == {
        'a': 'new failure', 'b': 'fixed', 'c': 'still failing',
        'd': 'new failure', 'g': 'new test'}


def test_compute_deltas_without_a_previous_run():
    assert rr.compute_deltas({'a': 'failed'}, None) == {}
    assert rr.compute_deltas({}, {'a': 'failed'}) == {}


def test_find_previous_run_wants_the_same_slug_and_an_earlier_start(tmp_path):
    for name in ('2026-08-01_10-00-00__views', '2026-08-02_10-00-00__views',
                 '2026-08-03_10-00-00__views', '2026-08-02_12-00-00__media', 'notes'):
        (tmp_path / name).mkdir()
    (tmp_path / '2026-08-02_11-00-00__views').write_text('a file, not a run', encoding='utf-8')
    assert rr.find_previous_run(tmp_path / '2026-08-03_10-00-00__views') == \
        tmp_path / '2026-08-02_10-00-00__views'
    assert rr.find_previous_run(tmp_path / '2026-08-01_10-00-00__views') is None
    assert rr.find_previous_run(tmp_path / '2026-08-02_12-00-00__media') is None
    assert rr.find_previous_run(tmp_path / 'notes') is None
    assert rr.find_previous_run(tmp_path / 'missing' / '2026-08-03_10-00-00__views') is None


def test_load_previous_outcomes_prefers_the_summary_records(tmp_path):
    prev = tmp_path / '2026-08-01_10-00-00__views'
    prev.mkdir()
    (prev / 'summary.json').write_text(json.dumps({'tests': [
        {'nodeid': NODEID, 'outcome': 'failed'}, {'nodeid': TWIN_A, 'outcome': 'passed'}]}),
        encoding='utf-8')
    assert rr.load_previous_outcomes(prev) == {NODEID: 'failed', TWIN_A: 'passed'}
    # An older archive without records still answers from its report.
    (prev / 'summary.json').unlink()
    (prev / 'report.html').write_text(_report_html({TWIN_B: [_row('Passed')]}), encoding='utf-8')
    assert rr.load_previous_outcomes(prev) == {TWIN_B: 'passed'}
    assert rr.load_previous_outcomes(tmp_path / 'empty') == {}


def test_summary_tests_tolerates_odd_shapes():
    assert rr.summary_tests({}) == []
    assert rr.summary_tests({'tests': 'nope'}) == []
    assert rr.summary_tests({'tests': [{'nodeid': 'a'}, {'x': 1}, 'str', {'nodeid': ''}]}) == \
        [{'nodeid': 'a'}]


def _summary_test_rows() -> list[dict]:
    """summary.json "tests" rows as run_archive writes them."""
    return [
        {'nodeid': NODEID, 'module': 'ui/views/test_views_basic.py',
         'title': 'Verify the view opens.', 'case_key': 'VK1', 'case_title': 'Open a view',
         'outcome': 'failed', 'duration_s': 101.2, 'phases': {'setup': 1.2, 'call': 100.0},
         'log_file': f'log/{SAFE}.log'},
        {'nodeid': TWIN_A, 'module': 'ui/c2c/test_cams.py', 'title': 'Reboot a camera',
         'case_key': None, 'case_title': None, 'outcome': 'passed', 'duration_s': 7.5,
         'phases': {'call': 7.5}, 'log_file': None},
        {'nodeid': TWIN_B, 'module': 'ui/c2c/test_cams.py', 'title': 'Reboot a camera',
         'case_key': None, 'case_title': None, 'outcome': 'skipped', 'duration_s': 0.4,
         'phases': {'setup': 0.4}, 'log_file': None},
    ]


def _add_summary_tests(run: Path, rows: list[dict], provenance: dict | None = None) -> None:
    summary = json.loads((run / 'summary.json').read_text(encoding='utf-8'))
    summary['tests'] = rows
    if provenance:
        summary['provenance'] = provenance
    (run / 'summary.json').write_text(json.dumps(summary), encoding='utf-8')


def test_build_run_report_shows_titles_facts_and_change_chips(tmp_path):
    run = _make_run(tmp_path)
    _add_summary_tests(run, _summary_test_rows(), {
        'env': 'qa', 'base_url_host': 'app.example.com', 'git_commit': 'abc1234',
        'playwright': '1.62.0', 'pytest_playwright': '0.9.0',
        'browser': 'chromium', 'browser_channel': 'chrome'})
    # The previous run of this target: NODEID passed, TWIN_A failed, TWIN_B absent.
    prev = tmp_path / '2026-08-23_10-00-00__tests-ui-views'
    prev.mkdir()
    (prev / 'summary.json').write_text(json.dumps({'tests': [
        {'nodeid': NODEID, 'outcome': 'passed'}, {'nodeid': TWIN_A, 'outcome': 'failed'}]}),
        encoding='utf-8')
    page = rr.build_run_report(run)

    card = page[page.index('<div class="card failed"'):page.index('id="advisories"')]
    # Title first, QA Touch case second, node id beneath; never a renamed test.
    assert (card.index('Verify the view opens.') < card.index('QA Touch VK1: Open a view')
            < card.index(f'<div class="nodeid">{NODEID}</div>'))
    assert '<span class="chip delta new-failure">new failure</span>' in card
    assert '1 min 41 s' in card
    assert f'href="log/{SAFE}.log"' in card
    key = re.search(r'<div class="card failed"[^>]*data-test="([^"]*)"', page).group(1)
    assert 'verify the view opens.' in key
    assert NODEID.lower() in key
    assert 'vk1' in key
    # The passed twin was fixed; the skipped twin is new.
    assert 'chip delta fixed">fixed<' in page
    assert 'chip delta new-test">new test<' in page
    assert '<h4 class="module">ui/c2c/test_cams.py (1)</h4>' in page
    # Header provenance and the compared-against link.
    for fact in ('ENV: <code>qa</code>', 'app.example.com', 'abc1234', 'chromium / chrome',
                 'playwright 1.62.0, pytest-playwright 0.9.0'):
        assert fact in page
    assert '2026-08-23_10-00-00__tests-ui-views/run.html' in page
    # Slowest sits between advisories and passed, longest first.
    assert page.index('id="advisories"') < page.index('id="slowest"') < page.index('id="passed"')
    slow = page[page.index('id="slowest"'):page.index('id="passed"')]
    assert slow.index('1 min 41 s') < slow.index('7.5 s') < slow.index('0.4 s')
    # The filter box and its script ship with the page.
    assert 'id="filter"' in page
    assert "getElementById('filter')" in page


def test_build_run_report_without_a_previous_run_has_no_chips(tmp_path):
    run = _make_run(tmp_path)
    _add_summary_tests(run, _summary_test_rows())
    page = rr.build_run_report(run)
    assert 'chip delta' not in page
    assert 'No earlier run of this target to compare with.' in page


def test_build_run_report_falls_back_on_an_older_archive(tmp_path):
    """No "tests" records: titles come from the node ids, timing from
    pytest-html, and the slowest block says why it is empty."""
    run = _make_run(tmp_path)
    page = rr.build_run_report(run)
    assert '<h3 class="title">Open</h3>' in page
    assert 'No per-test timing in this run.' in page
    assert '00:01:41' in page


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def test_cli_writes_run_html(tmp_path, capsys):
    run = _make_run(tmp_path)
    assert rr.main([str(run)]) == 0
    assert (run / 'run.html').is_file()
    assert str(run / 'run.html') in capsys.readouterr().out


def test_cli_latest_picks_the_newest_run(tmp_path, monkeypatch):
    from plugins import run_archive as ra
    runs = tmp_path / 'runs'
    for name in ('2026-08-01_10-00-00__a', '2026-08-03_10-00-00__c', 'index.html-not-a-run'):
        (runs / name).mkdir(parents=True)
    monkeypatch.setattr(ra, 'RUNS_DIR', runs)
    assert rr.main(['latest']) == 0
    assert (runs / '2026-08-03_10-00-00__c' / 'run.html').is_file()
    assert not (runs / '2026-08-01_10-00-00__a' / 'run.html').exists()


def test_cli_rejects_missing_folder_and_bad_usage(tmp_path, capsys):
    assert rr.main([str(tmp_path / 'nope')]) == 1
    assert 'No run folder' in capsys.readouterr().err
    assert rr.main([]) == 2
    assert rr.main(['a', 'b']) == 2
