"""Unit tests for plugins/run_archive.py.

Pure-helper coverage plus the screenshot copy's gates (run on temp folders):
slug building, collision suffixing, prune selection, path-cap truncation,
the summary shape, index rendering, outcome classification, the guard
decisions, and the run.html hand-off to run_report. The full end-to-end
archive needs a finished pytest session with real report files, so it is
exercised by real runs, not here.

Living under tests/plugins/ to be picked up by the default discovery without
needing to add a new test root or update pytest collection config. The tests
do not require playwright, a browser, or network.
"""
from __future__ import annotations

import json
import logging
import os
import re
import sys
from pathlib import Path

import pytest

# Ensure the repo root is importable so `plugins.run_archive` resolves
# the same way pytest itself loads it during a real run.
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from plugins import run_archive as ra  # noqa: E402

# ---------------------------------------------------------------------------
# Slug building + cap
# ---------------------------------------------------------------------------

def test_slug_flattens_path_separators():
    """Path separators in a target flatten to dashes in the run slug."""
    assert ra._build_slug(['tests/ui/views']) == 'tests-ui-views'


def test_slug_joins_multiple_targets():
    """Several targets join into one dash-separated slug."""
    assert ra._build_slug(['tests/ui/media', 'tests/ui/maps']) == \
        'tests-ui-media-tests-ui-maps'


def test_slug_appends_the_markexpr():
    """The -m expression rides on the end of the run slug."""
    assert ra._build_slug(['tests/ui'], 'smoke and not slow') == \
        'tests-ui-smoke-and-not-slow'


def test_slug_empty_invocation_becomes_all():
    """A bare invocation with no target or markexpr is slugged as 'all'."""
    assert ra._build_slug([]) == 'all'
    assert ra._build_slug([], '') == 'all'


def test_slug_all_junk_becomes_all():
    """A target that sanitizes away entirely must still name a folder."""
    assert ra._build_slug(['///']) == 'all'


def test_slug_caps_at_40():
    """The run slug is cut at 40 characters."""
    assert len(ra._build_slug(['x' * 200])) == 40
    assert ra.SLUG_MAX == 40


def test_slug_matches_the_report_media_sanitizer():
    """Run folders and the files inside them follow one naming convention."""
    raw = 'tests/ui/views/test_views_basic.py::TestViews'
    expected = re.sub(r'[^\w.-]+', '-', raw).strip('-')[:40]
    assert ra._build_slug([raw]) == expected


# ---------------------------------------------------------------------------
# Collision suffixing
# ---------------------------------------------------------------------------

def test_unique_dir_returns_the_base_name_when_free(tmp_path):
    """A free run folder name is used as is, with no suffix."""
    assert ra._unique_dir(tmp_path, 'run') == tmp_path / 'run'


def test_unique_dir_appends_2_then_3(tmp_path):
    """A taken run folder name gets -2, then -3, on collision."""
    (tmp_path / 'run').mkdir()
    assert ra._unique_dir(tmp_path, 'run') == tmp_path / 'run-2'
    (tmp_path / 'run-2').mkdir()
    assert ra._unique_dir(tmp_path, 'run') == tmp_path / 'run-3'


# ---------------------------------------------------------------------------
# Prune selection (pure: given names, pick what goes)
# ---------------------------------------------------------------------------

def _run_name(i: int) -> str:
    return f'2026-08-{i:02d}_10-00-00__all'


def test_prune_keeps_the_newest_20():
    """Pruning keeps the newest 20 runs and lists the oldest first to go."""
    names = [_run_name(i) for i in range(1, 26)]  # 25 runs, day 25 newest
    prunable = ra._select_prunable(names)
    assert prunable == [_run_name(i) for i in range(5, 0, -1)]
    assert ra.KEEP_RUNS == 20


def test_prune_nothing_at_or_under_the_cap():
    """At or under the cap, nothing is pruned."""
    assert ra._select_prunable([_run_name(i) for i in range(1, 21)]) == []
    assert ra._select_prunable([]) == []


def test_prune_ignores_non_run_names():
    """index.html and hand-made folders must never be candidates."""
    names = ['index.html', 'keep-me', '2026-08-01_10-00', 'notes.txt',
             *[_run_name(i) for i in range(1, 25)]]
    prunable = ra._select_prunable(names)
    assert prunable == [_run_name(i) for i in range(4, 0, -1)]


def test_prune_pattern_requires_the_double_underscore():
    """Only names with the double underscore before the slug count as runs."""
    assert ra.RUN_DIR_RE.match('2026-08-01_10-00-00__views')
    assert not ra.RUN_DIR_RE.match('2026-08-01_10-00-00')
    assert not ra.RUN_DIR_RE.match('2026-08-01_10-00-00_views')


def test_prune_counts_per_target():
    """A morning of debug iterations on one file must never evict the last
    full-suite archive - only older runs of the same target."""
    suite = '2026-08-01_22-00-00__tests'
    debug = [f'2026-08-{i:02d}_10-00-00__tests-ui-views' for i in range(2, 27)]
    prunable = ra._select_prunable([suite, *debug])
    assert suite not in prunable
    # The debug slug is over its own cap of 20; its 5 oldest runs go.
    assert prunable == sorted(debug)[4::-1]


