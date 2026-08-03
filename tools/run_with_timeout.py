"""Run wrapper with hard timeout - kills test runs that exceed time limit.

Prevents runaway test sessions from blocking CI/overnight slots indefinitely.
Configurable per run type: smoke (30 min), sanity (60 min), regression (180 min).

Usage:
  python tools/run_with_timeout.py --minutes 60 -- pytest tests/ -k smoke
  python tools/run_with_timeout.py --type smoke -- pytest tests/ ...
  python tools/run_with_timeout.py --type regression -- pytest tests/ ...

Preset timeouts:
  smoke:       30 minutes
  sanity:      60 minutes
  regression: 180 minutes
  full:       240 minutes

Exit codes:
  Same as wrapped command on normal completion
  124 - timed out (matching GNU timeout convention)
  1   - error starting command
"""
from __future__ import annotations

import argparse
import subprocess
import sys
import time

# Preset timeouts in minutes
PRESETS = {
    'smoke': 30,
    'sanity': 60,
    'regression': 180,
    'full': 240,
}


def run_with_timeout(command: list[str], timeout_minutes: int, run_type: str = '') -> int:
    """Run a command with a hard timeout. Returns exit code."""
    timeout_seconds = timeout_minutes * 60

    label = f'{run_type} ' if run_type else ''
    print(f'\n=== Timed Run: {label}timeout={timeout_minutes}m ===')
    print(f'  Command: {" ".join(command)}')
    print(f'  Timeout: {timeout_minutes} minutes ({timeout_seconds}s)')
    print(f'  Started: {time.strftime("%Y-%m-%d %H:%M:%S")}')
    print()

    start_time = time.time()

    try:
        # Use subprocess with timeout
        # On Windows, we can't use process groups the same way as Unix,
        # but subprocess.run with timeout handles it cross-platform
        result = subprocess.run(
            command,
            timeout=timeout_seconds,
        )
        elapsed = time.time() - start_time
        elapsed_min = elapsed / 60
        print(f'\n  Completed in {elapsed_min:.1f} minutes '
              f'(limit: {timeout_minutes}m, '
              f'{elapsed_min/timeout_minutes*100:.0f}% of budget)')
        return result.returncode

    except subprocess.TimeoutExpired:
        elapsed = time.time() - start_time
        print(f'\n  \033[91mTIMEOUT\033[0m: Run exceeded {timeout_minutes} minute limit '
              f'(ran for {elapsed/60:.1f}m)')
        print('  The test process has been terminated.')
        print('  Consider:')
        print(f'    - Increasing timeout: --minutes {timeout_minutes * 2}')
        print('    - Running fewer tests: -k "smoke" or -m "not slow"')
        print('    - Investigating slow tests: --durations=20')
        return 124  # GNU timeout convention

    except KeyboardInterrupt:
        elapsed = time.time() - start_time
        print(f'\n  Interrupted after {elapsed/60:.1f} minutes')
        return 130

    except FileNotFoundError:
        print(f'\n  \033[91mERROR\033[0m: Command not found: {command[0]}')
        return 1

    except Exception as e:
        print(f'\n  \033[91mERROR\033[0m: {e}')
        return 1


def main():
    parser = argparse.ArgumentParser(
        description='Run tests with a hard timeout',
        usage='%(prog)s [--minutes M | --type TYPE] -- command ...',
    )
    parser.add_argument('--minutes', type=int, default=None,
                        help='Timeout in minutes (overrides --type)')
    parser.add_argument('--type', choices=list(PRESETS.keys()), default=None,
                        help=f'Use preset timeout: {PRESETS}')
    parser.add_argument('command', nargs=argparse.REMAINDER,
                        help='Command to run (after --)')
    args = parser.parse_args()

    # Determine timeout
    if args.minutes:
        timeout = args.minutes
        run_type = 'custom'
    elif args.type:
        timeout = PRESETS[args.type]
        run_type = args.type
    else:
        timeout = PRESETS['regression']  # default
        run_type = 'regression (default)'

    # Parse command
    cmd = args.command
    if cmd and cmd[0] == '--':
        cmd = cmd[1:]
    if not cmd:
        parser.error('No command provided. Usage: run_with_timeout.py --type smoke -- pytest ...')

    sys.exit(run_with_timeout(cmd, timeout, run_type))


if __name__ == '__main__':
    main()
