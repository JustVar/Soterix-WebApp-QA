#!/bin/sh
# Nightly QA run on spartan1. Vendor-free: cron + git + pytest, nothing else.
# See Soterix-WebApp-QA docs/RUN_WORKFLOWS.md for the workflow this serves
# and deploy/spartan1/README.md for how this file reaches the box.
#
#   TARGET=tests/ui/licenses /data/qa/ci/nightly.sh   # narrow the scope
#   BOXES=india /data/qa/ci/nightly.sh                # one box only
#   TEST_TIMEOUT=120 /data/qa/ci/nightly.sh           # a trial with a short cap
#
# Unarmed on purpose for now: no QA Touch write, no ledger row. Evidence
# archives locally and is copied to the directory nginx serves, so each run
# is browsable at http://10.2.0.2/qa-runs/ when it finishes.
#
# Three guards, each earned by the week of 09/02-09/08/2026 when every
# nightly hung and nothing was archived:
# 1. One nightly at a time. A run that hangs (a drag that never returned)
#    stayed alive while the next night's cron started another beside it;
#    seven runs and seven browsers were found sharing the box. The script
#    runs as its own process group and kills the previous group first.
# 2. A ceiling on every test and on the whole run. Playwright cannot time
#    out a driver call that never answers, so pytest-timeout ends the test
#    (signal method, Linux only) and `timeout` ends the run.
# 3. The clone follows origin/main exactly. `git pull --ff-only` refused a
#    rewritten history, and the box ran week-old code without saying so.
#    The clone is disposable: evidence lives untracked under reports/, so a
#    hard reset never touches it.
set -u
REPO=/data/qa/ci/Soterix-WebApp-QA
SERVE=/data/qa/runs
LOG=/data/qa/ci/nightly.log
PIDFILE=/data/qa/ci/nightly.pid
TARGET="${TARGET:-tests/ui}"
BOXES="${BOXES:-india us}"
TEST_TIMEOUT="${TEST_TIMEOUT:-900}"   # seconds per test, setup and teardown included
RUN_TIMEOUT="${RUN_TIMEOUT:-4h}"      # per box; a full run measured about an hour at 4 workers
WORKERS="${WORKERS:-4}"

# Guard 1: become a process group of our own, so one kill reaches pytest,
# the Playwright driver and every browser it started. `-w` keeps a manual
# run in the foreground.
if [ -z "${NIGHTLY_GROUP:-}" ]; then
  NIGHTLY_GROUP=1 exec setsid -w "$0" "$@"
fi

{
  echo "=== $(date -Is) nightly start (target: $TARGET, boxes: $BOXES)"
  if [ -f "$PIDFILE" ]; then
    old=$(cat "$PIDFILE")
    if [ -n "$old" ] && kill -0 -- "-$old" 2>/dev/null; then
      echo "previous nightly (group $old) still alive after a day: killing it"
      kill -TERM -- "-$old" 2>/dev/null
      sleep 10
      kill -KILL -- "-$old" 2>/dev/null
    fi
  fi
  echo $$ > "$PIDFILE"
  # Live traces of a killed run. A finished run has moved its own.
  rm -rf /tmp/playwright-artifacts-*

  cd "$REPO" || exit 1
  # Guard 3.
  git fetch -q origin && git reset -q --hard origin/main
  echo "code: $(git log -1 --format='%h %s')"
  venv/bin/pip install -q -r requirements.txt

  for box in $BOXES; do
    # The suite reads QA_<BOX>_USER / QA_<BOX>_PASSWORD from .env for the
    # box it is asked for (config/env/qa.py). Without them a run would
    # stop at the first login, so it is skipped here and said so.
    key="QA_$(echo "$box" | tr '[:lower:]' '[:upper:]')_USER"
    if ! grep -q "^$key=." .env 2>/dev/null; then
      echo "=== $box skipped: $key is not set in $REPO/.env"
      continue
    fi
    started=$(date +%s)
    # Guard 2. `timeout` exit 124 means the run cap ended it. The empty
    # browser channel overrides pytest.ini's Chrome: the box has none, so
    # Playwright's own headless Chromium runs the tests.
    BOX="$box" timeout -k 60 "$RUN_TIMEOUT" venv/bin/python -m pytest "$TARGET" \
      -n "$WORKERS" --browser-channel "" \
      --timeout="$TEST_TIMEOUT" --timeout-method=signal
    rc=$?
    echo "=== $box pytest exit: $rc after $(( $(date +%s) - started ))s (124 = run cap)"
  done

  # Publish run folders, additive only, MINUS traces and videos. A trace
  # carries a live session cookie and a fresh-login test's trace carries the
  # account password, so it never reaches the served directory. rsync keeps
  # the exclusion in one place; cp has no --exclude. The 30-day prune on the
  # host is the only thing that deletes.
  for d in reports/runs/20*/; do
    [ -d "$d" ] || continue
    rsync -a --exclude="traces/" --exclude="*.webm" "$d" "$SERVE/$(basename "$d")/"
  done
  rm -f "$PIDFILE"
  echo "=== $(date -Is) nightly done"
} >> "$LOG" 2>&1
