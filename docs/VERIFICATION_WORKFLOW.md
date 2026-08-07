# QA Test Verification Workflow

## What Is This?

Every automated test goes through a verification process before it becomes part of the official test suite. A QA tester watches the test run step-by-step, confirms each step does what it's supposed to, and either approves or rejects it.

**The goal**: No automated test runs in CI without a human QA verifying it actually tests the right thing.

---

## How It Works (The Big Picture)

```
DEVELOPER                          QA TESTER                        OPS HUB
─────────                          ─────────                        ───────
1. Writes test with
   step_capture.mark() calls
   + JSON sidecar file
         │
2. Runs: pytest --verify-mode
   (headless, generates evidence)
         │
3. Evidence auto-uploaded ─────────────────────────────────────-> 4. Test appears in
   to Ops Hub                                                      Review Queue
                                   5. QA sees pending test
                                      in Ops Hub queue.
                                      Copies the pytest command.
                                         │
                                   6. Runs on their machine:
                                      pytest --headed --slowmo 300
                                      --verify-mode --step-review
                                      -k "test_name"
                                         │
                                   7. Watches browser execute
                                      step-by-step with on-screen
                                      overlay labels.
                                      Terminal prompts per step:
                                      [Enter]=OK  [f]=Flag  [q]=Quit
                                         │
                                   8. Records final verdict ─────-> 9. Stored in DB
                                      in Ops Hub UI                  (approved/rejected
                                      (confirm or override            + per-step verdicts)
                                       terminal verdicts)                │
                                                                   10. Synced to repo:
10. Developer runs sync tool ←──────────────────────────────────       config/verification
         │                                                              _status.json
11. Reads rejection feedback,
    fixes test, re-submits
    ─── OR ───
    Test is approved -> part
    of the verified suite
```

---

## For Developers: Writing Verifiable Tests

### Step 1: Add `step_capture` to Your Test

Every test class setup fixture must accept `step_capture` and wire it to the page:

```python
@pytest.fixture(autouse=True)
def setup(self, authenticated_page, step_capture):
    self.page = authenticated_page
    self.step_capture = step_capture
    step_capture.set_page(self.page)
    self.views = ViewsPage(self.page)
    yield
```

For function-based tests (login, logout):
```python
def test_valid_login(authenticated_page, step_capture):
    step_capture.set_page(authenticated_page)
    # ...
```

### Step 2: Add `.mark()` Calls After Each Step

```python
def test_export_clip_to_media(self):
    self.step_capture.mark(1, "Navigate to Views and load camera into tile")
    self.views.navigate()
    self.views.add_first_camera_via_checkbox()

    self.step_capture.mark(2, "Click Clip icon to enter timeline selection mode")
    self.views.click_clip_icon()

    self.step_capture.mark(3, "Click Export and check Save to Media checkbox")
    self.views.click_export_from_clip_menu()
    self.views.check_save_to_media()
    self.views.click_export_button()

    self.step_capture.mark(4, "Verify Export Successful toast appears")
    self.views.wait_for_export_success()
```

**Rules for step descriptions:**
- Write for QA reviewers, not developers
- Present tense ("Click Export", not "Clicks Export" or "Clicked Export")
- Describe what the tester sees/does, not code internals
- One mark per logical step (group related actions)
- Call `.mark()` AFTER the action (screenshot captures the result)

### Step 3: Create the JSON Sidecar

Create a matching file at `tests/steps/ui/{module}/test_{name}.json`:

```json
{
  "test_file": "tests/ui/views/test_views_export_clip.py",
  "class": "TestViewsExportClip",
  "tests": {
    "test_export_clip_to_media": {
      "title": "Verify clip export with Save to Media",
      "case_key": "ABC123",
      "steps": [
        {
          "n": 1,
          "action": "Navigate to Views and load camera into tile",
          "expected": "Camera stream visible in tile"
        },
        {
          "n": 2,
          "action": "Click Clip icon to enter timeline selection mode",
          "expected": "Timeline selection mode activates with time markers"
        },
        {
          "n": 3,
          "action": "Click Export and check Save to Media checkbox",
          "expected": "Export starts processing, toast shows Exporting"
        },
        {
          "n": 4,
          "action": "Verify Export Successful toast appears",
          "expected": "Toast shows Export Successful"
        }
      ]
    }
  }
}
```

**Important**: The `action` text in the JSON must match the `description` text in `.mark()` calls.

### Step 4: Generate Evidence

```bash
pytest --verify-mode -k "test_export_clip_to_media" tests/ui/views/test_views_export_clip.py
```

This runs headless and produces:
- `verification_output/screenshots/ABC123_step1.png` (one per step)
- `verification_output/{test_id}.json` (evidence file with all step data)

### Step 5: Check Rejection Feedback

After QA reviews your test:

```bash
python tools/sync_verification_status.py
```

Then check `config/verification_status.json`:
- **verified** -> your test is approved
- **rejected** -> read `reject_reason` and `step_verdicts` to see what to fix
- **pending** -> QA hasn't reviewed it yet

---

## For QA Testers: Reviewing Tests

