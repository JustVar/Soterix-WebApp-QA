"""Pins for the session stream-health guard (conftest.stream_guard and
tests/shared/helpers/stream_health.py): the decision is pure, the hook
measures once and only when it must, and a measurement that failed hides
nothing. Two facts feed it: the socket's frame count and whether the
session's browser decodes the codec the channel streams."""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import conftest  # noqa: E402
from tests.shared.helpers import stream_health as sh  # noqa: E402

DEAD = {'camera': 'Soterix Multicam 1.15', 'channel_id': 3120, 'frames': 0, 'seconds': 8, 'codec': 'H.265',
        'error': None, 'note': 'handshake refused: HTTP 1506 Failed to read response from the IVMS server',
        'decodes': True, 'browser': 'Chrome 152.0 on Windows'}
ALIVE = {**DEAD, 'frames': 41, 'note': None}
UNMEASURED = {**DEAD, 'error': 'ConnectionError: no route to host', 'decodes': None, 'browser': None}
NO_DECODER = {**ALIVE, 'decodes': False, 'browser': 'Chrome 153.0.8010.36 on Linux'}


@pytest.fixture(autouse=True)
def _own_summary_lines(monkeypatch):
    """These pins feed the guard made-up measurements; without this they landed in the real
    session's 'stream guard' summary, where '0 frames' and 'no route to host' read as real."""
    monkeypatch.setattr(conftest, '_STREAM_LINES', [])

class FakeItem:
    def __init__(self, *marks: str) -> None:
        self.keywords = dict.fromkeys(marks, True)
        self.markers: list = []

    def add_marker(self, marker) -> None:
        self.markers.append(marker)

    @property
    def skip_reasons(self) -> list[str]:
        return [m.kwargs.get('reason', '') for m in self.markers if m.name == 'skip']


def _config(collect_only: bool = False, channel: str | None = 'chrome', headed: bool = False):
    def getoption(name, default=None):
        return {'--collect-only': collect_only, '--browser-channel': channel, '--headed': headed}.get(name, default)
    return SimpleNamespace(getoption=getoption)


# ---------------------------------------------------------------- the decision

def test_no_frames_is_a_skip_that_carries_the_measurement():
    """The reason names the box, camera, channel, count, sample length and the socket's note."""
    reason = sh.stream_skip_reason(DEAD, 'us')
    assert reason.startswith("box us: the media socket for camera 'Soterix Multicam 1.15' (channel 3120) "
                             "delivered 0 frames in 8 s; media socket: handshake refused: HTTP 1506")
    assert 'STREAM_GUARD=off' in reason


def test_a_browser_without_the_decoder_is_a_skip_naming_the_codec_and_browser():
    """Frames flowing means nothing to a player that cannot decode them: the reason
    names the codec the box streams and the browser that answered false (spartan1's
    Chrome on Linux, 09/11/2026), and outranks the frame count."""
    reason = sh.stream_skip_reason(NO_DECODER, 'us')
    assert reason.startswith("box us streams H.265 on camera 'Soterix Multicam 1.15' and this browser "
                             "(Chrome 153.0.8010.36 on Linux) cannot decode it")
    assert 'Windows, Mac, or spartan1 headed on its Weston display' in reason
    assert sh.stream_skip_reason({**DEAD, 'decodes': False, 'browser': 'x'}, 'us').startswith('box us streams H.265')


def test_headless_on_windows_is_a_skip_even_though_the_codec_check_says_yes():
    """The one case where a true from the decode check is wrong.

    Headless Chrome on Windows answers MediaSource.isTypeSupported('hvc1') with
    true and then never decodes: the player holds readyState 1 and currentTime
    0.00 while the socket delivers frames. Measured 09/22/2026 on spartan20, the
    same test headless and headed minutes apart (register row 128). Before this
    rule the machine ran 28 tests red instead of skipping with a reason.
    """
    headless_win = {**ALIVE, 'decodes': True, 'os': 'Windows', 'headed': False,
                    'browser': 'Chrome 153.0.8010.53 on Windows, headless, 0 flags'}
    reason = sh.stream_skip_reason(headless_win, 'us')
    assert reason is not None, 'a machine that cannot play the tile must skip, not fail 28 tests'
    assert 'headless on Windows' in reason
    assert 'never decodes it' in reason
    assert 'readyState 1' in reason
    assert '--headed' in reason