def test_prune_total_cap_spans_targets():
    """One-off targets each stay under their own cap forever - the total
    cap is what keeps them from accumulating without bound."""
    names = [f'2026-08-{i:02d}_10-00-00__t{i}' for i in range(1, 8)]
    prunable = ra._select_prunable(names, keep=20, total=5)
    assert prunable == [names[1], names[0]]
    assert ra.KEEP_RUNS_TOTAL == 100


# ---------------------------------------------------------------------------
# Path-cap truncation
# ---------------------------------------------------------------------------

def test_fit_dest_passes_short_paths_through(tmp_path):
    """A destination path under the cap is returned untouched."""
    dest = tmp_path / 'traces' / 'short-trace.zip'
    assert ra._fit_dest(dest) is dest


def test_fit_dest_truncates_the_stem_to_fit(tmp_path):
    """An overlong destination is cut to the cap, keeping folder and suffix."""
    dest = tmp_path / ('t' * 300 + '.zip')
    fitted = ra._fit_dest(dest)
    assert fitted is not None
    assert len(str(fitted)) == 250
    assert fitted.suffix == '.zip'
    assert str(fitted.parent) == str(tmp_path)


def test_fit_dest_none_when_the_directory_alone_is_too_long(tmp_path):
    """No destination fits when the folder alone is past the path cap."""
    deep = tmp_path / ('d' * 300)
    assert ra._fit_dest(deep / 'f.zip') is None


def test_fit_dest_keeps_distinct_sources_distinct(tmp_path):
    """Names that differ only in the middle must not fit to one destination -
    the later copy would silently overwrite the earlier one's evidence."""
    limit = len(str(tmp_path)) + 1 + 40 + len('.zip')  # stem room of 40
    twins = [ra._fit_dest(tmp_path / f'{"h" * 30}cam-{i}{"t" * 30}.zip', limit)
             for i in (3, 4)]
    assert twins[0] is not None
    assert twins[1] is not None
    assert twins[0].name != twins[1].name
    for fitted in twins:
        assert len(str(fitted)) <= limit


def test_fit_dest_keeps_the_stem_tail(tmp_path):
    """The tail is what tells near-twins apart to a human - the camera id,
    the PASSED/FAILED label - so the cut must not eat it."""
    fitted = ra._fit_dest(tmp_path / ('x' * 290 + '__FAILED.png'))
    assert fitted is not None
    assert fitted.name.endswith('__FAILED.png')


# ---------------------------------------------------------------------------
# Screenshot copy gates (freshness + path cap)
# ---------------------------------------------------------------------------

def test_copy_screenshots_skips_images_older_than_the_session(tmp_path, monkeypatch):
    """REPORT_SCREENSHOTS=off skips report_media's session-start wipe, so a
    prior run's images can still sit in the folder - mtime keeps them out."""
    src = tmp_path / 'shots'
    src.mkdir()
    stale = src / 'old__FAILED.png'
    stale.write_bytes(b'old')
    os.utime(stale, (1_000, 1_000))
    fresh = src / 'new__FAILED.png'
    fresh.write_bytes(b'new')
    os.utime(fresh, (2_000, 2_000))
    monkeypatch.setattr(ra, 'SCREENSHOT_DIR', src)

    dest = tmp_path / 'run'
    ra._copy_screenshots(1_500.0, dest)
    assert (dest / 'screenshots' / 'new__FAILED.png').is_file()
    assert not (dest / 'screenshots' / 'old__FAILED.png').exists()


def test_copy_screenshots_caps_the_destination_path(tmp_path, monkeypatch):
    """Long screenshot names under a long run folder must be shortened, not
    lost - default Windows refuses paths past 260 chars."""
    src = tmp_path / 'shots'
    src.mkdir()
    dest = tmp_path / 'run'
    # Sized to fit in the source folder but exceed the cap in the archive.
    room = ra.DEST_PATH_MAX - len(str(dest / 'screenshots')) - 1
    long_name = 'p' * (room + 10) + '.png'
    (src / long_name).write_bytes(b'png')
    monkeypatch.setattr(ra, 'SCREENSHOT_DIR', src)

    ra._copy_screenshots(0.0, dest)
    copied = list((dest / 'screenshots').glob('*.png'))
    assert len(copied) == 1
    assert copied[0].name != long_name
    # Same normalization as _fit_dest: resolve() would expand 8.3 short
    # names and measure a different string than the one that was capped.
    assert len(os.path.abspath(copied[0])) <= ra.DEST_PATH_MAX


# ---------------------------------------------------------------------------
# Summary shape
# ---------------------------------------------------------------------------

