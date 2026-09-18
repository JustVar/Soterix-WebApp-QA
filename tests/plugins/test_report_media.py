"""Unit tests for plugins/report_media.py.

Pure-helper coverage: filename sanitizing and capping, phase/outcome to
suffix mapping, page resolution, the report-embed gate, the kill switch,
the cleanup guard decisions, and the mid-drag capture drain (clear-in-place
semantics, the per-test cap, filed names, embed gating, the skipped-drag
filing), the PASSED-shot settle, and the grid stream verdict
(ViewsPage.assert_tile_streaming's pure decision, kept here with the
other browser-free checks). The final-shot capture itself needs a live
browser plus the pytest-html run loop, so it is exercised by real UI
runs; the drag-frame filing runs here against fake pages and reports.

Living under tests/plugins/ to be picked up by the default discovery without
needing to add a new test root or update pytest collection config. The tests
do not require playwright, a browser, or network.
"""
from __future__ import annotations

import base64
import os
import re
import sys
from pathlib import Path

import pytest

# Ensure the repo root is importable so `plugins.report_media` resolves
# the same way pytest itself loads it during a real run.
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import conftest  # noqa: E402
from plugins import report_media as rm, run_report as rr  # noqa: E402
from tests.shared.pages.views_page import (  # noqa: E402
    describe_tile_samples,
    tile_stream_verdict,
)


def _deep_dir(tmp_path: Path, length: int = 190) -> Path:
    """A folder whose absolute path is `length` chars: a stand-in for a
    deep checkout, where the stem caps alone no longer keep a name under
    the path cap. 190 leaves the 20-char tail intact after the cut."""
    return tmp_path / ('d' * max(1, length - len(os.path.abspath(tmp_path)) - 1))

# ---------------------------------------------------------------------------
# Name sanitizing + capping
# ---------------------------------------------------------------------------

def test_safe_name_flattens_nodeid_separators():
    """Node id separators flatten to dashes in the screenshot stem."""
    nodeid = 'tests/ui/views/test_views_basic.py::TestViews::test_open[chromium]'
    assert rm._safe_name(nodeid) == 'tests-ui-views-test_views_basic.py-TestViews-test_open-chromium'


def test_safe_name_strips_edge_dashes():
    """Leading and trailing dashes are stripped from the stem."""
    assert rm._safe_name('[weird]') == 'weird'


def test_safe_name_keeps_word_chars_dots_and_hyphens():
    """Word characters, dots, and hyphens pass through the stem untouched."""
    assert rm._safe_name('a.b_c-d') == 'a.b_c-d'


def test_safe_name_caps_at_120():
    """The screenshot stem is cut at 120 characters."""
    assert len(rm._safe_name('x' * 300)) == 120
    assert rm.SAFE_NAME_MAX == 120


def test_safe_name_matches_the_trace_sanitizer():
    """Screenshot and trace stems must sort together; only the cap differs."""
    nodeid = 'tests/ui/media/test_media.py::TestMedia::test_vault[chromium-case 1]'
    expected = re.sub(r'[^\w.-]+', '-', nodeid).strip('-')[:120]
    assert rm._safe_name(nodeid) == expected


# ---------------------------------------------------------------------------
# Phase/outcome -> suffix mapping
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(('when', 'outcome', 'suffix'), [
    ('call', 'passed', 'PASSED'),
    ('call', 'failed', 'FAILED'),
    ('setup', 'failed', 'SETUP_FAILED'),
])
def test_suffix_for_captured_phases(when, outcome, suffix):
    """Call passes, call failures, and setup failures map to their suffixes."""
    assert rm._suffix_for(when, outcome) == suffix


@pytest.mark.parametrize(('when', 'outcome'), [
    ('call', 'skipped'),     # no final image; stashed drag frames file separately
    ('setup', 'passed'),     # setup success is not a result yet
    ('setup', 'skipped'),
    ('teardown', 'failed'),  # fixtures are already gone by teardown
    ('teardown', 'passed'),
])
def test_suffix_for_uncaptured_phases(when, outcome):
    """Skips, setup passes, and teardown reports capture no final image."""
    assert rm._suffix_for(when, outcome) is None


