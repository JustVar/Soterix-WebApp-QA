#!/usr/bin/env python3
"""
Generate an interactive HTML dashboard from FUTURE_ROADMAP.md.

Parses the unified roadmap markdown file and produces a single-file
HTML dashboard styled with Soterix brand guidelines.

Usage:
    python tools/generate_dashboard.py
    # Opens docs/dashboard.html in default browser
"""

import re
import os
import json
import base64
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
SCRIPT_DIR = Path(__file__).resolve().parent
REPO_ROOT = SCRIPT_DIR.parent
ROADMAP_PATH = REPO_ROOT / "docs" / "FUTURE_ROADMAP.md"
OUTPUT_PATH = REPO_ROOT / "docs" / "dashboard.html"
LOGO_PATH = SCRIPT_DIR / "soterix_logo.svg"
LOGO_PNG_PATH = Path(
    r"C:\Users\JustinVarughese\OneDrive - Soterix Systems\Documents"
    r"\Sales & Marketing Assets\Sales & Marketing Assets\Logos"
    r"\Logo-Soterix-Horizontal.png"
)
GOOD_TIMES_FONT_PATH = Path(
    r"C:\Users\JustinVarughese\OneDrive - Soterix Systems\Documents"
    r"\Soterix Fonts\good times rg.otf"
)

# ---------------------------------------------------------------------------
# Deploy target - soterix-internal-dashboards repo (NUC pulls from this)
# ---------------------------------------------------------------------------
DEPLOY_REPO = Path(
    r"C:\Users\JustinVarughese\Desktop\soterix-internal-dashboards"
)
DEPLOY_DASHBOARD = DEPLOY_REPO / "qa-roadmap" / "index.html"
DEPLOY_ROADMAP = DEPLOY_REPO / "qa-roadmap" / "FUTURE_ROADMAP.md"

# ---------------------------------------------------------------------------
# Status definitions
# ---------------------------------------------------------------------------
STATUS_MAP = {
    "✅": {"label": "Complete", "color": "#22c55e", "css_class": "complete"},
    "🔄": {"label": "In Progress", "color": "#127CA3", "css_class": "in-progress"},
    "🔜": {"label": "Planned", "color": "#46A1B1", "css_class": "planned"},
    "💡": {"label": "Idea", "color": "#AD9B68", "css_class": "idea"},
    "⏸️": {"label": "Blocked", "color": "#ef4444", "css_class": "blocked"},
    "🚫": {"label": "Blocked", "color": "#ef4444", "css_class": "blocked"},
}

# Also match "[x]" as complete
COMPLETED_CHECKBOX = re.compile(r"^\s*-\s*\[x\]", re.IGNORECASE)

# Date pattern for completion dates (MM/DD/YYYY)
DATE_PATTERN = re.compile(r"\((\d{2}/\d{2}/\d{4})\)\s*$")


def read_roadmap(path: Path) -> str:
    """Read the roadmap markdown file."""
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def read_logo(path: Path) -> str:
    """Read the SVG logo for inline embedding."""
    with open(path, "r", encoding="utf-8") as f:
        return f.read()


def read_logo_png(path: Path) -> str:
    """Read a PNG logo and return a base64 data URI img tag."""
    with open(path, "rb") as f:
        data = base64.b64encode(f.read()).decode("utf-8")
    return f'<img src="data:image/png;base64,{data}" alt="Soterix Systems">'


def read_font_base64(path: Path) -> str:
    """Read a font file and return base64 encoded data."""
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode("utf-8")


def extract_metadata(text: str) -> dict:
    """Extract header metadata (last updated, owner, migration progress)."""
    meta = {}
    m = re.search(r"\*\*Last Updated:\*\*\s*(.+)", text)
    meta["last_updated"] = m.group(1).strip() if m else datetime.now().strftime("%Y-%m-%d")
    m = re.search(r"\*\*Owner:\*\*\s*(.+)", text)
    meta["owner"] = m.group(1).strip() if m else ""
    m = re.search(r"\*\*Migration Progress:\*\*\s*(.+)", text)
    meta["migration_progress"] = m.group(1).strip() if m else ""
    return meta


def parse_sections(text: str) -> list[dict]:
    """
    Parse the roadmap into numbered sections.

    Each section has:
      - number, title
      - items: list of {text, status_icon, status_label, status_color}
      - counts by status
      - completion percentage
    """
    # Split on ## N. headings (e.g. "## 1. Playwright Test Migration")
    section_pattern = re.compile(r"^## (\d+)\.\s+(.+)$", re.MULTILINE)
    matches = list(section_pattern.finditer(text))

    sections = []
    for i, match in enumerate(matches):
        num = int(match.group(1))
        title = match.group(2).strip()
        start = match.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(text)
        body = text[start:end]

        items = extract_items(body)
        counts = count_statuses(items)
        total = len(items)
        completed = counts.get("✅", 0)
        pct = round((completed / total) * 100) if total > 0 else 0

        sections.append({
            "number": num,
            "title": title,
            "items": items,
            "counts": counts,
            "total": total,
            "completed": completed,
            "pct": pct,
        })

    return sections


def extract_items(body: str) -> list[dict]:
    """
    Extract individual items from a section body.

    Looks for:
    - Table rows with status icons (| Item | ✅ | ... |)
    - Checkbox items (- [x] completed thing)
    - Table rows with status text matching our icons

    Items are sorted by status: ✅ Complete -> 🔄 In Progress -> 🔜 Planned -> 💡 Ideas -> 🚫 Blocked
    """
    items = []
    # Status sort order: Complete first, Blocked last
    STATUS_ORDER = {"✅": 0, "🔄": 1, "🔜": 2, "💡": 3, "⏸️": 4, "🚫": 5}

    # --- Table rows ---
    # Match rows like: | Some item | ✅ | details |
    # or:             | Some item | 🔜 (High) | details |
    # or:             | Some item | In Progress | details |
    table_row = re.compile(r"^\|(.+)\|$", re.MULTILINE)
    for row_match in table_row.finditer(body):
        row = row_match.group(1)
        cells = [c.strip() for c in row.split("|")]
        if not cells:
            continue

        # Skip header/separator rows
        if all(c.startswith("-") or c == "" for c in cells):
            continue
        if any(c in ("Item", "Module", "Status", "Details", "Cadence",
                      "Icon", "Meaning", "Question", "Action Needed",
                      "Purpose", "Current", "Planned", "Timeframe", "Focus",
                      "Platform", "Current Testing Method")
               for c in cells[:3]):
            continue

        # Find status icon in cells
        status_icon = None
        item_text = cells[0] if cells else ""

        for cell in cells:
            for icon in STATUS_MAP:
                if icon in cell:
                    status_icon = icon
                    break
            if status_icon:
                break

        # Also check for text-based statuses
        if not status_icon:
            row_lower = row.lower()
            if "partially covered" in row_lower:
                status_icon = "🔄"
            elif "in progress" in row_lower:
                status_icon = "🔄"
            elif "blocked" in row_lower or "needs access" in row_lower:
                status_icon = "⏸️"
            elif "planned" in row_lower:
                status_icon = "🔜"
            elif "pending" in row_lower:
                status_icon = "🔜"
            elif "mentioned" in row_lower:
                status_icon = "💡"
            elif "future" in row_lower:
                status_icon = "🔜"
            elif "created" in row_lower:
                status_icon = "✅"
            elif "completed" in row_lower:
                status_icon = "✅"
            elif "quarterly" in row_lower or "monthly" in row_lower or "annual" in row_lower:
                status_icon = "🔄"  # recurring = ongoing
            elif "due" in row_lower:
                status_icon = "🔜"

        if status_icon and item_text and item_text not in ("---", ""):
            info = STATUS_MAP[status_icon]
            # Clean up item text
            item_text = re.sub(r"\*\*(.+?)\*\*", r"\1", item_text)  # remove bold
            item_text = re.sub(r"`(.+?)`", r"\1", item_text)  # remove code ticks
            # Extract details from last cell (if more than 2 meaningful cells)
            details = ""
            completed_date = None
            non_empty = [c for c in cells if c and c != "---" and not any(ic in c for ic in STATUS_MAP)]
            if len(non_empty) >= 2:
                last_cell = non_empty[-1].strip()
                if last_cell != item_text.strip():
                    details = re.sub(r"\*\*(.+?)\*\*", r"\1", last_cell)
                    details = re.sub(r"`(.+?)`", r"\1", details)
            # Check for Completed column (MM/DD/YYYY format)
            for cell in cells:
                date_match = re.match(r"^(\d{2}/\d{2}/\d{4})$", cell.strip())
                if date_match:
                    completed_date = date_match.group(1)
                    break
            items.append({
                "text": item_text.strip(),
                "details": details,
                "status_icon": status_icon,
                "status_label": info["label"],
                "status_color": info["color"],
                "css_class": info["css_class"],
                "completed_date": completed_date,
            })

    # --- Checkbox items: - [x] some completed thing (MM/DD/YYYY) ---
    for line in body.split("\n"):
        if COMPLETED_CHECKBOX.match(line):
            text = re.sub(r"^\s*-\s*\[x\]\s*", "", line, flags=re.IGNORECASE).strip()
            if text:
                # Extract date from end of line if present
                completed_date = None
                date_match = DATE_PATTERN.search(text)
                if date_match:
                    completed_date = date_match.group(1)
                    text = DATE_PATTERN.sub("", text).strip()
                items.append({
                    "text": text,
                    "details": "",
                    "status_icon": "✅",
                    "status_label": "Complete",
                    "status_color": "#22c55e",
                    "css_class": "complete",
                    "completed_date": completed_date,
                })

    # Sort items by status: ✅ Complete -> 🔄 In Progress -> 🔜 Planned -> 💡 Ideas -> 🚫 Blocked
    items.sort(key=lambda x: STATUS_ORDER.get(x["status_icon"], 99))

    return items


