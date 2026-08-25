"""Unit tests for run.py's command builder.

The scoped rerun policy: `--retry-streams` appends the one sanctioned
rerun (once, on the tenant's stream-failure message only) and nothing
else does. No browser, no network; the pytest child is a stub.
"""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

import run  # noqa: E402


def test_default_command_carries_no_rerun():
    """A plain run sends pytest no rerun option."""
    cmd = run.build_command(['tests/ui/views'], ['-s'])
    assert cmd == [*run.PYTEST, 'tests/ui/views', '-s']
    assert '--reruns' not in cmd
    assert '--only-rerun' not in cmd


def test_retry_streams_appends_the_scoped_rerun_only():
    """The flag appends one rerun on the stream-failure message and nothing else."""
    cmd = run.build_command(['tests/ui/views'], ['-s'], retry_streams=True)
    assert cmd[:5] == [*run.PYTEST, 'tests/ui/views', '-s']
    assert cmd[5:] == ['--reruns', '1', '--only-rerun', 'failed to load']


def test_stream_rerun_is_one_attempt_on_one_message():
    """The rerun policy stays at one attempt on one message class."""
    # The policy in one place: widen the match or the count and this fails.
    assert run.STREAM_RERUN_ARGS == ['--reruns', '1', '--only-rerun', 'failed to load']


def test_cli_flag_reaches_pytest_and_is_announced(monkeypatch, capsys):
    """--retry-streams reaches the pytest child and the run says so."""
    seen: list[list[str]] = []

    def fake_run(cmd, **kwargs):
        seen.append(list(cmd))
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(run.subprocess, 'run', fake_run)
    monkeypatch.setattr(run, '_run_dirs', lambda: [])

    rc = run.main(['module', 'views', '--retry-streams', '--', '-s'])

    assert rc == 0
    assert len(seen) == 1
    assert seen[0][-4:] == ['--reruns', '1', '--only-rerun', 'failed to load']
    assert '-s' in seen[0]
    out = capsys.readouterr().out
    assert 'Retry policy' in out
    assert '--only-rerun "failed to load"' in out


def test_cli_without_flag_sends_no_rerun(monkeypatch):
    """Without the flag the pytest child gets no rerun option."""
    seen: list[list[str]] = []

    def fake_run(cmd, **kwargs):
        seen.append(list(cmd))
        return SimpleNamespace(returncode=0)

    monkeypatch.setattr(run.subprocess, 'run', fake_run)
    monkeypatch.setattr(run, '_run_dirs', lambda: [])

    run.main(['module', 'views'])

    assert len(seen) == 1
    assert '--reruns' not in seen[0]
    assert '--only-rerun' not in seen[0]


def test_check_runs_the_reachability_gate_only(monkeypatch):
    """--check runs tools/pre_run_check.py for the env with the optional
    integrations skipped, and stops the run when it fails."""
    seen: list[list[str]] = []

    class Done:
        returncode = 0

    def fake_run(cmd, **kwargs):
        seen.append(list(cmd))
        return Done()

    monkeypatch.setattr(run.subprocess, 'run', fake_run)
    monkeypatch.setenv('ENV', 'stage')
    run._check()
    assert seen[0][1:] == [str(run.ROOT / 'tools' / 'pre_run_check.py'), '--env', 'stage',
                           '--skip-qatouch', '--skip-qa-ops']

    Done.returncode = 1
    with pytest.raises(SystemExit):
        run._check()
