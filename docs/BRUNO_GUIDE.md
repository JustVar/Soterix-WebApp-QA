# Bruno - API Exploration Guide for QA

This guide explains what Bruno is, why we use it alongside Playwright, and how to drive the Soterix VSaaS REST API with it.

## TL;DR

- **Playwright runs the automated API tests.** No external tool needed at test runtime.
- **Bruno is for humans** - interactive poking, response inspection, sharing endpoint collections, prototyping a request before promoting it into a Playwright smoke test.
- Bruno collections live as **plain files in the repo** (no cloud account, no sync drift). Anyone can clone the repo and open the collection.

## Why Bruno instead of Postman or Insomnia?

| Concern | Bruno | Postman | Insomnia |
|---|---|---|---|
| Collections stored as files | ✅ `.bru` files in git | ❌ Cloud sync (free tier limited) | ⚠️ Partial |
| Works fully offline | ✅ | ❌ requires sign-in | ⚠️ |
| Per-env vars in repo | ✅ | ⚠️ in cloud | ⚠️ |
| Free for teams | ✅ open source | ❌ paid tiers above 3 users | ❌ paid tiers |
| Code-review friendly | ✅ diff plain text | ❌ binary export | ❌ |

If your team is already deep into Postman, Postman is fine - the workflow below maps 1:1. We just don't want a cloud login to be a prerequisite for running a smoke test interactively.

## Install

- **Desktop app:** download from <https://www.usebruno.com/downloads>.
- **CLI (optional, for CI):** `npm install -g @usebruno/cli` - run a Bruno collection from the command line, useful for ad-hoc smoke runs outside Playwright.

## Where the collection lives

```
tests/api/bruno/
├── bruno.json              # collection manifest
├── environments/
│   ├── staging.bru         # https://staging.example.invalid
│   ├── qa.bru              # https://qa.example.invalid
│   └── prod.bru            # https://app.example.invalid
├── Auth/
│   ├── Login.bru
│   └── Get Session.bru
├── Sites/
│   ├── Get Site Details.bru
│   ├── Enterprise Site Details.bru
│   └── Edge Version Latest.bru
├── Rules/
│   └── Rule Search.bru
├── Events/
│   └── Site Search Event.bru
└── Licenses/
    ├── Available.bru
    ├── Assigned.bru
    └── Overview.bru
```

The collection is **not yet committed** - see "Bootstrapping the collection" below.

## Bootstrapping the collection (one-time, ~15 minutes)

1. Open Bruno -> **Create Collection** -> choose `tests/api/bruno/` inside this repo.
2. **Add an environment** named `staging`:
   - `baseUrl` = `https://staging.example.invalid/v-apiserver`
   - `enterpriseId` = `1`
   - `username` = your staging email
3. Repeat for `qa` and `prod` environments (different `baseUrl`).
4. Add a **Pre-request script** at the collection level that logs in and stores `JSESSIONID`:

   ```js
   // tests/api/bruno/scripts/login.js (pseudo - adapt to Bruno scripting syntax)
   const res = await bru.fetch({
     url: `${bru.env.baseUrl}/REST/central/user/auth/login`,
     method: "POST",
     body: { username: bru.env.username, password: bru.getEnvVar("password") }
   });
   const cookie = res.headers["set-cookie"]?.match(/JSESSIONID=([^;]+)/)?.[1];
   bru.setEnvVar("JSESSIONID", cookie);
   ```

5. Add **collection-level headers**: `Cookie: JSESSIONID={{JSESSIONID}}` and `Accept: application/json`.
6. Save & commit the collection (commit `.bru` files; do NOT commit a passwords file - use Bruno's secret env vars or a local `.env.local`).

## Day-to-day workflow

### Exploring a new endpoint before writing a test

1. **Capture the request from the SPA** - open Chrome DevTools, navigate to the feature, copy the request as a fetch from the Network panel.
2. **Paste into Bruno** -> New Request -> Paste as cURL/fetch.
3. **Replace hardcoded values** with `{{baseUrl}}`, `{{enterpriseId}}`, `{{siteId}}` etc.
4. **Send** - confirm 200 + sane response shape.
5. **Save under the appropriate folder** (Auth, Sites, Rules...) so others can re-use it.
6. **Promote to Playwright** - copy the path, method, and payload shape into a new `test_<area>_apis.py` in `tests/api/smoke/`. See `docs/API_ENDPOINTS.md` for the master endpoint catalog.

### Debugging a failing smoke test

1. Find the failing endpoint in `docs/API_ENDPOINTS.md`.
2. Open the matching Bruno request, hit Send.
3. If Bruno succeeds but Playwright fails -> check headers, body, content-type the Playwright client sends.
4. If Bruno also fails -> server-side problem; capture response and file in QA Ops Hub.

### Sharing a repro with the platform team

1. Reproduce the failing call in Bruno.
2. Export the single request: right-click -> **Export as cURL**.
3. Paste into the bug ticket. Anyone with credentials can reproduce.

## Important rules

1. **Never commit credentials.** Use Bruno's secret env vars or a gitignored `.env.local`. The `.bru` files in `environments/` should only contain non-secret host URLs and enterprise IDs.
2. **Don't run destructive requests against prod.** Bruno doesn't have built-in guardrails - be careful with POST/PUT/DELETE in the `prod` environment.
3. **Keep the collection aligned with `docs/API_ENDPOINTS.md`.** When you add a Bruno request, add or update the corresponding row in the endpoint catalog so the two stay in sync.
4. **Bruno is exploratory, Playwright is authoritative.** A green Bruno request does not constitute test coverage - only a smoke test in `tests/api/smoke/` does.

## What about running Bruno in CI?

We don't, currently. CI runs Playwright. Bruno's CLI (`bru run`) could shadow-run the collection in CI as a smoke-of-the-smoke, but that's redundant - if Playwright passes, Bruno would too. Skip unless we hit a specific need.

## Alternatives if Bruno isn't for you

- **Hoppscotch** (web app) - fast, no install, no auth required, but no checked-in collection.
- **Thunder Client** (VS Code extension) - collections are JSON files, lives in `.vscode/`.
- **HTTPie / curl** - no UI, no collection management, but fine for one-off pokes from a terminal.
- **Postman** - works, but cloud sign-in is friction for new teammates.

## Related docs

- [API_ENDPOINTS.md](./API_ENDPOINTS.md) - master catalog of every observed endpoint + smoke coverage status
- [API_TESTING_NOTES.md](./API_TESTING_NOTES.md) - QA environment runbook (site/camera inventory, JSESSIONID auth notes)
- `tests/shared/api_clients/base_api_client.py` - the Playwright/requests client all smoke tests extend