# ---------------------------------------------------------------------------
# Expected trace path (must mirror conftest._trace_path)
# ---------------------------------------------------------------------------

def test_expected_trace_path_shape():
    """The expected trace path ends reports/artifacts/<stem>-trace.zip.

    Since the package extraction, the plugin roots its paths at the repo
    (configure() runs in pytest_sessionstart), so the path is absolute
    rather than CWD-relative. It resolves to the same file when run from the
    repo root; the tail is what this pins."""
    nodeid = 'tests/ui/x.py::test_t[chromium]'
    got = rm._expected_trace_path(nodeid)
    assert got.parent.parts[-2:] == ('reports', 'artifacts')
    assert got.name == 'tests-ui-x.py-test_t-chromium-trace.zip'


def test_expected_trace_path_keeps_the_150_cap(tmp_path, monkeypatch):
    """The trace cap is conftest's 150, not the screenshot's 120. From a short
    root: on a deep checkout fit_name shortens the name to the path cap, and
    this pin is about the stem rule, not the machine it runs on."""
    monkeypatch.setattr(rm, 'TRACE_DIR', Path(tmp_path.anchor) / 's')
    path = rm._expected_trace_path('y' * 300)
    stem = path.name.removesuffix('-trace.zip')
    assert len(stem) == 150


def test_expected_trace_path_matches_conftest_on_a_deep_checkout(tmp_path, monkeypatch):
    """On a deep checkout the fixture shortens the trace name to fit the
    path cap. The report's link must name that same shortened file."""
    deep = _deep_dir(tmp_path)
    monkeypatch.setattr(conftest, 'TRACE_DIR', deep)
    monkeypatch.setattr(rm, 'TRACE_DIR', deep)
    nodeid = 'tests/ui/' + 'n' * 200 + '.py::TestT::test_t[chromium]'
    expected = rm._expected_trace_path(nodeid)
    assert expected == conftest._trace_path(nodeid)
    assert expected.name != re.sub(r'[^\w.-]+', '-', nodeid)[:150] + '-trace.zip'
    assert expected.name.endswith('-trace.zip')
    assert len(os.path.abspath(expected)) <= 250


def test_conftest_video_path_fits_the_cap_on_a_deep_checkout(tmp_path, monkeypatch):
    """The kept video shortens the same way, so Playwright's save_as
    never sees a path Windows refuses."""
    monkeypatch.setattr(conftest, 'TRACE_DIR', _deep_dir(tmp_path))
    path = conftest._video_path('tests/ui/' + 'n' * 200 + '.py::TestT::test_t[chromium]')
    assert path.name.endswith('-video.webm')
    assert len(os.path.abspath(path)) <= 250


def test_live_shortened_screenshot_name_matches_its_test(tmp_path, monkeypatch):
    """On a deep checkout the final shot's name shortens as it is written.
    run_report must still attach the file to the right parametrized twin,
    and a shortened mid-drag frame to its test."""
    monkeypatch.setattr(rm, 'SCREENSHOT_DIR', _deep_dir(tmp_path))
    twins = ['tests/c2c/test_cams.py::TestCams::test_reboot[camera-3]',
             'tests/c2c/test_cams.py::TestCams::test_reboot[camera-4]']
    safes = {rr._safe_name(n, rr.SAFE_NAME_MAX): n for n in twins}
    for nodeid in twins:
        name = rm._final_filename(nodeid, 'FAILED')
        assert name != f'{rm._safe_name(nodeid)}__FAILED.png'
        assert len(os.path.abspath(rm.SCREENSHOT_DIR / name)) <= 250
        parsed = rr.parse_screenshot_name(Path(name).stem)
        assert parsed is not None
        assert rr.match_test(parsed['test'], safes,
                             lambda safe, s=parsed['suffix']: f'{safe}__{s}') == nodeid
    frame = rm._capture_filename(twins[1], 'FAILED', 'mid-drag', 2)
    assert frame != f'{rm._safe_name(twins[1])}__FAILED__mid-drag-2.png'
    parsed = rr.parse_screenshot_name(Path(frame).stem)
    assert parsed is not None
    assert (parsed['label'], parsed['index']) == ('mid-drag', '2')
    tail = f"__{parsed['label']}-{parsed['index']}"
    assert rr.match_test(parsed['test'], safes,
                         lambda safe, s=parsed['suffix'], f=tail: f'{safe}__{s}{f}') == twins[1]


