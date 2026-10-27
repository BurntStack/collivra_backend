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
| `POST /auth/signup` | ✅ Live & tested | Dual-mode: Brand signup (`{ name, email, password, companyName }` → `{ token, user }`) & Creator mobile OTP |
| `POST /auth/login` | ✅ Live & tested | Password auth (email or mobile) with 5-attempt lockout; returns `{ token, user }` & token pair |
| `GET /auth/me` | ✅ Live & tested | Returns `{ user: { id, name, email, companyName, role } }` from Bearer token |
| `POST /auth/logout` | ✅ Live & tested | Invalidates session, returns `204 No Content` |
| `GET /creators` | ✅ Live & tested | Creator search with pagination envelope (`{ results, total, page, pageSize, totalPages }`), filters & sorting |
| `GET /creators/suggestions` | ✅ Live & tested | Hero search suggestion chips |
| `GET /creators/filters` | ✅ Live & tested | Dynamic filter dropdown options (`platforms`, `cities`, `categories`, `languages`, `priceBuckets`) |
| `GET /creators/:id` | ✅ Live & tested | Full creator profile with bio, gallery, badges, and turnaround time |
| `GET /creators/:id/packages` | ✅ Live & tested | Bookable packages list for booking card |
| `GET /creators/:id/reviews` | ✅ Live & tested | Paginated verified reviews with overall rating |
| `GET /creators/:id/similar` | ✅ Live & tested | Category/platform-matched similar creator recommendations |
| `POST /creators/:id/save` | ✅ Live & tested | Add creator to brand shortlist (heart) → `204` |
| `DELETE /creators/:id/save` | ✅ Live & tested | Remove creator from brand shortlist → `204` |
| `GET /cart` | ✅ Live & tested | Current cart items with joined creator and package details, line totals, and subtotal |
| `POST /cart/items` | ✅ Live & tested | Add package to cart (auto-increments if already present) |
| `PATCH /cart/items/:itemId` | ✅ Live & tested | Update item quantity (removes if quantity <= 0) |
| `DELETE /cart/items/:itemId` | ✅ Live & tested | Remove item from cart → `204 No Content` |
| `POST /offers` | ✅ Live & tested | Send a custom offer (`{ creatorId, deliverable, budget, message, deadline }`) → `201` |
| `POST /campaigns` | ✅ Live & tested | Post a job (`{ title, platform, deliverables, budgetMin, budgetMax, applyBy, brief }`) → `201` |
| `GET /campaigns` | ✅ Live & tested | Brand's campaigns list with `bidCount` and `proposalAvatars` preview |
| `GET /campaigns/:id` | ✅ Live & tested | One campaign detail (`open_for_bids`, `closed`, `awarded`) |
| `GET /campaigns/:id/bids` | ✅ Live & tested | Bids list (`[{ id, creator: { id, name, note, avatar }, price, status }]`) |
| `POST /campaigns/:id/bids/:bidId/select` | ✅ Live & tested | Pick winning creator → creates Order in escrow, sets campaign status `awarded` → `201` |
| `PATCH /campaigns/:id` | ✅ Live & tested | Edit job details |
| `GET /orders` | ✅ Live & tested | Brand's orders list (`[{ id, creator, deliverable, amount, status }]`) |
| `GET /orders/:id` | ✅ Live & tested | Order details with escrow status, deliverable details, and creator profile |
| `POST /orders` | ✅ Live & tested | Direct package booking or custom order creation → `201` |
| `POST /orders/:id/pay` | ✅ Live & tested | Fund escrow → returns client token & payment intent (test mode) |
| `POST /orders/:id/submit-draft` | ✅ Live & tested | Submit deliverable draft for brand review (`draft_submitted`) |
| `POST /orders/:id/request-changes` | ✅ Live & tested | Request revisions with review note (`changes_requested`) |
| `POST /orders/:id/approve` | ✅ Live & tested | "Approve & pay" — releases escrow funds to creator (`released`) |
| `GET /orders/:id/messages` | ✅ Live & tested | Order discussion thread & review audit trail |
| `GET /dashboard/summary` | ✅ Live & tested | Home screen summary (`{ greetingName, todos, stats, topCreators }`) |
| `PATCH /dashboard/todos/:id` | ✅ Live & tested | Tick/untick an onboarding checklist task (`{ done }`) |
| `GET /lists` | ✅ Live & tested | Shortlists overview (`[{ id, name, count, updatedAt, covers }]`) |
| `POST /lists` | ✅ Live & tested | Create new shortlist (`{ name }`) → `201` |
| `GET /lists/:id` | ✅ Live & tested | Shortlist details and full creator cards |
| `POST /lists/:id/creators` | ✅ Live & tested | Add creator to shortlist (`{ creatorId }`) → `201` |
| `DELETE /lists/:id/creators/:creatorId` | ✅ Live & tested | Remove creator from shortlist → `204 No Content` |
| `PATCH /lists/:id` | ✅ Live & tested | Rename shortlist (`{ name }`) |
| `POST /lists/:id/duplicate` | ✅ Live & tested | Duplicate shortlist with copied creators → `201` |
| `DELETE /lists/:id` | ✅ Live & tested | Delete shortlist → `204 No Content` |
| `GET /deliverables` | ✅ Live & tested | Content library search & filter (`?q=&jobId=&platform=&from=&to=`) |
| `GET /deliverables/:id` | ✅ Live & tested | Single deliverable asset details and URLs |
| `GET /deliverables/export` | ✅ Live & tested | Export deliverables content library as CSV |
| `GET /reporting` | ✅ Live & tested | Analytics reporting (`?period=`) with spend, impressions, platforms, top creators |
| `GET /reporting/export` | ✅ Live & tested | Export monthly analytics report as CSV |
| Creator Onboarding & KYC | ✅ Live & tested | PAN, bank AES encryption, private `kyc-docs` bucket, verification request |

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
│   │   ├── 20261027051046_foundation.sql             # Profiles, settings, audit log, RLS, trigger
│   │   ├── 20261027053217_otp_support.sql            # OTP rate-limit table + mobile_verified_at column
│   │   ├── 20261027055741_login_lockout.sql          # failed_logins + locked_until columns
│   │   ├── 20261027061448_revoke_sessions.sql        # revoke_user_sessions() DB function
│   │   ├── 20261027063000_revoke_single_session.sql  # revoke_session_by_refresh_token() DB function
│   │   └── 20261027064500_drop_change_password_fn.sql # Dropped custom password hash function
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

### Brand Marketplace Specification (React Frontend)
All endpoints directly match the field names consumed by the React brand web app.

- **Currency:** All monetary values are integer INR (e.g. `8000` = ₹8,000).
- **Pagination Envelope:** Used by all list endpoints (`GET /creators`, `/reviews`, etc.):
  ```json
  {
    "results": [ /* items */ ],
    "total": 2480,
    "page": 1,
    "pageSize": 12,
    "totalPages": 207
  }
  ```
- **Error Format:** Standard HTTP codes returning:
  ```json
  {
    "error": { "code": "error_code", "message": "Human readable explanation" },
    "message": "Human readable explanation",
    "code": "error_code"
  }
  ```

### How Auth works

#### Brand Web App Flow
1. **Signup** (`POST /auth/signup`): Send `{ name, email, password, companyName }`. Returns `{ token, user: { id, name, email, companyName, role: "brand" } }` with HTTP 201.
2. **Login** (`POST /auth/login`): Send `{ email, password }`. Returns `{ token, user: { id, name, email, companyName, role: "brand" } }`.
3. **Current User** (`GET /auth/me`): Send header `Authorization: Bearer <token>`. Returns `{ user: { id, name, email, companyName, role: "brand" } }`.
4. **Logout** (`POST /auth/logout`): Invalidate session and returns `204 No Content`.
5. **OAuth** (`POST /auth/oauth/google`, `POST /auth/oauth/apple`): Send `{ idToken }`, returns `{ token, user }`.

#### Creator Mobile App Flow
1. **Signup** (`POST /auth/signup` with `mobile`): Creates unverified account and sends SMS OTP.
2. **Verify OTP** (`POST /auth/otp/verify`): Returns `{ accessToken, refreshToken, next }`.
3. **Password Login** (`POST /auth/login` with `identifier: "+91..."` and `password`).

---

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

#### `POST /auth/login`
Password authentication. Enforces a 5-consecutive-failed-attempts lockout (15 minutes). No auth required.

**Request body:**
```json
{
  "identifier": "+919999999999",
  "password": "testpass123",
  "role": "creator"
}
```
`identifier` can be mobile number or email. `role` is optional (only required if one mobile number holds both brand and creator roles).

**Response `200`:**
```json
{
  "accessToken": "eyJ...",
  "refreshToken": "...",
  "expiresIn": 3600,
  "role": "creator",
  "status": "unverified",
  "next": "onboarding"
}
```

**Error codes:**

| HTTP | `code` | Meaning |
|---|---|---|
| 401 | `invalid_credentials` | Identifier or password does not match |
| 403 | `account_blocked` | Account status is `suspended` or `banned` |
| 403 | `mobile_not_verified` | Account mobile number has not yet been verified with OTP |
| 409 | `role_required` | Multiple accounts found for this mobile — specify `role` |
| 423 | `account_locked` | Locked due to 5 failed attempts (`lockedUntil` timestamp included) |
| 429 | `rate_limited` | Too many rapid requests — wait a moment |

