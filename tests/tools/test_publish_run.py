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
    """A fake archive with two runs. The newest carries the sensitive
    evidence (a trace zip and a video) plus the safe pages, so the exclusion
    can be checked."""
    d = tmp_path / 'runs'
    d.mkdir()
    (d / '2026-08-31_12-00-00__tests').mkdir()
    newest = d / '2026-09-01_10-39-03__tests-ui-licenses'
    newest.mkdir()
    (newest / 'run.html').write_text('run', encoding='utf-8')
    (newest / 'summary.json').write_text('{}', encoding='utf-8')
    (newest / 'traces').mkdir()
    (newest / 'traces' / 'test-trace.zip').write_bytes(b'PK\x03\x04secret-cookie')
    (newest / 'test-video.webm').write_bytes(b'\x1avideo')
    (newest / 'screenshots').mkdir()
    (newest / 'screenshots' / 'shot.png').write_bytes(b'\x89PNG')
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


def _scp_call(calls):
    """The scp command among the ssh/scp sequence (ssh rm, scp, ssh mv)."""
    return next(c for c in calls if c and c[0] == 'scp')


def test_default_is_the_newest_run(runs, monkeypatch, capsys):
    """With no argument, the newest archived run is the one published."""
    calls = _capture(monkeypatch)
    assert pr.main([]) == 0
    cmd = _scp_call(calls)
    assert any('2026-09-01_10-39-03__tests-ui-licenses' in a for a in cmd)
    assert not any('2026-08-31' in a for a in cmd)


def test_traces_and_videos_are_never_sent(runs, monkeypatch, tmp_path):
    """The trace zip carries a live session cookie and a fresh-login test's
    trace carries the account password; the video shows the authenticated
    session. Neither leaves the machine. What is staged for the host is the
    run.html, summary.json and screenshots only."""
    staged_paths = []
    class Proc:
        returncode = 0
    def fake_run(cmd, check):
        if cmd and cmd[0] == 'scp':
            staged = pr.Path(cmd[-2])        # the source arg to scp
            staged_paths.append(sorted(p.name for p in staged.rglob('*')))
        return Proc()
    monkeypatch.setattr(pr.subprocess, 'run', fake_run)
    assert pr.main([]) == 0
    names = staged_paths[0]
    assert 'test-trace.zip' not in names
    assert 'traces' not in names
    assert 'test-video.webm' not in names
    assert 'run.html' in names
    assert 'shot.png' in names               # screenshots still go


def test_the_local_index_is_not_pushed_over_the_hosts(runs, monkeypatch):
    """Each machine sees only its own runs, so a local index.html/health.html
    is partial and must not overwrite the host's fuller view."""
    calls = _capture(monkeypatch)
    assert pr.main([]) == 0
    joined = ' '.join(str(a) for c in calls for a in c)
    assert 'index.html' not in joined
    assert 'health.html' not in joined


def test_a_named_run_is_published_exactly(runs, monkeypatch):
    """Naming a run publishes that run, not the newest."""
    calls = _capture(monkeypatch)
    assert pr.main(['2026-08-31_12-00-00__tests']) == 0
    assert any('2026-08-31_12-00-00__tests' in a for a in _scp_call(calls))


def test_a_missing_run_refuses_with_the_available_names(runs, monkeypatch, capsys):
    """A typo in the run name is refused, and the reply lists real ones."""
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
    """No archived runs means exit 2 and no copy, not an empty publish."""
    import shutil
    for p in list(runs.iterdir()):
        if p.is_dir():
            shutil.rmtree(p)
    calls = _capture(monkeypatch)
    assert pr.main([]) == 2
    assert calls == []


def test_dry_run_runs_nothing(runs, monkeypatch, capsys):
    """--dry-run prints the scp command and executes nothing."""
    calls = _capture(monkeypatch)
    assert pr.main(['--dry-run']) == 0
    assert calls == []
    assert 'would stage' in capsys.readouterr().out


def test_scp_failure_is_exit_1_with_a_hint(runs, monkeypatch, capsys):
    """A failed copy exits 1 and tells the reader about key setup. The partial
    temp is cleaned up rather than left as a half-run."""
    def fake_run(cmd, check):
        rc = 1 if cmd and cmd[0] == 'scp' else 0
        return type('P', (), {'returncode': rc})()
    monkeypatch.setattr(pr.subprocess, 'run', fake_run)
    assert pr.main([]) == 1
    assert 'key installed' in capsys.readouterr().out


def test_host_and_dir_come_from_the_environment(runs, monkeypatch):
    """QA_RUNS_HOST and QA_RUNS_DIR override the destination."""
    monkeypatch.setenv('QA_RUNS_HOST', 'me@elsewhere')
    monkeypatch.setenv('QA_RUNS_DIR', '/srv/runs')
    calls = _capture(monkeypatch)
    assert pr.main([]) == 0
    scp = _scp_call(calls)
    assert scp[-1].startswith('me@elsewhere:/srv/runs/.pub-tmp-')