# ---------------------------------------------------------------------------
# Page resolution (class-based self.page first, then direct fixture requests)
# ---------------------------------------------------------------------------

class _FakePage:
    def __init__(self, closed=False):
        self._closed = closed

    def is_closed(self):
        return self._closed


class _FakeItem:
    def __init__(self, instance=None, funcargs=None,
                 nodeid='tests/ui/x.py::test_t', name='test_t'):
        self.instance = instance
        self.funcargs = funcargs or {}
        self.nodeid = nodeid
        self.name = name


class _FakeInstance:
    def __init__(self, page=None):
        if page is not None:
            self.page = page


def test_resolve_page_prefers_class_instance_page():
    """A class test's self.page wins over a page in funcargs."""
    inst_page, arg_page = _FakePage(), _FakePage()
    item = _FakeItem(instance=_FakeInstance(inst_page),
                     funcargs={'authenticated_page': arg_page})
    assert rm._resolve_page(item) is inst_page


def test_resolve_page_finds_instance_page_after_a_setup_crash():
    """pytest stops filling funcargs at the failing fixture, so after an
    autouse setup crash self.page is the only handle to the open page."""
    page = _FakePage()
    item = _FakeItem(instance=_FakeInstance(page), funcargs={})
    assert rm._resolve_page(item) is page


def test_resolve_page_falls_back_to_funcargs_for_function_tests():
    """A function test's page comes from its fixture funcargs."""
    page = _FakePage()
    item = _FakeItem(funcargs={'authenticated_page': page})
    assert rm._resolve_page(item) is page


def test_resolve_page_prefers_authenticated_page_over_page():
    """authenticated_page wins over page when both are requested."""
    auth, plain = _FakePage(), _FakePage()
    item = _FakeItem(funcargs={'authenticated_page': auth, 'page': plain})
    assert rm._resolve_page(item) is auth


def test_resolve_page_skips_closed_candidates():
    """A closed page is passed over for a live one."""
    live = _FakePage()
    item = _FakeItem(instance=_FakeInstance(_FakePage(closed=True)),
                     funcargs={'page': live})
    assert rm._resolve_page(item) is live


def test_resolve_page_skips_a_non_page_on_the_instance():
    """A class whose self.page holds something else (no is_closed) must not
    shadow a real page requested via fixture."""
    live = _FakePage()
    item = _FakeItem(instance=_FakeInstance(object()),
                     funcargs={'page': live})
    assert rm._resolve_page(item) is live


def test_resolve_page_none_when_nothing_is_usable():
    """With no page, or only a closed one, nothing resolves."""
    assert rm._resolve_page(_FakeItem()) is None
    assert rm._resolve_page(
        _FakeItem(funcargs={'page': _FakePage(closed=True)})) is None


# ---------------------------------------------------------------------------
# Drag-capture drain (mouse_drag's stash: returned in order, cleared in place)
# ---------------------------------------------------------------------------

def test_drain_returns_frames_in_order_and_clears_in_place():
    """Draining returns frames in drag order and empties the same list in place."""
    page = _FakePage()
    stash = [('mid-drag', b'one'), ('mid-drag', b'two')]
    page._drag_captures = stash

    taken = rm._drain_drag_captures(page)

    assert taken == [('mid-drag', b'one'), ('mid-drag', b'two')]
    # cleared in place: mouse_drag keeps appending to the SAME list, so a
    # replacement (rather than a clear) would leak frames to the next test
    assert stash == []
    assert page._drag_captures is stash


def test_drain_without_a_stash_is_empty():
    """A page with no drag stash drains to nothing."""
    assert rm._drain_drag_captures(_FakePage()) == []


def test_drain_without_a_page_is_empty():
    """Draining with no page at all yields nothing."""
    assert rm._drain_drag_captures(None) == []


