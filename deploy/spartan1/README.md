# spartan1 deployment

spartan1 (10.2.0.2) runs the nightly QA suite and serves the run archive.
The files in this folder are the copies of record for the configuration on
the box. Edit a file here, push it, then install it on the box.

## What runs on spartan1

| File here | Path on the box | What it does |
|---|---|---|
| `nightly.sh` | `/data/qa/ci/nightly.sh` | The nightly run. See "What the nightly does". |
| `cron.d-qa-nightly-run` | `/etc/cron.d/qa-nightly-run` | Starts `nightly.sh` at 09:00 UTC each day as user `soterix`. That is 04:00 in Chicago during daylight time. |
| `cron.d-qa-runs-prune` | `/etc/cron.d/qa-runs-prune` | Starts `qa-runs-prune` at 03:00 UTC each day as root. |
| `qa-runs-prune` | `/usr/local/bin/qa-runs-prune` | Deletes served run folders that are older than 30 days. |
| `qa-weston.service` | `/etc/systemd/system/qa-weston.service` | The headless Wayland display that Chrome needs to decode H.265. See "H.265 on the box". |
| `nginx-qa-runs-site.conf` | `/etc/nginx/sites-available/qa-runs` | The archive over HTTPS on port 8444. It serves `/data/qa/runs` read-only with basic auth and does not serve a name that starts with a dot. |
| `setup-https-archive.sh`, `nginx_port80_redirect.py` | Run from the clone | The one-time move of the archive to HTTPS. See "Hardening". |
| `setup-publish-user.sh` | Run from the clone | The one-time setup of the publish account, and the command that adds a person's key. See "Hardening". |

## What the nightly does

1. It stops a nightly that is still alive from the day before, and releases
   the run lock.
2. It resets the clone at `/data/qa/ci/Soterix-WebApp-QA` to `origin/main`
   and installs the requirements.
3. It checks the Weston display and writes one `H.265:` line.
4. It runs `tests/ui` one time for each box: `india`, then `us`. Each run
   uses 4 workers.
5. It runs the Camera 2 Cloud suite (`tests/c2c`) one time, with 1 worker,
   against the lab cameras.
6. It copies each run folder to `/data/qa/runs` without the trace zips.
7. It rebuilds the served index and the health page.

Limits: 600 s for each test, 4 hours for each leg, and a leg stops after 200
failures. While a leg runs, `live.json` in the served directory feeds the
"in progress" banner on the index and health pages.

The nightly is unarmed. It does not write to QA Touch and it does not add a
ledger row.

You can run the script by hand with a smaller scope:

```bash
TARGET=tests/ui/licenses /data/qa/ci/nightly.sh   # one module on each box, and the full camera suite
BOXES=india /data/qa/ci/nightly.sh                # one box, and the full camera suite
BOXES= /data/qa/ci/nightly.sh                     # cameras only
C2C=0 /data/qa/ci/nightly.sh                      # no camera run
TEST_TIMEOUT=120 /data/qa/ci/nightly.sh           # a short cap for a trial
TARGET=tests/ui/maps BOXES=india C2C=0 /data/qa/ci/nightly.sh   # the smallest trial
```

`TARGET` changes the web-app legs only. The camera suite always runs in
full unless you set `C2C=0`. A run by hand stops a nightly that is in
progress. The nightly starts at 09:00 UTC. Before you start a run by hand,
make sure that the last block in the log ends with `nightly done`.

## Access

- The box is on the lab network, 10.2.0.0/24. From a different network, ask
  Justin for the route.
- Log in as user `soterix` with an SSH key. Justin adds new keys to
  `/home/soterix/.ssh/authorized_keys`.
- Add this to `~/.ssh/config` on your machine. The commands in this file use
  the alias.

  ```
  Host spartan1
      HostName 10.2.0.2
      User soterix
  ```

- The archive is at `https://10.2.0.2:8444/qa-runs/`. The old address,
  `http://10.2.0.2/qa-runs/`, redirects to it. It uses basic auth with the
  user `qa`. The password is in the team password store.
- To publish a run from a laptop, a person needs a key on the account
  `qa-publish`, not on `soterix`. See "Hardening".
- The box pulls the repos over SSH with 2 deploy keys. Each key is read-only
  and belongs to one repo.
- User `soterix` owns `/data/qa/ci`, so an install of `nightly.sh` does not
  need sudo. The systemd unit, the cron files and nginx need sudo.

## Hardening