---

#### `GET /auth/me`
Reads the currently authenticated user's profile from their Bearer access token.

**Headers:**
```
Authorization: Bearer <accessToken>
```

**Response `200`:**
```json
{
  "id": "c3d599ff-c559-40f1-9c98-70e7830d4b33",
  "role": "creator",
  "status": "unverified",
  "name": "Test Creator",
  "mobile": "+919999999999"
}
```

---

#### `POST /auth/refresh`
Exchanges a valid refresh token for a fresh access token and rotated refresh token.

**Request body:**
```json
{ "refreshToken": "..." }
```

**Response `200`:**
```json
{
  "accessToken": "eyJ...",
  "refreshToken": "...",
  "expiresIn": 3600
}
```

---

#### `POST /auth/forgot-password`
Initiates password reset by sending an OTP to the account's registered mobile number. Always responds with `{ "ok": true }` (including when the account is unknown or rate-limited) to prevent mobile/account enumeration.

**Request body:**
```json
{ "identifier": "+919999999999" }
```
(`identifier` can be an Indian mobile number or an email).

**Response `200`:**
```json
{ "ok": true }
```

---

#### `POST /auth/reset-password`
Verifies the OTP code and sets the new password. Proof of phone ownership automatically marks `mobile_verified_at = now()`. Automatically invalidates all existing sessions and refresh tokens for that account so old tokens cannot be used.

**Request body:**
```json
{
  "identifier": "+919999999999",
  "code": "123456",
  "newPassword": "resetpass123"
}
```

**Response `200`:**
```json
{ "ok": true }
```

**Error codes:**

| HTTP | `code` | Meaning |
|---|---|---|
| 400 | `invalid_otp` | Code is wrong, expired, or account does not exist |
| 403 | `account_blocked` | Account status is `suspended` or `banned` |
| 409 | `role_required` | Number has both brand and creator accounts — specify `role` |

---

#### `POST /auth/change-password`
Allows an authenticated user to change their password by confirming their current password. Does **not** revoke the caller's session, so subsequent calls with the same access token remain authenticated.

**Headers:** `Authorization: Bearer <accessToken>`

**Request body:**
```json
{
  "current": "resetpass123",
  "next": "changedpass123"
}
```

**Response `200`:**
```json
{ "ok": true }
```

**Error codes:**

| HTTP | `code` | Meaning |
|---|---|---|
| 401 | `unauthorized` | Missing or invalid Bearer access token |
| 422 | `validation_error` | Wrong current password (`fields.current`), or `next` under 8 chars |

---

#### `POST /auth/logout`
Terminates only the session associated with the provided refresh token. No `Authorization` Bearer header is required (so logout succeeds even if the access token has expired). Other devices remain logged in. Always replies `{ "ok": true }`.

**Request body:**
```json
{
  "refreshToken": "4qbjyiiwaysu"
}
```

**Response `200`:**
```json
{ "ok": true }
```

---

### Creator Marketplace & Discovery (Brand Facing)

#### `GET /creators`
Paginated search and filter for discovering content creators. All query parameters are optional.

| Param | Type | Example | Description |
|---|---|---|---|
| `q` | text | `skincare` | Free-text search across name, category, and city |
| `platform` | text | `Instagram` | Platform filter (`Instagram`, `YouTube`, etc.) |
| `category` | text | `Beauty` | Category filter |
| `city` | text | `Bengaluru` | City / location filter |
| `priceMin` / `priceMax` | int | `0` / `10000` | Price range in integer INR |
| `followersMin` / `followersMax` | int | `10000` / `100000` | Follower count range |
| `gender` | text | `female` | Gender filter |
| `language` | text | `English` | Language spoken |
| `sort` | text | `recommended` | `recommended`, `price_asc`, `price_desc`, `followers`, `trending` |
| `page` / `pageSize` | int | `1` / `12` | Pagination controls (default: 1 / 12) |

**Response `200`:**
Returns the pagination envelope containing `Creator[]` in card form:
```json
{
  "results": [
    {
      "id": "ananya-rao",
      "name": "Ananya Rao",
      "category": "Beauty, Skincare",
      "location": "Bengaluru",
      "followers": "48.2k",
      "followerCount": 48200,
      "platform": "Instagram",
      "rating": 4.9,
      "reviewCount": 42,
      "priceFrom": 8000,
      "deliverable": "1 Instagram Reel (30–45 sec)",
      "quotes": ["Delivered two days early", "Great with brand guidelines"],
      "image": "https://images.unsplash.com/photo-1494790108377-be9c29b29330...",
      "topCreator": true
    }
  ],
  "total": 7,
  "page": 1,
  "pageSize": 12,
  "totalPages": 1
}
```

---

#### `GET /creators/suggestions`
Hero search chip suggestions for quick filtering on the frontend:
```json
[
  { "label": "Trending on Instagram", "query": { "platform": "Instagram", "sort": "trending" } },
  { "label": "Under ₹5,000", "query": { "priceMax": 5000 } }
]
```

---

#### `GET /creators/filters`
Available filter options to drive UI dropdowns dynamically:
```json
{
  "platforms": ["Instagram", "YouTube", "LinkedIn", "X", "Facebook"],
  "cities": ["Bengaluru", "Mumbai", "Delhi NCR", "Hyderabad", "Chennai", "Pune", "Kolkata"],
  "categories": ["Beauty, Skincare", "Fashion & Styling", "Tech & Gadgets", "Fitness & Health", "Food & Dining", "Finance & Business", "Travel & Lifestyle"],
  "languages": ["English", "Hindi", "Kannada", "Tamil", "Telugu", "Malayalam", "Marathi"],
  "priceBuckets": [
    { "label": "Under ₹5,000", "max": 5000 },
    { "label": "₹5,000 – ₹10,000", "min": 5000, "max": 10000 },
    { "label": "₹10,000 – ₹20,000", "min": 10000, "max": 20000 },
    { "label": "₹20,000+", "min": 20000 }
  ]
}
```

---

#### `GET /creators/:id`
Full creator profile. Extends the card format with bio, portfolio gallery, trust badges, and response time turnaround:
```json
{
  "id": "ananya-rao",
  "name": "Ananya Rao",
  "category": "Beauty, Skincare",
  "location": "Bengaluru",
  "followers": "48.2k",
  "followerCount": 48200,
  "platform": "Instagram",
  "rating": 4.9,
  "reviewCount": 42,
  "priceFrom": 8000,
  "deliverable": "1 Instagram Reel (30–45 sec)",
  "quotes": ["Delivered two days early", "Great with brand guidelines"],
  "image": "https://images.unsplash.com/...",
  "topCreator": true,
  "bio": "Beauty and clean skincare creator based in Bengaluru...",
  "gallery": ["https://...", "https://..."],
  "badges": ["Top Creator", "Replies within 2 hours"],
  "repliesWithin": "2 hours"
}
```

---

#### `GET /creators/:id/packages`
Bookable packages for the creator booking card.
```json
[
  {
    "id": "pkg_1",
    "title": "1 Instagram Reel (30–45 sec)",
    "note": "Posted to your product feed with a tagged mention.",
    "price": 8000,
    "platform": "Instagram"
  }
]
```

---

#### `GET /creators/:id/reviews`
Paginated reviews with overall rating:
```json
{
  "results": [
    {
      "id": "rev_1",
      "name": "Shreya S.",
      "avatar": "https://...",
      "stars": 5,
      "date": "2025-09-01",
      "text": "Delivered two days early! Matched our brand guidelines."
    }
  ],
  "rating": 4.9,
  "total": 3,
  "page": 1,
  "pageSize": 10,
  "totalPages": 1
}
```

---

#### `GET /creators/:id/similar`
Returns up to 3 similar creators based on category and platform matches.

---

#### `POST /creators/:id/save` and `DELETE /creators/:id/save`
Add/remove a creator to/from the authenticated brand's shortlist (heart icon).
- Requires `Authorization: Bearer <token>`.
- Returns `204 No Content`.

---

### Cart & Custom Offers (Spec Section 4)

#### `GET /cart`
Returns the caller's current booking cart with full creator and package details, line totals, and subtotal.
- Requires `Authorization: Bearer <token>`.

**Response `200`:**
```json
{
  "items": [
    {
      "id": "c43f238b-fbfe-4885-a01b-c3a81dccc6c5",
      "creator": {
        "id": "ananya-rao",
        "name": "Ananya Rao",
        "category": "Beauty, Skincare",
        "location": "Bengaluru",
        "followers": "48.2k",
        "followerCount": 48200,
        "platform": "Instagram",
        "rating": 4.9,
        "reviewCount": 42,
        "priceFrom": 8000,
        "deliverable": "1 Instagram Reel (30–45 sec)",
        "quotes": ["Delivered two days early", "Great with brand guidelines"],
        "image": "https://images.unsplash.com/...",
        "topCreator": true
      },
      "package": {
        "id": "pkg_1",
        "title": "1 Instagram Reel (30–45 sec)",
        "note": "Posted to your product feed with a tagged mention and swipe-up product link.",
        "price": 8000,
        "platform": "Instagram"
      },
      "quantity": 1,
      "lineTotal": 8000
    }
  ],
  "subtotal": 8000
}
```

