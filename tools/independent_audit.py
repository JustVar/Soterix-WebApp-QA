"""
Independent QA Touch Test Case Audit Script
Audits 3,011 test cases in master_test_repository.json for quality issues.
READ-ONLY - does not modify any step files or source data.

Audit dimensions:
  1. Title-to-step alignment: Do steps actually test what the title says?
  2. Step specificity: Are steps actionable for a new QA engineer?
  3. Navigation accuracy: Does step 2 (navigation) make sense for the module?
  4. Expected results: Are they verifiable, or vague?
  5. Step ordering: Logical sequence?
  6. Completeness: Enough steps to verify the title?

Programmatic scans:
  A. "functions correctly" / "works as expected" without specifics
  B. Identical action and expected text
  C. Navigation steps referencing wrong module name
  D. Cases with fewer than 4 steps
  E. Cases where step 1 is NOT a login step
  F. Duplicate step text within the same case
  G. Template variable leak: "{subject}" or "{predicate}" literally
"""

import json
import random
import re
from collections import Counter, defaultdict
from datetime import date
from pathlib import Path

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
REPO_ROOT = Path("c:/path/to/Soterix-WebApp-QA")
MASTER_JSON = REPO_ROOT / "config" / "master_test_repository.json"
AUDIT_DIR = REPO_ROOT / "tools" / "audit_reports"
TODAY = date.today().strftime("%Y%m%d")
OUTPUT_JSON = AUDIT_DIR / f"independent_audit_{TODAY}.json"

AUDIT_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Load data
# ---------------------------------------------------------------------------
print("Loading master_test_repository.json ...")
with open(MASTER_JSON, encoding="utf-8") as f:
    data = json.load(f)

all_cases_raw = list(data["cases"].values())
ALL_CASES = [c for c in all_cases_raw if c is not None]
print(f"  Loaded {len(ALL_CASES)} cases (expected 3011)")

# ---------------------------------------------------------------------------
# Build classification index
# ---------------------------------------------------------------------------
by_classification = defaultdict(list)
for c in ALL_CASES:
    gi = c.get("generation_info")
    cls = gi.get("classification", "unknown") if gi else "playwright"
    by_classification[cls].append(c)

ALL_CLASSIFICATIONS = sorted(by_classification.keys())
print(f"  Found {len(ALL_CLASSIFICATIONS)} classification types: {ALL_CLASSIFICATIONS}")

# ---------------------------------------------------------------------------
# Helper utilities
# ---------------------------------------------------------------------------

def get_steps(case):
    return case.get("steps") or []

def step_text(step):
    return f"{step.get('action', '')} | {step.get('expected', '')}"

def is_login_step(step):
    action = step.get("action", "").lower()
    return (
        "log in" in action
        or "login" in action
        or "sign in" in action
        or "open the application login page" in action
        or "log into" in action
    )

def is_vague_expected(text):
    """Return True if the expected result text is vague/generic."""
    vague_patterns = [
        r"\bfunctions correctly\b",
        r"\bworks as expected\b",
        r"\bworks correctly\b",
        r"\bworks fine\b",
        r"\boperates correctly\b",
        r"\bbehaves correctly\b",
        r"\bbehaves as expected\b",
        r"\bfunctions as expected\b",
        r"\bshould work\b",
        r"\bis working\b",
    ]
    text_lower = text.lower()
    return any(re.search(pat, text_lower) for pat in vague_patterns)

def has_template_leak(text):
    return bool(re.search(r"\{subject\}|\{predicate\}", text, re.IGNORECASE))

def steps_identical_action_expected(step):
    return step.get("action", "").strip().lower() == step.get("expected", "").strip().lower()

def extract_nav_module(step):
    """Extract the module reference from a navigation step action."""
    action = step.get("action", "")
    # Pattern: "Navigate to X > Y" or "Navigate to X"
    m = re.match(r"Navigate to (.+)", action, re.IGNORECASE)
    if m:
        return m.group(1).strip()
    return None

# ---------------------------------------------------------------------------
# PROGRAMMATIC SCAN - runs over ALL 3,011 cases
# ---------------------------------------------------------------------------
print("\nRunning programmatic scans over all 3,011 cases ...")

issues = {
    "vague_expected": [],          # A
    "identical_action_expected": [],  # B
    "wrong_nav_module": [],         # C
    "too_few_steps": [],            # D
    "no_login_first_step": [],      # E
    "duplicate_step_text": [],      # F
    "template_leak": [],            # G
}

for case in ALL_CASES:
    ck = case["case_key"]
    title = case.get("title", "")
    module_name = case.get("module_name", "")
    steps = get_steps(case)

    # D - fewer than 4 steps
    if len(steps) < 4:
        issues["too_few_steps"].append({
            "case_key": ck,
            "title": title,
            "module": module_name,
            "step_count": len(steps),
        })

    # E - step 1 not a login
    if steps and not is_login_step(steps[0]):
        issues["no_login_first_step"].append({
            "case_key": ck,
            "title": title,
            "module": module_name,
            "step_1_action": steps[0].get("action", ""),
        })

    # Step-level scans
    seen_step_texts = []
    nav_step_found = False
    for step in steps:
        action = step.get("action", "")
        expected = step.get("expected", "")
        combined = f"{action} {expected}"

        # A - vague expected
        if is_vague_expected(expected):
            issues["vague_expected"].append({
                "case_key": ck,
                "title": title,
                "module": module_name,
                "step_n": step.get("n"),
                "expected": expected,
            })

        # B - identical action and expected
        if steps_identical_action_expected(step) and action.strip():
            issues["identical_action_expected"].append({
                "case_key": ck,
                "title": title,
                "module": module_name,
                "step_n": step.get("n"),
                "text": action,
            })

        # C - navigation step referencing wrong module
        nav_ref = extract_nav_module(step)
        if nav_ref and not nav_step_found:
            nav_step_found = True
            # Check if module_name appears anywhere in the navigation reference
            # Be liberal: check if either contains the other or share significant words
            module_words = set(re.sub(r"[^a-z0-9 ]", "", module_name.lower()).split())
            nav_words = set(re.sub(r"[^a-z0-9 ]", "", nav_ref.lower()).split())
            # Remove common stop words
            stop = {"the", "a", "an", "to", "for", "in", "of", "and", "or", "is", "are"}
            module_words -= stop
            nav_words -= stop
            # If module has meaningful words, check overlap
            if module_words and not (module_words & nav_words):
                issues["wrong_nav_module"].append({
                    "case_key": ck,
                    "title": title,
                    "module": module_name,
                    "nav_reference": nav_ref,
                    "step_n": step.get("n"),
                })

        # G - template leak
        if has_template_leak(combined):
            issues["template_leak"].append({
                "case_key": ck,
                "title": title,
                "module": module_name,
                "step_n": step.get("n"),
                "action": action,
                "expected": expected,
            })

        # F - duplicate step text (action+expected)
        text_key = f"{action.strip().lower()}|||{expected.strip().lower()}"
        if text_key in seen_step_texts and action.strip():
            issues["duplicate_step_text"].append({
                "case_key": ck,
                "title": title,
                "module": module_name,
                "step_n": step.get("n"),
                "duplicate_text": action[:120],
            })
        seen_step_texts.append(text_key)

print("  Programmatic scan complete.")
for issue_type, lst in issues.items():
    print(f"    {issue_type}: {len(lst)} occurrences")

# ---------------------------------------------------------------------------
# MANUAL SAMPLE AUDIT - 10 cases per classification (250 total)
# ---------------------------------------------------------------------------
print("\nBuilding manual sample audit (10 per classification) ...")

random.seed(42)  # reproducible


