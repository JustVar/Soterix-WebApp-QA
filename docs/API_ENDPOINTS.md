# Soterix VSaaS - API Endpoint Catalog

Living catalog of every REST endpoint the NexaiQ-Core SPA exercises, with smoke-test coverage status. Source of truth: live network capture on `staging.example.invalid`. Vendor swagger is currently stale (per 2026-05-15 audit) - trust this doc over swagger until a refreshed spec is delivered.

Last updated: **2026-05-15**
Capture method: **chrome-devtools API + Playwright APIRequestContext, signed in as `qa@soterixsystems.com`**

## Base path

All endpoints below are relative to `<host>/v-apiserver`. Example: `/REST/central/user/session` is fetched from `https://staging.example.invalid/v-apiserver/REST/central/user/session`.

Per-environment host:

| Env | Host |
|---|---|
| prod | `https://app.example.invalid` |
| staging | `https://staging.example.invalid` |
| qa | `https://qa.example.invalid` |

Auth: JSESSIONID cookie (not JWT). See `tests/shared/api_clients/auth_helper.py`.

## Status legend

- ✅ **covered** - has a dedicated test in `tests/api/smoke/`
- 🔄 **in-progress** - Tier 1 stub written, assertions need fleshing out
- ❌ **uncovered** - observed live, no test
- 🚫 **untriggered** - likely exists (write path, lazy panel) but not yet captured

---

## Auth / Session

| Status | Method | Path | Notes |
|---|---|---|---|
| ❌ | POST | `/REST/central/user/auth/login` | Primary login. Used by `auth_helper.py` but no smoke. |
| ❌ | POST | `/REST/sso/login` | SSO fallback. Used by `auth_helper.py`. |
| 🚫 | POST | `/REST/site/{siteId}/auth/logout` | Inferred from prior swagger; not yet exercised on staging. |
| ✅ | GET | `/REST/central/user/session` | `test_user_apis.py::test_get_user_session` |
| ✅ | GET | `/REST/central/userprofile/roles` | `test_user_apis.py::test_get_user_roles` |
| ✅ | GET | `/REST/central/role/{enterpriseId}` | `test_user_apis.py::test_get_roles_by_enterprise` |

## User management (Admin -> Users)

| Status | Method | Path | Where surfaced |
|---|---|---|---|
| ❌ | GET | `/REST/site/user/{email}` | Views, Media, Admin |
| ❌ | GET | `/REST/central/user/enterprise/{enterpriseId}` | Admin -> Users tab |
| ❌ | GET | `/REST/central/user/enterprise/{enterpriseId}/profile/{profileId}` | Admin dashboard summary |
| 🚫 | POST | `/REST/central/user/update` | User edit (not triggered) |
| 🚫 | POST | `/REST/central/user/password/reset` | Forgot-password flow |
| 🚫 | PUT | `/REST/central/user/password/update` | Change-password modal |

## Sites & devices (Admin -> Sites)

| Status | Method | Path | Where surfaced |
|---|---|---|---|
| ✅ | GET | `/REST/site/{siteId}/location/tree` | `test_platform_apis.py` |
| ✅ | GET | `/REST/site/{siteId}/channel` | `test_camera_apis.py` |
| ✅ | GET | `/REST/site/{siteId}/channel/{channelId}/snap` | `test_camera_apis.py` |
| ❌ | POST | `/REST/enterprise/sitedetails` | Admin -> Sites tab |
| ❌ | GET | `/REST/site/{siteId}/getsitedetails` | Admin dashboard + Sites |
| ❌ | GET | `/REST/edge/version/latest` | Admin -> Sites |
| ❌ | GET | `/REST/edge/version/site/{siteId}/current` | Admin -> Sites |
| ❌ | GET | `/REST/edge/version/site/{siteId}/previous` | Admin -> Sites |
| 🚫 | DELETE | `/REST/site/{siteId}` | Site delete (not triggered) |

## Rules & analytics (Admin -> Rules)

| Status | Method | Path | Where surfaced |
|---|---|---|---|
| ❌ | POST | `/REST/rule/enterprise/{enterpriseId}/search` | Admin -> Rules + dashboard |
| ❌ | GET | `/REST/analyticschedule/{enterpriseId}/type/{type}` | Admin -> Rules |
| ❌ | GET | `/REST/webhook/{enterpriseId}` | Admin -> Rules -> Webhooks |
| ❌ | GET | `/REST/site/analytics/enterprise/{enterpriseId}/licensed` | Views, Search, Rules |
| 🚫 | POST | `/REST/rule/enterprise/{enterpriseId}/...` (CRUD) | Rule wizard (not triggered) |
| 🚫 | POST | `/REST/webhook` / `/webhook/update` | Webhook CRUD |

## Events

| Status | Method | Path | Where surfaced |
|---|---|---|---|
| ✅ | POST | `/REST/site/search` | `test_platform_apis.py`, `test_search_api.py` (person/vehicle payloads) |
| ❌ | POST | `/REST/site/search/event` | Events page -> Search button |
| ❌ | GET | `/REST/das/event/type/{typeId}/limit/{n}` | LPR page |

## Insights / dashboards / widgets

