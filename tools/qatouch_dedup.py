"""QA Touch Dedup Tool - find and fix duplicate scaffolded test cases.

Compares scaffolded (API-created) test case stubs against existing manual
cases in the same QA Touch module. Produces:
  1. A match report showing which scaffolded cases have manual equivalents
  2. Updated mapping JSON remapping Playwright tests to existing manual cases
  3. A cleanup CSV listing stub case keys to delete in QA Touch UI
  4. A CSV of cases that need Mode=Automation set in QA Touch UI

Usage:
  python tools/qatouch_dedup.py scan           # find matches (read-only)
  python tools/qatouch_dedup.py fix             # remap + generate cleanup files
  python tools/qatouch_dedup.py audit           # check all auto-matched entries for quality
"""
from __future__ import annotations

import csv
import functools
import json
import os
import re
import sys
from difflib import SequenceMatcher
from pathlib import Path

# Windows console encoding fix
_print = print
print = functools.partial(_print, flush=True)
if sys.platform == 'win32':
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv
load_dotenv(ROOT / '.env')

from tools.qatouch_client import QATouchClient

PROJECT_KEY = os.environ.get('QATOUCH_PROJECT_ID', 'JlW1')
MAPPING_PATH = ROOT / 'config' / 'qatouch_case_mapping.json'
OUTPUT_DIR = ROOT / 'config'


def load_mapping() -> dict:
    with open(MAPPING_PATH, encoding='utf-8') as f:
        return json.load(f)