def verdict_navigation(case):
    """
    Evaluate a navigation-type case.
    Returns (verdict, issues_list)
    """
    problems = []
    steps = get_steps(case)
    case.get("title", "")  # kept for its effect
    module = case.get("module_name", "")

    # Title-step alignment: navigation case should end with verifying URL or page loaded
    step_actions = [s.get("action", "").lower() for s in steps]
    has_url_check = any("url" in a for a in step_actions)
    has_page_load = any("load" in a for a in step_actions)
    if not has_url_check and not has_page_load:
        problems.append("No URL or page-load verification step")

    # Precondition steps appended at the end are out of logical order
    for s in steps:
        if s.get("n", 0) > 3 and "set up precondition" in s.get("action", "").lower():
            problems.append(f"Step {s['n']}: Precondition setup appears after verification steps (illogical order)")
            break

    # Navigation step 2 should reference the module
    if len(steps) >= 2:
        nav_ref = extract_nav_module(steps[1])
        if nav_ref:
            module_words = set(re.sub(r"[^a-z0-9 ]", "", module.lower()).split()) - {"the", "a", "an"}
            nav_words = set(re.sub(r"[^a-z0-9 ]", "", nav_ref.lower()).split()) - {"the", "a", "an"}
            if module_words and not (module_words & nav_words):
                problems.append(f"Step 2 navigation '{nav_ref}' does not match module '{module}'")

    # Check for vague expected results
    for s in steps:
        if is_vague_expected(s.get("expected", "")):
            problems.append(f"Step {s['n']}: Vague expected result: '{s['expected']}'")

    # Step count adequacy
    if len(steps) < 4:
        problems.append(f"Only {len(steps)} steps - insufficient for navigation test")

    if not problems:
        verdict = "Pass"
    elif len(problems) <= 2:
        verdict = "Needs Work"
    else:
        verdict = "Fail"

    return verdict, problems


def verdict_element_visibility(case):
    problems = []
    steps = get_steps(case)
    title = case.get("title", "")
    case.get("module_name", "")  # kept for its effect

    # Should have a step that locates/finds the element
    step_actions = [s.get("action", "").lower() for s in steps]
    has_locate = any("locate" in a or "find" in a or "scroll" in a for a in step_actions)
    if not has_locate:
        problems.append("No step that locates or scrolls to the target element")

    # Should have a step that asserts visible
    has_visible_check = any(
        "visible" in a or "displayed" in a or "appear" in a or "is visible" in s.get("expected", "").lower()
        for a, s in zip(step_actions, steps, strict=False)
    )
    if not has_visible_check:
        problems.append("No explicit visibility assertion step")

    # Check last verification step for vague expected
    for s in steps[-3:]:
        if is_vague_expected(s.get("expected", "")):
            problems.append(f"Step {s['n']}: Vague expected: '{s['expected']}'")

    # Title-to-step alignment: extract what should be visible from title
    title.lower().replace("verify ", "").replace(" is visible", "").strip()  # kept for its effect

    # Check for identical action/expected (template defect)
    for s in steps:
        if steps_identical_action_expected(s) and s.get("action", "").strip():
            problems.append(f"Step {s['n']}: Action equals expected ('{s.get('action', '')[:60]}...')")

    # Preconditions appended out of order
    for s in steps:
        if s.get("n", 0) > 3 and "set up precondition" in s.get("action", "").lower():
            problems.append(f"Step {s['n']}: Precondition setup appended at end - logically should be before test body")

    if not problems:
        verdict = "Pass"
    elif len(problems) <= 2:
        verdict = "Needs Work"
    else:
        verdict = "Fail"
    return verdict, problems


def verdict_configure_set(case):
    problems = []
    steps = get_steps(case)
    title = case.get("title", "")

    # Should navigate, locate control, apply change, verify, save, and check persistence
    step_actions = [s.get("action", "").lower() for s in steps]

    # Check for persistence verification
    has_refresh = any("refresh" in a for a in step_actions)
    if not has_refresh:
        problems.append("No refresh/persistence check after configuration change")

    # Step 5 often says "Apply the configuration change described: Verify [title]" - title injected verbatim
    for s in steps:
        action = s.get("action", "")
        if "apply the configuration change described: verify " in action.lower():
            # The full title is embedded - check if it's meaningful or just a template fill
            if "verify " in action.lower() and len(action) > 80:
                problems.append(f"Step {s['n']}: Step action embeds entire test title verbatim - not actionable for a QA engineer")

    # Save step is generic - doesn't specify WHERE to click
    for s in steps:
        if "save or confirm the configuration" in s.get("action", "").lower():
            if "save" not in s.get("expected", "").lower() and "success" not in s.get("expected", "").lower() and "confirm" not in s.get("expected", "").lower():
                problems.append(f"Step {s['n']}: Save step expected result is non-specific")

    # Check expected for vague patterns
    for s in steps:
        if is_vague_expected(s.get("expected", "")):
            problems.append(f"Step {s['n']}: Vague expected: '{s['expected']}'")

    # Title-step alignment: configure steps should mention the specific control being configured
    title_words = set(title.lower().replace("verify ", "").split()) - {"the", "a", "an", "to", "is", "in", "of", "and", "or"}
    step5_action = steps[4].get("action", "").lower() if len(steps) > 4 else ""
    title_found_in_steps = any(word in step5_action for word in title_words if len(word) > 4)
    if not title_found_in_steps and step5_action:
        # Mild concern - might just be template issue
        pass  # don't penalize here, covered above

    if not problems:
        verdict = "Pass"
    elif len(problems) <= 2:
        verdict = "Needs Work"
    else:
        verdict = "Fail"
    return verdict, problems


def verdict_auth(case):
    problems = []
    steps = get_steps(case)
    title = case.get("title", "")

    # Auth tests should NOT start with generic "Log in with valid credentials" (they need specific role)
    if steps and "log in to the application with valid credentials" in steps[0].get("action", "").lower():
        # Most auth cases start with "Open the application login page" which is correct
        # But if step_source is generated and classification is auth, should test specific role
        if case.get("step_source") == "generated":
            problems.append("Step 1: Uses generic login rather than specifying the required user role for this auth test")

    # Auth cases should test both positive (can access) and negative (blocked) paths, or be clear which
    step_actions = [s.get("action", "").lower() for s in steps]
    has_access_check = any("access" in a or "permission" in a or "role" in a for a in step_actions)
    if not has_access_check:
        problems.append("No explicit access/permission/role verification step")

    # Logout verification should be present in re-login tests
    if "re-login" in case.get("module_name", "").lower() or "re-login" in title.lower():
        has_logout = any("log out" in a or "logout" in a for a in step_actions)
        if not has_logout:
            problems.append("Re-login test has no logout step")

    # Check step ordering - precondition at end
    for s in steps:
        if s.get("n", 0) > 3 and "set up precondition" in s.get("action", "").lower():
            problems.append(f"Step {s['n']}: Precondition setup appears after verification steps")

    for s in steps:
        if is_vague_expected(s.get("expected", "")):
            problems.append(f"Step {s['n']}: Vague expected: '{s['expected']}'")

    if not problems:
        verdict = "Pass"
    elif len(problems) <= 2:
        verdict = "Needs Work"
    else:
        verdict = "Fail"
    return verdict, problems