def count_statuses(items: list[dict]) -> dict:
    """Count items by status icon."""
    counts = {}
    for item in items:
        icon = item["status_icon"]
        counts[icon] = counts.get(icon, 0) + 1
    return counts


def extract_priorities(text: str) -> list[dict]:
    """Extract the Priority Summary quick-reference list."""
    priorities = []
    in_priority = False
    current_tier = ""

    for line in text.split("\n"):
        if "Priority Summary" in line:
            in_priority = True
            continue
        if in_priority and line.startswith("## "):
            break  # next major section
        if in_priority:
            if "### Immediate" in line:
                current_tier = "Immediate"
            elif "### Short-Term" in line:
                current_tier = "Short-Term"
            elif "### Medium-Term" in line:
                current_tier = "Medium-Term"
            elif "### Long-Term" in line:
                current_tier = "Long-Term"
            elif re.match(r"^\d+\.\s+", line.strip()):
                text_content = re.sub(r"^\d+\.\s+", "", line.strip())
                priorities.append({"tier": current_tier, "text": text_content})

    return priorities


def extract_completions_with_dates(sections: list[dict]) -> list[dict]:
    """Extract all completed items with dates for velocity tracking."""
    completions = []
    for section in sections:
        for item in section["items"]:
            if item["status_icon"] == "✅" and item.get("completed_date"):
                completions.append({
                    "text": item["text"],
                    "date": item["completed_date"],
                    "section": section["title"],
                    "section_num": section["number"],
                })
    # Sort by date (most recent first)
    def parse_date(d):
        try:
            parts = d.split("/")
            return (int(parts[2]), int(parts[0]), int(parts[1]))  # (year, month, day)
        except:
            return (0, 0, 0)
    completions.sort(key=lambda x: parse_date(x["date"]), reverse=True)
    return completions


# ---------------------------------------------------------------------------
# Cost Savings Configuration
# ---------------------------------------------------------------------------
# Market rates for external contractor work (USD/hour)
COST_CONFIG = {
    "hours_per_task": 4,  # Moderate estimate: Tooling handles most work, human reviews
    "blended_hourly_rate": 100,  # Average across task types:
    # - Documentation/planning: $75/hr
    # - Python development: $100/hr
    # - Test automation: $125/hr
    # - DevOps/infrastructure: $125/hr
    "tooling_monthly_cost": 200,  # Tooling Pro + API usage estimate
}


def calculate_cost_savings(total_complete: int, velocity: dict) -> dict:
    """
    Calculate estimated cost savings from AI-assisted development.

    Based on market rates for equivalent contractor work.
    """
    hours_per_task = COST_CONFIG["hours_per_task"]
    hourly_rate = COST_CONFIG["blended_hourly_rate"]
    tooling_cost = COST_CONFIG["tooling_monthly_cost"]

    # Total hours saved
    hours_saved = total_complete * hours_per_task

    # Gross savings (what it would cost to hire someone)
    gross_savings = hours_saved * hourly_rate

    # Calculate weeks of work
    weeks_tracked = 1
    if velocity.get("earliest") and velocity.get("latest"):
        try:
            from datetime import datetime
            earliest = datetime.strptime(velocity["earliest"], "%m/%d/%Y")
            latest = datetime.strptime(velocity["latest"], "%m/%d/%Y")
            weeks_tracked = max(1, (latest - earliest).days / 7)
        except:
            pass

    # Tooling cost over that period
    months_tracked = max(1, weeks_tracked / 4.33)
    total_tooling_cost = tooling_cost * months_tracked

    # Net savings
    net_savings = gross_savings - total_tooling_cost

    # ROI percentage
    roi_pct = round((net_savings / total_tooling_cost) * 100) if total_tooling_cost > 0 else 0

    return {
        "hours_saved": hours_saved,
        "gross_savings": gross_savings,
        "net_savings": net_savings,
        "roi_pct": roi_pct,
        "hourly_rate": hourly_rate,
        "hours_per_task": hours_per_task,
        "tooling_cost": round(total_tooling_cost),
        "weeks_tracked": round(weeks_tracked, 1),
    }


def calculate_velocity(completions: list[dict]) -> dict:
    """Calculate completion velocity metrics."""
    if not completions:
        return {"weekly_avg": 0, "total_with_dates": 0, "date_range": "N/A"}

    # Parse dates and calculate
    dates = []
    for c in completions:
        try:
            parts = c["date"].split("/")
            dates.append(datetime(int(parts[2]), int(parts[0]), int(parts[1])))
        except:
            pass

    if len(dates) < 2:
        return {"weekly_avg": len(dates), "total_with_dates": len(dates), "date_range": completions[0]["date"] if completions else "N/A"}

    earliest = min(dates)
    latest = max(dates)
    weeks = max(1, (latest - earliest).days / 7)
    weekly_avg = round(len(dates) / weeks, 1)

    return {
        "weekly_avg": weekly_avg,
        "total_with_dates": len(dates),
        "date_range": f"{earliest.strftime('%m/%d/%Y')} - {latest.strftime('%m/%d/%Y')}",
        "earliest": earliest.strftime('%m/%d/%Y'),
        "latest": latest.strftime('%m/%d/%Y'),
    }


def extract_timeline(text: str) -> list[dict]:
    """Extract the Timeline Overview table."""
    timeline = []
    in_timeline = False

    for line in text.split("\n"):
        if "## Timeline Overview" in line:
            in_timeline = True
            continue
        if in_timeline and line.startswith("## "):
            break
        if in_timeline and line.startswith("|") and "**" in line:
            cells = [c.strip() for c in line.split("|")]
            cells = [c for c in cells if c]
            if len(cells) >= 2:
                period = re.sub(r"\*\*", "", cells[0]).strip()
                focus = cells[1].strip()
                timeline.append({"period": period, "focus": focus})

    return timeline


def generate_html(sections, metadata, priorities, timeline, logo_svg, completions, velocity, good_times_font_b64=""):
    """Generate the complete HTML dashboard."""

    # Build section cards JSON for JS
    sections_json = json.dumps(sections, ensure_ascii=False, indent=2)
    priorities_json = json.dumps(priorities, ensure_ascii=False, indent=2)
    timeline_json = json.dumps(timeline, ensure_ascii=False, indent=2)
    completions_json = json.dumps(completions, ensure_ascii=False, indent=2)  # All completions for collapsible section
    velocity_json = json.dumps(velocity, ensure_ascii=False, indent=2)

    # Calculate totals
    total_items = sum(s["total"] for s in sections)
    total_complete = sum(s["completed"] for s in sections)
    total_in_progress = sum(s["counts"].get("🔄", 0) for s in sections)
    total_planned = sum(s["counts"].get("🔜", 0) for s in sections)
    total_ideas = sum(s["counts"].get("💡", 0) for s in sections)
    total_blocked = sum(s["counts"].get("⏸️", 0) + s["counts"].get("🚫", 0) for s in sections)

    # Calculate cost savings
    cost_savings = calculate_cost_savings(total_complete, velocity)
    # Pre-format currency values for template
    cost_savings_formatted = f"${cost_savings['gross_savings']:,}"
    net_savings_formatted = f"${cost_savings['net_savings']:,}"
    overall_pct = round((total_complete / total_items) * 100) if total_items else 0

    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>QA Automation Roadmap - Soterix Systems</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link href="https://fonts.googleapis.com/css2?family=Yantramanav:wght@300;400;500;700;900&display=swap" rel="stylesheet">
<style>
/* ===== GOOD TIMES FONT (Soterix Brand) ===== */
@font-face {{
    font-family: 'Good Times';
    src: url('data:font/opentype;base64,{good_times_font_b64}') format('opentype');
    font-weight: normal;
    font-style: normal;
    font-display: swap;
}}

/* ===== RESET & BASE ===== */
*, *::before, *::after {{ box-sizing: border-box; margin: 0; padding: 0; }}

body {{
    font-family: 'Yantramanav', 'Open Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
    background: #2F2E37;
    color: #e0e0e0;
    line-height: 1.5;
    -webkit-font-smoothing: antialiased;
}}

/* ===== BRAND COLORS ===== */
:root {{
    --primary-blue: #127CA3;
    --oslo-gray: #BCBEC0;
    --dark-bg: #2F2E37;
    --accent-blue: #46A1B1;
    --accent-grey: #AD9B68;
    --green: #22c55e;
    --red: #ef4444;
    --white: #ffffff;
    --light-bg: #2F2E37;
    --card-bg: #3a3944;
    --card-bg-hover: #43424d;
    --card-shadow: 0 2px 8px rgba(0,0,0,0.3);
    --card-shadow-hover: 0 6px 20px rgba(0,0,0,0.45);
    --border-subtle: #4a4957;
    --text-primary: #f0f0f2;
    --text-secondary: #a8a8b0;
    --text-muted: #7a7a85;
}}

