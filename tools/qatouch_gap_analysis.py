#!/usr/bin/env python3
"""
QA Touch Gap Analysis Tool
===========================
Cross-references three data sources to identify testing coverage gaps:
  A) Feature Inventory  - live product features (from Chrome walkthrough)
  B) QA Touch Cases     - manual test cases (3,011 from snapshot)
  C) Playwright Tests   - automated tests (364 from test files)

Commands:
  inventory   - Load and summarize the feature inventory
  snapshot    - Analyze QA Touch snapshot by product area
  playwright  - Analyze Playwright test coverage by module
  matrix      - Generate full coverage matrix (A vs B vs C)
  gaps        - Show gaps: features without coverage
  report      - Generate comprehensive gap report (HTML + JSON)
  vet-smoke   - Vet current SMOKE tag selections against feature criticality
  vet-sanity  - Vet current SANITY tag selections against feature criticality
  regression  - Recommend REGRESSION candidates based on gap analysis

Usage:
  python tools/qatouch_gap_analysis.py snapshot
  python tools/qatouch_gap_analysis.py matrix
  python tools/qatouch_gap_analysis.py gaps --min-risk medium
  python tools/qatouch_gap_analysis.py report
  python tools/qatouch_gap_analysis.py vet-smoke
  python tools/qatouch_gap_analysis.py regression --target 500
"""

import sys
import os
import json
import re
import argparse
from pathlib import Path
from collections import defaultdict
from datetime import datetime

# Handle Windows encoding
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SCRIPT_DIR = Path(__file__).resolve().parent
PROJECT_ROOT = SCRIPT_DIR.parent
CONFIG_DIR = PROJECT_ROOT / "config"
SNAPSHOT_DIR = CONFIG_DIR / "qatouch_snapshots"
FEATURE_INVENTORY_PATH = CONFIG_DIR / "feature_inventory.json"
CASE_MAPPING_PATH = CONFIG_DIR / "qatouch_case_mapping.json"
TESTS_DIR = PROJECT_ROOT / "tests"
REPORT_DIR = CONFIG_DIR / "audit_reports"

# ── Product Area Mapping ─────────────────────────────────────────────
# Maps QA Touch module names to top-level product areas (NexaiQ nav structure)
# This is the canonical mapping between QA Touch's 470 sub-modules and
# the actual product navigation hierarchy.

