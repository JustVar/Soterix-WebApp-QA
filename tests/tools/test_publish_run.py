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
    # the archive keeps a failure's video beside its trace, in traces/
    (newest / 'traces' / 'test-video.webm').write_bytes(b'\x1avideo')
    (newest / 'screenshots').mkdir()
    (newest / 'screenshots' / 'shot.png').write_bytes(b'\x89PNG')
    (d / 'index.html').write_text('index', encoding='utf-8')
    (d / 'health.html').write_text('health', encoding='utf-8')
    monkeypatch.setattr(pr, 'RUNS', d)
    return d


def _capture(monkeypatch):
    """Every subprocess call as (cmd, batch text). Nothing runs."""
    calls = []
    class Proc:
        returncode = 0
    def fake_run(cmd, input=None, **_kw):
        calls.append((cmd, input or ''))
        return Proc()
    monkeypatch.setattr(pr.subprocess, 'run', fake_run)
    return calls


def _sftp_call(calls):
    """(cmd, batch) of the one sftp call a publish makes."""
    assert [c[0][0] for c in calls] == ['sftp'], 'a publish is one sftp call: the publish account has no shell'
    return calls[0]


def test_default_is_the_newest_run(runs, monkeypatch, capsys):
    """With no argument, the newest archived run is the one published."""
    calls = _capture(monkeypatch)
    assert pr.main([]) == 0
    _cmd, batch = _sftp_call(calls)
    assert '2026-09-01_10-39-03__tests-ui-licenses' in batch
    assert '2026-08-31' not in batch


def test_trace_zips_stay_local_and_videos_travel(runs, monkeypatch, tmp_path):
    """The trace zip carries a live session cookie and a fresh-login test's
    trace carries the account password, so it never leaves the machine. The
    failure video beside it does: run.html links it, and a password field
    shows dots. Staged for the host: run.html, summary.json, screenshots,
    and the traces/ folder holding only the videos."""
    staged_paths = []
    class Proc:
        returncode = 0
    def fake_run(cmd, input=None, **_kw):
        put = next(line for line in input.splitlines() if line.startswith('put -r '))
        staged = pr.Path(put.split('"')[1])   # the first quoted path is the local source
        staged_paths.append(sorted(p.name for p in staged.rglob('*')))
        return Proc()
    monkeypatch.setattr(pr.subprocess, 'run', fake_run)
    assert pr.main([]) == 0
    names = staged_paths[0]
    assert 'test-trace.zip' not in names
    assert 'traces' in names                 # the folder travels, holding the videos
    assert 'test-video.webm' in names
    assert 'run.html' in names
    assert 'shot.png' in names               # screenshots still go


def test_the_local_index_is_not_pushed_over_the_hosts(runs, monkeypatch):
    """Each machine sees only its own runs, so a local index.html/health.html
    is partial and must not overwrite the host's fuller view."""
    calls = _capture(monkeypatch)
    assert pr.main([]) == 0
    joined = ' '.join(str(a) for cmd, batch in calls for a in [*cmd, batch])
    assert 'index.html' not in joined
    assert 'health.html' not in joined


def test_a_named_run_is_published_exactly(runs, monkeypatch):
    """Naming a run publishes that run, not the newest."""
    calls = _capture(monkeypatch)
    assert pr.main(['2026-08-31_12-00-00__tests']) == 0
    assert '2026-08-31_12-00-00__tests' in _sftp_call(calls)[1]


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


def test_a_failed_copy_is_exit_1_with_a_hint(runs, monkeypatch, capsys):
    """A failed copy exits 1 and tells the reader about key setup."""
    def fake_run(cmd, input=None, **_kw):
        return type('P', (), {'returncode': 1})()
    monkeypatch.setattr(pr.subprocess, 'run', fake_run)
    assert pr.main([]) == 1
    assert 'key installed' in capsys.readouterr().out


def test_host_and_dir_come_from_the_environment(runs, monkeypatch):
    """QA_RUNS_HOST and QA_RUNS_DIR override the destination."""
    monkeypatch.setenv('QA_RUNS_HOST', 'me@elsewhere')
    monkeypatch.setenv('QA_RUNS_DIR', '/srv/runs')
    calls = _capture(monkeypatch)
    assert pr.main([]) == 0
    cmd, batch = _sftp_call(calls)
    assert cmd[-1] == 'me@elsewhere'
    assert 'mkdir "/srv/runs/.pub-tmp-' in batch


def test_the_batch_lands_the_folder_with_one_rename_and_tolerates_no_old_copy():
    """Hidden temp first, the old copy moved aside (allowed to fail), one rename into place, temp removed."""
    lines = pr.sftp_batch(pr.Path('C:/tmp/stage/2026-09-01_10-39-03__tests-ui'), '/data/qa/runs', stamp='17').splitlines()
    assert lines == [
        'mkdir "/data/qa/runs/.pub-tmp-2026-09-01_10-39-03__tests-ui-17"',
        'put -r "C:/tmp/stage/2026-09-01_10-39-03__tests-ui" "/data/qa/runs/.pub-tmp-2026-09-01_10-39-03__tests-ui-17/"',
        '-rename "/data/qa/runs/2026-09-01_10-39-03__tests-ui" "/data/qa/runs/.pub-old-2026-09-01_10-39-03__tests-ui-17"',
        'rename "/data/qa/runs/.pub-tmp-2026-09-01_10-39-03__tests-ui-17/2026-09-01_10-39-03__tests-ui" "/data/qa/runs/2026-09-01_10-39-03__tests-ui"',
        'chmod 775 "/data/qa/runs/2026-09-01_10-39-03__tests-ui"',
        'rmdir "/data/qa/runs/.pub-tmp-2026-09-01_10-39-03__tests-ui-17"',
    ]


