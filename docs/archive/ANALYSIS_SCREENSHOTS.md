# Screenshot Analysis & Gaps - Soterix QA

## Summary
This document records the UI vs Selenium vs Playwright PO gaps discovered from the 9 screenshots provided and the repository inspection. It identifies missing features, mismatches, and required Page Objects.

## Observed UI (from screenshots)
- Left navigation modules: Views, Events, Maps, Insights, Media, Search, LPR, Admin
- Post-login page: SPA root `/` showing video wall (Views) and side navigation
- Top-right: Notifications, Help, Profile menu
- Events: filters for rules, sites, cameras, time range
- Media: clips, folders, vault management UI
- Maps: Static/Google maps integrations
- Insights: dashboards/widgets
- LPR: left-nav presence, specialized LPR screens
- Admin: Sites, Users, Maps, Integrations, Rules, General, LPR, Licenses

## Gap analysis (screenshots vs Selenium tests)
- Screenshots show many modules with no equivalent Selenium coverage (Insights, Media, Search, Maps, LPR).
- Selenium tests focus on legacy flows and login/webclient flows; many use brittle XPaths and assume server-side routing.
- Key mismatches:
  - Selenium asserts navigations by full URL; current app is SPA and often lands at `/` or uses client route changes.
  - Selenium's camera playback checks rely on elements not present in the React/Next DOM.

## Page Objects required / mismatches
- Existing (playwright) POs: `LoginPage`, `CameraPage` (needs rename to `ViewsPage`), `EventsPage`, `DashboardPage`.
- New POs to create:
  - `tests/shared/pages/views_page.py` (replace CameraPage)
  - `tests/shared/pages/media_page.py`
  - `tests/shared/pages/insights_page.py`
  - `tests/shared/pages/search_page.py`
  - `tests/shared/pages/lpr_page.py`
  - `tests/shared/pages/admin_page.py`
  - `tests/shared/pages/topbar.py` and `tests/shared/pages/sidebar.py` for shared top/right UI and left nav

## Features present but untested
- Insights dashboards and widgets
- Media vault operations (download/share/delete)
- Maps-based features (pin/site visualization)
- Global Search with filters
- LPR result flows and admin license management

## Recommendations
- Prioritize POs that represent navigation and common components: `Sidebar`, `Topbar`, `ViewsPage`.
- Reuse Selenium test intent (business assertions) but reimplement with Playwright selectors and POs.
- Work with backend/devs to provide a QA account with stable fixtures (cameras, clips, events) and a reCAPTCHA bypass/test key.

---
End of analysis.