PRODUCT_AREAS = {
    "Views": {
        "description": "Live camera monitoring, grid layouts, saved views",
        "nav_path": "/views",
        "keywords": ["view", "grid", "tile", "canvas", "camera preview", "camera drag",
                      "camera replacement", "camera duplication", "camera favorite",
                      "camera fullscreen", "camera selection", "camera sorting",
                      "camera state", "camera status", "camera list", "camera details",
                      "default landing", "left navigation - views", "my views",
                      "empty grid", "expanded view", "layout", "landing navigation",
                      "live playback", "live transition", "hover controls",
                      "bottom toolbar", "page header", "view header", "view tab",
                      "view mode", "view layout", "view toggle", "locations",
                      "devices tab", "google maps", "offline camera", "overlays",
                      "remove video", "reset view", "dashboard preview"],
        "risk": "high",
    },
    "Playback": {
        "description": "Archive playback, playback controls, speed, timeline",
        "nav_path": "/views (archive mode)",
        "keywords": ["playback", "archive", "playback controls", "playback speed",
                      "playback stability", "playback continuity", "playback auto-timeout",
                      "fullscreen playback", "fullscreen controls", "fullscreen entry",
                      "fullscreen exit", "event playback", "snapshot", "video metadata",
                      "video playback"],
        "risk": "high",
    },
    "PTZ": {
        "description": "Pan-Tilt-Zoom camera controls, presets, tours",
        "nav_path": "/views (PTZ mode)",
        "keywords": ["ptz"],
        "risk": "medium",
    },
    "Bookmarks": {
        "description": "Bookmark creation, clip bookmarks, panel",
        "nav_path": "/views (bookmarks)",
        "keywords": ["bookmark"],
        "risk": "medium",
    },
    "Camera Sequences": {
        "description": "Camera sequence creation, timing, playback",
        "nav_path": "/views (sequences)",
        "keywords": ["sequence", "camera sequence"],
        "risk": "medium",
    },
    "Search": {
        "description": "Global search, forensic search, category filters, zone/line drawing",
        "nav_path": "/search",
        "keywords": ["search", "category", "person", "vehicle", "zone", "line",
                      "duration", "date picker", "time picker", "time range",
                      "custom date", "more filters", "search result", "search reset",
                      "search filter", "search landing", "clip selection",
                      "in-camera search", "widget search"],
        "risk": "high",
    },
    "Events": {
        "description": "Event wall, event detection, filtering, pinning, export",
        "nav_path": "/events",
        "keywords": ["event", "event wall", "event card", "event filter", "event panel",
                      "event export", "event vault", "event interaction",
                      "event timestamp", "pin", "pinned clip", "acknowledgement",
                      "aggression", "fire", "smoke", "intrusion", "loitering",
                      "occupancy", "entry-exit", "workplace safety",
                      "landing page controls", "landing page events"],
        "risk": "high",
    },
    "Insights": {
        "description": "Dashboards, widgets, analytics, reports",
        "nav_path": "/insights",
        "keywords": ["insight", "dashboard", "dashlet", "widget", "report",
                      "create dashboard", "create widget", "preset",
                      "my dashboard", "graph type", "widget card", "widget data",
                      "widget name", "widget panel", "widget placement",
                      "widget removal", "widget section", "widget selection",
                      "widget size", "full width", "half width", "save action",
                      "discard", "scrolling dashboard", "tabs insight",
                      "left navigation - insight", "session handling dashboard"],
        "risk": "medium",
    },
    "Media": {
        "description": "Media vault, clip management, folders, export, sharing",
        "nav_path": "/media",
        "keywords": ["media", "vault", "clip", "folder", "thumbnail", "group clip",
                      "bulk action", "export clip", "export download", "move to folder",
                      "share link", "share media", "create link", "sorting",
                      "media listing", "media tab", "selection", "delete",
                      "add to vault", "vault folder", "vault navigation",
                      "vault retention", "vault storage", "vault empty"],
        "risk": "medium",
    },
    "Maps": {
        "description": "Site maps, camera overlays, heat maps, static maps",
        "nav_path": "/maps",
        "keywords": ["map", "heat map", "map creation", "map deletion", "map editing",
                      "map list", "map navigation", "maps carousel", "maps widget",
                      "static map", "map configuration"],
        "risk": "medium",
    },
    "Notifications": {
        "description": "Notification panel, mute controls, popup alerts",
        "nav_path": "Global (bell icon)",
        "keywords": ["notification", "mute", "volume", "popup", "read unread",
                      "notification icon", "notification ordering", "notification panel"],
        "risk": "medium",
    },
    "Chats": {
        "description": "One-to-one chat, group chat, messaging",
        "nav_path": "/chats",
        "keywords": ["chat", "group chat", "one to one", "messaging",
                      "chat access", "chat list", "chat ui", "error handling chat"],
        "risk": "low",
    },
    "Admin - Users": {
        "description": "User management, roles, permissions",
        "nav_path": "/admin/users",
        "keywords": ["user", "add new user", "add user via upload", "delete user",
                      "edit user", "search user", "users widget", "users landing",
                      "users interaction", "users roles", "view toggle users",
                      "user list", "stability admin user"],
        "risk": "high",
    },
    "Admin - Roles & Permissions": {
        "description": "Role management, permission assignment, RBAC",
        "nav_path": "/admin/roles",
        "keywords": ["role", "permission", "role assignment", "role card",
                      "role dropdown", "role filter", "role permission",
                      "role selection", "role switching", "roles cancel",
                      "roles concurrency", "roles dependency", "roles error",
                      "roles persistence", "roles refresh", "roles save",
                      "roles tab", "roles ui", "roles validation",
                      "permission hierarchy", "permissions panel",
                      "group permissions", "global access"],
        "risk": "high",
    },
    "Admin - Rules": {
        "description": "Automation rules, rule creation, notifications",
        "nav_path": "/admin/rules",
        "keywords": ["rule", "add new rule", "all rules", "rules delete",
                      "rules edit", "rules module", "rules notification",
                      "rules widget"],
        "risk": "medium",
    },
    "Admin - Sites": {
        "description": "Site management, streaming, camera configuration",
        "nav_path": "/admin/sites",
        "keywords": ["site", "site action", "site detail", "site name",
                      "sites navigation", "sites rollback", "sites streaming",
                      "sites widget", "scrolling sites", "search sites",
                      "select site dropdown", "camera list site",
                      "camera image settings", "camera audio source",
                      "audio settings", "reboot"],
        "risk": "high",
    },
    "Admin - General": {
        "description": "General settings, storage, system logs, deployment",
        "nav_path": "/admin/general",
        "keywords": ["general", "settings", "storage", "system log",
                      "deployment", "configuration", "licenses",
                      "channels", "webhooks", "landing page admin"],
        "risk": "medium",
    },
    "Admin - Audit Trail": {
        "description": "User activity logs, LPR audit",
        "nav_path": "/admin/audit-trail",
        "keywords": ["audit trail"],
        "risk": "medium",
    },
    "Admin - LPR": {
        "description": "License Plate Recognition management",
        "nav_path": "/admin/lpr",
        "keywords": ["lpr", "license plate", "list license plate",
                      "add license plate", "landing page lpr",
                      "lpr landing", "navigation lpr", "performance lpr",
                      "permissions lpr", "session handling lpr",
                      "session management lpr"],
        "risk": "medium",
    },
    "Licenses": {
        "description": "License management, assignment, feature licensing",
        "nav_path": "/admin/licenses",
        "keywords": ["license"],
        "risk": "medium",
    },
    "Login & Auth": {
        "description": "Login, logout, MFA, session management, password reset",
        "nav_path": "/auth/login",
        "keywords": ["login", "logout", "authentication", "forgot password",
                      "password reset", "multi-factor", "multi session",
                      "re-login", "session", "security injection",
                      "security token", "session timeout", "session stability",
                      "session security", "session management login",
                      "validation login", "error handling login",
                      "accessibility login", "stability login"],
        "risk": "critical",
    },
    "Header & Navigation": {
        "description": "Top header, navigation menu, browser navigation",
        "nav_path": "Global",
        "keywords": ["header", "header icons", "header utilities",
                      "navigation menu", "navigation entry",
                      "navigation highlight", "browser navigation",
                      "left navigation", "page header", "page refresh"],
        "risk": "medium",
    },
    "Cross-Cutting": {
        "description": "UI consistency, accessibility, error handling, tooltips, UX",
        "nav_path": "Global",
        "keywords": ["accessibility", "tooltip", "ui consistency", "ui feedback",
                      "ui interaction", "ui resilience", "ui stability",
                      "ui state", "ux", "usability", "error handling",
                      "edge case", "empty state", "page rendering",
                      "page scrolling", "persistence", "rename", "save validation",
                      "system stability", "concurrency", "rollback",
                      "overall ui", "group ui", "utilities"],
        "risk": "low",
    },
    "Sharing & Export": {
        "description": "Share links, export clips, review pinned clips",
        "nav_path": "Multiple pages",
        "keywords": ["share", "export", "create link", "review pinned",
                      "export video modal", "export notification"],
        "risk": "medium",
    },
}

