"""Unit tests for plugins/single_run_guard.py.

The full decision matrix (free / held-by-live / held-by-stale / re-entrant /
collect-only / xdist worker / kill switch), the blocked message, and the
session hooks run against fakes and a temp lock dir - no browser, no
subprocesses. The guard exists because a second pytest beside a live run
wipes the first run's screenshots and run.log. A wrapper that holds the
lock and launches pytest is pinned at the consumer end: its child honors
the marker or the parent PID through decide().

Living under tests/plugins/ to be picked up by the default discovery
without needing a new test root or collection config.
"""
from __future__ import annotations

import json
import logging
import os
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
from _pytest.outcomes import Exit

# Ensure the repo root is importable so `plugins.single_run_guard` resolves
# the same way pytest itself loads it during a real run.
REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from plugins import single_run_guard as guard  # noqa: E402
from tools import run_lock  # noqa: E402

# Fakes for the injectable checks: liveness and staleness are decided by
# tools/run_lock.py in production; here each case pins one answer.

def _alive(pid):
    return True


def _dead(pid):
    return False


def _fresh(info, timeout):
    return False


def _stale(info, timeout):
    return True


OWN_PID = 4000
PARENT_PID = 3000
RIVAL_PID = 5000


def _lock(pid=RIVAL_PID, age_hours=0.0, **extra) -> dict:
    """A lock dict shaped like tools/run_lock.py writes it."""
    acquired = datetime.now(UTC) - timedelta(hours=age_hours)
    return {'env': 'qa', 'pid': pid, 'user': 'tester', 'run_type': 'manual',
            'acquired_at': acquired.isoformat(), 'hostname': 'lab-laptop', **extra}


def _decide(existing, environ=None, collect_only=False, pid_alive=_alive,
            is_stale=_fresh):
    action, _reason = guard.decide(existing, environ=environ or {},
                                   collect_only=collect_only, own_pid=OWN_PID,
                                   parent_pid=PARENT_PID, pid_alive=pid_alive,
                                   is_stale=is_stale)
    return action


# ---------------------------------------------------------------------------
# Decision matrix
# ---------------------------------------------------------------------------

def test_free_lock_is_acquired():
    """With no lock on disk, the run takes the lock."""
    assert _decide(None) == guard.ACQUIRE


def test_live_rival_blocks():
    """A lock held by a live rival process blocks the run."""
    assert _decide(_lock()) == guard.BLOCK


def test_stale_lock_is_reclaimed():
    """Same rule as run_lock.acquire: staleness beats liveness, so a lock
    past the timeout is reclaimed even if its holder still shows alive."""
    assert _decide(_lock(), is_stale=_stale) == guard.ACQUIRE


def test_dead_holder_is_reclaimed():
    """A lock whose holder is dead is reclaimed."""
    assert _decide(_lock(), pid_alive=_dead) == guard.ACQUIRE


def test_pidless_lock_is_reclaimed():
    """A lock with no recorded holder cannot be verified as a live run, and
    the guard only ever blocks on a verified one - it fails open."""
    assert _decide(_lock(pid=0)) == guard.ACQUIRE
    assert _decide({'acquired_at': datetime.now(UTC).isoformat()}) == guard.ACQUIRE


def test_own_pid_in_the_lock_is_reclaimed():
    """A lock recording this very process cannot be a rival run."""
    assert _decide(_lock(pid=OWN_PID)) == guard.ACQUIRE


def test_parent_held_lock_is_reentrant():
    """The pid-chain half of re-entrancy: a wrapper that holds the lock and
    launches pytest directly is our parent process, so its lock is ours to
    run under - not a rival to abort on."""
    assert _decide(_lock(pid=PARENT_PID)) == guard.SKIP


def test_marker_env_var_is_reentrant():
    """The marker half of re-entrancy: a wrapper that holds the lock exports
    RUN_GUARD_HELD to its pytest child, and the child stands aside on it."""
    assert guard.HELD_MARKER == 'RUN_GUARD_HELD'
    assert _decide(_lock(), environ={'RUN_GUARD_HELD': '3000'}) == guard.SKIP


def test_collect_only_skips_even_when_blocked():
    """A collect-only pass may run while a lock is active; collection
    writes nothing shared, so it must never be refused."""
    assert _decide(_lock(), collect_only=True) == guard.SKIP


