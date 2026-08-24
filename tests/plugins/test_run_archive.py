"""Unit tests for plugins/run_archive.py.

Pure-helper coverage plus the screenshot copy's gates (run on temp folders):
slug building, collision suffixing, prune selection, path-cap truncation,
the summary shape, index rendering, outcome classification, and the guard
decisions. The full end-to-end archive needs a finished pytest session with
real report files, so it is exercised by real runs, not here.

Living under tests/plugins/ to be picked up by the default discovery without
needing to add a new test root or update pytest collection config. The tests
do not require playwright, a browser, or network.
"""
from __future__ import annotations

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
    assert ra._build_slug(['tests/ui/views']) == 'tests-ui-views'


def test_slug_joins_multiple_targets():
    assert ra._build_slug(['tests/ui/media', 'tests/ui/maps']) == \
        'tests-ui-media-tests-ui-maps'


def test_slug_appends_the_markexpr():
    assert ra._build_slug(['tests/ui'], 'smoke and not slow') == \
        'tests-ui-smoke-and-not-slow'


def test_slug_empty_invocation_becomes_all():
    assert ra._build_slug([]) == 'all'
    assert ra._build_slug([], '') == 'all'


def test_slug_all_junk_becomes_all():
    """A target that sanitizes away entirely must still name a folder."""
    assert ra._build_slug(['///']) == 'all'


def test_slug_caps_at_40():
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
    assert ra._unique_dir(tmp_path, 'run') == tmp_path / 'run'


def test_unique_dir_appends_2_then_3(tmp_path):
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
    names = [_run_name(i) for i in range(1, 26)]  # 25 runs, day 25 newest
    prunable = ra._select_prunable(names)
    assert prunable == [_run_name(i) for i in range(5, 0, -1)]
    assert ra.KEEP_RUNS == 20


def test_prune_nothing_at_or_under_the_cap():
    assert ra._select_prunable([_run_name(i) for i in range(1, 21)]) == []
    assert ra._select_prunable([]) == []


def test_prune_ignores_non_run_names():
    """index.html and hand-made folders must never be candidates."""
    names = ['index.html', 'keep-me', '2026-08-01_10-00', 'notes.txt',
             *[_run_name(i) for i in range(1, 25)]]
    prunable = ra._select_prunable(names)
    assert prunable == [_run_name(i) for i in range(4, 0, -1)]


def test_prune_pattern_requires_the_double_underscore():
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
    dest = tmp_path / 'traces' / 'short-trace.zip'
    assert ra._fit_dest(dest) is dest


def test_fit_dest_truncates_the_stem_to_fit(tmp_path):
    dest = tmp_path / ('t' * 300 + '.zip')
    fitted = ra._fit_dest(dest)
    assert fitted is not None
    assert len(str(fitted)) == 250
    assert fitted.suffix == '.zip'
    assert str(fitted.parent) == str(tmp_path)


def test_fit_dest_none_when_the_directory_alone_is_too_long(tmp_path):
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
    counts = {'passed': 3, 'failed': 1, 'skipped': 2, 'errors': 0}
    summary = ra._build_summary(started=1000.0, ended=1090.5, exitstatus=1,
                                counts=counts, target=['tests/ui/views'],
                                markexpr='smoke', keyword='',
                                report_file='report.html')
    assert set(summary) == {'schema_version', 'started', 'ended', 'duration_s',
                            'exitstatus', 'counts', 'target', 'markexpr',
                            'keyword', 'report_file', 'advisories'}
    assert summary['schema_version'] == 1
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
    html = ra._render_index([
        _entry('2026-08-01_10-00-00__old'),
        _entry('2026-08-03_10-00-00__new'),
        _entry('2026-08-02_10-00-00__mid'),
    ])
    assert html.index('__new') < html.index('__mid') < html.index('__old')


def test_index_links_report_only_when_present():
    html = ra._render_index([
        _entry('2026-08-01_10-00-00__a', has_report=True),
        _entry('2026-08-02_10-00-00__b', has_report=False),
    ])
    assert '2026-08-01_10-00-00__a/report.html' in html
    assert '2026-08-02_10-00-00__b/report.html' not in html
    # The folder link is always there - traces have no report to link.
    assert '2026-08-02_10-00-00__b/' in html


def test_index_tolerates_an_empty_summary():
    """A folder from an older layout (no summary.json) still gets a row
    built from its name alone."""
    html = ra._render_index([_entry('2026-08-01_10-00-00__views')])
    assert '2026-08-01 10-00-00' in html  # timestamp from the folder name
    assert 'views' in html                # target from the folder name
    assert '<td>-</td>' in html           # unknown counts render as '-'