def test_drain_caps_at_8_and_still_clears_the_overflow():
    """Draining keeps the first 8 frames and discards the rest from the stash."""
    page = _FakePage()
    page._drag_captures = [('mid-drag', bytes([i])) for i in range(12)]

    taken = rm._drain_drag_captures(page)

    assert rm.DRAG_CAPTURE_MAX == 8
    assert taken == [('mid-drag', bytes([i])) for i in range(8)]
    # the dropped frames clear too - they must not resurface next test
    assert page._drag_captures == []


def test_drain_twice_yields_nothing_the_second_time():
    """A shared page drained at the call report has nothing left for the
    teardown report - the double-file path must be structurally closed."""
    page = _FakePage()
    page._drag_captures = [('mid-drag', b'x')]
    assert rm._drain_drag_captures(page) == [('mid-drag', b'x')]
    assert rm._drain_drag_captures(page) == []


# ---------------------------------------------------------------------------
# Mid-drag frame naming (stem and suffix of the final shot, plus the index)
# ---------------------------------------------------------------------------

def test_capture_filename_shape(tmp_path, monkeypatch):
    """A mid-drag frame is named <stem>__<suffix>__mid-drag-<n>.png (from a
    short root, so a deep checkout does not shorten the name under the pin)."""
    monkeypatch.setattr(rm, 'SCREENSHOT_DIR', Path(tmp_path.anchor) / 's')
    name = rm._capture_filename('tests/ui/x.py::test_t[chromium]',
                                'FAILED', 'mid-drag', 1)
    assert name == 'tests-ui-x.py-test_t-chromium__FAILED__mid-drag-1.png'


def test_capture_filename_reuses_the_capped_safe_stem(tmp_path, monkeypatch):
    """Longest possible name: 120-char stem + SETUP_FAILED + index, from a
    short root. A deep checkout (a root past about 70 characters) made this
    and two sibling pins fail and block every commit there, 09/18/2026."""
    monkeypatch.setattr(rm, 'SCREENSHOT_DIR', Path(tmp_path.anchor) / 's')
    name = rm._capture_filename('x' * 300, 'SETUP_FAILED', 'mid-drag', 8)
    assert name == 'x' * 120 + '__SETUP_FAILED__mid-drag-8.png'
    assert len(name) == 150


# ---------------------------------------------------------------------------
# Report-embed gate (failures always; PASSED only under REPORT_SCREENSHOTS=all)
# ---------------------------------------------------------------------------

@pytest.mark.parametrize('suffix', ['FAILED', 'SETUP_FAILED'])
def test_failures_always_embed(suffix):
    """Failed and setup-failed shots embed in the report whatever the env says."""
    assert rm._should_embed(suffix, {}) is True
    assert rm._should_embed(suffix, {'REPORT_SCREENSHOTS': 'all'}) is True


def test_passed_stays_out_of_the_report_by_default():
    """A full run's green screenshots would bloat the self-contained report
    past what a browser or the report email can carry."""
    assert rm._should_embed('PASSED', {}) is False


@pytest.mark.parametrize('value', ['all', 'ALL', ' all '])
def test_passed_embeds_when_opted_in(value):
    """REPORT_SCREENSHOTS=all, in any case or padding, embeds passed shots."""
    assert rm._should_embed('PASSED', {'REPORT_SCREENSHOTS': value}) is True


@pytest.mark.parametrize('value', ['on', '1', 'true', 'failures'])
def test_passed_stays_out_for_other_values(value):
    """REPORT_SCREENSHOTS values other than all leave passed shots out."""
    assert rm._should_embed('PASSED', {'REPORT_SCREENSHOTS': value}) is False


# ---------------------------------------------------------------------------
# Kill switch
# ---------------------------------------------------------------------------

@pytest.mark.parametrize('value', ['off', 'OFF', 'Off', '0', 'false', 'no', ' off '])
def test_kill_switch_off_values(value):
    """REPORT_SCREENSHOTS=off, in any spelling, disables capture."""
    assert rm._screenshots_disabled({'REPORT_SCREENSHOTS': value}) is True


@pytest.mark.parametrize('value', ['', 'on', '1', 'true', 'anything-else'])
def test_kill_switch_on_values(value):
    """Any REPORT_SCREENSHOTS value other than an off word keeps capture on."""
    assert rm._screenshots_disabled({'REPORT_SCREENSHOTS': value}) is False


