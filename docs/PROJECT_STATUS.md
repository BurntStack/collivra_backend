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

1. **Brand Accounts are Active Immediately**: Brands ("users") sign up (`POST /auth/signup`) and their account is active immediately with status `active`. No administrative verification or approval is required. They can immediately create campaigns, fund escrows, and hire creators.
2. **Creators Require Admin Approval**: Creators sign up with status `unverified`. They complete profile onboarding, KYC document upload, PAN, and bank details, then submit for review (`POST /creator/onboarding/submit`), transitioning to status `pending`. Until an administrator approves their application (`POST /admin/verifications/:id/approve`), creators cannot participate in marketplace activities. Any attempt to bid or access packages returns `403` with `{ code: "creator_not_approved" }`.
3. **Single Admin Database & Backend Enforcement**: Admin privileges are strictly locked to `socials@burntstack.com` at the PostgreSQL trigger level (`tr_enforce_single_admin`) and Django layer (`IsAdminUser`). The trigger rejects any INSERT or UPDATE assigning the admin or super_admin role to any other email address.
4. **Status and Role Protection (No Mass Assignment)**: Roles and statuses are never read from user-editable metadata after an account exists. The `handle_new_user` trigger enforces status on INSERT and only promotes to admin from `raw_app_meta_data`. No endpoint accepts `role` or `status` in request bodies (returns `422 validation_error`). Direct Supabase Auth `updateUser` calls changing `user_metadata` have zero effect on `public.profiles`.
5. **Schema Ownership belongs to Supabase Migrations**: The database schema is strictly owned and tracked by `supabase/migrations/*.sql`. All Django models in `backend/api/models.py` define `managed = False` in their `Meta`.
6. **The Brand Spec Wins for Brand Endpoints**: The latest "API Specification — Creator Marketplace (Brand side)" takes absolute precedence for all brand-facing routes.
7. **"Users" Means Brands**: Across Figma, frontend specs, and marketplace terminology, user-facing client accounts are brands. Creators are hired partners.
8. **Responses are Supersets of Both Specs**: Endpoints return supersets of both the Brand Spec and Page-by-Page spec so both web and mobile frontends function seamlessly without translation layers.
9. **Cross-Brand Resource Isolation**: Brand-owned resources enforce strict tenant isolation using `request.user.id`. Foreign brand queries return `404 Not Found`.
10. **Two-Stage Escrow Lifecycle**: Orders start in `awaiting_payment` and transition to `in_escrow` upon payment confirmation. Release of escrow occurs on brand approval (`POST /orders/:id/approve`), which is strictly idempotent.

---

## 3. Account Lifecycle & Status Matrix

| Role | Status | Allowed Actions | Restricted Actions (Returns 403) |
|---|---|---|---|
| **Brand** | `active` | Full access: browse creators, add to cart, create campaigns, select bids, create orders, fund escrow, approve deliverables, messages | Admin endpoints (`403`), Creator-only endpoints |
| **Brand** | `suspended` / `banned` | None (account blocked on every request with 403) | All endpoints |
| **Creator** | `unverified` | `/auth/me`, `/auth/refresh`, `/auth/logout`, Presign KYC uploads, edit onboarding profile, connect social, verify PAN/bank, submit verification | Marketplace bids (`403 creator_not_approved`), packages, order draft submissions |
| **Creator** | `pending` | `/auth/me`, view verification status, Presign uploads, support | Marketplace bids (`403 creator_not_approved`), packages, order draft submissions |
| **Creator** | `needs_info` | `/auth/me`, view rejection reasons, edit onboarding profile, re-upload KYC/bank, resubmit verification | Marketplace bids (`403 creator_not_approved`), packages, order draft submissions |
| **Creator** | `active` | Full creator access: submit bids (`POST /campaigns/:id/bids`), submit drafts, order messaging, view packages/orders | Brand-only endpoints (campaign creation, order approval) |
| **Creator** | `suspended` / `banned` | None (account blocked on every request with 403) | All endpoints |
| **Admin** | `active` | Full administrative review: list verifications, view masked documents/stats, approve, reject, request info, audit log access | Restricted to `socials@burntstack.com` |

---

## 4. Admin Approval Endpoints

All admin endpoints are strictly restricted to authenticated users with `role in ('admin', 'super_admin')`, `status = 'active'`, and `email = 'socials@burntstack.com'` verified server-side against `public.profiles` on every request.

