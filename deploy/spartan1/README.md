# spartan1 deployment

The CI host serving the run archive and running the nightly QA suite. These
files are the live configuration on spartan1 (10.2.0.2), version-controlled
here so they are auditable and recoverable rather than living only on the
box. The adversarial audit flagged that the nightly script was unauditable
because it existed nowhere in git.

## What runs on spartan1

| File here | Lives on the box at | What it does |
|---|---|---|
| `nightly.sh` | `/data/qa/ci/nightly.sh` | The nightly QA run: reset the clone to `origin/main`, install, pytest once per box (`india`, then `us`), then the Camera 2 Cloud suite (`tests/c2c`, serial, against the lab cameras, only when `.env` has `C2C_CAMERA_PASS`; `C2C=0` skips it), publish evidence minus trace zips. Cron at 04:00 America/Chicago (`/etc/cron.d/qa-nightly-run`). One nightly at a time, 600 s per test, 4 h per box, and a box's run ends after 200 failures so pytest still writes its summary and archive; when the 4 h cap fires anyway, the labelled screenshots and live log are kept beside the archive as `<stamp>__tests-ui-<box>-PARTIAL-run-cap`. While a box's run is going, `live.json` in the served directory feeds the in-progress banner on the index and health pages. |
| `qa-weston.service` | `/etc/systemd/system/qa-weston.service` | The headless Wayland display Chrome needs to decode H.265 on the box's Intel GPU: a GL renderer on that GPU, no monitor, one socket at `/run/qa-weston/wl-qa`. The nightly runs the web-app legs headed on it when the socket is up (What the box needs, H.265). |
| `qa-runs-prune` | `/usr/local/bin/qa-runs-prune` | Deletes run folders older than 30 days. Cron at 03:00. |
| `nginx-qa-runs.conf` | inside `/etc/nginx/sites-enabled/default` | The `/qa-runs/` location: serves `/data/qa/runs` read-only, basic auth, dotfiles denied. |

## Access

- SSH alias `spartan1` = `soterix@10.2.0.2`.
- The archive is at `http://10.2.0.2/qa-runs/` behind HTTP basic auth (user
  `qa`; password in the team password store).
- Two read-only per-repo deploy keys on the box pull the repos over SSH.

## What the box needs