The box has 3 protections for the evidence that it serves. The setup of
each one was done on 09/18/2026. This section is the record of what was
done, and the procedure for a new box.

| Protection | What it stops | Setup |
|---|---|---|
| The evidence scan | A password or a session cookie in a log file that the archive serves. `nightly.sh` runs `tools/evidence_scan.py --redact` on each new run folder, and copies only a folder that the scan marked as clean. | Install `nightly.sh` ("Install a change on the box"). Then scan what the archive has now, one time: see below. |
| The publish account | A laptop key that can read the box. `tools/publish_run.py` copies with sftp, so the account `qa-publish` needs no shell. sshd keeps it in a jail that holds the served run folders and nothing else. | `sudo sh deploy/spartan1/setup-publish-user.sh` |
| HTTPS | The archive password in clear text on the network. The archive moves to `https://10.2.0.2:8444/qa-runs/`. The old address redirects to it. | `sudo sh deploy/spartan1/setup-https-archive.sh` |

### Scan what the archive has now

The nightly scans new folders only. Do this one time, after you install
`nightly.sh`, for the folders that the archive got before the scan existed:

```bash
ssh spartan1 'cd /data/qa/ci/Soterix-WebApp-QA && venv/bin/python tools/evidence_scan.py --runs-dir /data/qa/runs --redact'
```

The command prints the file and the kind of each secret that it masked. It
does not print a value.

### Set up the publish account

1. On the box, from the clone: `sudo sh deploy/spartan1/setup-publish-user.sh`
2. For each person who publishes runs, copy their public key to the box and
   run: `sudo sh deploy/spartan1/setup-publish-user.sh add-key <person>.pub`
3. From that person's laptop, make sure that sftp works and a shell does
   not:

   ```bash
   sftp qa-publish@10.2.0.2      # "pwd" must print /runs, and "ls /" must show runs only
   ssh qa-publish@10.2.0.2 id    # must not print a uid
   ```

4. The person needs no setting. `tools/publish_run.py` uses this account
   and the path `/runs`, which is the served directory inside the jail.
5. Keep `/home/soterix/.ssh/authorized_keys` for the people who operate the
   box. Do not add a key there for a person who only publishes runs.

To remove a run that a laptop published, use sudo on the box:
`sudo rm -rf /data/qa/runs/<run>`. The files belong to `qa-publish`, so user
`soterix` cannot remove them. The prune removes them after 30 days.

What the script does:

- It makes the account with no shell and no password, and the group
  `qa-runs` for the account and user `soterix`.
- It sets `/data/qa/runs` to mode 3775. The group can add a folder. Only
  the owner of a folder can rename it or remove it, so a laptop cannot
  replace a run of the nightly or the index page. It can replace a run that
  it published.
- It makes the jail `/srv/qa-publish`, which root owns, and mounts the
  served directory in it as `/runs` (1 line in `/etc/fstab`).
- It adds `/etc/ssh/sshd_config.d/qa-publish.conf`: sftp only, in the jail,
  no port forwarding.
- It sets the `.env` of the clone to mode 600 if it has a different mode.

Before it reloads sshd, the script compares the sshd settings of user
`soterix` from before and after. It also makes sure that the jail and the
sftp-only rule apply to `qa-publish`. If a check fails, it removes its sshd
file and does not reload.

The `add-key` command accepts a file with 1 public key on 1 line. It refuses
a private key file and a file with 2 keys.

### Move the archive to HTTPS

1. On the box, from the clone: `sudo sh deploy/spartan1/setup-https-archive.sh`
2. Do the 2 checks that the script prints.
3. Install the new `qa-runs-prune` ("Install a change on the box"). It also
   removes what a publish leaves behind.

The site uses the box's mkcert certificate, the same one as the asset
tracker. The certificate names `spartan1` and `10.2.0.2`, and it is good
until 10/12/2028.

Who needs the certificate authority (CA) file on their machine:

- No person needs it to run tests, to publish a run or to use the tools.
  The tests talk to the QA tenants, not to the box. A publish uses sftp,
  which does not use certificates. No tool in the repos reads the archive
  over HTTPS.
- A person who opens the archive in a browser sees a warning page if the CA
  is not installed. They can continue past it, and the connection is still
  encrypted. To remove the warning, install the CA one time:
  `docs/CA_CERT_DISTRIBUTION.md` in the asset tracker repo. A laptop that
  opens the asset tracker with no warning already has it.