---

#### `POST /cart/items`
Adds a bookable package to the brand's cart. If the same package is already present, its quantity is automatically incremented.
- Requires `Authorization: Bearer <token>`.

**Request body:**
```json
{
  "creatorId": "ananya-rao",
  "packageId": "pkg_1",
  "quantity": 1
}
```

**Response `200`:** Returns the updated cart object `{ items, subtotal }`.

---

#### `PATCH /cart/items/:itemId`
Updates the quantity of a cart line item. If `quantity <= 0`, the item is automatically removed.
- Requires `Authorization: Bearer <token>`.

**Request body:**
```json
{
  "quantity": 3
}
```

**Response `200`:** Returns the updated cart object `{ items, subtotal }`.

---

#### `DELETE /cart/items/:itemId`
Removes an item from the cart.
- Requires `Authorization: Bearer <token>`.
- Returns `204 No Content`.

---

#### `POST /offers`
"Send a custom offer" to a creator with specific deliverable, budget, message, and deadline.
- Requires `Authorization: Bearer <token>`.

**Request body:**
```json
{
  "creatorId": "ananya-rao",
  "deliverable": "2 Dedicated Reels + 1 IG Live Session for Diwali Launch",
  "budget": 25000,
  "message": "We love your skincare content and would like an exclusive festive partnership.",
  "deadline": "2026-11-15"
}
```

**Response `201`:**
```json
{
  "id": "6428cc84-73d7-4093-a5bd-bd5082aacbcf",
  "creatorId": "ananya-rao",
  "deliverable": "2 Dedicated Reels + 1 IG Live Session for Diwali Launch",
  "budget": 25000,
  "message": "We love your skincare content and would like an exclusive festive partnership.",
  "deadline": "2026-11-15",
  "status": "pending",
  "createdAt": "2026-10-27T08:43:29.728543+00:00"
}
```

---

### Campaigns & Bids (Spec Section 5)

#### `POST /campaigns`
"Post a Job. Let Creators Bid."
- Requires `Authorization: Bearer <token>`.

**Request body:**
```json
{
  "title": "Winter Hydration Skincare Launch",
  "platform": "Instagram",
  "deliverables": "1 Reel (30–45 sec) + 2 Stories with link sticker",
  "budgetMin": 10000,
  "budgetMax": 25000,
  "applyBy": "2026-11-20",
  "brief": "Looking for beauty creators to highlight our new ceramide moisturizer in a clean morning skincare routine."
}
```

**Response `201`:**
```json
{
  "id": "2b210480-ef97-4ad0-ba46-dae0bd5495c3",
  "title": "Winter Hydration Skincare Launch",
  "status": "open_for_bids",
  "platform": "Instagram",
  "deliverables": "1 Reel (30–45 sec) + 2 Stories with link sticker",
  "budgetMin": 10000,
  "budgetMax": 25000,
  "applyBy": "2026-11-20",
  "brief": "Looking for beauty creators to highlight our new ceramide moisturizer...",
  "createdAt": "2026-10-27T08:54:01.611025+00:00"
}
```

---

#### `GET /campaigns`
Lists all campaigns created by the brand with bid counts and avatar previews for recent proposals.
- Requires `Authorization: Bearer <token>`.

**Response `200`:**
```json
[
  {
    "id": "2b210480-ef97-4ad0-ba46-dae0bd5495c3",
    "title": "Winter Hydration Skincare Launch",
    "status": "open_for_bids",
    "platform": "Instagram",
    "deliverables": "1 Reel (30–45 sec) + 2 Stories with link sticker",
    "budgetMin": 10000,
    "budgetMax": 25000,
    "applyBy": "2026-11-20",
    "bidCount": 2,
    "proposalAvatars": [
      "https://images.unsplash.com/photo-1534528741775-53994a69daeb?auto=format&fit=crop&w=600&q=80",
      "https://images.unsplash.com/photo-1494790108377-be9c29b29330?auto=format&fit=crop&w=600&q=80"
    ],
    "createdAt": "2026-10-27T08:54:01.611025+00:00"
  }
]
```

---

#### `GET /campaigns/:id`
Retrieves full details for a single campaign including its status (`open_for_bids`, `closed`, `awarded`).

---

#### `GET /campaigns/:id/bids`
Returns all creator proposals submitted for a campaign.
- Requires `Authorization: Bearer <token>`.

**Response `200`:**
```json
[
  {
    "id": "6343f8ec-047e-4a19-b455-b3456d751954",
    "creator": {
      "id": "ananya-rao",
      "name": "Ananya Rao",
      "note": "I would love to feature this moisturizer in my daily morning regimen!",
      "avatar": "https://images.unsplash.com/photo-1494790108377-be9c29b29330?auto=format&fit=crop&w=600&q=80"
    },
    "price": 18000,
    "status": "submitted"
  }
]
```

---

#### `POST /campaigns/:id/bids/:bidId/select`
Picks a winning creator proposal. Automatically updates the campaign to `awarded`, marks the bid as `selected`, marks rival bids as `rejected`, and creates an Order in escrow (`in_escrow`).
- Requires `Authorization: Bearer <token>`.

**Response `201`:**
```json
{
  "order": {
    "id": "3ae44a29-66ed-4667-8b51-2440ccc080d1",
    "brandId": "28cfcb14-4876-49b5-984f-2824e08c43cf",
    "creatorId": "ananya-rao",
    "campaignId": "2b210480-ef97-4ad0-ba46-dae0bd5495c3",
    "bidId": "6343f8ec-047e-4a19-b455-b3456d751954",
    "deliverable": "1 Reel (30–45 sec) + 2 Stories with link sticker",
    "amount": 18000,
    "status": "in_escrow",
    "createdAt": "2026-10-27T08:54:06.948979+00:00"
  }
}
```

---

#### `PATCH /campaigns/:id`
Edits campaign details (the "Edit" button on the UI).
- Requires `Authorization: Bearer <token>`.

---

#### `DELETE /campaigns/:id`
Deletes a campaign draft or job listing.
- Requires `Authorization: Bearer <token>`.
- Returns `204 No Content`.

---

### Orders & Escrow (Spec Section 6) — "Money moves only when you approve"

Escrow contracts hold the brand's payment safely until deliverables are approved.

**Status state machine:**
`in_escrow` → `draft_submitted` → (`changes_requested` → `draft_submitted`)* → `released` → `completed`.

#### `GET /orders`
Lists all orders belonging to the authenticated brand, joined with complete creator card details. Optional filter `?status=in_escrow`.
- Requires `Authorization: Bearer <token>`.

**Response `200`:**
```json
[
  {
    "id": "a543f5bb-8180-43c4-a38f-9ddd4cb80bdc",
    "creator": {
      "id": "ananya-rao",
      "name": "Ananya Rao",
      "category": "Beauty, Skincare",
      "location": "Bengaluru",
      "followers": "48.2k",
      "followerCount": 48200,
      "platform": "Instagram",
      "rating": 4.9,
      "reviewCount": 42,
      "priceFrom": 8000,
      "deliverable": "1 Instagram Reel (30–45 sec)",
      "image": "https://images.unsplash.com/photo-1494790108377-be9c29b29330?auto=format&fit=crop&w=600&q=80",
      "topCreator": true
    },
    "deliverable": "1 Instagram Reel (30–45 sec)",
    "amount": 8000,
    "status": "in_escrow",
    "campaignId": null,
    "bidId": null,
    "packageId": "pkg_1",
    "paymentIntent": "pi_test_a543f5bb818043c4",
    "clientSecret": "pi_test_secret_a543f5bb818043c4",
    "changeNote": null,
    "draftUrl": null,
    "releasedAt": null,
    "createdAt": "2026-10-27T09:02:17.382098+00:00",
    "updatedAt": "2026-10-27T09:02:17.382098+00:00"
  }
]
```

---

#### `GET /orders/:id`
Retrieves single order details, escrow status, and deliverables.
- Requires `Authorization: Bearer <token>`.

---

#### `POST /orders`
Direct booking or checkout from packages/offers without an open campaign.
- Requires `Authorization: Bearer <token>`.

**Request body:**
```json
{
  "creatorId": "ananya-rao",
  "packageId": "pkg_1",
  "deliverable": "1 Instagram Reel (30–45 sec)",
  "amount": 8000
}
```

**Response `201`:** Returns the created order in `in_escrow` status.

---

#### `POST /orders/:id/pay`
Funds escrow via payment provider (Razorpay test mode). Generates and returns a client token / payment intent for frontend confirmation.
- Requires `Authorization: Bearer <token>`.

**Response `200`:**
```json
{
  "orderId": "a543f5bb-8180-43c4-a38f-9ddd4cb80bdc",
  "amount": 8000,
  "currency": "INR",
  "clientToken": "pi_test_secret_a543f5bb818043c4",
  "clientSecret": "pi_test_secret_a543f5bb818043c4",
  "paymentIntent": "pi_test_a543f5bb818043c4",
  "status": "in_escrow",
  "provider": "razorpay_test"
}
```

---

