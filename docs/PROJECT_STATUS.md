# Collivra — Project Status

> **Who this is for:** Every teammate — frontend developers, backend contributors, and supervisors — including people who are seeing this project for the first time. Every technical term is explained the first time it appears.
>
> **Maintained by:** The backend agent. Updated automatically after every change to a migration, function, config, endpoint, or decision. Never write secret values in this file.

---

## 1. What this is

Collivra is an India-focused marketplace where brands discover and hire content creators. A brand posts a campaign or job listing, creators submit bids or applications, and — once an agreement is made — the platform handles the contract and payment.

The entire backend runs on **Supabase** (a managed Postgres database with built-in auth, file storage, and serverless functions). There is no separate Node or Django server. All API logic lives in a single **Edge Function** (a TypeScript file that runs at the edge, close to users) served under the path `/api/v1`. That function uses **Hono**, a lightweight web framework for TypeScript, to define routes. The contract that the frontend and backend both follow is the **"Page-by-Page API Specification"** document — when the spec and any other guide disagree, the spec wins.

---

## 2. Status at a glance

| Area | Status | Note |
|---|---|---|
| Database foundation | ✅ Done | Profiles, settings, audit log, RLS, signup trigger — pushed and tested |
| OTP infrastructure | ✅ Done | `otp_send_log` table and `mobile_verified_at` column — pushed to remote DB |
| `POST /auth/signup` | ✅ Live & tested | Creates account as `unverified`, sends OTP, returns `userId` |
| `POST /auth/otp/send` | ✅ Live & tested | Resends OTP; silent success for unknown numbers |
| `POST /auth/otp/verify` | ✅ Live & tested | Checks OTP → returns `accessToken`, `refreshToken`, `next` step |
| `GET /health` | ✅ Live & tested | Liveness check |
| `POST /auth/login` | 🔲 Not started | Password + OTP-based login |
| `GET /auth/me` | 🔲 Not started | Returns the logged-in user's profile |
| `POST /auth/refresh` | 🔲 Not started | Exchanges refresh token for a new session |
| Profiles (read/edit) | 🔲 Not started | Creator and brand profile endpoints |
| Campaigns / Jobs | 🔲 Not started | Brand-side posting endpoints |
| Bids | 🔲 Not started | Creator-side application/bid endpoints |
| Agreements | 🔲 Not started | Contract lifecycle |
| Payments | 🔲 Not started | Payout and commission logic |
| Chat | 🔲 Not started | In-app messaging |
| Admin | 🔲 Not started | Moderation, user management |
| File storage | 🔲 Not started | Portfolio uploads, creative deliverables |

---

## 3. Get started

These steps take a new teammate from zero to a running local environment.