def test_index_renders_summary_values():
    summary = {'started': '2026-08-01T10:00:00', 'exitstatus': 0,
               'counts': {'passed': 7, 'failed': 1, 'skipped': 2, 'errors': 0},
               'target': ['tests/ui/media']}
    html = ra._render_index([_entry('2026-08-01_10-00-00__media', summary)])
    assert '2026-08-01T10:00:00' in html
    assert 'tests/ui/media' in html
    for cell in ('<td>7</td>', '<td>1</td>', '<td>2</td>', '<td>0</td>'):
        assert cell in html


def test_index_has_a_caption_and_survives_no_runs():
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
    assert ra._classify(when, outcome) == counter


@pytest.mark.parametrize(('when', 'outcome'), [
    ('setup', 'passed'),      # setup success is not a result yet
    ('teardown', 'failed'),   # teardown reports never represent the test
    ('teardown', 'passed'),
    ('call', 'rerun'),        # rerun outcomes are not final
])
def test_classify_ignored_phases(when, outcome):
    assert ra._classify(when, outcome) is None


# ---------------------------------------------------------------------------
# Kill switch
# ---------------------------------------------------------------------------

@pytest.mark.parametrize('value', ['off', 'OFF', 'Off', '0', 'false', 'no', ' off '])
def test_kill_switch_off_values(value):
    assert ra._archive_disabled({'RUN_ARCHIVE': value}) is True


@pytest.mark.parametrize('value', ['', 'on', '1', 'true', 'anything-else'])
def test_kill_switch_on_values(value):
    assert ra._archive_disabled({'RUN_ARCHIVE': value}) is False


def test_kill_switch_defaults_to_on():
    assert ra._archive_disabled({}) is False


# ---------------------------------------------------------------------------
# Archive guard decisions
# ---------------------------------------------------------------------------

class _FakeConfig:
    """Just enough of pytest Config for _should_archive: getoption only."""

    def __init__(self, collect_only=False):
        self._collect_only = collect_only

    def getoption(self, name, default=None):
        if name == '--collect-only':
            return self._collect_only
        return default


def test_should_archive_in_a_plain_run():
    assert ra._should_archive(_FakeConfig(), {}, tests_run=5) is True


def test_should_not_archive_during_collect_only():
    """run_suite's planning pass must never bury the real run's archive."""
    assert ra._should_archive(_FakeConfig(collect_only=True), {}, tests_run=5) is False


def test_should_not_archive_in_xdist_worker():
    env = {'PYTEST_XDIST_WORKER': 'gw0'}
    assert ra._should_archive(_FakeConfig(), env, tests_run=5) is False


def test_should_not_archive_when_zero_tests_ran():
    assert ra._should_archive(_FakeConfig(), {}, tests_run=0) is False


def test_should_not_archive_when_every_guard_trips():
    env = {'PYTEST_XDIST_WORKER': 'gw1'}
    assert ra._should_archive(_FakeConfig(collect_only=True), env, tests_run=0) is False


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
        assert ra.scan_advisories(self.CAPTURED) == [
            "[VIEWS] view drag: mouse drag did not consume a tile; trying JS fallback",
            "[EXPORT] completed in 14s (progress bar hidden)",
            "[LPR] play_camera: drag landed nothing",
        ]

    def test_scan_tolerates_empty_and_none(self):
        assert ra.scan_advisories('') == []
        assert ra.scan_advisories(None) == []

    def test_summary_carries_advisories_and_defaults_empty(self):
        base = dict(started=1000.0, ended=1010.0, exitstatus=0,
                    counts={'passed': 1}, target=['t'], markexpr='',
                    keyword='', report_file=None)
        assert ra._build_summary(**base)['advisories'] == []
        items = [{'test': 't::a', 'phase': 'call', 'line': '[LPR] x'}]
        out = ra._build_summary(**base, advisories=items)
        assert out['advisories'] == items
        assert out['advisories'] is not items  # a copy, never the live list

    def test_format_groups_lines_under_their_test(self):
        text = ra._format_advisories([
            {'test': 't::a', 'line': '[VIEWS] one'},
            {'test': 't::a', 'line': '[VIEWS] two'},
            {'test': 't::b', 'line': '[LPR] three'},
        ])
        assert text == 't::a\n  [VIEWS] one\n  [VIEWS] two\nt::b\n  [LPR] three\n'

    def test_index_shows_the_count_and_tolerates_missing_key(self):
        html = ra._render_index([
            {'name': '2026-08-21_10-00-00__a', 'has_report': False,
             'summary': {'advisories': [{'line': '[LPR] x'}, {'line': '[VIEWS] y'}]}},
            {'name': '2026-08-21_09-00-00__b', 'has_report': False, 'summary': {}},
        ])
        assert '<th>Advisories</th>' in html
        assert '<td>2</td>' in html
        assert html.index('__a') < html.index('__b')