| Status | Method | Path | Where surfaced |
|---|---|---|---|
| ✅ | GET | `/REST/dashboard/site/{siteId}/status` | `test_platform_apis.py` |
| ✅ | GET | `/REST/dashboard/sharedwidgets/{customerId}/data` | `test_platform_apis.py` |
| ❌ | GET | `/REST/dashboard/widget/mywidgets/data` | Insights |
| ❌ | GET | `/REST/dashboard/getmydashboards/data` | Insights |
| ❌ | GET | `/REST/dashboard/shareddashboards/{customerId}/data` | Insights |
| ❌ | GET | `/REST/dashboard/thumbnail/{dashboardId}` | Insights |
| ❌ | GET | `/REST/dashboard/widget/thumbnail/{widgetId}` | Insights / LPR |
| 🚫 | PUT | `/REST/dashboard/widget/update/{widgetId}` | Widget edit |

## Maps

| Status | Method | Path | Where surfaced |
|---|---|---|---|
| ❌ | GET | `/REST/staticmap/{siteId}/metadata` | Maps + Admin dashboard |
| ❌ | GET | `/REST/staticmap/{siteId}/enc/{encId}/thumbnail` | Maps + Admin dashboard |
| 🚫 | POST / PUT | `/REST/staticmap/{siteId}` and `/addchannel`, `/addchannels`, `/direction` | Map edit |

## Media

| Status | Method | Path | Where surfaced |
|---|---|---|---|
| ❌ | GET | `/REST/media/storage/vault` | Media |
| ❌ | POST | `/REST/media/search/enc` | Media (clips, folders, vault, My Media all share this) |
| 🚫 | PUT | `/REST/media/vault/{mediaid}` | Add to vault |

## LPR

| Status | Method | Path | Where surfaced |
|---|---|---|---|
| ❌ | GET | `/REST/lpr/site/{siteId}/location/tree` | LPR |
| ❌ | GET | `/REST/lpr/enterprise/{enterpriseId}/widget/data` | LPR |

## Licenses (Admin -> Licenses)

| Status | Method | Path | Where surfaced |
|---|---|---|---|
| ❌ | GET | `/REST/user/license/available/{enterpriseId}/{email}` | Admin -> Licenses (default tab) |
| ❌ | GET | `/REST/user/license/overview/{enterpriseId}` | Admin -> Licenses |
| ❌ | GET | `/REST/user/license/assigned/{enterpriseId}/{email}` | Admin -> Assigned Licenses sub-tab |
| ❌ | GET | `/REST/enterprise/{enterpriseId}/withlogo` | Admin -> Licenses |
| 🚫 | POST | `/REST/user/license/feature/assignment` | License assign action |
| 🚫 | POST | `/REST/user/license/feature/update/assignment/{action}` | License unassign/re-assign |

## Platform / misc

| Status | Method | Path | Where surfaced |
|---|---|---|---|
| ❌ | GET | `/REST/favourite/getallfavourites` | Global (LPR + others) |
| ❌ | GET | `/REST/platform/deployment` | Admin -> General |

## Not REST (excluded from API smoke planning)

These features are backed by **Firebase Firestore live channels**, not REST. Test them via UI smoke instead:

- Notifications panel (bell icon, badge count, mute/unmute)
- Chats panel (group messages, real-time delivery)

Endpoint pattern: `firestore.googleapis.com/.../Listen/channel?...`

---

## How to update this doc

1. Drive the SPA through a feature you suspect has uncovered endpoints.
2. Capture network traffic. Three ways:
   - **Quick & local:** open Chrome DevTools -> Network -> filter `v-apiserver` -> click through the feature -> Save as HAR.
   - **Interactive exploration:** use Bruno to poke an endpoint and refine the request shape before promoting it to a smoke test. See [BRUNO_GUIDE.md](./BRUNO_GUIDE.md).
   - **Programmatic:** use `chrome-devtools` API from Tooling Code; patch `window.fetch` to log REST calls, then click through.
3. Diff against this catalog. Add new rows under the right section with status `❌` and a one-line "Where surfaced" note.
4. When a smoke test lands, flip status to ✅ and link the test file/function.
5. Bump the "Last updated" date.

## Tooling at a glance

| Tool | What it does | When to use |
|---|---|---|
| **Playwright** (`tests/api/smoke/`) | Authoritative automated API tests, runs in CI | Always - this is the source of truth for coverage |
| **Bruno** (`tests/api/bruno/`) | Human-friendly request collection, plain-file checked into git | Exploring a new endpoint, debugging a failing smoke test, sharing a repro with the platform team - see [BRUNO_GUIDE.md](./BRUNO_GUIDE.md) |
| **Chrome DevTools / chrome-devtools API** | Capturing what the SPA actually calls | First step in discovering an undocumented endpoint |

Playwright is the test runtime. Bruno is for exploration; it is not a CI dependency.

## Why no swagger?

Vendor swagger at `https://app.example.invalid/v-apiserver/v3/api-docs` was audited 2026-05-15 and found stale - at least 14 production endpoints (most of the dashboard, LPR, media, and analytics surfaces) are missing from it, and the documented base URL is wrong. Treat swagger as advisory, not authoritative. This document supersedes it for QA test planning.