- The clone at `/data/qa/ci/Soterix-WebApp-QA` with a venv (`venv/`, Python
  3.12 on the box) and Google Chrome, installed 09/11/2026 with
  `sudo venv/bin/python -m playwright install chrome` (153 at the time), so
  pytest.ini's `--browser-channel chrome` applies as it does on a laptop.
  H.265 (measured 09/11 and 09/17/2026). The tenants stream H.265 and
  Chrome on Linux has no software decoder for it: it answers false to
  `MediaSource.isTypeSupported` for hvc1/hev1 unless it reaches a GPU
  decoder through VA-API, and it hands the decoded frames to the
  compositor only from its Wayland backend. The box decodes it since
  09/17/2026 through its CPU's Intel UHD 770 graphics (enabled in the BIOS
  that day; before that no Intel device was on the PCI bus), Ubuntu's
  `intel-media-va-driver` (`vainfo` on the Intel render node lists
  VAProfileHEVCMain) and a headless Weston with a GL renderer on that GPU
  (`qa-weston.service` here). What the nightly needs, all of it:
  - `XDG_RUNTIME_DIR` and `WAYLAND_DISPLAY` naming the Weston socket;
  - Chrome HEADED (`--headed`): `--headless` switches Chrome to its own
    headless backend whatever the ozone flag says, and that backend loses
    the GPU process on the first decoded frame;
  - `CHROME_ARGS="--ozone-platform=wayland"`: without it Chrome picks X11,
    and with no X server it does not start. Under Wayland Chrome takes
    the GPU from the compositor: the render node, the VA-API driver and
    the GL renderer all resolve to the Intel device on their own.
  The test session (conftest's launch args), the stream guard and
  tools/stream_probe.py read the same CHROME_ARGS, so the guard measures
  the browser the tests get; its skip reason names how it opened Chrome
  (headed or headless, how many flags), so a wiring fault reads as one.
  Audited 09/17/2026 against the real tests, four workers, headed on
  Weston: this one-flag set and an eight-flag set (VA-API and HEVC
  features on, the GPU blocklist ignored, driver checks ignored, the
  render node pinned, `LIBVA_DRIVER_NAME=iHD`) gave identical outcomes on
  the Views half (25 passed, the same 8 failures: the save-view defect and
  bookmarks); the probe played Thermal-14 (2560x1440, 9 fps, 0 dropped)
  under every flag subset tried, including none but the ozone flag. Chrome
  153 has VA-API decoding and HEVC on by default on Linux; a later Chrome
  may need a flag again, and the guard's `[STREAM]` line (`decodes H.265:
  NO`) is where that shows. Chrome on the box is not auto-updated
  (unattended-upgrades allows Ubuntu origins only), so a Chrome update is
  a deliberate act: re-run the probe after one.
  Dead ends, so nobody re-runs them: every non-Wayland backend (headless,
  Xvfb, X11, with native GPU memory buffers, zero-copy, no GPU
  compositing, the legacy decoder) decodes frames and then loses the GPU
  process handing them on (`Could not find SharedImageBackingFactory ...
  BGRA_8888, gmb_type: platform`); under Xvfb or headless Chrome opens the
  NVIDIA render node and never calls libva unless the node is pinned; the
  NVIDIA RTX A400 through `nvidia-vaapi-driver` 0.0.8 (a community shim)
  reached readyState 1 then PIPELINE_ERROR_DECODE (09/11);
  `--ozone-platform=drm` is not in Google Chrome's build. All of that is
  still installed and harmless. Without the Weston socket the nightly runs
  headless as before and the stream guard skips the livestream tests with
  the measured reason; the Windows runner (`deploy/windows-runner/`) stays
  as the documented fallback.
- `/data/qa/ci/Soterix-WebApp-QA/.env` (mode 600) with the QA Touch keys
  and one account per box the nightly runs: `QA_INDIA_USER`,
  `QA_INDIA_PASSWORD`, `QA_US_USER`, `QA_US_PASSWORD`. The suite reads the
  box's own pair when `BOX` is set (config/env/qa.py); a legacy `QA_USER`
  alone is not enough, and a box without its pair is skipped with a line in
  the log.

## Deploying a change

The copy here is the one of record. Edit it here, run it through review
like any other file, push, then install it from the box's own clone; cron
reads the file on each run, so nothing reloads. Copy from the clone, not
from a Windows checkout: Git on Windows may hand you the file with CRLF
line endings, and `/bin/sh` refuses a script whose first line ends in `\r`.

```bash
ssh spartan1 'cd /data/qa/ci/Soterix-WebApp-QA && git fetch -q origin && \
  git show origin/main:deploy/spartan1/nightly.sh > /tmp/nightly.sh.new && sh -n /tmp/nightly.sh.new && \
  sudo cp /tmp/nightly.sh.new /data/qa/ci/nightly.sh.new && sudo chmod 755 /data/qa/ci/nightly.sh.new && \
  sudo mv /data/qa/ci/nightly.sh.new /data/qa/ci/nightly.sh && echo installed'
```

Two rules in that command. It reads the file from `origin/main` with `git show`
rather than resetting the clone, so a nightly that is running from the clone
is not disturbed. And it installs by rename, never by copying over the live
file: a shell reads its script as it runs, so overwriting `nightly.sh`
in place can hand a running nightly half of the new text. A rename leaves
the running one its old file and gives cron the new one.

```bash

# nginx: after editing /etc/nginx/sites-enabled/default
ssh spartan1 'sudo nginx -t && sudo systemctl reload nginx'
```

```bash
# qa-weston.service: the headless display for H.265 (What the box needs)
ssh spartan1 'cd /data/qa/ci/Soterix-WebApp-QA && git fetch -q origin && \
  git show origin/main:deploy/spartan1/qa-weston.service | sudo tee /etc/systemd/system/qa-weston.service > /dev/null && \
  sudo systemctl daemon-reload && sudo systemctl enable --now qa-weston.service && sleep 3 && \
  systemctl is-active qa-weston.service && ls -l /run/qa-weston/wl-qa && \
  journalctl -u qa-weston.service --no-pager | grep "GL renderer"'
```

The last line must name the Intel GPU (`GL renderer: Mesa Intel(R) Graphics`);
a software renderer or the NVIDIA one means the vendor file or the render
node changed. The nightly log then opens with `H.265: Weston display at
/run/qa-weston/wl-qa`, and each box's `[STREAM]` line ends `decodes H.265: yes`.

Try it before the cron does, on a small target and a short cap, and read
the tail of the log:

```bash
ssh spartan1 'TARGET=tests/ui/maps TEST_TIMEOUT=300 /data/qa/ci/nightly.sh; tail -n 20 /data/qa/ci/nightly.log'
```

## Updating Chrome on the box

The archive index (http://10.2.0.2/qa-runs/) opens with a runners line: each
machine's Chrome from its newest run, and `stable X is out: update it` when
Google's stable is newer. That line is the prompt for this section.

Chrome comes from Google's apt repository (`google-chrome.sources`), which
`unattended-upgrades` does not cover (Ubuntu origins only), so the box's
Chrome stays where it was installed until someone updates it. That is on
purpose: a Chrome update is a deliberate act, done in daylight and
verified, not something the nightly discovers. Windows laptops update
themselves on relaunch, so they usually run a newer Chrome than the box;
the tests are written for the current stable, and the box should not fall
more than a major version behind it. The current stable per platform:
`https://versionhistory.googleapis.com/v1/chrome/platforms/linux/channels/stable/versions`.

```bash
# 1. what is installed and what is offered
ssh spartan1 'apt-cache policy google-chrome-stable | sed -n 2,3p'
# 2. update (Google's repo is already configured; playwright install chrome did that on 09/11/2026)
ssh spartan1 'sudo apt-get update -q && sudo apt-get install -y --only-upgrade google-chrome-stable && google-chrome --version'
# 3. prove H.265 still decodes on the new Chrome, the way the nightly opens it
ssh spartan1 'cd /data/qa/ci/Soterix-WebApp-QA && XDG_RUNTIME_DIR=/run/qa-weston WAYLAND_DISPLAY=wl-qa   CHROME_ARGS=--ozone-platform=wayland BOX=india venv/bin/python -c "from tests.shared.helpers.stream_health import decode_check;   print(decode_check(\"H.265\", \"chrome\", headed=True))"'
```

Step 3 must print `decodes: True` with `headed` in the browser name. A
`False` means the new Chrome needs a flag again: read the H.265 notes
under "What the box needs", try the probe with the eight-flag set recorded
there, and put whatever works back into `CHROME_ARGS` in `nightly.sh`.

## Recovering a stuck nightly

The script kills its own predecessor: the process group in its pid file,
and since 09/11/2026 any pytest still running from the clone (a stalled run
whose pid file was gone kept the single-run lock, and the next nightly's
legs all exited in 0 s), then releases the in-repo run lock. So a stuck
nightly clears itself the next night. To clear one now:

```bash
ssh spartan1 'pkill -u soterix -f "[n]ightly.sh"; pkill -u soterix -f "[p]ytest tests/ui"; sleep 5; \
  pkill -u soterix -KILL -f "[p]ytest tests/ui"; pkill -u soterix -KILL -f "playwright/driver/[n]ode"; \
  pkill -u soterix -KILL -f "[m]s-playwright"; rm -rf /tmp/playwright-artifacts-* /data/qa/ci/nightly.pid; \
  pgrep -u soterix -fc "[p]ytest tests/ui|[m]s-playwright"'   # expect 0
```

The brackets are not decoration. `pkill -f "pytest tests/ui"` also matches
the SSH shell running that very command line, kills it, and reports
nothing; the runs survive. `[p]ytest` matches `pytest` in a process list
but not the literal `[p]ytest` in its own command line (09/08/2026, learned
the slow way).

If the clone has drifted (the log says `Not possible to fast-forward`, or
`code:` names an old commit), the script's reset fixes it on its next run;
by hand it is `git -C /data/qa/ci/Soterix-WebApp-QA fetch origin && git -C
/data/qa/ci/Soterix-WebApp-QA reset --hard origin/main`. Evidence under
`reports/` is untracked and survives the reset.

## Retention and safety

- Evidence is pruned after 30 days on the box. The permanent record is the
  git ledger (`history/*.jsonl`), not the evidence.
- Trace zips never reach the box: a trace carries live session cookies
  and, on a fresh-login test, the account password in a request body.
  `nightly.sh` rsyncs with `--exclude=*.zip`, and `tools/publish_run.py`
  stages a copy without them. Keep traces local for `playwright
  show-trace`. The failure videos beside the traces DO travel: run.html
  links each one, and a password field shows dots on screen. Until
  09/11/2026 the whole traces/ folder was held back, so every video link on
  the served pages was dead.
