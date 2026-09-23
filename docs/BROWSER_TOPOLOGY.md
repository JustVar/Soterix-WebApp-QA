# Where the browser runs, and what the second machine is for

Written for: the QA team and whoever inherits this suite.

The lab has 2 machines that can run a browser. This page says which one runs
the tests, why, and what the other one is for. It records the measurements
behind that choice so nobody has to take it on trust or repeat the work.

Researched and measured 09/22/2026. Register rows 117, 118 and 119 hold the
short version.

## The answer

The tests run on **spartan1**, and the browser runs there too, in the same
process tree as pytest. Nothing is split across machines.

**spartan20** is the Windows machine. It is not in the nightly. It is there
for 2 jobs:

1. A person's own Chrome, on the operating system customers use, for checking
   something by hand.
2. A second, independent client for concurrency and load work. See
   "The second machine" below. That work is planned, not built.

## The 2 machines

| | spartan1 | spartan20 |
|---|---|---|
| Address | 10.2.0.2 | 10.2.0.39 |
| System | Ubuntu | Windows 11 Home |
| Processor | 28 cores | i9-12900H, 20 threads |
| Memory | 15 GB | 32 GB |
| Graphics | Intel, VA-API | Intel Iris Xe |
| Chrome | 153, headed on a Weston display | 153, headed on the desktop |
| Runs the nightly | yes | no |
| Reached by | `ssh spartan1` | `ssh soterix@10.2.0.39`, AnyDesk |

## Why the browser stays with pytest

### The question we asked

Customers use Chrome on Windows. The suite runs Chrome on Linux. Playwright
can drive a browser on another machine, so the tests could run on spartan1
while the browser ran on spartan20. That would put a real Windows Chrome in
front of the app without moving the test code, the credentials or the archive.

### What the measurements said

The machines are not different enough to matter.

- Both decode H.265. Both play the app's livestream.
- The frame rate cannot tell them apart. The cameras are configured at 10 fps,
  so every healthy browser lands at the same ceiling. 3 runs on 1 laptop gave
  10.8, 9.0 and 5.6 fps over the window while their last 10 s gave 12.0, 12.0
  and 11.9. The spread is the time the stream takes to start, which belongs to
  the tenant, not to the browser.
- The 2 Chromes are 7 patch builds apart, on the same engine.
- The suite has no code whose behaviour depends on the operating system. The
  1 platform branch is on a framework guard, not on an app test. Downloads,
  the clipboard and dialogs all go through Chrome's own protocol, never an
  operating-system window.
- Register row 83 is this team's own controlled comparison: an app defect
  failed the same way on the box and on a Windows laptop. The variable that
  changed the outcome was the worker count, not the operating system.

### What the evidence said about the mechanism

The split needs `playwright run-server`. Against it:

- Playwright's maintainers hid that command from the help output in November
  2025, calling it internal, and closed the request to document it by hiding
  it.
- The server **drops Chrome launch flags without `--unsafe`**, and says
  nothing. `CHROME_ARGS` would vanish.
- The server has no authentication. `--host 0.0.0.0` puts it on the network.
- The client and the server must be on the same major and minor Playwright
  version. A mismatch ends every leg with a 428.
- Whether H.265 decode survives a locked screen **could not be measured**. A
  lock sent from outside cannot be undone from outside, so the attempt would
  leave the machine locked with no way back in.
- Outbound SSH from that machine hangs when it needs an answer and has no
  terminal: a `git clone` waiting on a host key, or an `sftp` reading an
  interactive stdin. Each hung child holds its parent session open, which reads
  as "SSH is unreliable" and is not. Measured 09/22/2026: 6 connections in a
  row, each under a second, once the hung children were cleared. Anything run
  there needs `BatchMode=yes`, `StrictHostKeyChecking=accept-new` and a batch
  file rather than stdin.

### What the measurements also said, in its favour

The data path itself is sound, and this is recorded so the question can be
reopened honestly:

- Screenshots, traces (63 KB, 15 entries, valid), video, file uploads from the
  caller's disk and downloads all reach the calling machine.
- 8 headed browsers ran at once. 4 of them cost 36 Chrome processes and 2.4 GB.
- The network adds 1.5 to 2.5 ms per call, about 1 to 2 percent of a 40 minute
  leg.

5 things would need code: pin `channel: chrome` in the launch options, use
`video.save_as` (`video.path` raises when remote), install ffmpeg on the box,
reap the orphaned Chrome processes after a leg, and wrap the connect in a
retry, because a network blip ends the session in 1 ms and nothing reconnects.

### The conclusion

The split costs a second machine in the nightly's critical path, a second
version pin, an unmeasured risk and a silent flag-dropping failure mode. It
buys fidelity on an axis the evidence says is not the discriminating one.
So the browser stays with pytest.

## The second machine

The reason to keep spartan20 is not a more realistic browser. It is that it
is a **second independent client**: its own address, its own sessions, its own
browser processes.

The defects this team has already found point that way. Register row 83 says
the worker count changed the outcome where the operating system did not. Row
100 says the server runs 1 search job for each account with no cancel, and
that this held 1 worker for 40 minutes. Those are concurrency defects, and
they are customer-facing.

