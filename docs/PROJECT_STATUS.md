# Collivra — Project Status

> **Maintained by:** Antigravity Backend Agent. Updated automatically after every change to migrations, edge functions, configs, endpoints, or contracts. Never write secrets or raw keys in this file. Detailed endpoint schemas and payload examples are documented in [API_REFERENCE.md](file:///Users/srikarnagavelli/Srikar/Burntstack/collivra/docs/API_REFERENCE.md).

---

## 1. What This Is

Collivra is an India-focused marketplace where brands discover and hire content creators. A brand posts a campaign or hires directly from creator packages; platform escrow protects funds until deliverables are approved.

The entire backend runs on **Supabase** (Postgres + Storage + GoTrue Auth) with a single TypeScript Edge Function (`api`) served under `/api/v1` using **Hono**.

- **Remote API URL:** `https://eetmsobqxlbsvcoscjnb.supabase.co/functions/v1/api/v1`
- **Linked Project Ref:** `eetmsobqxlbsvcoscjnb`

---

## 2. Contract Decisions

1. **The Brand Spec Wins for Brand Endpoints**: The latest "API Specification — Creator Marketplace (Brand side)" takes absolute precedence for all brand-facing routes.
2. **"Users" Means Brands**: Across Figma, frontend specs, and marketplace terminology, user-facing client accounts are brands. Creators are hired partners.
3. **Brand Signup is Email-Only**: Brand registration is email + password + company name (`POST /auth/signup`). Creator registration retains mobile + OTP.
4. **Responses are Supersets of Both Specs**: Where the Brand Spec and Page-by-Page spec differ (e.g. `token` vs `accessToken`, `user` vs flat fields), endpoints return the superset so both web and mobile frontends function seamlessly without translation layers.

---

## 3. Brand Side Contract Matrix (Spec Sections 1–7)

| Method | Path | Implemented | Tested | Deviations from Spec | Allowed Callers |
|---|---|---|---|---|---|
| `POST` | `/auth/signup` | Yes | Yes (`tests/auth.sh`) | None (supports brand `{ name, email, password, companyName }` & creator OTP) | Public |
| `POST` | `/auth/login` | Yes | Yes (`tests/auth.sh`) | Returns superset `{ token, user, accessToken, refreshToken }` | Public |
| `POST` | `/auth/logout` | Yes | Yes (`tests/auth.sh`) | Returns `204 No Content` | Authenticated |
| `GET` | `/auth/me` | Yes | Yes (`tests/auth.sh`) | None (returns `{ user: { id, name, email, companyName, role: "brand" } }`) | Authenticated |
| `POST` | `/auth/oauth/google` | Yes | Yes (`tests/auth.sh`) | None (uses `signInWithIdToken`, verifies brand role) | Public |
| `POST` | `/auth/oauth/apple` | Yes | Yes (`tests/auth.sh`) | Returns 501 unless `OAUTH_APPLE_ENABLED=true` | Public |
| `GET` | `/creators` | Yes | Yes (`tests/marketplace.sh`) | None (pagination envelope `{ results, total, page, pageSize, totalPages }`) | Public |
| `GET` | `/creators/suggestions` | Yes | Yes (`tests/marketplace.sh`) | None (returns suggestion chip array) | Public |
| `GET` | `/creators/filters` | Yes | Yes (`tests/marketplace.sh`) | None (returns platform, city, category, language, priceBuckets) | Public |
| `GET` | `/creators/:id` | Yes | Yes (`tests/marketplace.sh`) | None (B1 route-gated: 401 unauth, 403 creator) | Brand, Admin |
| `GET` | `/creators/:id/packages` | Yes | Yes (`tests/marketplace.sh`) | None (B1 route-gated: 401 unauth, 403 creator) | Brand, Admin |
| `GET` | `/creators/:id/reviews` | Yes | Yes (`tests/marketplace.sh`) | None (B1 route-gated: 401 unauth, 403 creator) | Brand, Admin |
| `GET` | `/creators/:id/similar` | Yes | Yes (`tests/marketplace.sh`) | None (B1 route-gated: 401 unauth, 403 creator) | Brand, Admin |
| `POST` | `/creators/:id/save` | Yes | Yes (`tests/marketplace.sh`) | B1 route-gated; returns `{ saved: true }` | Brand, Admin |
| `DELETE` | `/creators/:id/save` | Yes | Yes (`tests/marketplace.sh`) | B1 route-gated; returns `{ saved: false }` | Brand, Admin |
| `GET` | `/cart` | Yes | Yes (`tests/cart.sh`) | None (returns items with joined packages and subtotal) | Brand |
| `POST` | `/cart/items` | Yes | Yes (`tests/cart.sh`) | Server overrides price from package; auto-increments quantity | Brand |
| `PATCH` | `/cart/items/:itemId` | Yes | Yes (`tests/cart.sh`) | Deletes line item if quantity <= 0 | Brand |
| `DELETE` | `/cart/items/:itemId` | Yes | Yes (`tests/cart.sh`) | Returns updated cart | Brand |
| `POST` | `/offers` | Yes | Yes (`tests/cart.sh`) | None (creates custom collaboration offer in INR) | Brand |
| `POST` | `/campaigns` | Yes | Yes (`tests/campaigns.sh`) | Supports `status: "draft"` or default `"open_for_bids"`, strict budget check | Brand |
| `GET` | `/campaigns` | Yes | Yes (`tests/campaigns.sh`) | Excludes soft-deleted campaigns (`deleted_at is null`) | Brand |
| `GET` | `/campaigns/:id` | Yes | Yes (`tests/campaigns.sh`) | Returns 404 if campaign is soft-deleted | Brand |
| `PATCH` | `/campaigns/:id` | Yes | Yes (`tests/campaigns.sh`) | B2 rules: owner-only (404), locked fields if bids exist (409), whitelist (422) | Brand Owner |
| `DELETE` | `/campaigns/:id` | Yes | Yes (`tests/campaigns.sh`) | B2 rules: owner-only, 409 if bids/orders exist, 204 soft delete (`deleted_at`) | Brand Owner |
| `GET` | `/campaigns/:id/bids` | Yes | Yes (`tests/campaigns.sh`) | Excludes soft-deleted campaigns | Brand |
| `POST` | `/campaigns/:id/bids/:bidId/select` | Yes | Yes (`tests/campaigns.sh`) | Awards campaign, creates order directly in `in_escrow` | Brand Owner |
| `GET` | `/orders` | Yes | Yes (`tests/orders.sh`) | None (returns brand's orders with creator summary) | Brand |
| `GET` | `/orders/:id` | Yes | Yes (`tests/orders.sh`) | None (returns order status, deliverable details, creator card) | Brand |
| `POST` | `/orders` | Yes | Yes (`tests/orders.sh`) | Creates direct hire order in `in_escrow` | Brand |
| `POST` | `/orders/:id/pay` | Yes | Yes (`tests/orders.sh`) | Test mode stub returns deterministic clientToken & paymentIntentId | Brand Owner |
| `POST` | `/orders/:id/approve` | Yes | Yes (`tests/orders.sh`) | Releases escrow to creator; updates `orders.status` to `released`; idempotent | Brand Owner |
| `POST` | `/orders/:id/request-changes` | Yes | Yes (`tests/orders.sh`) | Updates order status to `changes_requested` with brand review note | Brand Owner |
| `GET` | `/dashboard/summary` | Yes | Yes (`tests/dashboard.sh`) | Aggregates real DB counts with fallback realism chips | Brand |
| `PATCH` | `/dashboard/todos/:id` | Yes | Yes (`tests/dashboard.sh`) | Toggles brand onboarding task completion state | Brand |
| `GET` | `/lists` | Yes | Yes (`tests/dashboard.sh`) | Returns user's custom creator shortlists | Brand |
| `POST` | `/lists` | Yes | Yes (`tests/dashboard.sh`) | Creates new shortlist | Brand |
| `GET` | `/lists/:id` | Yes | Yes (`tests/dashboard.sh`) | Returns shortlist creators | Brand |
| `POST` | `/lists/:id/creators` | Yes | Yes (`tests/dashboard.sh`) | Adds creator to shortlist | Brand |
| `DELETE` | `/lists/:id/creators/:creatorId` | Yes | Yes (`tests/dashboard.sh`) | Removes creator from shortlist | Brand |
| `PATCH` | `/lists/:id` | Yes | Yes (`tests/dashboard.sh`) | Renames shortlist | Brand |
| `POST` | `/lists/:id/duplicate` | Yes | Yes (`tests/dashboard.sh`) | Clones shortlist and associated creator links | Brand |
| `DELETE` | `/lists/:id` | Yes | Yes (`tests/dashboard.sh`) | Soft/hard deletes shortlist | Brand |
| `GET` | `/deliverables` | Yes | Yes (`tests/dashboard.sh`) | Content library search and filter (`q`, `jobId`, `platform`, `date`) | Brand |
| `GET` | `/deliverables/:id` | Yes | Yes (`tests/dashboard.sh`) | Detailed asset view | Brand |
| `GET` | `/deliverables/export` | Yes | Yes (`tests/dashboard.sh`) | Returns CSV export of deliverables | Brand |
| `GET` | `/reporting` | Yes | Yes (`tests/dashboard.sh`) | Aggregated monthly views, platform spend, top creator stats | Brand |
| `GET` | `/reporting/export` | Yes | Yes (`tests/dashboard.sh`) | Returns CSV export of monthly analytics report | Brand |

---

## 4. Known Gaps

1. **Payment Provider (Stub vs Real)**: Payment gateway integration (`POST /orders/:id/pay`) is currently a deterministic stub returning simulated `pi_test_<id>` and `ct_test_<id>`. No live Razorpay/Stripe keys or real INR capture are configured.
2. **Simulated State Transitions**:
   - `POST /campaigns/:id/bids/:bidId/select` directly transitions order to `in_escrow` prior to verified payment webhook confirmation.
   - Creator social metrics in `GET /creator/social/:platform/callback` are mocked stubs (`stats_source: 'stub'`).
3. **Missing Financial Lifecycles**:
   - Cancel order (`POST /orders/:id/cancel`)
   - Refund order (`POST /orders/:id/refund`)
   - Dispute order (`POST /orders/:id/dispute`)
   - Payment provider webhook handler (`POST /webhooks/payments`) with signature verification and idempotency keys.
4. **Missing Creator-Side Lifecycle Endpoints**:
   - Creator package management (`POST /creator/packages`, `PATCH /creator/packages/:id`)
   - Creator bid acceptance/decline (`POST /creator/offers/:id/accept`, `POST /creator/offers/:id/decline`)
   - Creator draft submission endpoint (`POST /orders/:id/submit-draft` is stubbed in Brand API but lacks creator-authenticated contract).
5. **Stub / Seed Data in Production Database**:
   - Seeded creators (`ananya-rao`, `rohan-verma`, `neha-sharma`) use Unsplash demo assets and hardcoded reviews.
   - Reporting numbers in `/reporting` return deterministic sample figures when DB order history is empty.
6. **DEV_MODE Enabled**: `DEV_MODE=true` in Edge Function environment allows bypass OTP `000000` for whitelisted test numbers. Must be disabled before public release.
7. **Repository Not on GitHub**: Repository currently resides exclusively on local development machine; lacks remote GitHub remote tracking and CI/CD pipelines.
8. **Token Lifetime Divergence**: Supabase GoTrue default JWT expiration is 1 hour (3600s), whereas Brand Specification requests 15 minutes (900s).
9. **Unconfirmed Spec Decisions**:
   - Single release upon approval vs 70/30 milestone payout.
   - Auto-approval window on submitted deliverables (48 hours vs 72 hours).
   - One mobile number holding both `brand` and `creator` roles (creates 409 role disambiguation prompt on login).

---

## 5. Migrations & Database Status

All 14 migrations are applied to both local and remote Supabase Postgres environments (`eetmsobqxlbsvcoscjnb`).

### Applied Migrations
1. `20261027051046_foundation.sql`: Profiles, settings, audit_log, RLS, signup trigger.
2. `20261027053217_otp_support.sql`: OTP send log and `mobile_verified_at`.
3. `20261027055741_login_lockout.sql`: Failed login lockout columns.
4. `20261027061448_revoke_sessions.sql`: `revoke_user_sessions()` function.
5. `20261027063000_revoke_single_session.sql`: `revoke_session_by_refresh_token()` function.
6. `20261027064500_drop_change_password_fn.sql`: Drops custom password rewrite function.
7. `20261027070119_creator_onboarding.sql`: KYC, encrypted PAN/bank, creator profiles.
8. `20261027081708_brand_marketplace.sql`: Creators, packages, reviews, saved shortlist.
9. `20261027083656_cart_and_offers.sql`: Cart items and custom offers.
10. `20261027085121_campaigns_and_bids.sql`: Campaigns, bids, orders base schema.
11. `20261027085903_orders_and_escrow.sql`: Escrow order state machine and messages.
12. `20261027090646_brand_dashboard.sql`: Shortlists, todos, deliverables, reporting.
13. `20261027091942_fix_cart_constraint.sql`: Unique package cart constraint.
14. `20261027093543_security_and_campaign_rules.sql`: `deleted_at` on campaigns, `campaigns_status_check` constraint, `brand_profiles` table, revoked all `anon` access on public schema.

### Unapplied Migrations
**None.** (0 unapplied migrations).

---

## 6. Access Control & Security

- **Row Level Security**: Enabled on all 23 public tables (`rls_enabled = true`).
- **Anon Access**: Explicitly revoked from all public tables, functions, and sequences per B4. Public endpoints execute under Edge Function service-role client.
- **Route Gating**: Creator profile details, packages, reviews, and shortlists strictly require brand or admin tokens (B1).
- **Campaign Ownership**: Edit and delete operations strictly restricted to campaign owners; locked fields enforced when bids exist (B2).
- **Field Encryption**: PAN and bank account numbers are encrypted at rest using AES-256-GCM (`FIELD_ENCRYPTION_KEY`).