def test_summary_shape():
    """The summary carries exactly the schema-2 keys with the run's facts."""
    counts = {'passed': 3, 'failed': 1, 'skipped': 2, 'errors': 0}
    summary = ra._build_summary(started=1000.0, ended=1090.5, exitstatus=1,
                                counts=counts, target=['tests/ui/views'],
                                markexpr='smoke', keyword='',
                                report_file='report.html')
    assert set(summary) == {'schema_version', 'started', 'ended', 'duration_s',
                            'exitstatus', 'counts', 'target', 'markexpr',
                            'keyword', 'report_file', 'advisories', 'tests',
                            'provenance'}
    assert summary['schema_version'] == 2
    assert summary['tests'] == []
    assert summary['provenance'] == {}
    assert summary['duration_s'] == 90.5
    assert summary['exitstatus'] == 1
    assert summary['counts'] == counts
    assert summary['target'] == ['tests/ui/views']
    assert summary['markexpr'] == 'smoke'
    assert summary['keyword'] == ''
    assert summary['report_file'] == 'report.html'


def test_summary_counts_are_a_copy_with_fixed_keys():
    """The archive snapshot must not alias live state, and a sparse counts
    dict still yields every key the index renders."""
    counts = {'passed': 5}
    summary = ra._build_summary(started=0.0, ended=1.0, exitstatus=0,
                                counts=counts, target=[], markexpr='',
                                keyword='', report_file=None)
    assert summary['counts'] == {'passed': 5, 'failed': 0, 'skipped': 0, 'errors': 0}
    counts['passed'] = 99
    assert summary['counts']['passed'] == 5
    assert summary['report_file'] is None


# ---------------------------------------------------------------------------
# Index rendering (order + tolerated missing keys)
# ---------------------------------------------------------------------------

def _entry(name, summary=None, has_report=False):
    return {'name': name, 'summary': summary or {}, 'has_report': has_report}


def test_index_orders_newest_first():
    """The index lists runs newest first regardless of input order."""
    html = ra._render_index([
        _entry('2026-08-01_10-00-00__old'),
        _entry('2026-08-03_10-00-00__new'),
        _entry('2026-08-02_10-00-00__mid'),
    ])
    assert html.index('__new') < html.index('__mid') < html.index('__old')


def test_index_links_report_only_when_present():
    """The index links report.html only for runs that have one; the folder always."""
    html = ra._render_index([
        _entry('2026-08-01_10-00-00__a', has_report=True),
        _entry('2026-08-02_10-00-00__b', has_report=False),
    ])
    assert '2026-08-01_10-00-00__a/report.html' in html
    assert '2026-08-02_10-00-00__b/report.html' not in html
    # The folder link is always there - traces have no report to link.
    assert '2026-08-02_10-00-00__b/' in html


def test_index_links_the_run_report_first_when_present():
    """run.html is where a reader starts, so its link leads the Open cell."""
    html = ra._render_index([
        {'name': '2026-08-01_10-00-00__a', 'summary': {}, 'has_report': True,
         'has_run_report': True},
        {'name': '2026-08-02_10-00-00__b', 'summary': {}, 'has_report': True},
    ])
    cell_a = html[html.index('2026-08-01_10-00-00__a/run.html'):]
    assert cell_a.index('run report') < cell_a.index('>report<') < cell_a.index('folder')
    assert '2026-08-02_10-00-00__b/run.html' not in html


def test_load_entries_flags_the_run_report(tmp_path):
    """Loaded entries flag whether the run folder holds a run.html."""
    (tmp_path / '2026-08-01_10-00-00__a').mkdir()
    (tmp_path / '2026-08-01_10-00-00__a' / 'run.html').write_text('x', encoding='utf-8')
    (tmp_path / '2026-08-02_10-00-00__b').mkdir()
    flags = {e['name']: e['has_run_report'] for e in ra._load_entries(tmp_path)}
    assert flags == {'2026-08-01_10-00-00__a': True, '2026-08-02_10-00-00__b': False}


def test_index_tolerates_an_empty_summary():
    """A folder from an older layout (no summary.json) still gets a row
    built from its name alone."""
    html = ra._render_index([_entry('2026-08-01_10-00-00__views')])
    assert '2026-08-01 10-00-00' in html  # timestamp from the folder name
    assert 'views' in html                # target from the folder name
    assert '<td>-</td>' in html           # unknown counts render as '-'


def test_index_renders_summary_values():
    """The index shows the summary's start time, target, and counts."""
    summary = {'started': '2026-08-01T10:00:00', 'exitstatus': 0,
               'counts': {'passed': 7, 'failed': 1, 'skipped': 2, 'errors': 0},
               'target': ['tests/ui/media']}
    html = ra._render_index([_entry('2026-08-01_10-00-00__media', summary)])
    assert '2026-08-01T10:00:00' in html
    assert 'tests/ui/media' in html
    for cell in ('<td>7</td>', '<td>1</td>', '<td>2</td>', '<td>0</td>'):
        assert cell in html


def test_index_has_a_caption_and_survives_no_runs():
    """An empty archive still renders the caption and a no-runs notice."""
    html = ra._render_index([])
    assert 'newest first' in html
    assert 'No archived runs' in html