| Method | Path | Description | Payload / Parameters | Response |
|---|---|---|---|---|
| `GET` | `/admin/verifications` | List pending verification requests | `?status=pending|needs_info&page=1&pageSize=20` | `{ results: [...], total, page, pageSize, totalPages }` |
| `GET` | `/admin/verifications/:id` | View detailed creator application with short-lived signed ID URL and masked PAN/bank | None | Full creator profile, KYC details (ciphertext excluded), social stats with `stats_source` |
| `POST` | `/admin/verifications/:id/approve` | Approves creator, sets profile `active`, links/creates catalog `creators` row, writes `audit_log` (idempotent, atomic) | `{}` | `{ status: "active", verificationStatus: "approved", creatorId }` |
| `POST` | `/admin/verifications/:id/reject` | Rejects application, sets status to `needs_info` so creator can correct and resubmit, writes `audit_log` (atomic) | `{ "reason": "<mandatory_string>" }` | `{ status: "needs_info", reason }` |
| `POST` | `/admin/verifications/:id/request-info` | Requests additional info, sets status to `needs_info`, writes `audit_log` (atomic) | `{ "message": "<mandatory_string>" }` | `{ status: "needs_info", message }` |

---

## 5. Endpoint Contract & Permissions Matrix

| Method | Path | Permission Class | User Scoping / Query Filter | Test Suite | Allowed Callers |
|---|---|---|---|---|---|
| `GET` | `/health` | `AllowAny` | Public health status check | Integration | Public |
| `POST` | `/auth/signup` | `AllowAny` | Brand signup -> active; Creator signup -> unverified | `tests/auth.sh`, `tests/approval.sh` | Public |
| `POST` | `/auth/otp/send` | `AllowAny` | OTP generation logged in `otp_send_log` | `tests/creator_auth.sh` | Public |
| `POST` | `/auth/otp/verify` | `AllowAny` | Validates mobile OTP and marks verified | `tests/creator_auth.sh` | Public |
| `POST` | `/auth/login` | `AllowAny` | GoTrue password auth + lockout check | `tests/auth.sh`, `tests/creator_auth.sh` | Public |
| `GET` | `/auth/me` | `IsAuthenticatedUser` | Scoped to `request.user.id` | `tests/auth.sh`, `tests/approval.sh` | Authenticated |
| `PATCH` | `/auth/me` | `IsAuthenticatedUser` | Updates name/company; rejects role/status (422) | `tests/approval.sh` | Authenticated |
| `POST` | `/auth/refresh` | `AllowAny` | Refreshes GoTrue session tokens | `tests/auth.sh` | Public |
| `POST` | `/auth/forgot-password` | `AllowAny` | Password reset trigger | `tests/creator_auth.sh` | Public |
| `POST` | `/auth/reset-password` | `AllowAny` | Clears lockout and sets new password | `tests/creator_auth.sh` | Public |
| `POST` | `/auth/change-password` | `IsAuthenticatedUser` | Verifies old password and updates | `tests/creator_auth.sh` | Authenticated |
| `POST` | `/auth/logout` | `IsAuthenticatedUser` | Revokes GoTrue session | `tests/auth.sh` | Authenticated |
| `POST` | `/auth/oauth/google` | `AllowAny` | Validates Google ID token | `tests/auth.sh` | Public |
| `POST` | `/auth/oauth/apple` | `AllowAny` | Returns 501 (disabled per spec) | `tests/auth.sh` | Public |
| `POST` | `/uploads/presign` | `IsCreatorOnboarding` | Presigns KYC upload URL | `tests/onboarding.sh`, `tests/approval.sh` | Creator, Admin |
| `PUT` | `/creator/onboarding/profile` | `IsCreatorOnboarding` | Scoped to `request.user.id` | `tests/onboarding.sh`, `tests/approval.sh` | Creator, Admin |
| `GET` | `/creator/social/:platform/connect-url` | `IsCreatorOnboarding` | OAuth state generator | `tests/onboarding.sh` | Creator, Admin |
| `GET` | `/creator/social/:platform/callback` | `AllowAny` | Scoped to state token `user_id` | `tests/onboarding.sh` | Creator / Redirect |
| `POST` | `/creator/kyc/id` | `IsCreatorOnboarding` | Attaches uploaded ID doc | `tests/onboarding.sh` | Creator, Admin |
| `POST` | `/creator/kyc/pan` | `IsCreatorOnboarding` | Encrypted at rest, validates format | `tests/onboarding.sh`, `tests/approval.sh` | Creator, Admin |
| `POST` | `/creator/bank` | `IsCreatorOnboarding` | Encrypted at rest, validates account/UPI | `tests/onboarding.sh`, `tests/approval.sh` | Creator, Admin |
| `POST` | `/creator/onboarding/submit` | `IsCreatorOnboarding` | Submits for review; transitions to `pending` | `tests/onboarding.sh`, `tests/approval.sh` | Creator, Admin |
| `GET` | `/creator/verification-status` | `IsAuthenticatedUser` | Scoped to `request.user.id` | `tests/onboarding.sh` | Authenticated |
| `GET` | `/creators` | `AllowAny` | Public search, filters seed data when hidden | `tests/marketplace.sh` | Public |
| `GET` | `/creators/suggestions` | `AllowAny` | Public search chips | `tests/marketplace.sh` | Public |
| `GET` | `/creators/filters` | `AllowAny` | Dynamic metadata filter options | `tests/marketplace.sh` | Public |
| `GET` | `/creators/:id` | `IsBrandUser` | Creator card; 404 for seed data when hidden | `tests/marketplace.sh` | Brand, Admin |
| `GET` | `/creators/:id/packages` | `IsMarketplaceParticipant` | Creator packages; 403 for unapproved creators | `tests/marketplace.sh`, `tests/approval.sh` | Brand, Active Creator |
| `GET` | `/creators/:id/reviews` | `IsBrandUser` | Creator reviews; 404 for seed data when hidden | `tests/marketplace.sh` | Brand, Admin |
| `GET` | `/creators/:id/similar` | `IsBrandUser` | Similar creators; 404 for seed data when hidden | `tests/marketplace.sh` | Brand, Admin |
| `POST/DELETE` | `/creators/:id/save` | `IsBrandUser` | Scoped to `request.user.id` | `tests/marketplace.sh` | Brand, Admin |
| `GET` | `/cart` | `IsBrandUser` | Scoped to `brand_id = request.user.id` | `tests/cart.sh` | Brand |
| `POST` | `/cart/items` | `IsBrandUser` | Adds item to cart; 404 for seed packages | `tests/cart.sh` | Brand |
| `PATCH/DELETE` | `/cart/items/:id` | `IsBrandUser` | Scoped to `brand_id = request.user.id` | `tests/cart.sh` | Brand |
| `POST` | `/offers` | `IsBrandUser` | Creates custom offer; 404 for seed creator | `tests/cart.sh` | Brand |
| `GET/POST` | `/campaigns` | `IsBrandUser` | Scoped to `brand_id = request.user.id` | `tests/campaigns.sh`, `tests/approval.sh` | Brand |
| `GET/PATCH/DELETE` | `/campaigns/:id` | `IsBrandUser` | B2 rules: owner-only (404), locked if bids (409) | `tests/campaigns.sh` | Brand Owner |
| `GET` | `/campaigns/:id/bids` | `IsBrandUser` | Owner view of submitted bids (404 foreign) | `tests/campaigns.sh` | Brand Owner |
| `POST` | `/campaigns/:id/bids` | `IsActiveCreator` | Creator bid; requires active status, deadline/budget checks | `tests/campaigns.sh`, `tests/approval.sh` | Active Creator |
| `POST` | `/campaigns/:id/bids/:bidId/select` | `IsBrandUser` | Executes `public.select_bid` -> `awaiting_payment` | `tests/campaigns.sh` | Brand Owner |
| `GET/POST` | `/orders` | `IsBrandUser` | Scoped to `brand_id = request.user.id` | `tests/orders.sh` | Brand |
| `GET` | `/orders/:id` | `IsMarketplaceParticipant` | Scoped to order brand or creator (404 foreign) | `tests/orders.sh` | Order Participants |
| `POST` | `/orders/:id/pay` | `IsBrandUser` | Escrow payment intent (owner-only) | `tests/orders.sh` | Brand Owner |
| `POST` | `/orders/:id/confirm-payment-stub` | `IsBrandUser` | Moves `awaiting_payment` -> `in_escrow` | `tests/orders.sh` | Brand Owner |
| `POST` | `/orders/:id/submit-draft` | `IsActiveCreator` | Creator submits deliverable draft | `tests/orders.sh` | Active Creator |
| `POST` | `/orders/:id/request-changes` | `IsBrandUser` | Scoped to owner (max 2 revisions) | `tests/orders.sh` | Brand Owner |
| `POST` | `/orders/:id/approve` | `IsBrandUser` | Releases escrow: `orders.status = released` (idempotent, row locked) | `tests/orders.sh` | Brand Owner |
| `GET/POST` | `/orders/:id/messages` | `IsMarketplaceParticipant` | Order discussion thread | `tests/orders.sh` | Order Participants |
| `GET` | `/dashboard/summary` | `IsBrandUser` | Brand counts & onboarding checklist | `tests/dashboard.sh` | Brand |
| `PATCH` | `/dashboard/todos/:id` | `IsBrandUser` | Scoped to `brand_id = request.user.id` | `tests/dashboard.sh` | Brand |
| `GET/POST` | `/lists` | `IsBrandUser` | Shortlists scoped to brand | `tests/dashboard.sh` | Brand |
| `GET/PATCH/DELETE` | `/lists/:id` | `IsBrandUser` | Scoped to brand owner (404 foreign) | `tests/dashboard.sh` | Brand Owner |
| `POST/DELETE` | `/lists/:id/creators` | `IsBrandUser` | Scoped to brand owner | `tests/dashboard.sh` | Brand Owner |
| `POST` | `/lists/:id/duplicate` | `IsBrandUser` | Clones shortlist for owner | `tests/dashboard.sh` | Brand Owner |
| `GET` | `/deliverables` | `IsBrandUser` | Scoped to brand | `tests/dashboard.sh` | Brand |
| `GET` | `/deliverables/export` | `IsBrandUser` | CSV export scoped to brand | `tests/dashboard.sh` | Brand |
| `GET` | `/deliverables/:id` | `IsBrandUser` | Scoped to brand owner | `tests/dashboard.sh` | Brand Owner |
| `GET` | `/reporting` | `IsBrandUser` | Order analytics scoped to brand | `tests/dashboard.sh` | Brand |
| `GET` | `/reporting/export` | `IsBrandUser` | CSV export of analytics | `tests/dashboard.sh` | Brand |
| `GET` | `/admin/verifications` | `IsAdminUser` | List pending & needs_info requests | `tests/approval.sh` | Admin (`socials@burntstack.com`) |
| `GET` | `/admin/verifications/:id` | `IsAdminUser` | Verification detail with short-lived signed URL | `tests/approval.sh` | Admin (`socials@burntstack.com`) |
| `POST` | `/admin/verifications/:id/approve` | `IsAdminUser` | Approves creator, creates catalog row, writes audit log | `tests/approval.sh` | Admin (`socials@burntstack.com`) |
| `POST` | `/admin/verifications/:id/reject` | `IsAdminUser` | Rejects with reason, sets needs_info, writes audit log | `tests/approval.sh` | Admin (`socials@burntstack.com`) |
| `POST` | `/admin/verifications/:id/request-info` | `IsAdminUser` | Requests info, sets needs_info, writes audit log | `tests/approval.sh` | Admin (`socials@burntstack.com`) |