- `curl` in Git Bash has its own CA list and does not read the Windows
  store. Use `curl -k` for a check from Git Bash.

The script keeps the old files in `/etc/nginx/qa-runs-backup-<time>/`. If
nginx refuses the new configuration, the script puts the old files back.

## What the box needs

- The clone at `/data/qa/ci/Soterix-WebApp-QA` with a venv at `venv/`
  (Python 3.12).
- Google Chrome from Google's apt repository. `pytest.ini` sets
  `--browser-channel chrome`, the same as on a laptop. Do not install
  Playwright's Chromium.
- `/data/qa/ci/Soterix-WebApp-QA/.env` with mode 600. It holds one account
  pair for each box: `QA_INDIA_USER`, `QA_INDIA_PASSWORD`, `QA_US_USER`,
  `QA_US_PASSWORD`. The nightly skips a box that has no pair and writes a
  line in the log. A `QA_USER` value alone is not sufficient.
- `C2C_CAMERA_PASS` in the same `.env` for the camera suite. Without it the
  nightly skips that suite and writes a line in the log.
- Read access to the shared package. `requirements.txt` names
  `soterix-qa-shared` with an HTTPS address, and the repo is private. The
  box has a read-only deploy key for it, a `Host github-shared` entry in
  `~/.ssh/config` that uses the key, and this rewrite:
  `git config --global url."git@github-shared:Soterix-Systems/SOTERIX-QA-SHARED.git".insteadOf "https://github.com/Soterix-Systems/SOTERIX-QA-SHARED.git"`.
  Without them the `pip install` in the nightly fails.
- No `QATOUCH_UPLOAD` or `QATOUCH_RUN_KEY` line in the `.env`. One of them
  arms the nightly.
- The packages in "H.265 on the box".

## A leg is missing or a run looks wrong

Read the log first. Each nightly writes a block to `/data/qa/ci/nightly.log`.

```bash
ssh spartan1 'grep -n "nightly start" /data/qa/ci/nightly.log | tail -n 1'
ssh spartan1 'tail -n 80 /data/qa/ci/nightly.log'
```

A good night has these lines, in this order: `nightly start`, `code:`,
`H.265:`, `india pytest exit`, `us pytest exit`, `c2c pytest exit`,
`served index and health page rebuilt`, `nightly done`.

| Line in the log | Meaning | Action |
|---|---|---|
| No `nightly start` line for today | Cron did not start the script. | Make sure that `/etc/cron.d/qa-nightly-run` exists and that `systemctl is-active cron` prints `active`. |
| `previous nightly (group N) still alive after a day: killing it` | The run of the day before did not finish. The script stopped it. | Find the test that stalled in the run of the day before. |
| `pytest from an earlier run still alive with no pid file: killing it` | The same, but the pid file was gone. | The same. |
| `code:` names an old commit | The fetch failed, so the clone did not move. | Run the `git fetch` by hand on the box and read the error. |
| `H.265: Weston display at ...` | The display is up. The legs run headed and the livestream tests run. | None. |
| `H.265: no Weston socket ...` | Weston is not running. | `sudo systemctl start qa-weston` |
| `H.265: the Weston socket exists but nothing answers on it` | Weston stopped and left its socket file. | `sudo systemctl restart qa-weston` |
| `H.265: no Intel render node ...` | The CPU graphics are off in the BIOS, or the i915 driver did not load. | Enable the CPU graphics in the BIOS. |
| `=== <box> skipped: QA_<BOX>_USER is not set` | The `.env` on the box has no account pair for that box. | Add the pair to the `.env` on the box. |
| `=== c2c skipped: C2C_CAMERA_PASS is not set` | The `.env` on the box has no camera password. | Add it to the `.env` on the box. |
| `pytest exit: 0` | All tests passed. | None. |
| `pytest exit: 1` | Some tests failed. This is the usual result. | Open the run in the archive. |
| `pytest exit: 2` after minutes or hours | A web-app leg stopped at 200 failures. The log says `stopping after 200 failures`. The archive index shows "Interrupted". | Open the run in the archive. Its `One cause` line names the shared error. |
| `pytest exit: 2` after 0 s or 1 s | The run lock refused the leg. A pytest run from the clone was alive, or it left its lock. | Make sure that no pytest runs on the box. Then release the lock: `ssh spartan1 'cd /data/qa/ci/Soterix-WebApp-QA && venv/bin/python tools/run_lock.py release --env qa --force'` |
| `pytest exit: 3` | pytest had an internal error. | Read the `INTERNALERROR` lines above the exit line. |
| `pytest exit: 4` | pytest refused the command line. | Read the usage error above the exit line. |
| `pytest exit: 5` | pytest collected no tests. The `TARGET` path is wrong. | Correct `TARGET`. |
| `pytest exit: 7` | The preflight refused the run. The tenant did not answer, or it refused the account. | Read the `PREFLIGHT:` line above the exit line. |
| `pytest exit: 124` | The leg hit the 4 hour cap. The script kept the screenshots and the log in a `PARTIAL-run-cap` folder. | Find the test that stalled. The last lines of `run.log` in that folder name it. |
| `THIS RUN WAS NOT ARCHIVED` | The archive step failed. The line gives the error and the free disk space. | Free disk space if it is low, then run the leg again. |
| `evidence_scan: N run folder(s) read, M secret(s) redacted.` | The scan ran. `M` above 0 means that a log held a secret, and the served copy has `***` in its place. | For `M` above 0, read the lines above it. They name the file and the kind of secret. Find the code that printed it, and correct it. |
| `evidence scan had errors ... was not published` | The scan could not read or write a file in a run folder. That folder has no `.evidence_scanned` mark, and the archive does not have it. The other folders are served. | Read the `ERROR` line above it. It names the file. Correct the file's permissions. The next nightly scans the folder again and publishes it. |
| `served index rebuild FAILED` | The health tool failed. The run folders are served, but the index is old. | Run `venv/bin/python tools/health_summary.py --runs-dir /data/qa/runs` on the box and read the error. |