#### `POST /orders/:id/submit-draft`
Submits draft video or creative asset for review. Moves status from `in_escrow` (or `changes_requested`) to `draft_submitted`. Automatically posts an update with asset link to the order discussion thread.
- Requires `Authorization: Bearer <token>`.

**Request body:**
```json
{
  "draftUrl": "https://assets.collivra.com/drafts/ananya_reel_v1.mp4",
  "note": "Here is the first cut of the reel! Let me know your thoughts."
}
```

---

#### `POST /orders/:id/request-changes`
"Request Changes" button. Transitions order to `changes_requested`, records the feedback note, and logs an entry to the order conversation thread.
- Requires `Authorization: Bearer <token>`.

**Request body:**
```json
{
  "note": "Great lighting! Could you please make the product bottle more visible in the first 3 seconds?"
}
```

**Response `200`:** Returns updated order object with `status: 'changes_requested'`.

---

#### `POST /orders/:id/approve`
"Approve & Pay" button. Releases escrowed funds to the creator. Moves status to `released`, timestamps `releasedAt`, and logs an automated release notification in the order thread.
- Requires `Authorization: Bearer <token>`.

**Response `200`:**
```json
{
  "id": "a543f5bb-8180-43c4-a38f-9ddd4cb80bdc",
  "status": "released",
  "releasedAt": "2026-10-27T09:02:33.511Z"
}
```

---

#### `GET /orders/:id/messages`
Retrieves complete conversation thread and review audit trail for the order.
- Requires `Authorization: Bearer <token>`.

**Response `200`:**
```json
[
  {
    "id": "a5bffdf3-01f4-44cb-8662-bb5f05d86e88",
    "orderId": "a543f5bb-8180-43c4-a38f-9ddd4cb80bdc",
    "senderId": "28cfcb14-4876-49b5-984f-2824e08c43cf",
    "senderName": "Acme Brand",
    "senderRole": "brand",
    "message": "Hi Ananya, excited to work together! Please focus on our glow serum features.",
    "attachments": [],
    "createdAt": "2026-10-27T09:02:22.771239+00:00"
  }
]
```

---

#### `POST /orders/:id/messages`
Posts a message or attachment into the order's collaboration thread.
- Requires `Authorization: Bearer <token>`.

**Request body:**
```json
{
  "message": "Looks great, approving now!",
  "attachments": []
}
```

**Response `201`:** Returns the created message object.

---

### Brand Dashboard, Shortlists, Content Library & Reporting (Spec Section 7)

#### `GET /dashboard/summary`
Home screen view for the logged-in brand app. Returns user greeting, onboarding checklist status, high-level business stats, and top-rated creators.
- Requires `Authorization: Bearer <token>`.

**Response `200`:**
```json
{
  "greetingName": "Acme Marketing",
  "todos": [
    { "id": "complete-profile", "label": "Complete brand profile & logo", "done": true },
    { "id": "first-job", "label": "Post your first campaign job", "done": true },
    { "id": "hire-creator", "label": "Hire a creator via escrow", "done": true },
    { "id": "add-payment-method", "label": "Set up payment method", "done": true }
  ],
  "stats": [
    { "label": "Total Creators Hired", "value": "3", "sub": "+1 this week" },
    { "label": "Active Campaigns", "value": "1", "sub": "2 bids received" },
    { "label": "Escrow Balance", "value": "₹26,000", "sub": "Protected in escrow" },
    { "label": "Deliverables Approved", "value": "5", "sub": "100% on time" }
  ],
  "topCreators": [
    {
      "id": "ananya-rao",
      "name": "Ananya Rao",
      "category": "Beauty, Skincare",
      "location": "Bengaluru",
      "followers": "48.2k",
      "followerCount": 48200,
      "platform": "Instagram",
      "rating": 4.9,
      "reviewCount": 42,
      "priceFrom": 8000,
      "deliverable": "1 Instagram Reel (30–45 sec)",
      "image": "https://images.unsplash.com/photo-1494790108377-be9c29b29330?auto=format&fit=crop&w=600&q=80",
      "topCreator": true
    }
  ]
}
```

---

#### `PATCH /dashboard/todos/:id`
Toggles an onboarding task checkbox.
- Requires `Authorization: Bearer <token>`.

**Request body:**
```json
{
  "done": true
}
```

**Response `200`:** `{ "done": true }`

---

#### `GET /lists`
Returns all custom shortlists created by the brand, including the total creator count and up to 4 avatar cover images.
- Requires `Authorization: Bearer <token>`.

**Response `200`:**
```json
[
  {
    "id": "515354be-e1db-44f8-bdb0-74b969d40ef5",
    "name": "Diwali Beauty Campaign",
    "count": 2,
    "updatedAt": "2026-10-27T09:09:48.319Z",
    "covers": [
      "https://images.unsplash.com/photo-1494790108377-be9c29b29330?auto=format&fit=crop&w=600&q=80",
      "https://images.unsplash.com/photo-1507003211169-0a1dd7228f2d?auto=format&fit=crop&w=600&q=80"
    ]
  }
]
```

---

#### `POST /lists`
Creates a new shortlist.
- Requires `Authorization: Bearer <token>`.

**Request body:**
```json
{
  "name": "Diwali Beauty Campaign"
}
```

**Response `201`:** Returns new list envelope with `count: 0` and empty `covers`.

---

#### `GET /lists/:id`
Returns full list details and its array of creator profile cards.
- Requires `Authorization: Bearer <token>`.

---

#### `POST /lists/:id/creators`
Adds a creator to the specified shortlist.
- Requires `Authorization: Bearer <token>`.

**Request body:**
```json
{
  "creatorId": "ananya-rao"
}
```

**Response `201`:** `{ "ok": true, "listId": "...", "creatorId": "ananya-rao" }`

---

#### `DELETE /lists/:id/creators/:creatorId`
Removes a creator from a shortlist.
- Requires `Authorization: Bearer <token>`.
- Returns `204 No Content`.

---

#### `PATCH /lists/:id`
Renames an existing shortlist (accessible from the "•••" card menu).
- Requires `Authorization: Bearer <token>`.

**Request body:**
```json
{
  "name": "Diwali & Festive Mega Stars"
}
```

---

#### `POST /lists/:id/duplicate`
Duplicates a shortlist and copies all contained creators under name `"<Name> (Copy)"` (from the "•••" card menu).
- Requires `Authorization: Bearer <token>`.
- Returns `201` with the new list object.

---

#### `DELETE /lists/:id`
Deletes a shortlist and unlinks all members.
- Requires `Authorization: Bearer <token>`.
- Returns `204 No Content`.

---

#### `GET /deliverables`
Content library filterable by search term `q`, `jobId`, `platform`, `from`, and `to`. Returns list of deliverables with status (`Approved`, `Needs review`, `Live`, `Revision asked`), preview links, and download URLs.
- Requires `Authorization: Bearer <token>`.

**Response `200`:**
```json
[
  {
    "id": "ddefa7ce-503c-45de-a48b-6b55ef43ca53",
    "content": "Festive Lookbook Outfit Styling",
    "type": "Reel",
    "creator": {
      "id": "neha-sharma",
      "name": "Neha Sharma"
    },
    "job": null,
    "platform": "Instagram",
    "deliveredAt": "2026-10-26T09:09:49.123Z",
    "status": "Needs review",
    "previewUrl": "https://images.unsplash.com/photo-1490481651871-ab68de25d43d?auto=format&fit=crop&w=600&q=80",
    "downloadUrl": "https://assets.collivra.com/deliverables/neha_festive_cut.mp4"
  }
]
```

---

#### `GET /deliverables/:id`
Returns a single deliverable with preview/download URLs and complete creator card.
- Requires `Authorization: Bearer <token>`.

---

#### `GET /deliverables/export`
"Download all" export generating a clean CSV file with content metadata, platform, creator name, status, and download links.
- Requires `Authorization: Bearer <token>`.
- Response: `Content-Type: text/csv` with `Content-Disposition: attachment; filename="collivra_deliverables.csv"`.

---

#### `GET /reporting`
Campaign analytics overview supporting `?period=` (`last_30_days`, `last_3_months`, `last_6_months`, `last_12_months`, `all_time`).
- Requires `Authorization: Bearer <token>`.

**Response `200`:**
```json
{
  "period": "last_6_months",
  "stats": [
    { "label": "Total Spend", "value": "₹1,45,000", "sub": "Across 6 campaigns" },
    { "label": "Total Views", "value": "1.2M", "sub": "+24% vs prior period" },
    { "label": "Avg. Engagement Rate", "value": "4.8%", "sub": "Industry avg 2.4%" },
    { "label": "Avg. Cost Per 1k Views (CPM)", "value": "₹120", "sub": "Best on Instagram Reels" }
  ],
  "viewsByMonth": [
    { "month": "May", "instagram": 120000, "youtube": 60000 },
    { "month": "Jun", "instagram": 150000, "youtube": 80000 },
    { "month": "Jul", "instagram": 180000, "youtube": 95000 },
    { "month": "Aug", "instagram": 220000, "youtube": 110000 },
    { "month": "Sep", "instagram": 260000, "youtube": 140000 },
    { "month": "Oct", "instagram": 310000, "youtube": 165000 }
  ],
  "spendByPlatform": [
    { "label": "Instagram", "amount": 95000, "pct": 65 },
    { "label": "YouTube", "amount": 50000, "pct": 35 }
  ],
  "topCreators": [
    {
      "creator": { "id": "ananya-rao", "name": "Ananya Rao" },
      "posts": 3,
      "views": 450000,
      "engagement": "5.4%",
      "spend": 32000,
      "costPer1k": 71
    }
  ]
}
```

