# Windows runner for the livestream tests

The tests marked `livestream` need a tile that plays. The QA tenants stream
H.265, and Chrome decodes it only through a platform decoder: Windows
Chrome has one out of the box; Chrome on Linux only through a GPU's VA-API
on a Wayland display, which spartan1 has
(`deploy/spartan1/README.md`), so its nightly runs the livestream tests.
This runner is the fallback for the day that path breaks: one Windows
machine runs just those tests, on a schedule, publishing each run to the
same archive at http://10.2.0.2/qa-runs/. On spartan20 it runs daily at 02:30 local
(07:30 UTC), which is inside the machine's Windows Update active hours and ends before
spartan1's 09:00 UTC nightly starts: both drive the same US account, and the app
runs one search job per account, so the two must not overlap.

| File here | What it does |
|---|---|
| `livestream-run.ps1` | The run: reset the clone to `origin/main`, install, `pytest tests/ui -m livestream` once per box (`india`, then `us`, 2 workers), publish each archived run with `tools/publish_run.py`. One run at a time, a 90 min cap per box, log in `logs\livestream-run.log`. |
| `register-task.ps1` | Registers the daily scheduled task (05:00 local by default; spartan20 uses `-At 02:30`) that runs it, with an interactive logon because the run is headed. Registered on spartan20 on 09/25/2026. |
| `kiosk-setup.ps1` | Makes the machine able to run unattended: no sleep, no display timeout, Windows Update held to active hours, Chrome's updater off. Elevated, safe to run again, and it reads every setting back. |

## What the machine needs

- Windows 10 or 11 with Google Chrome. Prove the decoder before anything
  else (the reason this machine exists):

  ```powershell
  venv\Scripts\python.exe -c "from tests.shared.helpers.stream_health import decode_check; print(decode_check('H.265', 'chrome'))"
  ```

  Expected `{'decodes': True, ...}`. `False` means the HEVC Video Extensions
  are missing (Microsoft Store: "HEVC Video Extensions from Device
  Manufacturer", or the paid one); install and re-check.
- Git for Windows (it ships the OpenSSH client `publish_run.py` uses) and
  Python 3.12.
- The clone at `C:\qa\Soterix-WebApp-QA` (any path: pass `-Repo` to both
  scripts), with a venv:

  ```powershell
  git clone https://github.com/Soterix-Systems/Soterix-WebApp-QA.git C:\qa\Soterix-WebApp-QA
  cd C:\qa\Soterix-WebApp-QA
  python -m venv venv
  venv\Scripts\python.exe -m pip install -r requirements.txt
  ```

  The requirements pull the shared package from GitHub over HTTPS, so the
  machine's git credential (the one `git clone` used) needs read access
  to SOTERIX-QA-SHARED as well.
- `.env` in the clone (never committed) with the box accounts the run
  signs in as: `QA_INDIA_USER`, `QA_INDIA_PASSWORD`, `QA_US_USER`,
  `QA_US_PASSWORD`. A box without its pair is skipped with a line in the
  log. Copy the QA Touch keys too only if this machine should upload;
  the scheduled run does not.
- An SSH key for the publish account on spartan1: `ssh-keygen` on the
  machine, then Justin adds the public key with `setup-publish-user.sh
  add-key` (`deploy/spartan1/README.md`, "Hardening"). To prove it, run
  `sftp qa-publish@10.2.0.2` from the same account that the task runs as.
  `pwd` must print `/runs`.

## Install

```powershell
cd C:\qa\Soterix-WebApp-QA
# 1. a trial on this machine, one box, no reset, no publish
powershell -NoProfile -ExecutionPolicy Bypass -File deploy\windows-runner\livestream-run.ps1 -Boxes us -NoReset -NoPublish
Get-Content logs\livestream-run.log -Tail 30
# 2. the same with a publish, then find the run at http://10.2.0.2/qa-runs/
powershell -NoProfile -ExecutionPolicy Bypass -File deploy\windows-runner\livestream-run.ps1 -Boxes us -NoReset
# 3. the schedule
powershell -NoProfile -ExecutionPolicy Bypass -File deploy\windows-runner\register-task.ps1
Start-ScheduledTask -TaskName 'QA livestream run'
```

The task runs as the user who registered it, highest run level, without a
stored password (S4U). If `publish_run.py` reports `scp failed` only under
the task and not from a shell, re-register with `-StorePassword`.

Those commands assume a shell **on the machine**. Over ssh, run the script
through a scheduled task instead, never straight from the ssh session.

Windows OpenSSH kills the whole process tree when the session closes, and
`Start-Process`, `-WindowStyle Hidden` and `&` do not escape it. A run started
that way dies the moment the ssh command returns, and it dies quietly: the
first attempt wrote its lock, left both output files at 0 bytes, and left no
end line in `livestream-run.log`, so the log looked like a run still in
progress for half an hour. A scheduled task belongs to the scheduler, not to
the session, and survives.

The dead run's lock needs no cleaning up. `tools/run_lock.py` clears a lock
whose holder process is gone, so the next run takes it.

## Reading a run

- `logs\livestream-run.log`: one line per step, the pytest `-rfEs`
  summary per box, and the publish result. `logs\livestream-<box>.out`
  holds the whole pytest output of the last run for that box.
- The archive lists the run as `<stamp>__tests-ui` from this host; the
  run's `run.html` names the box and the product.
- The session stream guard prints one `[STREAM]` line per run: the frame
  count on the box's test camera and whether this Chrome decodes the
  codec. A run whose livestream tests all skipped has that line as the
  reason (the tenant streamed nothing at that moment); the guard's
  measurement is per session, so the next run measures again.

## Recovering a stuck run

The script kills its own predecessor at the next scheduled start. To clear
one now:

```powershell
$p = Get-Content C:\qa\Soterix-WebApp-QA\logs\livestream-run.pid
taskkill /PID $p /T /F
Remove-Item C:\qa\Soterix-WebApp-QA\logs\livestream-run.pid
```

## Retention and safety

- Trace zips never leave the machine: `publish_run.py` stages a copy
  without them (a trace carries the session cookie and, on a fresh-login
  test, the account password). Failure videos do travel.
- The clone is disposable: the reset at each run discards local edits, so
  never develop in it. Evidence under `reports\` is untracked and stays.
