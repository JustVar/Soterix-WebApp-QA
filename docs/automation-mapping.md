# VSaaS QA Automation - Doc # Mapping Convention

## 1. Source of truth (read this first)

**`qa/doc_registry.yaml` is the single source of truth.**

- The registry is canonical for **scope, owner, status, path, deployment**.
- `qa/Automation_QA.csv` is a **regenerated tracker view** - git-diffable, human-readable, refreshed from the registry by `qa/export_registry.py`. Never hand-edit it.
- `qa/Automation_QA.xlsx` is a **regenerated tracker view** - the `Test Mapping` tab is refreshed from the registry. Other tabs (legend, dashboards, manual notes) are preserved. Never hand-edit the `Test Mapping` tab.
- Test files carry a **Doc # header + `@pytest.mark.qa_doc(...)` marker** - that's the immutable join key between code and the registry.

Why this way? Git history is the audit log. PR review catches drift. One commit, one place to look. The xlsx stays useful for stakeholders without becoming a drift source.

## 2. Doc # scheme

Format: `QA-{TYPE}-{AREA}-{NN}`

| Segment | Values | Meaning |
|---|---|---|
| QA | fixed | Project prefix |
| TYPE | `API` / `SIM` / `PLN` / `REF` | API smoke, real-world simulation, planned, reference UI E2E |
| AREA | 3-7 letter code (may include one dash, e.g. `ADM-USR`) | Functional area - see `qa/area_codes.md` |
| NN | zero-padded sequence | `01`, `02`, ... unique within TYPE+AREA |

Examples: `QA-API-PLT-01`, `QA-SIM-NET-03`, `QA-PLN-RBAC-01`, `QA-REF-UI-LGN`.

Doc #s are **never reused**. Retired tests get `status: retired` in the registry; new tests get the next free `NN`.

## 3. Where the Doc # lives

### 3a. In test files

First line of the module docstring:

```python
"""
QA-API-PLT-01 - Platform APIs smoke
Spec: qa/doc_registry.yaml › QA-API-PLT-01
Section: I. API
Owner: JV
Deployment: After FT
"""
```

Mark each test function:

```python
@pytest.mark.qa_doc("QA-API-PLT-01")
def test_site_status(...): ...
```

Playwright (TS) tests use the title prefix:

```ts
test.describe("QA-API-PLT-01 - Platform APIs smoke", () => { ... });
```

### 3b. In the registry

Append an entry to `qa/doc_registry.yaml`:

```yaml
- doc_id: QA-API-PLT-01
  section: I. API
  area: Platform APIs (session, dashboard, widgets, camera tree)
  path: tests/smoke/test_platform_apis.py   # lives in the Soterix-API-QA repo
  owner: JV
  deployment: After FT
  status: active
```

### 3c. Folder structure

Folder path mirrors the registry `path`. Editing the file location? Update the registry in the same commit.

## 4. Workflows

### Adding a new test (engineer)

1. **Reserve a Doc #** by adding a row to `qa/doc_registry.yaml`.
2. **Write the test file** at the path you wrote in the registry.
3. **Add the docstring header + `@pytest.mark.qa_doc(...)` marker.**
4. **Run `python qa/check_doc_ids.py`** locally - should print OK.
5. **Run `python qa/export_registry.py --csv`** to refresh `qa/Automation_QA.csv`.
6. **Commit registry, test file, and CSV together** in the same PR. Reference the Doc # in the PR description.

### Requesting a new test (non-engineer QA)

1. Open a GitHub Issue using the **"New test request"** template (`.github/ISSUE_TEMPLATE/new_test_request.md`).
2. Fill in: proposed area, what it should verify, owner, deployment point.
3. An engineer picks it up, assigns a Doc #, and either writes the test or files it as `status: planned` in the registry.

### Refreshing the xlsx tracker view

After merging changes to the registry, regenerate the xlsx for stakeholders:

```sh
python qa/export_registry.py --xlsx
```

This refreshes the `Test Mapping` tab in `qa/Automation_QA.xlsx`. Other tabs (legends, manual dashboards) are preserved. Commit the xlsx if you're publishing the refreshed view; otherwise share it out-of-band.

CI optionally runs the same export on every merge to `main` and commits the refreshed `Automation_QA.csv` automatically.

### Retiring a test

1. Set `status: retired` in `qa/doc_registry.yaml` (keep the entry - Doc # is never reused).
2. Delete or move the test file. The registry path becomes a tombstone.
3. Regenerate the CSV.

## 5. CI guardrails

`qa/check_doc_ids.py` runs in pre-commit and CI. It verifies:

- Every test file under enforcement paths has a Doc # in its header
- Every Doc # referenced in code exists in the registry
- Every registry entry's `path` resolves to a real file (unless `status: planned`)
- No duplicate Doc #s

Run locally: `python qa/check_doc_ids.py` (warn-only) or `python qa/check_doc_ids.py --strict` (CI mode).

## 6. Section conventions

| Section | Type prefix | Where tests live | Notes |
|---|---|---|---|
| I. API | `QA-API-*` | `tests/smoke/` in Soterix-API-QA | One Doc # per `test_*_apis.py` file |
| II. Simulation | `QA-SIM-*` | `tests/simulation/` (mix of automated + manual) | Manual ones live as runbooks in `qa/runbooks/<doc_id>.md (planned - the folder does not exist yet)` |
| III. Planned | `QA-PLN-*` | path = (to be created) until built | Keep in registry with `status: planned` |
| Ref. UI E2E | `QA-REF-UI-*` | `tests/ui/<area>/` | Feature coverage - not part of main automation rollup but tracked for completeness |

## 7. Area codes

Single source of truth is [qa/area_codes.md](../qa/area_codes.md). New area = update that file in the same commit.

## 8. PR template addition

[.github/pull_request_template.md](../.github/pull_request_template.md) includes a **QA mapping** section requiring contributors to list Doc #(s) touched and confirm the registry + CSV are updated.

## 9. Mental model summary

```
                          ┌─────────────────────────────────────┐
                          │ qa/doc_registry.yaml  ← TRUTH       │
                          │ (engineers edit; PR-reviewed)       │
                          └────────────────┬────────────────────┘
                                           │ qa/export_registry.py
                          ┌────────────────┼───────────────────────┐
                          ▼                ▼                       ▼
            qa/Automation_QA.csv   qa/Automation_QA.xlsx    test files (Doc #
            (git-diffable view)    (stakeholder tracker)    in docstring + marker)
```

Read paths flow downward. Nothing flows upward. The xlsx and CSV are sinks, not sources.

## Related

- [API_ENDPOINTS.md](./API_ENDPOINTS.md) - pointer only. The endpoint catalog moved to the Soterix-API-QA repo on 2026-08-07.
- [BRUNO_GUIDE.md](./BRUNO_GUIDE.md) - pointer only. The Bruno collection moved to the Soterix-API-QA repo on 2026-08-07.
- [qa/README.md](../qa/README.md) - entry point for the `qa/` directory