# ---------------------------------------------------------------------------
# Outcome classification (summary counters)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(('when', 'outcome', 'counter'), [
    ('call', 'passed', 'passed'),
    ('call', 'failed', 'failed'),
    ('call', 'skipped', 'skipped'),
    ('setup', 'failed', 'errors'),    # a setup crash is an error, not a failure
    ('setup', 'skipped', 'skipped'),
])
def test_classify_counted_phases(when, outcome, counter):
    """Call outcomes and setup failures land in the matching counter."""
    assert ra._classify(when, outcome) == counter


@pytest.mark.parametrize(('when', 'outcome'), [
    ('setup', 'passed'),      # setup success is not a result yet
    ('teardown', 'failed'),   # teardown reports never represent the test
    ('teardown', 'passed'),
    ('call', 'rerun'),        # rerun outcomes are not final
])
def test_classify_ignored_phases(when, outcome):
    """Setup passes, teardown reports, and reruns count toward nothing."""
    assert ra._classify(when, outcome) is None


# ---------------------------------------------------------------------------
# Kill switch
# ---------------------------------------------------------------------------

@pytest.mark.parametrize('value', ['off', 'OFF', 'Off', '0', 'false', 'no', ' off '])
def test_kill_switch_off_values(value):
    """RUN_ARCHIVE=off, in any spelling, disables the archive."""
    assert ra._archive_disabled({'RUN_ARCHIVE': value}) is True


@pytest.mark.parametrize('value', ['', 'on', '1', 'true', 'anything-else'])
def test_kill_switch_on_values(value):
    """Any RUN_ARCHIVE value other than an off word leaves the archive on."""
    assert ra._archive_disabled({'RUN_ARCHIVE': value}) is False


def test_kill_switch_defaults_to_on():
    """With RUN_ARCHIVE unset, the archive is on."""
    assert ra._archive_disabled({}) is False


# ---------------------------------------------------------------------------
# Archive guard decisions
# ---------------------------------------------------------------------------

class _FakeConfig:
    """Just enough of pytest Config for the guard and the archive: getoption
    plus the invocation targets in `args`."""

    def __init__(self, collect_only=False, args=('tests/ui',), htmlpath=None):
        self._collect_only = collect_only
        self.args = list(args)
        self._htmlpath = htmlpath

    def getoption(self, name, default=None):
        if name == '--collect-only':
            return self._collect_only
        if name == 'htmlpath':
            return self._htmlpath
        return default


def test_should_archive_in_a_plain_run():
    """A plain run with tests executed is archived."""
    assert ra._should_archive(_FakeConfig(), {}, tests_run=5) is True


def test_should_not_archive_during_collect_only():
    """run_suite's planning pass must never bury the real run's archive."""
    assert ra._should_archive(_FakeConfig(collect_only=True), {}, tests_run=5) is False


def test_should_not_archive_in_xdist_worker():
    """An xdist worker never archives; the controller does."""
    env = {'PYTEST_XDIST_WORKER': 'gw0'}
    assert ra._should_archive(_FakeConfig(), env, tests_run=5) is False


def test_should_not_archive_when_zero_tests_ran():
    """A run that executed no tests is not archived."""
    assert ra._should_archive(_FakeConfig(), {}, tests_run=0) is False


def test_should_not_archive_when_every_guard_trips():
    """Collect-only, an xdist worker, and zero tests together still refuse."""
    env = {'PYTEST_XDIST_WORKER': 'gw1'}
    assert ra._should_archive(_FakeConfig(collect_only=True), env, tests_run=0) is False


@pytest.mark.parametrize('args', [
    ['tests/plugins'],
    ['tests/tools'],
    ['tests/plugins', 'tests/tools'],
    ['tests/plugins/test_run_archive.py::test_slug_caps_at_40'],
    ['tests\\plugins\\test_run_archive.py'],
    ['tests/plugins/'],
    ['C:/repo/tests/tools/test_qatouch_client.py'],
])
def test_should_not_archive_a_unit_test_only_run(args):
    """The repo's own unit tests leave no UI evidence; a folder per plugin
    test run would bury the suite runs the archive exists for."""
    assert ra._unit_tests_only(args) is True
    assert ra._should_archive(_FakeConfig(args=args), {}, tests_run=40) is False


@pytest.mark.parametrize('args', [
    [],                                   # bare pytest: the whole suite
    ['tests'],
    ['tests/ui/views'],
    ['tests/plugins', 'tests/ui/views'],  # one UI target keeps the archive
    ['tests/ui/plugins_page/test_x.py'],  # a UI folder that merely contains the word
])
def test_should_archive_when_any_target_is_not_a_unit_test(args):
    """One UI target in the invocation is enough to keep the archive."""
    assert ra._unit_tests_only(args) is False
    assert ra._should_archive(_FakeConfig(args=args), {}, tests_run=5) is True


# ---------------------------------------------------------------- run.html hand-off