---

#### `GET /reporting/export`
Exports tabular campaign analytics as CSV.
- Requires `Authorization: Bearer <token>`.
- Response: `Content-Type: text/csv` with `Content-Disposition: attachment; filename="collivra_reporting_last_6_months.csv"`.

---

### Creator Onboarding Endpoints (Pages 17 & 18)

#### `POST /uploads/presign`
Generates a short-lived presigned upload URL for direct file uploads to private Supabase Storage buckets. Currently allows `kyc-id` purpose (bucket `kyc-docs`). Enforces maximum 10 MB and MIME types `image/jpeg`, `image/png`, and `application/pdf`. Records an entry in the `uploads` table with `status: 'pending'`.

**Request body:**
```json
{
  "purpose": "kyc-id",
  "fileName": "passport.pdf",
  "contentType": "application/pdf",
  "size": 2450000
}
```

**Response `200`:**
```json
{
  "uploadUrl": "https://.../storage/v1/object/upload/sign/kyc-docs/{userId}/{uuid}-passport.pdf?token=...",
  "fileKey": "{userId}/{uuid}-passport.pdf"
}
```

**Errors:** `413 file_too_large` (>10 MB), `415 unsupported_media_type` (not JPEG, PNG, or PDF).

---

#### `PUT /creator/onboarding/profile`
Upserts public-facing creator details (`category`, `languages`, `city`, `topics`). Accessible only while creator status is `unverified`, `needs_info`, or `pending`.

**Request body:**
```json
{
  "category": "Tech & Gadgets",
  "languages": ["English", "Hindi"],
  "city": "Bengaluru",
  "topics": ["AI", "Smartphones", "Code"]
}
```

**Response `200`:**
```json
{
  "profile": {
    "category": "Tech & Gadgets",
    "languages": ["English", "Hindi"],
    "city": "Bengaluru",
    "topics": ["AI", "Smartphones", "Code"],
    "headline": null,
    "bio": null
  }
}
```

---

#### `GET /creator/social/:platform/connect-url`
Initiates OAuth connection for Instagram or YouTube. In development stub mode (`SOCIAL_MODE=stub`), generates a signed callback URL with an HMAC-SHA256 signature containing `userId`, `platform`, and a 10-minute expiry timestamp.

**Response `200`:**
```json
{
  "url": "https://.../functions/v1/api/v1/creator/social/instagram/callback?state=eyJ..."
}
```

---

#### `GET /creator/social/:platform/callback`
Verifies the HMAC-signed state token. In stub mode, populates the `social_accounts` table with simulated creator statistics (`stats_source: 'stub'`). Supports error simulation via query parameters (`?simulate_error=too_small` -> 400, `?simulate_error=private` -> 400).

**Response `200`:**
```json
{
  "connected": true,
  "platform": "instagram",
  "handle": "creator_insta",
  "followers": 45200,
  "statsSource": "stub"
}
```

---

#### `POST /creator/kyc/id`
Attaches an uploaded identity document (`aadhaar`, `passport`, `voter_id`, `driving_licence`). Validates that the `fileKey` exists in the `uploads` table, belongs to the caller, and is located in the `kyc-docs` bucket. Sets `id_status: 'checking'`.

**Request body:**
```json
{
  "docType": "passport",
  "fileKey": "{userId}/passport.pdf"
}
```

**Response `200`:**
```json
{ "status": "checking" }
```

---

#### `POST /creator/kyc/pan`
Validates 10-character Indian Permanent Account Number (PAN) format (`^[A-Z]{5}[0-9]{4}[A-Z]$`). Encrypts the full PAN with AES-GCM (256-bit) using `FIELD_ENCRYPTION_KEY` and stores the ciphertext, `pan_last4`, and `name_on_pan`. Compares `nameOnPan` with the profile name and returns verification status.

**Request body:**
```json
{
  "pan": "ABCDE1234F",
  "nameOnPan": "Test Creator"
}
```

**Response `200`:**
```json
{
  "valid": true,
  "nameMatch": true,
  "panLast4": "234F"
}
```

---

#### `POST /creator/bank`
Validates bank account number (9-18 digits) and Indian Financial System Code (IFSC, `^[A-Z]{4}0[A-Z0-9]{6}$`), or a UPI VPA (`name@upi`). Encrypts the bank account number with AES-GCM (256-bit). Performs word-order and case-insensitive comparison between `holderName` and `name_on_pan`.

**Request body:**
```json
{
  "accountNumber": "123456789012",
  "ifsc": "HDFC0001234",
  "holderName": "Test Creator"
}
```

**Response `200`:**
```json
{
  "verified": true,
  "maskedAccount": "XXXX9012",
  "nameMatch": true
}
```

---

#### `POST /creator/onboarding/submit`
Validates that all prerequisites are completed: profile details present, at least one social account connected, valid PAN recorded, verified bank details, and an attached KYC ID document. If any element is missing, returns `422 onboarding_incomplete` with a breakdown in `fields`. Upon validation, creates/updates `verification_requests` row (`status: 'pending'`) and updates `profiles.status` to `'pending'`.

**Response `200`:**
```json
{ "status": "pending" }
```

---

#### `GET /{role}/verification-status`
Returns the status of the caller's verification request (`unverified`, `pending`, `needs_info`, `approved`, or `rejected`), any reviewer feedback reasons or messages, and estimated review turnaround time (default 24 hours).

**Response `200`:**
```json
{
  "status": "pending",
  "reasons": [],
  "message": null,
  "estimatedHours": 24
}
```

---

### Planned endpoints (not yet live)

Aligned with Pages 16, 18, and 50 of the API specification:

| Page | Area | Endpoints |
|---|---|---|
| **Page 16** | Brand setup | `GET /brand/profile`, `PUT /brand/profile`, `GET /meta/geocode`, `POST /brand/gst/verify`, `POST /brand/onboarding/submit` |
| **Page 18** | Support tickets | `POST /support/tickets` |
| **Page 50** | Admin verification queue | Admin verification review queue, reviewer actions (`approve`, `reject`, `request-info`) |

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
| `name` | text | Display name |
| `mobile` | text | E.164 format (e.g. `+919876543210`) |
| `email` | text | Optional; null if the user signed up with mobile only |
| `mobile_verified_at` | timestamp | When the user first verified their OTP (on signup verify or password reset) |
| `failed_logins` | int | Count of consecutive wrong password attempts (reset on success) |
| `locked_until` | timestamp | Account is locked until this time after 5 wrong attempts; null otherwise |
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
| `purpose` | `signup`, `login`, or `reset` |
| `created_at` | When the send happened |

### `creator_profiles`
Public-facing creator information. Upserted during onboarding (`PUT /creator/onboarding/profile`).

| Column | Type | What it holds |
|---|---|---|
| `user_id` | UUID | Foreign key to `profiles.id` (primary key) |
| `category` | text | Creator industry / niche (e.g. "Tech & Gadgets") |
| `languages` | text[] | Languages spoken / content created in (max 10) |
| `city` | text | Location / base city |
| `topics` | text[] | Tags or topics (max 10) |
| `headline` | text | Short professional headline |
| `bio` | text | Detailed creator bio |
| `visibility` | jsonb | Public visibility flags (`{"followers":true,"audience":true,"rates":true}`) |
| `slug` | text | Unique profile URL slug |

*Access rules:* Creator reads own row; internal admins read all rows; writes restricted to service role.

---

### `social_accounts`
Connected social media accounts (Instagram, YouTube). Created via OAuth or development stub callbacks.

| Column | Type | What it holds |
|---|---|---|
| `id` | UUID | Unique identifier |
| `user_id` | UUID | Foreign key to `profiles.id` |
| `platform` | enum | `instagram` or `youtube` |
| `handle` | text | Public handle or channel name |
| `external_id` | text | Platform-assigned unique ID (unique per platform) |
| `followers` | int | Follower or subscriber count |
| `avg_views` | int | Average view count per post/video |
| `engagement` | numeric | Engagement rate percentage (e.g. 4.25%) |
| `audience` | jsonb | Audience demographics (top cities, age/gender breakdown) |
| `stats_source` | enum | `verified_api`, `self_reported`, or `stub` (marks mock development data) |
| `token_ciphertext`| text | Encrypted OAuth tokens (never returned in any API reply) |

*Access rules:* Creator reads own public statistics columns; token columns never granted to clients; writes restricted to service role.

---

### `creator_kyc`
Sensitive Know Your Customer (KYC) identity and banking information. Server-only table.

