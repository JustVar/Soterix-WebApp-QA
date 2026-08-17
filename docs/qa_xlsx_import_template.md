# QA xlsx Import Template - Author Guide

This is the QA-facing spec for authoring test cases in Excel that flow cleanly
through the converter (`qa_xlsx_to_qatouch_csv.py`), the QA Touch CSV importer,
the metadata backfill, and the post-import step splitter.

**Audience:** QA team authoring test cases. You are filling a spreadsheet - you
do not need to know anything about the QA Touch API. The pipeline operator
(Ops/Justin) runs the import for you.

**Design intent:** the converter is intentionally tolerant of the column-name
variants QA already uses in the wild (Family A "Scenario", Family B "Module",
Family C "Title") so you do not have to re-author existing sheets. Read the
**Accepted Column Aliases** table below to see what the converter will accept
from your spreadsheet.

---

## The Author Template

Fill one row per test case. The template ships at
`tools/templates/qa_author_template.xlsx` (regenerate with
`python tools/generate_qa_author_template.py`) with the 15 canonical column
headers in row 1 (frozen), three worked example rows, and a companion
`INSTRUCTIONS` sheet listing enum reference values and dos-and-don'ts.

**Author template v3 (2026-06-26): one step per row.** Each test case
now spans MULTIPLE ROWS in the authored xlsx:
- The first row of a case carries the metadata (Module_name, Test Case
  Title, Type, Priority, Tags, Description, etc.) PLUS the first step's
  text in the Steps column.
- Each additional step lives on its OWN row, with the metadata columns
  left blank and only the Steps cell filled.
