"""Unit tests for plugins/report_media.py.

Pure-helper coverage: filename sanitizing and capping, phase/outcome to
suffix mapping, page resolution, the report-embed gate, the kill switch,
the cleanup guard decisions, and the mid-drag capture drain (clear-in-place
semantics, the per-test cap, filed names, embed gating, the skipped-drag
filing). The final-shot capture itself needs a live browser plus the
pytest-html run loop, so it is exercised by real UI runs; the drag-frame
filing runs here against fake pages and reports.

Living under tests/plugins/ to be picked up by the default discovery without
needing to add a new test root or update pytest collection config. The tests
do not require playwright, a browser, or network.
"""
from __future__ import annotations

import base64
import re
import sys
from pathlib import Path

import pytest

# Ensure the repo root is importable so `plugins.report_media` resolves
# the same way pytest itself loads it during a real run.
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from plugins import report_media as rm  # noqa: E402

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
    """The expected trace path is reports/artifacts/<stem>-trace.zip."""
    nodeid = 'tests/ui/x.py::test_t[chromium]'
    assert rm._expected_trace_path(nodeid) == \
        Path('reports') / 'artifacts' / 'tests-ui-x.py-test_t-chromium-trace.zip'


def test_expected_trace_path_keeps_the_150_cap():
    """The trace cap is conftest's 150, not the screenshot's 120."""
    path = rm._expected_trace_path('y' * 300)
    stem = path.name.removesuffix('-trace.zip')
    assert len(stem) == 150


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

def test_capture_filename_shape():
    """A mid-drag frame is named <stem>__<suffix>__mid-drag-<n>.png."""
    name = rm._capture_filename('tests/ui/x.py::test_t[chromium]',
                                'FAILED', 'mid-drag', 1)
    assert name == 'tests-ui-x.py-test_t-chromium__FAILED__mid-drag-1.png'


def test_capture_filename_reuses_the_capped_safe_stem():
    """Longest possible name: 120-char stem + SETUP_FAILED + index. At 150
    chars the absolute path stays under Windows' 260 from this checkout."""
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
