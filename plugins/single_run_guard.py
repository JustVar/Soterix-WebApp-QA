"""Single-run guard -- pytest plugin.

Stops a second test run from starting while one is already active. Two
simultaneous runs share reports/report.html, reports/screenshots/, and
reports/artifacts/, so the slower run silently overwrites the faster run's
evidence. tools/run_suite.py and tools/guarded_run.py already serialize
their runs through the lock in tools/run_lock.py; this plugin takes the
same lock for bare `pytest` invocations, so every entry point contends on
one lock file (logs/.run_lock_<env>.json). Because the protected artifacts
are repo-global, the guard also refuses to start while a live run holds
ANY other environment's lock - an ENV=stage run corrupts a qa run's
report.html just the same.

A blocked run stops at session start, before any test executes, with:

    Another test run is already active - not starting this one.
      Environment: qa
      Holder:      <user> (PID <pid>), started <timestamp>
      Target:      <what that run is executing, when recorded>
    Two runs at once corrupt each other's report.html, screenshots, and traces.
    If that run is finished or dead, clear the lock with:
      python tools/run_lock.py release --env qa --force
    Kill switch (skips this guard entirely): RUN_GUARD=off

When the guard does start a run, it writes the lock at session start and
releases it at pytest shutdown. While tests report it stamps the lock's
heartbeat_at, at most once a minute, and it does the same for the parent's
lock when it runs under one (RUN_GUARD_HELD, or the lock records the parent
PID). A run that dies without releasing is covered by tools/run_lock.py's
backstops: a lock whose holder process is dead, or whose last sign of life
(the heartbeat, else acquired_at) is older than the 4-hour staleness
timeout, is cleared automatically by the next run. The sign of life is
test progress on purpose: a live run past 4 h keeps its lock, a hung run
does not (before 09/14/2026 nothing refreshed the lock, so a long live run
lost it).

The guard stands aside - no lock taken, run proceeds - when:
  - RUN_GUARD=off (kill switch; same off values as REPORT_SCREENSHOTS);
  - the run is --collect-only (nothing shared gets written; this is also
    what keeps run_suite's planning pass out of the lock's way);
  - RUN_GUARD_HELD is set (a parent such as tools/run_suite.py already
    holds the lock and exported the marker to its pytest child);
  - the lock holder is this process's direct parent (same re-entrancy for
    a wrapper that predates the marker, e.g. tools/guarded_run.py);
  - running as a pytest-xdist worker (the controller holds for the run).

The guard is protection, not testing: when the guard machinery itself
fails - lock file unreadable, permission denied - it logs a warning and
lets the run proceed. It only ever blocks when another live run really
holds the lock.
"""
from __future__ import annotations

import logging
import os
import time
from collections.abc import Mapping
from typing import Any

import pytest

from tools.run_lock import (
    DEFAULT_TIMEOUT_HOURS,
    HEARTBEAT_INTERVAL_S,
    _holder_info,
    _is_stale,
    _pid_alive,
    _read_lock,
    _remove_lock,
    _write_lock,
    beat,
)

log = logging.getLogger('single_run_guard')

# The lock this session stamps as tests report: (env, the PIDs the lock may
# record: this process, or the parent whose lock this run runs under). Set
# at session start, cleared at unconfigure; None means nothing to stamp.
_beat_state: dict | None = None

# Kill switch: same off-values idiom as plugins/report_media.py.
_OFF_VALUES = ('off', '0', 'false', 'no')

# Exported by a parent (tools/run_suite.py) that already holds the run lock,
# so the pytest child it launches treats that lock as its own instead of
# aborting on it.
HELD_MARKER = 'RUN_GUARD_HELD'

# decide() actions
SKIP = 'skip'
ACQUIRE = 'acquire'
BLOCK = 'block'