/* ===== HEADER ===== */
.header {{
    background: #26252d;
    color: var(--white);
    padding: 24px 40px;
    display: flex;
    align-items: center;
    justify-content: space-between;
    flex-wrap: wrap;
    gap: 16px;
    border-bottom: 2px solid var(--primary-blue);
}}
.header-left {{
    display: flex;
    align-items: center;
    gap: 24px;
}}
.header-logo svg,
.header-logo img {{
    height: 52px;
    width: auto;
}}
.header-title {{
    font-family: 'Good Times', 'Yantramanav', sans-serif;
    font-weight: normal;
    font-size: 26px;
    letter-spacing: 3px;
    text-transform: uppercase;
    color: var(--white);
}}
.header-subtitle {{
    font-size: 16px;
    color: var(--oslo-gray);
    font-weight: 300;
    margin-top: 2px;
}}
.header-meta {{
    text-align: right;
    font-size: 14px;
    color: var(--oslo-gray);
    font-weight: 300;
}}
.header-meta strong {{
    color: var(--accent-blue);
    font-weight: 500;
}}
.header-meta strong {{
    color: var(--accent-blue);
    font-weight: 500;
}}

/* ===== CONTAINER ===== */
.container {{
    max-width: 1280px;
    margin: 0 auto;
    padding: 24px 20px;
}}

/* ===== SEARCH BAR (compact, in header) ===== */
.search-container {{
    margin: 0;
}}
.search-input {{
    width: 220px;
    padding: 8px 14px 8px 36px;
    font-size: 13px;
    border: 1px solid var(--border-subtle);
    border-radius: 8px;
    background: rgba(255,255,255,0.08);
    color: var(--text-primary);
    font-family: inherit;
    transition: all 0.2s;
}}
.search-input:focus {{
    outline: none;
    border-color: var(--primary-blue);
    background: rgba(255,255,255,0.12);
    width: 280px;
}}
.search-input::placeholder {{
    color: var(--text-muted);
}}
.search-wrapper {{
    position: relative;
}}
.search-icon {{
    position: absolute;
    left: 10px;
    top: 50%;
    transform: translateY(-50%);
    color: var(--text-muted);
    font-size: 14px;
    pointer-events: none;
}}
.search-clear {{
    position: absolute;
    right: 8px;
    top: 50%;
    transform: translateY(-50%);
    background: none;
    border: none;
    color: var(--text-muted);
    font-size: 18px;
    cursor: pointer;
    padding: 4px 8px;
    border-radius: 4px;
    display: none;
}}
.search-clear:hover {{
    color: var(--text-primary);
    background: var(--card-bg-hover);
}}
.search-clear.visible {{
    display: block;
}}
.no-results {{
    text-align: center;
    padding: 40px 20px;
    color: var(--text-muted);
    font-size: 15px;
}}
.section-card.hidden {{
    display: none;
}}
.highlight {{
    background: rgba(18,124,163,0.3);
    border-radius: 2px;
    padding: 0 2px;
}}

/* ===== SUMMARY CARDS ===== */
.summary-row {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
    gap: 16px;
    margin-bottom: 28px;
}}
.summary-card {{
    background: var(--card-bg);
    border-radius: 12px;
    padding: 20px 20px 16px;
    box-shadow: var(--card-shadow);
    text-align: center;
    transition: box-shadow 0.2s, transform 0.15s;
    border: 1px solid var(--border-subtle);
    cursor: pointer;
}}
.summary-card:hover {{
    box-shadow: var(--card-shadow-hover);
    transform: translateY(-2px);
    background: var(--card-bg-hover);
}}
.summary-card .number {{
    font-size: 48px;
    font-weight: 900;
    line-height: 1;
    margin-bottom: 4px;
}}
.summary-card .label {{
    font-size: 15px;
    text-transform: uppercase;
    letter-spacing: 1.5px;
    color: var(--text-secondary);
    font-weight: 500;
}}
.summary-card.overall .number {{ color: var(--primary-blue); }}
.summary-card.total .number {{ color: var(--text-primary); }}
.summary-card.complete .number {{ color: var(--green); }}
.summary-card.in-progress .number {{ color: var(--primary-blue); }}
.summary-card.planned .number {{ color: var(--accent-blue); }}
.summary-card.blocked .number {{ color: var(--red); }}

/* ===== STATUS LEGEND ITEMS (used in Projects) ===== */
.status-legend-item {{
    display: flex;
    align-items: center;
    gap: 8px;
    font-size: 13px;
    color: var(--text-secondary);
}}
.status-legend-item .legend-indicator {{
    width: 14px;
    height: 14px;
    display: flex;
    align-items: center;
    justify-content: center;
}}
.status-legend-item .legend-dot {{
    width: 10px;
    height: 10px;
    border-radius: 50%;
    position: relative;
}}
/* Complete - green with checkmark */
.status-legend-item.complete .legend-dot {{
    background: #22c55e;
}}
.status-legend-item.complete .legend-dot::after {{
    content: '';
    position: absolute;
    left: 3px;
    top: 1px;
    width: 3px;
    height: 6px;
    border: solid #fff;
    border-width: 0 2px 2px 0;
    transform: rotate(45deg);
}}
/* In Progress - blue pulse */
.status-legend-item.in-progress .legend-dot {{
    background: #127CA3;
    animation: pulse 2s ease-in-out infinite;
}}
/* Planned - outline */
.status-legend-item.planned .legend-dot {{
    background: transparent;
    border: 2px solid #46A1B1;
    width: 8px;
    height: 8px;
}}
/* Idea - diamond */
.status-legend-item.idea .legend-dot {{
    background: #AD9B68;
    border-radius: 2px;
    transform: rotate(45deg);
    width: 8px;
    height: 8px;
}}
/* Blocked - red square */
.status-legend-item.blocked .legend-dot {{
    background: #ef4444;
    border-radius: 2px;
}}

/* ===== DRILLDOWN MODAL ===== */
.modal-overlay {{
    display: none;
    position: fixed;
    top: 0; left: 0; right: 0; bottom: 0;
    background: rgba(0,0,0,0.65);
    z-index: 1000;
    justify-content: center;
    align-items: flex-start;
    padding: 60px 20px 20px;
    overflow-y: auto;
    backdrop-filter: blur(4px);
}}
.modal-overlay.open {{
    display: flex;
}}
.modal {{
    background: var(--card-bg);
    border-radius: 16px;
    max-width: 720px;
    width: 100%;
    box-shadow: 0 20px 60px rgba(0,0,0,0.5);
    border: 1px solid var(--border-subtle);
    max-height: calc(100vh - 100px);
    display: flex;
    flex-direction: column;
}}
.modal-header {{
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 24px 28px 16px;
    border-bottom: 1px solid var(--border-subtle);
    flex-shrink: 0;
}}
.modal-header h2 {{
    margin: 0;
    font-size: 22px;
    color: var(--text-primary);
    font-weight: 700;
}}
.modal-header .modal-count {{
    font-size: 15px;
    color: var(--text-secondary);
    margin-left: 12px;
    font-weight: 400;
}}
.modal-close {{
    background: none;
    border: none;
    color: var(--text-secondary);
    font-size: 24px;
    cursor: pointer;
    padding: 4px 8px;
    border-radius: 6px;
    transition: background 0.15s;
}}
.modal-close:hover {{
    background: var(--card-bg-hover);
    color: var(--text-primary);
}}
.modal-body {{
    padding: 20px 28px 28px;
    overflow-y: auto;
    flex: 1;
}}
.modal-section {{
    margin-bottom: 20px;
}}
.modal-section:last-child {{
    margin-bottom: 0;
}}
.modal-section-title {{
    font-size: 15px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 1px;
    color: var(--text-secondary);
    margin-bottom: 10px;
    padding-bottom: 6px;
    border-bottom: 1px solid var(--border-subtle);
}}
.modal-item {{
    display: flex;
    align-items: flex-start;
    gap: 10px;
    padding: 8px 0;
    font-size: 17px;
    color: var(--text-primary);
    line-height: 1.45;
}}
.modal-item .item-icon {{
    flex-shrink: 0;
    width: 20px;
    height: 20px;
    display: flex;
    align-items: center;
    justify-content: center;
    margin-top: 2px;
}}
.modal-item .status-dot {{
    width: 12px;
    height: 12px;
    border-radius: 50%;
    position: relative;
}}
/* Modal status colors */
.modal-item.complete .status-dot {{
    background: #22c55e;
}}
.modal-item.complete .status-dot::after {{
    content: '';
    position: absolute;
    left: 4px;
    top: 1px;
    width: 3px;
    height: 7px;
    border: solid #fff;
    border-width: 0 2px 2px 0;
    transform: rotate(45deg);
}}
.modal-item.in-progress .status-dot {{
    background: #127CA3;
    animation: pulse-item 2s ease-in-out infinite;
}}
.modal-item.planned .status-dot {{
    background: transparent;
    border: 2px solid #46A1B1;
    width: 10px;
    height: 10px;
}}
.modal-item.idea .status-dot {{
    background: #AD9B68;
    border-radius: 2px;
    transform: rotate(45deg);
    width: 10px;
    height: 10px;
}}
.modal-item.blocked .status-dot {{
    background: #ef4444;
    border-radius: 2px;
}}
.modal-item .item-detail {{
    color: var(--text-muted);
    margin-left: 4px;
}}