| Column | Type | What it holds |
|---|---|---|
| `user_id` | UUID | Foreign key to `profiles.id` (primary key) |
| `pan_ciphertext` | text | Full 10-character PAN encrypted with AES-256-GCM |
| `pan_last4` | text | Plaintext last 4 characters of PAN (e.g. `234F`) for display |
| `name_on_pan` | text | Name as registered on PAN |
| `pan_valid` | boolean | Verification validity flag |
| `pan_name_match`| boolean | True if name matches profile name |
| `id_doc_type` | text | `aadhaar`, `passport`, `voter_id`, or `driving_licence` |
| `id_file_key` | text | Storage object key in `kyc-docs` bucket |
| `id_status` | text | `none`, `checking`, `verified`, or `failed` |
| `bank_account_ciphertext` | text | Bank account number encrypted with AES-256-GCM |
| `bank_account_last4` | text | Last 4 digits of bank account for display |
| `bank_ifsc` | text | 11-character bank IFSC code |
| `bank_holder_name` | text | Account holder name reported by user |
| `upi_id` | text | Virtual Payment Address (UPI) |
| `bank_verified` | boolean | Bank account verification status |
| `bank_name_match` | boolean | True if bank holder name matches PAN name |
| `provider` | text | Verification provider (`stub` indicates simulated check) |

*Access rules:* **No RLS grant policies exist for clients.** Direct access via client REST API is strictly forbidden (`permission denied`). Only the Edge Function can read or write via the service-role client.

---

### `verification_requests`
Review queue tracking submissions for admin verification. Shared by creator and brand onboarding.

| Column | Type | What it holds |
|---|---|---|
| `id` | UUID | Unique review request ID |
| `user_id` | UUID | Foreign key to `profiles.id` |
| `type` | enum | `brand` or `creator` |
| `status` | enum | `pending`, `needs_info`, `rejected`, or `approved` |
| `reasons` | text[] | Rejection or clarification reasons from admin |
| `message` | text | Custom note or feedback from reviewer |
| `reviewer_id` | UUID | Foreign key to admin `profiles.id` |
| `submitted_at`| timestamptz | When user submitted onboarding |
| `reviewed_at` | timestamptz | When admin took action |

*Access rules:* Creator/brand reads own rows; admins read all rows; writes restricted to service role. Only one open request (`pending` or `needs_info`) is permitted per user.

---

### `uploads`
Tracks files uploaded directly to Supabase Storage buckets via server-issued presigned URLs.

| Column | Type | What it holds |
|---|---|---|
| `id` | UUID | Unique upload ID |
| `owner_id` | UUID | Foreign key to `profiles.id` |
| `purpose` | text | `kyc-id`, `brand-doc`, `logo`, `job-ref`, `draft`, `evidence`, `chat`, `proof` |
| `bucket` | text | Storage bucket name (`kyc-docs`, etc.) |
| `file_key` | text | Path inside storage bucket `{userId}/{uuid}-{filename}` |
| `content_type` | text | MIME type of uploaded file |
| `size_bytes` | bigint | Declared file size in bytes |
| `status` | text | `pending`, `uploaded`, or `attached` |

---

### `cart_items`
Stores packages added to a brand's booking cart.

| Column | Type | What it holds |
|---|---|---|
| `id` | UUID | Unique cart line item ID |
| `user_id` | UUID | Foreign key to `profiles.id` (brand) |
| `creator_id` | text | References `creators.id` |
| `package_id` | text | References `creator_packages.id` |
| `quantity` | int | Quantity of package (default 1) |
| `created_at` | timestamptz | When item was added |
| `updated_at` | timestamptz | Last quantity update |

*Access rules (RLS):* Authenticated brands can only select, insert, update, or delete their own cart items.

---

### `custom_offers`
Tracks custom collaboration offers sent by brands to creators.

| Column | Type | What it holds |
|---|---|---|
| `id` | UUID | Unique offer ID |
| `brand_id` | UUID | Foreign key to `profiles.id` (brand) |
| `creator_id` | text | References `creators.id` |
| `deliverable` | text | Deliverable description |
| `budget` | int | Proposed budget in integer INR |
| `message` | text | Personal note from the brand |
| `deadline` | text | Proposed delivery deadline |
| `status` | text | `pending`, `accepted`, `declined`, or `expired` |

*Access rules (RLS):* Authenticated brands can select, insert, update, or delete their own custom offers.

### `campaigns`
Job postings published by brands for creators to bid on.

| Column | Type | What it holds |
|---|---|---|
| `id` | UUID | Unique campaign ID |
| `brand_id` | UUID | Foreign key to `profiles.id` (brand) |
| `title` | text | Job title (e.g. "Winter Hydration Skincare Launch") |
| `platform` | text | Primary platform (`Instagram`, `YouTube`, etc.) |
| `deliverables` | text | Scope of deliverables required |
| `budget_min` | int | Minimum budget in integer INR |
| `budget_max` | int | Maximum budget in integer INR |
| `apply_by` | text | Application deadline date |
| `brief` | text | Detailed creative brief / campaign instructions |
| `status` | text | `open_for_bids`, `closed`, or `awarded` |

*Access rules (RLS):* Anyone can view campaigns for marketplace discovery; only the owning brand can update or delete their campaign.

---

### `campaign_bids`
Proposals submitted by creators on open brand campaigns.

| Column | Type | What it holds |
|---|---|---|
| `id` | UUID | Unique bid ID |
| `campaign_id` | UUID | Foreign key to `campaigns.id` |
| `creator_id` | text | References `creators.id` |
| `price` | int | Proposed price in integer INR |
| `note` | text | Pitch / cover note from the creator |
| `status` | text | `submitted`, `selected`, or `rejected` |

*Access rules (RLS):* The campaign brand can view all bids submitted to their campaign; creators can manage their own bids.

---

### `orders`
Escrow contracts created when a brand hires a creator (via package booking or awarding a campaign bid). "Money moves only when you approve."

| Column | Type | What it holds |
|---|---|---|
| `id` | UUID | Unique order ID |
| `brand_id` | UUID | Foreign key to `profiles.id` (brand) |
| `creator_id` | text | References `creators.id` |
| `campaign_id` | UUID | Optional foreign key to awarded `campaigns.id` |
| `bid_id` | UUID | Optional foreign key to selected `campaign_bids.id` |
| `package_id` | text | Optional foreign key to `creator_packages.id` |
| `deliverable` | text | Agreed deliverable specification |
| `amount` | int | Total contract amount held in escrow (integer INR) |
| `status` | text | `in_escrow`, `draft_submitted`, `changes_requested`, `released`, or `completed` |
| `payment_intent` | text | Test-mode payment gateway intent identifier |
| `client_secret` | text | Test-mode payment provider confirmation secret |
| `change_note` | text | Brand's revision notes when requesting modifications |
| `draft_url` | text | Deliverable media link submitted by creator |
| `released_at` | timestamptz | Exact timestamp when brand released funds to creator |
| `created_at` | timestamptz | When order was placed |
| `updated_at` | timestamptz | Last status update |

*Access rules (RLS):* Authenticated brands can view and manage their own orders.

---

### `order_messages`
Collaboration and audit thread for each order. Captures brand instructions, creator draft submissions, revision notes, and payment release confirmations.

| Column | Type | What it holds |
|---|---|---|
| `id` | UUID | Unique message ID |
| `order_id` | UUID | Foreign key to `orders.id` |
| `sender_id` | UUID | Foreign key to `profiles.id` |
| `sender_name` | text | Display name of the sender |
| `sender_role` | text | Sender role (`brand`, `creator`, or `system`) |
| `message` | text | Message body or revision note |
| `attachments` | jsonb | Array of attachments (e.g. `[{ url, type }]`) |
| `created_at` | timestamptz | When message was posted |

*Access rules (RLS):* Accessible only to the participants of the associated order.

---

### `brand_todos`
Tracks brand onboarding checklist items (e.g. logo, first job, escrow hire).

| Column | Type | What it holds |
|---|---|---|
| `user_id` | UUID | Foreign key to `profiles.id` |
| `todo_id` | text | Task slug (`complete-profile`, `first-job`, `hire-creator`, `add-payment-method`) |
| `label` | text | Display label shown in checklist |
| `done` | boolean | Completion flag (default false) |
| `updated_at` | timestamptz | Last modified timestamp |

*Access rules (RLS):* Authenticated brands can only manage their own checklist items.

---

### `shortlists`
Custom creator collections curated by brands.

| Column | Type | What it holds |
|---|---|---|
| `id` | UUID | Unique shortlist ID |
| `brand_id` | UUID | Foreign key to `profiles.id` |
| `name` | text | Shortlist name (e.g. "Diwali Beauty Campaign") |
| `created_at` | timestamptz | Created timestamp |
| `updated_at` | timestamptz | Last modified timestamp |

*Access rules (RLS):* Authenticated brands can only view, create, rename, or delete their own shortlists.

---

### `shortlist_creators`
Many-to-many join table between shortlists and creators.

| Column | Type | What it holds |
|---|---|---|
| `id` | UUID | Unique relation ID |
| `list_id` | UUID | Foreign key to `shortlists.id` (on delete cascade) |
| `creator_id` | text | Foreign key to `creators.id` (on delete cascade) |
| `created_at` | timestamptz | When creator was added |

*Access rules (RLS):* Authenticated brands can only view and mutate entries belonging to their shortlists.

---

### `deliverables`
Content library assets delivered by creators for brand campaigns and orders.

