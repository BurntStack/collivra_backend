# Creator-User Identity Unification Design (Clean Greenfield Schema)

## 1. Context & Objectives

In a fresh production database with no legacy data to preserve, we eliminate all legacy text-based primary keys and dual-write/backfill complexity. 

The architecture establishes a strict **1:1 relationship** between authentication users (`public.profiles`) and marketplace creators (`public.creators`):
- Every real creator account is anchored to their authentication UUID (`profiles.id`).
- Public creator URLs are powered by a decoupled, unique `slug` (`/creators/ananya-rao`).

---

## 2. Target Schema Design

```
   auth.users (Supabase GoTrue)
        | 1:1 (id UUID)
        v
   public.profiles
        | 1:1 (id UUID, role='creator')
        v
   public.creators
     - id: UUID PRIMARY KEY REFERENCES public.profiles(id) ON DELETE CASCADE
     - slug: VARCHAR(100) UNIQUE NOT NULL
     - name, bio, image, gallery, badges, location, city
     - platform, followers, follower_count, rating, review_count, price_from
     - status: VARCHAR(20) DEFAULT 'pending_approval' ('pending_approval', 'active', 'rejected', 'suspended')
     - is_seed: BOOLEAN DEFAULT FALSE
     - created_at, updated_at
```

### Relational Foreign Keys
All dependent tables reference `public.creators(id)` directly via standard UUID foreign keys:

| Table | Column | Type | Target Constraint |
| :--- | :--- | :--- | :--- |
| `campaign_bids` | `creator_id` | `UUID` | `REFERENCES public.creators(id) ON DELETE CASCADE` |
| `orders` | `creator_id` | `UUID` | `REFERENCES public.creators(id) ON DELETE RESTRICT` |
| `cart_items` | `creator_id` | `UUID` | `REFERENCES public.creators(id) ON DELETE CASCADE` |
| `saved_creators` | `creator_id` | `UUID` | `REFERENCES public.creators(id) ON DELETE CASCADE` |
| `shortlist_creators` | `creator_id` | `UUID` | `REFERENCES public.creators(id) ON DELETE CASCADE` |
| `creator_packages` | `creator_id` | `UUID` | `REFERENCES public.creators(id) ON DELETE CASCADE` |
| `creator_reviews` | `creator_id` | `UUID` | `REFERENCES public.creators(id) ON DELETE CASCADE` |
| `deliverables` | `creator_id` | `UUID` | `REFERENCES public.creators(id) ON DELETE SET NULL` |
| `custom_offers` | `creator_id` | `UUID` | `REFERENCES public.creators(id) ON DELETE CASCADE` |

---

## 3. Real Creator Lifecycle

1. **Registration**:
   - Creator signs up and verifies identity -> row in `auth.users` and `public.profiles` (`role = 'creator'`, `status = 'unverified'`).
2. **Catalog Onboarding**:
   - Creator submits portfolio, handle, bio, and package pricing.
   - System validates and creates `public.creators` with `id = request.user.id`, sanitized unique `slug`, and `status = 'pending_approval'`.
3. **Verification & Admin Approval**:
   - Admin reviews creator profile in admin queue and approves (`status = 'active'`).
4. **Marketplace & Bidding Access**:
   - Only `active` creators appear in marketplace searches and can submit bids (`POST /campaigns/<pk>/bids`).
   - If an unlisted user bids, the API returns `403 creator_not_listed`. Fake/invented rows are never created.

---

## 4. Key Decisions for You to Make

### Decision 1: Creator Auth Method (Mobile OTP vs Email & Password)
- **Option A (Mobile OTP via Twilio Verify)**: Natural for creators in India; fast mobile onboarding. Requires Twilio account credentials in production, and OTP costs per sign-in.
- **Option B (Email + Password, identical to Brands)**: Zero third-party SMS dependency, zero per-login cost, instant reliable delivery, works identically to brand signup. Mobile number can still be verified optionally after signup.
- *Recommendation*: **Option B (Email + Password)** for launch. It eliminates external SMS delivery failure points and Twilio cost before product-market fit.

### Decision 2: Slug Customization
- **Option A**: Auto-generated from name / handle (e.g. `ananya-rao`), with auto-increment suffix if taken (`ananya-rao-2`).
- **Option B**: Creator explicitly chooses their vanity handle during onboarding (e.g. `@ananyacreates`), validated for uniqueness.
- *Recommendation*: **Option B** (custom handle chosen by creator, fallback to slugified name).

### Decision 3: Production Seed Data Strategy
- **Option A (Pure Clean Slate)**: `SHOW_SEED_DATA=false` in production. Zero seed rows. Only real registered and approved creators appear.
- **Option B (Curated Launch Seed Creators)**: Include 4–8 curated real-looking creator showcase profiles flagged `is_seed = true`, visible only if `SHOW_SEED_DATA=true` is set.
- *Recommendation*: **Option A** for the clean production Supabase project.

### Decision 4: Admin Verification Gate
- **Strict Verification (Recommended)**: Creators cannot submit bids or be discovered in search until platform admin approves their listing (`status = 'active'`).
- **Immediate Open Access**: Creators are discoverable immediately after onboarding, with an unverified badge.
