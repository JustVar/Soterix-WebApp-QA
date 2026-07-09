# Implementation Roadmap - Playwright Soterix QA

## Executive summary (today)
- Implemented Playwright pilot migration scaffolding: `LoginPage`, `Camera/Views`, `Events`, `Dashboard` POs.
- Added pilot smoke tests for Login, Camera (Views) and Events and validated Login + Camera flows against QA.
- Addressed ReCAPTCHA by adding a best-effort checkbox handler and relaxing landing expectations.
- Normalized environment config (`ENV=qa` for pilots) and updated `.env.example`.

## 2‑Week Implementation Plan

Week 1 - Quick wins (deliverable smoke tests + POs)
- Day 1: Stabilize login + environment handling
  - Add API-based login fixture (if auth endpoint available).
  - Ensure `conftest.py` exposes `tenant_login` and `base_url` fixtures.
- Day 2-3: Views PO + smoke
  - Implement `tests/shared/pages/views_page.py`
  - Add `tests/views/software/smoke/test_views_load_and_play_smoke.py`
- Day 4-5: Events + Media smoke
  - Extend `tests/shared/pages/events_page.py` (filters/time range)
  - Add `tests/events/.../test_events_filter_search_smoke.py`
  - Implement basic `tests/shared/pages/media_page.py` and `tests/media/.../test_media_list_play_smoke.py`

Week 2 - Expansion and robustness
- Day 6-7: Topbar/Sidebar PO and Admin smoke
  - `tests/shared/pages/topbar.py`, `sidebar.py` and `tests/admin/.../test_admin_users_list_smoke.py`
- Day 8-9: Search & Insights smoke tests
  - `tests/search/.../test_global_search_smoke.py` and `tests/insights/...` basic smoke
- Day 10: Harden CI
  - Add failure artifact capture (screenshot + HTML) in `conftest.py` on test failure
  - Configure CI to use QA test key or API auth bypass

## The 5 priority smoke tests (Week 1)
1. `tests/auth/software/smoke/test_login_sw_smoke.py` - Login + landing
2. `tests/views/software/smoke/test_views_load_and_play_smoke.py` - Video wall loads and first camera playback
3. `tests/events/software/smoke/test_events_filter_search_smoke.py` - Events filtering and open event
4. `tests/media/software/smoke/test_media_list_play_smoke.py` - Media list and clip playback
5. `tests/admin/software/smoke/test_admin_users_list_smoke.py` - Admin users list loads

## Team member task assignments
- Jus (Jus/You): Project lead - code merges, CI config, API auth fixture, `conftest.py` fixes, and shepherd the pilot tests.
- QA Engineer A: Implement POs (ViewsPage, MediaPage, Topbar/Sidebar) and write the Views + Media smoke tests.
- QA Engineer B: Events + Admin pages, Insights smoke tests, and help implement artifact capture + flaky-test mitigations.

## Dependencies & Blockers
- ReCAPTCHA on Stage/Prod blocks UI login - blocker for Stage/Prod UI tests. Mitigations:
  - Use QA account (reCAPTCHA-friendly) for CI or request test key from devs.
  - Implement API/token login to bypass UI.
- Test data: Cameras, Clips, Events must exist in QA account used for tests.
  - Coordinate with platform owners to provision a stable QA account/tenant.
- CI environment must install Playwright browsers: `playwright install chromium`.

---
End of roadmap.