def verdict_create(case):
    problems = []
    steps = get_steps(case)
    title = case.get("title", "")

    step_actions = [s.get("action", "").lower() for s in steps]

    # Title-to-step alignment: create steps should test creation, not delete/search
    # Biggest problem: title says "cannot be added twice" but steps test a generic create flow
    if "cannot be added" in title.lower() or "duplicate" in title.lower():
        has_duplicate_check = any("duplicate" in a or "already exists" in a or "cannot add" in a or "twice" in a for a in step_actions)
        if not has_duplicate_check:
            problems.append("CRITICAL: Title says 'cannot be added twice'/'duplicate' but steps test generic create flow - steps don't align with title")

    # Embedding raw title in step text
    for s in steps:
        action = s.get("action", "")
        s.get("expected", "")  # kept for its effect
        # Step 10 typically says "Verify the newly created [raw_title_fragment] appears..."
        if "newly created" in action.lower():
            # Extract what comes after "newly created"
            after = re.sub(r".*newly created ", "", action.lower())
            # If it's a long phrase verbatim from the title, it's a template defect
            if len(after) > 40:
                problems.append(f"Step {s['n']}: 'Newly created' step embeds raw title text - step is confusing ('{action[:80]}...')")
            if "cannot" in after or "adds them" in after or "does not" in after:
                problems.append(f"Step {s['n']}: Expected result description is actually the test title, not a verifiable outcome")

    # Should have form-filling step
    has_fill = any("fill in" in a or "enter" in a or "input" in a for a in step_actions)
    if not has_fill:
        problems.append("No step to fill in form fields - create test cannot verify form submission")

    for s in steps:
        if is_vague_expected(s.get("expected", "")):
            problems.append(f"Step {s['n']}: Vague expected: '{s['expected']}'")

    if not problems:
        verdict = "Pass"
    elif len(problems) <= 2:
        verdict = "Needs Work"
    else:
        verdict = "Fail"
    return verdict, problems


def verdict_delete(case):
    problems = []
    steps = get_steps(case)
    title = case.get("title", "")

    step_actions = [s.get("action", "").lower() for s in steps]

    # Title-to-step alignment: delete cases where title is not about deleting an entity
    # e.g. "Verify clearing Search Views restores full view list" is a search/filter action, not a delete

    # The delete template is applied regardless of whether the title is about deletion
    if "clearing" in title.lower() or "unchecking" in title.lower() or "hiding" in title.lower():
        problems.append("CRITICAL: Classification 'delete' misapplied - title describes a search/filter/toggle action but delete template steps are used (confirmation dialog, item count, etc.)")

    # Identify the target entity in steps - it's often the raw title injected into step text
    for s in steps:
        action = s.get("action", "")
        if "identify the" in action.lower() and title.lower().replace("verify ", "") in action.lower():
            problems.append(f"Step {s['n']}: Step uses full test title as entity name - not actionable (a QA engineer cannot identify 'clearing Search Views restores full view list' in a list)")

    # Should have a count-based verification
    has_count = any("count" in a for a in step_actions)
    if not has_count:
        problems.append("No step verifying item count decreased after deletion")

    for s in steps:
        if is_vague_expected(s.get("expected", "")):
            problems.append(f"Step {s['n']}: Vague expected: '{s['expected']}'")

    if not problems:
        verdict = "Pass"
    elif len(problems) <= 2:
        verdict = "Needs Work"
    else:
        verdict = "Fail"
    return verdict, problems


def verdict_edit(case):
    problems = []
    steps = get_steps(case)
    title = case.get("title", "")

    step_actions = [s.get("action", "").lower() for s in steps]

    # Title-to-step alignment: is this really an edit/update operation?
    is_edit_title = any(w in title.lower() for w in ["changing", "editing", "modif", "updat", "selecting", "adjusting"])
    if not is_edit_title:
        # May be misclassified
        problems.append(f"Classification 'edit' but title doesn't describe an edit operation: '{title}'")

    # Steps inject raw title as entity name
    for s in steps:
        action = s.get("action", "")
        if "identify an existing" in action.lower():
            after = re.sub(r".*identify an existing ", "", action.lower())
            if len(after) > 40 and "verify" not in after:
                problems.append(f"Step {s['n']}: Entity name in step is raw title text, not a real record type ('{action[:80]}...')")

    # Should have pre-fill verification
    has_prefill = any("pre-fill" in a or "pre-populated" in a or "current value" in a or "existing" in a for a in step_actions)
    if not has_prefill:
        problems.append("No step verifying existing values are pre-populated in edit form")

    # Should have a save/update step
    has_save = any("save" in a or "update" in a or "submit" in a for a in step_actions)
    if not has_save:
        problems.append("No Save/Update step in edit test")

    for s in steps:
        if is_vague_expected(s.get("expected", "")):
            problems.append(f"Step {s['n']}: Vague expected: '{s['expected']}'")

    if not problems:
        verdict = "Pass"
    elif len(problems) <= 2:
        verdict = "Needs Work"
    else:
        verdict = "Fail"
    return verdict, problems


def verdict_error_validation(case):
    problems = []
    steps = get_steps(case)
    title = case.get("title", "")

    step_actions = [s.get("action", "").lower() for s in steps]

    # Title-to-step alignment: error_validation cases should test that invalid input is rejected
    # But some error_validation cases are about resilience ("camera tiles remain unaffected when another tile fails")
    is_form_validation = any(w in title.lower() for w in ["invalid", "empty", "required", "accepted", "earlier than", "longer than", "exceeds", "cannot", "not accepted"])
    is_resilience = any(w in title.lower() for w in ["unaffected", "fail", "error", "offline", "timeout", "recover"])

    if is_resilience and not is_form_validation:
        # These are better classified as performance_resilience
        problems.append("MISCLASSIFICATION: Title describes resilience/error-handling, not form validation. Template applies form validation steps that don't match the scenario")
        # Check that steps follow form validation template
        has_invalid_input = any("enter invalid" in a for a in step_actions)
        if has_invalid_input:
            problems.append("Steps instruct 'Enter invalid data' but the test is about a camera failure scenario - cannot manually trigger a camera failure this way")

    # "The invalid input is accepted into the field" - wrong expected for invalid input step
    for s in steps:
        if "enter invalid" in s.get("action", "").lower():
            if "accepted into the field" in s.get("expected", "").lower():
                problems.append(f"Step {s['n']}: Expected says 'invalid input is ACCEPTED into the field' - this is confusing; should say 'field accepts the typed value' to distinguish input entry from validation acceptance")

    # Check precondition placement
    for s in steps:
        if s.get("n", 0) > 3 and "set up precondition" in s.get("action", "").lower():
            problems.append(f"Step {s['n']}: Precondition setup appears after verification steps")

    for s in steps:
        if is_vague_expected(s.get("expected", "")):
            problems.append(f"Step {s['n']}: Vague expected: '{s['expected']}'")

    if not problems:
        verdict = "Pass"
    elif len(problems) <= 2:
        verdict = "Needs Work"
    else:
        verdict = "Fail"
    return verdict, problems


def verdict_search_filter(case):
    problems = []
    steps = get_steps(case)
    case.get("title", "")  # kept for its effect

    step_actions = [s.get("action", "").lower() for s in steps]

    # Step 6 injects title into search criteria description - vague
    for s in steps:
        action = s.get("action", "")
        if "enter the search criteria" in action.lower():
            # Check if the actual search value is specified
            after = re.sub(r".*enter the search criteria or select the filter option for ", "", action.lower())
            if len(after) > 30 and ("filter" in after or "search" in after or "hide" in after):
                problems.append(f"Step {s['n']}: Search criteria is described by injecting the title rather than specifying the actual search value or filter option")

    # "on entered text" as precondition is awkward
    for s in steps:
        if "set up precondition" in s.get("action", "").lower() and "entered text" in s.get("action", "").lower():
            problems.append(f"Step {s['n']}: 'Precondition: on entered text' is not a setup action - the text input is part of the test body, not a precondition")

    # Should verify results count changes
    has_count = any("count" in a for a in step_actions)
    if not has_count:
        problems.append("No step verifying result count changed after search/filter")

    # Should verify clearing restores full list
    has_clear = any("clear" in a for a in step_actions)
    if not has_clear:
        problems.append("No step to clear filter and verify full list returns")

    for s in steps:
        if is_vague_expected(s.get("expected", "")):
            problems.append(f"Step {s['n']}: Vague expected: '{s['expected']}'")

    if not problems:
        verdict = "Pass"
    elif len(problems) <= 2:
        verdict = "Needs Work"
    else:
        verdict = "Fail"
    return verdict, problems


