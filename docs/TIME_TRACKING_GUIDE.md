# Time Tracking Guide - Tooling Web + Tooling Code

## Why Track Time?

- Measure project velocity
- Estimate future work
- Report to leadership
- Identify efficiency improvements

---

## How to Track Time

### At Session Start

1. **Note the start time** in your notepad or phone
2. Or run this in PowerShell to log it:

```powershell
Add-Content docs/time_log_temp.txt "START: $(Get-Date -Format 'yyyy-MM-dd HH:mm')"
```

### During Session

Track which tool you're using:
- **Tooling Web** - Planning, discussions, research, decisions
- **Tooling Code** - File edits, running commands, mechanical work

### At Session End

1. **Note the end time**
2. Or run:

```powershell
Add-Content docs/time_log_temp.txt "END: $(Get-Date -Format 'yyyy-MM-dd HH:mm')"
```

3. Calculate total and update PROJECT_HOURS_LOG.md

---

## Time Estimation Guidelines

If you forget to track, estimate based on work completed:

| Task Type | Typical Time |
|-----------|--------------|
| Add markers to 1 test file | 5-10 min |
| Create new Page Object Model | 30-60 min |
| Migrate 1 Selenium test | 15-30 min |
| Debug failing test | 10-30 min |
| Create documentation file | 15-30 min |
| Planning/decision discussion | 10-20 min |
| Git commit and push | 2-5 min |

---

## Session Summary Template

At end of each session, update SESSION_SUMMARY with:

```markdown
## Session Info
- **Date**: YYYY-MM-DD
- **Duration**: X.X hours
- **Tooling Web**: ~XX min (planning, decisions)
- **Tooling Code**: ~XX min (implementation)
```

---

## Quick Time Log Command

Run this at session start:

```powershell
$env:SESSION_START = Get-Date; Write-Host "Session started at $env:SESSION_START"
```

Run this at session end:

```powershell
$duration = (Get-Date) - [datetime]$env:SESSION_START; Write-Host "Session duration: $($duration.TotalMinutes) minutes"
```

---

## File Locations

| File | Purpose |
|------|---------|
| docs/PROJECT_HOURS_LOG.md | Cumulative hours by session |
| docs/SESSION_SUMMARY_YYYY-MM-DD.md | Daily session details |
| docs/time_log_temp.txt | Quick start/end timestamps (optional) |