def test_the_headless_windows_rule_does_not_catch_the_setups_that_work():
    """Narrow on purpose: it is one measured fact, not a guess about headless.

    Headed on Windows plays (measured, same run). Linux is spartan1's business:
    it runs headed on Weston, and a Linux browser that cannot decode already
    answers false, which the rule above it catches.
    """
    win = {**ALIVE, 'decodes': True, 'os': 'Windows', 'browser': 'Chrome 153 on Windows, headed, 0 flags'}
    assert sh.stream_skip_reason({**win, 'headed': True}, 'us') is None
    assert sh.stream_skip_reason({**win, 'os': 'Linux', 'headed': False}, 'us') is None
    # H.264 headless on Windows is not what was measured, so it is not claimed.
    assert sh.stream_skip_reason({**win, 'headed': False, 'codec': 'H.264'}, 'us') is None
    # And a measurement with no os/headed at all (an older record) still runs.
    assert sh.stream_skip_reason(ALIVE, 'us') is None


def test_frames_mean_no_skip_and_so_does_a_failed_measurement():
    """Frames arrived and the browser decodes: run. Could not measure: run too, and say so."""
    assert sh.stream_skip_reason(ALIVE, 'us') is None
    assert sh.stream_skip_reason(UNMEASURED, 'us') is None
    assert sh.describe(UNMEASURED).startswith("[STREAM] guard could not measure 'Soterix Multicam 1.15': ConnectionError")
    assert sh.describe(UNMEASURED).endswith('(no test skipped)')
    assert sh.describe(ALIVE) == ("[STREAM] 'Soterix Multicam 1.15' (channel 3120, H.265): 41 frames in 8 s; "
                                  "Chrome 152.0 on Windows decodes H.265: yes")
    assert sh.describe(NO_DECODER).endswith('decodes H.265: NO')


def test_measure_without_a_camera_name_is_an_error_not_a_skip():
    """No camera name in the env config is a measurement error, which skips nothing."""
    out = sh.measure_stream(None)
    assert out['error'].startswith('no test_camera_name')
    assert sh.stream_skip_reason(out, 'us') is None


def test_decode_check_without_a_known_codec_gives_no_verdict():
    """An unknown or missing codec opens no browser and decides nothing."""
    assert sh.decode_check(None, 'chrome') == {'decodes': None, 'browser': None}
    assert sh.decode_check('codecType 3', 'chrome') == {'decodes': None, 'browser': None}


def test_assess_skips_the_decode_check_when_the_measurement_failed(monkeypatch):
    """No browser is opened for a channel that could not be measured."""
    monkeypatch.setattr(sh, 'measure_stream', lambda camera, seconds=8: dict(UNMEASURED))
    monkeypatch.setattr(sh, 'decode_check', lambda codec, channel, headed=False: pytest.fail('browser opened'))
    out = sh.assess('x', 'chrome')
    assert (out['decodes'], out['browser']) == (None, None)


def test_guard_switch_reads_off_values_only():
    """STREAM_GUARD is on unless it says off, 0, false or no."""
    assert sh.guard_enabled({}) is True
    assert sh.guard_enabled({'STREAM_GUARD': 'on'}) is True
    for value in ('off', '0', 'false', 'no', 'OFF'):
        assert sh.guard_enabled({'STREAM_GUARD': value}) is False, value


# ---------------------------------------------------------------- the hook