def test_xdist_worker_skips_even_when_blocked():
    """The controller holds the lock for the whole run - a worker seeing
    the controller's lock as a rival would deadlock every -n run."""
    assert _decide(_lock(), environ={'PYTEST_XDIST_WORKER': 'gw0'}) == guard.SKIP


@pytest.mark.parametrize('value', ['off', 'OFF', 'Off', '0', 'false', 'no', ' off '])
def test_kill_switch_off_values_skip_even_when_blocked(value):
    """RUN_GUARD=off, in any spelling, stands the guard down even against a rival."""
    assert _decide(_lock(), environ={'RUN_GUARD': value}) == guard.SKIP


@pytest.mark.parametrize('value', ['', 'on', '1', 'true', 'anything-else'])
def test_kill_switch_on_values_leave_the_guard_active(value):
    """Any RUN_GUARD value other than an off word leaves the guard active."""
    assert _decide(None, environ={'RUN_GUARD': value}) == guard.ACQUIRE
    assert _decide(_lock(), environ={'RUN_GUARD': value}) == guard.BLOCK


def test_real_staleness_check_is_the_default():
    """With no fakes injected, decide uses run_lock's own staleness rule:
    a missing or ancient acquired_at reclaims, a fresh one blocks."""
    assert guard.decide(_lock(age_hours=100), environ={}, collect_only=False,
                        own_pid=OWN_PID, parent_pid=PARENT_PID,
                        pid_alive=_alive)[0] == guard.ACQUIRE
    assert guard.decide(_lock(age_hours=0), environ={}, collect_only=False,
                        own_pid=OWN_PID, parent_pid=PARENT_PID,
                        pid_alive=_alive)[0] == guard.BLOCK


# ---------------------------------------------------------------------------
# Lock env resolution
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(('environ', 'expected'), [
    ({}, 'qa'),                        # no ENV set - matches config's default
    ({'ENV': 'qa'}, 'qa'),
    ({'ENV': ' STAGE '}, 'stage'),     # trimmed and lower-cased, nothing else
    ({'ENV': 'Neurosen'}, 'neurosen'),
    ({'ENV': 'unknown-name'}, 'unknown-name'),  # any name passes through
])
def test_lock_env_is_env_as_written(environ, expected):
    """The lock is keyed on ENV as written, trimmed and lower-cased. No alias
    folds: the cross-env scan treats every other lock file as a rival, so two
    spellings of one environment still contend."""
    assert guard._lock_env(environ) == expected


# ---------------------------------------------------------------------------
# Blocked message
# ---------------------------------------------------------------------------

def test_blocked_message_names_the_holder_and_the_way_out():
    """The blocked message names the holder, its target, and how to release."""
    lock = _lock(target='-m smoke')
    msg = guard._blocked_message('qa', lock)
    assert 'Another test run is already active' in msg
    assert f'PID {RIVAL_PID}' in msg
    assert 'tester' in msg
    assert lock['acquired_at'] in msg  # when the rival started is shown
    assert '-m smoke' in msg
    assert 'python tools/run_lock.py release --env qa --force' in msg
    assert 'RUN_GUARD=off' in msg


def test_blocked_message_falls_back_to_run_type_for_the_target():
    """Without a recorded target, the message shows the run type instead."""
    msg = guard._blocked_message('stage', _lock())
    assert 'Target:      manual' in msg
    assert '--env stage --force' in msg


def test_blocked_message_survives_an_empty_lock():
    """An empty lock still yields a blocked message, without a blank Target line."""
    msg = guard._blocked_message('qa', {})
    assert 'Another test run is already active' in msg
    assert 'Target:' not in msg  # nothing recorded, no empty line shown


# ---------------------------------------------------------------------------
# Session hooks against a temp lock dir
# ---------------------------------------------------------------------------

class _FakePluginManager:
    """Just enough of pytest's pluginmanager for _mute_html_report."""

    def __init__(self, plugins=()):
        self.plugins = list(plugins)
        self.unregistered = []

    def get_plugins(self):
        return list(self.plugins)

    def unregister(self, plugin):
        self.unregistered.append(plugin)
        self.plugins.remove(plugin)


class _FakeConfig:
    """Just enough of pytest Config for the hooks: getoption, the invocation
    args the lock records, and a pluginmanager."""

    def __init__(self, collect_only=False, args=('-m', 'smoke'), plugins=()):
        self._collect_only = collect_only
        self.invocation_params = SimpleNamespace(args=tuple(args))
        self.pluginmanager = _FakePluginManager(plugins)

    def getoption(self, name, default=None):
        if name == '--collect-only':
            return self._collect_only
        return default