# Risk severity ordering
RISK_ORDER = {"critical": 4, "high": 3, "medium": 2, "low": 1}


def classify_module(module_name: str) -> str:
    """Classify a QA Touch module name into a product area."""
    mod_lower = module_name.lower()

    # Score each area by keyword matches
    best_area = "Unclassified"
    best_score = 0

    for area_name, area_info in PRODUCT_AREAS.items():
        score = 0
        for kw in area_info["keywords"]:
            if kw in mod_lower:
                # Longer keyword matches get higher score (more specific)
                score += len(kw)
        if score > best_score:
            best_score = score
            best_area = area_name

    return best_area


# ── Data Loaders ─────────────────────────────────────────────────────

def load_latest_snapshot() -> dict:
    """Load the most recent QA Touch snapshot."""
    snapshots = sorted(SNAPSHOT_DIR.glob("snapshot_*.json"))
    if not snapshots:
        print("ERROR: No snapshots found in", SNAPSHOT_DIR)
        sys.exit(1)
    latest = snapshots[-1]
    print(f"Loading snapshot: {latest.name}")
    with open(latest, encoding="utf-8") as f:
        return json.load(f)


def load_case_mapping() -> dict:
    """Load Playwright -> QA Touch case mapping."""
    with open(CASE_MAPPING_PATH, encoding="utf-8") as f:
        return json.load(f)


def load_feature_inventory() -> dict | None:
    """Load Chrome-captured feature inventory, if it exists."""
    if FEATURE_INVENTORY_PATH.exists():
        with open(FEATURE_INVENTORY_PATH, encoding="utf-8") as f:
            return json.load(f)
    return None


def discover_playwright_tests() -> dict:
    """Scan test files to build Playwright test inventory."""
    test_map = defaultdict(lambda: {"files": [], "tests": [], "count": 0})

    for test_file in sorted(TESTS_DIR.rglob("test_*.py")):
        rel_path = test_file.relative_to(PROJECT_ROOT)
        # Determine module from directory structure
        parts = rel_path.parts  # e.g., ('tests', 'ui', 'admin', 'test_admin_users.py')
        if len(parts) >= 3:
            module = parts[2] if parts[1] == "ui" else parts[1]  # 'admin' or 'smoke'
        else:
            module = "other"

        # Count test functions (both top-level and class methods)
        content = test_file.read_text(encoding="utf-8", errors="replace")
        test_funcs = re.findall(r"^\s*def (test_\w+)", content, re.MULTILINE)

        test_map[module]["files"].append(str(rel_path))
        test_map[module]["tests"].extend(test_funcs)
        test_map[module]["count"] += len(test_funcs)

    return dict(test_map)


# ── Analysis Functions ───────────────────────────────────────────────

