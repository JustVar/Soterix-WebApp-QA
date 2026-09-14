#!/usr/bin/env python3
"""Step Quality Audit Tool.

Comprehensive vetting of all 3,011 QA Touch test case step definitions.
Runs four audit passes:

  1. Alignment Audit   - scores how well steps match the case title
  2. Anomaly Detection  - finds misclassified cases (wrong template)
  3. Stratified Sample   - random sample per classification for manual review
  4. Module Walkthrough  - top modules summary for QA Touch UI review

Usage:
    python tools/step_quality_audit.py audit       # full audit (all 4 passes)
    python tools/step_quality_audit.py alignment    # pass 1 only
    python tools/step_quality_audit.py anomalies    # pass 2 only
    python tools/step_quality_audit.py sample       # pass 3 only
    python tools/step_quality_audit.py walkthrough  # pass 4 only
    python tools/step_quality_audit.py report       # generate markdown report
"""
from __future__ import annotations

import argparse
import json
import random
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONFIG = ROOT / "config"
MANUAL_DIR = ROOT / "tests" / "steps" / "manual"
PW_DIR = ROOT / "tests" / "steps" / "ui"
MASTER_REPO = CONFIG / "master_test_repository.json"
REPORT_DIR = ROOT / "tools" / "audit_reports"

# ── Keyword extraction helpers ─────────────────────────────────────────

# Words that carry no test-specific meaning
STOP_WORDS = {
    "verify", "that", "the", "is", "are", "a", "an", "for", "in", "on",
    "of", "to", "and", "or", "with", "when", "after", "before", "should",
    "can", "be", "not", "does", "do", "has", "have", "its", "it", "by",
    "this", "from", "at", "as", "if", "no", "all", "each", "into", "via",
    "validate", "check", "confirm", "ensure", "test", "testing",
    "general", "functionality", "behaves", "expected", "correctly",
    "properly", "displayed", "functions", "page", "loads", "without",
    "errors", "error", "user", "admin", "application", "system",
    "successfully", "appropriate", "relevant",
}

def extract_keywords(text: str) -> set[str]:
    """Extract meaningful keywords from text, excluding stop words."""
    words = set(re.findall(r"[a-z]+", text.lower()))
    return words - STOP_WORDS


def title_keywords(title: str) -> set[str]:
    """Extract keywords from a case title."""
    # Remove common prefixes
    cleaned = re.sub(r"^(?:Verify|Validate|Check|Confirm|Ensure|Test)\s+(?:that\s+)?", "", title, flags=re.I)
    return extract_keywords(cleaned)


def steps_keywords(steps: list[dict]) -> set[str]:
    """Extract keywords from all step actions and expected results."""
    words = set()
    for step in steps:
        words |= extract_keywords(step.get("action", ""))
        words |= extract_keywords(step.get("expected", ""))
    return words


# ── Classification expectation rules ───────────────────────────────────