| Column | Type | What it holds |
|---|---|---|
| `id` | UUID | Unique deliverable asset ID |
| `brand_id` | UUID | Foreign key to `profiles.id` |
| `creator_id` | text | Foreign key to `creators.id` |
| `campaign_id` | UUID | Optional foreign key to `campaigns.id` |
| `order_id` | UUID | Optional foreign key to `orders.id` |
| `content` | text | Deliverable title / description |
| `type` | text | Content format (`Reel`, `Video`, `Story`, `Post`) |
| `platform` | text | Platform channel (`Instagram`, `YouTube`) |
| `status` | text | Approval state (`Approved`, `Needs review`, `Live`, `Revision asked`) |
| `preview_url` | text | Image/poster preview link |
| `download_url` | text | High-resolution master asset download URL |
| `delivered_at` | timestamptz | Timestamp delivered |
| `created_at` | timestamptz | Timestamp created |

*Access rules (RLS):* Authenticated brands can only access their own deliverables.

---

### Storage Buckets

#### `kyc-docs` (Private)
Holds identity documents for KYC verification.
- **Max file size:** 10 MB (10,485,760 bytes).
- **Allowed MIME types:** `image/jpeg`, `image/png`, `application/pdf`.
- **Access control:** No public access policies. Writes require a server-issued presigned upload URL (`POST /uploads/presign`). Admin viewing requires short-lived signed download URLs. Direct client reading or writing is blocked.

---

### Database Functions

#### `revoke_user_sessions(uid uuid)`
Revokes all active sessions and refresh tokens for a user in Supabase Auth (`auth.sessions` and `auth.refresh_tokens`). Defined as `security definer`, accessible only to `service_role`. Used on password reset (`POST /auth/reset-password`).

#### `revoke_session_by_refresh_token(p_refresh_token text)`
Terminates only the session corresponding to a specific refresh token. Defined as `security definer`, accessible only to `service_role`. Used during logout (`POST /auth/logout`).

---

## 7. Secrets and access

**Never write any secret value in this file or in code. Store them only in Supabase secrets (`supabase secrets set`) or a secure secrets manager.**

| Secret name | What it is | Who to ask |
|---|---|---|
| `SUPABASE_URL` | The project's API URL | Auto-injected by Supabase into Edge Functions |
| `SUPABASE_ANON_KEY` | Public key for anonymous requests | Auto-injected |
| `SUPABASE_SERVICE_ROLE_KEY` | Admin key — full DB access, never expose to frontend | Auto-injected |
| `FIELD_ENCRYPTION_KEY` | 32-byte Base64 AES-GCM key used for encrypting PAN and bank numbers | Set in Supabase secrets; store in password manager |
| `STATE_SIGNING_KEY` | Secret key used for HMAC-SHA256 signing of social connect OAuth states | Set in Supabase secrets |
| `KYC_MODE` | Provider mode for KYC verification (`stub` or `live`) | Default: `stub` |
| `SOCIAL_MODE` | Provider mode for social metrics (`stub` or `live`) | Default: `stub` |
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
| 2026-10-27 | **AES-256-GCM field-level encryption for PAN and bank numbers.** | Encryption keys reside solely in Edge Function secrets (`FIELD_ENCRYPTION_KEY`), not in the database. A leaked database dump never exposes sensitive financial credentials. |
| 2026-10-27 | **Strictly private `kyc-docs` storage bucket with zero public policies.** | Direct reading and writing by `anon` or `authenticated` roles is disallowed. Uploads must use server-issued presigned URLs, and admin review uses short-lived signed URLs. |
| 2026-10-27 | **Explicit `stub` tags in database for development metrics and verification.** | Fake stats and mock checks are marked with `stats_source: 'stub'` and `provider: 'stub'` so real accounts are never mistakenly approved in admin queues based on mock data. |
| 2026-10-27 | **PAN/Bank name mismatch warns admin but does not block onboarding.** | The specification states that bank account holder names "should match" the PAN. Name differences (e.g. spelling variations or initials) are stored in `bank_name_match` for admin inspection rather than hard-blocking creator submission. |
| 2026-10-27 | **Supabase-only backend.** No separate application server. | Reduces infrastructure to manage; Postgres + Auth + Storage + Edge Functions covers every need for this stage. |
| 2026-10-27 | **Hono for Edge Function routing.** | Lightweight, Deno-compatible, gives clean route definitions and middleware without bloat. |
| 2026-10-27 | **Twilio Verify for OTP.** | Handles code generation, delivery, expiry (10 min), and attempt limiting (5 tries) — no need to duplicate that logic in our DB. |
| 2026-10-27 | **Dev-mode OTP bypass scoped to a number whitelist.** | A fixed code on all numbers would be an auth bypass if left on in prod. Whitelisting specific test numbers limits blast radius. Must be removed before launch. |
| 2026-10-27 | **API spec wins over feature guide when they conflict.** | The spec is the signed contract between frontend and backend. Deviating from it silently breaks the frontend. Any spec change must be agreed by both sides. |
| 2026-10-27 | **Placeholder emails for mobile-only users.** | Supabase Auth requires an email. Users who sign up with only a mobile number get an internal address (`<number>.<role>@mobile.collivra.app`) that is never shown or stored in their profile. |
| 2026-10-27 | **`otp_send_log` for rate limiting, not a full `otp_codes` table.** | Twilio Verify already manages code storage, expiry, and attempt counting. We only need to track send count to enforce the spec's 5-sends-per-hour limit. |
| 2026-10-27 | **User-scoped `PUT /auth/v1/user` for password change.** | `admin.auth.admin.updateUserById` unconditionally terminates all sessions in Supabase GoTrue; updating via the user's bearer token keeps the caller's session and refresh token valid. |
| 2026-10-27 | **`revoke_session_by_refresh_token` database function.** | Allows `POST /auth/logout` to end only the calling device's session without revoking sessions on other devices or requiring an active access token. |

---

## 9. Open questions

| Question | Context | Owner |
|---|---|---|
| Rejected accounts UX and status | The spec defines a `rejected` verification status in `verification_requests`, but no `rejected` account status in `profiles`. We assume a rejected user can view reviewer feedback, update profile/KYC details, and resubmit (returning to `pending`). Please confirm. | Product lead / Frontend lead |
| PAN and bank name mismatch policy | The spec states PAN and bank holder name "should match". We currently store `bank_name_match: boolean` and flag mismatches for admin review without hard-blocking submission. Should mismatches block submission automatically? | Risk / Legal team |
| ID document compliance and DPDP | Legal requirements under Indian law strictly restrict collecting Aadhaar numbers. We store only uploaded document images in `kyc-docs` and never store Aadhaar numbers. Confirm required consent disclosures and DPDP data deletion policies with legal counsel. | Legal counsel / CA |
| Video draft upload limit on Supabase Free Plan | Spec allows up to 500 MB video drafts. Supabase free plan caps file uploads at 50 MB. Project must be upgraded to a paid Supabase plan before launching video draft uploads. | Founders / Infrastructure lead |
| Commission and payout split | Spec says 70/30 in release 1. Feature guide says Phase 2. Which is correct and when? | Founders / product lead |
| Auto-approval window: 48 h or 72 h? | Two documents contradict each other. Affects the agreement lifecycle. | Product lead |
| One mobile number for both brand and creator | The spec allows it. OTP login cannot tell which role is intended, so we return a `role_required` 409 and ask for a `role` field. Frontend needs to handle this. Is the spec correct, or should one number be one role? | Frontend lead + product |
| Twilio India DLT registration | Twilio requires DLT (Distributed Ledger Technology) registration to send SMS to Indian numbers commercially. Trial accounts can only send to numbers you have verified in the Twilio console. Who is handling this? | Business / legal team |
| GitHub repository location | The repo needs a permanent home (GitHub org, visibility). | Project lead |
| `mobile_not_verified` UX on login | If a user signs up but never verifies, `/auth/login` returns `403 mobile_not_verified`. The spec doesn't cover this case. Frontend should redirect to the OTP screen. Needs team alignment. | Frontend lead |
| Ending other devices' sessions on password change | The user-scoped call (`PUT /auth/v1/user`) keeps the current device session active. Should other devices' sessions be terminated on password change? Good security practice suggests terminating others while keeping the current device signed in. The spec is silent. | Product / Security lead |

---

## 10. Next steps & Roadmap

All core milestones across the Brand Marketplace specification and Creator Onboarding are now **100% built, deployed, and validated with live end-to-end curl tests**:
- **Milestone 1:** Creator Discovery, Profiles, Filters, Suggestions, and Brand Authentication.
- **Milestone 2 (Section 4):** Cart, Package Bookings, and Custom Deals.
- **Milestone 3 (Section 5):** Job Postings, Bidding, and Bid Awarding.
- **Milestone 4 (Section 6):** Orders, Escrow State Machine, Deliverable Revisions, and In-app Messages.
- **Milestone 5 (Section 7):** Brand Dashboard Home, Checklists, Custom Shortlists, Deliverables Content Library, and Reporting/Analytics.