def _archive_on_temp(tmp_path, monkeypatch):
    """Point every live path at the temp folder and archive one fake run."""
    monkeypatch.setattr(ra, 'RUNS_DIR', tmp_path / 'runs')
    monkeypatch.setattr(ra, 'SCREENSHOT_DIR', tmp_path / 'shots')
    monkeypatch.setattr(ra, 'TRACE_DIR', tmp_path / 'artifacts')
    monkeypatch.setattr(ra, 'RESULTS_JSON', tmp_path / 'none.json')
    (tmp_path / 'shots').mkdir()
    (tmp_path / 'shots' / 't-x.py-test_a-chromium__FAILED.png').write_bytes(b'png')
    state = ra._RunState()
    state.started = 1_700_000_000.0
    state.ended = state.started + 12.5
    state.exitstatus = 1
    state.counts['failed'] = 1
    state.advisories = [{'test': 't/x.py::test_a[chromium]', 'phase': 'call',
                         'line': '[LPR] play_camera: drag landed nothing'}]
    ra._archive_run(_FakeConfig(args=['t/x.py']), state)
    folders = [p for p in (tmp_path / 'runs').iterdir() if p.is_dir()]
    assert len(folders) == 1
    return folders[0]


def test_archive_writes_the_run_report(tmp_path, monkeypatch):
    """The archive writes run.html with failures, screenshots, and advisories."""
    dest = _archive_on_temp(tmp_path, monkeypatch)
    page = (dest / 'run.html').read_text(encoding='utf-8')
    assert (dest / 'summary.json').is_file()
    assert (dest / 'advisories.txt').is_file()
    assert 'Failures (1)' in page
    assert 'screenshots/t-x.py-test_a-chromium__FAILED.png' in page
    assert '[LPR] play_camera: drag landed nothing' in page


def test_archive_survives_a_report_builder_failure(tmp_path, monkeypatch):
    """A page that cannot be built costs the page, never the copies."""
    def boom(run_dir):
        raise RuntimeError('builder down')
    monkeypatch.setattr(ra, 'build_run_report', boom)
    dest = _archive_on_temp(tmp_path, monkeypatch)
    assert (dest / 'summary.json').is_file()
    assert (dest / 'screenshots' / 't-x.py-test_a-chromium__FAILED.png').is_file()
    assert not (dest / 'run.html').exists()


# ---------------------------------------------------------------- advisories

class TestAdvisories:
    """The [VIEWS]/[LPR]/[EXPORT] marker lines ride into the archive."""

    CAPTURED = (
        "[AUTH] Loading cached session from .auth_state.json\n"
        "DEBUG expand_site_and_show_cameras: Clicked devices subtab\n"
        "[VIEWS] view drag: mouse drag did not consume a tile; trying JS fallback\n"
        "[VIEWS] view drag: mouse drag did not consume a tile; trying JS fallback\n"
        "  [EXPORT] completed in 14s (progress bar hidden)\n"
        "[LPR] play_camera: drag landed nothing\n"
        "[TRACE] Saved failure trace to reports/artifacts/x-trace.zip\n"
        "[VIEWS]\n"
    )

    def test_scan_keeps_only_tagged_lines_in_order(self):
        """Only tagged lines with text survive the advisory scan, in order."""
        assert ra.scan_advisories(self.CAPTURED) == [
            "[VIEWS] view drag: mouse drag did not consume a tile; trying JS fallback",
            "[EXPORT] completed in 14s (progress bar hidden)",
            "[LPR] play_camera: drag landed nothing",
        ]

    def test_scan_tolerates_empty_and_none(self):
        """Scanning empty or missing output yields no advisories."""
        assert ra.scan_advisories('') == []
        assert ra.scan_advisories(None) == []

    def test_summary_carries_advisories_and_defaults_empty(self):
        """The summary copies the advisory list and defaults it to empty."""
        base = dict(started=1000.0, ended=1010.0, exitstatus=0,
                    counts={'passed': 1}, target=['t'], markexpr='',
                    keyword='', report_file=None)
        assert ra._build_summary(**base)['advisories'] == []
        items = [{'test': 't::a', 'phase': 'call', 'line': '[LPR] x'}]
        out = ra._build_summary(**base, advisories=items)
        assert out['advisories'] == items
        assert out['advisories'] is not items  # a copy, never the live list

    def test_format_groups_lines_under_their_test(self):
        """advisories.txt groups each test's lines under its node id."""
        text = ra._format_advisories([
            {'test': 't::a', 'line': '[VIEWS] one'},
            {'test': 't::a', 'line': '[VIEWS] two'},
            {'test': 't::b', 'line': '[LPR] three'},
        ])
        assert text == 't::a\n  [VIEWS] one\n  [VIEWS] two\nt::b\n  [LPR] three\n'

    def test_index_shows_the_count_and_tolerates_missing_key(self):
        """The index shows each run's advisory count and blanks a missing key."""
        html = ra._render_index([
            {'name': '2026-08-21_10-00-00__a', 'has_report': False,
             'summary': {'advisories': [{'line': '[LPR] x'}, {'line': '[VIEWS] y'}]}},
            {'name': '2026-08-21_09-00-00__b', 'has_report': False, 'summary': {}},
        ])
        assert '<th>Advisories</th>' in html
        assert '<td>2</td>' in html
        assert html.index('__a') < html.index('__b')