# Same aliases as config.base_config.ENV_ALIAS, collapsed to the env names
# tools/run_lock.py locks on - every spelling of an environment has to land
# on the same lock file or two runs against one box would not contend.
_ENV_LOCK_NAMES = {
    'staging': 'stage',
    'uat': 'stage',
    'production': 'prod',
    'demo': 'prod',
    'user': 'prod',
}


def _guard_disabled(environ: Mapping[str, str]) -> bool:
    """Kill switch: RUN_GUARD=off turns the whole guard off."""
    return environ.get('RUN_GUARD', '').strip().lower() in _OFF_VALUES


def _lock_env(environ: Mapping[str, str]) -> str:
    """The environment name the lock file is keyed on, resolved from ENV."""
    raw = (environ.get('ENV') or 'qa').strip().lower()
    return _ENV_LOCK_NAMES.get(raw, raw)


def decide(existing: dict | None, *, environ: Mapping[str, str], collect_only: bool,
           own_pid: int, parent_pid: int, pid_alive=None, is_stale=None) -> tuple[str, str]:
    """Return (action, reason) for this session: SKIP, ACQUIRE, or BLOCK.

    Pure decision - no filesystem access, no exits - so the whole matrix is
    unit-testable (tests/plugins/test_single_run_guard.py). pid_alive and
    is_stale are injectable for the same reason; the defaults are the real
    checks from tools/run_lock.py, resolved at call time so tests can also
    patch them on this module.
    """
    if pid_alive is None:
        pid_alive = _pid_alive
    if is_stale is None:
        is_stale = _is_stale

    if _guard_disabled(environ):
        return SKIP, 'RUN_GUARD=off'
    if collect_only:
        return SKIP, 'collect-only run - nothing shared is written'
    if environ.get('PYTEST_XDIST_WORKER'):
        return SKIP, 'xdist worker - the controller holds the lock for the run'
    if environ.get(HELD_MARKER):
        return SKIP, f'{HELD_MARKER} set - the parent run already holds the lock'
    if existing is None:
        return ACQUIRE, 'lock is free'
    if is_stale(existing, DEFAULT_TIMEOUT_HOURS):
        return ACQUIRE, 'stale lock - older than the staleness backstop'
    holder = existing.get('pid') or 0
    if holder == own_pid:
        return ACQUIRE, 'lock records this process - it cannot be a rival run'
    if not holder or not pid_alive(holder):
        # A lock with no live, verifiable holder cannot be a running rival.
        # Failing open here is deliberate: the guard must only ever block
        # when another run really is active.
        return ACQUIRE, 'holder process is dead or unrecorded'
    if holder == parent_pid:
        return SKIP, 'lock held by our parent process - re-entrant run'
    return BLOCK, f'held by live PID {holder}'


def _other_lock_envs(env_name: str) -> list[str]:
    """Env names of every OTHER lock file currently on disk."""
    from tools.run_lock import LOCK_DIR
    prefix = '.run_lock_'
    envs = []
    try:
        for path in LOCK_DIR.glob(f'{prefix}*.json'):
            other = path.name[len(prefix):-len('.json')]
            if other and other != env_name:
                envs.append(other)
    except OSError as e:
        log.debug(f'single_run_guard: lock-dir scan failed: {e}')
    return sorted(envs)


def cross_env_rival(env_name: str, *, environ: Mapping[str, str], own_pid: int,
                    parent_pid: int, read_lock=None, lock_envs=None,
                    pid_alive=None, is_stale=None):
    """A live rival holding ANY other environment's lock, or None.

    The artifacts the guard protects (report.html, screenshots/, artifacts/)
    are repo-global, so a stage run corrupts a qa run just the same - the
    per-env lock keying exists for run_suite's own semantics, not because
    the blast radius is per-env. Each foreign lock goes through the same
    decide() matrix; only a BLOCK verdict (live, non-parent holder) makes
    it a rival, so stale and dead foreign locks stand aside as usual.
    """
    if read_lock is None:
        read_lock = _read_lock
    if lock_envs is None:
        lock_envs = _other_lock_envs(env_name)
    for other in lock_envs:
        existing = read_lock(other)
        if existing is None:
            continue
        action, _ = decide(existing, environ=environ, collect_only=False,
                           own_pid=own_pid, parent_pid=parent_pid,
                           pid_alive=pid_alive, is_stale=is_stale)
        if action == BLOCK:
            return other, existing
    return None