# Each classification type should have certain keywords in title OR steps
CLASSIFICATION_SIGNALS = {
    "element_visibility": {"visible", "present", "displayed", "shown", "appears", "icon", "label", "badge", "tooltip", "overlay", "menu", "option", "indicator", "column", "header", "row", "name", "details", "format"},
    "element_state": {"enabled", "disabled", "checked", "selected", "active", "inactive", "highlighted", "focused", "readonly", "editable", "clickable"},
    "navigation": {"navigate", "redirect", "load", "land", "url", "route", "back", "forward", "breadcrumb", "tab", "link", "open"},
    "create": {"create", "add", "new", "insert", "register", "submit"},
    "edit": {"edit", "update", "modify", "change", "rename", "save"},
    "delete": {"delete", "remove", "clear", "purge", "discard"},
    "search_filter": {"search", "filter", "sort", "find", "query", "pagination", "reorder"},
    "error_validation": {"error", "invalid", "fail", "reject", "block", "prevent", "mismatch", "validation", "mandatory", "required"},
    "data_display": {"display", "show", "reflect", "count", "total", "number", "list", "populate", "contain", "accuracy", "matches", "consistent"},
    "interaction": {"click", "toggle", "expand", "collapse", "scroll", "drag", "drop", "hover", "select", "switch", "resize", "close", "cancel", "pin"},
    "persistence": {"persist", "retain", "remember", "restore", "session", "reload", "refresh", "maintain"},
    "configure_set": {"configur", "setting", "enable", "disable", "assign", "suspend", "reboot"},
    "button_control": {"button", "arrow", "slider", "control", "zoom"},
    "playback_media": {"playback", "video", "stream", "frame", "rewind", "pause", "play", "mute", "volume", "audio", "record", "preview", "fullscreen"},
    "ui_integrity": {"overlap", "truncat", "aligned", "distortion", "render", "broken", "responsive", "resolution", "contrast", "width"},
    "field_input": {"field", "input", "placeholder", "character", "limit", "trim", "spaces"},
    "drawing_zone": {"draw", "anchor", "direction", "crossing", "zone", "line"},
    "chat_message": {"chat", "message", "send", "chronolog"},
    "schedule_time": {"schedule", "timeout", "dwell", "calendar"},
    "performance_resilience": {"performance", "concurrent", "rapid", "simultaneous", "recovery", "crash", "cpu", "memory", "idle"},
    "logging_audit": {"logged", "audit", "read"},
    "auth": {"login", "logout", "password", "credentials", "session", "permission", "role", "restrict", "unauthorized"},
    "reset_default": {"reset", "default", "revert", "restore", "factory"},
    "data_transfer": {"export", "import", "download", "upload", "csv", "file"},
}


# ── Pass 1: Alignment Audit ───────────────────────────────────────────

def alignment_audit(cases: dict) -> list[dict]:
    """Score how well each case's steps match its title.

    Returns list of flagged cases sorted by alignment score (worst first).
    """
    results = []

    for ck, case in cases.items():
        title = case.get("title", "")
        steps = case.get("steps", [])

        if not steps:
            results.append({
                "case_key": ck,
                "title": title,
                "module": case.get("module_name", ""),
                "score": 0.0,
                "issue": "NO_STEPS",
                "classification": case.get("generation_info", {}).get("classification", "playwright") if case.get("generation_info") else "playwright",
            })
            continue

        t_kw = title_keywords(title)
        s_kw = steps_keywords(steps)

        if not t_kw:
            continue  # Title has no meaningful keywords

        # Overlap score: what fraction of title keywords appear in steps
        overlap = t_kw & s_kw
        score = len(overlap) / len(t_kw) if t_kw else 1.0

        # Check for specific issues
        issues = []

        # Subject mismatch: the main noun(s) from title should be in steps
        # Extract subject words (nouns likely to be the test target)
        subject_words = t_kw - {"visible", "present", "displayed", "enabled", "disabled",
                                 "loaded", "appears", "exists", "works", "opens", "closes",
                                 "selected", "highlighted", "active", "inactive", "correct",
                                 "updated", "created", "deleted", "removed", "filtered",
                                 "sorted", "searched", "saved", "submitted", "valid",
                                 "invalid", "empty", "full", "single", "multiple",
                                 "new", "old", "first", "last", "default", "custom"}
        subject_in_steps = subject_words & s_kw
        if subject_words and not subject_in_steps:
            issues.append(f"SUBJECT_MISSING: title subjects {subject_words - s_kw} not in steps")

        # Generic step check: are steps mostly boilerplate?
        generic_phrases = [
            "wait for the page to fully render",
            "locate the relevant ui area",
            "is displayed and functions correctly",
            "verify no errors or unexpected behavior",
        ]
        generic_count = sum(
            1 for s in steps
            if any(gp in s.get("action", "").lower() for gp in generic_phrases)
        )
        if generic_count >= 2:
            issues.append(f"GENERIC_STEPS: {generic_count} generic/boilerplate steps")

        # Navigation mismatch: nav step should reference the module
        module = case.get("module_name", "")
        nav_step = steps[1] if len(steps) > 1 else {}
        nav_action = nav_step.get("action", "").lower()
        module_words = set(re.findall(r"[a-z]+", module.lower())) - STOP_WORDS
        if module_words and not any(mw in nav_action for mw in module_words):
            if "navigate" in nav_action:
                issues.append(f"NAV_MISMATCH: nav step doesn't mention module '{module}'")

        if issues or score < 0.4:
            results.append({
                "case_key": ck,
                "title": title,
                "module": case.get("module_name", ""),
                "score": round(score, 3),
                "issue": "; ".join(issues) if issues else f"LOW_SCORE ({score:.2f})",
                "classification": case.get("generation_info", {}).get("classification", "playwright") if case.get("generation_info") else "playwright",
            })

    results.sort(key=lambda x: x["score"])
    return results


