# QA Touch Import Pipeline - Operator Runbook

> **For NEW cases there is now a public API path.** QA Touch shipped
> `POST /api/v1/testCase/import` in July 2026. `tools/qatouch_csv_import.py`
> uses it: no browser, no session that expires, and multi-line steps split
> themselves so the step-splitter phase below is not needed. It is create-only,
> so the update and backfill phases here still apply. See
> `docs/QA_TOUCH_INTEGRATION.md`.


This is the Ops-facing runbook for the 5-phase pipeline that converts a
QA-authored xlsx into fully-populated QA Touch test cases with one quoted
canonical CSV in the middle and per-step rows at the end.

**Audience:** the pipeline operator (Ops/Justin). The QA team's job is
described in `qa_xlsx_import_template.md` - they just fill the spreadsheet.

**Why it has 5 phases:** the QA Touch CSV importer silently drops or rewrites
several fields (see `docs/local/qa_touch_integration.md:339-347`). Each phase has a clear
owner, a single command, and a verifiable artifact. Skipping a phase leaves a
specific, named gap that the next phase repairs - nothing is hidden.

---

## Quick reference - one full run

```bash
# Phase 0 - one-time setup per project (skip if already done)
#   - Create the four canonical tags in QA Touch UI: smoke, sanity, regression, future
#   - Record your projectKey (e.g. JlW1, 70l1, 60W5) - it's the alphanumeric
#     token in the QA Touch URL when viewing the project. You'll pass it
#     directly to phases 4 and 5 via --project-key. There is no alias config
#     file and no meta-fetch step.

# Phase 1 - QA fills tests/data/<release>_<module>_authored.xlsx (no operator action)

# Phase 2 - convert xlsx -> canonical CSV
python tools/qa_xlsx_to_qatouch_csv.py \
    --xlsx tests/data/<release>_<module>_authored.xlsx \
    --out  tests/data/<release>_<module>_canonical.csv

# Phase 3 - import the CSV via QA Touch UI (manual upload)

# Phase 4 - backfill metadata (Type, Reference, Tags, Mode, Description, Priority)
python tools/backfill_qa_touch_metadata.py \
    --csv tests/data/<release>_<module>_canonical.csv \
    --project-key <PROJECT_KEY>

# Phase 5 - split the merged Step 1 into per-step rows with last-step expected
python tools/qa_post_import_split_and_position.py \
    --project-key <PROJECT_KEY> \
    --csv tests/data/<release>_<module>_canonical.csv
```

Order matters. `2 -> 3 -> 4 -> 5`. Skipping 4 leaves Type=Regression, no
Reference, no Tags. Skipping 5 leaves one merged Step 1 per case. Both are
reversible by re-running.

---

## Phase 0 - One-time project setup

**Owner:** Ops. **Frequency:** once per new QA Touch project.

**Why:** the QA Touch CSV importer matches tags by exact label-string against
the project's tag dictionary (`docs/local/qa_touch_integration.md:342-343`). Tags that do
not exist in the dictionary are silently dropped at import - losing them from
the row entirely. We pre-create the four canonical tags so the importer accepts
them. The metadata backfill (phase 4) re-applies them anyway as defense in
depth, but pre-creating eliminates a class of silent loss.

**Steps:**

0a. In QA Touch UI -> Project Settings -> Tags, manually create the four
    canonical tags: `smoke`, `sanity`, `regression`, `future`.

0b. Record your projectKey. The projectKey is the alphanumeric token QA Touch
    shows in the URL when you open the project - e.g. open Tech App and the
    URL contains `/p/JlW1/`, so the key is `JlW1`. Known live keys:
    - `JlW1` - Tech App
    - `70l1` - Partner Admin
    - `60W5` - C2C
    Write it down (sticky note, ticket, top of your terminal - wherever). You
    will pass it as `--project-key <KEY>` to phases 4 and 5. There is no
    alias config file: the tools take the literal projectKey directly.

**Verify:** check QA Touch UI shows the four tags in Project Settings, and
that you have the projectKey written down somewhere you can paste from.

---

## Phase 1 - QA authors test cases

**Owner:** QA team. **Frequency:** ongoing per feature/release.