def build_coverage_matrix(snapshot: dict, pw_tests: dict, case_mapping: dict,
                          feature_inv: dict | None = None) -> dict:
    """Build the three-layer coverage matrix."""
    matrix = {}

    # Initialize from product areas
    for area_name, area_info in PRODUCT_AREAS.items():
        matrix[area_name] = {
            "description": area_info["description"],
            "nav_path": area_info["nav_path"],
            "risk": area_info["risk"],
            "qatouch_cases": [],
            "qatouch_modules": set(),
            "playwright_tests": [],
            "playwright_modules": set(),
            "features": [],  # From Chrome inventory
            "case_count": 0,
            "test_count": 0,
            "feature_count": 0,
        }

    # Also track unclassified
    matrix["Unclassified"] = {
        "description": "Modules not yet mapped to a product area",
        "nav_path": "Unknown",
        "risk": "low",
        "qatouch_cases": [],
        "qatouch_modules": set(),
        "playwright_tests": [],
        "playwright_modules": set(),
        "features": [],
        "case_count": 0,
        "test_count": 0,
        "feature_count": 0,
    }

    # Layer B: QA Touch cases
    for case in snapshot.get("cases", []):
        module = case.get("module name", "Unknown")
        area = classify_module(module)
        matrix[area]["qatouch_cases"].append({
            "key": case.get("case_key"),
            "title": case.get("case_title"),
            "module": module,
            "priority": case.get("Priority", ""),
            "type": case.get("Type", ""),
            "tags": case.get("NewTags", ""),
        })
        matrix[area]["qatouch_modules"].add(module)
        matrix[area]["case_count"] += 1

    # Layer C: Playwright tests
    # Map Playwright modules to product areas
    PW_AREA_MAP = {
        "admin": ["Admin - Users", "Admin - Roles & Permissions", "Admin - Rules",
                   "Admin - Sites", "Admin - General", "Admin - Audit Trail"],
        "login": ["Login & Auth"],
        "views": ["Views", "Playback"],
        "events": ["Events"],
        "search": ["Search"],
        "insights": ["Insights"],
        "media": ["Media"],
        "maps": ["Maps"],
        "notifications": ["Notifications"],
        "chats": ["Chats"],
        "sequences": ["Camera Sequences"],
        "licenses": ["Licenses"],
        "smoke": [],  # API tests span multiple areas
    }

    for pw_module, pw_info in pw_tests.items():
        target_areas = PW_AREA_MAP.get(pw_module, ["Unclassified"])
        if not target_areas:
            continue
        # Distribute tests to first matching area (or split for admin)
        for test_name in pw_info["tests"]:
            test_lower = test_name.lower()
            placed = False
            for area in target_areas:
                if area in matrix:
                    # For admin, try to place in the right sub-area
                    if pw_module == "admin":
                        if any(kw in test_lower for kw in ["user", "role", "permission"]):
                            area = "Admin - Users"
                        elif any(kw in test_lower for kw in ["rule", "mute"]):
                            area = "Admin - Rules"
                        elif any(kw in test_lower for kw in ["site", "camera"]):
                            area = "Admin - Sites"
                        elif any(kw in test_lower for kw in ["audit", "trail"]):
                            area = "Admin - Audit Trail"
                        elif any(kw in test_lower for kw in ["event_wall"]):
                            area = "Events"
                        else:
                            area = "Admin - General"
                    matrix[area]["playwright_tests"].append(test_name)
                    matrix[area]["playwright_modules"].add(pw_module)
                    matrix[area]["test_count"] += 1
                    placed = True
                    break
            if not placed:
                matrix["Unclassified"]["playwright_tests"].append(test_name)
                matrix["Unclassified"]["test_count"] += 1

    # Layer A: Feature inventory (if available)
    if feature_inv and "areas" in feature_inv:
        for area_entry in feature_inv["areas"]:
            area_name = area_entry.get("product_area", "Unclassified")
            if area_name in matrix:
                features = area_entry.get("features", [])
                matrix[area_name]["features"] = features
                matrix[area_name]["feature_count"] = len(features)

    # Convert sets to lists for JSON serialization
    for area in matrix:
        matrix[area]["qatouch_modules"] = sorted(matrix[area]["qatouch_modules"])
        matrix[area]["playwright_modules"] = sorted(matrix[area]["playwright_modules"])

    return matrix


def compute_gap_scores(matrix: dict) -> list[dict]:
    """Compute gap scores for each product area."""
    gaps = []
    total_cases = sum(m["case_count"] for m in matrix.values())
    total_tests = sum(m["test_count"] for m in matrix.values())

    for area_name, area_data in matrix.items():
        cases = area_data["case_count"]
        tests = area_data["test_count"]
        features = area_data["feature_count"]
        risk = area_data["risk"]
        risk_weight = RISK_ORDER.get(risk, 1)

        # Automation ratio (what % of QA Touch cases have automation)
        auto_ratio = tests / cases if cases > 0 else 0

        # Gap score: higher = bigger gap
        # Factors: risk level, case volume, low automation ratio
        gap_score = risk_weight * (1 - auto_ratio) * (cases / max(total_cases, 1)) * 100

        # Coverage status
        if cases == 0 and features > 0:
            status = "RED_NO_CASES"
        elif cases > 0 and tests == 0:
            status = "YELLOW_NO_AUTOMATION"
        elif cases > 0 and auto_ratio < 0.05:
            status = "YELLOW_LOW_AUTOMATION"
        elif cases > 0 and auto_ratio >= 0.05:
            status = "GREEN"
        else:
            status = "GREY_NO_DATA"

        gaps.append({
            "area": area_name,
            "risk": risk,
            "risk_weight": risk_weight,
            "case_count": cases,
            "test_count": tests,
            "feature_count": features,
            "auto_ratio": round(auto_ratio, 4),
            "gap_score": round(gap_score, 2),
            "status": status,
            "modules": area_data["qatouch_modules"],
            "description": area_data["description"],
        })

    gaps.sort(key=lambda x: x["gap_score"], reverse=True)
    return gaps