### Step 1: Find Tests to Review

Open the QA Ops Hub -> Verification page. Pending tests appear in the Review Queue.

### Step 2: Run the Test Locally (Headed + Step Review)

The Ops Hub shows the exact command. Copy and run it in your terminal:

```bash
pytest --headed --slowmo 300 --verify-mode --step-review -k "test_export_clip_to_media" tests/ui/views/test_views_export_clip.py
```

**What you'll see:**
- A Chrome browser opens and executes the test
- A green overlay appears at the top of the page at each step:
  `Step 1/4: Navigate to Views and load camera into tile`
- After each step, your terminal prompts you:

```
  ┌─ Step 1/4: Navigate to Views and load camera into tile
  │  Expected: Camera stream visible in tile
  └─ [Enter] = OK   [f] = Flag   [q] = Quit early
  >
```

### Step 3: Respond to Each Step

| Key | Meaning | When to use |
|-----|---------|-------------|
| **Enter** | Step looks correct | Browser shows the expected result |
| **f** | Flag this step | Something is wrong (prompts for a note) |
| **q** | Quit early | Test is clearly broken, no point continuing |

### Step 4: Record Final Verdict in Ops Hub

After the test finishes (or you quit early), go to the Ops Hub and submit the overall verdict:
- **Approve** - All steps correct, test is ready for the suite
- **Reject** - One or more steps wrong, include reason for the developer
- **Needs Review** - Uncertain, want someone else to look

---

## Run Modes Summary

| Command | When to use | What happens |
|---------|-------------|-------------|
| `pytest` | Normal test run | No verification. `step_capture.mark()` is a no-op. Zero overhead. |
| `pytest --verify-mode` | Generate evidence | Headless. Captures screenshots + evidence JSON per step. |
| `pytest --headed --verify-mode` | Watch execution | Headed browser with step overlays. No terminal prompts. |
| `pytest --headed --slowmo 300 --verify-mode --step-review` | **QA review** | Full review: headed browser + overlays + terminal prompts per step. |

**Safety guards:**
- `--step-review` without `--headed` -> automatically disabled (no browser to watch)
- `--step-review` in non-interactive terminal (CI) -> automatically disabled (no stdin for prompts)
- `--verify-mode` off -> everything is a no-op, zero performance impact

---

## Evidence JSON Format

Each test produces a JSON file in `verification_output/`:

```json
{
  "nodeid": "tests/ui/views/test_views_export_clip.py::TestViewsExportClip::test_export_clip_to_media",
  "case_key": "ABC123",
  "result": "passed",
  "duration_seconds": 12.5,
  "captured_at": "2026-03-15T12:00:00+00:00",
  "total_steps_defined": 4,
  "steps": [
    {
      "step": 1,
      "description": "Navigate to Views and load camera into tile",
      "expected": "Camera stream visible in tile",
      "screenshot": "verification_output/screenshots/ABC123_step1.png",
      "timestamp": 1710504000.0,
      "result": "passed"
    }
  ],
  "step_verdicts": [
    {"step": 1, "verdict": "ok", "note": ""},
    {"step": 2, "verdict": "ok", "note": ""},
    {"step": 3, "verdict": "flagged", "note": "Wrong panel opened"},
    {"step": 4, "verdict": "ok", "note": ""}
  ],
  "review_mode": "step_review"
}
```

The `step_verdicts` array is only present when `--step-review` was used. The `expected` field comes from the JSON sidecar step definitions.

---

## Verification Status File

`config/verification_status.json` tracks the current state of all reviewed tests:

```json
{
  "version": 1,
  "last_synced": "2026-03-15T12:00:00Z",
  "verified": {
    "tests/ui/views/...::test_export_clip": {
      "session_id": "VS-0005",
      "verified_by": "reviewer_name",
      "verified_at": "2026-03-15T12:00:00Z"
    }
  },
  "rejected": {
    "tests/ui/views/...::test_drag_camera": {
      "session_id": "VS-0005",
      "rejected_by": "reviewer_name",
      "reject_reason": "Step 3 opens wrong panel",
      "step_verdicts": [
        {"step": 1, "verdict": "ok"},
        {"step": 3, "verdict": "wrong", "note": "Wrong panel"}
      ]
    }
  },
  "pending": ["tests/ui/admin/...::test_page_loads"]
}
```

Sync with: `python tools/sync_verification_status.py`

---

## File Reference

| File | Purpose |
|------|---------|
| `plugins/verification_runner.py` | Core plugin: `--verify-mode`, `--step-review`, `StepCapture` fixture |
| `tests/steps/step_registry.py` | Loads step definitions from JSON sidecars |
| `tests/steps/ui/{module}/*.json` | Step definitions (action + expected per step) |
| `config/qatouch_case_mapping.json` | Maps test nodeids -> QA Touch case keys |
| `config/verification_status.json` | Exported verdicts from Ops Hub (synced) |
| `tools/sync_verification_status.py` | Pulls verdicts from Ops Hub -> local JSON |
| `verification_output/` | Evidence JSONs + screenshots (gitignored) |