def test_hook_measures_twice_on_an_empty_sample_and_skips_only_the_livestream_tests(monkeypatch):
    """An empty first sample earns a second one (the US camera read 0 frames
    and then 117 a minute apart, 09/12/2026); two empties skip the livestream
    items only, with the same reason, using the session's browser channel."""
    calls: list = []
    monkeypatch.setattr(sh, 'assess', lambda camera, channel, seconds=8, headed=False: (calls.append((camera, channel)), dict(DEAD))[1])
    monkeypatch.setattr(conftest, 'ENV_SETTINGS', {'test_camera_name': 'Soterix Multicam 1.15'})
    monkeypatch.delenv('STREAM_GUARD', raising=False)
    items = [FakeItem('livestream', 'views'), FakeItem('views'), FakeItem('livestream')]
    conftest.stream_guard(_config(), items, 'us')
    assert calls == [('Soterix Multicam 1.15', 'chrome')] * 2
    assert items[0].skip_reasons == [sh.stream_skip_reason(DEAD, 'us')]
    assert items[2].skip_reasons == items[0].skip_reasons
    assert items[1].markers == []


def test_hook_measures_once_when_the_stream_is_alive(monkeypatch):
    """A first sample with frames is the measurement: one call, no skips."""
    calls: list = []
    monkeypatch.setattr(sh, 'assess', lambda camera, channel, seconds=8, headed=False: (calls.append((camera, channel)), dict(ALIVE))[1])
    monkeypatch.setattr(conftest, 'ENV_SETTINGS', {'test_camera_name': 'Soterix Multicam 1.15'})
    monkeypatch.delenv('STREAM_GUARD', raising=False)
    items = [FakeItem('livestream', 'views'), FakeItem('views')]
    conftest.stream_guard(_config(), items, 'us')
    assert calls == [('Soterix Multicam 1.15', 'chrome')]
    assert items[0].markers == []
    assert items[1].markers == []


def test_hook_second_sample_with_frames_skips_nothing(monkeypatch):
    """An empty first sample and a live second one: the session runs."""
    answers = [dict(DEAD), dict(ALIVE)]
    monkeypatch.setattr(sh, 'assess', lambda camera, channel, seconds=8, headed=False: answers.pop(0))
    monkeypatch.setattr(conftest, 'ENV_SETTINGS', {'test_camera_name': 'Soterix Multicam 1.15'})
    monkeypatch.delenv('STREAM_GUARD', raising=False)
    items = [FakeItem('livestream', 'views')]
    conftest.stream_guard(_config(), items, 'us')
    assert answers == []
    assert items[0].markers == []


def test_hook_does_not_measure_without_a_livestream_test_or_on_collect_only_or_when_off(monkeypatch):
    """No livestream item, --collect-only, or STREAM_GUARD=off: the socket is never opened."""
    monkeypatch.setattr(sh, 'assess', lambda *a, **k: pytest.fail('measured'))
    monkeypatch.setattr(conftest, 'ENV_SETTINGS', {'test_camera_name': 'x'})
    monkeypatch.delenv('STREAM_GUARD', raising=False)
    conftest.stream_guard(_config(), [FakeItem('views')], 'us')                  # nothing to guard
    conftest.stream_guard(_config(collect_only=True), [FakeItem('livestream')], 'us')
    monkeypatch.setenv('STREAM_GUARD', 'off')
    item = FakeItem('livestream')
    conftest.stream_guard(_config(), [item], 'us')
    assert item.markers == []


def test_hook_keeps_the_tests_when_the_measurement_failed(monkeypatch, capsys):
    """A failed measurement leaves every test to run and says so on the terminal."""
    monkeypatch.setattr(sh, 'assess', lambda camera, channel, seconds=8, headed=False: dict(UNMEASURED))
    monkeypatch.setattr(conftest, 'ENV_SETTINGS', {'test_camera_name': 'x'})
    monkeypatch.delenv('STREAM_GUARD', raising=False)
    item = FakeItem('livestream')
    conftest.stream_guard(_config(), [item], 'us')
    assert item.markers == []
    assert 'guard could not measure' in capsys.readouterr().out


def test_livestream_marker_is_registered_with_the_guard_in_its_text():
    """pytest.ini describes the marker with the guard and its switch."""
    text = (REPO_ROOT / 'pytest.ini').read_text(encoding='utf-8')
    line = next(ln for ln in text.splitlines() if ln.strip().startswith('livestream:'))
    assert 'STREAM_GUARD=off' in line


