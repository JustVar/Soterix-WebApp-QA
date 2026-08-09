# Reviewing team changes to the test scripts

The whole QA team writes and fixes tests in this repo. Their work arrives
through the company remote. This page describes how to find their changes,
study them, and make sure a refactor does not undo a teammate's fix.

## The tool

```
python tools/team_changes.py            # fetch remotes + report
python tools/team_changes.py --ack      # mark everything reviewed
python tools/team_changes.py --no-fetch # offline report
```

The report has three parts:

1. **DIVERGENCE** - commits on `company/main` that `main` does not have.
   Merge these carefully. Past merges lost work in files git merged
   WITHOUT conflict, so check unopposed files for size drops, not just
   the conflicted ones.
2. **TEAM CHANGES** - commits in `main` by someone other than you, newer
   than the review marker. Read each one: what did they fix, and why.
3. **OVERLAP** - files that both sides changed since the marker. For each
   file, open the teammate's diff (`git log -p <sha> -- <file>`) and
   check the same logic in HEAD. Their fix must survive or be replaced
   by something better on purpose, never by accident.

After the review, run `--ack`. That moves a local marker
(`refs/team-review/last`), so the next run shows only new work. The
marker is local to your clone and creates no commits.

## The workflow

- **Before any large refactor** of shared files (page objects, conftest,
  fixtures): run the tool and review the overlap list first.
- **Weekly**: run the tool, read new team commits, `--ack`.
- When a teammate's fix and your change collide, study their approach.
  Adopt it, or improve it and note why in the commit body. Do not
  silently replace it.

## Who counts as "the team"

The tool treats commits from the emails in `SELF_AUTHORS` (top of
`tools/team_changes.py`) as yours and everything else as team work. Add
your own new identity there if your git config changes. Never add a
teammate's email to silence their commits.

## Review log

| Date | Marker | Reviewed | Outcome |
|------|--------|----------|---------|
| 2026-08-08 | initial | All 17 team commits (domain migration + dynamic site/camera discovery, events filter fixes, email reporting, license fixes, sequence + LPR conversions) against the 08/07-08 wait-conversion refactor | All team fixes survive. Their dynamic discovery, MUI tree scan, camera name matching, Unicode email fixes, and report paths are intact under the conversion. Two deliberate changes on top of their work: test_site_name updated after the tenant renamed the site (trace-verified), and EMAIL_REPORTS.md examples corrected to the qa-reports mailbox. |
| 2026-08-08 | ba6fcf5 | Page-object wait-conversion tranche (events, license, media, sequence, insights, lpr, views) checked against every team fix before commit, via two independent audit agents on the full diff | All team patterns intact: listbox-hidden selection signals, the scoped events pin fix, tr.MuiTableRow-root and ExpandMoreIcon selectors, dynamic discovery, the tenant-drift guard, and baseline-delta oracles. Their sleep escalations were replaced with signal waits as planned (their selector fixes untouched), the events select_site nth(1) hardcode now uses their own config-driven pattern, and the sequence_page dead code after a return was removed. Audit findings on the conversion itself (12) were fixed before commit. |
| 2026-08-08 | initial | Technique study of the same 17 commits: are their approaches the ones to standardize on? | Four of their patterns are best practice and are now named conventions (CONVENTIONS.md > Locators and scoping): MUI listbox-hidden as the selection signal, row-scoped locators before .first, MUI built-in data-testid icons, and baseline-delta count oracles. Three of the four match patterns the wait conversion reached independently, which validates both. Their sleep-escalation stabilizations (license navigation, events trailing sleeps) work but predate the Waits convention - the next conversion tranche replaces the sleeps while keeping their selector fixes. One inconsistency to unify: events select_site hardcodes option position nth(1) with the old site name in a comment instead of using their own config-driven pattern from the domain-migration commit. |
