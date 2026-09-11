#!/bin/sh
# Nightly QA run on spartan1. Vendor-free: cron + git + pytest, nothing else.
# See Soterix-WebApp-QA docs/RUN_WORKFLOWS.md for the workflow this serves
# and deploy/spartan1/README.md for how this file reaches the box.
#
#   TARGET=tests/ui/licenses /data/qa/ci/nightly.sh   # narrow the scope
#   BOXES=india /data/qa/ci/nightly.sh                # one box only
#   TEST_TIMEOUT=120 /data/qa/ci/nightly.sh           # a trial with a short cap
#   C2C=0 /data/qa/ci/nightly.sh                      # web app only, no camera run
#   BOXES= /data/qa/ci/nightly.sh                     # cameras only
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
BOXES="${BOXES-india us}"             # `-` not `:-`: an explicit BOXES= means no box (cameras only);
                                      # 09/11 a trial meant that way ran both boxes instead
TEST_TIMEOUT="${TEST_TIMEOUT:-600}"   # seconds per test, setup and teardown included
RUN_TIMEOUT="${RUN_TIMEOUT:-4h}"      # per box; a full run measured about an hour at 4 workers
WORKERS="${WORKERS:-4}"
MAXFAIL="${MAXFAIL:-200}"             # failures+errors that end a box's run early; ~25% of the suite.
                                      # 120 was too close: c2c ran early and 09/11 had 116 by mid-run
