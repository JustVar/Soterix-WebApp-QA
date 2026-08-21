"""Run lock - prevent concurrent test runs against the same environment.

Creates a lock file per environment to prevent overlapping test runs.
If a lock exists from a stale process, auto-clears after a configurable timeout.

Usage:
  # Acquire lock before running:
  python tools/run_lock.py acquire --env qa
  pytest tests/ ...
  python tools/run_lock.py release --env qa

  # Or use as a context wrapper:
  python tools/run_lock.py wrap --env qa -- pytest tests/ ...

  # Check lock status:
  python tools/run_lock.py status --env qa

  # Force release (e.g., after crash):
  python tools/run_lock.py release --env qa --force

Lock file: logs/.run_lock_{env}.json
Stale timeout: 4 hours (configurable via --timeout)
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
LOCK_DIR = ROOT / 'logs'

# Default stale lock timeout: 4 hours
DEFAULT_TIMEOUT_HOURS = 4


def _lock_path(env: str) -> Path:
    return LOCK_DIR / f'.run_lock_{env}.json'


def _read_lock(env: str) -> dict | None:
    path = _lock_path(env)
    if not path.exists():
        return None
    try:
        with open(path) as f:
            return json.load(f)
    except (json.JSONDecodeError, ValueError):
        return None


def _write_lock(env: str, info: dict) -> None:
    LOCK_DIR.mkdir(parents=True, exist_ok=True)
    with open(_lock_path(env), 'w') as f:
        json.dump(info, f, indent=2)


def _remove_lock(env: str) -> None:
    path = _lock_path(env)
    if path.exists():
        path.unlink()


def _is_stale(lock_info: dict, timeout_hours: float) -> bool:
    """Check if a lock is stale (older than timeout)."""
    acquired = lock_info.get('acquired_at', '')
    if not acquired:
        return True
    try:
        acquired_dt = datetime.fromisoformat(acquired)
        age_hours = (datetime.now(UTC) - acquired_dt).total_seconds() / 3600
        return age_hours > timeout_hours
    except (ValueError, TypeError):
        return True


def _pid_alive(pid: int) -> bool:
    """Check if a process is still running.

    Not os.kill(pid, 0) on Windows: there, signal 0 is CTRL_C_EVENT, so the
    call can only see processes sharing this console - every other live
    process reads as dead, and a same-console process group would actually
    receive the Ctrl+C. Ask the kernel for the process object instead.
    """
    if sys.platform == 'win32':
        return _pid_alive_windows(pid)
    try:
        os.kill(pid, 0)
        return True
    except (OSError, ProcessLookupError):
        return False


def _pid_alive_windows(pid: int) -> bool:
    """True while the kernel still tracks `pid` as a running process."""
    import ctypes

    process_query_limited_information = 0x1000
    still_active = 259
    error_access_denied = 5

    kernel32 = ctypes.WinDLL('kernel32', use_last_error=True)
    handle = kernel32.OpenProcess(process_query_limited_information, False, pid)
    if not handle:
        # A pid we may not open (another user's, or a protected system
        # process) still exists; a freed pid cannot be opened at all.
        return ctypes.get_last_error() == error_access_denied
    try:
        code = ctypes.c_ulong()
        if not kernel32.GetExitCodeProcess(handle, ctypes.byref(code)):
            return True  # the object exists; unreadable state stays "alive"
        # An open handle elsewhere keeps a finished process openable - the
        # exit code is what tells finished from running.
        return code.value == still_active
    finally:
        kernel32.CloseHandle(handle)


def _holder_info(env: str, run_type: str) -> dict:
    """The metadata a lock records about its holder.

    Shared with plugins/single_run_guard.py so a lock looks the same to
    status/acquire no matter which entry point wrote it.
    """
    return {
        'env': env,
        'pid': os.getpid(),
        'user': os.environ.get('USER', os.environ.get('USERNAME', 'unknown')),
        'run_type': run_type,
        'acquired_at': datetime.now(UTC).isoformat(),
        'hostname': os.environ.get('COMPUTERNAME', os.environ.get('HOSTNAME', 'unknown')),
    }


def acquire(env: str, timeout_hours: float = DEFAULT_TIMEOUT_HOURS,
            run_type: str = 'unknown') -> bool:
    """Acquire a run lock for an environment. Returns True on success."""
    existing = _read_lock(env)

    if existing:
        holder_pid = existing.get('pid', 0)
        holder_user = existing.get('user', 'unknown')
        holder_type = existing.get('run_type', 'unknown')
        acquired = existing.get('acquired_at', '?')

        # Check if stale
        if _is_stale(existing, timeout_hours):
            print(f'  Lock for {env} is stale (acquired {acquired}). Auto-clearing.')
            _remove_lock(env)
        # Check if process is dead
        elif holder_pid and not _pid_alive(holder_pid):
            print(f'  Lock holder PID {holder_pid} is dead. Auto-clearing.')
            _remove_lock(env)
        else:
            print(f'  BLOCKED: Environment "{env}" is locked.')
            print(f'    Holder:   {holder_user} (PID {holder_pid})')
            print(f'    Type:     {holder_type}')
            print(f'    Acquired: {acquired}')
            print(f'    To force: python tools/run_lock.py release --env {env} --force')
            return False

    _write_lock(env, _holder_info(env, run_type))
    print(f'  Lock acquired for env={env} (PID {os.getpid()})')
    return True


def release(env: str, force: bool = False) -> bool:
    """Release a run lock. Returns True if released."""
    existing = _read_lock(env)
    if not existing:
        print(f'  No lock exists for env={env}')
        return True

    if not force:
        # Only release if we own the lock
        if existing.get('pid') != os.getpid():
            print(f'  Lock owned by PID {existing.get("pid")}, not us ({os.getpid()}). '
                  f'Use --force to override.')
            return False

    _remove_lock(env)
    print(f'  Lock released for env={env}')
    return True


def status(env: str) -> None:
    """Print lock status for an environment."""
    existing = _read_lock(env)
    if not existing:
        print(f'  env={env}: \033[92mUNLOCKED\033[0m')
        return

    stale = _is_stale(existing, DEFAULT_TIMEOUT_HOURS)
    pid_alive = _pid_alive(existing.get('pid', 0))

    if stale:
        state = '\033[93mSTALE\033[0m'
    elif not pid_alive:
        state = '\033[93mORPHANED\033[0m (PID dead)'
    else:
        state = '\033[91mLOCKED\033[0m'

    print(f'  env={env}: {state}')
    print(f'    Holder: {existing.get("user", "?")} (PID {existing.get("pid", "?")})')
    print(f'    Type:   {existing.get("run_type", "?")}')
    print(f'    Since:  {existing.get("acquired_at", "?")}')
    print(f'    Host:   {existing.get("hostname", "?")}')


def wrap(env: str, command: list[str], timeout_hours: float = DEFAULT_TIMEOUT_HOURS,
         run_type: str = 'wrapped') -> int:
    """Acquire lock, run command, release lock. Returns command exit code."""
    if not acquire(env, timeout_hours, run_type):
        return 1

    try:
        result = subprocess.run(command)
        return result.returncode
    except KeyboardInterrupt:
        print('\n  Interrupted - releasing lock...')
        return 130
    finally:
        # Always release on exit
        _remove_lock(env)
        print(f'  Lock released for env={env}')


def main():
    parser = argparse.ArgumentParser(description='Test run lock manager')
    sub = parser.add_subparsers(dest='action', required=True)

    # acquire
    acq = sub.add_parser('acquire', help='Acquire a run lock')
    acq.add_argument('--env', required=True, help='Environment name (qa, stage, prod)')
    acq.add_argument('--type', default='manual', help='Run type (smoke, regression, manual)')
    acq.add_argument('--timeout', type=float, default=DEFAULT_TIMEOUT_HOURS,
                     help=f'Stale lock timeout in hours (default: {DEFAULT_TIMEOUT_HOURS})')

    # release
    rel = sub.add_parser('release', help='Release a run lock')
    rel.add_argument('--env', required=True, help='Environment name')
    rel.add_argument('--force', action='store_true', help='Force release even if not owner')

    # status
    st = sub.add_parser('status', help='Check lock status')
    st.add_argument('--env', required=True, help='Environment name')

    # wrap
    wr = sub.add_parser('wrap', help='Acquire lock, run command, release lock')
    wr.add_argument('--env', required=True, help='Environment name')
    wr.add_argument('--type', default='wrapped', help='Run type')
    wr.add_argument('--timeout', type=float, default=DEFAULT_TIMEOUT_HOURS,
                    help=f'Stale lock timeout in hours (default: {DEFAULT_TIMEOUT_HOURS})')
    wr.add_argument('command', nargs=argparse.REMAINDER,
                    help='Command to run (after --)')

    args = parser.parse_args()

    if args.action == 'acquire':
        ok = acquire(args.env, args.timeout, args.type)
        sys.exit(0 if ok else 1)
    elif args.action == 'release':
        ok = release(args.env, args.force)
        sys.exit(0 if ok else 1)
    elif args.action == 'status':
        status(args.env)
    elif args.action == 'wrap':
        cmd = args.command
        # Strip leading '--' if present
        if cmd and cmd[0] == '--':
            cmd = cmd[1:]
        if not cmd:
            parser.error('No command provided. Usage: run_lock.py wrap --env qa -- pytest ...')
        sys.exit(wrap(args.env, cmd, args.timeout, args.type))


if __name__ == '__main__':
    main()
