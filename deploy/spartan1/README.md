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
  Measured the same day: Chrome on Linux answers false to
  `MediaSource.isTypeSupported` for H.265 (hvc1/hev1) while Windows Chrome
  answers true, and the QA tenants stream H.265 (codecType 8). So the
  tests that need a playing tile cannot pass on this box; the session
  stream guard (tests/shared/helpers/stream_health.py) skips them here with
  that measurement, and they run on a Windows or Mac runner.

  The box has an NVIDIA RTX A400 (driver 610.57), whose NVDEC decodes
  H.265, and the chain was tried on 09/11/2026 (all still installed, all
  harmless to leave): `nvidia-vaapi-driver` 0.0.8, `vainfo`, `libva2`,
  `xvfb`, and `soterix` in the `render` and `video` groups. What each step
  answered, so the next attempt starts where this one stopped:
  - `vainfo` with `LIBVA_DRIVER_NAME=nvidia NVD_BACKEND=egl` lists
    VAProfileHEVCMain (the `direct` backend fails to init on driver 610).
  - Chrome headless, any flags: `MediaSource.isTypeSupported` false for HEVC.
  - Chrome HEADED under `xvfb-run` with `CHROME_ARGS="--ignore-gpu-blocklist
    --enable-features=VaapiOnNvidiaGPUs,VaapiVideoDecodeLinuxGL,PlatformHEVCDecoderSupport,VaapiIgnoreDriverChecks,AcceleratedVideoDecodeLinuxGL
    --use-gl=angle --use-angle=gl"` (tools/stream_probe.py reads that variable):
    isTypeSupported true for the tenant's exact type
    (`hvc1.1.6.L153.B0,flac`), the tile's player reaches readyState 1 with
    its 640x360 metadata, then `PIPELINE_ERROR_DECODE`; the VA driver log
    shows profile queries and a terminate, never a decode session. The same
    proof on a Windows Chrome plays at readyState 4 within 5 s.
  - Not tried: the upstream driver built from source (Ubuntu ships 0.0.8;
    the project does not support Chromium), a Windows VM with the GPU passed
    through. Until one of those is proven, the livestream tests run from a
    Windows or Mac Chrome.
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

Try it before the cron does, on a small target and a short cap, and read
the tail of the log:

```bash
ssh spartan1 'TARGET=tests/ui/maps TEST_TIMEOUT=300 /data/qa/ci/nightly.sh; tail -n 20 /data/qa/ci/nightly.log'
```

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