# ── Pass 2: Anomaly Detection ─────────────────────────────────────────

def anomaly_detection(cases: dict) -> list[dict]:
    """Find cases where classification doesn't match title keywords."""
    anomalies = []

    for ck, case in cases.items():
        gen_info = case.get("generation_info")
        if not gen_info:
            continue  # PW cases don't have generation_info

        classification = gen_info.get("classification", "")
        title = case.get("title", "")
        t_kw = title_keywords(title)

        if not t_kw or classification == "default":
            continue

        # Check if a different classification would be a better match
        current_signals = CLASSIFICATION_SIGNALS.get(classification, set())
        current_match = len(t_kw & current_signals)

        best_alt = None
        best_alt_score = 0
        for alt_cls, alt_signals in CLASSIFICATION_SIGNALS.items():
            if alt_cls == classification:
                continue
            alt_match = len(t_kw & alt_signals)
            if alt_match > best_alt_score:
                best_alt_score = alt_match
                best_alt = alt_cls

        # Flag if another classification matches MORE title keywords
        # and the current one matches ZERO
        if current_match == 0 and best_alt_score >= 2:
            anomalies.append({
                "case_key": ck,
                "title": title,
                "module": case.get("module_name", ""),
                "current_classification": classification,
                "suggested_classification": best_alt,
                "reason": f"Title keywords match '{best_alt}' ({best_alt_score} keywords) but not '{classification}' (0 keywords)",
                "title_keywords": sorted(t_kw),
            })
        # Also flag if another classification matches significantly better
        elif best_alt_score >= current_match + 3 and best_alt_score >= 3:
            anomalies.append({
                "case_key": ck,
                "title": title,
                "module": case.get("module_name", ""),
                "current_classification": classification,
                "suggested_classification": best_alt,
                "reason": f"'{best_alt}' matches {best_alt_score} keywords vs '{classification}' matches {current_match}",
                "title_keywords": sorted(t_kw),
            })

    anomalies.sort(key=lambda x: x["current_classification"])
    return anomalies


# ── Pass 3: Stratified Sample ─────────────────────────────────────────

def stratified_sample(cases: dict, per_type: int = 5, seed: int = 42) -> dict[str, list[dict]]:
    """Pull a random sample from each classification type for manual review."""
    random.seed(seed)

    by_type = defaultdict(list)
    for _ck, case in cases.items():
        gen_info = case.get("generation_info")
        if gen_info:
            cls = gen_info.get("classification", "unknown")
        else:
            cls = "playwright"
        by_type[cls].append(case)

    samples = {}
    for cls, cls_cases in sorted(by_type.items()):
        n = min(per_type, len(cls_cases))
        selected = random.sample(cls_cases, n)
        samples[cls] = []
        for case in selected:
            samples[cls].append({
                "case_key": case["case_key"],
                "title": case["title"],
                "module": case.get("module_name", ""),
                "step_count": case.get("step_count", 0),
                "steps_preview": [
                    f"{s['n']}. {s['action'][:60]}"
                    for s in case.get("steps", [])[:3]
                ],
                "qa_touch_url": f"https://soterixsystems.qatouch.com/v2#/testCase/JlW1/{case['case_key']}",
            })

    return samples


# ── Pass 4: Module Walkthrough ─────────────────────────────────────────