# ---------------------------------------------------------------- per-test facts

class _FakePhaseReport:
    """Just enough of a pytest TestReport for record_phase."""

    def __init__(self, nodeid, when, outcome, duration=1.0, stdout='', stderr='',
                 longrepr=''):
        self.nodeid = nodeid
        self.when = when
        self.outcome = outcome
        self.duration = duration
        self.capstdout = stdout
        self.capstderr = stderr
        self.longreprtext = longrepr


MAPPED = 'tests/ui/admin/test_admin_general.py::TestAdminGeneral::test_tabs[chromium]'


def _write_mapping(tmp_path, mappings) -> Path:
    path = tmp_path / 'mapping.json'
    path.write_text(json.dumps({'version': 1, 'mappings': mappings}), encoding='utf-8')
    return path


class TestCaseMapping:
    """QA Touch case titles ride along when the node id is mapped."""

    def test_load_reads_key_and_title(self, tmp_path):
        """Loading the mapping keeps only rows with a case key, as key plus title."""
        path = _write_mapping(tmp_path, {
            MAPPED: {'case_key': 'VKbBPP', 'case_title': 'Verify the tabs', 'reviewed': True},
            'tests/x.py::test_no_key': {'case_title': 'orphan'},
            'tests/x.py::test_odd': 'not a row',
        })
        assert ra.load_case_mapping(path) == {
            MAPPED: {'case_key': 'VKbBPP', 'case_title': 'Verify the tabs'}}

    def test_load_tolerates_missing_and_malformed_files(self, tmp_path):
        """A missing or malformed mapping file loads as empty."""
        assert ra.load_case_mapping(tmp_path / 'nope.json') == {}
        bad = tmp_path / 'bad.json'
        bad.write_text('{not json', encoding='utf-8')
        assert ra.load_case_mapping(bad) == {}
        bad.write_text(json.dumps({'mappings': ['a', 'b']}), encoding='utf-8')
        assert ra.load_case_mapping(bad) == {}

    def test_lookup_exact_then_bare_then_none(self):
        """Lookup tries the exact node id, then the bare function, then gives up."""
        mapping = {MAPPED: {'case_key': 'K1', 'case_title': 'T1'},
                   'tests/y.py::test_bare': {'case_key': 'K2', 'case_title': ''}}
        assert ra.lookup_case(mapping, MAPPED) == {'case_key': 'K1', 'case_title': 'T1'}
        # A mapping keyed on the bare function still names the [chromium] variant.
        assert ra.lookup_case(mapping, 'tests/y.py::test_bare[chromium]') == {
            'case_key': 'K2', 'case_title': None}
        assert ra.lookup_case(mapping, 'tests/z.py::test_other') == {
            'case_key': None, 'case_title': None}
        assert ra.lookup_case({}, MAPPED) == {'case_key': None, 'case_title': None}


class TestLogFileName:
    def test_sanitizes_like_the_screenshot_stem(self):
        """The log file name is the screenshot stem plus .log."""
        nodeid = 'tests/ui/views/test_views_basic.py::TestViews::test_open[chromium]'
        assert ra.log_file_name(nodeid) == \
            'tests-ui-views-test_views_basic.py-TestViews-test_open-chromium.log'

    def test_caps_the_stem(self):
        """The log file stem is cut at 120 characters."""
        name = ra.log_file_name('tests/' + 'x' * 300)
        assert name.endswith('.log')
        assert len(name) == ra.LOG_NAME_MAX + len('.log')
        assert ra.LOG_NAME_MAX == 120