def _session(config=None):
    return SimpleNamespace(config=config or _FakeConfig())


@pytest.fixture
def lock_dir(tmp_path, monkeypatch):
    """Point the real lock file into tmp and scrub the ambient variables
    that would flip the decision - this suite itself may be running under
    a wrapper (marker set), under xdist, or with RUN_GUARD exported."""
    monkeypatch.setattr(run_lock, 'LOCK_DIR', tmp_path)
    for var in ('RUN_GUARD', 'RUN_GUARD_HELD', 'PYTEST_XDIST_WORKER'):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv('ENV', 'qa')
    return tmp_path


def _lock_file(lock_dir: Path) -> Path:
    return lock_dir / '.run_lock_qa.json'


def test_sessionstart_takes_the_lock_when_free(lock_dir):
    """Session start writes a lock with this pid, run type, and target."""
    config = _FakeConfig()
    guard.pytest_sessionstart(_session(config))
    written = json.loads(_lock_file(lock_dir).read_text())
    assert written['pid'] == os.getpid()
    assert written['run_type'] == 'pytest'
    assert written['target'] == '-m smoke'
    assert config._single_run_guard_env == 'qa'


def test_unconfigure_releases_the_lock_it_took(lock_dir):
    """Session end releases the lock this run took."""
    config = _FakeConfig()
    guard.pytest_sessionstart(_session(config))
    assert _lock_file(lock_dir).exists()
    guard.pytest_unconfigure(config)
    assert not _lock_file(lock_dir).exists()


def test_unconfigure_leaves_a_rival_relock_alone(lock_dir):
    """If our lock was force-released and a rival re-acquired, shutdown must
    not delete the rival's lock out from under its run."""
    config = _FakeConfig()
    guard.pytest_sessionstart(_session(config))
    run_lock._write_lock('qa', _lock())  # rival took over after a --force
    guard.pytest_unconfigure(config)
    assert json.loads(_lock_file(lock_dir).read_text())['pid'] == RIVAL_PID


def test_unconfigure_without_an_acquisition_is_a_no_op(lock_dir):
    """A run that never took the lock leaves the existing lock alone at exit."""
    run_lock._write_lock('qa', _lock())
    guard.pytest_unconfigure(_FakeConfig())
    assert _lock_file(lock_dir).exists()


def test_sessionstart_blocks_on_a_live_rival(lock_dir, monkeypatch):
    """Session start exits on a live rival and leaves its lock untouched."""
    monkeypatch.setattr(guard, '_pid_alive', _alive)
    run_lock._write_lock('qa', _lock(target='tests/ui/views'))
    config = _FakeConfig()
    with pytest.raises(Exit) as excinfo:
        guard.pytest_sessionstart(_session(config))
    assert 'Another test run is already active' in str(excinfo.value)
    assert str(RIVAL_PID) in str(excinfo.value)
    assert 'tests/ui/views' in str(excinfo.value)
    # The losing run changed nothing: rival's lock intact, nothing to release.
    assert json.loads(_lock_file(lock_dir).read_text())['pid'] == RIVAL_PID
    assert not hasattr(config, '_single_run_guard_env')


def test_a_blocked_run_mutes_the_html_report(lock_dir, monkeypatch):
    """pytest-html still writes at sessionfinish after pytest.exit, so the
    block path unregisters its writer - otherwise being refused would
    itself replace the last real report.html with an empty shell."""
    monkeypatch.setattr(guard, '_pid_alive', _alive)
    run_lock._write_lock('qa', _lock())

    class _FakeHtmlReport:
        pass
    _FakeHtmlReport.__module__ = 'pytest_html.selfcontained_report'
    html_writer = _FakeHtmlReport()
    bystander = SimpleNamespace()
    config = _FakeConfig(plugins=[html_writer, bystander])

    with pytest.raises(Exit):
        guard.pytest_sessionstart(_session(config))
    assert html_writer in config.pluginmanager.unregistered
    assert bystander not in config.pluginmanager.unregistered