def test_kill_switch_defaults_to_on():
    """With REPORT_SCREENSHOTS unset, capture is on."""
    assert rm._screenshots_disabled({}) is False


# ---------------------------------------------------------------------------
# Mid-drag frame filing (fake page + report; no browser, no run loop)
# ---------------------------------------------------------------------------

class _FakeShotPage(_FakePage):
    """A fake page whose screenshot() returns stand-in final-shot bytes."""

    def screenshot(self):
        return b'final-bytes'


class _FakeReport:
    """Just enough of a pytest report: the phase and its outcome."""

    def __init__(self, when='call', outcome='failed'):
        self.when = when
        self.outcome = outcome


def _stashed_item(*frames, **item_kwargs):
    """A fake item whose page carries the given mid-drag frame bytes."""
    page = _FakeShotPage()
    page._drag_captures = [('mid-drag', png) for png in frames]
    return _FakeItem(funcargs={'page': page}, **item_kwargs), page


def test_failed_test_files_and_embeds_its_mid_drag_frames(monkeypatch, tmp_path):
    """A failed drag files its frames and final shot and embeds them in order."""
    monkeypatch.setattr(rm, 'SCREENSHOT_DIR', tmp_path)
    monkeypatch.delenv('REPORT_SCREENSHOTS', raising=False)
    item, page = _stashed_item(b'one', b'two',
                               nodeid='tests/ui/v.py::test_drag[chromium]',
                               name='test_drag[chromium]')
    report = _FakeReport('call', 'failed')

    rm._attach_media(item, report)

    stem = 'tests-ui-v.py-test_drag-chromium'
    assert (tmp_path / f'{stem}__FAILED__mid-drag-1.png').read_bytes() == b'one'
    assert (tmp_path / f'{stem}__FAILED__mid-drag-2.png').read_bytes() == b'two'
    assert (tmp_path / f'{stem}__FAILED.png').read_bytes() == b'final-bytes'
    assert page._drag_captures == []
    # frames embed in drag order, ahead of the final shot they lead up to
    assert [extra['name'] for extra in report.extras] == [
        'test_drag[chromium] - mid-drag 1',
        'test_drag[chromium] - mid-drag 2',
        'test_drag[chromium] - FAILED',
    ]
    assert report.extras[0]['content'] == base64.b64encode(b'one').decode('ascii')


def test_passed_frames_stay_on_disk_only_by_default(monkeypatch, tmp_path):
    """Embed gating follows the final shot's rule: PASSED embeds nothing
    unless REPORT_SCREENSHOTS=all, but the disk copies are written."""
    monkeypatch.setattr(rm, 'SCREENSHOT_DIR', tmp_path)
    monkeypatch.delenv('REPORT_SCREENSHOTS', raising=False)
    item, page = _stashed_item(b'one')
    report = _FakeReport('call', 'passed')

    rm._attach_media(item, report)

    assert (tmp_path / 'tests-ui-x.py-test_t__PASSED__mid-drag-1.png').is_file()
    assert (tmp_path / 'tests-ui-x.py-test_t__PASSED.png').is_file()
    assert page._drag_captures == []
    assert getattr(report, 'extras', None) is None


def test_passed_frames_embed_when_the_final_shot_embeds(monkeypatch, tmp_path):
    """With REPORT_SCREENSHOTS=all, passed frames embed ahead of the final shot."""
    monkeypatch.setattr(rm, 'SCREENSHOT_DIR', tmp_path)
    monkeypatch.setenv('REPORT_SCREENSHOTS', 'all')
    item, _ = _stashed_item(b'one')
    report = _FakeReport('call', 'passed')

    rm._attach_media(item, report)

    assert [extra['name'] for extra in report.extras] == [
        'test_t - mid-drag 1',
        'test_t - PASSED',
    ]


def test_stash_clears_even_when_the_phase_files_no_image(monkeypatch, tmp_path):
    """A teardown report has no suffix, but frames stashed on a page that
    outlives the test must still be discarded, never filed next test."""
    monkeypatch.setattr(rm, 'SCREENSHOT_DIR', tmp_path)
    item, page = _stashed_item(b'stale')

    rm._attach_media(item, _FakeReport('teardown', 'passed'))

    assert page._drag_captures == []
    assert list(tmp_path.iterdir()) == []