def get_tagged_cases(snapshot: dict) -> dict:
    """Extract cases by tag from snapshot."""
    tags = {"smoke": [], "sanity": [], "automated": [], "regression": [], "untagged": []}
    for case in snapshot.get("cases", []):
        case_tags = (case.get("NewTags") or "").lower()
        if not case_tags:
            tags["untagged"].append(case)
        else:
            if "smoke" in case_tags:
                tags["smoke"].append(case)
            if "sanity" in case_tags:
                tags["sanity"].append(case)
            if "automated" in case_tags:
                tags["automated"].append(case)
            if "regression" in case_tags:
                tags["regression"].append(case)
    return tags


# ── Command Handlers ─────────────────────────────────────────────────

def cmd_snapshot(args):
    """Analyze QA Touch snapshot by product area."""
    snapshot = load_latest_snapshot()
    cases = snapshot.get("cases", [])
    print(f"\nTotal cases: {len(cases)}")

    # Group by product area
    area_counts = defaultdict(lambda: {"count": 0, "modules": set()})
    for case in cases:
        module = case.get("module name", "Unknown")
        area = classify_module(module)
        area_counts[area]["count"] += 1
        area_counts[area]["modules"].add(module)

    print(f"\n{'Product Area':<30} {'Cases':>6} {'Modules':>8} {'Risk':<10}")
    print("-" * 60)
    for area in sorted(area_counts, key=lambda a: area_counts[a]["count"], reverse=True):
        info = area_counts[area]
        risk = PRODUCT_AREAS.get(area, {}).get("risk", "?")
        print(f"{area:<30} {info['count']:>6} {len(info['modules']):>8} {risk:<10}")

    print(f"\n{'TOTAL':<30} {len(cases):>6}")


def cmd_playwright(args):
    """Analyze Playwright test coverage."""
    pw = discover_playwright_tests()
    total = sum(m["count"] for m in pw.values())

    print(f"\nTotal Playwright tests: {total}")
    print(f"\n{'Module':<20} {'Tests':>6} {'Files':>6}")
    print("-" * 40)
    for mod in sorted(pw, key=lambda m: pw[m]["count"], reverse=True):
        info = pw[mod]
        print(f"{mod:<20} {info['count']:>6} {len(info['files']):>6}")


def cmd_matrix(args):
    """Generate full coverage matrix."""
    snapshot = load_latest_snapshot()
    pw_tests = discover_playwright_tests()
    mapping = load_case_mapping()
    feature_inv = load_feature_inventory()

    matrix = build_coverage_matrix(snapshot, pw_tests, mapping, feature_inv)
    gaps = compute_gap_scores(matrix)

    # Status icons
    STATUS_ICON = {
        "RED_NO_CASES": "!!",
        "YELLOW_NO_AUTOMATION": "--",
        "YELLOW_LOW_AUTOMATION": "~",
        "GREEN": "OK",
        "GREY_NO_DATA": "??",
    }

    print(f"\n{'Area':<30} {'Risk':<9} {'Cases':>6} {'PW Tests':>9} {'Auto%':>6} {'Gap':>6} {'Status'}")
    print("-" * 85)
    for g in gaps:
        icon = STATUS_ICON.get(g["status"], "?")
        auto_pct = f"{g['auto_ratio']*100:.1f}%" if g["case_count"] > 0 else "N/A"
        print(f"{g['area']:<30} {g['risk']:<9} {g['case_count']:>6} {g['test_count']:>9} {auto_pct:>6} {g['gap_score']:>6.1f} [{icon}]")

    total_cases = sum(g["case_count"] for g in gaps)
    total_tests = sum(g["test_count"] for g in gaps)
    overall_ratio = total_tests / total_cases * 100 if total_cases else 0
    print(f"\n{'TOTALS':<30} {'':9} {total_cases:>6} {total_tests:>9} {overall_ratio:>5.1f}%")

    has_features = any(g["feature_count"] > 0 for g in gaps)
    if not has_features:
        print("\nNOTE: Feature inventory not loaded. Run Chrome walkthrough to populate config/feature_inventory.json")
        print("      This will enable RED_NO_CASES detection (features with zero test coverage).")

    # Save matrix JSON
    output_path = REPORT_DIR / f"gap_matrix_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump({"generated": datetime.now().isoformat(), "gaps": gaps, "matrix": {
            k: {kk: vv for kk, vv in v.items() if kk not in ("qatouch_cases", "playwright_tests")}
            for k, v in matrix.items()
        }}, f, indent=2, default=str)
    print(f"\nMatrix saved: {output_path.name}")


def cmd_gaps(args):
    """Show coverage gaps, optionally filtered by risk."""
    snapshot = load_latest_snapshot()
    pw_tests = discover_playwright_tests()
    mapping = load_case_mapping()
    feature_inv = load_feature_inventory()

    matrix = build_coverage_matrix(snapshot, pw_tests, mapping, feature_inv)
    gaps = compute_gap_scores(matrix)

    min_risk = RISK_ORDER.get(args.min_risk, 0) if args.min_risk else 0

    print(f"\n=== COVERAGE GAPS (min risk: {args.min_risk or 'all'}) ===\n")
    for g in gaps:
        if g["risk_weight"] < min_risk:
            continue
        if g["status"] in ("GREEN", "GREY_NO_DATA"):
            continue

        print(f"  [{g['risk'].upper()}] {g['area']}")
        print(f"    QA Touch cases: {g['case_count']} | Playwright tests: {g['test_count']} | Auto: {g['auto_ratio']*100:.1f}%")
        print(f"    Status: {g['status']} | Gap Score: {g['gap_score']}")
        if g["modules"]:
            print(f"    Modules ({len(g['modules'])}): {', '.join(g['modules'][:5])}{'...' if len(g['modules']) > 5 else ''}")
        print()