def test_sessionstart_reclaims_a_stale_lock(lock_dir, monkeypatch):
    """Session start takes over a lock past the staleness timeout."""
    monkeypatch.setattr(guard, '_pid_alive', _alive)
    run_lock._write_lock('qa', _lock(age_hours=100))
    guard.pytest_sessionstart(_session())
    assert json.loads(_lock_file(lock_dir).read_text())['pid'] == os.getpid()


def test_sessionstart_skips_when_the_parent_holds_the_lock(lock_dir, monkeypatch):
    """Re-entrancy end to end: a wrapper holding the lock is this process's
    parent, so its pytest child starts cleanly and leaves the lock alone."""
    monkeypatch.setattr(guard, '_pid_alive', _alive)
    run_lock._write_lock('qa', _lock(pid=os.getppid()))
    config = _FakeConfig()
    guard.pytest_sessionstart(_session(config))
    assert json.loads(_lock_file(lock_dir).read_text())['pid'] == os.getppid()
    assert not hasattr(config, '_single_run_guard_env')


def test_sessionstart_honors_the_parent_marker(lock_dir, monkeypatch):
    """The wrapper handshake, consumer side: with RUN_GUARD_HELD exported
    the child neither blocks nor takes a lock of its own."""
    monkeypatch.setenv('RUN_GUARD_HELD', '4242')
    config = _FakeConfig()
    guard.pytest_sessionstart(_session(config))
    assert not _lock_file(lock_dir).exists()
    assert not hasattr(config, '_single_run_guard_env')


def test_sessionstart_skips_collect_only_runs(lock_dir, monkeypatch):
    """A collect-only session neither blocks nor touches the rival's lock."""
    monkeypatch.setattr(guard, '_pid_alive', _alive)
    run_lock._write_lock('qa', _lock())
    guard.pytest_sessionstart(_session(_FakeConfig(collect_only=True)))
    assert json.loads(_lock_file(lock_dir).read_text())['pid'] == RIVAL_PID


# ---------------------------------------------------------------------------
# The guard machinery failing must never block a run
# ---------------------------------------------------------------------------

def test_unreadable_lock_degrades_to_a_warning(lock_dir, monkeypatch, caplog):
    """An unreadable lock file warns and lets the run proceed unguarded."""
    def _boom(env):
        raise PermissionError('lock file is locked by an antivirus scan')
    monkeypatch.setattr(guard, '_read_lock', _boom)
    with caplog.at_level(logging.WARNING, logger='single_run_guard'):
        guard.pytest_sessionstart(_session())  # must not raise
    assert 'run proceeds unguarded' in caplog.text
    assert not _lock_file(lock_dir).exists()


def test_unwritable_lock_degrades_to_a_warning(lock_dir, monkeypatch, caplog):
    """A lock that cannot be written warns and lets the run proceed unguarded."""
    def _boom(env, info):
        raise OSError('read-only logs directory')
    monkeypatch.setattr(guard, '_write_lock', _boom)
    config = _FakeConfig()
    with caplog.at_level(logging.WARNING, logger='single_run_guard'):
        guard.pytest_sessionstart(_session(config))  # must not raise
    assert 'run proceeds unguarded' in caplog.text
    assert not hasattr(config, '_single_run_guard_env')


def test_release_failure_degrades_to_a_warning(lock_dir, monkeypatch, caplog):
    """A release failure at exit warns instead of raising."""
    config = _FakeConfig()
    guard.pytest_sessionstart(_session(config))

    def _boom(env):
        raise OSError('file handle held open')
    monkeypatch.setattr(guard, '_read_lock', _boom)
    with caplog.at_level(logging.WARNING, logger='single_run_guard'):
        guard.pytest_unconfigure(config)  # must not raise
    assert 'backstops' in caplog.text


# ---------------------------------------------------------------------------
# Liveness probe (the BLOCK decision's key input, from tools/run_lock.py)
# ---------------------------------------------------------------------------

def test_pid_alive_sees_this_very_process():
    """Pins the Windows fix: os.kill(pid, 0) there is CTRL_C_EVENT, which
    reported even this process as dead - so the guard could never block."""
    assert run_lock._pid_alive(os.getpid()) is True


@pytest.mark.skipif(sys.platform != 'win32', reason='Windows liveness probe')
def test_pid_alive_reads_access_denied_as_alive():
    """PID 4 is the Windows System process: real, alive, and not openable
    with our rights. Denial must read as alive - never as a dead holder
    whose lock is free to reclaim."""
    assert run_lock._pid_alive(4) is True