def verdict_button_control(case):
    problems = []
    steps = get_steps(case)
    title = case.get("title", "")

    step_actions = [s.get("action", "").lower() for s in steps]

    # Step 5 says "Click or interact with the control" - but doesn't say what clicking does
    for s in steps:
        if "click or interact with the control" in s.get("action", "").lower():
            expected = s.get("expected", "")
            if "responds to the interaction" in expected.lower():
                problems.append(f"Step {s['n']}: Expected 'control responds to the interaction' is too vague - should specify what happens when the button is clicked")

    # Step 6 expected often duplicates step action
    for s in steps:
        if steps_identical_action_expected(s) and s.get("action", "").strip():
            problems.append(f"Step {s['n']}: Action and expected result are identical text (template variable leak or copy-paste error)")

    # Check for "on hover" precondition appended at end
    for s in steps:
        if "set up precondition" in s.get("action", "").lower() and "hover" in s.get("action", "").lower():
            problems.append(f"Step {s['n']}: Hover precondition appended after test body - hover should be a test action step, not a postcondition")

    # Button visibility title vs interaction steps - misalignment
    if "is visible" in title.lower() and not any("visible" in a or "displayed" in a for a in step_actions):
        problems.append("Title says button 'is visible' but no visibility assertion in steps")

    for s in steps:
        if is_vague_expected(s.get("expected", "")):
            problems.append(f"Step {s['n']}: Vague expected: '{s['expected']}'")

    if not problems:
        verdict = "Pass"
    elif len(problems) <= 2:
        verdict = "Needs Work"
    else:
        verdict = "Fail"
    return verdict, problems


def verdict_interaction(case):
    problems = []
    steps = get_steps(case)
    case.get("title", "")  # kept for its effect

    # Step 5 often has identical action/expected
    for s in steps:
        if steps_identical_action_expected(s) and s.get("action", "").strip():
            problems.append(f"Step {s['n']}: Action equals expected (template variable leak)")

    # "on clicking Refresh" appended as precondition at end - should be in test body
    for s in steps:
        if "set up precondition" in s.get("action", "").lower() and s.get("n", 0) > 4:
            problems.append(f"Step {s['n']}: Precondition appended after verification steps - should be set up before interaction")

    # Step 4 says "Locate the target UI element for [partial title]" - truncated title used as element name
    for s in steps:
        if "locate the target ui element for" in s.get("action", "").lower():
            after = re.sub(r".*locate the target ui element for ", "", s.get("action", "").lower())
            if len(after) > 5 and not any(w in after for w in ["button", "icon", "link", "field", "panel", "tab", "menu", "dropdown"]):
                problems.append(f"Step {s['n']}: Element to locate is identified by truncated test title, not a UI element name ('{s.get('action', '')[:80]}')")

    for s in steps:
        if is_vague_expected(s.get("expected", "")):
            problems.append(f"Step {s['n']}: Vague expected: '{s['expected']}'")

    if not problems:
        verdict = "Pass"
    elif len(problems) <= 2:
        verdict = "Needs Work"
    else:
        verdict = "Fail"
    return verdict, problems


def verdict_playback_media(case):
    problems = []
    steps = get_steps(case)
    title = case.get("title", "")

    step_actions = [s.get("action", "").lower() for s in steps]

    # Title-to-step alignment: "horizontal scrollbar" is a UI test, not a media playback test
    if "scrollbar" in title.lower() or "layout" in title.lower() or "ui" in title.lower():
        problems.append("MISCLASSIFICATION: Title is about UI layout/scrollbar, but 'playback_media' template is applied with video streaming steps")
        has_media_step = any("video" in a or "stream" in a or "audio" in a or "playback" in a for a in step_actions)
        if has_media_step:
            problems.append("Steps reference video/stream/playback but title is about scrollbar visibility - mismatched steps")

    # Step 5 action/expected identical check
    for s in steps:
        if steps_identical_action_expected(s) and s.get("action", "").strip():
            problems.append(f"Step {s['n']}: Action equals expected (template variable leak)")

    # Playback test should have a media source selection step
    has_camera_select = any("camera" in a or "media source" in a for a in step_actions)
    if not has_camera_select:
        problems.append("No step to select camera or media source before playback")

    for s in steps:
        if is_vague_expected(s.get("expected", "")):
            problems.append(f"Step {s['n']}: Vague expected: '{s['expected']}'")

    if not problems:
        verdict = "Pass"
    elif len(problems) <= 2:
        verdict = "Needs Work"
    else:
        verdict = "Fail"
    return verdict, problems


def verdict_playwright(case):
    """Playwright cases have real steps extracted from actual tests."""
    problems = []
    steps = get_steps(case)
    case.get("title", "")  # kept for its effect
    module = case.get("module_name", "")

    # Last step often has identical action/expected
    if steps:
        last = steps[-1]
        if steps_identical_action_expected(last) and last.get("action", "").strip():
            problems.append(f"Step {last['n']} (last): Action equals expected - likely generated from Playwright assertion label, not manually written")

    # Step specificity: Playwright steps should be specific
    for s in steps:
        action = s.get("action", "")
        expected = s.get("expected", "")
        if "verify" in action.lower() and "verify" in expected.lower() and action.strip().lower() == expected.strip().lower():
            problems.append(f"Step {s['n']}: Circular verification - action and expected are the same verification statement")

    # Check for vague expected
    for s in steps:
        if is_vague_expected(s.get("expected", "")):
            problems.append(f"Step {s['n']}: Vague expected: '{s['expected']}'")

    # Navigation step alignment
    if len(steps) >= 2:
        nav_ref = extract_nav_module(steps[1])
        if nav_ref:
            module_words = set(re.sub(r"[^a-z0-9 ]", "", module.lower()).split()) - {"the", "a", "an"}
            nav_words = set(re.sub(r"[^a-z0-9 ]", "", nav_ref.lower()).split()) - {"the", "a", "an"}
            if module_words and not (module_words & nav_words):
                problems.append(f"Step 2 navigates to '{nav_ref}' but module is '{module}'")

    if not problems:
        verdict = "Pass"
    elif len(problems) <= 1:
        verdict = "Needs Work"
    else:
        verdict = "Fail"
    return verdict, problems


def verdict_element_state(case):
    problems = []
    steps = get_steps(case)
    case.get("title", "")  # kept for its effect
    step_actions = [s.get("action", "").lower() for s in steps]

    # Should inspect current state
    has_inspect = any("inspect" in a or "state" in a or "check" in a or "is selected" in a or "is active" in a for a in step_actions)
    if not has_inspect:
        problems.append("No step to inspect or verify the element's current state")

    for s in steps:
        if is_vague_expected(s.get("expected", "")):
            problems.append(f"Step {s['n']}: Vague expected: '{s['expected']}'")

    if steps and len(steps) < 4:
        problems.append(f"Only {len(steps)} steps - too shallow for state verification")

    if not problems:
        verdict = "Pass"
    elif len(problems) <= 1:
        verdict = "Needs Work"
    else:
        verdict = "Fail"
    return verdict, problems


