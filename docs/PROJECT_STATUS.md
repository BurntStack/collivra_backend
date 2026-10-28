# Collivra — Project Status

> **Maintained by:** Antigravity Backend Agent. Updated automatically after changes to backend services, configs, endpoints, or contracts. Never write secrets or raw keys in this file. Detailed endpoint schemas and payload examples are documented in [API_REFERENCE.md](file:///Users/srikarnagavelli/Srikar/Burntstack/collivra/docs/API_REFERENCE.md).

---

## 1. Architecture Overview

Collivra is an India-focused marketplace where brands discover and hire content creators. A brand posts a campaign or hires directly from creator packages; platform escrow protects funds until deliverables are approved.

The application backend runs as a standalone **Django (Python / Django REST Framework)** service hosted on Render, with **Supabase** serving strictly as the managed PostgreSQL database, Object Storage, and GoTrue authentication provider.

### Text Architecture Diagram

```
+-------------------------------------------------------------------------+
|                    Client Applications (Web & Mobile)                   |
+-------------------------------------------------------------------------+
                                     |
                                     | HTTPS / JSON (Bearer JWT)
                                     v
+-------------------------------------------------------------------------+
|                  Render Web Service (Django 6.1.2 + DRF)                |
|                                                                         |
|  [CorsHeaders] -> [SupabaseAuthentication] -> [Role Permissions & Views]|
|                                                                         |
|  - Auth & Profile Management      - Cart & Custom Offers                |
|  - Creator Discovery & Gating     - Campaign Management & B2 Rules      |
|  - Creator Onboarding & KYC       - Escrow Orders & Review Revisions    |
|  - Brand Shortlists & Todos       - Deliverable Library & Reporting     |
+-------------------------------------------------------------------------+
             |                                              |
      Direct Pooler (PgBouncer: 6543)                Auth API calls
             |                                              |
             v                                              v
+------------------------------------+      +-----------------------------+
|    Supabase PostgreSQL Database    |      |     Supabase GoTrue Auth    |
|       (eetmsobqxlbsvcoscjnb)       |      |   (JWT Issuance & OAuth)    |
|                                    |      +-----------------------------+
|  - 24 Tables (All managed = False) |                      |
|  - RLS Enabled on all tables       |                      v
|  - Direct PostgREST access blocked |      +-----------------------------+
|  - Schema owned by SQL migrations  |      |       Supabase Storage      |
+------------------------------------+      |   (KYC & Deliverables)      |
                                            +-----------------------------+
```

### Core Architecture Components

- **Backend Framework:** Django 6.1.2 + Django REST Framework (`backend/api/`) deployed via Gunicorn on Render (`render.yaml`).
- **Database Engine & Pooler:** PostgreSQL 15 connected through Supabase AWS transaction pooler (`aws-0-ap-south-1.pooler.supabase.com:6543`) with `DISABLE_SERVER_SIDE_CURSORS = True` for PgBouncer transaction mode safety.
- **Database Access Lockdown:** Direct database access for `anon` and `authenticated` roles via PostgREST is revoked (returns 403). All database interactions are routed through Django.
- **Authentication Bridge:** `api.authentication.SupabaseAuthentication` verifies GoTrue JWTs via `SUPABASE_JWT_SECRET` with fallback to Supabase `/auth/v1/user`, mapping claims to `request.user.id` and `request.user.role`.
- **API Base URL:** `http://127.0.0.1:8000/api/v1` (local) / `https://collivra-backend.onrender.com/api/v1` (production).
- **GitHub Repository:** `https://github.com/BurntStack/collivra_backend.git` (branch `main`).

---

## 2. Architecture & Contract Decisions

1. **Schema Ownership belongs to Supabase Migrations**: The database schema is strictly owned and tracked by `supabase/migrations/*.sql`. All Django models in `backend/api/models.py` define `managed = False` in their `Meta` to prevent Django's migration engine from conflicting with database schema definitions.
2. **The Brand Spec Wins for Brand Endpoints**: The latest "API Specification — Creator Marketplace (Brand side)" takes absolute precedence for all brand-facing routes.
3. **"Users" Means Brands**: Across Figma, frontend specs, and marketplace terminology, user-facing client accounts are brands. Creators are hired partners.
4. **Brand Signup is Email-Only**: Brand registration is email + password + company name (`POST /auth/signup`). Creator registration retains mobile + OTP verification.
5. **Responses are Supersets of Both Specs**: Where the Brand Spec and Page-by-Page spec differ (e.g. `token` vs `accessToken`, `user` vs flat fields), endpoints return the superset so both web and mobile frontends function seamlessly without translation layers.
6. **Cross-Brand Resource Isolation**: Brand-owned resources (Campaigns, Orders, Cart, Shortlists, Deliverables) enforce strict tenant isolation using `request.user.id`. Foreign brand queries return `404 Not Found` (never 403 or 200).
7. **Two-Stage Escrow Lifecycle**: Orders start in `awaiting_payment` and transition to `in_escrow` upon payment confirmation. Release of escrow occurs on brand approval (`POST /orders/:id/approve`), which is strictly idempotent.

---

## 3. Endpoint Contract & Permissions Matrix

| Method | Path | Permission Class | User Scoping / Query Filter | Test Suite | Allowed Callers |
|---|---|---|---|---|---|
| `GET` | `/health` | `AllowAny` | Public health status check | Integration | Public |
| `POST` | `/auth/signup` | `AllowAny` | Creates brand or creator profile | `tests/auth.sh`, `tests/creator_auth.sh` | Public |
| `POST` | `/auth/otp/send` | `AllowAny` | OTP generation logged in `otp_send_log` | `tests/creator_auth.sh` | Public |
| `POST` | `/auth/otp/verify` | `AllowAny` | Validates mobile OTP and marks verified | `tests/creator_auth.sh` | Public |
| `POST` | `/auth/login` | `AllowAny` | GoTrue password auth + lockout check | `tests/auth.sh`, `tests/creator_auth.sh` | Public |
| `GET` | `/auth/me` | `AllowAny` | Scoped to `request.user.id` | `tests/auth.sh` | Authenticated |
| `POST` | `/auth/refresh` | `AllowAny` | Refreshes GoTrue session tokens | `tests/auth.sh` | Public |
| `POST` | `/auth/forgot-password` | `AllowAny` | Password reset trigger | `tests/creator_auth.sh` | Public |
| `POST` | `/auth/reset-password` | `AllowAny` | Clears lockout and sets new password | `tests/creator_auth.sh` | Public |
| `POST` | `/auth/change-password` | `AllowAny` | Verifies old password and updates | `tests/creator_auth.sh` | Authenticated |
| `POST` | `/auth/logout` | `AllowAny` | Revokes GoTrue session | `tests/auth.sh`, `tests/creator_auth.sh` | Authenticated |
| `POST` | `/auth/oauth/google` | `AllowAny` | Validates Google ID token | `tests/auth.sh` | Public |
| `POST` | `/auth/oauth/apple` | `AllowAny` | Returns 501 (disabled per spec) | `tests/auth.sh` | Public |
| `POST` | `/uploads/presign` | `AllowAny` | Scoped to authenticated user ID | `tests/onboarding.sh` | Authenticated |
| `PATCH/PUT` | `/creator/onboarding/profile` | `IsCreatorUser` | Scoped to `creator_profiles.id = request.user.id` | `tests/onboarding.sh` | Creator |
| `GET` | `/creator/social/:platform/connect-url` | `IsCreatorUser` | Stub OAuth redirect generator | `tests/onboarding.sh` | Creator |
| `GET` | `/creator/social/:platform/callback` | `AllowAny` | Scoped to state token `user_id` | `tests/onboarding.sh` | Creator / Redirect |
| `POST` | `/creator/kyc/id` | `IsCreatorUser` | Scoped to `creator_kyc.creator_id = request.user.id` | `tests/onboarding.sh` | Creator |
| `POST` | `/creator/kyc/pan` | `IsCreatorUser` | Encrypted at rest, scoped to creator | `tests/onboarding.sh` | Creator |
| `POST` | `/creator/bank` | `IsCreatorUser` | Encrypted at rest, scoped to creator | `tests/onboarding.sh` | Creator |
| `POST` | `/creator/onboarding/submit` | `IsCreatorUser` | Sets `verification_requests.creator_id = request.user.id` | `tests/onboarding.sh` | Creator |
| `GET` | `/creator/verification-status` | `AllowAny` | Scoped to `request.user.id` | `tests/onboarding.sh` | Authenticated |
| `GET` | `/creators` | `AllowAny` | Public search, pagination, active filter | `tests/marketplace.sh` | Public |
| `GET` | `/creators/suggestions` | `AllowAny` | Public search chips | `tests/marketplace.sh` | Public |
| `GET` | `/creators/filters` | `AllowAny` | Dynamic metadata filter options | `tests/marketplace.sh` | Public |
| `GET` | `/creators/:id` | `IsBrandUser` | Public creator record with packages/reviews | `tests/marketplace.sh` | Brand, Admin |
| `GET` | `/creators/:id/packages` | `IsBrandUser` | Scoped to creator packages | `tests/marketplace.sh` | Brand, Admin |
| `GET` | `/creators/:id/reviews` | `IsBrandUser` | Scoped to creator reviews | `tests/marketplace.sh` | Brand, Admin |
| `GET` | `/creators/:id/similar` | `IsBrandUser` | Recommendation query based on niche | `tests/marketplace.sh` | Brand, Admin |
| `POST/DELETE` | `/creators/:id/save` | `IsBrandUser` | Scoped to `saved_creators.brand_id = request.user.id` | `tests/marketplace.sh` | Brand, Admin |
| `GET` | `/cart` | `IsBrandUser` | Scoped to `cart_items.brand_id = request.user.id` | `tests/cart.sh` | Brand |
| `POST` | `/cart/items` | `IsBrandUser` | Scoped to `cart_items.brand_id = request.user.id` | `tests/cart.sh` | Brand |
| `PATCH/DELETE` | `/cart/items/:id` | `IsBrandUser` | Scoped to `brand_id = request.user.id` (404 foreign) | `tests/cart.sh` | Brand |
| `POST` | `/offers` | `IsBrandUser` | Sets `custom_offers.brand_id = request.user.id` | `tests/cart.sh` | Brand |
| `GET` | `/campaigns` | `IsBrandUser` | Scoped to `brand_id = request.user.id, deleted_at is null` | `tests/campaigns.sh` | Brand |
| `POST` | `/campaigns` | `IsBrandUser` | Creates campaign with `brand_id = request.user.id` | `tests/campaigns.sh` | Brand |
| `GET` | `/campaigns/:id` | `IsBrandUser` | Scoped to `brand_id = request.user.id` (404 foreign) | `tests/campaigns.sh` | Brand Owner |
| `PATCH` | `/campaigns/:id` | `IsBrandUser` | B2 rules: owner-only (404), locked fields if bids (409) | `tests/campaigns.sh` | Brand Owner |
| `DELETE` | `/campaigns/:id` | `IsBrandUser` | B2 rules: owner-only (404), 409 if bids exist, 204 soft-delete | `tests/campaigns.sh` | Brand Owner |
| `GET` | `/campaigns/:id/bids` | `AllowAny` | Public/owner view of bids on active campaign | `tests/campaigns.sh` | Brand Owner, Creator |
| `POST` | `/campaigns/:id/bids` | `AllowAny` | Creator submits bid to open campaign | `tests/campaigns.sh` | Creator |
| `POST` | `/campaigns/:id/bids/:bidId/select` | `IsBrandUser` | Owner select: creates order in `in_escrow`, awards campaign | `tests/campaigns.sh` | Brand Owner |
| `GET` | `/orders` | `IsBrandUser` | Scoped to `orders.brand_id = request.user.id` | `tests/orders.sh` | Brand |
| `POST` | `/orders` | `IsBrandUser` | Creates direct order for `brand_id = request.user.id` | `tests/orders.sh` | Brand |
| `GET` | `/orders/:id` | `IsBrandUser` | Scoped to `brand_id = request.user.id` (404 foreign) | `tests/orders.sh` | Brand Owner |
| `POST` | `/orders/:id/pay` | `IsBrandUser` | Escrow payment intent (owner-only, 404 foreign) | `tests/orders.sh` | Brand Owner |
| `POST` | `/orders/:id/confirm-payment-stub` | `IsBrandUser` | Moves `awaiting_payment` -> `in_escrow` (409 if paid) | `tests/orders.sh` | Brand Owner |
| `POST` | `/orders/:id/submit-draft` | `AllowAny` | Admin/Creator submits deliverable draft | `tests/orders.sh` | Admin, Creator |
| `POST` | `/orders/:id/request-changes` | `IsBrandUser` | Scoped to owner (max 2 revisions, 409 on limit) | `tests/orders.sh` | Brand Owner |
| `POST` | `/orders/:id/approve` | `IsBrandUser` | Releases escrow: `orders.status = released` (idempotent) | `tests/orders.sh` | Brand Owner |
| `GET/POST` | `/orders/:id/messages` | `IsBrandUser` | Scoped to order participants | `tests/orders.sh` | Brand, Creator |
| `GET` | `/dashboard/summary` | `IsBrandUser` | Scoped to brand counts and onboarding todos | `tests/dashboard.sh` | Brand |
| `PATCH` | `/dashboard/todos/:id` | `IsBrandUser` | Scoped to `brand_todos.brand_id = request.user.id` | `tests/dashboard.sh` | Brand |
| `GET/POST` | `/lists` | `IsBrandUser` | Scoped to `shortlists.brand_id = request.user.id` | `tests/dashboard.sh` | Brand |
| `GET/PATCH/DELETE` | `/lists/:id` | `IsBrandUser` | Scoped to `brand_id = request.user.id` (404 foreign) | `tests/dashboard.sh` | Brand Owner |
| `POST/DELETE` | `/lists/:id/creators` | `IsBrandUser` | Scoped to `shortlist.brand_id = request.user.id` | `tests/dashboard.sh` | Brand Owner |
| `POST` | `/lists/:id/duplicate` | `IsBrandUser` | Clones list and links for `request.user.id` | `tests/dashboard.sh` | Brand Owner |
| `GET` | `/deliverables` | `IsBrandUser` | Scoped to `deliverables.brand_id = request.user.id` | `tests/dashboard.sh` | Brand |
| `GET` | `/deliverables/export` | `IsBrandUser` | CSV export scoped to `request.user.id` | `tests/dashboard.sh` | Brand |
| `GET` | `/deliverables/:id` | `IsBrandUser` | Scoped to `brand_id = request.user.id` (404 foreign) | `tests/dashboard.sh` | Brand Owner |
| `GET` | `/reporting` | `IsBrandUser` | Scoped to `orders.brand_id = request.user.id` | `tests/dashboard.sh` | Brand |
| `GET` | `/reporting/export` | `IsBrandUser` | CSV export of analytics for `request.user.id` | `tests/dashboard.sh` | Brand |

---

## 4. Known Gaps

1. **Payment Gateway Webhook & Real Settlement**: Escrow payment initiation (`POST /orders/:id/pay`) and stub confirmation (`POST /orders/:id/confirm-payment-stub`) are deterministic test stubs. Real Razorpay/Cashfree webhook handling (`POST /webhooks/payments`) with HMAC signature verification and automatic escrow ledger capture is documented in `docs/DESIGN_PAYMENTS.md` but pending merchant account activation.
2. **Third-Party Social OAuth Token Exchange**: `/creator/social/:platform/connect-url` and `/creator/social/:platform/callback` run in deterministic mock mode. Connecting live YouTube Data API and Instagram Graph API requires production app client credentials.
3. **External KYC Provider API**: KYC ID and PAN validations enforce structural formats (Indian PAN regex: `^[A-Z]{5}[0-9]{4}[A-Z]{1}$`, IFSC: `^[A-Z]{4}0[A-Z0-9]{6}$`). Automated live verification via Karza / Cashfree KYC API is stubbed.
4. **Live SMS OTP Delivery**: Phone verification for dev whitelisted numbers uses deterministic code `123456`. Real SMS gateway integration (Twilio / Msg91) is ready in `api.services.OtpService` pending SMS gateway API keys.
5. **Partial Milestone Releases & Disputes**: The order state machine currently supports direct full release upon brand approval (`awaiting_payment` -> `in_escrow` -> `draft_submitted` -> `released`). Milestone payouts (e.g., 70% upfront / 30% on completion) and dispute arbitration flows remain to be implemented.
6. **Token Lifetime Alignment**: Supabase GoTrue issues JWTs with default 1-hour expiration; Brand Specification suggests 15-minute access tokens.

---

## 5. Migrations & Database Status

All 17 database migrations are tracked in `supabase/migrations/` and applied to Supabase PostgreSQL:

1. `20261027051046_foundation.sql`: Profiles, settings, audit_log, RLS, signup trigger.
2. `20261027053217_otp_support.sql`: OTP send log and `mobile_verified_at`.
3. `20261027055741_login_lockout.sql`: Failed login lockout columns.
4. `20261027061448_revoke_sessions.sql`: `revoke_user_sessions()` function.
5. `20261027063000_revoke_single_session.sql`: `revoke_session_by_refresh_token()` function.
6. `20261027063500_change_password_fn.sql`: Custom password rewrite function.
7. `20261027064500_drop_change_password_fn.sql`: Drops custom password rewrite function.
8. `20261027070153_creator_onboarding.sql`: KYC, encrypted PAN/bank, creator profiles.
9. `20261027082143_brand_marketplace.sql`: Creators, packages, reviews, saved shortlist.
10. `20261027084021_cart_and_offers.sql`: Cart items and custom offers.
11. `20261027085121_campaigns_and_bids.sql`: Campaigns, bids, orders base schema.
12. `20261027085903_orders_and_escrow.sql`: Escrow order state machine and messages.
13. `20261027090646_brand_dashboard.sql`: Shortlists, todos, deliverables, reporting.
14. `20261027093543_security_and_campaign_rules.sql`: `deleted_at` on campaigns, `campaigns_status_check` constraint, `brand_profiles` table, revoked all `anon` access on public schema.
15. `20261027100420_security_lockdown.sql`: Revokes public PostgREST direct access on public tables.
16. `20261027100421_order_integrity_and_fixes.sql`: Constraints, order revisions counter, delivery tracking.
17. `20261027100422_drop_stale_policies.sql`: Cleans up legacy unused RLS policies.

### Django Models (All `managed = False`)

All 24 models in `backend/api/models.py` map directly to tables created by Supabase SQL migrations without Django creating or managing tables:

- `AuditLog` (`audit_log`)
- `BrandProfiles` (`brand_profiles`)
- `BrandTodos` (`brand_todos`)
- `CampaignBids` (`campaign_bids`)
- `Campaigns` (`campaigns`)
- `CartItems` (`cart_items`)
- `CreatorKyc` (`creator_kyc`)
- `CreatorPackages` (`creator_packages`)
- `CreatorProfiles` (`creator_profiles`)
- `CreatorReviews` (`creator_reviews`)
- `Creators` (`creators`)
- `CustomOffers` (`custom_offers`)
- `Deliverables` (`deliverables`)
- `OrderMessages` (`order_messages`)
- `Orders` (`orders`)
- `OtpSendLog` (`otp_send_log`)
- `Profiles` (`profiles`)
- `SavedCreators` (`saved_creators`)
- `Settings` (`settings`)
- `ShortlistCreators` (`shortlist_creators`)
- `Shortlists` (`shortlists`)
- `SocialAccounts` (`social_accounts`)
- `Uploads` (`uploads`)
- `VerificationRequests` (`verification_requests`)

---

## 6. Access Control & Security Verification

- **Row Level Security**: Enabled on all 24 public tables (`rls_enabled = true`).
- **PostgREST Direct Access Blocked**: Direct HTTP requests to Supabase PostgREST tables return `403 Forbidden` (`tests/security.sh` step 4). All application queries are routed through Django.
- **Route Gating**: Creator profile details, packages, reviews, and shortlists return `401 Unauthorized` for anonymous requests and `403 Forbidden` for creator tokens (`tests/marketplace.sh`, `tests/security.sh`).
- **Cross-Brand Tenant Isolation**: All endpoints verify resource ownership against `request.user.id`; any attempt to access another brand's campaigns, orders, cart items, or deliverables returns `404 Not Found` (`tests/security.sh` step 6).
- **Field Encryption**: PAN and bank account numbers are encrypted at rest using AES-256-GCM (`FIELD_ENCRYPTION_KEY`).