**Why:** QA writes test cases in a familiar Excel format. The author template
ships at `tools/templates/qa_author_template.xlsx` with the 15 canonical
column headers in row 1 (frozen, bold), three worked example rows
(Functional / Negative / Security), and a companion `INSTRUCTIONS` sheet
listing enum reference values and dos-and-don'ts. Regenerate the template
with `python tools/generate_qa_author_template.py` if you ever need to
rebuild it. The converter also accepts Family A/B/C in-the-wild header
variants via alias-resolution, so legacy sheets work without re-authoring.

**Steps:**

1a. QA copies `tools/templates/qa_author_template.xlsx` to
    `tests/data/<release>_<module>_authored.xlsx`.

1b. QA fills one row per test case using the canonical column set. See
    `qa_xlsx_import_template.md` for column meanings, accepted aliases, and
    dos/don'ts.

1c. QA commits the xlsx to `Soterix-WebApp-QA` and notifies Ops.

**Verify:** the file is present at `tests/data/<release>_<module>_authored.xlsx`
on the operator's checkout.

---

## Phase 2 - Convert xlsx -> canonical CSV

**Owner:** Ops. **Tool:** `tools/qa_xlsx_to_qatouch_csv.py`.

**Why:** produces the 15-column canonical CSV (proven by sitedevice_canonical,
distributor_canonical, ldap_canonical). The converter:

- Auto-detects the header row in rows 1-5 (handles Family A's banner-in-rows-1-3
  layout).
- Resolves QA's column names via the alias tables (Family A "Scenario",
  Family B "Module", Family C "Title" all work).
- Merges "Expected Result" + "Acceptance Criteria" columns into the single
  `Expected_result` field with a `\n\n` separator (never drops either).
- Emits ONLY the seven canonical Type enum values, so the importer's silent
  rewrite-to-Regression quirk never fires on our output.
- HTML-escapes literal `<` and `>` in Steps/Expected_result/Test Data/
  Precondition/Description (TR0028/TR0029 defense). Module_name's ` > `
  separator is preserved RAW because the importer needs it to nest modules.
- Emits Steps as one quoted RFC-4180 cell containing
  `Step 1: ...\nStep 2: ...\n...\nStep N: ...` with literal LF newlines.
  Expected_result mirrors step count, with `-` padding on steps 1..N-1 and the
  case-level expected on step N. This is the pre-stage for phase 5.
- FAILS LOUD if any required field cannot be resolved - never silently skips
  rows.

**Steps:**

2a. Run the converter:
    ```bash
    python tools/qa_xlsx_to_qatouch_csv.py \
        --xlsx tests/data/<release>_<module>_authored.xlsx \
        --out  tests/data/<release>_<module>_canonical.csv
    ```

2b. If converter prints a `FAIL: sheet '<name>' is missing required field(s)`
    message, the spreadsheet has a header it cannot resolve. Either:
    - Rename the column in the xlsx to one of the accepted aliases (see the
      printed alias list), or
    - Add a new alias to `ALIASES` in `tools/qa_xlsx_to_qatouch_csv.py`.
    Re-run.

2c. Review the printed manifest. Pay attention to:
    - `Rows written` - sanity-check against expected case count.
    - `Per-sheet row counts` - confirm each sheet contributed.
    - `Rows with both Expected+Acceptance merged` - QA filled both columns;
      audit for overlap.
    - `Rows that used sheet-name for case_type` - type was inferred; backfill
      will re-write.
    - `Type/Severity column-shift swaps applied` - Family A LDAP-style swap
      auto-corrected.
    - `Warnings: tag_dropped` - tag values outside the four canonical tags
      were dropped; QA should fix those rows OR Ops can ignore (backfill only
      re-applies the four canonical tags anyway).

2d. Commit the canonical CSV alongside the xlsx so the import is reproducible.

**Verify:** open the CSV in a text editor - header row matches `CANONICAL_COLUMNS`,
data rows look right, multi-line Steps cells are wrapped in quotes.

---

## Phase 3 - Import CSV via QA Touch UI

**Owner:** Ops. **Tool:** QA Touch UI (manual upload).

**Why:** QA Touch's CSV importer is the only supported bulk-create path. It
will SILENTLY:

- Drop the `reference` (refLink) column on import. We tolerate - phase 4
  re-applies via /v1/case/update.
- Rewrite unknown `test_type` values to `Regression`. The converter only emits
  known values, so this should not fire in practice.
