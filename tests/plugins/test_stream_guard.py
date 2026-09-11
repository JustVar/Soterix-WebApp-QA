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


class FakeItem:
    def __init__(self, *marks: str) -> None:
        self.keywords = dict.fromkeys(marks, True)
        self.markers: list = []

    def add_marker(self, marker) -> None:
        self.markers.append(marker)

    @property
    def skip_reasons(self) -> list[str]:
        return [m.kwargs.get('reason', '') for m in self.markers if m.name == 'skip']


def _config(collect_only: bool = False, channel: str | None = 'chrome'):
    def getoption(name, default=None):
        return {'--collect-only': collect_only, '--browser-channel': channel}.get(name, default)
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
    assert 'Windows or Mac' in reason
    assert sh.stream_skip_reason({**DEAD, 'decodes': False, 'browser': 'x'}, 'us').startswith('box us streams H.265')


def test_frames_mean_no_skip_and_so_does_a_failed_measurement():
    """Frames arrived and the browser decodes: run. Could not measure: run too, and say so."""
    assert sh.stream_skip_reason(ALIVE, 'us') is None
    assert sh.stream_skip_reason({**ALIVE, 'decodes': None}, 'us') is None   # unknown codec: no verdict on decoding
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
    monkeypatch.setattr(sh, 'decode_check', lambda codec, channel: pytest.fail('browser opened'))
    out = sh.assess('x', 'chrome')
    assert (out['decodes'], out['browser']) == (None, None)


def test_guard_switch_reads_off_values_only():
    """STREAM_GUARD is on unless it says off, 0, false or no."""
    assert sh.guard_enabled({}) is True
    assert sh.guard_enabled({'STREAM_GUARD': 'on'}) is True
    for value in ('off', '0', 'false', 'no', 'OFF'):
        assert sh.guard_enabled({'STREAM_GUARD': value}) is False, value


# ---------------------------------------------------------------- the hook

def test_hook_measures_once_and_skips_only_the_livestream_tests(monkeypatch):
    """One assessment per session with the session's browser channel; only the
    livestream items get the skip, with the same reason."""
    calls: list = []
    monkeypatch.setattr(sh, 'assess', lambda camera, channel, seconds=8: (calls.append((camera, channel)), dict(DEAD))[1])
    monkeypatch.setattr(conftest, 'ENV_SETTINGS', {'test_camera_name': 'Soterix Multicam 1.15'})
    monkeypatch.delenv('STREAM_GUARD', raising=False)
    items = [FakeItem('livestream', 'views'), FakeItem('views'), FakeItem('livestream')]
    conftest.stream_guard(_config(), items, 'us')
    assert calls == [('Soterix Multicam 1.15', 'chrome')]
    assert items[0].skip_reasons == [sh.stream_skip_reason(DEAD, 'us')]
    assert items[2].skip_reasons == items[0].skip_reasons
    assert items[1].markers == []


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
    monkeypatch.setattr(sh, 'assess', lambda camera, channel, seconds=8: dict(UNMEASURED))
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