def _invocation_target(config: Any) -> str:
    """The pytest command line, recorded so a blocked rival can name us.

    Capped so a long -k expression cannot bloat the lock file.
    """
    try:
        return ' '.join(str(a) for a in config.invocation_params.args)[:200]
    except Exception:  # noqa: BLE001 - the target is a nicety, never worth failing for
        return ''


def _blocked_message(env_name: str, existing: Mapping[str, Any]) -> str:
    """The message a blocked run exits with. Kept in step with the module doc."""
    holder = existing.get('user', 'unknown')
    pid = existing.get('pid', '?')
    started = existing.get('acquired_at', 'an unknown time')
    target = existing.get('target') or existing.get('run_type') or ''
    lines = [
        'Another test run is already active - not starting this one.',
        f'  Environment: {env_name}',
        f'  Holder:      {holder} (PID {pid}), started {started}',
    ]
    if target:
        lines.append(f'  Target:      {target}')
    lines += [
        "Two runs at once corrupt each other's report.html, screenshots, and traces.",
        'If that run is finished or dead, clear the lock with:',
        f'  python tools/run_lock.py release --env {env_name} --force',
        'Kill switch (skips this guard entirely): RUN_GUARD=off',
    ]
    return '\n'.join(lines)


def _mute_html_report(config: Any) -> None:
    """Best-effort: keep a blocked run from writing an empty report.html.

    pytest-html writes its report at sessionfinish, which still runs after
    pytest.exit - so without this, being blocked would itself overwrite the
    last real report with a 0-test shell (the same wipe class as run_suite's
    old planning pass). Unregistering the report writer prevents the write;
    if pytest-html's internals ever change shape, failing here only means
    the empty report gets written - never that the block is lost.
    """
    try:
        pm = config.pluginmanager
        for plugin in list(pm.get_plugins()):
            if type(plugin).__module__.startswith('pytest_html'):
                pm.unregister(plugin)
    except Exception as e:  # noqa: BLE001 - muting is a nicety on an exit path
        log.debug(f'single_run_guard: could not mute the html report: {e}')


@pytest.hookimpl(tryfirst=True)
def pytest_sessionstart(session: Any) -> None:
    """Take the run lock before any other plugin touches shared artifacts.

    tryfirst so a blocked run stops before report_media empties
    reports/screenshots/ - a run that loses the lock must change nothing.
    """
    config = session.config
    try:
        env_name = _lock_env(os.environ)
        collect_only = bool(config.getoption('--collect-only', default=False))
        existing = _read_lock(env_name)
        action, reason = decide(existing, environ=os.environ, collect_only=collect_only,
                                own_pid=os.getpid(), parent_pid=os.getppid())
    except Exception as e:  # noqa: BLE001 - a broken guard must never block testing
        log.warning(f'single_run_guard: guard check failed ({e}) - run proceeds unguarded')
        return

    if action == SKIP:
        log.debug(f'single_run_guard: standing aside - {reason}')
        _arm_heartbeat_for_parent(env_name, reason)
        return

    if action == ACQUIRE:
        # Our env's lock is free - but the artifacts are repo-global, so a
        # live run against ANY env is still a rival (see cross_env_rival).
        try:
            rival = cross_env_rival(env_name, environ=os.environ,
                                    own_pid=os.getpid(), parent_pid=os.getppid())
        except Exception as e:  # noqa: BLE001 - a broken guard must never block testing
            log.warning(f'single_run_guard: cross-env scan failed ({e}) - run proceeds')
            rival = None
        if rival is not None:
            rival_env, rival_lock = rival
            _mute_html_report(config)
            pytest.exit(_blocked_message(rival_env, rival_lock), returncode=2)
        try:
            if existing is not None:
                # Stale, dead-holder, or self-recorded lock: clear it the way
                # run_lock.acquire does before writing our own.
                _remove_lock(env_name)
            info = _holder_info(env_name, 'pytest')
            info['target'] = _invocation_target(config)
            _write_lock(env_name, info)
            # What pytest_unconfigure releases; unset means nothing to release.
            config._single_run_guard_env = env_name
            _arm_heartbeat(env_name, {os.getpid()})
            log.info(f'single_run_guard: run lock taken for env={env_name} ({reason})')
        except Exception as e:  # noqa: BLE001 - a broken guard must never block testing
            log.warning(f'single_run_guard: could not take the run lock ({e}) - '
                        f'run proceeds unguarded')
        return

    # BLOCK: another live run holds the lock. Stop before anything shared
    # is touched, and without replacing the last real report.
    _mute_html_report(config)
    pytest.exit(_blocked_message(env_name, existing or {}), returncode=2)