def cmd_vet_smoke(args):
    """Vet current SMOKE tagged cases against gap analysis."""
    snapshot = load_latest_snapshot()
    pw_tests = discover_playwright_tests()
    mapping = load_case_mapping()

    matrix = build_coverage_matrix(snapshot, pw_tests, mapping)
    gaps = compute_gap_scores(matrix)
    tagged = get_tagged_cases(snapshot)

    smoke_cases = tagged["smoke"]
    print(f"\n=== SMOKE TAG AUDIT ({len(smoke_cases)} cases) ===\n")

    # Group smoke cases by area
    smoke_by_area = defaultdict(list)
    for case in smoke_cases:
        area = classify_module(case.get("module name", ""))
        smoke_by_area[area].append(case)

    # Compare against risk areas
    critical_areas = [g for g in gaps if g["risk"] in ("critical", "high")]

    print(f"{'Area':<30} {'Risk':<9} {'Total Cases':>11} {'SMOKE Tagged':>12} {'Coverage':>8}")
    print("-" * 75)
    for g in sorted(critical_areas, key=lambda x: x["risk_weight"], reverse=True):
        smoke_count = len(smoke_by_area.get(g["area"], []))
        pct = f"{smoke_count/g['case_count']*100:.1f}%" if g["case_count"] > 0 else "N/A"
        flag = " *** MISSING" if smoke_count == 0 and g["case_count"] > 0 else ""
        print(f"{g['area']:<30} {g['risk']:<9} {g['case_count']:>11} {smoke_count:>12} {pct:>8}{flag}")

    # Show areas with smoke tags but low risk
    low_risk_smoke = {a: cases for a, cases in smoke_by_area.items()
                      if PRODUCT_AREAS.get(a, {}).get("risk", "low") == "low"}
    if low_risk_smoke:
        print(f"\nNOTE: {sum(len(c) for c in low_risk_smoke.values())} SMOKE cases are in LOW-risk areas:")
        for area, cases in low_risk_smoke.items():
            print(f"  {area}: {len(cases)} cases")

    # Recommendations
    missing_critical = [g["area"] for g in critical_areas
                        if len(smoke_by_area.get(g["area"], [])) == 0 and g["case_count"] > 0]
    if missing_critical:
        print(f"\nRECOMMENDATION: Add SMOKE cases for these critical/high-risk areas:")
        for area in missing_critical:
            print(f"  - {area}")


def cmd_vet_sanity(args):
    """Vet current SANITY tagged cases against gap analysis."""
    snapshot = load_latest_snapshot()
    pw_tests = discover_playwright_tests()
    mapping = load_case_mapping()

    matrix = build_coverage_matrix(snapshot, pw_tests, mapping)
    gaps = compute_gap_scores(matrix)
    tagged = get_tagged_cases(snapshot)

    sanity_cases = tagged["sanity"]
    print(f"\n=== SANITY TAG AUDIT ({len(sanity_cases)} cases) ===\n")

    # Note: The snapshot only shows 18 with sanity tag, but the SANITY run has 221 cases
    # This discrepancy likely means many sanity cases are added to the run directly, not tagged
    print("NOTE: Snapshot shows {} tagged 'sanity' but SANITY run (zvXPw) has 221 cases.".format(len(sanity_cases)))
    print("      Cases may be in the run without the tag. Cross-reference with QA Touch run data.\n")

    sanity_by_area = defaultdict(list)
    for case in sanity_cases:
        area = classify_module(case.get("module name", ""))
        sanity_by_area[area].append(case)

    all_areas = [g for g in gaps if g["case_count"] > 0]
    print(f"{'Area':<30} {'Risk':<9} {'Total Cases':>11} {'SANITY Tagged':>13} {'Coverage':>8}")
    print("-" * 76)
    for g in sorted(all_areas, key=lambda x: (x["risk_weight"], x["case_count"]), reverse=True):
        sanity_count = len(sanity_by_area.get(g["area"], []))
        pct = f"{sanity_count/g['case_count']*100:.1f}%" if g["case_count"] > 0 else "N/A"
        print(f"{g['area']:<30} {g['risk']:<9} {g['case_count']:>11} {sanity_count:>13} {pct:>8}")