C2C="${C2C:-1}"                      # 0 skips the Camera 2 Cloud run

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
  # The pid file is not the only witness: on 09/11/2026 a stalled run had
  # no pid file (the run before it had removed the file at its own end),
  # so nothing was killed, the stalled session kept the single-run lock,
  # and every leg of the new nightly exited in 0 s. Whatever pytest is
  # still running from the clone is an earlier nightly by definition:
  # kill it, its drivers and browsers, and release the lock it held.
  if pgrep -u "$(id -un)" -f "[p]ytest tests/" > /dev/null; then
    echo "pytest from an earlier run still alive with no pid file: killing it"
    pkill -u "$(id -un)" -TERM -f "[p]ytest tests/"
    sleep 5
    pkill -u "$(id -un)" -KILL -f "[p]ytest tests/"
    pkill -u "$(id -un)" -KILL -f "playwright/driver/[n]ode"
    pkill -u "$(id -un)" -KILL -f "[m]s-playwright|[c]hrome"
  fi
  echo $$ > "$PIDFILE"
  # Live traces of a killed run. A finished run has moved its own.
  rm -rf /tmp/playwright-artifacts-*

  cd "$REPO" || exit 1
  # Nothing of an earlier run is alive now, so its single-run lock (the
  # in-repo guard that refused this nightly's legs on 09/11) is stale.
  venv/bin/python tools/run_lock.py release --env qa --force > /dev/null 2>&1 || true
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
    # Guard 2. `timeout` exit 124 means the run cap ended it. Google Chrome
    # is on the box since 09/11/2026 (playwright install chrome), so
    # pytest.ini's channel applies; note Chrome on Linux has no H.265
    # decoder, so the livestream tests skip here by measurement. --maxfail ends a
    # run whose failures are systemic (every test erroring at setup) while
    # pytest can still write its summary and archive: the first three
    # scheduled runs (09/09-09/11/2026) all hit the run cap instead, and
    # the cap's kill threw the evidence away. -rfEs lists every failure,
    # error and skip in this log at the end.
    # QA_RUNS_LIVE_DIR: the run's live record (live.json) is also written
    # into the served directory, so the archive index and health page at
    # http://10.2.0.2/qa-runs/ show the run in progress and its estimate.
    BOX="$box" QA_RUNS_LIVE_DIR="$SERVE" timeout -k 60 "$RUN_TIMEOUT" venv/bin/python -m pytest "$TARGET" \
      -n "$WORKERS" -rfEs --maxfail="$MAXFAIL" \
      --timeout="$TEST_TIMEOUT" --timeout-method=signal
    rc=$?
    echo "=== $box pytest exit: $rc after $(( $(date +%s) - started ))s (124 = run cap)"
    if [ "$rc" = 124 ]; then
      # The archive is written at session end, which a kill never reaches.
      # Keep what exists: labelled screenshots and the live log. Traces and
      # videos stay off the served directory (session cookies, passwords).
      part="$SERVE/$(date +%Y-%m-%d_%H-%M-%S)__tests-ui-$box-PARTIAL-run-cap"
      mkdir -p "$part" && rsync -a reports/screenshots logs/run.log "$part/" 2>/dev/null
      echo "=== $box run cap hit: partial evidence kept at $part"
    fi
  done

  # Camera 2 Cloud: tests/c2c is a product root of its own (config/products.py),
  # so the web-app target above never collects it. It runs once, not per box:
  # the tests talk to the lab cameras' own web UIs (tests/data/c2c_cameras.yaml),
  # never to a tenant. Serial on purpose: they reboot and reconfigure real
  # devices (docs/PARALLEL_EXECUTION.md). C2C_REQUIRE_HARDWARE=1 makes an
  # unreachable camera a failure instead of a skip, so a camera that went dark
  # shows in the archive. The archive's path rule reports the results to the
  # Camera 2 Cloud project. Without the shared lab password in .env the suite
  # fails once per camera, loudly, so it is skipped here and said so.
  if [ "$C2C" = 1 ] && grep -q "^C2C_CAMERA_PASS=." .env 2>/dev/null; then
    started=$(date +%s)
    C2C_REQUIRE_HARDWARE=1 QA_RUNS_LIVE_DIR="$SERVE" timeout -k 60 "$RUN_TIMEOUT" venv/bin/python -m pytest tests/c2c \
      -rfEs --maxfail="$MAXFAIL" \
      --timeout="$TEST_TIMEOUT" --timeout-method=signal
    rc=$?
    echo "=== c2c pytest exit: $rc after $(( $(date +%s) - started ))s (124 = run cap)"
    if [ "$rc" = 124 ]; then
      part="$SERVE/$(date +%Y-%m-%d_%H-%M-%S)__tests-c2c-PARTIAL-run-cap"
      mkdir -p "$part" && rsync -a reports/screenshots logs/run.log "$part/" 2>/dev/null
      echo "=== c2c run cap hit: partial evidence kept at $part"
    fi
  elif [ "$C2C" = 1 ]; then
    echo "=== c2c skipped: C2C_CAMERA_PASS is not set in $REPO/.env"
  fi

  # Publish run folders, additive only, MINUS the trace zips. A trace
  # carries a live session cookie and a fresh-login test's trace carries the
  # account password in a request body, so it never reaches the served
  # directory. The failure VIDEOS beside them do get published: run.html
  # links each one, and they show the screen (a password field shows dots).
  # Until 09/11/2026 the whole traces/ folder was skipped and every video
  # link on the served pages was dead. The 30-day prune on the host is the
  # only thing that deletes.
  for d in reports/runs/20*/; do
    [ -d "$d" ] || continue
    rsync -a --exclude="*.zip" "$d" "$SERVE/$(basename "$d")/"
  done
  # The served index and health page must list what the SERVED directory
  # holds. The archive plugin rebuilds only the clone's own index, and the
  # copy served since 09/01 listed none of the runs copied after it
  # (found 09/11/2026). health_summary rebuilds both for any runs dir.
  venv/bin/python tools/health_summary.py --runs-dir "$SERVE" > /dev/null \
    && echo "=== served index and health page rebuilt from $SERVE" \
    || echo "=== served index rebuild FAILED (health_summary exit $?)"
  rm -f "$PIDFILE"
  echo "=== $(date -Is) nightly done"
} >> "$LOG" 2>&1
