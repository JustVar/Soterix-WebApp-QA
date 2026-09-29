# Scheduled run on a Windows machine

These scripts run the UI tests on a schedule on one Windows machine. They
exist for the tests marked `livestream`: the QA server streams H.265, and
Windows Chrome decodes it out of the box. Chrome on Linux needs a GPU and a
Wayland display (`docs/LINUX_H265.md`). Nothing is scheduled today. Register
the task when the team wants a daily run.

| File here | What it does |
|---|---|
| `livestream-run.ps1` | The run: reset the clone to `origin/main`, install, `pytest tests/ui -m livestream --headed` with 2 workers. One run at a time, a 90 min cap, log in `logs\livestream-run.log`. |
| `register-task.ps1` | Registers the daily scheduled task (05:00 local by default) that runs it, with an interactive logon because the run is headed. |
| `kiosk-setup.ps1` | Makes the machine able to run unattended: no sleep, no display timeout, Windows Update held to active hours, Chrome's updater off. Elevated, safe to run again, and it reads every setting back. |

## What the machine needs

- Windows 10 or 11 with Google Chrome, Git for Windows and Python 3.14.
- The clone (any path: pass `-Repo` to both scripts) with a venv:

  ```powershell
  git clone https://github.com/Soterix-Systems/Soterix-WebApp-QA.git C:\qa\Soterix-WebApp-QA
  cd C:\qa\Soterix-WebApp-QA
  python -m venv venv
  venv\Scripts\python.exe -m pip install -r requirements.txt
  ```

- The decode check. Do it before anything else, because it is the reason
  this machine exists:

  ```powershell
  venv\Scripts\python.exe -c "from tests.shared.helpers.stream_health import decode_check; print(decode_check('H.265', 'chrome', headed=True))"
  ```

  Expected `{'decodes': True, ...}`. `False` means the HEVC Video Extensions
  are missing (Microsoft Store: "HEVC Video Extensions from Device
  Manufacturer", or the paid one). Install them and check again.
- `.env` in the clone (never committed) with the account the run signs in
  as: `QA_USER` and `QA_PASSWORD`. The run stops with a line in the log
  when `QA_USER` is missing.
- Automatic sign-in, set by a person at the machine with `netplwiz`. A
  headed browser needs a desktop, so the task runs only while somebody is
  signed in. `kiosk-setup.ps1` makes the checkbox reachable.

## Install

```powershell
cd C:\qa\Soterix-WebApp-QA
# 1. what the run would do, without running it
powershell -NoProfile -ExecutionPolicy Bypass -File deploy\windows-runner\livestream-run.ps1 -NoReset -DryRun
# 2. a trial on this machine, no reset
powershell -NoProfile -ExecutionPolicy Bypass -File deploy\windows-runner\livestream-run.ps1 -NoReset
Get-Content logs\livestream-run.log -Tail 30
# 3. the schedule
powershell -NoProfile -ExecutionPolicy Bypass -File deploy\windows-runner\register-task.ps1
Start-ScheduledTask -TaskName 'QA livestream run'
```

Step 1 is proven on a laptop. Steps 2 and 3 have not run since the pivot to
one QA server. Read the log after the first scheduled run.

Those commands assume a shell on the machine. Over ssh, run the script
through a scheduled task, never straight from the ssh session. Windows
OpenSSH kills the whole process tree when the session closes, and
`Start-Process`, `-WindowStyle Hidden` and `&` do not escape it. A run
started that way dies the moment the ssh command returns, and it dies
quietly: the lock is written, both output files stay at 0 bytes, and the
log has no end line. A scheduled task belongs to the scheduler, not to the
session, and survives.

## Reading a run

- `logs\livestream-run.log`: one line per step, the pytest `-rfEs` summary,
  and the path of the run page. `logs\livestream-run.out` holds the whole
  pytest output of the last run.
- The run page is `reports\runs\<run>\run.html` on this machine. Nothing
  leaves the machine. Before you share a run folder, run
  `python tools/evidence_scan.py reports/runs/<run> --redact`: a trace zip
  carries the session cookie, and a fresh-login test carries the password.
- The `[STREAM]` line in the pytest summary gives the frame count on the
  test camera and whether this Chrome decodes the codec. When every
  livestream test skipped, that line is the reason. The measurement is per
  session, so the next run measures again.

## Recovering a stuck run

The script kills its own predecessor at the next scheduled start. To clear
one now:

```powershell
$p = Get-Content C:\qa\Soterix-WebApp-QA\logs\livestream-run.pid
taskkill /PID $p /T /F
Remove-Item C:\qa\Soterix-WebApp-QA\logs\livestream-run.pid
```

The clone is disposable: the reset at each run discards local edits, so
never develop in it. Evidence under `reports\` is untracked and stays.