def test_skipped_drag_test_files_frames_but_no_final_shot(monkeypatch, tmp_path):
    """A call-phase skip is how the drag tests bail on a failed drag, so
    the stashed mid-drag frames - the most diagnostic evidence of what
    the drag did - still land on disk under the SKIPPED suffix. No final
    shot and no embed: the skipped-tests contract holds for the report."""
    monkeypatch.setattr(rm, 'SCREENSHOT_DIR', tmp_path)
    item, page = _stashed_item(b'one', b'two')
    report = _FakeReport('call', 'skipped')

    rm._attach_media(item, report)

    stem = 'tests-ui-x.py-test_t'
    assert (tmp_path / f'{stem}__SKIPPED__mid-drag-1.png').read_bytes() == b'one'
    assert (tmp_path / f'{stem}__SKIPPED__mid-drag-2.png').read_bytes() == b'two'
    assert not (tmp_path / f'{stem}__SKIPPED.png').exists()
    assert page._drag_captures == []
    assert getattr(report, 'extras', None) is None


def test_frameless_skip_still_writes_nothing(monkeypatch, tmp_path):
    """A skip with an empty stash keeps the old contract: no image at all."""
    monkeypatch.setattr(rm, 'SCREENSHOT_DIR', tmp_path)
    item = _FakeItem(funcargs={'page': _FakeShotPage()})
    report = _FakeReport('call', 'skipped')

    rm._attach_media(item, report)

    assert list(tmp_path.iterdir()) == []
    assert getattr(report, 'extras', None) is None


def test_setup_skip_discards_stale_frames_without_writing(monkeypatch, tmp_path):
    """Frames sitting on the stash when setup skips predate this test (the
    shared page outlives tests), so they are discarded, never filed."""
    monkeypatch.setattr(rm, 'SCREENSHOT_DIR', tmp_path)
    item, page = _stashed_item(b'stale')

    rm._attach_media(item, _FakeReport('setup', 'skipped'))

    assert page._drag_captures == []
    assert list(tmp_path.iterdir()) == []


def test_kill_switch_still_clears_the_stash(monkeypatch, tmp_path):
    """REPORT_SCREENSHOTS=off writes and attaches nothing - but the stash
    still empties, because mouse_drag stashes regardless of the switch."""
    monkeypatch.setattr(rm, 'SCREENSHOT_DIR', tmp_path)
    item, page = _stashed_item(b'frame')
    report = _FakeReport('call', 'failed')

    rm._process_report(item, report, {'REPORT_SCREENSHOTS': 'off'})

    assert page._drag_captures == []
    assert list(tmp_path.iterdir()) == []
    assert getattr(report, 'extras', None) is None


# ---------------------------------------------------------------------------
# Cleanup guard decisions
# ---------------------------------------------------------------------------

class _FakeConfig:
    """Just enough of pytest Config for _should_clean: getoption only."""

    def __init__(self, collect_only=False):
        self._collect_only = collect_only

    def getoption(self, name, default=None):
        if name == '--collect-only':
            return self._collect_only
        return default


def test_should_clean_in_a_plain_run():
    """A plain run wipes the screenshot folder at session start."""
    assert rm._should_clean(_FakeConfig(), {}) is True


def test_should_not_clean_during_collect_only():
    """run_suite's planning pass must never wipe the last real run's images."""
    assert rm._should_clean(_FakeConfig(collect_only=True), {}) is False


def test_should_not_clean_in_xdist_worker():
    """An xdist worker never wipes the screenshot folder."""
    assert rm._should_clean(_FakeConfig(), {'PYTEST_XDIST_WORKER': 'gw0'}) is False


def test_should_not_clean_when_both_guards_trip():
    """Collect-only inside an xdist worker still does not wipe the folder."""
    env = {'PYTEST_XDIST_WORKER': 'gw1'}
    assert rm._should_clean(_FakeConfig(collect_only=True), env) is False


# ---------------------------------------------------------------------------
# Cleanup scope (guard c: *.png directly inside the folder, nothing else)
# ---------------------------------------------------------------------------