def cmd_regression(args):
    """Recommend REGRESSION candidates based on gap analysis."""
    target = args.target or 500
    snapshot = load_latest_snapshot()
    pw_tests = discover_playwright_tests()
    mapping = load_case_mapping()

    matrix = build_coverage_matrix(snapshot, pw_tests, mapping)
    gaps = compute_gap_scores(matrix)
    tagged = get_tagged_cases(snapshot)

    # Already tagged cases (don't double-tag)
    already_tagged_keys = set()
    for tag_name in ("smoke", "sanity", "regression"):
        for case in tagged[tag_name]:
            already_tagged_keys.add(case.get("case_key"))

    print(f"\n=== REGRESSION CANDIDATE SELECTION (target: ~{target} cases) ===\n")
    print(f"Already tagged (smoke/sanity/regression): {len(already_tagged_keys)} cases\n")

    # Collect untagged cases per area, scored within each area
    area_candidates = defaultdict(list)
    for area_name, area_data in matrix.items():
        risk_weight = RISK_ORDER.get(area_data["risk"], 1)
        for case in area_data["qatouch_cases"]:
            if case["key"] in already_tagged_keys:
                continue

            priority_score = {"Critical": 4, "High": 3, "Medium": 2, "Low": 1}.get(
                case.get("priority", ""), 1)
            type_score = {"Functional": 3, "Acceptance": 3, "Integration": 2,
                          "Regression": 3, "Exploratory": 1}.get(case.get("type", ""), 1)

            score = risk_weight * 3 + priority_score * 2 + type_score
            area_candidates[area_name].append({
                "key": case["key"],
                "title": case["title"],
                "module": case["module"],
                "area": area_name,
                "risk": area_data["risk"],
                "priority": case.get("priority", ""),
                "type": case.get("type", ""),
                "score": score,
            })

    # Sort within each area by score
    for area in area_candidates:
        area_candidates[area].sort(key=lambda x: x["score"], reverse=True)

    # Proportional allocation: each area gets target * (area_weight / total_weight)
    # Weight = case_count * risk_weight (so high-risk areas with many cases get more)
    area_weights = {}
    for area_name, cases in area_candidates.items():
        risk = matrix[area_name]["risk"]
        risk_weight = RISK_ORDER.get(risk, 1)
        area_weights[area_name] = len(cases) * risk_weight

    total_weight = sum(area_weights.values()) or 1

    # Allocate slots per area, minimum 2 per area with candidates
    area_slots = {}
    remaining = target
    for area_name, weight in area_weights.items():
        raw_slots = int(target * weight / total_weight)
        slots = max(2, min(raw_slots, len(area_candidates[area_name])))
        area_slots[area_name] = slots

    # Adjust to hit target
    total_allocated = sum(area_slots.values())
    if total_allocated < target:
        # Add more to highest-weight areas
        for area_name in sorted(area_weights, key=lambda a: area_weights[a], reverse=True):
            if total_allocated >= target:
                break
            available = len(area_candidates[area_name]) - area_slots[area_name]
            add = min(available, target - total_allocated)
            area_slots[area_name] += add
            total_allocated += add
    elif total_allocated > target:
        # Trim from lowest-weight areas
        for area_name in sorted(area_weights, key=lambda a: area_weights[a]):
            if total_allocated <= target:
                break
            trim = min(area_slots[area_name] - 2, total_allocated - target)
            if trim > 0:
                area_slots[area_name] -= trim
                total_allocated -= trim

    # Select top N from each area
    selected = []
    area_summary = {}
    for area_name, slots in area_slots.items():
        picked = area_candidates[area_name][:slots]
        selected.extend(picked)
        area_summary[area_name] = len(picked)

    candidates = []
    for cases in area_candidates.values():
        candidates.extend(cases)

    print(f"Candidates available: {len(candidates)} (untagged)")
    print(f"Selected: {len(selected)} (top by score)\n")

    print(f"{'Area':<30} {'Selected':>8} {'Risk':<10}")
    print("-" * 52)
    for area in sorted(area_summary, key=lambda a: area_summary[a], reverse=True):
        risk = PRODUCT_AREAS.get(area, {}).get("risk", "?")
        print(f"{area:<30} {area_summary[area]:>8} {risk:<10}")

    print(f"\n{'TOTAL':<30} {len(selected):>8}")

    # Save candidate list
    output_path = REPORT_DIR / f"regression_candidates_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump({
            "generated": datetime.now().isoformat(),
            "target": target,
            "total_candidates": len(candidates),
            "selected_count": len(selected),
            "already_tagged": len(already_tagged_keys),
            "area_summary": dict(area_summary),
            "candidates": selected,
        }, f, indent=2)
    print(f"\nCandidates saved: {output_path.name}")
    print(f"Review the file, then use qatouch_api_mode_update.py pattern to apply tags via API.")


def cmd_inventory(args):
    """Load and display feature inventory status."""
    inv = load_feature_inventory()
    if not inv:
        print(f"\nFeature inventory not found at: {FEATURE_INVENTORY_PATH}")
        print("\nTo create it, perform a Chrome walkthrough of the Stage environment")
        print("and save the results as config/feature_inventory.json")
        print("\nExpected format:")
        print(json.dumps({
            "generated": "2026-03-13T...",
            "environment": "stage",
            "url": "https://staging.example.invalid",
            "areas": [
                {
                    "product_area": "Views",
                    "nav_path": "/views",
                    "features": [
                        {"name": "Live camera grid", "type": "page",
                         "interactions": ["drag-drop", "resize", "fullscreen"]},
                    ]
                }
            ]
        }, indent=2))
        return

    areas = inv.get("areas", [])
    total_features = sum(len(a.get("features", [])) for a in areas)
    print(f"\nFeature Inventory: {total_features} features across {len(areas)} areas")
    print(f"Environment: {inv.get('environment', '?')} | Generated: {inv.get('generated', '?')}\n")

    for area in areas:
        features = area.get("features", [])
        print(f"  {area['product_area']}: {len(features)} features")