def test_every_published_directory_is_made_readable_by_the_archive(tmp_path):
    """nginx has to traverse into the run folder and its subfolders.

    `put -r` carries the LOCAL directory modes. From Windows those map to 0700,
    so the first sftp publish landed a folder the archive could not serve: the
    files were group-readable, the directories were not. Nothing in the batch
    said otherwise, so nothing did (09/23/2026).
    """
    run = tmp_path / '2026-09-23_14-05-21__tests-ui'
    (run / 'log').mkdir(parents=True)
    (run / 'screenshots').mkdir()
    (run / 'artifacts' / 'videos').mkdir(parents=True)
    (run / 'run.html').write_text('x', encoding='utf-8')

    lines = pr.sftp_batch(run, '/data/qa/runs', stamp='17').splitlines()
    chmods = [line for line in lines if line.startswith('chmod ')]
    assert chmods == [
        'chmod 775 "/data/qa/runs/2026-09-23_14-05-21__tests-ui"',
        'chmod 775 "/data/qa/runs/2026-09-23_14-05-21__tests-ui/artifacts"',
        'chmod 775 "/data/qa/runs/2026-09-23_14-05-21__tests-ui/artifacts/videos"',
        'chmod 775 "/data/qa/runs/2026-09-23_14-05-21__tests-ui/log"',
        'chmod 775 "/data/qa/runs/2026-09-23_14-05-21__tests-ui/screenshots"',
    ], 'every directory, and a parent before the child it contains'
    # and they run after the folder is in place, never against the temp name
    assert lines.index('rename "/data/qa/runs/.pub-tmp-2026-09-23_14-05-21__tests-ui-17/'
                       '2026-09-23_14-05-21__tests-ui" "/data/qa/runs/2026-09-23_14-05-21__tests-ui"') < lines.index(chmods[0])
    assert lines[-1].startswith('rmdir ')
    # a file is not chmod'd: the account's umask already reaches those
    assert not any('run.html' in line for line in chmods)


def test_a_name_that_would_break_the_batch_is_refused():
    """A quote in a path would end the quoted argument and start a new sftp command."""
    with pytest.raises(ValueError, match='cannot be published'):
        pr.sftp_batch(pr.Path('2026-09-01_10-39-03__te"sts'), '/data/qa/runs', stamp='1')


def test_the_published_copy_is_masked_and_the_local_run_is_not(tmp_path, monkeypatch, capsys):
    """A password in a per-test log is *** in the staged copy; the original keeps it for the person debugging."""
    from tools import evidence_scan
    monkeypatch.setattr(evidence_scan, 'ENV_FILE', tmp_path / 'no.env')
    run = tmp_path / '2026-09-18_09-00-06__tests-ui'
    (run / 'log').mkdir(parents=True)
    line = "E   {'email': 'qa@example.com', 'password': 'hunter2-long'}"
    (run / 'log' / 'test_login.log').write_text(line, encoding='utf-8')
    staged = pr._staged_copy(run)
    assert 'hunter2-long' not in (staged / 'log' / 'test_login.log').read_text(encoding='utf-8')
    assert (run / 'log' / 'test_login.log').read_text(encoding='utf-8') == line
    out = capsys.readouterr().out
    assert 'masked 1 secret(s)' in out
    assert 'hunter2-long' not in out


def test_the_publish_account_gets_its_jail_path(runs, monkeypatch):
    """qa-publish is jailed: the served directory is /runs for it, and QA_RUNS_DIR still wins when set."""
    monkeypatch.delenv('QA_RUNS_DIR', raising=False)
    monkeypatch.setenv('QA_RUNS_HOST', 'qa-publish@10.2.0.2')
    calls = _capture(monkeypatch)
    assert pr.main([]) == 0
    assert 'mkdir "/runs/.pub-tmp-' in _sftp_call(calls)[1]
    monkeypatch.setenv('QA_RUNS_DIR', '/elsewhere')
    calls.clear()
    assert pr.main([]) == 0
    assert 'mkdir "/elsewhere/.pub-tmp-' in _sftp_call(calls)[1]


def test_a_path_that_sftp_would_expand_is_refused():
    """sftp expands * ? [ in the local path of put, in quotes too."""
    for name in ('2026-09-01_10-39-03__tests[ui]', '2026-09-01_10-39-03__te*'):
        with pytest.raises(ValueError, match='cannot be published'):
            pr.sftp_batch(pr.Path(name), '/runs', stamp='1')

