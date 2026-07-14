---
name: New test request
about: Propose a new automation test (for non-engineer QAs and engineers alike)
title: "[Test request] "
labels: ["test-request", "qa"]
---

<!--
Use this template to propose a new test that should be added to automation.
An engineer will pick it up, assign a Doc #, and either write the test or
file it as status: planned in qa/doc_registry.yaml.

Read docs/automation-mapping.md if you want background on how Doc #s work.
You do NOT need to edit any files yourself - just fill out below.
-->

## What should this test verify?

<!-- One paragraph in plain English. What feature/endpoint/flow? What's the success criterion? -->

## Section

<!-- Tick one - see docs/automation-mapping.md § 6 -->

- [ ] I. API smoke (a REST endpoint)
- [ ] II. Simulation (real-world scenario - camera offline, network blip, scale)
- [ ] III. Planned (nice-to-have, not yet ready to build)
- [ ] Ref. UI E2E (a UI feature)

## Suggested area code

<!-- See qa/area_codes.md. Examples: AUTH, ADM-USR, ADM-RUL, EVT, RBAC, NTF, NET. If unsure, leave blank - the engineer will pick. -->

Area:

## Why now / deployment point

<!-- "After FT", "Before next release", "Q3 2026", etc. -->

## Owner suggestion

<!-- Leave blank if you don't have a preference -->

## Existing context

<!-- Link to Jira / QA Touch / Slack thread / Confluence page if any -->

---

### For the triaging engineer (delete this section once filled)

- [ ] Assigned Doc #: `QA-___-___-___`
- [ ] Added entry to `qa/doc_registry.yaml` (status: `active` if shipping now, `planned` if not)
- [ ] Linked this Issue to the PR that lands the test
- [ ] Ran `python qa/export_registry.py --csv` and committed the refreshed CSV