- Drop tags not in the per-project dictionary. Phase 0 pre-creates the four
  canonical tags, so this also should not fire in practice.
- Collapse multi-row steps into a single merged "Step 1: ...\nStep 2: ...". We
  emit the merged-cell format INTENTIONALLY - phase 5 splits it.

Historical note (now mitigated): pre-2026-06-26 the canonical CSV used
friendly Title-Case headers (`Description`, `Tags`, `Priority`, `Mode`,
`Type`). A CSV column literally named `Description` maps to a hidden vendor
field that is silently dropped - the user-visible Description field is
populated only by the `test_description` slug. Phase 4 was compensating for
this drop without anyone realizing why. After 2026-06-26 the converter emits
VENDOR-CANONICAL slugs (including routing `Description` -> `test_description`)
so the description silent-drop is no longer possible. The auto-map "the
wizard auto-fills dropdowns when headers match" claim made in an earlier
2026-06-26 revision of this doc was wrong (verified empirically - see
§7.A.1 of `docs/local/qa_touch_integration.md` "auto-map is a myth"); the wizard always
defaults dropdowns to Skip and the operator (or a script) must select each.
The QA-facing author template was restored to friendly headers (v2,
2026-06-26) since the auto-map benefit was never real.

**Steps - pick ONE of the two paths below:**

### Format A - Standard Import wizard (`--format=merged-steps`, the default)

CSV is one row per case with newline-merged steps + expected. Goes through
the standard import wizard. **Requires the Phase 5 step splitter** to break
the merged "Step 1" into per-step rows post-import.

3a. Open QA Touch -> target project -> Test Cases -> Import.

3b. Upload `tests/data/<release>_<module>_canonical.csv`.