# ---------------------------------------------------------------- cross-env

class TestCrossEnvRival:
    """The artifacts are repo-global, so a live foreign-env lock is a rival.

    cross_env_rival reuses decide() per foreign lock; these pins fix the
    verdicts for the live / stale / dead / parent-held foreign cases.
    """

    def _rival(self, existing, pid_alive=_alive, is_stale=_fresh):
        return guard.cross_env_rival(
            'qa', environ={}, own_pid=OWN_PID, parent_pid=PARENT_PID,
            read_lock=lambda env: existing if env == 'stage' else None,
            lock_envs=['stage'], pid_alive=pid_alive, is_stale=is_stale)

    def test_live_foreign_holder_is_a_rival(self):
        """A live lock in another env is a rival, reported with its env and pid."""
        found = self._rival(_lock(pid=RIVAL_PID))
        assert found is not None
        env, lock = found
        assert env == 'stage'
        assert lock['pid'] == RIVAL_PID

    def test_stale_foreign_lock_is_not_a_rival(self):
        """A stale foreign lock is not a rival."""
        assert self._rival(_lock(pid=RIVAL_PID), is_stale=_stale) is None

    def test_dead_foreign_holder_is_not_a_rival(self):
        """A foreign lock whose holder is dead is not a rival."""
        assert self._rival(_lock(pid=RIVAL_PID), pid_alive=_dead) is None

    def test_parent_held_foreign_lock_is_not_a_rival(self):
        """A foreign lock held by the parent process is not a rival."""
        assert self._rival(_lock(pid=PARENT_PID)) is None

    def test_no_foreign_locks_scans_clean(self):
        """With no foreign locks, the cross-env scan finds no rival."""
        assert guard.cross_env_rival(
            'qa', environ={}, own_pid=OWN_PID, parent_pid=PARENT_PID,
            read_lock=lambda env: None, lock_envs=[]) is None


# ---------------------------------------------------------------------------
# Heartbeat: the lock's sign of life is test progress
# ---------------------------------------------------------------------------

def _report(when='call'):
    return SimpleNamespace(when=when)


def test_staleness_reads_the_heartbeat_when_present():
    """An old lock with a fresh heartbeat is alive; a lock whose heartbeat
    itself is old is stale; without a heartbeat acquired_at decides."""
    fresh_beat = datetime.now(UTC).isoformat()
    old_beat = (datetime.now(UTC) - timedelta(hours=5)).isoformat()
    assert run_lock._is_stale(_lock(age_hours=100, heartbeat_at=fresh_beat), 4) is False
    assert run_lock._is_stale(_lock(age_hours=100, heartbeat_at=old_beat), 4) is True
    assert run_lock._is_stale(_lock(age_hours=1), 4) is False
    assert run_lock._is_stale(_lock(age_hours=100), 4) is True


def test_beat_stamps_only_a_lock_that_records_a_holder_pid(lock_dir):
    """A rival's lock is never revived by our stamp."""
    run_lock._write_lock('qa', _lock(pid=RIVAL_PID))
    assert run_lock.beat('qa', {OWN_PID}) is False
    assert 'heartbeat_at' not in json.loads(_lock_file(lock_dir).read_text())
    assert run_lock.beat('qa', {RIVAL_PID}) is True
    assert json.loads(_lock_file(lock_dir).read_text())['heartbeat_at']


def test_a_test_report_stamps_the_lock_the_session_took(lock_dir, monkeypatch):
    """Session start arms the heartbeat; the first report stamps the lock."""
    monkeypatch.setattr(guard, '_beat_state', None)
    config = _FakeConfig()
    guard.pytest_sessionstart(_session(config))
    assert 'heartbeat_at' not in json.loads(_lock_file(lock_dir).read_text())
    guard.pytest_runtest_logreport(_report())
    written = json.loads(_lock_file(lock_dir).read_text())
    assert written['pid'] == os.getpid()
    assert written['heartbeat_at']
    guard.pytest_unconfigure(config)
    assert guard._beat_state is None