def test_frames_with_no_decode_verdict_is_a_skip_that_says_what_was_unconfirmed():
    """An unknown codec, or a decode check that did not run, must not let the
    livestream tests run: on 09/17/2026 Thermal-14's codecType 2 was unmapped, the
    check gave no verdict, the tests ran against a tile Linux Chrome cannot decode,
    and three of four workers died on the after-test screenshot (four-hour cap)."""
    unknown = sh.stream_skip_reason({**ALIVE, 'codec': 'codecType 2', 'decodes': None, 'browser': None}, 'india')
    assert unknown
    assert 'could not be confirmed' in unknown
    assert 'codecType 2' in unknown
    unrun = sh.stream_skip_reason({**ALIVE, 'codec': 'H.265', 'decodes': None,
                                   'browser': 'check failed: TimeoutError'}, 'india')
    assert unrun
    assert 'decode check did not run' in unrun
    assert 'TimeoutError' in unrun
    # a real verdict still rules: decodes True runs, False skips
    assert sh.stream_skip_reason({**ALIVE, 'codec': 'H.265', 'decodes': True}, 'us') is None


def test_codec_is_read_from_the_socket_init_segment_not_the_parameter_map():
    """The frames say hvc1: the guard reports H.265 whatever codecType the channel parameters carried."""
    seen = {}

    def fake_parse(buf):
        seen['buf'] = buf
        return {'codec': 'H.265 (HEVC)'}

    import tools.stream_probe as sp
    orig = sp.parse_init_segment
    sp.parse_init_segment = fake_parse
    try:
        frames = [{'opcode': 2, 'data': b'ftyp...moov...'}, {'opcode': 2, 'data': b'moof'}]
        assert sh.codec_from_frames(frames) == 'H.265'
        assert seen['buf'].startswith(b'ftyp')
        sp.parse_init_segment = lambda buf: {'codec': 'H.264 (AVC)'}
        assert sh.codec_from_frames(frames) == 'H.264'
        sp.parse_init_segment = lambda buf: {}
        assert sh.codec_from_frames(frames) is None
    finally:
        sp.parse_init_segment = orig
    assert sh.codec_from_frames([]) is None
    assert sh.CODEC_TYPES[2] == 'H.265'


# ---------------------------------------------------------------- the session's Chrome flags

def test_chrome_args_come_from_the_environment_and_default_to_none():
    """CHROME_ARGS is the one variable every Chrome the suite opens reads; unset means no extra flag."""
    assert sh.chrome_args({}) == []
    assert sh.chrome_args({'CHROME_ARGS': ''}) == []
    flags = sh.chrome_args({'CHROME_ARGS': '--ozone-platform=wayland --enable-features=A,B  --use-angle=gl-egl'})
    assert flags == ['--ozone-platform=wayland', '--enable-features=A,B', '--use-angle=gl-egl']


def test_launch_args_gain_the_flags_and_keep_the_plugins_own():
    """The override appends to pytest-playwright's options and never drops headed or channel."""
    base = {'headless': False, 'channel': 'chrome', 'args': ['--x']}
    assert sh.launch_args_with_chrome_flags(base, {}) is base
    out = sh.launch_args_with_chrome_flags(base, {'CHROME_ARGS': '--a --b'})
    assert out == {'headless': False, 'channel': 'chrome', 'args': ['--x', '--a', '--b']}
    assert base['args'] == ['--x']


def test_decode_check_opens_the_browser_the_tests_get(monkeypatch):
    """The guard's verdict is worth nothing from a different browser: the check
    launches with the session's flags and headed-ness (spartan1 decodes H.265 only
    headed on Wayland with its flags, 09/17/2026)."""
    seen: dict = {}

    class Page:
        def goto(self, url):
            pass

        def evaluate(self, js, arg=None):
            return True

    class Browser:
        version = '153.0'

        def new_page(self):
            return Page()

        def close(self):
            pass

    class Chromium:
        def launch(self, **kw):
            seen.clear()
            seen.update(kw)
            return Browser()

    class PW:
        chromium = Chromium()

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

    import playwright.sync_api as api
    monkeypatch.setattr(api, 'sync_playwright', lambda: PW())
    monkeypatch.setenv('CHROME_ARGS', '--ozone-platform=wayland')
    out = sh.decode_check('H.265', 'chrome', headed=True)
    assert out['decodes'] is True
    assert seen == {'channel': 'chrome', 'headless': False, 'args': ['--ozone-platform=wayland']}
    assert out['browser'].endswith(', headed, 1 flag')
    sh.decode_check('H.265', 'chrome')
    assert seen['headless'] is True