**Prerequisites:** [Node.js](https://nodejs.org) (any LTS version) and [Homebrew](https://brew.sh) (macOS only).

```bash
# 1. Clone the repository (replace URL once it is finalised — see Open Questions)
git clone <REPO_URL>
cd collivra

# 2. Install the Supabase CLI
brew install supabase/tap/supabase

# 3. Log in to Supabase (opens a browser tab)
supabase login

# 4. Link your local copy to the remote project
supabase link --project-ref eetmsobqxlbsvcoscjnb

# 5. Apply all migrations to the remote database
supabase db push --linked

# 6. Run the foundation security tests
#    All 8 should pass. The final error "P0001" is expected — it rolls back test data.
supabase db test --linked supabase/tests/foundation_check.sql
```

> **Note:** The Supabase project reference ID is `eetmsobqxlbsvcoscjnb`. You need to be added to the Supabase organisation to run `db push`. Ask the project lead.

---

## 4. Project layout

```
collivra/
├── supabase/
│   ├── config.toml                  # Supabase project settings (local ports, function options)
│   ├── migrations/                  # SQL files that build the database schema in order
│   │   ├── 20261027051046_foundation.sql     # Profiles, settings, audit log, RLS, trigger
│   │   └── 20261027053217_otp_support.sql    # OTP rate-limit table + mobile_verified_at column
│   ├── functions/
│   │   └── api/
│   │       ├── index.ts             # All /api/v1 routes (the main Edge Function file)
│   │       ├── otpService.ts        # OTP send/check logic — Twilio Verify or dev bypass
│   │       ├── deno.json            # Deno (the TypeScript runtime) config and import map
│   │       └── .npmrc               # Registry config for npm packages used inside Deno
│   └── tests/
│       └── foundation_check.sql     # 8 SQL assertions for RLS and signup rules
└── docs/
    └── PROJECT_STATUS.md            # This file
```

**Key concepts:**
- **Migration:** a SQL file that changes the database schema. Files run in filename order (timestamp prefix). Never edit a migration that has already been pushed — create a new one instead.
- **Edge Function:** a TypeScript file deployed to Supabase's servers that handles HTTP requests. Our single function (`api`) handles all `/api/v1` routes.
- **RLS (Row-Level Security):** a Postgres feature that controls which database rows each user can see or change. All our tables have RLS enabled.

---

## 5. For the frontend team

### Base URL
```
https://eetmsobqxlbsvcoscjnb.supabase.co/functions/v1/api/v1
```

Set this as `VITE_API_BASE_URL` (or equivalent) in your environment config.

### How auth works

1. **Signup** (`POST /auth/signup`) creates the account and sends an OTP (one-time password, a 6-digit SMS code) to the mobile number. It returns a `userId` but **no tokens yet**.
2. **OTP verify** (`POST /auth/otp/verify`) checks the code. On success it returns an `accessToken` (a JWT — a short-lived signed string that proves identity) and a `refreshToken` (a long-lived token to get new access tokens).
3. **Every protected request** must include: `Authorization: Bearer <accessToken>`.
4. When the access token expires (after `expiresIn` seconds, currently 3600 = 1 hour), call `POST /auth/refresh` with the `refreshToken` to get a new pair. _(This endpoint is not yet built — see Next Steps.)_
5. The `next` field in the verify response tells the frontend where to send the user:
   - `"onboarding"` → profile setup (new/unverified accounts)
   - `"dashboard"` → main app (active accounts)
   - `"pending"` → waiting for admin approval

### Error format

Every error from this API has the same shape:
```json
{
  "message": "Human-readable explanation",
  "code": "machine_readable_code",
  "fields": { "fieldName": "What is wrong with this field" }
}
```
`fields` only appears on validation errors (HTTP 422). Show `fields[name]` next to the relevant input.

### Live endpoints

#### `GET /health`
Liveness check — no auth required.
```bash
curl https://eetmsobqxlbsvcoscjnb.supabase.co/functions/v1/api/v1/health
```
**Response `200`:**
```json
{ "ok": true, "time": "2026-10-27T05:27:54.312Z" }
```

---

#### `POST /auth/signup`
Creates a new creator or brand account. Sends an OTP to the mobile number. No auth required.

**Request body:**
```json
{
  "role": "creator",
  "name": "Test Creator",
  "mobile": "+919999999999",
  "email": "optional@example.com",
  "password": "testpass123",
  "acceptTerms": true,
  "termsVersion": "1.0"
}
```

| Field | Required | Notes |
|---|---|---|
| `role` | ✅ | `"brand"` or `"creator"` |
| `name` | ✅ | 2–100 characters |
| `mobile` | ✅ | Indian number, any common format (e.g. `9876543210`, `+919876543210`, `09876543210`) |
| `email` | ❌ | If omitted, a private placeholder is used internally — never shown to the user |
| `password` | ✅ | Minimum 8 characters |
| `acceptTerms` | ✅ | Must be exactly `true` |
| `termsVersion` | ✅ | The version string of the terms document the user accepted |

**Response `201`:**
```json
{ "userId": "c3d599ff-c559-40f1-9c98-70e7830d4b33", "otpSent": true, "resendInSeconds": 30 }
```

**Error codes:**

| HTTP | `code` | Meaning |
|---|---|---|
| 409 | `mobile_taken` | This mobile + role combination is already registered |
| 409 | `email_taken` | Email is already registered |
| 422 | `validation_error` | A field failed validation — check `fields` |
| 429 | `rate_limited` | More than 5 OTP sends in an hour for this number |
| 502 | `otp_send_failed` | Account created but SMS failed — show resend option |

---

#### `POST /auth/otp/send`
Resend or send an OTP for an existing account. No auth required.

**Request body:**
```json
{ "mobile": "+919999999999", "purpose": "login" }
```
`purpose` is `"signup"` or `"login"`.

**Response `200`** (same whether or not the number is registered — prevents probing):
```json
{ "resendInSeconds": 30 }
```

---

#### `POST /auth/otp/verify`
Verify the OTP and get session tokens. No auth required.

**Request body:**
```json
{
  "mobile": "+919999999999",
  "code": "123456",
  "purpose": "signup",
  "role": "creator"
}
```
`role` is optional. Only needed if the same mobile number is registered as both brand and creator (see Open Questions).

**Response `200`:**
```json
{
  "accessToken": "eyJ...",
  "refreshToken": "4qbjyiiwaysu",
  "expiresIn": 3600,
  "role": "creator",
  "status": "unverified",
  "next": "onboarding"
}
```

**Error codes:**

| HTTP | `code` | Meaning |
|---|---|---|
| 400 | `invalid_otp` | Code is wrong, expired, or the account does not exist |
| 403 | `account_blocked` | Account is suspended or banned |
| 409 | `role_required` | Number has both brand and creator accounts — resend with `role` field |

---

### Planned endpoints (not yet live)

| Method | Path | Purpose |
|---|---|---|
| `POST` | `/auth/login` | Sign in with mobile + password, triggers OTP |
| `GET` | `/auth/me` | Get current user's profile |
| `POST` | `/auth/refresh` | Exchange refresh token for new access token |

---

## 6. Database

All tables live in the `public` schema of the Postgres database, unless noted.

### `profiles`
One row per user account. Created automatically when Supabase Auth creates a user (via a database trigger).

| Column | Type | What it holds |
|---|---|---|
| `id` | UUID | Matches the Supabase Auth user ID |
| `role` | text | `brand` or `creator` — set at signup, cannot be changed by the user |
| `status` | text | `unverified` → `needs_info` → `active` (or `suspended`/`banned`) |
| `full_name` | text | Display name |
| `mobile` | text | E.164 format (e.g. `+919876543210`) |
| `email` | text | Optional; null if the user signed up with mobile only |
| `mobile_verified_at` | timestamp | When the user first verified their OTP; null until then |
| `terms_accepted_at` | timestamp | When the user accepted the terms |
| `terms_version` | text | Which version of the terms they accepted |
| `created_at` | timestamp | When the account was created |
| `updated_at` | timestamp | Last update time |

**Access rules (RLS):**
- A logged-in user can read and update only their own row.
- A logged-in user cannot change their own `role` or `status` — those are admin-only fields.
- Anonymous (not logged in) visitors cannot read any row.
- Admins (users with `role = 'admin'` — internal staff only) can read and update all rows.

### `settings`
One row per user, created alongside the profile. Holds user preferences (notifications, etc.). Same RLS rules as `profiles` — own row only.

### `audit_log`
Append-only log of important changes (e.g. status changes, role changes). No user can write to this directly — only the database itself writes here via triggers. Only service-role (admin) can read.

### `otp_send_log`
Records every OTP send attempt. Used to enforce the 5-sends-per-hour limit per number. **No user (logged in or not) can read or write this table** — only the Edge Function can, via the service role key.

| Column | What it holds |
|---|---|
| `mobile` | The number the OTP was sent to |
| `purpose` | `signup` or `login` |
| `created_at` | When the send happened |

---

## 7. Secrets and access

**Never write any secret value in this file or in code. Store them only in Supabase secrets (`supabase secrets set`) or a secure secrets manager.**

| Secret name | What it is | Who to ask |
|---|---|---|
| `SUPABASE_URL` | The project's API URL | Auto-injected by Supabase into Edge Functions |
| `SUPABASE_ANON_KEY` | Public key for anonymous requests | Auto-injected |
| `SUPABASE_SERVICE_ROLE_KEY` | Admin key — full DB access, never expose to frontend | Auto-injected |
| `TWILIO_ACCOUNT_SID` | Twilio account identifier | Project lead / Twilio console |
| `TWILIO_AUTH_TOKEN` | Twilio authentication token | Project lead / Twilio console |
| `TWILIO_VERIFY_SERVICE_SID` | Identifies the Twilio Verify service for OTP | Project lead / Twilio console |
| `DEV_MODE` | `true` enables the test-number OTP bypass | Backend team — **remove before launch** |
| `DEV_OTP_CODE` | Fixed OTP code accepted for test numbers in dev mode | Backend team — **remove before launch** |
| `DEV_TEST_NUMBERS` | Comma-separated list of mobile numbers that bypass Twilio | Backend team — **remove before launch** |
| `PHONE_EMAIL_DOMAIN` | Domain used for internal placeholder emails | Backend team (default: `mobile.collivra.app`) |

**Getting access to the Supabase project:** ask the project lead to add your email to the Supabase organisation. The project reference is `eetmsobqxlbsvcoscjnb`.

---

## 8. Decisions and why

| Date | Decision | Why |
|---|---|---|
| 2026-10-27 | **Supabase-only backend.** No separate application server. | Reduces infrastructure to manage; Postgres + Auth + Storage + Edge Functions covers every need for this stage. |
| 2026-10-27 | **Hono for Edge Function routing.** | Lightweight, Deno-compatible, gives clean route definitions and middleware without bloat. |
| 2026-10-27 | **Twilio Verify for OTP.** | Handles code generation, delivery, expiry (10 min), and attempt limiting (5 tries) — no need to duplicate that logic in our DB. |
| 2026-10-27 | **Dev-mode OTP bypass scoped to a number whitelist.** | A fixed code on all numbers would be an auth bypass if left on in prod. Whitelisting specific test numbers limits blast radius. Must be removed before launch. |
| 2026-10-27 | **API spec wins over feature guide when they conflict.** | The spec is the signed contract between frontend and backend. Deviating from it silently breaks the frontend. Any spec change must be agreed by both sides. |
| 2026-10-27 | **Placeholder emails for mobile-only users.** | Supabase Auth requires an email. Users who sign up with only a mobile number get an internal address (`<number>.<role>@mobile.collivra.app`) that is never shown or stored in their profile. |
| 2026-10-27 | **`otp_send_log` for rate limiting, not a full `otp_codes` table.** | Twilio Verify already manages code storage, expiry, and attempt counting. We only need to track send count to enforce the spec's 5-sends-per-hour limit. |

---

## 9. Open questions

| Question | Context | Owner |
|---|---|---|
| Commission and payout split | Spec says 70/30 in release 1. Feature guide says Phase 2. Which is correct and when? | Founders / product lead |
| Auto-approval window: 48 h or 72 h? | Two documents contradict each other. Affects the agreement lifecycle. | Product lead |
| One mobile number for both brand and creator | The spec allows it. OTP login cannot tell which role is intended, so we return a `role_required` 409 and ask for a `role` field. Frontend needs to handle this. Is the spec correct, or should one number be one role? | Frontend lead + product |
| Twilio India DLT registration | Twilio requires DLT (Distributed Ledger Technology) registration to send SMS to Indian numbers commercially. Trial accounts can only send to numbers you have verified in the Twilio console. Who is handling this? | Business / legal team |
| GitHub repository location | The repo needs a permanent home (GitHub org, visibility). | Project lead |

---

## 10. Next steps

1. **`POST /auth/login`** — takes `mobile` + `password`, verifies credentials against Supabase Auth, then sends OTP. Returns same `201` shape as signup.
2. **`GET /auth/me`** — reads the JWT from `Authorization: Bearer`, looks up the profile, returns it. First protected endpoint.
3. **`POST /auth/refresh`** — exchanges a `refreshToken` for a new `accessToken` + `refreshToken` pair.
4. **Profile endpoints** — `GET /profiles/:id`, `PATCH /profiles/me` for creators and brands.
5. **Remove dev secrets before any public/staging deployment** — `supabase secrets unset DEV_MODE DEV_OTP_CODE DEV_TEST_NUMBERS`.

---

## 11. Changelog

| Date | What changed | Why it matters |
|---|---|---|
| 2026-10-27 | **`POST /auth/signup`, `POST /auth/otp/send`, `POST /auth/otp/verify` deployed and tested.** Signup returns `201` with `userId`; verify returns `accessToken`, `refreshToken`, `role`, `status`, `next`. | Frontend can now build the signup and OTP screens against real endpoints. |
| 2026-10-27 | **`otpService.ts` added.** Twilio Verify integration with dev-mode bypass for whitelisted test numbers. | No SMS credentials needed to develop and test locally. |
| 2026-10-27 | **Migration `otp_support` pushed.** Adds `mobile_verified_at` to `profiles` and creates `otp_send_log`. | Enables OTP rate limiting (5/hour) and tracks when a number was first verified. |
| 2026-10-27 | **`supabase/functions/api/index.ts` bootstrapped with Hono and `/health` endpoint.** `verify_jwt = false` set in config so unauthenticated routes work. | Established the API pipeline end-to-end. Frontend base URL confirmed working. |
| 2026-10-27 | **Migration `foundation` pushed.** Profiles, settings, audit_log, RLS policies, and signup trigger. 8 security assertions passed. | Core data model and security rules are in place. No user can escalate their own role or read another user's data. |
| 2026-10-27 | **`supabase/tests/foundation_check.sql` added.** | Any teammate can rerun the 8 security assertions after future migrations with `supabase db test`. |