---

## 6. Known Gaps

1. **Payment Gateway Webhook & Real Settlement**: Escrow payment initiation (`POST /orders/:id/pay`) and stub confirmation (`POST /orders/:id/confirm-payment-stub`) are deterministic test stubs. Real Razorpay/Cashfree webhook handling (`POST /webhooks/payments`) with HMAC signature verification and automatic escrow ledger capture is documented in `docs/DESIGN_PAYMENTS.md` but pending merchant account activation.
2. **Third-Party Social OAuth Token Exchange**: `/creator/social/:platform/connect-url` and `/creator/social/:platform/callback` run in deterministic mock mode. Connecting live YouTube Data API and Instagram Graph API requires production app client credentials.
3. **External KYC Provider API**: KYC ID and PAN validations enforce structural formats (Indian PAN regex: `^[A-Z]{5}[0-9]{4}[A-Z]{1}$`, IFSC: `^[A-Z]{4}0[A-Z0-9]{6}$`). Automated live verification via Karza / Cashfree KYC API is stubbed.
4. **Live SMS OTP Delivery**: Phone verification for dev whitelisted numbers uses deterministic code `123456`. Real SMS gateway integration (Twilio / Msg91) is ready in `api.services.OtpService` pending SMS gateway API keys.
5. **Partial Milestone Releases & Disputes**: The order state machine currently supports direct full release upon brand approval (`awaiting_payment` -> `in_escrow` -> `draft_submitted` -> `released`). Milestone payouts (e.g., 70% upfront / 30% on completion) and dispute arbitration flows remain to be implemented.
6. **Token Lifetime Alignment**: Supabase GoTrue issues JWTs with default 1-hour expiration; Brand Specification suggests 15-minute access tokens.

---

## 7. Migrations & Database Status

All 21 database migrations are tracked in `supabase/migrations/` and applied to Supabase PostgreSQL:

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
18. `20261028102500_seed_creators_and_unique_bids.sql`: `is_seed` column on creators, unique index on campaign bids per creator.
19. `20261028104500_create_collivra_app_role.sql`: Dedicated least-privilege `collivra_app` role without superuser privileges.
20. `20261028114000_enforce_single_admin_email.sql`: PostgreSQL trigger `tr_enforce_single_admin` restricting admin role to `socials@burntstack.com`.
21. `20261028120000_creator_approval_and_brand_active.sql`: Auto-activates brand accounts on signup; sets creators to unverified; protects role/status from mass assignment.


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
