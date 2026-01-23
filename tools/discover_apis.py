#!/usr/bin/env python3
"""Discover and group APIs from a downloaded OpenAPI spec (QA).

Reads `tests/shared/schemas/openapi_spec_qa.json` and prints grouped endpoints.
"""
import json
from pathlib import Path
import os
import sys

ROOT = Path(__file__).resolve().parents[1]
SPEC_PATH = ROOT / "tests" / "shared" / "schemas" / "openapi_spec_qa.json"

TOP_APIS = [
    ("get", "/REST/dashboard/site/{siteId}/status"),
    ("get", "/REST/site/{siteId}/location/tree"),
    ("get", "/REST/site/{siteId}/channel/{channelId}/snap"),
    ("get", "/REST/dashboard/sharedwidgets/{customerId}/data"),
    ("get", "/REST/central/user/session"),
    ("get", "/REST/central/userprofile/roles"),
    ("post", "/REST/site/search"),
]


def load_spec():
    if not SPEC_PATH.exists():
        print(f"Spec not found: {SPEC_PATH}. Run download_openapi_spec.py first.")
        sys.exit(2)
    with open(SPEC_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def discover(spec: dict):
    paths = spec.get("paths", {})
    grouped = {}
    for path, ops in paths.items():
        for method, op in ops.items():
            tags = op.get("tags") or ["untagged"]
            for t in tags:
                grouped.setdefault(t, []).append({
                    "method": method.lower(),
                    "path": path,
                    "summary": op.get("summary") or op.get("description") or "",
                })
    return grouped


def print_grouped(grouped: dict):
    total = 0
    for tag, items in grouped.items():
        print(f"\nTag: {tag} ({len(items)} endpoints)")
        for it in items:
            print(f" - {it['method'].upper():6} {it['path']} -- {it['summary']}")
        total += len(items)
    print(f"\nTotal endpoints: {total}")


def check_top_apis(grouped: dict):
    found = {}
    # flatten to set of (method,path)
    flat = set()
    for items in grouped.values():
        for it in items:
            flat.add((it['method'], it['path']))
    for m, p in TOP_APIS:
        exists = (m.lower(), p) in flat
        found[(m, p)] = exists
    return found


def main():
    spec = load_spec()
    grouped = discover(spec)
    print_grouped(grouped)
    found = check_top_apis(grouped)
    print("\nTop API presence:")
    for (m, p), ok in found.items():
        print(f" - {m.upper():4} {p} : {'FOUND' if ok else 'MISSING'}")


if __name__ == '__main__':
    main()
