# spartan1 deployment

The CI host serving the run archive and running the nightly QA suite. These
files are the live configuration on spartan1 (10.2.0.2), version-controlled
here so they are auditable and recoverable rather than living only on the
box. The adversarial audit flagged that the nightly script was unauditable
because it existed nowhere in git.

## What runs on spartan1

| File here | Lives on the box at | What it does |
|---|---|---|
| `nightly.sh` | `/data/qa/ci/nightly.sh` | The nightly QA run: reset the clone to `origin/main`, install, pytest once per box (`india`, then `us`), publish evidence minus traces/videos. Cron at 04:00 America/Chicago (`/etc/cron.d/qa-nightly-run`). One nightly at a time, 900 s per test, 4 h per box. |
| `qa-runs-prune` | `/usr/local/bin/qa-runs-prune` | Deletes run folders older than 30 days. Cron at 03:00. |
| `nginx-qa-runs.conf` | inside `/etc/nginx/sites-enabled/default` | The `/qa-runs/` location: serves `/data/qa/runs` read-only, basic auth, dotfiles denied. |

## Access

- SSH alias `spartan1` = `soterix@10.2.0.2`.
- The archive is at `http://10.2.0.2/qa-runs/` behind HTTP basic auth (user
  `qa`; password in the team password store).
- Two read-only per-repo deploy keys on the box pull the repos over SSH.

## What the box needs

- The clone at `/data/qa/ci/Soterix-WebApp-QA` with a venv (`venv/`, Python
  3.12 on the box) and Playwright's own Chromium
  (`venv/bin/python -m playwright install chromium`). There is no Google
  Chrome on the box; `nightly.sh` passes an empty `--browser-channel` so
  the headless Chromium runs the tests.
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
ssh spartan1 'cd /data/qa/ci/Soterix-WebApp-QA && git fetch -q origin && git reset -q --hard origin/main && \
  sudo cp deploy/spartan1/nightly.sh /data/qa/ci/nightly.sh && sudo chmod 755 /data/qa/ci/nightly.sh && \
  sh -n /data/qa/ci/nightly.sh && echo installed'

# nginx: after editing /etc/nginx/sites-enabled/default
ssh spartan1 'sudo nginx -t && sudo systemctl reload nginx'
```

Try it before the cron does, on a small target and a short cap, and read
the tail of the log:

```bash
ssh spartan1 'TARGET=tests/ui/maps TEST_TIMEOUT=300 /data/qa/ci/nightly.sh; tail -n 20 /data/qa/ci/nightly.log'
```

## Recovering a stuck nightly

The script kills its own predecessor, so a stuck nightly clears itself the
next night. To clear one now, or one started by an older script:

```bash
ssh spartan1 'pkill -u soterix -f /data/qa/ci/nightly.sh; \
  pkill -u soterix -f "pytest tests/ui"; sleep 5; \
  pkill -u soterix -KILL -f "playwright/driver/node"; pkill -u soterix -KILL -f ms-playwright; \
  rm -rf /tmp/playwright-artifacts-* /data/qa/ci/nightly.pid; \
  pgrep -u soterix -fc "nightly.sh|pytest tests/ui|ms-playwright"'   # expect 0
```

If the clone has drifted (the log says `Not possible to fast-forward`, or
`code:` names an old commit), the script's reset fixes it on its next run;
by hand it is `git -C /data/qa/ci/Soterix-WebApp-QA fetch origin && git -C
/data/qa/ci/Soterix-WebApp-QA reset --hard origin/main`. Evidence under
`reports/` is untracked and survives the reset.

## Retention and safety

- Evidence is pruned after 30 days on the box. The permanent record is the
  git ledger (`history/*.jsonl`), not the evidence.
- Traces and videos never reach the box: they carry live session cookies
  and, on a fresh-login test, the account password. `nightly.sh` rsyncs with
  `--exclude=traces/ --exclude=*.webm`, and `tools/publish_run.py` stages a
  filtered copy. Keep traces local for `playwright show-trace`.