def verdict_field_input(case):
    problems = []
    steps = get_steps(case)
    case.get("title", "")  # kept for its effect
    step_actions = [s.get("action", "").lower() for s in steps]

    # Step 5 often injects entire title as test value
    for s in steps:
        if "enter the test value described: verify " in s.get("action", "").lower():
            problems.append(f"Step {s['n']}: 'Enter the test value described: Verify [title]' is not actionable - what specific value should be entered?")

    # Should specify what input to test
    has_specific_input = any(
        ("enter" in a or "type" in a or "input" in a) and len(a) > 20 and "verify" not in a[:10]
        for a in step_actions
    )
    if not has_specific_input:
        problems.append("No step specifying what specific value to enter in the field")

    # Blur/tab validation
    has_blur = any("tab out" in a or "blur" in a or "click elsewhere" in a for a in step_actions)
    if not has_blur:
        problems.append("No blur/tab-out step to trigger inline validation")

    for s in steps:
        if is_vague_expected(s.get("expected", "")):
            problems.append(f"Step {s['n']}: Vague expected: '{s['expected']}'")

    if not problems:
        verdict = "Pass"
    elif len(problems) <= 2:
        verdict = "Needs Work"
    else:
        verdict = "Fail"
    return verdict, problems


def verdict_chat_message(case):
    problems = []
    steps = get_steps(case)
    title = case.get("title", "")
    step_actions = [s.get("action", "").lower() for s in steps]

    # Title-to-step alignment: "camera tile displays error message" is NOT a chat message test
    if "error message" in title.lower() or "camera" in title.lower() or "tile" in title.lower():
        problems.append("CRITICAL MISCLASSIFICATION: Title describes a camera error display, not a chat/messaging feature. Chat template (message input, send, chat thread) is completely misaligned")
        has_chat = any("chat" in a or "message input" in a or "conversation" in a for a in step_actions)
        if has_chat:
            problems.append("Steps include chat panel and message sending - irrelevant to camera tile error display")

    # Precondition appended at end
    for s in steps:
        if s.get("n", 0) > 4 and "set up precondition" in s.get("action", "").lower():
            problems.append(f"Step {s['n']}: Precondition appended after test body")

    for s in steps:
        if is_vague_expected(s.get("expected", "")):
            problems.append(f"Step {s['n']}: Vague expected: '{s['expected']}'")

    if not problems:
        verdict = "Pass"
    elif len(problems) <= 2:
        verdict = "Needs Work"
    else:
        verdict = "Fail"
    return verdict, problems


def verdict_data_display(case):
    problems = []
    steps = get_steps(case)
    case.get("title", "")  # kept for its effect
    step_actions = [s.get("action", "").lower() for s in steps]

    # Should verify data is not placeholder
    has_data_check = any("n/a" in a or "loading" in a or "placeholder" in a or "not empty" in a for a in step_actions)
    if not has_data_check:
        problems.append("No step verifying data is not empty/placeholder")

    # Should verify data format
    has_format = any("format" in a or "formatted" in a for a in step_actions)
    if not has_format:
        problems.append("No step verifying data is formatted correctly")

    # Identical action/expected in last verification step
    for s in steps:
        if steps_identical_action_expected(s) and s.get("action", "").strip():
            problems.append(f"Step {s['n']}: Action equals expected")

    for s in steps:
        if is_vague_expected(s.get("expected", "")):
            problems.append(f"Step {s['n']}: Vague expected: '{s['expected']}'")

    if not problems:
        verdict = "Pass"
    elif len(problems) <= 2:
        verdict = "Needs Work"
    else:
        verdict = "Fail"
    return verdict, problems


def verdict_data_transfer(case):
    problems = []
    steps = get_steps(case)
    title = case.get("title", "")

    # Title injected into steps repeatedly
    title_frag = title.replace("Verify ", "").lower()
    title_in_steps = sum(1 for s in steps if title_frag[:20] in s.get("action", "").lower())
    if title_in_steps >= 3:
        problems.append(f"Title fragment injected into {title_in_steps} step actions - repetitive and non-specific")

    # Should have a step verifying the file/data received is correct
    has_content_check = any("correct and complete" in s.get("expected", "").lower() or "matches the source" in s.get("expected", "").lower() for s in steps)
    if not has_content_check:
        problems.append("No step verifying the transferred file/data content is correct")

    # Destination accessibility check
    has_dest_check = any("accessed at the destination" in s.get("expected", "").lower() or "file opens correctly" in s.get("expected", "").lower() for s in steps)
    if not has_dest_check:
        problems.append("No step verifying transfer destination is accessible")

    for s in steps:
        if is_vague_expected(s.get("expected", "")):
            problems.append(f"Step {s['n']}: Vague expected: '{s['expected']}'")

    if not problems:
        verdict = "Pass"
    elif len(problems) <= 2:
        verdict = "Needs Work"
    else:
        verdict = "Fail"
    return verdict, problems


def verdict_drawing_zone(case):
    problems = []
    steps = get_steps(case)
    title = case.get("title", "")
    step_actions = [s.get("action", "").lower() for s in steps]

    # Title-to-step alignment: PTZ controls are NOT drawing zones
    if "ptz" in title.lower() or "arrow" in title.lower() or "directional" in title.lower() or "moves" in title.lower():
        problems.append("MISCLASSIFICATION: Title describes PTZ camera controls, not a drawing zone. Template applies drawing tool steps (line, zone, crosshair) which are irrelevant")
        has_draw_steps = any("drawing tool" in a or "crosshair" in a or "draw" in a for a in step_actions)
        if has_draw_steps:
            problems.append("Steps include drawing tool activation - irrelevant to PTZ directional controls")

    for s in steps:
        if is_vague_expected(s.get("expected", "")):
            problems.append(f"Step {s['n']}: Vague expected: '{s['expected']}'")

    if not problems:
        verdict = "Pass"
    elif len(problems) <= 2:
        verdict = "Needs Work"
    else:
        verdict = "Fail"
    return verdict, problems


def verdict_logging_audit(case):
    problems = []
    steps = get_steps(case)
    title = case.get("title", "")
    step_actions = [s.get("action", "").lower() for s in steps]

    # Precondition appended at end
    for s in steps:
        if s.get("n", 0) > 4 and "set up precondition" in s.get("action", "").lower():
            problems.append(f"Step {s['n']}: Precondition (session timeout) appended after verification - should be set up before navigating to audit log")

    # Should verify specific log entry fields
    has_specifics = any("action type" in s.get("expected", "").lower() or "timestamp" in s.get("expected", "").lower() or "user" in s.get("expected", "").lower() for s in steps)
    if not has_specifics:
        problems.append("No step verifying specific log entry fields (action type, user, timestamp)")

    # The trigger action for "session timeout" cannot be manually done via a button click
    if "session timeout" in title.lower():
        has_timeout_setup = any("wait" in a or "timeout" in a or "idle" in a for a in step_actions)
        if not has_timeout_setup:
            problems.append("Session timeout test has no step to trigger or simulate the timeout condition")

    for s in steps:
        if is_vague_expected(s.get("expected", "")):
            problems.append(f"Step {s['n']}: Vague expected: '{s['expected']}'")

    if not problems:
        verdict = "Pass"
    elif len(problems) <= 2:
        verdict = "Needs Work"
    else:
        verdict = "Fail"
    return verdict, problems


def verdict_performance_resilience(case):
    problems = []
    steps = get_steps(case)
    case.get("title", "")  # kept for its effect
    step_actions = [s.get("action", "").lower() for s in steps]

    # Step 4 injects title as "stress condition"
    for s in steps:
        if "introduce the stress condition: verify " in s.get("action", "").lower():
            problems.append(f"Step {s['n']}: 'Introduce the stress condition: Verify [title]' is not actionable - how many times? What tool? What timing?")

    # Should have measurable performance criteria
    has_metrics = any("ms" in s.get("expected", "").lower() or "second" in s.get("expected", "").lower() or "threshold" in s.get("expected", "").lower() or "benchmark" in s.get("expected", "").lower() for s in steps)
    if not has_metrics:
        problems.append("No measurable performance threshold specified in expected results")

    # Recovery check
    has_recovery = any("recover" in a for a in step_actions)
    if not has_recovery:
        problems.append("No step verifying the application recovers after the stress condition")

    for s in steps:
        if is_vague_expected(s.get("expected", "")):
            problems.append(f"Step {s['n']}: Vague expected: '{s['expected']}'")

    if not problems:
        verdict = "Pass"
    elif len(problems) <= 2:
        verdict = "Needs Work"
    else:
        verdict = "Fail"
    return verdict, problems