/* ===== OVERALL PROGRESS BAR ===== */
.overall-progress {{
    background: var(--card-bg);
    border-radius: 12px;
    padding: 24px;
    box-shadow: var(--card-shadow);
    margin-bottom: 28px;
    border: 1px solid var(--border-subtle);
}}
.overall-progress h2 {{
    font-size: 14px;
    text-transform: uppercase;
    letter-spacing: 2px;
    color: var(--text-secondary);
    font-weight: 700;
    margin-bottom: 12px;
}}
.progress-bar-wrap {{
    background: #26252d;
    border-radius: 10px;
    height: 28px;
    overflow: hidden;
    position: relative;
}}
.progress-bar-fill {{
    height: 100%;
    border-radius: 10px;
    background: linear-gradient(90deg, var(--primary-blue), var(--accent-blue));
    transition: width 0.8s ease;
    display: flex;
    align-items: center;
    justify-content: flex-end;
    padding-right: 12px;
    font-size: 13px;
    font-weight: 700;
    color: var(--white);
    min-width: 60px;
}}

/* ===== AI ENABLEMENT ===== */
.ai-section {{
    background: linear-gradient(135deg, #127CA3 0%, #46A1B1 100%);
    border-radius: 12px;
    padding: 28px 28px 24px;
    color: var(--white);
    margin-bottom: 28px;
    box-shadow: var(--card-shadow);
    border: 1px solid rgba(70,161,177,0.3);
}}
.ai-section h2 {{
    font-size: 18px;
    text-transform: uppercase;
    letter-spacing: 2px;
    font-weight: 700;
    margin-bottom: 8px;
}}
.ai-section p {{
    font-size: 15px;
    font-weight: 300;
    margin-bottom: 16px;
    opacity: 0.95;
}}
.ai-highlights {{
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
    gap: 12px;
}}
.ai-highlight-card {{
    background: rgba(255,255,255,0.15);
    border-radius: 8px;
    padding: 14px 16px;
    backdrop-filter: blur(4px);
    position: relative;
    cursor: help;
    transition: transform 0.15s, box-shadow 0.15s;
}}
.ai-highlight-card:hover {{
    transform: translateY(-2px);
    box-shadow: 0 4px 12px rgba(0,0,0,0.3);
}}
.ai-highlight-card .ai-num {{
    font-size: 28px;
    font-weight: 900;
    line-height: 1;
}}
.ai-highlight-card .ai-label {{
    font-size: 12px;
    text-transform: uppercase;
    letter-spacing: 1px;
    opacity: 0.85;
    margin-top: 4px;
}}
/* Tooltip for AI cards */
.ai-highlight-card .tooltip {{
    visibility: hidden;
    opacity: 0;
    position: absolute;
    bottom: 100%;
    left: 50%;
    transform: translateX(-50%);
    background: #1a1a22;
    color: var(--text-secondary);
    padding: 10px 14px;
    border-radius: 8px;
    font-size: 13px;
    line-height: 1.5;
    white-space: normal;
    width: 220px;
    text-align: left;
    box-shadow: 0 4px 16px rgba(0,0,0,0.4);
    border: 1px solid var(--border-subtle);
    z-index: 100;
    margin-bottom: 8px;
    transition: opacity 0.2s, visibility 0.2s;
    text-transform: none;
    letter-spacing: 0;
    font-weight: 400;
}}
.ai-highlight-card .tooltip::after {{
    content: '';
    position: absolute;
    top: 100%;
    left: 50%;
    transform: translateX(-50%);
    border: 6px solid transparent;
    border-top-color: #1a1a22;
}}
.ai-highlight-card:hover .tooltip {{
    visibility: visible;
    opacity: 1;
}}

/* ===== PROJECTS SECTION ===== */
.projects-section {{
    margin-bottom: 28px;
}}
.projects-header {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 16px 20px;
    background: var(--card-bg);
    border-radius: 12px 12px 0 0;
    border: 1px solid var(--border-subtle);
    border-bottom: none;
    gap: 16px;
}}
.projects-title {{
    font-size: 16px;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 2px;
    color: var(--text-primary);
    display: flex;
    align-items: center;
    gap: 10px;
}}
.projects-title .section-count {{
    font-size: 13px;
    font-weight: 500;
    color: var(--text-muted);
    letter-spacing: 0;
    text-transform: none;
}}
.projects-search {{
    position: relative;
}}
.projects-search .search-input {{
    width: 240px;
    padding: 8px 14px 8px 36px;
    font-size: 13px;
    border: 1px solid var(--border-subtle);
    border-radius: 8px;
    background: rgba(255,255,255,0.06);
    color: var(--text-primary);
    font-family: inherit;
    transition: all 0.2s;
}}
.projects-search .search-input:focus {{
    outline: none;
    border-color: var(--primary-blue);
    background: rgba(255,255,255,0.1);
    width: 300px;
}}
.projects-search .search-input::placeholder {{
    color: var(--text-muted);
}}
.projects-search .search-icon {{
    position: absolute;
    left: 10px;
    top: 50%;
    transform: translateY(-50%);
    color: var(--text-muted);
    font-size: 14px;
    pointer-events: none;
}}
.projects-search .search-clear {{
    position: absolute;
    right: 8px;
    top: 50%;
    transform: translateY(-50%);
    background: none;
    border: none;
    color: var(--text-muted);
    font-size: 16px;
    cursor: pointer;
    padding: 2px 6px;
    border-radius: 4px;
    display: none;
}}
.projects-search .search-clear:hover {{
    color: var(--text-primary);
    background: rgba(255,255,255,0.1);
}}
.projects-search .search-clear.visible {{
    display: block;
}}
.projects-legend {{
    display: flex;
    justify-content: center;
    gap: 24px;
    flex-wrap: wrap;
    padding: 12px 20px;
    background: var(--card-bg);
    border: 1px solid var(--border-subtle);
    border-top: none;
}}
.projects-body {{
    background: rgba(47,46,55,0.3);
    border: 1px solid var(--border-subtle);
    border-top: none;
    border-radius: 0 0 12px 12px;
    padding: 16px;
}}

/* ===== COLLAPSIBLE SECTION (Recent Completions) ===== */
.collapsible-section {{
    background: var(--card-bg);
    border-radius: 12px;
    box-shadow: var(--card-shadow);
    margin-bottom: 20px;
    border: 1px solid var(--border-subtle);
    overflow: hidden;
}}
.collapsible-header {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 16px 20px;
    cursor: pointer;
    user-select: none;
    transition: background 0.15s;
}}
.collapsible-header:hover {{
    background: var(--card-bg-hover);
}}
.collapsible-header h2 {{
    font-size: 16px;
    text-transform: uppercase;
    letter-spacing: 2px;
    color: var(--text-primary);
    font-weight: 700;
    margin: 0;
    display: flex;
    align-items: center;
    gap: 12px;
}}
.collapsible-header .preview-badge {{
    font-size: 12px;
    font-weight: 500;
    padding: 4px 10px;
    border-radius: 12px;
    background: rgba(18,124,163,0.15);
    color: var(--accent-blue);
    letter-spacing: 0;
    text-transform: none;
}}
.collapsible-header .chevron {{
    font-size: 18px;
    color: var(--oslo-gray);
    transition: transform 0.3s;
}}
.collapsible-section.open .collapsible-header .chevron {{
    transform: rotate(180deg);
}}
.collapsible-body {{
    max-height: 0;
    overflow: hidden;
    transition: max-height 0.4s ease;
}}
.collapsible-section.open .collapsible-body {{
    max-height: 2000px;
}}
.collapsible-body-inner {{
    padding: 0 20px 20px;
    border-top: 1px solid var(--border-subtle);
}}

/* ===== SECTION CARDS ===== */
.sections-grid {{
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(380px, 1fr));
    gap: 16px;
}}
.section-card {{
    background: var(--card-bg);
    border-radius: 12px;
    box-shadow: var(--card-shadow);
    overflow: hidden;
    transition: box-shadow 0.2s;
    border: 1px solid var(--border-subtle);
}}
.section-card:hover {{
    box-shadow: var(--card-shadow-hover);
}}
.section-header {{
    padding: 18px 20px 14px;
    cursor: pointer;
    user-select: none;
    display: flex;
    flex-direction: column;
    gap: 10px;
}}
.section-header:hover {{
    background: var(--card-bg-hover);
}}
.section-top-row {{
    display: flex;
    align-items: center;
    justify-content: space-between;
}}
.section-title {{
    font-size: 20px;
    font-weight: 700;
    color: var(--text-primary);
    display: flex;
    align-items: center;
    gap: 8px;
}}
.section-num {{
    background: var(--primary-blue);
    color: var(--white);
    font-size: 15px;
    font-weight: 700;
    width: 32px;
    height: 32px;
    border-radius: 6px;
    display: flex;
    align-items: center;
    justify-content: center;
    flex-shrink: 0;
}}
.section-pct {{
    font-size: 19px;
    font-weight: 700;
    color: var(--primary-blue);
}}
.section-progress {{
    background: #26252d;
    border-radius: 6px;
    height: 8px;
    overflow: hidden;
}}
.section-progress-fill {{
    height: 100%;
    border-radius: 6px;
    background: linear-gradient(90deg, var(--primary-blue), var(--accent-blue));
    transition: width 0.6s ease;
}}
.section-badges {{
    display: flex;
    gap: 8px;
    flex-wrap: wrap;
}}
/* ===== MODERN STATUS BADGES ===== */
.badge {{
    font-size: 13px;
    padding: 6px 10px;
    border-radius: 16px;
    font-weight: 600;
    display: inline-flex;
    align-items: center;
    gap: 6px;
    transition: all 0.2s ease;
    position: relative;
}}

/* Status indicator (geometric shapes) */
.badge .indicator {{
    width: 10px;
    height: 10px;
    display: inline-block;
    flex-shrink: 0;
    position: relative;
}}