def module_walkthrough(cases: dict, top_n: int = 20) -> list[dict]:
    """Summarize top modules for QA Touch UI walkthrough."""
    modules = defaultdict(lambda: {
        "count": 0, "classifications": defaultdict(int),
        "sample_cases": [], "case_keys": [],
    })

    for ck, case in cases.items():
        mod = case.get("module_name", "Unknown")
        modules[mod]["count"] += 1
        modules[mod]["case_keys"].append(ck)

        gen_info = case.get("generation_info")
        cls = gen_info.get("classification", "unknown") if gen_info else "playwright"
        modules[mod]["classifications"][cls] += 1

        if len(modules[mod]["sample_cases"]) < 3:
            modules[mod]["sample_cases"].append({
                "case_key": ck,
                "title": case.get("title", "")[:70],
            })

    # Sort by case count descending
    sorted_mods = sorted(modules.items(), key=lambda x: -x[1]["count"])[:top_n]

    result = []
    for mod_name, info in sorted_mods:
        result.append({
            "module": mod_name,
            "case_count": info["count"],
            "classifications": dict(info["classifications"]),
            "sample_cases": info["sample_cases"],
            "qa_touch_url": "https://soterixsystems.qatouch.com/v2#/project/JlW1",
        })

    return result


# ── Report Generation ──────────────────────────────────────────────────

def generate_report(alignment: list, anomalies: list, samples: dict, walkthrough: list) -> str:
    """Generate a markdown audit report."""
    lines = []
    now = datetime.now().strftime("%Y-%m-%d %H:%M")

    lines.append("# Step Quality Audit Report")
    lines.append(f"**Generated:** {now}")
    lines.append("")

    # ── Summary
    lines.append("## Executive Summary")
    lines.append("")
    total_alignment_flags = len(alignment)
    critical = sum(1 for a in alignment if a["score"] < 0.2 or a["issue"] == "NO_STEPS")
    warnings = sum(1 for a in alignment if 0.2 <= a["score"] < 0.4)
    generic = sum(1 for a in alignment if "GENERIC_STEPS" in a.get("issue", ""))
    nav_mismatch = sum(1 for a in alignment if "NAV_MISMATCH" in a.get("issue", ""))
    subject_missing = sum(1 for a in alignment if "SUBJECT_MISSING" in a.get("issue", ""))

    lines.append("| Check | Count | Severity |")
    lines.append("|-------|-------|----------|")
    lines.append(f"| Alignment flags | {total_alignment_flags} | Mixed |")
    lines.append(f"| - Critical (score < 0.2 or no steps) | {critical} | High |")
    lines.append(f"| - Warnings (score 0.2-0.4) | {warnings} | Medium |")
    lines.append(f"| - Generic/boilerplate steps | {generic} | Low |")
    lines.append(f"| - Navigation mismatch | {nav_mismatch} | Low |")
    lines.append(f"| - Subject missing from steps | {subject_missing} | Medium |")
    lines.append(f"| Classification anomalies | {len(anomalies)} | Medium |")
    lines.append(f"| Review sample size | {sum(len(v) for v in samples.values())} cases | - |")
    lines.append("")

    # ── Pass 1: Alignment
    lines.append("## Pass 1: Alignment Audit")
    lines.append("")
    if not alignment:
        lines.append("No alignment issues found.")
    else:
        lines.append(f"**{total_alignment_flags} cases flagged** (sorted by alignment score, worst first)")
        lines.append("")

        # Group by issue type
        for issue_type, label in [
            ("NO_STEPS", "Cases with No Steps"),
            ("GENERIC_STEPS", "Cases with Generic/Boilerplate Steps"),
            ("SUBJECT_MISSING", "Cases Missing Subject in Steps"),
            ("NAV_MISMATCH", "Navigation Mismatch"),
            ("LOW_SCORE", "Low Alignment Score"),
        ]:
            flagged = [a for a in alignment if issue_type in a.get("issue", "")]
            if not flagged:
                continue
            lines.append(f"### {label} ({len(flagged)})")
            lines.append("")
            lines.append("| Case Key | Score | Module | Title | Classification |")
            lines.append("|----------|-------|--------|-------|----------------|")
            for a in flagged[:30]:  # Cap at 30 per category
                title_short = a["title"][:50] + ("..." if len(a["title"]) > 50 else "")
                lines.append(f"| `{a['case_key']}` | {a['score']:.2f} | {a['module'][:25]} | {title_short} | {a['classification']} |")
            if len(flagged) > 30:
                lines.append(f"| ... | | | *{len(flagged) - 30} more* | |")
            lines.append("")

    # ── Pass 2: Anomalies
    lines.append("## Pass 2: Classification Anomalies")
    lines.append("")
    if not anomalies:
        lines.append("No classification anomalies detected.")
    else:
        lines.append(f"**{len(anomalies)} potential misclassifications found**")
        lines.append("")
        lines.append("| Case Key | Title | Current | Suggested | Reason |")
        lines.append("|----------|-------|---------|-----------|--------|")
        for a in anomalies[:50]:
            title_short = a["title"][:40] + ("..." if len(a["title"]) > 40 else "")
            reason_short = a["reason"][:50] + ("..." if len(a["reason"]) > 50 else "")
            lines.append(f"| `{a['case_key']}` | {title_short} | {a['current_classification']} | {a['suggested_classification']} | {reason_short} |")
        if len(anomalies) > 50:
            lines.append(f"| ... | | | | *{len(anomalies) - 50} more* |")
    lines.append("")

    # ── Pass 3: Stratified Sample
    lines.append("## Pass 3: Stratified Review Sample")
    lines.append("")
    total_sample = sum(len(v) for v in samples.values())
    lines.append(f"**{total_sample} cases sampled** across {len(samples)} classification types (5 per type)")
    lines.append("")
    lines.append("Review these cases in QA Touch to validate step quality for each classification.")
    lines.append("")
    for cls, cls_samples in samples.items():
        lines.append(f"### {cls} ({len(cls_samples)} samples)")
        lines.append("")
        for s in cls_samples:
            lines.append(f"- **[{s['case_key']}]({s['qa_touch_url']})** - {s['title'][:60]}")
            lines.append(f"  - Module: {s['module']}, Steps: {s['step_count']}")
            for preview in s["steps_preview"]:
                lines.append(f"  - `{preview}`")
        lines.append("")

    # ── Pass 4: Module Walkthrough
    lines.append("## Pass 4: Top Module Walkthrough")
    lines.append("")
    lines.append(f"Top {len(walkthrough)} modules by case count. Review these modules in QA Touch UI.")
    lines.append("")
    lines.append("| # | Module | Cases | Top Classification | Sample Case |")
    lines.append("|---|--------|-------|--------------------|-------------|")
    for i, mod in enumerate(walkthrough, 1):
        top_cls = max(mod["classifications"], key=mod["classifications"].get) if mod["classifications"] else "-"
        sample = mod["sample_cases"][0]["title"][:40] if mod["sample_cases"] else "-"
        lines.append(f"| {i} | {mod['module'][:30]} | {mod['case_count']} | {top_cls} | {sample}... |")
    lines.append("")

    return "\n".join(lines)