def _arm_heartbeat(env_name: str, pids: set[int]) -> None:
    global _beat_state
    _beat_state = {'env': env_name, 'pids': pids, 'last': None}


def _arm_heartbeat_for_parent(env_name: str, reason: str) -> None:
    """A run under a parent's lock keeps that lock alive for the parent:
    the parent (run_suite, guarded_run) only waits on its child."""
    pids: set[int] = set()
    if HELD_MARKER in reason:
        marker = os.environ.get(HELD_MARKER, '')
        if marker.isdigit():
            pids.add(int(marker))
        pids.add(os.getppid())
    elif 'parent process' in reason:
        pids.add(os.getppid())
    if pids:
        _arm_heartbeat(env_name, pids)


def pytest_runtest_logreport(report: Any) -> None:  # noqa: ARG001 - pytest names the hook argument
    """Each test report is a sign of life; stamp the lock at most once a
    minute. A stamp that fails is logged once and never fails the run."""
    state = _beat_state
    if state is None:
        return
    now = time.monotonic()
    # None, not 0: monotonic counts from boot on both platforms, and a box
    # up for less than the interval would otherwise skip its first stamp
    # (the CI runner did, 09/14/2026)
    if state['last'] is not None and now - state['last'] < HEARTBEAT_INTERVAL_S:
        return
    state['last'] = now
    try:
        beat(state['env'], state['pids'])
    except Exception as e:  # noqa: BLE001 - a heartbeat must never fail a run
        log.warning(f'single_run_guard: could not stamp the run lock ({e}); '
                    f'the staleness backstop falls back to acquired_at')
        _disarm_heartbeat()


def _disarm_heartbeat() -> None:
    global _beat_state
    _beat_state = None


def pytest_unconfigure(config: Any) -> None:
    """Release the lock this session took - and only that lock.

    pytest_unconfigure runs on every exit path pytest controls (normal end,
    Ctrl-C, --exitfirst, internal error), so a finished run never leaves a
    lock behind. A hard kill still can - that is exactly what run_lock's
    dead-PID and staleness backstops then clear on the next run.
    """
    _disarm_heartbeat()
    env_name = getattr(config, '_single_run_guard_env', None)
    if not env_name:
        return
    try:
        existing = _read_lock(env_name)
        # Only delete a lock that still records this process - deleting
        # blindly could free a rival that re-acquired after a --force.
        if existing is not None and existing.get('pid') == os.getpid():
            _remove_lock(env_name)
    except Exception as e:  # noqa: BLE001 - release failure must not fail the run
        log.warning(f'single_run_guard: could not release the run lock ({e}) - '
                    f'the backstops in tools/run_lock.py will clear it')
