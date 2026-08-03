#!/usr/bin/env python3
"""One-time script to build feature_inventory.json from existing data sources."""
import json
import re
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

PROJECT_ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = PROJECT_ROOT / "config"

# ── Load data sources ──
with open(CONFIG_DIR / "qatouch_snapshots/snapshot_2026-03-02.json", encoding="utf-8") as f:
    snap = json.load(f)
with open(CONFIG_DIR / "module_nav_context.json", encoding="utf-8") as f:
    nav_ctx = json.load(f)

# Build module -> app_area mapping
mod_areas = {}
for mod_name, mod_info in nav_ctx.get("modules", {}).items():
    mod_areas[mod_name] = mod_info.get("app_area", "other")

# ── Scan Playwright Page Objects ──
pom_features = defaultdict(list)
pages_dir = PROJECT_ROOT / "tests" / "shared" / "pages"
for pom_file in sorted(pages_dir.glob("*_page.py")):
    content = pom_file.read_text(encoding="utf-8", errors="replace")
    cls_match = re.search(r"class (\w+Page)", content)
    cls_name = cls_match.group(1) if cls_match else pom_file.stem
    methods = re.findall(r"def ((?!_)\w+)\(self", content)
    locators = re.findall(r"self\.(\w+)\s*=\s*page\.locator\(", content)

    fname = pom_file.stem.replace("_page", "").lower()
    area_map = {
        "admin": "admin", "login": "login", "views": "views", "view": "views",
        "search": "search", "events": "events", "event": "events",
        "insights": "insights", "media": "media", "maps": "maps",
        "map": "maps", "notifications": "notifications", "chats": "other",
        "chat": "other", "license": "admin", "lpr": "lpr",
    }
    area = "other"
    for key, val in area_map.items():
        if key in fname:
            area = val
            break

    pom_features[area].append({
        "page_object": cls_name,
        "file": str(pom_file.relative_to(PROJECT_ROOT)),
        "methods": methods,
        "locators": locators,
    })

# ── Group QA Touch cases by area -> module ──
area_data = defaultdict(lambda: {
    "modules": defaultdict(lambda: {"cases": [], "priorities": set(), "types": set()}),
    "case_count": 0,
})

for c in snap["cases"]:
    mod = c.get("module name", "Unknown")
    area = mod_areas.get(mod, "other")
    area_data[area]["modules"][mod]["cases"].append({
        "title": c.get("case_title", ""),
        "key": c.get("case_key", ""),
        "priority": c.get("Priority", ""),
        "type": c.get("Type", ""),
        "tags": c.get("NewTags", ""),
    })
    area_data[area]["modules"][mod]["priorities"].add(c.get("Priority", ""))
    area_data[area]["modules"][mod]["types"].add(c.get("Type", ""))
    area_data[area]["case_count"] += 1

# ── Compile feature inventory ──
AREA_DESCRIPTIONS = {
    "views": {"name": "Views", "nav": "/views",
              "desc": "Live camera monitoring, grid layouts, saved views, playback, PTZ, bookmarks, sequences, sharing"},
    "search": {"name": "Search", "nav": "/search",
               "desc": "Global search, forensic search, category filters (person/vehicle/event), zone/line drawing, date/time pickers"},
    "events": {"name": "Events", "nav": "/events",
               "desc": "Event wall, AI detection events, filtering, pinning, export, acknowledgement"},
    "admin": {"name": "Admin", "nav": "/admin",
              "desc": "Users, roles, permissions, rules, sites, general settings, audit trail, licenses, channels, webhooks, storage"},
    "insights": {"name": "Insights", "nav": "/insights",
                 "desc": "Dashboards, widgets, analytics, reports, preset and custom dashboards"},
    "media": {"name": "Media", "nav": "/media",
              "desc": "Media vault, clip management, folders, export, sharing, bulk actions"},
    "maps": {"name": "Maps", "nav": "/maps",
             "desc": "Site maps, camera overlays, heat maps, static maps, map CRUD"},
    "login": {"name": "Login & Auth", "nav": "/auth/login",
              "desc": "Login, logout, MFA, session management, password reset, security"},
    "lpr": {"name": "LPR", "nav": "/admin/lpr",
            "desc": "License Plate Recognition management, lists, permissions"},
    "notifications": {"name": "Notifications", "nav": "Global (bell icon)",
                      "desc": "Notification panel, mute controls, popup alerts, read/unread state"},
    "other": {"name": "Cross-Cutting / Other", "nav": "Multiple",
              "desc": "Chats, UI consistency, accessibility, tooltips, error handling"},
}

ACTIONS = [
    "verify", "navigate", "click", "drag", "drop", "search", "filter",
    "create", "delete", "edit", "save", "export", "share", "upload",
    "toggle", "expand", "collapse", "scroll", "sort", "pin", "unpin",
    "mute", "unmute", "play", "pause", "fullscreen", "download",
    "reset", "refresh", "close", "open", "select", "assign", "remove",
]

inventory = {
    "generated": datetime.now().isoformat(),
    "environment": "stage",
    "url": "https://staging.example.invalid",
    "source": "auto-generated from QA Touch snapshot (3,011 cases) + Playwright POMs (15 files)",
    "note": "Validate against live Stage environment; add any missing features",
    "total_features": 0,
    "areas": [],
}

for area_key in ["views", "search", "events", "admin", "insights", "media",
                  "maps", "login", "lpr", "notifications", "other"]:
    area_info = AREA_DESCRIPTIONS.get(area_key, {"name": area_key, "nav": "?", "desc": ""})
    ad = area_data[area_key]

    features = []
    for mod_name in sorted(ad["modules"].keys()):
        mod = ad["modules"][mod_name]
        interactions = set()
        for c in mod["cases"]:
            title_lower = c["title"].lower()
            for action in ACTIONS:
                if action in title_lower:
                    interactions.add(action)

        features.append({
            "name": mod_name,
            "type": "module",
            "case_count": len(mod["cases"]),
            "priorities": sorted(mod["priorities"] - {""}),
            "interactions": sorted(interactions),
        })

    pom_info = pom_features.get(area_key, [])

    area_entry = {
        "product_area": area_info["name"],
        "nav_path": area_info["nav"],
        "description": area_info["desc"],
        "case_count": ad["case_count"],
        "module_count": len(ad["modules"]),
        "features": features,
        "page_objects": [
            {"class": p["page_object"], "methods": len(p["methods"]),
             "locators": len(p["locators"])}
            for p in pom_info
        ],
    }
    inventory["areas"].append(area_entry)
    inventory["total_features"] += len(features)

# Save
output_path = CONFIG_DIR / "feature_inventory.json"
with open(output_path, "w", encoding="utf-8") as f:
    json.dump(inventory, f, indent=2, default=list)

print(f"Feature inventory generated: {inventory['total_features']} features across {len(inventory['areas'])} areas")
for a in inventory["areas"]:
    pom_str = f" ({len(a['page_objects'])} POMs)" if a["page_objects"] else ""
    print(f"  {a['product_area']}: {len(a['features'])} features, {a['case_count']} cases{pom_str}")
print(f"\nSaved to: {output_path}")