# ── Main ───────────────────────────────────────────────────────────────

def load_cases() -> dict:
    """Load all cases from master repository."""
    with open(MASTER_REPO, encoding="utf-8") as f:
        master = json.load(f)
    return master.get("cases", {})


def run_audit(passes: list[str] | None = None):
    """Run audit passes and print results."""
    cases = load_cases()
    print(f"Loaded {len(cases)} cases from master repository\n")

    all_passes = passes or ["alignment", "anomalies", "sample", "walkthrough"]

    alignment_results = []
    anomaly_results = []
    sample_results = {}
    walkthrough_results = []

    if "alignment" in all_passes:
        print("=" * 60)
        print("  PASS 1: Alignment Audit")
        print("=" * 60)
        alignment_results = alignment_audit(cases)

        critical = [a for a in alignment_results if a["score"] < 0.2 or a["issue"] == "NO_STEPS"]
        warnings = [a for a in alignment_results if "GENERIC_STEPS" in a.get("issue", "") or "SUBJECT_MISSING" in a.get("issue", "")]
        info = [a for a in alignment_results if "NAV_MISMATCH" in a.get("issue", "")]

        print(f"  Total flagged: {len(alignment_results)}")
        print(f"  Critical:      {len(critical)}")
        print(f"  Warnings:      {len(warnings)}")
        print(f"  Info:          {len(info)}")

        if critical:
            print("\n  Top 10 critical issues:")
            for a in critical[:10]:
                print(f"    [{a['case_key']}] score={a['score']:.2f} | {a['title'][:55]}")
                print(f"      Issue: {a['issue'][:70]}")
        print()

    if "anomalies" in all_passes:
        print("=" * 60)
        print("  PASS 2: Anomaly Detection")
        print("=" * 60)
        anomaly_results = anomaly_detection(cases)
        print(f"  Potential misclassifications: {len(anomaly_results)}")

        if anomaly_results:
            # Group by current classification
            by_cls = defaultdict(list)
            for a in anomaly_results:
                by_cls[a["current_classification"]].append(a)

            print("\n  By current classification:")
            for cls, items in sorted(by_cls.items(), key=lambda x: -len(x[1])):
                print(f"    {cls}: {len(items)} anomalies")
                for item in items[:3]:
                    print(f"      [{item['case_key']}] -> {item['suggested_classification']}: {item['title'][:50]}")
        print()

    if "sample" in all_passes:
        print("=" * 60)
        print("  PASS 3: Stratified Sample")
        print("=" * 60)
        sample_results = stratified_sample(cases)
        total = sum(len(v) for v in sample_results.values())
        print(f"  Sample size: {total} cases across {len(sample_results)} types")
        for cls, cls_samples in sample_results.items():
            print(f"    {cls}: {len(cls_samples)} cases")
        print()

    if "walkthrough" in all_passes:
        print("=" * 60)
        print("  PASS 4: Module Walkthrough")
        print("=" * 60)
        walkthrough_results = module_walkthrough(cases)
        total_covered = sum(m["case_count"] for m in walkthrough_results)
        print(f"  Top {len(walkthrough_results)} modules cover {total_covered} cases ({total_covered/len(cases)*100:.0f}%)")
        for i, mod in enumerate(walkthrough_results[:10], 1):
            print(f"    {i}. {mod['module'][:35]:35s} ({mod['case_count']} cases)")
        print()

    # Generate report
    if len(all_passes) > 1 or "report" in (passes or []):
        REPORT_DIR.mkdir(parents=True, exist_ok=True)
        report = generate_report(alignment_results, anomaly_results, sample_results, walkthrough_results)
        report_path = REPORT_DIR / f"audit_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md"
        report_path.write_text(report, encoding="utf-8")
        print(f"  Report saved: {report_path}")

    # Also save raw JSON for programmatic use
    if len(all_passes) > 1:
        raw_path = REPORT_DIR / f"audit_{datetime.now().strftime('%Y%m%d_%H%M%S')}_raw.json"
        raw_data = {
            "generated_at": datetime.now().isoformat(),
            "total_cases": len(cases),
            "alignment_flags": len(alignment_results),
            "anomalies": len(anomaly_results),
            "sample_size": sum(len(v) for v in sample_results.values()),
            "alignment_results": alignment_results[:100],  # Cap for file size
            "anomaly_results": anomaly_results,
            "sample_results": {k: v for k, v in sample_results.items()},
            "walkthrough_results": walkthrough_results,
        }
        with open(raw_path, "w", encoding="utf-8") as f:
            json.dump(raw_data, f, indent=2, ensure_ascii=False)
        print(f"  Raw data saved: {raw_path}")

    return alignment_results, anomaly_results, sample_results, walkthrough_results


def main():
    parser = argparse.ArgumentParser(description="Step Quality Audit Tool")
    parser.add_argument("command", nargs="?", default="audit",
                       choices=["audit", "alignment", "anomalies", "sample", "walkthrough", "report"],
                       help="Which audit pass to run (default: all)")
    args = parser.parse_args()

    if args.command == "audit" or args.command == "report":
        run_audit()
    elif args.command == "alignment":
        run_audit(["alignment"])
    elif args.command == "anomalies":
        run_audit(["anomalies"])
    elif args.command == "sample":
        run_audit(["sample"])
    elif args.command == "walkthrough":
        run_audit(["walkthrough"])


if __name__ == "__main__":
    main()
