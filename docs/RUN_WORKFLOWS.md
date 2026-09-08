# Run Workflows

What happens after a test run, who looks where, and what each system of
record holds. This is the operating document for automated runs. How to
write tests is `docs/CONVENTIONS.md`; how to read a failure trace is
`docs/FAILURE_TRIAGE.md`.

## One Question, One Place

| Question | Where | Held how long |
|---|---|---|
| Did it pass? | The QA Touch run | Forever, QA Touch |
| Why did it fail? | The run's `run.html` in the archive | 30 days (evidence policy below) |
| When did this start failing? Is the suite slower? | `history/*.jsonl` in git | Forever, committed |
| Is this a defect? | Jira, through the approval queue | Forever, Jira |

Nothing is duplicated. QA Touch never holds evidence, the archive never
holds statuses of record, and Jira only holds defects a person approved.

## The Pane of Glass

Every run archives itself to `reports/runs/<timestamp>__<target>/` before
the next run can overwrite anything. Three pages make the archive readable:

- `reports/runs/index.html` lists every archived run, newest first.
- Each run's `run.html` shows failures first, each with its error, call
  log, screenshots, video, and a ready-made trace command.
- `reports/runs/health.html` is the cross-run view: pass rate per module,
  tests to watch, each module's last run. Regenerate it with
  `python run.py health`.

The hosted archive at http://10.2.0.2/qa-runs/ is behind HTTP basic auth
(user `qa`; the password is in the team password store, not in git). It is
one shared read-only viewing credential, so a dropped WireGuard unit or a
new reviewer needs no per-person setup. The publish command below uses SSH,
not this credential, so publishing is unaffected.

The archive is local to the machine that ran the tests, and gitignored on
purpose: a week of evidence measured 4.4 GB before pruning, and all of it
is regenerable by re-running. The plugin already prunes locally, keeping
the newest 20 runs per target and 100 in total (`RUN_ARCHIVE=off` is the
kill switch). The plan of record for viewing runs from any machine is
below.

## Scenario 1: a Scheduled Run Finishes

Scheduled runs are armed, so QA Touch is already updated when the run
ends. Nobody transcribes results.

1. **Green:** done. The ledger row is the record. Nobody opens anything.
2. **Red:** open the run's `run.html`. Failures are sorted first with the
   evidence inline. Triage each failure one of two ways:
   - **App bug.** The failure is scored into `tools/review_queue.json`.
     A person approves it in the review CLI before anything reaches Jira.
     Automation never files an unreviewed bug.
   - **Test or data problem.** Add a row to `docs/TEST_REPAIRS.md` and
     work the register before writing new tests.

The triage rule of thumb: `docs/FAILURE_TRIAGE.md`. Known tenant-data
drift symptoms are listed there before you blame the app.

## Scenario 2: a Manual Run Finishes

An unarmed run uploads nothing and ledgers nothing, so a debug loop leaves
no trace outside your machine. Run it, open `run.html` or the trace,
iterate. There is nothing to clean up.

When a manual run IS an official check of a feature area, arm it against
a dedicated QA Touch run and it becomes scenario 1:

```powershell
venv\Scripts\python.exe -m pytest tests/ui/licenses --qatouch-upload --qatouch-run <KEY>
```

Create the run in QA Touch first (or ask for one), containing the module
whose cases the tests map to. The upload summary's `Run coverage` line
then says how much of the run the selected tests set.

## Where the Team Views Runs: the Plan of Record

Decided 09/01/2026. Evidence hosting is a directory served by nginx, not
an application. Previous research already found an app for this redundant:
the pipeline writes self-contained HTML, so the only missing piece is a
host.

**spartan1 (10.2.0.2) serves the archive.**

```
spartan1
+- nginx  ->  http://spartan1/qa-runs/     read-only archive browsing
+- /data/qa/runs/                          the archive directory
+- later: self-hosted GitHub runner        writes archives directly there
```

The same box is the candidate for self-hosted CI runs. That pairing is
the point: a scheduled run on that runner writes its archive onto the box
that serves it. No upload step, no sync, nothing to break.
`qa-nightly.yml` already carries the switch instructions in its header
comment (`runs-on: [self-hosted, qa-lab]`).

