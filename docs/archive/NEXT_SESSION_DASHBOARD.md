# Next Session: Dashboard Enhancements & Roadmap Features

> **Paste this into a new Tooling Code instance to continue dashboard work.**
> **Repository:** `C:\Users\JustinVarughese\.tooling-worktrees\playwright-soterix-qa\amazing-curran`

---

## Context

We have built an interactive HTML dashboard (`docs/dashboard.html`) that is auto-generated from `docs/FUTURE_ROADMAP.md` using `tools/generate_dashboard.py`. The dashboard visualizes QA automation progress across 20 workstreams for leadership at Soterix Systems (AI VSAAS platform).

### Key Files
- **`docs/FUTURE_ROADMAP.md`** - Single source of truth. 20 sections, ~163 items, status icons (✅🔄🔜💡🚫)
- **`tools/generate_dashboard.py`** - Python script (~1,320 lines) that parses the roadmap markdown and generates a single-file HTML dashboard with Soterix brand styling (dark theme, `#2F2E37` background, primary blue `#127CA3`)
- **`docs/dashboard.html`** - Generated output (~164KB). Self-contained HTML with inline CSS/JS, base64-embedded logo, clickable summary tiles with drilldown modals, expandable section cards, priority roadmap, and timeline
- **`tools/soterix_logo.svg`** - SVG wordmark fallback
- **Logo PNG** at `C:\Users\JustinVarughese\OneDrive - Soterix Systems\Documents\Sales & Marketing Assets\Sales & Marketing Assets\Logos\Logo-Soterix-Horizontal.png`

### Current Dashboard Features
- 6 summary tiles (Overall %, Total Items, Complete, In Progress, Planned/Ideas, Blocked) - each clickable with drilldown modals showing items grouped by section
- Overall progress bar with legend
- AI-Enabled Outcomes section (4 highlight cards)
- 20 collapsible section cards with per-section progress bars and status badges
- Priority Roadmap (4 tiers: Immediate, Short-Term, Medium-Term, Long-Term)
- Timeline section
- Auto-updates "Last Updated" date in the markdown when dashboard is regenerated
- Dark theme matching Soterix brand guidelines
- Google Fonts (Yantramanav for body text)

### Current Stats
- 20 sections, 163 total items, 30 complete, ~18% overall progress

---

## Tasks for This Session

### 1. Time Tracking - How Long Items Take

**Goal:** Add completion dates to finished items and show velocity/duration on the dashboard.

**Scope to explore:**
- What format to use for completion dates on `- [x]` items (e.g., `- [x] Item name (2026-01-28)` or `<!-- completed: 2026-01-28 -->`)
- Whether to also track start dates (for duration calculation)
- Dashboard visualization: "Recently Completed" timeline, average items/week velocity, completion trend chart
- How to retroactively add dates to the 30 existing completed items (approximate dates from git history)
- Consider: should table row items (✅ status) also get dates?

**Questions to resolve:**
- Do we want a simple date stamp or full duration tracking?
- Should this be a new dashboard section or integrated into existing sections?

### 2. AI Cost Savings Estimate

**Goal:** Quantify the value AI tools bring - estimated hours saved per completed item, projected savings.

**Scope to explore:**
- Metadata format for hours saved (e.g., `<!-- hours_saved: 40 -->` comments, or a dedicated column)
- Calculation approach: hours saved × hourly QA engineer rate
- Whether to show as a separate tab/page or a section within the main dashboard
- Categories: Documentation, Test Migration, Integration Setup, Automation Scripts, Research
- How to estimate hours for existing completed items retroactively
- Consider: total hours invested vs. total hours saved (ROI calculation)

**Questions to resolve:**
- What hourly rate to use? (Market rate for Platform QA Lead? A standard estimate?)
- Should we show individual item savings or just aggregate totals?
- Separate tab/page vs. new section on main dashboard?

### 3. Change Tracking - Moved, Changed, Deleted Items

**Goal:** Track what changed in the roadmap over time so leadership sees the evolution.

**Scope to explore three approaches:**

**Option A: Changelog Section (Manual)**
- Add a `## Changelog` section at the bottom of the roadmap
- Format: `- 2026-02-03: Added edge box security hardening to Section 9`
- Simple, always visible, easy to maintain
- Pro: No code changes. Con: Manual maintenance

**Option B: Auto-generated from Git**
- Parse `git log --follow -p docs/FUTURE_ROADMAP.md` to extract changes
- Show "Recent Changes" section on the dashboard with actual diffs
- Pro: Automatic, accurate. Con: Complex parsing, may be noisy

**Option C: Archive Section**
- Instead of deleting items, move them to a `## Archived / Removed Items` section
- Track reason for removal: "Deprioritized", "Merged into X", "No longer needed"
- Pro: Nothing is lost. Con: File grows over time

**Questions to resolve:**
- Which approach (or combination) works best?
- How far back should change history go?
- Should changes appear on the dashboard or just in the markdown?

---

## Other Pending Dashboard Items

### 4. PDF Export Button
- Add a "Export to PDF" button to the dashboard
- Use `window.print()` with print-optimized CSS (expand all sections, hide interactive elements)
- For sharing snapshots via Box or email to management

### 5. Hosting Strategy
- **SharePoint** for tech team (upload HTML directly or embed)
- **Box** for management (shared link, note: JS may be stripped in Box preview)
- **GitHub Pages** option (push docs/ folder, auto-updates on push)
- Decision needed on which to implement

### 6. "3 Tooling Interfaces Used" -> Update
- The AI Enablement section says "3 Tooling Interfaces Used" - should this be updated to reflect all AI tools used (Tooling Code Terminal, Tooling Code VS Code, Tooling Chat, ChatGPT, etc.)?

---

## How to Start

1. Read `docs/FUTURE_ROADMAP.md` to understand the current structure
2. Read `tools/generate_dashboard.py` to understand the generator architecture
3. Start with feature scoping - explore each of the 3 main features, discuss tradeoffs
4. Get user approval on approach before implementing
5. After any changes: `python tools/generate_dashboard.py` to regenerate

---

## Brand Guidelines Quick Reference
- **Primary Blue:** `#127CA3`
- **Oslo Gray:** `#BCBEC0`
- **Dark Background:** `#2F2E37`
- **Card Surface:** `#3a3944`
- **Accent Blue:** `#46A1B1`
- **Accent Grey:** `#AD9B68`
- **Fonts:** Good Times (headers), Yantramanav (body - Google Fonts)