### Production Readiness Items:
1. **Razorpay Live Gateway Integration:** Switch from test-mode client tokens to live webhook handlers (`order.paid`, `payment.authorized`, `refund.processed`).
2. **Supabase Paid Plan Upgrade:** Required to lift the 50 MB file upload limit to 500 MB for master 4K creator video reels.
3. **Twilio India DLT Registration:** Complete commercial DLT template registration for non-whitelisted Indian phone numbers.
4. **WebSocket / Realtime Subscriptions:** Enable Supabase Realtime on `order_messages` and `campaign_bids` for instant UI updates.

---

## 11. Changelog

| Date | What changed | Why it matters |
|---|---|---|
| 2026-10-27 | **Brand Dashboard, Shortlists, Deliverables & Reporting (Spec Section 7) built, deployed, and tested.** Migration `brand_dashboard` pushed. Created tables `brand_todos`, `shortlists`, `shortlist_creators`, and `deliverables`. Live endpoints: `GET /dashboard/summary` (greeting, todos, real-time escrow/campaign stats, top creators), `PATCH /dashboard/todos/:id` (toggle onboarding tasks), `GET /lists`, `POST /lists` (create shortlist), `GET /lists/:id` (creators in shortlist), `POST /lists/:id/creators` (add creator), `DELETE /lists/:id/creators/:creatorId` (remove creator), `PATCH /lists/:id` (rename shortlist), `POST /lists/:id/duplicate` (duplicate shortlist with copied creators), `DELETE /lists/:id` (204), `GET /deliverables` (content library with filter by q, platform, jobId, date), `GET /deliverables/:id`, `GET /deliverables/export` (CSV download), `GET /reporting` (analytics with views by month, spend by platform, top performers), `GET /reporting/export` (analytics CSV export). All 15 automated test cases passed in `test_dashboard.sh`. | Brand app is now completely supported end-to-end: home dashboard, shortlist management, content approval library, and financial reporting. |
| 2026-10-27 | **Orders & Escrow (Spec Section 6) built, deployed, and tested.** Migration `orders_and_escrow` pushed. Added escrow and deliverable columns to `orders` and created `order_messages` table. Live endpoints: `GET /orders` (brand's orders with creator card profiles), `GET /orders/:id` (order details), `POST /orders` (direct package checkout), `POST /orders/:id/pay` (escrow funding, client token and test payment intent), `POST /orders/:id/submit-draft` (moves to `draft_submitted`), `POST /orders/:id/request-changes` (`changes_requested` with note), `POST /orders/:id/approve` ("Approve & Pay" releasing escrow, timestamps `released_at`), `GET /orders/:id/messages` (order collaboration and audit thread), `POST /orders/:id/messages` (post discussion note or attachment). All 11 automated test cases passed in `test_orders.sh`. | Fulfills the core marketplace value proposition: "Money moves only when you approve." Full escrow lifecycle is now operational for the brand web app. |
| 2026-10-27 | **Campaigns & Bids (Spec Section 5) built, deployed, and tested.** Migration `campaigns_and_bids` pushed. Created tables `campaigns`, `campaign_bids`, and `orders`. Live endpoints: `POST /campaigns` ("Post a Job"), `GET /campaigns` (with bid counts and preview avatars), `GET /campaigns/:id`, `PATCH /campaigns/:id`, `DELETE /campaigns/:id`, `GET /campaigns/:id/bids` (creator proposals), `POST /campaigns/:id/bids/:bidId/select` (picks winner, creates escrow order, awards job, rejects rivals). All 10 automated test cases passed in `test_campaigns.sh`. | Brands can post jobs and receive, review, and award creator bids with one click. |
| 2026-10-27 | **Cart & Custom Offers (Spec Section 4) built, deployed, and tested.** Migration `cart_and_offers` pushed. Created tables `cart_items` and `custom_offers`. Live endpoints: `GET /cart` (joined creator and package items with subtotal), `POST /cart/items` (auto-increments existing items), `PATCH /cart/items/:itemId` (quantity updater), `DELETE /cart/items/:itemId` (204), `POST /offers` (custom collaboration offers). All 8 automated test cases passed in `test_cart_and_offers.sh`. | Enables direct booking and custom deals with creators from their profiles. |
| 2026-10-27 | **Brand Marketplace & Creator Discovery (Milestone 1) built, deployed, and tested.** Migration `brand_marketplace` pushed. Added `company_name` to `profiles`, created tables `creators`, `creator_packages`, `creator_reviews`, and `saved_creators` seeded with rich realistic profiles (Ananya Rao, Rohan Verma, Neha Sharma, etc.). Live endpoints: Brand Signup (`POST /auth/signup` with `{ name, email, password, companyName }` → `{ token, user }`), Brand Login (`POST /auth/login` → `{ token, user }`), `GET /auth/me` (`{ user }`), `POST /auth/logout` (204), `GET /creators` (with search, filter, sort, pagination envelope), `GET /creators/suggestions`, `GET /creators/filters`, `GET /creators/:id` (full profile), `GET /creators/:id/packages`, `GET /creators/:id/reviews`, `GET /creators/:id/similar`, `POST /creators/:id/save` (204), `DELETE /creators/:id/save` (204). All 15 automated test cases passed. | Directly unblocks the React frontend brand marketplace, search & discovery, creator profiles, shortlist, and brand authentication. |
| 2026-10-27 | **Creator onboarding (Pages 17 & 18) built, deployed, and tested.** Migration `creator_onboarding` pushed. Added AES-256-GCM field encryption (`crypto.ts`) and KYC provider abstraction (`kycProvider.ts`). Live endpoints: `POST /uploads/presign` (10 MB, jpeg/png/pdf), `PUT /creator/onboarding/profile`, `GET /creator/social/:platform/connect-url`, `GET /creator/social/:platform/callback` (stub mode with signed state), `POST /creator/kyc/id`, `POST /creator/kyc/pan` (encrypted), `POST /creator/bank` (encrypted), `POST /creator/onboarding/submit` (validates all requirements), `GET /{role}/verification-status`. All 4 Step 4 checks passed. | Creators can now complete their entire onboarding flow, attach documents, connect mock social accounts, register verified KYC/banking credentials, and enter the verification queue. |
| 2026-10-27 | **Dropped `change_user_password` and switched `change-password` to user-scoped update.** Migration `drop_change_password_fn` pushed. Replaced direct hash rewrites with standard GoTrue user endpoint (`PUT /auth/v1/user` with caller's Bearer token). Preserves the caller's active session and refresh token without custom SQL or session destruction. Tests D and E passed. | Eliminates direct writes to `auth` schema while ensuring the caller device stays authenticated after changing their password. |
| 2026-10-27 | **Auth endpoints aligned with exact API specification.** `/auth/forgot-password` (`body { identifier } → { ok: true }`), `/auth/reset-password` (`body { identifier, code, newPassword } → { ok: true }`, invalidates all sessions), `/auth/change-password` (`body { current, next } → { ok: true }`, 422 `fields.current`, keeps session alive), `/auth/logout` (`body { refreshToken } → { ok: true }`, ends only single session, no Bearer header). Migrations `revoke_single_session` and `change_password_fn` pushed. All 6 validation tests passed. | Guarantees seamless compatibility with the existing creator frontend. Prevents unexpected session logouts on password changes and allows expired tokens to log out cleanly. |
| 2026-10-27 | **`POST /auth/login`, `GET /auth/me`, `POST /auth/refresh` deployed and tested.** Login returns tokens directly (no OTP step). Me returns `id, role, status, name, mobile`. Refresh rotates the token. | Frontend can build the login and session refresh flow. |
| 2026-10-27 | **Migration `login_lockout` pushed.** Adds `failed_logins` and `locked_until` to `profiles`. Five wrong attempts lock the account for 15 minutes. | Protects accounts from brute-force attacks per spec. |
| 2026-10-27 | **Bug fixed: `full_name` → `name`.** The profiles table column is `name` (set in foundation migration). `full_name` was a typo in the code and this doc. | `/auth/me` was returning 401 because the profile query silently returned null. |
| 2026-10-27 | **`POST /auth/signup`, `POST /auth/otp/send`, `POST /auth/otp/verify` deployed and tested.** Signup returns `201` with `userId`; verify returns `accessToken`, `refreshToken`, `role`, `status`, `next`. | Frontend can build the signup and OTP screens against real endpoints. |
| 2026-10-27 | **`otpService.ts` added.** Twilio Verify integration with dev-mode bypass for whitelisted test numbers. | No SMS credentials needed to develop and test locally. |
| 2026-10-27 | **Migration `otp_support` pushed.** Adds `mobile_verified_at` to `profiles` and creates `otp_send_log`. | Enables OTP rate limiting (5/hour) and tracks when a number was first verified. |
| 2026-10-27 | **`supabase/functions/api/index.ts` bootstrapped with Hono and `/health` endpoint.** `verify_jwt = false` set in config so unauthenticated routes work. | Established the API pipeline end-to-end. Frontend base URL confirmed working. |
| 2026-10-27 | **Migration `foundation` pushed.** Profiles, settings, audit_log, RLS policies, and signup trigger. 8 security assertions passed. | Core data model and security rules are in place. No user can escalate their own role or read another user's data. |
| 2026-10-27 | **`supabase/tests/foundation_check.sql` added.** | Any teammate can rerun the 8 security assertions after future migrations with `supabase db test`. |