class TestRecordPhase:
    NODEID = 'tests/ui/views/test_views_drag_drop.py::TestDrag::test_drag_camera_to_tile[chromium]'

    def _state(self):
        state = ra._RunState()
        state.mapping = {self.NODEID: {'case_key': 'K9', 'case_title': 'Drag a camera'}}
        return state

    def test_builds_the_record_across_phases(self):
        """Phase reports build one record with title, case, outcome, and timings."""
        state = self._state()
        phases = [
            _FakePhaseReport(self.NODEID, 'setup', 'passed', 0.5, stdout='[AUTH] cached\n'),
            _FakePhaseReport(self.NODEID, 'call', 'failed', 12.25, stdout='[VIEWS] fallback\n',
                             stderr='warn\n', longrepr='E   assert False'),
            _FakePhaseReport(self.NODEID, 'teardown', 'passed', 0.25),
        ]
        for report in phases:
            ra.record_phase(state, report, doc='Verify a camera can be dragged.\n\n    More.',
                            mapping=state.mapping)
        rec = state.tests[self.NODEID]
        assert rec['title'] == 'Verify a camera can be dragged.'
        assert rec['module'] == 'ui/views/test_views_drag_drop.py'
        assert rec['case_key'] == 'K9'
        assert rec['case_title'] == 'Drag a camera'
        assert rec['outcome'] == 'failed'
        assert rec['phases'] == {'setup': 0.5, 'call': 12.25, 'teardown': 0.25}
        assert rec['duration_s'] == 13.0
        assert rec['log_file'] is None
        captured = state.captured[self.NODEID]
        assert [c['phase'] for c in captured] == ['setup', 'call', 'teardown']
        assert captured[1]['stderr'] == 'warn\n'
        assert captured[1]['error'] == 'E   assert False'
        assert captured[0]['error'] == ''  # only a failed phase keeps its traceback

    @pytest.mark.parametrize(('when', 'outcome', 'expected'), [
        ('setup', 'failed', 'error'),
        ('setup', 'skipped', 'skipped'),
        ('call', 'passed', 'passed'),
        ('call', 'skipped', 'skipped'),
    ])
    def test_outcome_vocabulary(self, when, outcome, expected):
        """A setup failure records as error; skips and passes keep their names."""
        state = self._state()
        ra.record_phase(state, _FakePhaseReport(self.NODEID, when, outcome))
        assert state.tests[self.NODEID]['outcome'] == expected

    def test_title_falls_back_to_the_function_name(self):
        """Without a docstring, the record's title comes from the function name."""
        state = ra._RunState()
        state.mapping = {}
        ra.record_phase(state, _FakePhaseReport(self.NODEID, 'setup', 'passed'), doc=None)
        assert state.tests[self.NODEID]['title'] == 'Drag camera to tile'
        assert state.tests[self.NODEID]['case_key'] is None

    def test_capture_reads_the_phase_section_only(self):
        """pytest accumulates sections across phases, so capstdout on the
        call report repeats setup's output; the phase's section does not."""
        report = _FakePhaseReport(self.NODEID, 'call', 'passed', 1.0,
                                  stdout='[AUTH] cached\n[VIEWS] drag\n')
        report.sections = [('Captured stdout setup', '[AUTH] cached\n'),
                           ('Captured stdout call', '[VIEWS] drag\n'),
                           ('Captured stderr call', 'warn\n')]
        assert ra.phase_capture(report, 'stdout') == '[VIEWS] drag\n'
        assert ra.phase_capture(report, 'stderr') == 'warn\n'
        report.when = 'teardown'
        assert ra.phase_capture(report, 'stdout') == ''
        # No sections at all: the joined attribute is the only source.
        plain = _FakePhaseReport(self.NODEID, 'call', 'passed', stdout='x\n')
        assert ra.phase_capture(plain, 'stdout') == 'x\n'
        assert ra.phase_capture(plain, 'stderr') == ''

    def test_rerun_attempts_are_not_final(self):
        """A rerun attempt leaves no outcome; the final attempt sets it."""
        state = self._state()
        ra.record_phase(state, _FakePhaseReport(self.NODEID, 'call', 'rerun', 30.0))
        assert state.tests[self.NODEID]['outcome'] is None
        assert state.tests[self.NODEID]['phases'] == {}
        assert self.NODEID not in state.captured
        ra.record_phase(state, _FakePhaseReport(self.NODEID, 'call', 'passed', 8.0))
        assert state.tests[self.NODEID]['outcome'] == 'passed'
        assert state.tests[self.NODEID]['duration_s'] == 8.0

    def test_summary_copies_the_records(self):
        """The summary snapshots the test records so later edits do not leak in."""
        state = self._state()
        ra.record_phase(state, _FakePhaseReport(self.NODEID, 'call', 'passed', 2.0))
        summary = ra._build_summary(started=0.0, ended=5.0, exitstatus=0, counts={},
                                    target=[], markexpr='', keyword='', report_file=None,
                                    tests=list(state.tests.values()),
                                    provenance={'env': 'qa'})
        assert summary['tests'][0]['nodeid'] == self.NODEID
        assert summary['provenance'] == {'env': 'qa'}
        state.tests[self.NODEID]['phases']['teardown'] = 1.0
        assert 'teardown' not in summary['tests'][0]['phases']