def test_clean_deletes_only_top_level_pngs(tmp_path):
    """Cleanup removes only top-level .png files, sparing other files and subfolders."""
    (tmp_path / 'a__PASSED.png').write_bytes(b'x')
    (tmp_path / 'b__FAILED.png').write_bytes(b'x')
    (tmp_path / 'notes.txt').write_text('keep me')
    nested = tmp_path / 'keep-dir'
    nested.mkdir()
    (nested / 'nested.png').write_bytes(b'x')

    removed = rm._clean_screenshot_dir(tmp_path)

    assert removed == 2
    assert not (tmp_path / 'a__PASSED.png').exists()
    assert not (tmp_path / 'b__FAILED.png').exists()
    assert (tmp_path / 'notes.txt').exists()
    assert (nested / 'nested.png').exists()


def test_clean_missing_dir_is_a_noop(tmp_path):
    """Cleaning a folder that does not exist removes nothing."""
    assert rm._clean_screenshot_dir(tmp_path / 'never-created') == 0


# ---------------------------------------------------------------------------
# PASSED-shot settle (spinners leave before the green screenshot)
# ---------------------------------------------------------------------------

class _FakeSettlePage(_FakeShotPage):
    """A fake page whose wait_for_function records its call and either
    returns (the spinners left) or raises (still up, or broken)."""

    def __init__(self, raise_with=None):
        super().__init__()
        self.raise_with = raise_with
        self.calls = []

    def wait_for_function(self, expression, timeout=None):
        self.calls.append((expression, timeout))
        if self.raise_with is not None:
            raise self.raise_with


def test_settle_waits_on_the_spinner_selector_with_the_5s_bound():
    """The settle polls the app's spinner selector for count zero, 5 s at most."""
    page = _FakeSettlePage()
    assert rm._settle_loaders(page) is True
    [(expression, timeout)] = page.calls
    assert rm.LOADER_SELECTOR in expression
    assert 'length === 0' in expression
    assert timeout == rm.SETTLE_MS == 5000


def test_settle_swallows_a_timeout_and_reports_false():
    """A spinner that stays is not an error: the shot is taken as-is."""
    page = _FakeSettlePage(raise_with=TimeoutError('still spinning'))
    assert rm._settle_loaders(page, timeout_ms=10) is False
    assert page.calls[0][1] == 10


def test_settle_without_a_page_or_the_method_is_false():
    """No page, or a page without wait_for_function, settles nothing."""
    assert rm._settle_loaders(None) is False
    assert rm._settle_loaders(_FakeShotPage()) is False


@pytest.mark.parametrize(('outcome', 'settle_calls'), [('passed', 1), ('failed', 0)])
def test_only_the_passed_shot_settles_first(monkeypatch, tmp_path, outcome, settle_calls):
    """PASSED waits for the spinners before its shot; FAILED keeps its
    spinner as evidence and shoots at once."""
    monkeypatch.setattr(rm, 'SCREENSHOT_DIR', tmp_path)
    monkeypatch.delenv('REPORT_SCREENSHOTS', raising=False)
    page = _FakeSettlePage()
    item = _FakeItem(funcargs={'page': page})

    rm._attach_media(item, _FakeReport('call', outcome))

    assert len(page.calls) == settle_calls
    assert (tmp_path / f'tests-ui-x.py-test_t__{outcome.upper()}.png').read_bytes() == b'final-bytes'


def test_a_broken_settle_never_costs_the_passed_shot(monkeypatch, tmp_path):
    """Any settle error is swallowed and the screenshot is still written."""
    monkeypatch.setattr(rm, 'SCREENSHOT_DIR', tmp_path)
    monkeypatch.delenv('REPORT_SCREENSHOTS', raising=False)
    page = _FakeSettlePage(raise_with=RuntimeError('page gone'))
    item = _FakeItem(funcargs={'page': page})

    rm._attach_media(item, _FakeReport('call', 'passed'))

    assert (tmp_path / 'tests-ui-x.py-test_t__PASSED.png').is_file()


# ---------------------------------------------------------------------------
# Grid stream verdict (ViewsPage.assert_tile_streaming's pure decision)
# ---------------------------------------------------------------------------

