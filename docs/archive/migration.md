# Selenium -> Playwright Migration Guide

Purpose: provide a concise migration playbook to convert Selenium tests from the legacy repo into this Playwright project.

Phases

1) Inventory (Day 0-2)
- Count Selenium tests and group by feature (auth, dashboard, events, cameras).
- Identify page objects, common helpers, and flaky tests.

2) Pilot (Week 1)
- Convert 2-3 smoke tests (one per helix if possible).
- Keep expected behavior identical; validate locators and assertions.
- Store converted POs in `tests/shared/pages/` and reference from new tests.

3) Expand (Weeks 2-6)
- Migrate all smoke and sanity tests.
- Add pytest markers and restructure tests into the new folder layout.

4) Regression & CI (Weeks 6-12)
- Convert full regression and add CI orchestration (playwright chromium install, secrets, QA Touch upload).
- Archive Selenium code to `legacy/selenium/`.

Guidelines & Patterns

- Locator strategy: prefer data-testids where available. If not, use stable CSS/XPath and avoid brittle absolute paths.
- Waiting: replace explicit sleeps with Playwright auto-wait and `page.wait_for_selector` where appropriate.
- Page objects: use simple methods that return primitive values or perform actions; avoid over-abstracting early.

Common Pitfalls

- Frames and cross-domain redirects: stub or adapt these flows in Playwright (use `frame` APIs).
- File uploads/downloads: use Playwright APIs for file chooser and downloads.

Checklist for each converted test

- [ ] Test file placed under `tests/<feature>/helix/<helix>/<type>/`
- [ ] Marked with `@pytest.mark.<helix_marker>` and `@pytest.mark.<type>`
- [ ] Uses `tests/shared/pages` POs
- [ ] Runs locally with `ENV` and `.env.<env>.local` provided
- [ ] Adds mapping to QA Touch case id (via marker or CSV)

Contact: Add project owner and migration lead references here.