def verdict_persistence(case):
    problems = []
    steps = get_steps(case)
    case.get("title", "")  # kept for its effect
    step_actions = [s.get("action", "").lower() for s in steps]

    # Should have refresh + navigate away + navigate back
    has_refresh = any("refresh" in a for a in step_actions)
    has_nav_away = any("navigate away" in a or "different page" in a for a in step_actions)
    has_nav_back = any("navigate back" in a for a in step_actions)

    if not has_refresh:
        problems.append("No page refresh step to verify persistence")
    if not has_nav_away:
        problems.append("No navigate-away step for full persistence verification")
    if not has_nav_back:
        problems.append("No navigate-back step to confirm persistence after navigation")

    for s in steps:
        if is_vague_expected(s.get("expected", "")):
            problems.append(f"Step {s['n']}: Vague expected: '{s['expected']}'")

    if not problems:
        verdict = "Pass"
    elif len(problems) <= 2:
        verdict = "Needs Work"
    else:
        verdict = "Fail"
    return verdict, problems


def verdict_reset_default(case):
    problems = []
    steps = get_steps(case)
    title = case.get("title", "")
    step_actions = [s.get("action", "").lower() for s in steps]

    # Title-to-step alignment: "hiding favorites hides non-favorite presets" is a filter action, not reset/default
    if "hiding" in title.lower() or "filter" in title.lower() or "search" in title.lower():
        problems.append("MISCLASSIFICATION: Title describes a filter/hide action, not a reset-to-default operation. Reset template steps don't match")

    # Should have a specific reset button or action
    has_reset_action = any("reset" in a or "default" in a or "revert" in a or "restore" in a for a in step_actions)
    if not has_reset_action:
        problems.append("No explicit reset/revert/default button action step")

    for s in steps:
        if is_vague_expected(s.get("expected", "")):
            problems.append(f"Step {s['n']}: Vague expected: '{s['expected']}'")

    if not problems:
        verdict = "Pass"
    elif len(problems) <= 2:
        verdict = "Needs Work"
    else:
        verdict = "Fail"
    return verdict, problems


def verdict_schedule_time(case):
    problems = []
    steps = get_steps(case)
    case.get("title", "")  # kept for its effect

    # Step 4 injects title as configuration value - not actionable
    for s in steps:
        if "configure the schedule or time value: verify " in s.get("action", "").lower():
            problems.append(f"Step {s['n']}: 'Configure the schedule or time value: Verify [title]' - embeds test title as the value to configure. Not actionable")

    # Should verify saved schedule is correct
    has_display_check = any("displayed correctly" in s.get("expected", "").lower() for s in steps)
    if not has_display_check:
        problems.append("No step verifying the saved schedule is displayed correctly in the UI")

    for s in steps:
        if is_vague_expected(s.get("expected", "")):
            problems.append(f"Step {s['n']}: Vague expected: '{s['expected']}'")

    if not problems:
        verdict = "Pass"
    elif len(problems) <= 2:
        verdict = "Needs Work"
    else:
        verdict = "Fail"
    return verdict, problems


def verdict_ui_integrity(case):
    problems = []
    steps = get_steps(case)
    case.get("title", "")  # kept for its effect
    step_actions = [s.get("action", "").lower() for s in steps]

    # "without overlap" as precondition at end is a test condition, not a setup step
    for s in steps:
        if "set up precondition" in s.get("action", "").lower() and "overlap" in s.get("action", "").lower():
            problems.append(f"Step {s['n']}: 'Precondition: without overlap' is actually a verification criterion, not a setup step - it should be part of the assertion")

    # Should check multiple viewports
    has_resize = any("resize" in a or "viewport" in a or "window" in a for a in step_actions)
    if not has_resize:
        problems.append("No responsive/viewport check for UI integrity test")

    # Should verify text readability
    has_text_check = any("text" in a and ("readable" in a or "truncat" in a or "legible" in a) for a in step_actions)
    if not has_text_check:
        problems.append("No step verifying text legibility/readability")

    for s in steps:
        if is_vague_expected(s.get("expected", "")):
            problems.append(f"Step {s['n']}: Vague expected: '{s['expected']}'")

    if not problems:
        verdict = "Pass"
    elif len(problems) <= 2:
        verdict = "Needs Work"
    else:
        verdict = "Fail"
    return verdict, problems


def verdict_curated(case):
    """Curated cases are hand-crafted - evaluate with stricter standards."""
    problems = []
    steps = get_steps(case)
    case.get("title", "")  # kept for its effect

    # Curated should be very specific
    for s in steps:
        if is_vague_expected(s.get("expected", "")):
            problems.append(f"Step {s['n']}: Vague expected in curated case: '{s['expected']}'")
        if steps_identical_action_expected(s) and s.get("action", "").strip():
            problems.append(f"Step {s['n']}: Action equals expected in curated case")

    if len(steps) < 3:
        problems.append(f"Only {len(steps)} steps in curated case - insufficient")

    if not problems:
        verdict = "Pass"
    elif len(problems) <= 1:
        verdict = "Needs Work"
    else:
        verdict = "Fail"
    return verdict, problems


# Map classification -> verdict function
VERDICT_FNS = {
    "navigation": verdict_navigation,
    "element_visibility": verdict_element_visibility,
    "configure_set": verdict_configure_set,
    "auth": verdict_auth,
    "create": verdict_create,
    "delete": verdict_delete,
    "edit": verdict_edit,
    "error_validation": verdict_error_validation,
    "search_filter": verdict_search_filter,
    "button_control": verdict_button_control,
    "interaction": verdict_interaction,
    "playback_media": verdict_playback_media,
    "playwright": verdict_playwright,
    "element_state": verdict_element_state,
    "field_input": verdict_field_input,
    "chat_message": verdict_chat_message,
    "data_display": verdict_data_display,
    "data_transfer": verdict_data_transfer,
    "drawing_zone": verdict_drawing_zone,
    "logging_audit": verdict_logging_audit,
    "performance_resilience": verdict_performance_resilience,
    "persistence": verdict_persistence,
    "reset_default": verdict_reset_default,
    "schedule_time": verdict_schedule_time,
    "ui_integrity": verdict_ui_integrity,
    "curated": verdict_curated,
}

SAMPLE_SIZE = 10
sample_audits = {}
verdict_summary = Counter()

for cls in ALL_CLASSIFICATIONS:
    cases_in_cls = by_classification[cls]
    sample = random.sample(cases_in_cls, min(SAMPLE_SIZE, len(cases_in_cls)))
    fn = VERDICT_FNS.get(cls)
    cls_audits = []
    for case in sample:
        if fn:
            verdict, problems = fn(case)
        else:
            verdict, problems = "Needs Work", ["No classification-specific verdict function defined"]
        verdict_summary[verdict] += 1
        cls_audits.append({
            "case_key": case["case_key"],
            "title": case["title"],
            "module": case.get("module_name"),
            "step_count": case.get("step_count", len(get_steps(case))),
            "verdict": verdict,
            "issues": problems,
        })
    sample_audits[cls] = cls_audits

total_sampled = sum(len(v) for v in sample_audits.values())
print(f"\n  Sampled {total_sampled} cases across {len(ALL_CLASSIFICATIONS)} classifications")
print(f"  Verdicts: {dict(verdict_summary)}")

# ---------------------------------------------------------------------------
# AGGREGATE STATISTICS
# ---------------------------------------------------------------------------
print("\nComputing aggregate statistics ...")

