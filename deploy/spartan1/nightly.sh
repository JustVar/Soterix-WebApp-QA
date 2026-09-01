#!/bin/sh
# Nightly QA run on spartan1. Vendor-free: cron + git + pytest, nothing else.
# See Soterix-WebApp-QA docs/RUN_WORKFLOWS.md for the workflow this serves.
#
#   TARGET=tests/ui/licenses /data/qa/ci/nightly.sh   # override the scope
#
# Unarmed on purpose for now: no QA Touch write, no ledger row. Evidence
# archives locally and is copied to the directory nginx serves, so the run
# is browsable at http://10.2.0.2/qa-runs/ when it finishes.
set -u
REPO=/data/qa/ci/Soterix-WebApp-QA
SERVE=/data/qa/runs
LOG=/data/qa/ci/nightly.log
TARGET="${TARGET:-tests/ui}"
{
  echo "=== $(date -Is) nightly start (target: $TARGET)"
  cd "$REPO" || exit 1
  git pull -q --ff-only
  venv/bin/pip install -q -r requirements.txt
  venv/bin/python -m pytest "$TARGET" --browser-channel "" ; rc=$?
  echo "=== pytest exit: $rc"
  # Publish run folders, additive only, MINUS traces and videos. A trace
  # carries a live session cookie and a fresh-login test's trace carries the
  # account password, so it never reaches the served directory. rsync keeps
  # the exclusion in one place; cp has no --exclude. The 30-day prune on the
  # host is the only thing that deletes.
  for d in reports/runs/20*/; do
    [ -d "$d" ] || continue
    rsync -a --exclude="traces/" --exclude="*.webm" "$d" "$SERVE/$(basename "$d")/"
  done
  echo "=== $(date -Is) nightly done"
} >> "$LOG" 2>&1