If the log is good but a run is not in the archive, check the disk:
`ssh spartan1 'df -h /data'`.

## Get a trace from a nightly run

A trace holds a session cookie, and sometimes a password. For that reason
the trace zips stay in the clone on the box. The served archive does not
have them. The clone keeps a run for a short time only: see "Retention
and safety". Get the trace in the first 3 days.

1. Open the failure in the served `run.html`. It shows the run folder name
   and the file name of the trace.
2. List the traces of that run:

   ```bash
   ssh spartan1 'ls /data/qa/ci/Soterix-WebApp-QA/reports/runs/<run>/traces/'
   ```

3. Copy the trace to your machine:

   ```bash
   scp "spartan1:/data/qa/ci/Soterix-WebApp-QA/reports/runs/<run>/traces/<name>-trace.zip" .
   ```

4. Open it: `venv\Scripts\playwright show-trace <name>-trace.zip`
5. Delete your copy when you are done. Do not attach a trace to a ticket or
   a chat.

## Install a change on the box

Install from the clone on the box, not from a Windows checkout. Git on
Windows can give the file CRLF line endings, and `/bin/sh` refuses them.

### nightly.sh

```bash
ssh spartan1 'cd /data/qa/ci/Soterix-WebApp-QA && git fetch -q origin && \
  git show origin/main:deploy/spartan1/nightly.sh > /data/qa/ci/nightly.sh.new && \
  sh -n /data/qa/ci/nightly.sh.new && chmod 755 /data/qa/ci/nightly.sh.new && \
  mv /data/qa/ci/nightly.sh.new /data/qa/ci/nightly.sh && echo installed'
```

The command has 2 rules.

- It reads the file with `git show`. It does not reset the clone, so a
  nightly that runs from the clone is not disturbed.
- It installs with a rename. A shell reads its script while it runs. If you
  copy over the live file, a nightly that is running can read half of the
  new text.

Cron reads the file at each start, so you do not reload anything.

Then run a trial with a small target, and read the end of the log:

```bash
ssh spartan1 'TARGET=tests/ui/maps BOXES=india C2C=0 TEST_TIMEOUT=300 /data/qa/ci/nightly.sh; tail -n 20 /data/qa/ci/nightly.log'
```

### qa-weston.service

```bash
ssh spartan1 'cd /data/qa/ci/Soterix-WebApp-QA && git fetch -q origin && \
  git show origin/main:deploy/spartan1/qa-weston.service | sudo tee /etc/systemd/system/qa-weston.service > /dev/null && \
  sudo systemctl daemon-reload && sudo systemctl enable --now qa-weston.service && sleep 3 && \
  systemctl is-active qa-weston.service && ls -l /run/qa-weston/wl-qa && \
  journalctl -u qa-weston.service --no-pager | grep "GL renderer"'
```