def test_hook_passes_the_sessions_headedness_to_the_measurement(monkeypatch):
    """A --headed session is measured headed; the default session headless."""
    calls: list = []
    monkeypatch.setattr(sh, 'assess', lambda camera, channel, seconds=8, headed=False: (calls.append(headed), dict(ALIVE))[1])
    monkeypatch.setattr(conftest, 'ENV_SETTINGS', {'test_camera_name': 'Thermal-14'})
    monkeypatch.delenv('STREAM_GUARD', raising=False)
    conftest.stream_guard(_config(headed=True), [FakeItem('livestream')], 'india')
    conftest.stream_guard(_config(), [FakeItem('livestream')], 'india')
    assert calls == [True, False]


# ---------------------------------------------------------------- one measurement per run, shown in the summary

def _node(config):
    return SimpleNamespace(config=config, workerinput={})


def test_the_controller_measures_once_and_hands_it_to_every_worker(monkeypatch):
    """Four workers, one measurement: each gets the same JSON, and the lines are kept for the summary."""
    calls: list = []
    monkeypatch.setattr(sh, 'assess', lambda camera, channel, seconds=8, headed=False: (calls.append(1), dict(ALIVE))[1])
    monkeypatch.setattr(conftest, 'ENV_SETTINGS', {'test_camera_name': 'Thermal-14'})
    monkeypatch.setattr(conftest, '_may_collect_livestream', lambda config: True)
    monkeypatch.setattr(conftest, '_STREAM_LINES', [])
    monkeypatch.delenv('STREAM_GUARD', raising=False)
    config = _config()
    nodes = [_node(config) for _ in range(4)]
    for node in nodes:
        conftest.pytest_configure_node(node)
    assert calls == [1]
    assert len({n.workerinput[conftest.WORKER_MEASURE_KEY] for n in nodes}) == 1
    assert conftest._STREAM_LINES[0].startswith("[STREAM] 'Soterix Multicam 1.15'")


def test_a_worker_uses_the_controllers_measurement_and_measures_nothing(monkeypatch):
    """With the measurement in workerinput the worker skips on it and never calls assess."""
    import json
    monkeypatch.setattr(sh, 'assess', lambda *a, **k: pytest.fail('a worker measured'))
    monkeypatch.delenv('STREAM_GUARD', raising=False)
    config = _config()
    config.workerinput = {conftest.WORKER_MEASURE_KEY: json.dumps(DEAD)}
    items = [FakeItem('livestream'), FakeItem('views')]
    conftest.stream_guard(config, items, 'us')
    assert items[0].skip_reasons == [sh.stream_skip_reason(DEAD, 'us')]
    assert items[1].markers == []


def test_no_livestream_target_means_no_controller_measurement(monkeypatch, tmp_path):
    """A target with no livestream test costs no login, socket or Chrome launch; the marker in a file does."""
    (tmp_path / 'test_plain.py').write_text('def test_x(): pass\n', encoding='utf-8')
    config = SimpleNamespace(rootpath=tmp_path, args=[str(tmp_path)],
                             getoption=lambda name, default=None: default)
    assert conftest._may_collect_livestream(config) is False
    (tmp_path / 'test_live.py').write_text('import pytest\n@pytest.mark.livestream\ndef test_y(): pass\n', encoding='utf-8')
    assert conftest._may_collect_livestream(config) is True
    excluded = SimpleNamespace(rootpath=tmp_path, args=[str(tmp_path)],
                               getoption=lambda name, default=None: 'not livestream' if name == 'markexpr' else default)
    assert conftest._may_collect_livestream(excluded) is False


def test_every_run_has_a_per_test_cap():
    """pytest.ini carries --timeout, so a bare run cannot hang for good on one stuck browser call."""
    assert '--timeout=600' in (REPO_ROOT / 'pytest.ini').read_text(encoding='utf-8')