- The LAST step row of the case also carries the Expected_result (the
  case's final outcome). Intermediate Expected_result cells are blank.
- A new case begins when a row has Module_name and Test Case Title
  filled in again.

This layout has two advantages over the prior one-row-per-case shape:
each step is visually obvious in Excel/Sheets with no wrap_text
dependency, and it matches QA Touch's own data-migration sample shape
(steps land pre-split at import).

Header set is still the QA-friendly Title-Case names (`Module_name`,
`Test Case Title`, `Description`, `Tags`, `Priority`, `Mode`, ...) so
authors don't need to think about the vendor's internal field names.
The converter routes `Description` -> user-visible Description; aliases
are listed in the table below.

**Backwards-compatible.** Legacy files authored in the prior one-row-
per-case shape (multi-line Steps cell) still convert correctly - the
converter's pre-pass leaves single-row cases untouched and only
coalesces when continuation rows are present.

You can also use any of the Family A/B/C "in the wild" header variants below -
the converter resolves them via alias-resolution so legacy sheets work without
re-authoring. The alias table maps to a simplified 12-field author model;
each row's `Column Name` is the LOGICAL field; the shipped template's row 1
uses friendly Title-Case names that map 1:1 to those logical fields.

| #  | Column Name       | Required? | Type         | Default if blank | Aliases the converter accepts |
|----|-------------------|-----------|--------------|------------------|--------------------------------|
| 1  | `title`           | REQUIRED  | text         | -                | Title, Test Case Title, Scenario, Summary, Case Title |
| 2  | `case_type`       | REQUIRED  | enum         | sheet-name fallback or `functional` | Type, Testing Type, Test Type, Category |
| 3  | `priority`        | recommended | enum       | `medium`         | Priority, Priorities |
| 4  | `module`          | REQUIRED  | text (` > ` separated) | - | ModuleName, Module, Module Name, Module_name |
| 5  | `precondition`    | recommended | free text  | (empty)          | Precondition, Preconditions, Test Conditions, Pre-Condition, Setup |
| 6  | `steps`           | REQUIRED  | multi-line text | -             | Steps, Test Steps, Test Step, Procedure |
| 7  | `expected_result` | REQUIRED  | free text    | -                | ExpectedResult, Expected Result, Expected Results, Acceptance Criteria, Acceptance |
| 8  | `test_data`       | optional  | free text    | (empty)          | Test Data, Data, Test Inputs |
| 9  | `tags`            | optional  | pipe-delimited | (empty)        | Tags, New Tags, Labels, Suite Tags |
| 10 | `mode`            | optional  | enum         | `manual`         | Mode, Execution Mode |
| 11 | `test_idea`       | optional  | free text    | (empty)          | Test Idea, Description, Rationale (writes to canonical CSV column `test_description` - the user-visible Description in QA Touch) |
| 12 | `severity`        | optional (Family A) | enum | -               | Severity |

> **Why `Description` aliases to `test_idea` then writes to `test_description`:**
> the QA Touch import wizard treats a CSV column named literally `description`
> as a hidden internal field and silently drops it. Only the `test_description`
> slug populates the user-visible Description on the case detail page (verified
> by live probe upload to project 60w8 on 2026-06-26 - see
> `docs/local/qa_touch_integration.md` §7.A.1). The converter sidesteps the trap by
> emitting `test_description` regardless of which alias the QA author used.

### Enum value reference

- `case_type`: `functional`, `negative`, `security`, `performance`, `regression`,
  `acceptance`, `automation` (case-insensitive on input, normalized to lowercase).
- `priority`: `critical`, `high`, `medium`, `low`.
- `mode`: `manual`, `automation` (input `automated` is normalized to `automation`).
- `severity`: `Critical`, `High`, `Medium`, `Low` - Family A only. If `priority`
  is blank but `severity` is filled, the converter maps `severity` -> `priority`.
- `tags`: `smoke`, `sanity`, `regression`, `future` - pipe-delimited e.g.
  `smoke|regression`. These four labels must already exist in the per-project tag
  dictionary in QA Touch (Ops handles this once per project - see
  `qa_import_pipeline.md` phase 0). Unknown tags are silently dropped by the
  importer, so stick to the four.

### Special Family A handling

If your sheet has both `Feature Name` and `Sub Feature Name` columns, the
converter concatenates them into a single `module` value as
`{Feature Name} > {Sub Feature Name}`. You do NOT need a `module` column in that
case - Family A authors keep working as they always have.

### Sheet-name fallback for `case_type`

If `case_type` is blank for a row AND the sheet is named one of:
`Functional`, `Non-Functional`, `Performance`, `Security`, `API`, `Regression`
then the sheet name is used as the type. So a multi-sheet workbook organized by
type still works without filling the column on every row.

---

## Dos and Don'ts

### DO

- Write `title` like a sentence: *"Admin can add a new LDAP server with valid
  LDAPS port 636"*. This becomes the match key the metadata backfill uses to
  re-apply Type/Priority/Tags/Reference after import, so it must be unique within
  the sheet.
- Write `module` as a hierarchy with ` > ` (space-greater-space) separators:
  *"Add New LDAP Server > Connection > Validation"*. The importer nests modules
  on the ` > ` boundary.
- Write `steps` as numbered lines, one step per line:
  ```
  1. Navigate to Admin > Integrations > LDAP
  2. Click "Add LDAP Server"
  3. Enter LDAPS host and port 636
  4. Click Save
  ```
  The converter strips the leading `N. ` or `Step N:` numbering and re-emits as
  `Step 1: ...\nStep 2: ...` in the canonical CSV.
- Write `expected_result` as the **final assertion** of the test - what must be
  true after the last step runs. This single value gets placed on the LAST step
  by the post-import step splitter; intermediate steps get `-` (single dash).
  This is by design - the last step carries the assertion.
- If you have BOTH an "Expected Result" column AND an "Acceptance Criteria"
  column, fill either or both. The converter merges them into the
  `expected_result` field with a double-newline separator and never drops either.

### DON'T

- DON'T paste literal `<` or `>` characters into `steps`, `expected_result`,
  `test_data`, `precondition`, or `test_idea`. The CSV importer's parser
  corrupts on raw angle brackets (the TR0028/TR0029 quirk). The converter
  HTML-escapes them automatically (`<` -> `&lt;`, `>` -> `&gt;`) when writing
  the CSV, but if you must reference HTML, prefer prose: *"the &lt;input&gt;
  field"* or *"the input element"*. The ` > ` separator in `module` IS preserved
  raw (the importer needs it to nest).
- DON'T put a literal `;` or `&` inside `steps` if you can avoid it - those are
  fine inside a quoted CSV cell BUT can confuse manual diffs. The converter does
  not escape them; raw `;` and `&` stay as-is and rely on the csv module's
  RFC-4180 quoting.
- DON'T break a single test case across multiple rows. The canonical format is
  ONE CSV row per test case - all steps live in ONE quoted cell joined by
  newlines. (The importer collapses multi-row Steps into Step 1 anyway, so
  multi-row input is a silent data loss.)
- DON'T rename a header column without telling Ops. The converter's
  alias-resolution covers a wide range of variants, but if you invent a column
  name that doesn't match any alias, the converter FAILS LOUD with the list of
  headers it saw - no silent row drops. Either add an alias to the converter or
  rename your column to a known variant.
- DON'T type tag names other than `smoke`, `sanity`, `regression`, `future`.
  Other strings get silently dropped by the QA Touch importer at the tag column.
- DON'T leave `title` blank or duplicated within the same sheet. Backfill is
  matched on title - a blank or duplicate title cannot be matched back to its
  QA Touch case.

---

## Worked Example - Single Row

| Column | Value |
|--------|-------|
| `title` | `Admin can add a new LDAP server with valid LDAPS port 636` |
| `case_type` | `Functional` |
| `priority` | `High` |
| `module` | `Add New LDAP Server > Connection > Validation` |
| `precondition` | `Logged in as Admin. LDAP integration enabled in project settings.` |
| `steps` | `1. Navigate to Admin > Integrations > LDAP`<br>`2. Click "Add LDAP Server"`<br>`3. Enter LDAPS host and port 636`<br>`4. Click Save` |
| `expected_result` | `LDAP server appears in the configured list with status=Connected and a success toast 'LDAP server saved' is shown.` |
| `test_data` | `host=ldap.example.com, port=636, bindDN=cn=svc,dc=example,dc=com` |
| `tags` | `smoke\|regression` |
| `mode` | `manual` |
| `test_idea` | `Verifies the LDAPS happy path so we don't regress encrypted-bind support during the auth rewrite.` |
| `severity` | *(leave blank - priority is filled)* |

After the full pipeline runs, in QA Touch you will see:

- Title, Type=Functional, Priority=High, Tags=smoke,regression, Mode=Manual.
- Module nested as `Add New LDAP Server` > `Connection` > `Validation`.
- Description: `Verifies the LDAPS happy path so we don't regress encrypted-bind support during the auth rewrite.`
- Reference: auto-assigned by the converter, e.g. `LDAP_Functional_001`, and re-written via API by the backfill so it shows on the case.
- Steps tab: 4 rows. Rows 1-3 each have a step description and `-` in the
  expected-result column. Row 4 has step `Click Save` and the full
  `LDAP server appears in the configured list ...` text as its expected result.

---

## What the Converter Will NOT Touch

These fields are managed by the pipeline, not by the author:

- `case_code` - assigned by QA Touch on import.
- `reference` - auto-assigned by the converter as
  `{SHEET_NAME}_{case_type}_{index:03d}` (e.g. `LDAP_Functional_001`). The
  metadata backfill re-applies this to QA Touch via `/v1/case/update` because
  the CSV importer silently drops the Reference column.
- `created_by` - filled by the converter from its `--created-by` CLI flag.
- `estimate` - not touched by the pipeline; safe to leave blank.
- `test_suite` - importer-only column; the backfill does not touch it.

---

## When Something Goes Wrong

- Converter says `header not resolved`: rename your column to one of the
  accepted aliases (see the table above), or ask Ops to add a new alias.
- Converter says `row N missing required field`: fill `title`, `case_type`,
  `module`, `steps`, or `expected_result` for that row.
- After import, a case shows up as Type=Regression: that's the importer's
  silent rewrite quirk. Phase 4 (metadata backfill) corrects this - confirm
  Ops ran it.
- After import, all steps are merged into Step 1: that's expected post-import.
  Phase 5 (step splitter) breaks them into per-step rows.
- After step split, a case shows fewer rows than expected: re-run the step
  splitter with `--only-titles "<the title>"`.

See `qa_import_pipeline.md` for the full operator runbook.