def save_mapping(data: dict):
    with open(MAPPING_PATH, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
        f.write('\n')


def normalize(text: str) -> str:
    """Normalize text for fuzzy comparison."""
    text = text.lower().strip()
    # Remove common prefixes
    for prefix in ['verify ', 'verify that ', 'check ', 'test ', 'ensure ',
                   'validate ', 'confirm ']:
        if text.startswith(prefix):
            text = text[len(prefix):]
    # Remove special chars, collapse whitespace
    text = re.sub(r'[^a-z0-9 ]', ' ', text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text


def word_overlap_score(a: str, b: str) -> float:
    """Score based on word overlap between two strings."""
    words_a = set(normalize(a).split())
    words_b = set(normalize(b).split())
    if not words_a or not words_b:
        return 0.0
    intersection = words_a & words_b
    union = words_a | words_b
    return len(intersection) / len(union)


def combined_score(test_title: str, case_title: str) -> float:
    """Combined similarity score using multiple methods."""
    # Method 1: SequenceMatcher on normalized text
    norm_test = normalize(test_title)
    norm_case = normalize(case_title)
    seq_score = SequenceMatcher(None, norm_test, norm_case).ratio()

    # Method 2: Word overlap (Jaccard)
    word_score = word_overlap_score(test_title, case_title)

    # Method 3: Key phrase matching
    # Extract key nouns/concepts from both
    key_phrases_test = set(re.findall(r'[a-z]{3,}', norm_test))
    key_phrases_case = set(re.findall(r'[a-z]{3,}', norm_case))
    if key_phrases_test and key_phrases_case:
        phrase_overlap = len(key_phrases_test & key_phrases_case) / len(key_phrases_test)
    else:
        phrase_overlap = 0.0

    # Weighted combination
    return (seq_score * 0.4) + (word_score * 0.3) + (phrase_overlap * 0.3)


def find_best_matches(test_title: str, module_cases: list[dict],
                      exclude_keys: set[str], top_n: int = 5) -> list[tuple[float, dict]]:
    """Find the best matching existing cases for a test title."""
    scored = []
    for case in module_cases:
        case_key = case.get('case_key', '')
        if case_key in exclude_keys:
            continue
        case_title = case.get('case_title', '')
        score = combined_score(test_title, case_title)
        scored.append((score, case))

    scored.sort(key=lambda x: x[0], reverse=True)
    return scored[:top_n]


def cmd_scan():
    """Scan for scaffolded stubs and find existing manual case matches."""
    print("=" * 70)
    print("QA Touch Dedup - Scan for Duplicate Scaffolded Cases")
    print("=" * 70)

    mapping = load_mapping()
    client = QATouchClient()

    # Find all scaffolded entries
    scaffolded = {}
    for nodeid, entry in mapping['mappings'].items():
        if not entry.get('auto_matched', True):
            scaffolded[nodeid] = entry

    print(f"\nScaffolded stubs found: {len(scaffolded)}")
    if not scaffolded:
        print("No scaffolded cases to check. All mappings are auto-matched.")
        return

    # Get all scaffolded case keys (to exclude from match candidates)
    scaffolded_keys = {e['case_key'] for e in scaffolded.values()}

    # Fetch all test cases from QA Touch
    print(f"\nFetching all test cases from QA Touch...")
    all_cases = client.list_all_test_cases(PROJECT_KEY)
    print(f"  Found {len(all_cases)} total cases")

    # Group cases by module
    cases_by_module: dict[str, list[dict]] = {}
    for case in all_cases:
        mod = case.get('module', 'Unknown')
        cases_by_module.setdefault(mod, []).append(case)

    # Also build a flat lookup by case_key
    case_by_key = {c['case_key']: c for c in all_cases if 'case_key' in c}

    print(f"\n{'=' * 70}")
    print(f"MATCH REPORT")
    print(f"{'=' * 70}")

    for nodeid, entry in scaffolded.items():
        stub_key = entry['case_key']
        stub_title = entry['case_title']
        stub_module = entry.get('module', 'Unknown')

        # Get the stub's actual module from QA Touch (it might differ)
        stub_case = case_by_key.get(stub_key, {})
        actual_module = stub_case.get('module', stub_module)

        short_nid = nodeid.split('::')[-1].replace('[chromium]', '')
        print(f"\n--- {short_nid} ---")
        print(f"  Stub: [{stub_key}] \"{stub_title}\"")
        print(f"  Module: {actual_module}")

        # Search in the same module first, then across all
        module_cases = cases_by_module.get(actual_module, [])
        matches = find_best_matches(stub_title, module_cases, scaffolded_keys, top_n=3)

        # If no good matches in module, try broader search
        if not matches or matches[0][0] < 0.3:
            broader_matches = find_best_matches(stub_title, all_cases, scaffolded_keys, top_n=3)
            if broader_matches and broader_matches[0][0] > (matches[0][0] if matches else 0):
                matches = broader_matches
                print(f"  (Searched across all modules)")

        if matches:
            for i, (score, case) in enumerate(matches):
                marker = " <-- BEST" if i == 0 and score >= 0.35 else ""
                print(f"  Match {i+1} (score={score:.2f}): [{case['case_key']}] "
                      f"\"{case['case_title'][:80]}\""
                      f" ({case.get('module', '?')}){marker}")
        else:
            print(f"  No matches found")

    print(f"\n{'=' * 70}")
    print(f"SUMMARY")
    print(f"{'=' * 70}")
    print(f"  Scaffolded stubs: {len(scaffolded)}")

    good_matches = 0
    for nodeid, entry in scaffolded.items():
        stub_key = entry['case_key']
        stub_title = entry['case_title']
        stub_case = case_by_key.get(stub_key, {})
        actual_module = stub_case.get('module', entry.get('module', 'Unknown'))
        module_cases = cases_by_module.get(actual_module, [])
        matches = find_best_matches(stub_title, module_cases, scaffolded_keys, top_n=1)
        if not matches or matches[0][0] < 0.3:
            matches = find_best_matches(stub_title, all_cases, scaffolded_keys, top_n=1)
        if matches and matches[0][0] >= 0.35:
            good_matches += 1

    print(f"  Likely duplicates (score >= 0.35): {good_matches}")
    print(f"  Possibly unique (score < 0.35): {len(scaffolded) - good_matches}")
    print(f"\nRun 'python tools/qatouch_dedup.py fix' to remap and generate cleanup files.")


def cmd_fix(threshold: float = 0.35):
    """Remap scaffolded stubs to existing manual cases and generate cleanup files."""
    print("=" * 70)
    print("QA Touch Dedup - Fix: Remap + Generate Cleanup Files")
    print("=" * 70)

    mapping = load_mapping()
    client = QATouchClient()

    # Find scaffolded entries
    scaffolded = {}
    for nodeid, entry in mapping['mappings'].items():
        if not entry.get('auto_matched', True):
            scaffolded[nodeid] = entry

    print(f"\nScaffolded stubs: {len(scaffolded)}")
    if not scaffolded:
        print("Nothing to fix.")
        return

    scaffolded_keys = {e['case_key'] for e in scaffolded.values()}

    # Fetch all cases
    print("Fetching all test cases...")
    all_cases = client.list_all_test_cases(PROJECT_KEY)
    print(f"  Found {len(all_cases)} cases")

    cases_by_module: dict[str, list[dict]] = {}
    for case in all_cases:
        mod = case.get('module', 'Unknown')
        cases_by_module.setdefault(mod, []).append(case)

    case_by_key = {c['case_key']: c for c in all_cases if 'case_key' in c}

    # Process each scaffolded entry
    remapped = []      # (nodeid, old_key, new_key, new_title, score)
    kept = []          # (nodeid, key, title) - genuinely new, no match found
    stubs_to_delete = []  # case_keys to delete in QA Touch UI
    cases_to_set_automation = []  # case_keys that need Mode=Automation

    for nodeid, entry in scaffolded.items():
        stub_key = entry['case_key']
        stub_title = entry['case_title']
        stub_case = case_by_key.get(stub_key, {})
        actual_module = stub_case.get('module', entry.get('module', 'Unknown'))

        module_cases = cases_by_module.get(actual_module, [])
        matches = find_best_matches(stub_title, module_cases, scaffolded_keys, top_n=1)

        if not matches or matches[0][0] < threshold:
            matches = find_best_matches(stub_title, all_cases, scaffolded_keys, top_n=1)

        if matches and matches[0][0] >= threshold:
            best_score, best_case = matches[0]
            new_key = best_case['case_key']
            new_title = best_case['case_title']
            new_module = best_case.get('module', '?')

            # Remap in mapping
            mapping['mappings'][nodeid] = {
                'case_key': new_key,
                'case_title': new_title,
                'score': round(best_score, 2),
                'module': new_module,
                'auto_matched': True,
            }
            remapped.append((nodeid, stub_key, new_key, new_title, best_score))
            stubs_to_delete.append(stub_key)
            cases_to_set_automation.append({
                'case_key': new_key,
                'case_title': new_title,
                'module': new_module,
                'playwright_test': nodeid.split('::')[-1].replace('[chromium]', ''),
            })
        else:
            # No good match - keep the scaffolded case but flag it
            kept.append((nodeid, stub_key, stub_title))
            cases_to_set_automation.append({
                'case_key': stub_key,
                'case_title': stub_title,
                'module': actual_module,
                'playwright_test': nodeid.split('::')[-1].replace('[chromium]', ''),
            })

    # Save updated mapping
    mapping['total_mapped'] = len(mapping['mappings'])
    save_mapping(mapping)

    # Generate cleanup CSV - stubs to delete
    if stubs_to_delete:
        delete_csv = OUTPUT_DIR / 'qatouch_stubs_to_delete.csv'
        with open(delete_csv, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['case_key', 'stub_title', 'remapped_to', 'remapped_title'])
            for nodeid, old_key, new_key, new_title, score in remapped:
                old_title = scaffolded[nodeid]['case_title']
                writer.writerow([old_key, old_title, new_key, new_title])
        print(f"\n  Wrote: {delete_csv}")
        print(f"    {len(stubs_to_delete)} stub cases to delete in QA Touch UI")

    # Generate Mode=Automation CSV
    if cases_to_set_automation:
        mode_csv = OUTPUT_DIR / 'qatouch_set_automation_mode.csv'
        with open(mode_csv, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['case_key', 'case_title', 'module', 'playwright_test'])
            for item in cases_to_set_automation:
                writer.writerow([
                    item['case_key'], item['case_title'],
                    item['module'], item['playwright_test'],
                ])
        print(f"  Wrote: {mode_csv}")
        print(f"    {len(cases_to_set_automation)} cases need Mode=Automation in QA Touch UI")

    # Print summary
    print(f"\n{'=' * 70}")
    print(f"RESULTS")
    print(f"{'=' * 70}")
    print(f"  Remapped to existing cases: {len(remapped)}")
    for nodeid, old_key, new_key, new_title, score in remapped:
        short_nid = nodeid.split('::')[-1].replace('[chromium]', '')
        print(f"    {short_nid}: [{old_key}] -> [{new_key}] (score={score:.2f})")
        print(f"      \"{new_title[:70]}\"")

    if kept:
        print(f"\n  Kept as genuinely new (no match >= {threshold}): {len(kept)}")
        for nodeid, key, title in kept:
            short_nid = nodeid.split('::')[-1].replace('[chromium]', '')
            print(f"    {short_nid}: [{key}] \"{title[:70]}\"")

    print(f"\n  Mapping updated: {MAPPING_PATH.name}")
    print(f"\n--- NEXT STEPS (in QA Touch UI) ---")
    if stubs_to_delete:
        print(f"  1. Delete {len(stubs_to_delete)} stub cases (see qatouch_stubs_to_delete.csv)")
        print(f"     Case keys: {', '.join(stubs_to_delete)}")
    print(f"  2. Set Mode=Automation on {len(cases_to_set_automation)} cases (see qatouch_set_automation_mode.csv)")
    print(f"     Quickest way: filter by case key in QA Touch, click case, Edit, change Mode dropdown")


def cmd_audit(low_threshold: float = 0.45):
    """Audit ALL mapped entries (auto-matched and scaffolded) for quality.

    Flags entries where the auto-match score is suspiciously low,
    indicating the Playwright test might be mapped to the wrong case.
    """
    print("=" * 70)
    print("QA Touch Dedup - Audit All Mappings")
    print("=" * 70)

    mapping = load_mapping()

    low_quality = []
    for nodeid, entry in mapping['mappings'].items():
        score = entry.get('score', 1.0)
        if score < low_threshold:
            low_quality.append((nodeid, entry))

    low_quality.sort(key=lambda x: x[1].get('score', 0))

    print(f"\nTotal mapped: {len(mapping['mappings'])}")
    print(f"Low-quality matches (score < {low_threshold}): {len(low_quality)}")

    if low_quality:
        print(f"\n--- LOW QUALITY MATCHES ---")
        for nodeid, entry in low_quality:
            short_nid = nodeid.split('::')[-1].replace('[chromium]', '')
            print(f"\n  {short_nid} (score={entry.get('score', '?')})")
            print(f"    -> [{entry['case_key']}] \"{entry['case_title'][:70]}\"")
            print(f"    Module: {entry.get('module', '?')}")
            auto = "auto-matched" if entry.get('auto_matched', True) else "scaffolded"
            print(f"    Source: {auto}")
    else:
        print("  All mappings look good!")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        sys.exit(0)

    cmd = sys.argv[1].lower()

    if cmd == 'scan':
        cmd_scan()
    elif cmd == 'fix':
        threshold = float(sys.argv[2]) if len(sys.argv) > 2 else 0.35
        cmd_fix(threshold=threshold)
    elif cmd == 'audit':
        threshold = float(sys.argv[2]) if len(sys.argv) > 2 else 0.45
        cmd_audit(low_threshold=threshold)
    else:
        print(f"Unknown command: {cmd}")
        print("Commands: scan, fix, audit")
        sys.exit(1)


if __name__ == '__main__':
    main()
