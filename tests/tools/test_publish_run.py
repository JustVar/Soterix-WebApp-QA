"""The publish-a-run command.

All offline: scp is stubbed, folders come from tmp_path. What is under
test is the selection (newest run, named run, refusals) and that the
command publishes exactly what it says. The one live thing, the scp
itself, is proven by using the tool for real.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools import publish_run as pr  # noqa: E402


@pytest.fixture
def runs(tmp_path, monkeypatch):
    """A fake archive with two runs and the front-door pages."""
    d = tmp_path / 'runs'
    d.mkdir()
    (d / '2026-08-31_12-00-00__tests').mkdir()
    (d / '2026-09-01_10-39-03__tests-ui-licenses').mkdir()
    (d / 'index.html').write_text('index', encoding='utf-8')
    (d / 'health.html').write_text('health', encoding='utf-8')
    monkeypatch.setattr(pr, 'RUNS', d)
    return d


def _capture(monkeypatch):
    calls = []
    class Proc:
        returncode = 0
    monkeypatch.setattr(pr.subprocess, 'run', lambda cmd, check: calls.append(cmd) or Proc())
    return calls


def test_default_is_the_newest_run(runs, monkeypatch, capsys):
    calls = _capture(monkeypatch)
    assert pr.main([]) == 0
    cmd = calls[0]
    assert any('2026-09-01_10-39-03__tests-ui-licenses' in a for a in cmd)
    assert not any('2026-08-31' in a for a in cmd)


def test_the_front_door_pages_ride_along(runs, monkeypatch):
    """index.html and health.html keep the host's entry point current."""
    calls = _capture(monkeypatch)
    assert pr.main([]) == 0
    joined = ' '.join(calls[0])
    assert 'index.html' in joined
    assert 'health.html' in joined


def test_a_named_run_is_published_exactly(runs, monkeypatch):
    calls = _capture(monkeypatch)
    assert pr.main(['2026-08-31_12-00-00__tests']) == 0
    assert any('2026-08-31_12-00-00__tests' in a for a in calls[0])


def test_a_missing_run_refuses_with_the_available_names(runs, monkeypatch, capsys):
    calls = _capture(monkeypatch)
    assert pr.main(['2026-01-01_00-00-00__nope']) == 2
    assert calls == []
    assert '2026-09-01_10-39-03' in capsys.readouterr().out


def test_a_non_run_folder_is_refused(runs, monkeypatch, capsys):
    """`reports/runs/somefolder` that is not a timestamped run must not be
    pushed to the shared host by accident."""
    (runs / 'scratch').mkdir()
    calls = _capture(monkeypatch)
    assert pr.main(['scratch']) == 2
    assert calls == []
    assert 'Refusing' in capsys.readouterr().out


def test_an_empty_archive_is_an_error_not_a_publish(runs, monkeypatch):
    for p in list(runs.iterdir()):
        if p.is_dir():
            p.rmdir()
    calls = _capture(monkeypatch)
    assert pr.main([]) == 2
    assert calls == []


def test_dry_run_runs_nothing(runs, monkeypatch, capsys):
    calls = _capture(monkeypatch)
    assert pr.main(['--dry-run']) == 0
    assert calls == []
    assert 'would run: scp' in capsys.readouterr().out


def test_scp_failure_is_exit_1_with_a_hint(runs, monkeypatch, capsys):
    class Proc:
        returncode = 1
    monkeypatch.setattr(pr.subprocess, 'run', lambda cmd, check: Proc())
    assert pr.main([]) == 1
    assert 'key installed' in capsys.readouterr().out


def test_host_and_dir_come_from_the_environment(runs, monkeypatch):
    monkeypatch.setenv('QA_RUNS_HOST', 'me@elsewhere')
    monkeypatch.setenv('QA_RUNS_DIR', '/srv/runs')
    calls = _capture(monkeypatch)
    assert pr.main([]) == 0
    assert calls[0][-1] == 'me@elsewhere:/srv/runs/'