/* Complete - solid green circle with checkmark */
.badge.complete {{ 
    background: rgba(34, 197, 94, 0.12); 
    color: #4ade80; 
}}
.badge.complete .indicator {{
    background: #22c55e;
    border-radius: 50%;
}}
.badge.complete .indicator::after {{
    content: '';
    position: absolute;
    left: 3px;
    top: 1px;
    width: 3px;
    height: 6px;
    border: solid #fff;
    border-width: 0 2px 2px 0;
    transform: rotate(45deg);
}}

/* In Progress - animated pulse ring */
.badge.in-progress {{ 
    background: rgba(18, 124, 163, 0.15); 
    color: #5bb8d4; 
}}
.badge.in-progress .indicator {{
    background: #127CA3;
    border-radius: 50%;
    animation: pulse 2s ease-in-out infinite;
}}
@keyframes pulse {{
    0%, 100% {{ box-shadow: 0 0 0 0 rgba(18, 124, 163, 0.5); }}
    50% {{ box-shadow: 0 0 0 4px rgba(18, 124, 163, 0); }}
}}

/* Planned - outline circle */
.badge.planned {{ 
    background: rgba(70, 161, 177, 0.12); 
    color: #6ec5d4; 
}}
.badge.planned .indicator {{
    background: transparent;
    border: 2px solid #46A1B1;
    border-radius: 50%;
    width: 8px;
    height: 8px;
}}

/* Ideas - diamond shape */
.badge.idea {{ 
    background: rgba(173, 155, 104, 0.15); 
    color: #c9b87e; 
}}
.badge.idea .indicator {{
    background: #AD9B68;
    border-radius: 2px;
    transform: rotate(45deg);
    width: 8px;
    height: 8px;
}}

/* Blocked - red square/stop */
.badge.blocked {{ 
    background: rgba(239, 68, 68, 0.12); 
    color: #f87171; 
}}
.badge.blocked .indicator {{
    background: #ef4444;
    border-radius: 2px;
}}

/* Hover & active states */
.badge.clickable {{ 
    cursor: pointer; 
}}
.badge.clickable:hover {{ 
    transform: translateY(-1px); 
    box-shadow: 0 3px 10px rgba(0,0,0,0.25);
}}
.badge.active {{ 
    box-shadow: 0 0 0 2px var(--white); 
    transform: scale(1.05); 
}}

/* Label visibility - compact by default, expand on hover */
.badge .label {{
    max-width: 0;
    overflow: hidden;
    white-space: nowrap;
    transition: max-width 0.3s ease, margin-left 0.3s ease;
    margin-left: 0;
    opacity: 0;
}}
.badge:hover .label,
.badge.active .label {{
    max-width: 100px;
    margin-left: 2px;
    opacity: 1;
}}

.clear-filter {{
    font-size: 12px;
    padding: 4px 10px;
    border-radius: 12px;
    background: rgba(255,255,255,0.08);
    color: var(--text-secondary);
    border: 1px solid var(--border-subtle);
    cursor: pointer;
    margin-left: 6px;
    transition: all 0.15s;
}}
.clear-filter:hover {{ 
    background: rgba(255,255,255,0.15); 
    color: var(--text-primary); 
}}
.item-row.filtered-out {{ display: none; }}

.chevron {{
    font-size: 22px;
    color: var(--oslo-gray);
    transition: transform 0.3s;
    flex-shrink: 0;
    margin-left: 8px;
}}
.section-card.open .chevron {{
    transform: rotate(180deg);
}}

/* ===== SECTION DETAIL (expandable) ===== */
.section-detail {{
    max-height: 0;
    overflow: hidden;
    transition: max-height 0.4s ease;
}}
.section-card.open .section-detail {{
    max-height: 2000px;
}}
.section-detail-inner {{
    padding: 0 20px 18px;
    border-top: 1px solid var(--border-subtle);
}}
.item-row {{
    display: flex;
    align-items: flex-start;
    gap: 10px;
    padding: 8px 0;
    border-bottom: 1px solid rgba(74,73,87,0.5);
    font-size: 17px;
}}
.item-row:last-child {{ border-bottom: none; }}

/* ===== ITEM STATUS INDICATORS (geometric) ===== */
.item-status {{
    width: 18px;
    height: 18px;
    flex-shrink: 0;
    margin-top: 3px;
    display: flex;
    align-items: center;
    justify-content: center;
}}
.item-status .status-dot {{
    width: 12px;
    height: 12px;
    border-radius: 50%;
    position: relative;
}}

/* Complete - green with checkmark */
.item-status.complete .status-dot {{
    background: #22c55e;
}}
.item-status.complete .status-dot::after {{
    content: '';
    position: absolute;
    left: 4px;
    top: 1px;
    width: 3px;
    height: 7px;
    border: solid #fff;
    border-width: 0 2px 2px 0;
    transform: rotate(45deg);
}}

/* In Progress - blue with pulse */
.item-status.in-progress .status-dot {{
    background: #127CA3;
    animation: pulse-item 2s ease-in-out infinite;
}}
@keyframes pulse-item {{
    0%, 100% {{ box-shadow: 0 0 0 0 rgba(18, 124, 163, 0.4); }}
    50% {{ box-shadow: 0 0 0 3px rgba(18, 124, 163, 0); }}
}}

/* Planned - outline circle */
.item-status.planned .status-dot {{
    background: transparent;
    border: 2px solid #46A1B1;
    width: 10px;
    height: 10px;
}}

/* Idea - diamond */
.item-status.idea .status-dot {{
    background: #AD9B68;
    border-radius: 2px;
    transform: rotate(45deg);
    width: 10px;
    height: 10px;
}}

/* Blocked - red square */
.item-status.blocked .status-dot {{
    background: #ef4444;
    border-radius: 2px;
}}

.item-text {{
    flex: 1;
    color: var(--text-secondary);
}}
.item-text.complete-text {{
    color: var(--text-secondary);
}}
.item-detail {{
    color: var(--text-muted);
    font-size: 13px;
}}