The last line must name the Intel GPU: `GL renderer: Mesa Intel(R) Graphics`.
If it names a software renderer or the NVIDIA GPU, the vendor file or the
render node changed.

### Cron files

```bash
ssh spartan1 'cd /data/qa/ci/Soterix-WebApp-QA && git fetch -q origin && \
  git show origin/main:deploy/spartan1/cron.d-qa-nightly-run | sudo tee /etc/cron.d/qa-nightly-run > /dev/null'
```

Use the same command for `cron.d-qa-runs-prune` and `/etc/cron.d/qa-runs-prune`.
For the prune script, use it for `qa-runs-prune` and
`/usr/local/bin/qa-runs-prune`, then run `sudo chmod 755` on the file.

Run the `ssh` commands in this file from Git Bash. PowerShell changes the
quotes inside them.

### nginx

Edit `/etc/nginx/sites-enabled/default` on the box, then:

```bash
ssh spartan1 'sudo nginx -t && sudo systemctl reload nginx'
```

## H.265 on the box

The tenants stream H.265. Chrome on Linux has no software decoder for it.
Chrome decodes H.265 only through the GPU's VA-API decoder, and it shows
the decoded frames only from its Wayland backend.

The box has these parts. The versions were read on 09/18/2026.

| Part | On the box |
|---|---|
| GPU | The CPU's Intel UHD 770 graphics, enabled in the BIOS. |
| VA-API driver | Ubuntu package `intel-media-va-driver` 24.1.0. |
| Check tool | Ubuntu package `vainfo` 2.12.0. |
| Display | Ubuntu package `weston` 13.0.0, started by `qa-weston.service`, with a GL renderer on the Intel GPU. |
| Browser | `google-chrome-stable` 153.0.8010.47. |
| Groups of user `soterix` | `video` and `render`. |

The nightly sets 4 things for the web-app legs when the display is up:

- `XDG_RUNTIME_DIR=/run/qa-weston` and `WAYLAND_DISPLAY=wl-qa`. They name
  the Weston socket.
- `--headed`. With `--headless`, Chrome uses its own headless backend and
  ignores the Wayland flag. That backend loses the GPU process on the first
  decoded frame.
- `CHROME_ARGS="--ozone-platform=wayland"`. Without it Chrome selects X11.
  The box has no X server, so Chrome does not start.

No other Chrome flag is necessary. Under Wayland, Chrome finds the Intel
GPU, the VA-API driver and the GL renderer without help. An audit compared
this 1 flag with a set of 8 flags on the real tests with 4 workers, on
Chrome 153. The results were identical.

The test session, the stream guard and `tools/stream_probe.py` read the
same `CHROME_ARGS`. Thus the guard measures the browser that the tests get.
The guard's skip reason says how it opened Chrome: headed or headless, and
the number of flags.

When the display is not usable, the legs run headless and the stream guard
skips the livestream tests. The skip reason gives the measurement. The
Windows runner in `deploy/windows-runner/` is the fallback for those tests.

### Prove that H.265 decodes

```bash
ssh spartan1 'cd /data/qa/ci/Soterix-WebApp-QA && XDG_RUNTIME_DIR=/run/qa-weston WAYLAND_DISPLAY=wl-qa \
  CHROME_ARGS=--ozone-platform=wayland BOX=india venv/bin/python -c \
  "from tests.shared.helpers.stream_health import decode_check; print(decode_check(\"H.265\", \"chrome\", headed=True))"'
```

The output must show `'decodes': True`, and the browser name must contain
`headed`. In a run, the `[STREAM]` line is in the terminal summary below
`stream guard`. On a good run it ends with `decodes H.265: yes`.

### Set up H.265 on a second Linux machine

1. Make sure that the machine has an Intel GPU:
   `grep -l 0x8086 /sys/class/drm/renderD*/device/vendor` must print a path.
   If it prints nothing, enable the CPU graphics in the BIOS.
2. Install the packages: `sudo apt-get install intel-media-va-driver vainfo weston`.
3. Make sure that the decoder is there: `vainfo` on the Intel render node
   must list `VAProfileHEVCMain`.
4. Add the test user to the groups `video` and `render`.
5. Install Google Chrome from Google's apt repository.
6. Install `qa-weston.service`. See "Install a change on the box".
7. Do the procedure in "Prove that H.265 decodes".

### Approaches that failed

Do not try these again. Each one was measured on the box.

