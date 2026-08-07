# API Surfaces, Auth Contracts, and Environments

Last verified: **2026-08-05**

There are **two separate APIs** behind the same hostnames. They have different
base paths, different authentication, and different availability per environment.
Confusing them is the most likely source of wasted debugging time, so this doc is
the single reference for both.

| | Internal API | Integration API |
|---|---|---|
| Base path | `/v-apiserver` | `/v-integration-api` |
| Auth | `JSESSIONID` session cookie | `x-vsaas-key` header (static API key) |
| Scope | Everything the web app does | 14 read-only endpoints for 3rd parties |
| Methods | GET / POST / PUT / DELETE | GET only |
| Documented? | No public spec - discovered by testing | Swagger UI published |
| Available | QA, stage, prod | **QA only** (404 elsewhere as of 2026-08-05) |

---

## 1. Internal API (`/v-apiserver`)

This is what the existing suite in `tests/api/` targets, and what the SPA itself uses.

### Login - the only path that works from an API client

```
POST {host}/v-apiserver/REST/central/user/login
Content-Type: application/json

{
  "accountid": "user@soterixsystems.com",   <- the EMAIL goes here
  "username":  "Example Label",                   <- hardcoded literal, not the user
  "password":  "<SHA512 hex digest of the plaintext password>"
}
```

Success returns `200` with the token at `result[0].JSESSIONID`. Send it on every
subsequent call as `Cookie: JSESSIONID=<token>`.

Implemented in `AuthHelper._api_login()`
(`tests/shared/api_clients/auth_helper.py`). **No browser is required.**

### Things that do NOT work - and why

- **`/REST/central/user/auth/login` requires a `captcha` query parameter.** Only a
  browser can produce a reCAPTCHA token, so this endpoint is unusable from an API
  client. The suite used to call it, fail, and silently fall back to driving a
  headed Chromium. That fallback is now opt-in only (`ALLOW_UI_LOGIN_FALLBACK=1`).
- **Plaintext passwords are always rejected.** The password must be SHA512-hashed.
- **`/REST/sso/login`** returns "Missing one or more mandatory request
  parameter(s)" for every shape tried; its required parameters are unknown.

The `accountid` / `"Example Label"` / SHA512 contract was read from the web app's own
JS bundle (chunk `6031-*.js`) and confirmed **byte-identical across QA, stage and
prod** - the same build artifact is deployed to all three. If login ever breaks
with correct credentials, re-check that chunk first.

### Reading login failures

The server distinguishes these, and each needs a different fix:

| Response | Meaning | Fix |
|---|---|---|
| `404` "There is no user with the userid!" | Account does not exist on this host | Wrong environment for this credential |
| `400` "Invalid username and/or password!" | Account exists, password rejected | Stored password is stale |
| Connection error / DNS failure | Host is wrong or unreachable | Check `BASE_URL`, VPN |

`AuthHelper` raises these as distinct messages - trust them.

---

## 2. Integration API (`/v-integration-api`)

Swagger UI: <https://qa.example.invalid/v-integration-api/swagger-ui/index.html>
Machine-readable spec: `/v-integration-api/v3/api-docs`

This surface is published for **third-party integrators**. It is a deliberately
small read-only subset - it is *not* a substitute for the internal API, and most
of what QA tests has no equivalent here.

### Auth

A single static API key in a header. No login, no session, no expiry handling:

```
x-vsaas-key: <key>
```

Missing or wrong key returns `401` with `status: 9581`,
`"Invalid API Key in request headers."`

**The key is not yet stored in `.env`.** Add it as `VSAAS_INTEGRATION_KEY` when
issued, and never commit it.

### Endpoints (14, all GET)

**Sites**
- `/REST/site`
- `/REST/site/{siteid}`

**Cameras**
- `/REST/site/channel`
- `/REST/site/channel/{siteid}`
- `/REST/site/channel/{siteid}/{channelid}`
- `/REST/site/channel/{siteid}/{channelid}/image/parameter`
- `/REST/site/channel/{siteid}/{channelid}/streaming/parameter`
- `/REST/site/channel/{siteid}/{channelid}/streaming/parameter/capability`

**Events**
- `/REST/event`
- `/REST/event/snap/{siteid}/{snapid}`

**Streaming**
- `/REST/stream`
- `/REST/stream/session`
- `/REST/stream/{siteid}/startlive/{channelid}`
- `/REST/stream/{siteid}/startarchive/{channelid}/{starttimestamp}`

### Why this matters for test design

Because it is key-authenticated and read-only, this surface is the cheapest thing
in the whole system to test: no login flow, no session expiry, no captcha, no
browser, and safe to run against any environment that exposes it. It is a good
first target for the API test repo.

The catch is coverage - 14 endpoints. Everything else still requires the internal
API and its session login, and remains **undocumented**: the endpoint list has to
be discovered by capturing what the app does. `docs/API_ENDPOINTS.md` is that
running catalog.

---

## 3. Environments

| Env | Host | Internal API | Integration API | Account |
|---|---|---|---|---|
| QA | `https://qa.example.invalid` | ✅ verified | ✅ verified | `qa@soterixsystems.com` |
| Stage | `https://staging.example.invalid` | ✅ verified | ❌ 404 | `qa@soterixsystems.com` |
| QA production box | `https://app.example.invalid` | ⚠️ not yet tested | ❌ 404 | `hardware-lab@soterixsystems.com` |

Config lives in `config/env/{qa,stage,prod}.py`; hosts there are authoritative.

### Two accounts, one QA URL

`https://qa.example.invalid` serves **two different backends** depending on
which account signs in:

- `qa@soterixsystems.com` - the `india` box in `config/env/qa.py`.
  Hosted elsewhere, fully populated. **Currently active**, and what the suite uses.
- `qa@soterixsystems.com` - the locally hosted box. Not fully set up yet.

So `base_url` alone does not identify the environment under test - the *account*
does. Switch by repointing `QA_USER` / `QA_PASSWORD` in `.env`; both accounts'
passwords are stored there under their own names.

### Known-good QA test data (account: justin.varughese)

- Sites: `16, 17, 105, 109, 111` - `enterpriseId` `2`
- Channel counts: site 17 -> 6, site 16 -> 5, site 111 -> 2, site 109 -> 1, site 105 -> 0
- `TEST_SITE_ID=17` (site `110` is **not** valid for this account and returns 400)

Site topology changes; prefer the discovery fixtures over hardcoded ids.

---

## Open items

- Obtain and store the integration API key (`VSAAS_INTEGRATION_KEY`).
- Set the `hardware-lab@soterixsystems.com` password and verify internal-API login
  against `app.example.invalid`.
- Integration API is QA-only; re-check stage/prod when it is rolled out.
- `/REST/sso/login` parameter contract is still unknown.