**Retention on spartan1: 30 days for evidence.** A cron prunes run
folders older than that. `summary.json` files may be kept longer (they
are kilobytes, and `health.html` reads them). The permanent history is
the git ledger, not the evidence.

**Manual runs stay local by default.** Publishing a local run is opt-in,
one command, for runs worth sharing. Same philosophy as arming: the
deliberate act is the filter.

```powershell
venv\Scripts\python.exe tools\publish_run.py            # newest run
venv\Scripts\python.exe tools\publish_run.py --dry-run  # show, send nothing
```

The command copies the run folder plus the archive's front-door pages and
prints the resulting URL. Host and paths are overridable with
`QA_RUNS_HOST` / `QA_RUNS_DIR` / `QA_RUNS_URL`.

**Scheduled runs live on spartan1 as plain cron** (since 09/01/2026):
`/data/qa/ci/nightly.sh` (the copy of record is `deploy/spartan1/nightly.sh`),
daily 04:00 America/Chicago. It resets the clone to `origin/main`, installs
pins, runs `tests/ui` headless once per box (`india`, then `us`; a box
whose `QA_<BOX>_USER` is not in the box's `.env` is skipped and said so),
and copies each archive into the served directory, so the runs are
browsable at the URL above when they finish. Each run's `run.html` and its
index row name the box. Unarmed for now: no QA Touch write until the
nightly run-key strategy is decided. Logs: `/data/qa/ci/nightly.log`.

The first week (09/02-09/08/2026) taught the script its three guards.
Every nightly hung on one drag that Playwright never timed out, the next
night's cron started another beside it (seven runs and seven browsers were
found alive at once), and `git pull --ff-only` had refused the rewritten
history, so the box ran week-old code and archived nothing all week. Now:
one nightly at a time (its own process group; the previous group is killed
first), a ceiling on every test (`pytest-timeout`, 900 s, signal method)
and on each box's run (`timeout`, 4 h), and `git reset --hard origin/main`
instead of a pull.

Vendor-free on purpose. A GitHub self-hosted runner was compared and
deferred, not rejected: self-hosted runner minutes are free today, but
everything a runner would give a SCHEDULED run (execution, archive,
publish), cron already does with zero external dependency. What a runner
adds is GitHub-side triggers and logs: on-demand runs from the Actions
tab, PR-triggered browser runs, secrets management. Adopt it when someone
needs those, by registering a runner on this same box and flipping
`qa-nightly.yml` to `runs-on: [self-hosted, qa-lab]` - the pipeline
underneath does not change, which is what makes the migration cheap in
either direction. GitHub-HOSTED runs (`qa-nightly.yml` today) upload
`reports/` as a 7-day artifact: a zip download, kept only as the fallback.

## Status of Each Piece

| Piece | State |
|---|---|
| Run archive, `run.html`, `index.html`, `health.html` | working today |
| Armed upload + read-back verification | working, proven live from both repos |
| Git ledger (`history/`) | working, first rows committed |
| Jira approval queue | working, double-gated |
| GitHub artifact on CI runs | working, 7-day retention |
| nginx on spartan1 | working: http://10.2.0.2/qa-runs/ (since 09/01/2026), HTTP basic auth (user `qa`), dotfiles denied |
| 30-day prune cron on spartan1 | working, mutation-tested in both directions |
| Nightly cron on spartan1 (`/data/qa/ci/nightly.sh`) | proven end to end 09/01 on one file; hung every night 09/02-09/08 (no timeout, stale clone, runs piling up); rebuilt 09/08 with the three guards, both boxes, awaiting its first scheduled run |
| Self-hosted GitHub runner | deferred by comparison; adopt when PR-triggered or on-demand GitHub runs are wanted |
| Publish-a-local-run command | working: `tools/publish_run.py`, proven with a real publish |
| Scheduled nightly (GitHub-hosted path) | stays commented out in `qa-nightly.yml`; the box cron is the live schedule |
| Email report | broken until the Azure secret rotates |