- Each backend that is not Wayland (headless, Xvfb, X11) decodes frames and
  then loses the GPU process. The error is `Could not find
  SharedImageBackingFactory ... BGRA_8888, gmb_type: platform`. Native GPU
  memory buffers, zero copy, no GPU compositing and the legacy decoder did
  not change that.
- Under Xvfb or headless, Chrome opens the NVIDIA render node and does not
  call libva unless you pin the node.
- The NVIDIA RTX A400 with `nvidia-vaapi-driver` 0.0.8 reached readyState 1
  and then gave `PIPELINE_ERROR_DECODE`.
- `--ozone-platform=drm` is not in Google Chrome's build.

The packages from those attempts are still on the box. They do no harm.

## Update Chrome on the box

The archive index opens with a runners line. It shows each machine's Chrome
from its newest run. When Google's stable version is newer, it shows `stable
X is out: update it`. Do this procedure when you see that text.

Chrome on the box does not update itself. `unattended-upgrades` covers
Ubuntu origins only, and Chrome comes from Google's apt repository. This is
intended: do the update in the daytime and verify it. Windows laptops update
Chrome at each relaunch, so they are usually ahead of the box. Do not let the
box fall more than 1 major version behind the stable version. The stable
version for each platform is at
`https://versionhistory.googleapis.com/v1/chrome/platforms/linux/channels/stable/versions`.

1. Read what is installed and what is offered:

   ```bash
   ssh spartan1 'apt-cache policy google-chrome-stable | sed -n 2,3p'
   ```

2. Update:

   ```bash
   ssh spartan1 'sudo apt-get update -q && sudo apt-get install -y --only-upgrade google-chrome-stable && google-chrome --version'
   ```

3. Do the procedure in "Prove that H.265 decodes".

If step 3 shows `'decodes': False`, the new Chrome needs a flag again. Try the
probe with these flags, which were the set of 8 in the audit: VA-API and
HEVC features on, the GPU blocklist ignored, the driver checks ignored, the
render node pinned, and `LIBVA_DRIVER_NAME=iHD`. Put the flags that work in
`CHROME_ARGS` in `nightly.sh`.

## Stop a stuck nightly

The script stops the nightly of the day before at its start, so a stuck
nightly clears on the next night. Only Justin stops a nightly by hand.

```bash
ssh spartan1 'pkill -u soterix -f "[n]ightly.sh"; pkill -u soterix -f "[p]ytest tests/"; sleep 5; \
  pkill -u soterix -KILL -f "[p]ytest tests/"; pkill -u soterix -KILL -f "playwright/driver/[n]ode"; \
  pkill -u soterix -KILL -f "[m]s-playwright|[c]hrome"; rm -rf /tmp/playwright-artifacts-* /data/qa/ci/nightly.pid; \
  cd /data/qa/ci/Soterix-WebApp-QA && venv/bin/python tools/run_lock.py release --env qa --force; \
  pgrep -u soterix -fc "[p]ytest tests/|[m]s-playwright|[c]hrome"'   # the result must be 0
```

The patterns are the same as in `nightly.sh`. The box runs Google Chrome,
so a check for `ms-playwright` alone does not see the browsers.

Keep the brackets. `pkill -f "pytest tests/"` also matches the SSH shell
that runs the command, and stops it. `[p]ytest` matches `pytest` in the
process list, but it does not match its own command line.

If the clone has drifted, the script's reset corrects it on the next run.
To do it by hand:

```bash
ssh spartan1 'git -C /data/qa/ci/Soterix-WebApp-QA fetch origin && git -C /data/qa/ci/Soterix-WebApp-QA reset --hard origin/main'
```

The evidence below `reports/` is not tracked, so the reset does not delete it.

## Retention and safety

- The served archive at `/data/qa/runs` keeps a run for 30 days. The prune
  also removes what a publish leaves behind (`.pub-tmp-*`, `.pub-old-*`)
  after 2 days.
- The clone keeps the newest 20 runs of each target. The india leg and the
  us leg have the same target, so that is approximately 10 nights. It also
  keeps no more than 100 runs and no more than 10 GB in total. The oldest
  runs go first, and 1 livestream trace can be near 1 GB.
- The permanent record is the git ledger (`history/*.jsonl`). You can make
  the evidence again if you run the tests again.
- Trace zips do not go to the served archive. `nightly.sh` copies with
  `--exclude=*.zip`, and `tools/publish_run.py` stages a copy without them.
- The failure videos do go to the served archive. `run.html` links each
  one. A video shows the screen, and a password field shows dots.