def _sample(**over):
    """One tile sample as the page's sampler returns it: a loading tile
    (video silent at readyState 0, the snapshot on screen) unless
    overridden."""
    base = {'found': True, 'surface': 'img 960x540', 'readable': True,
            'hash': 's', 'loader': 0, 'failed': False,
            'video_ready': 0, 'video_t': 0.0, 'video_w': 0}
    base.update(over)
    return base


def _playing(t=1.5, **over):
    """A sample whose video reports a decoded frame at currentTime t."""
    return _sample(video_ready=4, video_t=t, video_w=1280, **over)


def test_verdict_video_when_the_player_reports_and_time_moves():
    """The player's own word passes: readyState >= 3 and currentTime past
    the first sample - the full screen rule."""
    assert tile_stream_verdict(_sample(), _playing(0.4)) == 'video'
    assert tile_stream_verdict(_playing(0.4), _playing(1.1)) == 'video'


def test_verdict_video_that_reports_but_stalls_is_no_pass():
    """Once the video reports, a still currentTime is a stall - and the
    picture path is not consulted, even with a changed hash."""
    assert tile_stream_verdict(_playing(1.0), _playing(1.0)) == ''
    assert tile_stream_verdict(_playing(1.0), _playing(1.0, hash='other')) == ''


def test_verdict_frames_when_the_video_never_reports_but_the_picture_moves():
    """Fallback: the same painted surface hashing differently between
    the samples is a frame advancing."""
    canvas = _sample(surface='canvas.paint 640x360', hash='c1')
    assert tile_stream_verdict(canvas, dict(canvas, hash='c2')) == 'frames'


def test_verdict_empty_on_a_still():
    """Equal hashes with a silent video are a still - the snapshot under
    the spinner, or a frozen feed."""
    assert tile_stream_verdict(_sample(), _sample()) == ''


def test_verdict_waits_out_a_surface_change():
    """Snapshot image to painted canvas differs in hash but is not a
    frame advancing; the next pair on the new surface decides."""
    assert tile_stream_verdict(_sample(), _sample(surface='canvas.paint 640x360', hash='c1')) == ''


def test_verdict_empty_without_a_surface_or_a_tile():
    """No picture surface, no tile, or no sample at all is never a verdict."""
    assert tile_stream_verdict(_sample(surface=''), _sample(surface='')) == ''
    missing = {'found': False, 'tiles': 0}
    assert tile_stream_verdict(missing, missing) == ''
    assert tile_stream_verdict(None, _sample()) == ''


def test_verdict_unreadable_live_needs_no_loader_and_no_failure():
    """A tainted surface passes only with the spinner gone and no overlay."""
    tainted = _sample(surface='canvas.paint 640x360', readable=False, hash='', error='SecurityError')
    assert tile_stream_verdict(tainted, tainted) == 'unreadable-live'
    assert tile_stream_verdict(tainted, dict(tainted, loader=1)) == ''
    assert tile_stream_verdict(tainted, dict(tainted, failed=True)) == ''


def test_verdict_never_passes_across_a_readable_and_an_unreadable_sample():
    """A hash against no hash is not a comparison."""
    assert tile_stream_verdict(_sample(readable=False, hash=''), _sample(hash='b2')) == ''


def test_describe_names_the_still_the_loader_the_video_and_the_overlay():
    """The failure text carries the surface, both hashes, the loader,
    the video's readyState and currentTime, and the overlay when up."""
    first = _sample(loader=1)
    last = _sample(loader=0, failed=True)
    text = describe_tile_samples(first, last)
    assert 'surface img 960x540' in text
    assert 'hash s -> s (still)' in text
    assert 'no loader' in text
    assert 'video readyState 0 -> 0, currentTime 0.00 -> 0.00' in text
    assert "the tile shows 'The camera failed to load'" in text


def test_describe_reports_a_surface_change_and_a_missing_tile():
    """A surface that changed is named with the one it started on; a
    missing tile says how many player tiles were on screen."""
    text = describe_tile_samples(_sample(), _sample(surface='canvas.paint 640x360', hash='t'))
    assert 'surface canvas.paint 640x360 (was img 960x540)' in text
    assert 'hash s -> t' in text
    assert '(still)' not in text
    gone = describe_tile_samples(_sample(), {'found': False, 'tiles': 0})
    assert 'no player tile at that index (0 player tile(s)' in gone