# Deduplicate wrong_nav_module issues (only report each case once)
# and compute per-case issue counts
issues_per_case = defaultdict(set)
for issue_type, lst in issues.items():
    for item in lst:
        issues_per_case[item["case_key"]].add(issue_type)

cases_with_any_issue = len(issues_per_case)
cases_clean = len(ALL_CASES) - cases_with_any_issue

# Step count distribution
step_counts = Counter(case.get("step_count", len(get_steps(case))) for case in ALL_CASES)

# Vague expected - unique cases
vague_cases = len(set(i["case_key"] for i in issues["vague_expected"]))

# Navigation mismatch - this is a broad check; separate truly wrong from borderline
nav_mismatches = issues["wrong_nav_module"]
nav_mismatch_cases = len(set(i["case_key"] for i in nav_mismatches))

# Identical action/expected - unique cases
identical_cases = len(set(i["case_key"] for i in issues["identical_action_expected"]))

# Duplicate step text - unique cases
dup_step_cases = len(set(i["case_key"] for i in issues["duplicate_step_text"]))

# No login step 1 - unique cases
no_login_cases = len(issues["no_login_first_step"])

# Too few steps
too_few_cases = len(issues["too_few_steps"])

# Template leak
template_leak_cases = len(set(i["case_key"] for i in issues["template_leak"]))

# ---------------------------------------------------------------------------
# SYSTEMIC PATTERNS - cross-cutting issues beyond per-case scans
# ---------------------------------------------------------------------------
print("Identifying systemic patterns ...")

# Pattern 1: Precondition injected at end in generated cases
precondition_at_end = []
for case in ALL_CASES:
    if case.get("step_source") != "generated":
        continue
    steps = get_steps(case)
    for s in steps:
        if s.get("n", 0) > 3 and "set up precondition" in s.get("action", "").lower():
            precondition_at_end.append(case["case_key"])
            break

# Pattern 2: Steps that inject raw title text
title_injected_in_steps = []
for case in ALL_CASES:
    title = case.get("title", "").lower().replace("verify ", "")
    steps = get_steps(case)
    for s in steps:
        action = s.get("action", "").lower()
        # Look for title fragment (first 25 chars) in step action
        if len(title) > 20 and title[:25] in action and "navigate" not in action:
            title_injected_in_steps.append(case["case_key"])
            break

# Pattern 3: Misclassification - template class doesn't match test intent
misclassified = []
misclass_reasons = {
    "chat_message": "Camera error display cases misclassified as chat",
    "drawing_zone": "PTZ control cases misclassified as drawing zones",
    "playback_media": "UI layout/scrollbar cases misclassified as playback",
    "delete": "Search/filter/toggle cases misclassified as delete",
    "reset_default": "Filter/hide cases misclassified as reset-to-default",
    "create": "Negative/duplicate-prevention tests use create template",
}
for cls, reason in misclass_reasons.items():
    for case in by_classification.get(cls, []):
        title = case.get("title", "").lower()
        # Spot-check for known patterns
        if (cls == "chat_message" and ("error message" in title or "camera tile" in title or "tile" in title)) or (cls == "drawing_zone" and ("ptz" in title or "directional" in title or "arrow" in title or "moves camera" in title)) or (cls == "playback_media" and ("scrollbar" in title or "layout" in title or "ui" in title or "align" in title or "visible" in title)) or (cls == "delete" and ("clearing" in title or "unchecking" in title or "hiding" in title or "restores" in title)) or (cls == "reset_default" and ("hiding" in title or "filter" in title or "search" in title)) or (cls == "create" and ("cannot be added twice" in title or "duplicate" in title or "same" in title)):
            misclassified.append({"case_key": case["case_key"], "title": case["title"], "classification": cls, "reason": reason})

print(f"  Precondition-at-end pattern: {len(precondition_at_end)} cases")
print(f"  Title injected in steps: {len(title_injected_in_steps)} cases")
print(f"  Misclassified cases detected: {len(misclassified)}")

# ---------------------------------------------------------------------------
# SEVERITY RATINGS
# ---------------------------------------------------------------------------
SEVERITY_MAP = {
    "vague_expected": "High",           # Blocks test execution verification
    "identical_action_expected": "High",  # Template variable leak
    "wrong_nav_module": "Medium",        # May be false positives
    "too_few_steps": "High",
    "no_login_first_step": "Low",        # Auth cases intentionally start differently
    "duplicate_step_text": "Medium",
    "template_leak": "Critical",
}

# ---------------------------------------------------------------------------
# BUILD FINAL REPORT
# ---------------------------------------------------------------------------
print("\nBuilding final audit report ...")