3c. Map the 17 dropdowns. **The wizard does NOT auto-select - every
    dropdown defaults to "Skip" even when the CSV column names match the
    vendor's slugs.** Two ways to do this:

    - **Manual:** click each dropdown and pick the option whose name
      matches the row's label (e.g. for the "Module Name" row, pick
      `section_name`; for "Test Case Title", pick `title`; for
      "Description", pick `test_description` - NOT `description`, that's
      a trap, see §7.A.1). The 15 vendor-canonical headers our converter
      emits all match by name. Leave `tags` (legacy) + `heirarchy` +
      the trap-name `description` at Skip.
    - **One-click:** paste the [DevTools Quick-Map snippet](#devtools-quick-map-snippet)
      below into Chrome's Console (F12 -> Console tab). It sets all 15
      mappings in one shot and reports success. The Vue chips may still
      visually show "Skip" - that's a display bug; the form values are
      correct (proven against the 312-case Partner Portal import).

    Leave the template radio at "Test Case ( Steps )" (default), click
    Import.

3d. After import completes, note the imported case count.

### Format B - Data Migration wizard (`--format=migration-rows`, RECOMMENDED for new batches)

CSV is single-row-per-step layout. Goes through the Data Migration wizard.
**Eliminates Phase 5** - steps land pre-split (each CSV step-row becomes its
own step row in QA Touch with its own expected_result). Verified against
60w8 on 2026-06-26.

3a. Convert with the migration-rows format:
    ```bash
    python tools/qa_xlsx_to_qatouch_csv.py \
        --xlsx tests/data/<release>_<module>_authored.xlsx \
        --out  tests/data/<release>_<module>_canonical_B.csv \
        --format migration-rows
    ```
    Expect ~8x row count (1 case = N+1 CSV rows where N = step count) and
    a ~5-10% file-size increase. Still under the 1 MB cap for typical
    300-case authoring batches.

3b. Open QA Touch -> target project -> Test Cases -> **Data Migration**
    (NOT Import - different wizard). URL is
    `/v2/case/migration/import/p/{projectKey}`.

3c. Upload the `_canonical_B.csv` file. Map the 18 dropdowns (same drill
    as Format A §3c - **dropdowns do NOT auto-select** even with
    vendor-canonical headers).

    - **Manual:** Module Name -> `section_name`, Test Case Title ->
      `title`, Test Data -> `test_data`, Estimate Time -> `estimate`,
      References -> `reference`, Preconditions -> `precondition`, Steps
      -> `steps`, Expected Result -> `expected_result`, Test Suite ->
      `test_suite`, New Tags -> `newtags`, Description -> `test_description`
      (NOT `description`), Type -> `test_type`, Priority -> `test_priority`,
      Mode -> `test_mode`, Created By -> `created_by`. Leave Tags and the
      other unmatched slots at Skip.
    - **One-click:** paste the [DevTools Quick-Map snippet](#devtools-quick-map-snippet)
      below into Chrome's Console. Same proven path as the 312-case
      Partner Portal import - Vue chips may still visually show "Skip"
      but the form POSTs the correct mappings.

    Leave the template radio at "CSV (steps with single row)" (default),
    click Import.

3d. After import completes, note the case count (this should match the CSV's
    header-row count - i.e. number of *cases*, not number of CSV rows).

**Skip Phase 5 entirely when using Format B.** Phase 4 backfill is still
useful (defense-in-depth re-application of metadata), but is not load-
bearing for fresh imports - see Phase 4 description for what each pass
covers.

### DevTools Quick-Map snippet

After uploading the CSV (and the wizard's dropdowns appear), open
Chrome's DevTools (F12 or Ctrl+Shift+I), switch to the **Console** tab,
paste the snippet below, hit Enter. Works on BOTH the standard Import
wizard and the Data Migration wizard - same dropdown structure.

What it does: sets each of the 15 vendor-canonical dropdown slots
(`section_name`, `title`, `test_data`, ..., `created_by`) to the matching
CSV column. Leaves the three vendor-only slots (`description` /
`tags` / `heirarchy`) at Skip - those don't exist in our canonical
CSV and are correctly unmapped.

What you'll see: a green ✓ summary in the Console. The wizard's
dropdown chips may continue to visually show "Skip" - that's a Vue
display lag we documented in `docs/local/qa_touch_integration.md` §7.A.1. **The
form's underlying values are correct** - verified by capturing the
multipart POST body on the 2026-06-26 312-case Partner Portal import.
Just click Import; the right mappings get posted.

```javascript
// QA Touch Wizard Quick-Map
// Paste into Chrome DevTools Console after uploading the canonical CSV.
// Sets all 15 vendor-canonical dropdowns to their matching CSV column.
// Vue chips may still visually show "Skip" - form values are correct.
(() => {
  const SLOTS = [
    "section_name", "title", "test_data", "estimate", "reference",
    "precondition", "steps", "expected_result", "test_suite", "newtags",
    "test_description", "test_type", "test_priority", "test_mode", "created_by",
  ];
  const nativeSetter = Object.getOwnPropertyDescriptor(
    window.HTMLSelectElement.prototype, "value"
  ).set;

  const set = [], missing = [];
  for (const slot of SLOTS) {
    const sel = document.querySelector(`select[name="${slot}"]`);
    if (!sel) {
      missing.push(`${slot} (no <select> on page - wrong wizard?)`);
      continue;
    }
    const opts = Array.from(sel.options).map(o => o.value);
    if (!opts.includes(slot)) {
      missing.push(`${slot} (CSV column missing - has the file been uploaded?)`);
      continue;
    }
    nativeSetter.call(sel, slot);
    sel.dispatchEvent(new Event("input", { bubbles: true }));
    sel.dispatchEvent(new Event("change", { bubbles: true }));
    set.push(slot);
  }

  if (set.length === SLOTS.length) {
    console.log(
      `%c✓ Quick-Map: ${set.length}/${SLOTS.length} mappings set. ` +
      `Vue chips may still show "Skip" - that's cosmetic. Click Import.`,
      "color:#0a0; font-weight:bold; font-size:14px"
    );
  } else {
    console.warn(
      `Quick-Map: ${set.length}/${SLOTS.length} set. Missing:`, missing
    );
  }
  return { set, missing };
})();
```

**Verify:** imported count == CSV row count - 1 (header). If short, check the
tag dictionary (phase 0a) - missing tag dictionary entries are the most
common cause of silent row drops.

---

## Phase 4 - Metadata backfill

**Owner:** Ops. **Tool:** `tools/backfill_qa_touch_metadata.py`.

**Why:** since 2026-06-26 the canonical CSV emits vendor-canonical slugs and
the operator (or a script) maps the wizard dropdowns to the matching slugs,
so most fields land correctly at import. Empirically: when imported via the
Data Migration wizard (Format B) with all 15 mappings set, **every metadata
field lands correctly including `reference`**, so Phase 4 is now reduced to
a defense-in-depth pass. Matches each CSV row to a QA Touch case by title,
then re-applies via `/v1/case/update`:

- `reference` (refLink) - used to be reported as silently dropped (era of
  friendly Title-Case CSV columns + manual operator mapping where Reference
  was often skipped). With vendor-canonical CSV headers + the column mapped
  to `reference` at upload time, the import populates References correctly
  (verified against the 312-case Partner Portal import 2026-06-26).
  Backfill keeps re-applying as defense-in-depth.
- `test_description` - lands on import (Description -> `test_description` via
  the column mapping); backfill is defense-in-depth.
- `test_mode` (via MODE_NORMALIZE) - lands on import; defense-in-depth.
- `test_type` (via TYPE_ENC enc_id) - lands on import; defense-in-depth.
- `test_priority` (via PRI_ENC) - lands on import; defense-in-depth.
- `newtags` (via TAG_ENC list from pipe-delimited string) - lands on import
  IF the per-project tag dictionary already contains the four canonical tags
  (Phase 0a); otherwise the import silently drops them and Phase 4 re-applies.

For new imports against fresh projects, the backfill is effectively a
defense-in-depth pass - almost everything will be a no-op. (A future
`--only-fields reference` flag is a candidate optimization but the tool does
not have it today; the full backfill is the safe default.)

The script reads BOTH the new vendor-canonical CSV headers
(`reference`/`test_description`/`test_type`/`test_priority`/`test_mode`/`newtags`/
`section_name`/`title`) AND the legacy friendly headers (`Reference`/
`Description`/`Type`/`Priority`/`Mode`/`Tags`/`Module_name`/`Test Case Title`),
so historical canonical CSVs (sitedevice_canonical, distributor_canonical,
ldap_canonical) keep working without `--title-column` overrides.

Treats HTTP 500 with body `{"status":true}` as success
(`ok_500_quirk`, `backfill_qa_touch_metadata.py:18-20`). This is a documented
QA Touch quirk - the update succeeds, but a downstream side-effect raises a
500. Body content is the source of truth.

**Steps:**

4a. Run:
    ```bash
    python tools/backfill_qa_touch_metadata.py \
        --csv tests/data/<release>_<module>_canonical.csv \
        --project-key <PROJECT_KEY>
    ```
    Replace `<PROJECT_KEY>` with the literal alphanumeric key from phase 0b
    (e.g. `JlW1`, `70l1`, `60W5`). The literal flag is `--project-key` -
    verified at `backfill_qa_touch_metadata.py:577`.

4b. Review the per-case ok/fail summary.

4c. Re-run failed cases:
    ```bash
    python tools/backfill_qa_touch_metadata.py \
        --csv tests/data/<release>_<module>_canonical.csv \
        --project-key <PROJECT_KEY> \
        --only-titles "<title1>,<title2>"
    ```

**Verify:** spot-check 3 cases in the UI. test_type, test_priority,
reference, newtags, test_description, test_mode should all match the
canonical CSV row (UI labels these "Type", "Priority", "References", "Tags",
"Description", "Mode" respectively - the vendor names are just the import
slugs).

---

## Phase 5 - Post-import step split + last-step expected placer

**Owner:** Ops. **Tool:** `tools/qa_post_import_split_and_position.py`.

**Why:** the importer collapsed our multi-line Steps cell into a single
"Step 1" row in QA Touch. This tool reads the merged row, parses it back into
N step texts, deletes the merged row, and saves N new step rows via
`/v1/steps/save`. The case-level `expected_result` (which was padded with `-`
on steps 1..N-1 by the converter) is placed on the LAST step only - design
requirement #2: the last step is the assertion.

**Why per-step "-" instead of repeating the expected:** when QA's intent is
"the test passes if the final state matches", repeating the same expected
text on every step is noisy and misleading. The `-` sentinel makes the
intent obvious in the UI: intermediate steps are pure actions, the final step
is the verification.

**Built on:** `qatouch_c2c_step_split.py` (proven against project 60W5,
C2C Hardware module).

**Rate limits:**
- `INTER_CALL_DELAY = 0.15s` between every `/v1/*` call.
- `INTER_CASE_DELAY = 0.3s` between cases.
- `RATE_LIMIT_PAUSE = 15.0s` sleep on HTTP 429, then retry the save once.

**Auth:** Playwright Chromium headed (slow_mo=50). XSRF-TOKEN cookie harvested
from document.cookie and sent as X-XSRF-TOKEN header. Auth state cached at
`tools/.qatouch_auth_state.json`. Headless mode is known to fail (per
`MEMORY.md`) - leave the browser visible.

**Steps:**

5a. Run:
    ```bash
    python tools/qa_post_import_split_and_position.py \
        --project-key <projectKey> \
        --csv tests/data/<release>_<module>_canonical.csv
    ```
    Optional flags: `--module-key`, `--case-keys`, `--only-titles`, `--limit N`,
    `--dry-run`, `--resume-from N`, `--auth-state-file PATH`, `--rate-ms`,
    `--inter-step-ms`.

5b. If a case shows `verify_mismatch`, re-run that one with `--only-titles`.

**Verify:** spot-check 3 cases in the UI Steps tab. Should show N rows; rows
1..N-1 have `-` in the expected column; row N has the full expected text.

---

## Phase 6 - Verify + document

**Owner:** Ops. **Frequency:** every import.

6a. Spot-check 3 cases:
   - Steps tab: N rows.
   - Rows 1..N-1: `-` expected.
   - Row N: real expected text.
   - test_type, test_priority, newtags, reference, test_description,
     test_mode all match canonical CSV (UI shows Type / Priority / Tags /
     References / Description / Mode respectively).

6b. Append a row to the release-import log at
    `qa-ops-hub/docs/imports/<release>.md`:
    - Source xlsx path
    - Canonical CSV path
    - projectKey (e.g. `JlW1`, `70l1`, `60W5`)
    - Row counts (xlsx -> CSV -> imported -> backfilled -> split)
    - Any per-case fails

---

## Failure modes -> defenses (quick lookup)

| Importer quirk | Phase that defends | How |
|---|---|---|
| Unknown test_type rewritten to Regression | Phase 2 (+ 4 defense-in-depth) | Converter only emits known Types; backfill re-applies via TYPE_ENC |
| reference dropped on import | Phase 4 | Importer drops reference unconditionally; backfill re-applies via /v1/case/update (refLink) |
| Tags not in dictionary dropped | Phase 0a (+ 4 defense-in-depth) | Pre-create the four canonical tags; backfill re-applies via TAG_ENC |
| Hidden vendor `description` field swallows the column literally named `description` | Phase 2 | Converter emits `test_description` (vendor-canonical for user-visible Description) instead of the trap-name `description` |
| Literal `<`, `>` corrupt parser | Phase 2 | Converter HTML-escapes in steps/expected_result/test_data/precondition/test_description (NOT section_name) |
| Multi-row Steps collapsed | Phase 2 + 5 | Converter emits merged-cell format intentionally; step splitter breaks into per-step rows |
| NewTags -> Tags vendor rename (in the public API only) | Phase 4 | Backfill is the only API caller; pipe-delimited string in CSV stays stable |
| /v1/case/update returns 500 with status:true | Phase 4 | ok_500_quirk handler treats body status:true as success |
| /v1/case/update returns 422 `"Please add some steps"` when caseStep stripped | Phase 4 | Backfill carries caseStep through verbatim (see docs/local/qa_touch_integration.md §7.B.1) |
| /v1/steps/save 429 rate limit | Phase 5 | 15s pause + retry once |
| QA renames a header column | Phase 2 | Header auto-detect needs >=3 required fields; FAIL LOUD with seen-headers list |
| LDAP rows-73..82 type/severity column shift | Phase 2 | SEVERITY_TOKENS vs TESTING_TYPE_TOKENS membership check + auto-swap |
| Both Expected + Acceptance columns present | Phase 2 | Converter merges with `\n\n` separator; never drops either |
| Legacy CSVs use friendly headers (Test Case Title, Description, Reference, ...) | Phase 4 + 5 | Backfill and step splitter both alias-read the legacy + vendor-canonical names |

See `docs/local/qa_touch_integration.md` for the underlying API behavior and
`tools/archive/build_partner_admin_backfill.py` (a finished one-off, kept for its enc_id reference tables).