spartan1 alone cannot make 2 real clients. It runs 1 pytest session with
several workers, from 1 address. 2 machines can put 2 independent clients on
1 tenant, 1 account or 1 edge box at the same time, which is how customers
actually collide with each other.

For that job the browser must run **on** spartan20, not be driven from
spartan1. 1 test process driving 2 browsers is not 2 users. `deploy/windows-runner/`
already holds that shape: pytest runs on the Windows machine and publishes its
run back to the archive.

### What the machine needs first

It is a test machine, so it can be set up as a kiosk. The state on 09/22/2026
and what has to change:

| Setting | State on 09/22 | Wanted |
|---|---|---|
| Sleep on AC | off | off |
| Display off on AC | off | off |
| Screen lock | nothing forces one | keep it that way |
| Chrome updates | updater services and task all disabled, pinned at 153.0.8010.53 | on demand, so a run is never surprised |
| Windows Update | active hours 02:00 to 20:00 local | no restart during a run |
| Sign in after a restart | automatic | automatic, or the headed browser cannot start |
| Admin channel | SSH, measured reliable | SSH, with WinRM as a second way in |

Two of those rows were wrong when first written, and both were found by reading
the machine rather than the script that set it up:

- **Windows Update was set with Group Policy keys, on an edition that has no
  policy engine.** This is Windows 11 *Home*. `NoAutoRebootWithLoggedOnUsers`
  and `AUOptions` under `HKLM\SOFTWARE\Policies` were read by nothing, so the
  machine was free to restart whenever it liked while the page said otherwise.
  The keys are removed. Active hours is what Home honours, and it is set to
  02:00-20:00 local, which covers the 09:00 UTC nightly at 03:00 local. The
  span may be at most 18 hours, so 20:00-02:00 is left for Windows to restart in.
- **Chrome's updater was only half off.** The scheduled task was disabled and
  the check reported the updater services "do not exist on this box". They do:
  `GoogleUpdaterService` and `GoogleUpdaterInternalService`, both Automatic and
  merely stopped at the moment they were looked at. A stopped Automatic service
  starts again. Both are Disabled now.

Chrome no longer patches itself here, so somebody has to update it on purpose.
That is the trade the row asks for: a known version beats a current one when the
machine's job is to reproduce what a customer sees.

**Automatic sign-in is the setting that decides whether this machine works.** A
restart without it leaves no desktop, and the run is headed, so nothing plays.

That statement was briefly removed from this page on 09/22/2026 on the strength
of this:

```
H.265: {'decodes': True, 'browser': 'Chrome 153.0.8010.53 on Windows, headless, 0 flags'}
```

which was read as headless being fine. It is not evidence of that.
`decode_check` calls `MediaSource.isTypeSupported`, so it reports what Chrome
**claims**, and a claim is not a decoded frame. The run is the measurement, and
it disagreed: 28 failed, 2 passed, 8 errors, every failure a tile that never
played.

One test, twice, minutes apart, same tenant, only the browser mode different:

| | headless | headed |
|---|---|---|
| Result | failed, 161 s | **passed, 25 s** |
| `readyState` | 1 -> 1 | **4** |
| `currentTime` | 0.00 -> 0.00 | 0.12 -> 0.14 |
| Frames on the socket | 124 in 8 s | 116 in 8 s |
| `isTypeSupported` | **yes** | yes |

The socket delivers either way. Headless Chrome on Windows says it supports
H.265 and then never decodes it, leaving the player at `readyState 1` while the
app shows "The camera failed to load".

So both machines run headed, for different reasons: Linux Chrome reaches H.265
only through VA-API on Wayland, and Windows Chrome reaches it only with a
desktop. The Windows scheduled task therefore logs on interactively, and the
machine signs in automatically so that a desktop exists after a restart.

A warning this leaves behind: **a passing `decode_check` does not mean a tile
will play.** A failing one is still conclusive, and the guard's skip reasons
still rest on it. Treat `true` as "not ruled out" (register row 128).

## Reopening this

Reopen it if any of these becomes true:

- The suite grows tests that read the operating system: a file picker, a
  print dialog, the clipboard outside Chrome's protocol, or image comparisons.
- A customer reports something that only happens on Windows, and the box
  cannot reproduce it.
- Playwright documents `run-server` and gives it authentication.

To settle it with data rather than argument, run the same suite on both
machines on the same night, with the same box and the same worker count, and
compare **verdicts**, not frame rates. Remove every failure that names a known
tenant or concurrency cause. If no verdict differs, the operating system is
not the variable. That run needs no new code.

## The measuring tool

`tools/livestream_bench.py` plays 1 camera on 1 browser and reports what it
saw.

```
BOX=us venv/Scripts/python.exe tools/livestream_bench.py --seconds 40
BOX=us venv/Scripts/python.exe tools/livestream_bench.py --ws ws://10.2.0.39:3000/ --headed --seconds 40
```

It answers "does this browser play the stream at all". It does not answer
"which browser plays it better", and it never did: the source caps at 10 fps,
and the count includes frames the player dropped. The first comparison
published from it compared tails and read as a difference where there was
none. Read `first_frame_s`, `restarts` and `dropped` before the rate.