report = {
    "audit_metadata": {
        "audit_date": TODAY,
        "auditor": "independent_audit.py",
        "source_file": str(MASTER_JSON),
        "total_cases_in_repo": len(ALL_CASES),
        "classifications_audited": len(ALL_CLASSIFICATIONS),
        "sample_size_per_classification": SAMPLE_SIZE,
        "total_cases_sampled": total_sampled,
        "random_seed": 42,
    },
    "executive_summary": {
        "total_cases": len(ALL_CASES),
        "cases_with_at_least_one_issue": cases_with_any_issue,
        "cases_clean": cases_clean,
        "issue_rate_pct": round(cases_with_any_issue / len(ALL_CASES) * 100, 1),
        "sample_verdict_counts": dict(verdict_summary),
        "sample_pass_rate_pct": round(verdict_summary["Pass"] / total_sampled * 100, 1),
        "sample_needs_work_rate_pct": round(verdict_summary["Needs Work"] / total_sampled * 100, 1),
        "sample_fail_rate_pct": round(verdict_summary["Fail"] / total_sampled * 100, 1),
    },
    "programmatic_scan_results": {
        "A_vague_expected_results": {
            "severity": SEVERITY_MAP["vague_expected"],
            "description": "Steps whose expected result contains 'functions correctly', 'works as expected', etc. without specifying what that means",
            "unique_cases_affected": vague_cases,
            "total_occurrences": len(issues["vague_expected"]),
            "sample": issues["vague_expected"][:20],
        },
        "B_identical_action_and_expected": {
            "severity": SEVERITY_MAP["identical_action_expected"],
            "description": "Steps where action text == expected text (template variable leak)",
            "unique_cases_affected": identical_cases,
            "total_occurrences": len(issues["identical_action_expected"]),
            "sample": issues["identical_action_expected"][:20],
        },
        "C_navigation_module_mismatch": {
            "severity": SEVERITY_MAP["wrong_nav_module"],
            "description": "Navigation step references a path that does not contain the case's module name",
            "unique_cases_affected": nav_mismatch_cases,
            "total_occurrences": len(nav_mismatches),
            "note": "Some matches may be false positives where module name is an abbreviation or synonym",
            "sample": nav_mismatches[:20],
        },
        "D_too_few_steps": {
            "severity": SEVERITY_MAP["too_few_steps"],
            "description": "Cases with fewer than 4 steps - insufficient to verify the test title",
            "unique_cases_affected": too_few_cases,
            "total_occurrences": too_few_cases,
            "sample": issues["too_few_steps"][:20],
        },
        "E_no_login_first_step": {
            "severity": SEVERITY_MAP["no_login_first_step"],
            "description": "Cases where step 1 is not a login action (inconsistency vs. majority pattern)",
            "unique_cases_affected": no_login_cases,
            "total_occurrences": no_login_cases,
            "note": "Auth cases intentionally start with login page navigation rather than 'Log in with valid credentials' - these may be acceptable",
            "sample": issues["no_login_first_step"][:20],
        },
        "F_duplicate_step_text": {
            "severity": SEVERITY_MAP["duplicate_step_text"],
            "description": "Same action+expected text appears twice within a single case",
            "unique_cases_affected": dup_step_cases,
            "total_occurrences": len(issues["duplicate_step_text"]),
            "sample": issues["duplicate_step_text"][:20],
        },
        "G_template_variable_leak": {
            "severity": SEVERITY_MAP["template_leak"],
            "description": "Steps containing literal '{subject}' or '{predicate}' - unfilled template placeholders",
            "unique_cases_affected": template_leak_cases,
            "total_occurrences": len(issues["template_leak"]),
            "sample": issues["template_leak"][:10],
        },
    },
    "systemic_patterns": {
        "precondition_appended_at_end": {
            "description": "Generated cases append 'Set up precondition: [condition]' as a late step, after verification steps. Preconditions should appear before the test body.",
            "severity": "High",
            "cases_affected": len(precondition_at_end),
            "sample_case_keys": precondition_at_end[:30],
        },
        "title_injected_into_steps": {
            "description": "Step actions use the raw test title as the entity name or action description, making steps non-actionable for a QA engineer who must guess what entity to find",
            "severity": "High",
            "cases_affected": len(title_injected_in_steps),
            "sample_case_keys": title_injected_in_steps[:30],
        },
        "misclassification_wrong_template": {
            "description": "Cases where the assigned classification does not match the test intent, causing a completely wrong step template to be applied",
            "severity": "Critical",
            "cases_affected": len(misclassified),
            "examples": misclassified[:30],
        },
        "configure_set_save_step_ambiguity": {
            "description": "configure_set template step 7 'Save or confirm the configuration if a save action is required' does not specify WHERE to click or what button label to use",
            "severity": "Medium",
            "cases_affected": len(by_classification.get("configure_set", [])),
        },
        "delete_template_misapplied": {
            "description": "delete template steps (confirmation dialog, item count, 'Identify the X to be deleted') are applied to search/filter/toggle actions that don't involve deleting records",
            "severity": "High",
            "example_titles": [c["title"] for c in by_classification.get("delete", [])[:5]],
        },
        "create_template_entity_name_is_raw_title": {
            "description": "In create template, 'Verify the newly created [entity] appears' uses the full test title as the entity name (e.g. 'Verify the newly created selecting multiple maps adds them to different grid tiles appears') - unreadable and non-actionable",
            "severity": "High",
            "cases_affected": len(by_classification.get("create", [])),
        },
    },
    "sample_audit_by_classification": sample_audits,
    "step_count_distribution": {str(k): v for k, v in sorted(step_counts.items())},
    "all_issues_raw": {
        "vague_expected": issues["vague_expected"],
        "identical_action_expected": issues["identical_action_expected"],
        "wrong_nav_module": nav_mismatches,
        "too_few_steps": issues["too_few_steps"],
        "no_login_first_step": issues["no_login_first_step"],
        "duplicate_step_text": issues["duplicate_step_text"],
        "template_leak": issues["template_leak"],
    },
    "recommendations": [
        {
            "priority": "Critical",
            "issue": "Template misclassification",
            "recommendation": "Review classification logic in qatouch_step_generator.py. Cases about camera error display, PTZ controls, UI scrollbars, and search/filter are being assigned chat_message, drawing_zone, playback_media, and delete templates respectively. Add title keyword guards to prevent wrong template assignment.",
        },
        {
            "priority": "Critical",
            "issue": "Identical action and expected text (template variable leak)",
            "recommendation": f"Fix template rendering for {identical_cases} cases where the action and expected result are identical. This occurs when the title-derived variable substitution produces the same string for both fields.",
        },
        {
            "priority": "High",
            "issue": "Precondition steps appended at end",
            "recommendation": f"{len(precondition_at_end)} generated cases append 'Set up precondition: [condition]' as a late step after verification. Move preconditions to step 1.5 (after login/navigate, before test body). This requires a generator change.",
        },
        {
            "priority": "High",
            "issue": "Raw title text injected as entity/element names in steps",
            "recommendation": f"{len(title_injected_in_steps)} cases embed the full test title (or fragment) as the entity/element to interact with. Steps should name specific UI elements (button labels, field names) not test titles.",
        },
        {
            "priority": "High",
            "issue": "Vague expected results",
            "recommendation": f"{vague_cases} unique cases have expected results using vague language ('functions correctly', 'works as expected'). Replace with specific observable outcomes.",
        },
        {
            "priority": "High",
            "issue": "configure_set steps embed title as configuration value",
            "recommendation": "Step 5 of configure_set template says 'Apply the configuration change described: Verify [full title]' - not actionable. Replace with 'Click/toggle the [specific control name]' with the expected new state.",
        },
        {
            "priority": "Medium",
            "issue": "Navigation mismatch",
            "recommendation": f"Review {nav_mismatch_cases} cases where the navigation step path does not reference the module name. Verify these are genuine mismatches vs. module name abbreviations.",
        },
        {
            "priority": "Medium",
            "issue": "schedule_time template injects title as the time value",
            "recommendation": "Step 4 of schedule_time template says 'Configure the schedule or time value: Verify [title]' - the test title is not a time value. Specify what date/time/interval to configure.",
        },
        {
            "priority": "Medium",
            "issue": "performance_resilience lacks measurable thresholds",
            "recommendation": f"All {len(by_classification.get('performance_resilience', []))} performance cases have no quantitative expected results (response time, frame rate, etc.). Without thresholds, these tests cannot produce a binary pass/fail verdict.",
        },
        {
            "priority": "Low",
            "issue": "Auth test step 1 inconsistency",
            "recommendation": "Auth cases use 'Open the application login page' as step 1 while all other classifications use 'Log in to the application with valid credentials'. This is intentional for auth tests but documents a pattern difference that may confuse new engineers.",
        },
    ],
}

# ---------------------------------------------------------------------------
# Save output
# ---------------------------------------------------------------------------
print(f"\nSaving audit report to {OUTPUT_JSON} ...")
with open(OUTPUT_JSON, "w", encoding="utf-8") as f:
    json.dump(report, f, indent=2, ensure_ascii=False)

print(f"\n{'='*70}")
print("AUDIT COMPLETE - SUMMARY")
print(f"{'='*70}")
print(f"  Total cases audited:        {len(ALL_CASES)}")
print(f"  Cases with >=1 issue:       {cases_with_any_issue} ({report['executive_summary']['issue_rate_pct']}%)")
print(f"  Cases with no issues:       {cases_clean}")
print()
print(f"  Sample audit ({total_sampled} cases across {len(ALL_CLASSIFICATIONS)} classifications):")
print(f"    Pass:        {verdict_summary['Pass']} ({report['executive_summary']['sample_pass_rate_pct']}%)")
print(f"    Needs Work:  {verdict_summary['Needs Work']} ({report['executive_summary']['sample_needs_work_rate_pct']}%)")
print(f"    Fail:        {verdict_summary['Fail']} ({report['executive_summary']['sample_fail_rate_pct']}%)")
print()
print("  Programmatic scan findings:")
print(f"    A. Vague expected results:           {vague_cases} unique cases, {len(issues['vague_expected'])} occurrences")
print(f"    B. Identical action=expected:        {identical_cases} unique cases, {len(issues['identical_action_expected'])} occurrences")
print(f"    C. Navigation module mismatch:       {nav_mismatch_cases} unique cases")
print(f"    D. Too few steps (<4):               {too_few_cases} cases")
print(f"    E. Step 1 not a login:               {no_login_cases} cases")
print(f"    F. Duplicate step text:              {dup_step_cases} unique cases")
print(f"    G. Template variable leak:           {template_leak_cases} cases")
print()
print("  Systemic patterns:")
print(f"    Precondition appended at end:        {len(precondition_at_end)} cases")
print(f"    Title injected into step text:       {len(title_injected_in_steps)} cases")
print(f"    Misclassified (wrong template):      {len(misclassified)} cases detected")
print()
print(f"  Full report: {OUTPUT_JSON}")
print(f"{'='*70}")