def cmd_report(args):
    """Generate comprehensive gap report."""
    snapshot = load_latest_snapshot()
    pw_tests = discover_playwright_tests()
    mapping = load_case_mapping()
    feature_inv = load_feature_inventory()

    matrix = build_coverage_matrix(snapshot, pw_tests, mapping, feature_inv)
    gaps = compute_gap_scores(matrix)
    tagged = get_tagged_cases(snapshot)

    total_cases = sum(g["case_count"] for g in gaps)
    total_tests = sum(g["test_count"] for g in gaps)

    report = {
        "generated": datetime.now().isoformat(),
        "summary": {
            "total_qatouch_cases": total_cases,
            "total_playwright_tests": total_tests,
            "overall_automation_ratio": round(total_tests / total_cases * 100, 1) if total_cases else 0,
            "product_areas": len([g for g in gaps if g["case_count"] > 0]),
            "areas_with_automation": len([g for g in gaps if g["test_count"] > 0]),
            "areas_no_automation": len([g for g in gaps if g["case_count"] > 0 and g["test_count"] == 0]),
            "has_feature_inventory": feature_inv is not None,
            "smoke_tagged": len(tagged["smoke"]),
            "sanity_tagged": len(tagged["sanity"]),
            "untagged": len(tagged["untagged"]),
        },
        "gaps_by_priority": gaps,
        "recommendations": [],
    }

    # Generate recommendations
    for g in gaps:
        if g["status"] == "YELLOW_NO_AUTOMATION" and g["risk_weight"] >= 3:
            report["recommendations"].append({
                "priority": "HIGH",
                "area": g["area"],
                "action": f"Add Playwright automation for {g['area']} ({g['case_count']} manual cases, 0 automated)",
                "impact": f"Risk: {g['risk']}, Gap Score: {g['gap_score']}",
            })
        elif g["status"] == "YELLOW_LOW_AUTOMATION" and g["risk_weight"] >= 2:
            report["recommendations"].append({
                "priority": "MEDIUM",
                "area": g["area"],
                "action": f"Expand automation for {g['area']} (currently {g['auto_ratio']*100:.1f}% automated)",
                "impact": f"Risk: {g['risk']}, {g['case_count']} cases",
            })

    output_path = REPORT_DIR / f"gap_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(report, f, indent=2)

    # Print summary
    s = report["summary"]
    print(f"\n=== GAP ANALYSIS REPORT ===\n")
    print(f"QA Touch Cases:      {s['total_qatouch_cases']}")
    print(f"Playwright Tests:    {s['total_playwright_tests']}")
    print(f"Automation Coverage: {s['overall_automation_ratio']}%")
    print(f"Product Areas:       {s['product_areas']} ({s['areas_with_automation']} with automation)")
    print(f"Areas w/o Automation:{s['areas_no_automation']}")
    print(f"Feature Inventory:   {'Loaded' if s['has_feature_inventory'] else 'NOT LOADED (run Chrome walkthrough)'}")
    print(f"\nTagging:")
    print(f"  SMOKE:    {s['smoke_tagged']} cases")
    print(f"  SANITY:   {s['sanity_tagged']} cases")
    print(f"  Untagged: {s['untagged']} cases ({s['untagged']/s['total_qatouch_cases']*100:.0f}%)")

    if report["recommendations"]:
        print(f"\nTop Recommendations ({len(report['recommendations'])}):")
        for i, rec in enumerate(report["recommendations"][:10], 1):
            print(f"  {i}. [{rec['priority']}] {rec['action']}")

    print(f"\nFull report: {output_path.name}")


# ── Main ─────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="QA Touch Gap Analysis Tool")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("inventory", help="Show feature inventory status")
    sub.add_parser("snapshot", help="Analyze QA Touch snapshot by product area")
    sub.add_parser("playwright", help="Analyze Playwright coverage")
    sub.add_parser("matrix", help="Generate coverage matrix")

    gaps_p = sub.add_parser("gaps", help="Show coverage gaps")
    gaps_p.add_argument("--min-risk", choices=["low", "medium", "high", "critical"])

    sub.add_parser("vet-smoke", help="Vet SMOKE selections")
    sub.add_parser("vet-sanity", help="Vet SANITY selections")

    reg_p = sub.add_parser("regression", help="Recommend REGRESSION candidates")
    reg_p.add_argument("--target", type=int, default=500, help="Target number of cases")

    sub.add_parser("report", help="Generate comprehensive gap report")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        return

    commands = {
        "inventory": cmd_inventory,
        "snapshot": cmd_snapshot,
        "playwright": cmd_playwright,
        "matrix": cmd_matrix,
        "gaps": cmd_gaps,
        "vet-smoke": cmd_vet_smoke,
        "vet-sanity": cmd_vet_sanity,
        "regression": cmd_regression,
        "report": cmd_report,
    }
    commands[args.command](args)


if __name__ == "__main__":
    main()