class TestTestLog:
    """One file per test: every phase's captured output, in order."""

    def test_format_lists_each_phase(self):
        """The test log lists its header lines, then each phase's output in order."""
        rec = {'nodeid': 't/x.py::test_a', 'title': 'Do a thing', 'case_key': 'K1',
               'case_title': 'Case one'}
        phases = [
            {'phase': 'setup', 'outcome': 'passed', 'duration': 0.5, 'stdout': '[AUTH] ok\n'},
            {'phase': 'call', 'outcome': 'failed', 'duration': 3.0, 'stdout': '',
             'stderr': 'boom\n', 'error': 'E   assert 1 == 2'},
            {'phase': 'teardown', 'outcome': 'passed', 'duration': 0.1},
        ]
        text = ra.format_test_log(rec, phases)
        assert text.startswith('t/x.py::test_a\nDo a thing\nQA Touch K1: Case one\n')
        assert '=== setup: passed (0.50 s) ===\n--- stdout ---\n[AUTH] ok\n' in text
        assert '=== call: failed (3.00 s) ===\n--- stderr ---\nboom\n--- error ---\nE   assert 1 == 2' in text
        assert '=== teardown: passed (0.10 s) ===\n(no output)\n' in text

    def test_format_without_a_case_or_phases(self):
        """A record with no case and no phases logs just its id and title."""
        text = ra.format_test_log({'nodeid': 't::a', 'title': 'A', 'case_key': None}, [])
        assert text == 't::a\nA\n'

    def test_archive_writes_the_log_folder(self, tmp_path, monkeypatch):
        """log/<test>.log per test plus the session's run.log, and the
        summary record points at the file."""
        monkeypatch.setattr(ra, 'RUNS_DIR', tmp_path / 'runs')
        monkeypatch.setattr(ra, 'SCREENSHOT_DIR', tmp_path / 'shots')
        monkeypatch.setattr(ra, 'TRACE_DIR', tmp_path / 'artifacts')
        monkeypatch.setattr(ra, 'RESULTS_JSON', tmp_path / 'none.json')
        state = ra._RunState()
        state.mapping = {}
        state.started, state.ended, state.exitstatus = 1_700_000_000.0, 1_700_000_010.0, 0
        state.counts['passed'] = 1
        nodeid = 't/x.py::test_a[chromium]'
        ra.record_phase(state, _FakePhaseReport(nodeid, 'setup', 'passed', 0.5, stdout='hi\n'))
        ra.record_phase(state, _FakePhaseReport(nodeid, 'call', 'passed', 2.0, stdout='[LPR] x\n'))
        state.run_log.attach(tmp_path / 'live' / 'run.log')
        logging.getLogger('views_page').info('opened the page')
        state.run_log.detach()

        ra._archive_run(_FakeConfig(args=['t/x.py']), state)
        dest = next(p for p in (tmp_path / 'runs').iterdir() if p.is_dir())
        test_log = dest / 'log' / 't-x.py-test_a-chromium.log'
        assert test_log.is_file()
        body = test_log.read_text(encoding='utf-8')
        assert 'hi\n' in body
        assert '[LPR] x' in body
        assert 'opened the page' in (dest / 'log' / 'run.log').read_text(encoding='utf-8')
        summary = json.loads((dest / 'summary.json').read_text(encoding='utf-8'))
        assert summary['tests'][0]['log_file'] == 'log/t-x.py-test_a-chromium.log'
        assert summary['tests'][0]['title'] == 'A'
        assert set(summary['provenance']) == {'env', 'base_url_host', 'git_commit', 'playwright',
                                              'pytest_playwright', 'browser', 'browser_channel'}
        page = (dest / 'run.html').read_text(encoding='utf-8')
        assert 'href="log/t-x.py-test_a-chromium.log"' in page
        assert 'href="log/run.log"' in page


class TestRunLog:
    def test_attach_writes_info_records_and_detach_restores(self, tmp_path):
        """Attaching writes INFO records to run.log; detaching restores the root logger."""
        root = logging.getLogger()
        before_level = root.level
        before_handlers = list(root.handlers)
        run_log = ra._RunLog()
        run_log.attach(tmp_path / 'run.log')
        try:
            assert root.getEffectiveLevel() <= logging.INFO
            logging.getLogger('report_media').info('cleared 3 screenshots')
            logging.getLogger('report_media').debug('not at INFO')
        finally:
            run_log.detach()
        text = (tmp_path / 'run.log').read_text(encoding='utf-8')
        assert 'INFO report_media: cleared 3 screenshots' in text
        assert 'not at INFO' not in text
        assert root.level == before_level
        assert root.handlers == before_handlers
        run_log.detach()  # a second detach is harmless

    def test_unit_test_runs_never_start_a_run_log(self):
        """Same guard as the archive: the repo's own tests leave no evidence."""
        assert ra._process_may_archive(_FakeConfig(args=['tests/plugins']), {}) is False
        assert ra._process_may_archive(_FakeConfig(collect_only=True), {}) is False
        assert ra._process_may_archive(_FakeConfig(), {'PYTEST_XDIST_WORKER': 'gw0'}) is False
        assert ra._process_may_archive(_FakeConfig(), {}) is True


def test_index_links_health_only_when_it_exists(tmp_path):
    """The index links health.html only when the file exists."""
    entries = [_entry('2026-08-01_10-00-00__a')]
    assert 'href="health.html"' not in ra._render_index(entries)
    assert 'run.py health' in ra._render_index(entries)
    assert 'href="health.html"' in ra._render_index(entries, has_health=True)
    (tmp_path / '2026-08-01_10-00-00__a').mkdir()
    ra._write_index(tmp_path)
    assert 'href="health.html"' not in (tmp_path / 'index.html').read_text(encoding='utf-8')
    (tmp_path / 'health.html').write_text('x', encoding='utf-8')
    ra._write_index(tmp_path)
    assert 'href="health.html"' in (tmp_path / 'index.html').read_text(encoding='utf-8')