/* ===== PRIORITY SECTION ===== */
.priority-section {{
    background: var(--card-bg);
    border-radius: 12px;
    padding: 24px;
    box-shadow: var(--card-shadow);
    margin-bottom: 28px;
    border: 1px solid var(--border-subtle);
}}
.priority-section h2 {{
    font-size: 16px;
    text-transform: uppercase;
    letter-spacing: 2px;
    color: var(--text-primary);
    font-weight: 700;
    margin-bottom: 16px;
}}
.priority-tier {{
    margin-bottom: 16px;
}}
.priority-tier:last-child {{ margin-bottom: 0; }}
.tier-label {{
    font-size: 16px;
    text-transform: uppercase;
    letter-spacing: 1.5px;
    font-weight: 700;
    margin-bottom: 8px;
    padding: 4px 12px;
    border-radius: 6px;
    display: inline-block;
}}
.tier-label.immediate {{ background: rgba(239,68,68,0.15); color: #f87171; }}
.tier-label.short-term {{ background: rgba(173,155,104,0.2); color: #c9b87e; }}
.tier-label.medium-term {{ background: rgba(18,124,163,0.2); color: #5bb8d4; }}
.tier-label.long-term {{ background: rgba(70,161,177,0.15); color: #6ec5d4; }}
.priority-list {{
    list-style: none;
    padding: 0;
}}
.priority-list li {{
    padding: 6px 0 6px 16px;
    font-size: 17px;
    color: var(--text-secondary);
    position: relative;
}}
.priority-list li::before {{
    content: '';
    position: absolute;
    left: 0;
    top: 13px;
    width: 8px;
    height: 8px;
    border-radius: 50%;
    background: var(--primary-blue);
}}

/* ===== TIMELINE ===== */
.timeline-section {{
    background: var(--card-bg);
    border-radius: 12px;
    padding: 24px;
    box-shadow: var(--card-shadow);
    margin-bottom: 28px;
    border: 1px solid var(--border-subtle);
}}
.timeline-section h2 {{
    font-size: 16px;
    text-transform: uppercase;
    letter-spacing: 2px;
    color: var(--text-primary);
    font-weight: 700;
    margin-bottom: 20px;
}}
.timeline {{
    position: relative;
    padding-left: 32px;
}}
.timeline::before {{
    content: '';
    position: absolute;
    left: 8px;
    top: 0;
    bottom: 0;
    width: 3px;
    background: linear-gradient(to bottom, var(--primary-blue), var(--accent-blue), var(--oslo-gray));
    border-radius: 2px;
}}
.timeline-item {{
    position: relative;
    margin-bottom: 24px;
}}
.timeline-item:last-child {{ margin-bottom: 0; }}
.timeline-dot {{
    position: absolute;
    left: -28px;
    top: 4px;
    width: 14px;
    height: 14px;
    border-radius: 50%;
    background: var(--primary-blue);
    border: 3px solid var(--card-bg);
    box-shadow: 0 0 0 2px var(--primary-blue);
}}
.timeline-item:first-child .timeline-dot {{
    background: var(--green);
    box-shadow: 0 0 0 2px var(--green);
}}
.timeline-period {{
    font-weight: 700;
    font-size: 18px;
    color: var(--text-primary);
    margin-bottom: 4px;
}}
.timeline-focus {{
    font-size: 16px;
    color: var(--text-secondary);
    line-height: 1.4;
}}

/* ===== FOOTER ===== */
.footer {{
    text-align: center;
    padding: 24px;
    font-size: 12px;
    color: var(--oslo-gray);
}}
.footer a {{
    color: var(--accent-blue);
    text-decoration: none;
}}

/* ===== RESPONSIVE ===== */
@media (max-width: 768px) {{
    .header {{
        padding: 20px;
        flex-direction: column;
        text-align: center;
        gap: 12px;
    }}
    .header-left {{
        flex-direction: column;
    }}
    .header-meta {{ text-align: center; }}
    .header-title {{ font-size: 20px; }}
    .projects-header {{
        flex-direction: column;
        gap: 12px;
        text-align: center;
    }}
    .projects-search .search-input {{
        width: 100%;
    }}
    .projects-search .search-input:focus {{
        width: 100%;
    }}
    .projects-legend {{
        gap: 12px;
        padding: 10px;
    }}
    .status-legend-item {{
        font-size: 11px;
    }}
    .sections-grid {{
        grid-template-columns: 1fr;
    }}
    .summary-row {{
        grid-template-columns: repeat(3, 1fr);
    }}
    .collapsible-header h2 {{
        font-size: 14px;
    }}
}}

@media print {{
    .section-detail {{ max-height: none !important; }}
    .chevron {{ display: none; }}
    body {{ background: #1a1a22; }}
}}
</style>
</head>
<body>

<!-- HEADER -->
<div class="header">
    <div class="header-left">
        <div class="header-logo">{logo_svg}</div>
        <div>
            <div class="header-title">QA Automation Roadmap</div>
            <div class="header-subtitle">AI-Enabled Testing & Automation Progress</div>
        </div>
    </div>
    <div class="header-meta">
        <div>Updated: <strong>{metadata['last_updated']}</strong></div>
        <div>{metadata['owner']}</div>
    </div>
</div>

<div class="container">

    <!-- SUMMARY CARDS -->
    <div class="summary-row">
        <div class="summary-card overall" onclick="openDrilldown('overall')">
            <div class="number">{overall_pct}%</div>
            <div class="label">Overall Complete</div>
        </div>
        <div class="summary-card total" onclick="openDrilldown('total')">
            <div class="number">{total_items}</div>
            <div class="label">Total Items</div>
        </div>
        <div class="summary-card complete" onclick="openDrilldown('complete')">
            <div class="number">{total_complete}</div>
            <div class="label">Complete</div>
        </div>
        <div class="summary-card in-progress" onclick="openDrilldown('in-progress')">
            <div class="number">{total_in_progress}</div>
            <div class="label">In Progress</div>
        </div>
        <div class="summary-card planned" onclick="openDrilldown('planned')">
            <div class="number">{total_planned + total_ideas}</div>
            <div class="label">Planned / Ideas</div>
        </div>
        <div class="summary-card blocked" onclick="openDrilldown('blocked')">
            <div class="number">{total_blocked}</div>
            <div class="label">Blocked</div>
        </div>
    </div>

    <!-- DRILLDOWN MODAL -->
    <div class="modal-overlay" id="drilldown-modal" onclick="if(event.target===this)closeDrilldown()">
        <div class="modal">
            <div class="modal-header">
                <h2 id="drilldown-title">Drilldown</h2>
                <button class="modal-close" onclick="closeDrilldown()">&times;</button>
            </div>
            <div class="modal-body" id="drilldown-body"></div>
        </div>
    </div>

    <!-- OVERALL PROGRESS BAR -->
    <div class="overall-progress">
        <h2>Roadmap Progress</h2>
        <div class="progress-bar-wrap">
            <div class="progress-bar-fill" style="width: {overall_pct}%">{overall_pct}%</div>
        </div>
    </div>

    <!-- AI ENABLEMENT -->
    <div class="ai-section">
        <h2>AI-Enabled Outcomes</h2>
        <p>All items on this roadmap are being planned, built, and executed with AI tools as a force multiplier across test automation, documentation, integrations, and strategic planning.</p>
        <div class="ai-highlights">
            <div class="ai-highlight-card">
                <div class="ai-num">{total_complete}</div>
                <div class="ai-label">Deliverables Completed</div>
                <div class="tooltip">Roadmap items marked as complete. Includes documentation, test automation, integrations, and infrastructure tasks tracked in FUTURE_ROADMAP.md</div>
            </div>
            <div class="ai-highlight-card">
                <div class="ai-num">{velocity.get('weekly_avg', 0)}</div>
                <div class="ai-label">Items / Week (Velocity)</div>
                <div class="tooltip">Average completion rate calculated from {velocity.get('total_with_dates', 0)} items with tracked dates over {cost_savings['weeks_tracked']} weeks ({velocity.get('date_range', 'N/A')})</div>
            </div>
            <div class="ai-highlight-card">
                <div class="ai-num">{len(sections)}</div>
                <div class="ai-label">Workstreams Active</div>
                <div class="tooltip">Parallel workstreams being managed: Test Automation, QA Touch, CI/CD, Mobile, Hardware, Documentation, and more</div>
            </div>
            <div class="ai-highlight-card">
                <div class="ai-num">3</div>
                <div class="ai-label">Tooling Interfaces Used</div>
                <div class="tooltip"><strong>Tooling Code (VS Code)</strong> - IDE integration for code editing<br><strong>Tooling Code (Terminal)</strong> - CLI for automation scripts<br><strong>Tooling.ai</strong> - Web app for research and planning</div>
            </div>
        </div>
        <!-- Cost Savings Row -->
        <div class="ai-highlights" style="margin-top: 16px;">
            <div class="ai-highlight-card">
                <div class="ai-num">{cost_savings['hours_saved']}</div>
                <div class="ai-label">Hours Saved</div>
                <div class="tooltip"><strong>Calculation:</strong><br>{total_complete} deliverables × {cost_savings['hours_per_task']} hrs/task = {cost_savings['hours_saved']} hours<br><br>Estimate assumes Tooling handles ~80% of work, human reviews and refines</div>
            </div>
            <div class="ai-highlight-card">
                <div class="ai-num">{cost_savings_formatted}</div>
                <div class="ai-label">Est. Cost Savings</div>
                <div class="tooltip"><strong>Calculation:</strong><br>{cost_savings['hours_saved']} hrs × ${cost_savings['hourly_rate']}/hr = {cost_savings_formatted}<br><br><strong>Market rate breakdown:</strong><br>• Documentation: $75/hr<br>• Python dev: $100/hr<br>• Test automation: $125/hr<br>• DevOps: $125/hr<br>Blended avg: ${cost_savings['hourly_rate']}/hr</div>
            </div>
            <div class="ai-highlight-card">
                <div class="ai-num">{cost_savings['roi_pct']}%</div>
                <div class="ai-label">ROI vs Tooling Cost</div>
                <div class="tooltip"><strong>Return on Investment:</strong><br>Net savings / Tooling cost × 100<br><br><strong>Tooling cost:</strong> ~${cost_savings['tooling_cost']} over {cost_savings['weeks_tracked']} weeks<br>(Pro subscription + API usage)<br><br><strong>Net savings:</strong> {net_savings_formatted}</div>
            </div>
        </div>
    </div>

    <!-- RECENT COMPLETIONS (collapsible, closed by default) -->
    <div class="collapsible-section" id="recent-completions">
        <div class="collapsible-header" onclick="this.parentElement.classList.toggle('open')">
            <h2>
                Recent Completions
                <span class="preview-badge">{len(completions)} items</span>
            </h2>
            <span class="chevron">&#9660;</span>
        </div>
        <div class="collapsible-body">
            <div class="collapsible-body-inner" id="completions-list"></div>
        </div>
    </div>

    <!-- PROJECTS SECTION -->
    <div class="projects-section">
        <div class="projects-header">
            <div class="projects-title">
                Projects
                <span class="section-count">{len(sections)} workstreams</span>
            </div>
            <div class="projects-search">
                <span class="search-icon">🔍</span>
                <input type="text" class="search-input" id="search-input" placeholder="Search projects..." autocomplete="off">
                <button class="search-clear" id="search-clear" onclick="clearSearch()">&times;</button>
            </div>
        </div>
        <div class="projects-legend">
            <div class="status-legend-item complete">
                <span class="legend-indicator"><span class="legend-dot"></span></span>
                <span>Complete</span>
            </div>
            <div class="status-legend-item in-progress">
                <span class="legend-indicator"><span class="legend-dot"></span></span>
                <span>In Progress</span>
            </div>
            <div class="status-legend-item planned">
                <span class="legend-indicator"><span class="legend-dot"></span></span>
                <span>Planned</span>
            </div>
            <div class="status-legend-item idea">
                <span class="legend-indicator"><span class="legend-dot"></span></span>
                <span>Idea</span>
            </div>
            <div class="status-legend-item blocked">
                <span class="legend-indicator"><span class="legend-dot"></span></span>
                <span>Blocked</span>
            </div>
        </div>
        <div class="projects-body">
            <!-- NO RESULTS MESSAGE -->
            <div class="no-results" id="no-results" style="display:none;">
                No sections or items match your search.
            </div>

            <!-- SECTION CARDS -->
            <div class="sections-grid" id="sections-grid">
            </div>
        </div>
    </div>

    <!-- PRIORITY SUMMARY -->
    <div class="priority-section" id="priority-section">
        <h2>Priority Roadmap</h2>
    </div>

    <!-- TIMELINE -->
    <div class="timeline-section" id="timeline-section">
        <h2>Timeline</h2>
        <div class="timeline" id="timeline"></div>
    </div>

</div>

<div class="footer">
    Generated from <a href="#">docs/FUTURE_ROADMAP.md</a> on {datetime.now().strftime('%Y-%m-%d %H:%M')} &middot; Soterix Systems
</div>

<script>
// ===== DATA =====
const sections = {sections_json};
const priorities = {priorities_json};
const timeline = {timeline_json};
const recentCompletions = {completions_json};
const velocity = {velocity_json};

// ===== RENDER RECENT COMPLETIONS =====
const completionsList = document.getElementById('completions-list');
if (recentCompletions.length > 0) {{
    let html = '<ul class="priority-list">';
    recentCompletions.forEach(c => {{
        html += `<li><strong>${{c.date}}</strong> - ${{c.text}} <span style="color:var(--text-muted);font-size:13px;">(Section ${{c.section_num}})</span></li>`;
    }});
    html += '</ul>';
    if (velocity.date_range && velocity.date_range !== 'N/A') {{
        html += `<div style="margin-top:12px;font-size:13px;color:var(--text-muted);">Tracking ${{velocity.total_with_dates}} completions from ${{velocity.date_range}}</div>`;
    }}
    completionsList.innerHTML = html;
}} else {{
    completionsList.innerHTML = '<div style="color:var(--text-muted);font-size:14px;">No completion dates tracked yet. Add (MM/DD/YYYY) to completed items.</div>';
}}

// ===== RENDER SECTIONS =====
const grid = document.getElementById('sections-grid');

sections.forEach((section, sectionIndex) => {{
    const card = document.createElement('div');
    card.className = 'section-card';
    card.dataset.sectionIndex = sectionIndex;

    // Build badges HTML with click handlers for filtering
    // Modern minimal design: indicator + count, label appears on hover
    const badgeOrder = [
        [['✅'], 'complete', 'Complete'],
        [['🔄'], 'in-progress', 'In Progress'],
        [['🔜'], 'planned', 'Planned'],
        [['💡'], 'idea', 'Ideas'],
        [['⏸️', '🚫'], 'blocked', 'Blocked'],
    ];
    let badgesHtml = '';
    badgeOrder.forEach(([icons, cls, label]) => {{
        let count = 0;
        icons.forEach(i => {{ count += (section.counts[i] || 0); }});
        if (count > 0) {{
            const iconsJson = JSON.stringify(icons).replace(/"/g, "'");
            badgesHtml += `<span class="badge ${{cls}} clickable" data-icons="${{iconsJson}}" onclick="filterSectionItems(${{sectionIndex}}, ${{JSON.stringify(icons)}}, this, event)"><span class="indicator"></span>${{count}}<span class="label">${{label}}</span></span>`;
        }}
    }});

    // Build items HTML with data-status for filtering
    // Use geometric status indicators instead of emojis
    let itemsHtml = '';
    section.items.forEach(item => {{
        const textClass = item.css_class === 'complete' ? 'item-text complete-text' : 'item-text';
        const detailSpan = item.details ? `<span class="item-detail"> - ${{item.details}}</span>` : '';
        itemsHtml += `
            <div class="item-row" data-status="${{item.status_icon}}">
                <span class="item-status ${{item.css_class}}"><span class="status-dot"></span></span>
                <span class="${{textClass}}">${{item.text}}${{detailSpan}}</span>
            </div>`;
    }});

    card.innerHTML = `
        <div class="section-header" onclick="this.parentElement.classList.toggle('open')">
            <div class="section-top-row">
                <div class="section-title">
                    <span class="section-num">${{section.number}}</span>
                    ${{section.title}}
                </div>
                <div style="display:flex;align-items:center;gap:8px;">
                    <span class="section-pct">${{section.pct}}%</span>
                    <span class="chevron">&#9660;</span>
                </div>
            </div>
            <div class="section-progress">
                <div class="section-progress-fill" style="width: ${{section.pct}}%"></div>
            </div>
            <div class="section-badges">${{badgesHtml}}</div>
        </div>
        <div class="section-detail">
            <div class="section-detail-inner">
                ${{itemsHtml || '<div style="padding:12px 0;color:#999;font-size:13px;">No tracked items in this section.</div>'}}
            </div>
        </div>`;

    grid.appendChild(card);
}});

// ===== RENDER PRIORITIES =====
const prioSection = document.getElementById('priority-section');
const tiers = {{}};
priorities.forEach(p => {{
    if (!tiers[p.tier]) tiers[p.tier] = [];
    tiers[p.tier].push(p.text);
}});

const tierMeta = {{
    'Immediate': 'immediate',
    'Short-Term': 'short-term',
    'Medium-Term': 'medium-term',
    'Long-Term': 'long-term'
}};

Object.entries(tiers).forEach(([tier, items]) => {{
    const div = document.createElement('div');
    div.className = 'priority-tier';
    const cls = tierMeta[tier] || 'planned';
    div.innerHTML = `
        <div class="tier-label ${{cls}}">${{tier}}</div>
        <ul class="priority-list">
            ${{items.map(t => `<li>${{t}}</li>`).join('')}}
        </ul>`;
    prioSection.appendChild(div);
}});

// ===== RENDER TIMELINE =====
const timelineEl = document.getElementById('timeline');
timeline.forEach(t => {{
    const item = document.createElement('div');
    item.className = 'timeline-item';
    item.innerHTML = `
        <div class="timeline-dot"></div>
        <div class="timeline-period">${{t.period}}</div>
        <div class="timeline-focus">${{t.focus}}</div>`;
    timelineEl.appendChild(item);
}});

// ===== DRILLDOWN MODAL =====
const filterMap = {{
    'complete': {{ icons: ['✅'], title: 'Completed Items', color: '#22c55e' }},
    'in-progress': {{ icons: ['🔄'], title: 'In Progress Items', color: '#127CA3' }},
    'planned': {{ icons: ['🔜', '💡'], title: 'Planned & Ideas', color: '#46A1B1' }},
    'blocked': {{ icons: ['⏸️', '🚫'], title: 'Blocked Items', color: '#ef4444' }},
    'total': {{ icons: ['✅', '🔄', '🔜', '💡', '⏸️', '🚫'], title: 'All Items', color: '#f0f0f2' }},
    'overall': {{ icons: null, title: 'Progress by Section', color: '#127CA3' }},
}};

function openDrilldown(filter) {{
    const modal = document.getElementById('drilldown-modal');
    const title = document.getElementById('drilldown-title');
    const body = document.getElementById('drilldown-body');
    const config = filterMap[filter];
    if (!config) return;

    body.innerHTML = '';

    if (filter === 'overall') {{
        // Show per-section progress breakdown
        title.innerHTML = config.title;
        let html = '';
        sections.forEach(s => {{
            const total = s.items.length;
            const complete = s.items.filter(i => i.status_icon === '✅').length;
            const inProg = s.items.filter(i => i.status_icon === '🔄').length;
            const pct = total > 0 ? Math.round((complete / total) * 100) : 0;
            html += `<div class="modal-section" style="margin-bottom:16px;">
                <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:6px;">
                    <span style="font-size:15px;font-weight:600;color:var(--text-primary);">${{s.number}}. ${{s.title}}</span>
                    <span style="font-size:15px;color:var(--text-secondary);font-weight:600;">${{pct}}% <span style="font-weight:400;font-size:13px;">(${{complete}}/${{total}})</span></span>
                </div>
                <div style="background:var(--bg-dark,#26252d);border-radius:6px;height:8px;overflow:hidden;">
                    <div style="height:100%;border-radius:6px;width:${{pct}}%;background:linear-gradient(90deg,#127CA3,#46A1B1);transition:width 0.3s;"></div>
                </div>
                <div style="font-size:13px;color:var(--text-muted);margin-top:4px;display:flex;gap:12px;align-items:center;">
                    <span style="display:flex;align-items:center;gap:4px;"><span style="width:8px;height:8px;background:#22c55e;border-radius:50%;display:inline-block;"></span> ${{complete}} complete</span>
                    <span style="display:flex;align-items:center;gap:4px;"><span style="width:8px;height:8px;background:#127CA3;border-radius:50%;display:inline-block;"></span> ${{inProg}} in progress</span>
                    <span>· ${{total}} total</span>
                </div>
            </div>`;
        }});
        body.innerHTML = html;
    }} else {{
        // Filter items by status icons
        const icons = config.icons;
        let totalCount = 0;
        let html = '';

        sections.forEach(s => {{
            const matched = s.items.filter(i => icons.includes(i.status_icon));
            if (matched.length === 0) return;
            totalCount += matched.length;

            html += `<div class="modal-section">
                <div class="modal-section-title">${{s.number}}. ${{s.title}} (${{matched.length}})</div>`;
            matched.forEach(item => {{
                const detailSpan = item.details ? `<span class="item-detail">- ${{item.details}}</span>` : '';
                html += `<div class="modal-item ${{item.css_class}}">
                    <span class="item-icon"><span class="status-dot"></span></span>
                    <span>${{item.text}}${{detailSpan}}</span>
                </div>`;
            }});
            html += `</div>`;
        }});

        title.innerHTML = `${{config.title}}<span class="modal-count">${{totalCount}} items</span>`;
        body.innerHTML = html || '<div style="padding:20px;color:var(--text-muted);text-align:center;">No items found.</div>';
    }}

    modal.classList.add('open');
    document.body.style.overflow = 'hidden';
}}

function closeDrilldown() {{
    document.getElementById('drilldown-modal').classList.remove('open');
    document.body.style.overflow = '';
}}

document.addEventListener('keydown', e => {{
    if (e.key === 'Escape') closeDrilldown();
}});

// ===== SECTION ITEM FILTERING =====
// Track active filters per section
const sectionFilters = {{}};

function filterSectionItems(sectionIndex, icons, badgeEl, event) {{
    // Stop propagation so clicking badge doesn't toggle section open/close
    event.stopPropagation();

    const card = document.querySelector(`.section-card[data-section-index="${{sectionIndex}}"]`);
    if (!card) return;

    // Auto-expand section when filtering
    card.classList.add('open');

    const items = card.querySelectorAll('.item-row');
    const badges = card.querySelectorAll('.badge.clickable');
    const badgesContainer = card.querySelector('.section-badges');

    // Check if this filter is already active (toggle off)
    const filterKey = icons.join(',');
    const isActive = sectionFilters[sectionIndex] === filterKey;

    // Remove active class from all badges in this section
    badges.forEach(b => b.classList.remove('active'));

    // Remove existing clear button if any
    const existingClear = badgesContainer.querySelector('.clear-filter');
    if (existingClear) existingClear.remove();

    if (isActive) {{
        // Toggle off - show all items
        sectionFilters[sectionIndex] = null;
        items.forEach(item => item.classList.remove('filtered-out'));
    }} else {{
        // Apply filter - show only matching items
        sectionFilters[sectionIndex] = filterKey;
        badgeEl.classList.add('active');

        items.forEach(item => {{
            const status = item.dataset.status;
            if (icons.includes(status)) {{
                item.classList.remove('filtered-out');
            }} else {{
                item.classList.add('filtered-out');
            }}
        }});

        // Add clear filter button
        const clearBtn = document.createElement('button');
        clearBtn.className = 'clear-filter';
        clearBtn.textContent = '✕ Clear';
        clearBtn.onclick = (e) => {{
            e.stopPropagation();
            clearSectionFilter(sectionIndex);
        }};
        badgesContainer.appendChild(clearBtn);
    }}
}}

function clearSectionFilter(sectionIndex) {{
    const card = document.querySelector(`.section-card[data-section-index="${{sectionIndex}}"]`);
    if (!card) return;

    sectionFilters[sectionIndex] = null;

    // Show all items
    card.querySelectorAll('.item-row').forEach(item => item.classList.remove('filtered-out'));

    // Remove active state from badges
    card.querySelectorAll('.badge.clickable').forEach(b => b.classList.remove('active'));

    // Remove clear button
    const clearBtn = card.querySelector('.clear-filter');
    if (clearBtn) clearBtn.remove();
}}

// ===== SEARCH FUNCTIONALITY =====
const searchInput = document.getElementById('search-input');
const searchClear = document.getElementById('search-clear');
const noResults = document.getElementById('no-results');

searchInput.addEventListener('input', function() {{
    const query = this.value.toLowerCase().trim();
    searchClear.classList.toggle('visible', query.length > 0);
    filterSections(query);
}});

function clearSearch() {{
    searchInput.value = '';
    searchClear.classList.remove('visible');
    filterSections('');
    searchInput.focus();
}}

function filterSections(query) {{
    const cards = document.querySelectorAll('.section-card');
    let visibleCount = 0;

    cards.forEach((card, index) => {{
        const section = sections[index];
        const titleMatch = section.title.toLowerCase().includes(query);
        const itemsMatch = section.items.some(item =>
            item.text.toLowerCase().includes(query) ||
            (item.details && item.details.toLowerCase().includes(query))
        );

        if (query === '' || titleMatch || itemsMatch) {{
            card.classList.remove('hidden');
            visibleCount++;
            // Auto-expand cards with matching items when searching
            if (query && itemsMatch && !titleMatch) {{
                card.classList.add('open');
            }}
        }} else {{
            card.classList.add('hidden');
        }}
    }});

    noResults.style.display = visibleCount === 0 && query ? 'block' : 'none';
}}

// Focus search with Ctrl+K or /
document.addEventListener('keydown', e => {{
    if ((e.ctrlKey && e.key === 'k') || (e.key === '/' && document.activeElement.tagName !== 'INPUT')) {{
        e.preventDefault();
        searchInput.focus();
        searchInput.select();
    }}
}});
</script>

</body>
</html>"""

    return html


def deploy_to_dashboards_repo(html: str, roadmap_text: str):
    """Deploy generated dashboard to soterix-internal-dashboards repo.

    Copies the dashboard HTML and roadmap source, then commits and pushes
    so the NUC can auto-pull the latest version.
    """
    import subprocess
    import shutil

    if not DEPLOY_REPO.exists():
        print(f"\n  Deploy repo not found at {DEPLOY_REPO}, skipping deploy.")
        return False

    # Ensure qa-roadmap directory exists
    DEPLOY_DASHBOARD.parent.mkdir(parents=True, exist_ok=True)

    # Write dashboard HTML
    with open(DEPLOY_DASHBOARD, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"  Copied dashboard -> {DEPLOY_DASHBOARD}")

    # Write roadmap source
    with open(DEPLOY_ROADMAP, "w", encoding="utf-8") as f:
        f.write(roadmap_text)
    print(f"  Copied roadmap   -> {DEPLOY_ROADMAP}")

    # Copy generator script and logo
    src_script = SCRIPT_DIR / "generate_dashboard.py"
    src_logo = LOGO_PATH
    dst_script = DEPLOY_REPO / "qa-roadmap" / "generate_dashboard.py"
    dst_logo = DEPLOY_REPO / "qa-roadmap" / "soterix_logo.svg"

    shutil.copy2(src_script, dst_script)
    print(f"  Copied generator -> {dst_script}")
    if src_logo.exists():
        shutil.copy2(src_logo, dst_logo)
        print(f"  Copied logo      -> {dst_logo}")

    # Git commit and push
    try:
        repo = str(DEPLOY_REPO)
        # Check if there are changes
        result = subprocess.run(
            ["git", "-C", repo, "status", "--porcelain"],
            capture_output=True, text=True
        )
        if not result.stdout.strip():
            print("  No changes to deploy.")
            return True

        subprocess.run(["git", "-C", repo, "add", "qa-roadmap/"], check=True)
        subprocess.run(
            ["git", "-C", repo, "commit", "-m", "Update QA roadmap dashboard"],
            check=True, capture_output=True
        )
        subprocess.run(["git", "-C", repo, "push"], check=True, capture_output=True)
        print("  Pushed to soterix-internal-dashboards repo.")
        return True
    except subprocess.CalledProcessError as e:
        print(f"  Git deploy failed: {e}")
        return False


def main():
    """Main entry point."""
    print("Reading roadmap...")
    text = read_roadmap(ROADMAP_PATH)

    print("Reading logo...")
    if LOGO_PNG_PATH.exists():
        logo_html = read_logo_png(LOGO_PNG_PATH)
        print(f"  Using horizontal PNG logo from OneDrive")
    else:
        logo_html = read_logo(LOGO_PATH)
        # Make SVG logo white for dark header
        logo_html = logo_html.replace('fill="#157ca4"', 'fill="#ffffff"')
        logo_html = logo_html.replace('fill="#bcbdbf"', 'fill="rgba(255,255,255,0.7)"')
        print(f"  Falling back to SVG wordmark")

    # Auto-update "Last Updated" date in the roadmap file
    today = datetime.now().strftime("%Y-%m-%d")
    updated_text = re.sub(
        r"(\*\*Last Updated:\*\*)\s*.+",
        rf"\1 {today}",
        text,
        count=1,
    )
    if updated_text != text:
        with open(ROADMAP_PATH, "w", encoding="utf-8") as f:
            f.write(updated_text)
        text = updated_text
        print(f"  Updated 'Last Updated' to {today}")

    print("Extracting metadata...")
    metadata = extract_metadata(text)
    metadata["last_updated"] = today  # Always use current date

    print("Parsing sections...")
    sections = parse_sections(text)
    for s in sections:
        print(f"  Section {s['number']}: {s['title']} - {s['total']} items, {s['pct']}% complete")

    print("Extracting priorities...")
    priorities = extract_priorities(text)
    print(f"  {len(priorities)} priority items found")

    print("Extracting timeline...")
    timeline = extract_timeline(text)
    print(f"  {len(timeline)} timeline entries found")

    print("Extracting completions with dates...")
    completions = extract_completions_with_dates(sections)
    print(f"  {len(completions)} completions with dates found")

    print("Calculating velocity...")
    velocity = calculate_velocity(completions)
    print(f"  Weekly average: {velocity.get('weekly_avg', 0)} items/week")

    print("Loading Good Times font...")
    good_times_b64 = ""
    if GOOD_TIMES_FONT_PATH.exists():
        good_times_b64 = read_font_base64(GOOD_TIMES_FONT_PATH)
        print(f"  Embedded Good Times font ({len(good_times_b64)} bytes)")
    else:
        print("  Warning: Good Times font not found, using fallback")

    print("Generating HTML...")
    html = generate_html(sections, metadata, priorities, timeline, logo_html, completions, velocity, good_times_b64)

    print(f"Writing to {OUTPUT_PATH}...")
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        f.write(html)

    print(f"\nDashboard generated: {OUTPUT_PATH}")
    print(f"  Total sections: {len(sections)}")
    total = sum(s['total'] for s in sections)
    complete = sum(s['completed'] for s in sections)
    print(f"  Total items: {total}")
    print(f"  Complete: {complete}")
    print(f"  Overall: {round((complete/total)*100) if total else 0}%")

    # Deploy to soterix-internal-dashboards repo (NUC auto-pulls from GitHub)
    print("\nDeploying to dashboard server repo...")
    deploy_to_dashboards_repo(html, text)


if __name__ == "__main__":
    main()