def test_reports_are_throttled_to_the_interval(lock_dir, monkeypatch):
    """A second report inside the interval writes nothing."""
    monkeypatch.setattr(guard, '_beat_state', None)
    monkeypatch.setattr(guard, 'HEARTBEAT_INTERVAL_S', 3600)
    config = _FakeConfig()
    guard.pytest_sessionstart(_session(config))
    guard.pytest_runtest_logreport(_report())
    first = json.loads(_lock_file(lock_dir).read_text())['heartbeat_at']
    run_lock._write_lock('qa', {**json.loads(_lock_file(lock_dir).read_text()), 'heartbeat_at': 'untouched'})
    guard.pytest_runtest_logreport(_report())
    assert json.loads(_lock_file(lock_dir).read_text())['heartbeat_at'] == 'untouched'
    assert first
    guard.pytest_unconfigure(config)


def test_reports_never_revive_a_rivals_lock(lock_dir, monkeypatch):
    """Our lock was force-released and a rival took over: our reports must
    not stamp the rival's lock."""
    monkeypatch.setattr(guard, '_beat_state', None)
    monkeypatch.setattr(guard, 'HEARTBEAT_INTERVAL_S', 0)
    config = _FakeConfig()
    guard.pytest_sessionstart(_session(config))
    run_lock._write_lock('qa', _lock())
    guard.pytest_runtest_logreport(_report())
    assert 'heartbeat_at' not in json.loads(_lock_file(lock_dir).read_text())
    guard.pytest_unconfigure(config)


def test_reports_stamp_the_parents_lock_under_the_marker(lock_dir, monkeypatch):
    """A child under a wrapper's lock keeps that lock alive: the parent
    only waits on the child and would otherwise go stale at 4 h."""
    monkeypatch.setattr(guard, '_beat_state', None)
    monkeypatch.setenv('RUN_GUARD_HELD', '4242')
    run_lock._write_lock('qa', _lock(pid=4242))
    guard.pytest_sessionstart(_session(_FakeConfig()))
    guard.pytest_runtest_logreport(_report())
    written = json.loads(_lock_file(lock_dir).read_text())
    assert written['pid'] == 4242
    assert written['heartbeat_at']
    guard.pytest_unconfigure(_FakeConfig())


def test_reports_stamp_the_lock_the_parent_process_holds(lock_dir, monkeypatch):
    """The wrapper that predates the marker: the lock records our parent PID."""
    monkeypatch.setattr(guard, '_beat_state', None)
    monkeypatch.setattr(guard, '_pid_alive', _alive)
    run_lock._write_lock('qa', _lock(pid=os.getppid()))
    guard.pytest_sessionstart(_session(_FakeConfig()))
    guard.pytest_runtest_logreport(_report())
    written = json.loads(_lock_file(lock_dir).read_text())
    assert written['pid'] == os.getppid()
    assert written['heartbeat_at']
    guard.pytest_unconfigure(_FakeConfig())


@pytest.mark.parametrize(('var', 'value'), [('PYTEST_XDIST_WORKER', 'gw0'), ('RUN_GUARD', 'off')])
def test_a_run_standing_aside_arms_nothing(lock_dir, monkeypatch, var, value):
    """xdist workers and RUN_GUARD=off runs hold no lock, arm no heartbeat
    and stamp nothing, even on a lock that records their parent."""
    monkeypatch.setattr(guard, '_beat_state', None)
    monkeypatch.setenv(var, value)
    run_lock._write_lock('qa', _lock(pid=os.getppid()))
    guard.pytest_sessionstart(_session(_FakeConfig()))
    assert guard._beat_state is None
    guard.pytest_runtest_logreport(_report())
    assert 'heartbeat_at' not in json.loads(_lock_file(lock_dir).read_text())


def test_the_first_report_stamps_on_a_box_just_booted(lock_dir, monkeypatch):
    """monotonic counts from boot; an uptime under the interval must not
    swallow the first stamp (the CI runner's, 09/14/2026)."""
    monkeypatch.setattr(guard, '_beat_state', None)
    monkeypatch.setattr(guard.time, 'monotonic', lambda: 5.0)
    config = _FakeConfig()
    guard.pytest_sessionstart(_session(config))
    guard.pytest_runtest_logreport(_report())
    assert json.loads(_lock_file(lock_dir).read_text())['heartbeat_at']
    guard.pytest_unconfigure(config)


def test_the_lock_is_written_in_one_step(lock_dir):
    """The write goes through a temp file replaced over the lock, and the
    temp file does not survive."""
    run_lock._write_lock('qa', _lock())
    assert json.loads(_lock_file(lock_dir).read_text())['pid'] == RIVAL_PID
    assert [p.name for p in lock_dir.iterdir()] == ['.run_lock_qa.json']
