# Collivra API Reference

Complete request and response specifications for the Collivra API (`/api/v1`).

- **Base URL:** `https://eetmsobqxlbsvcoscjnb.supabase.co/functions/v1/api/v1`
- **Format:** JSON over HTTPS
- **Currency:** Integer INR (e.g. `8000` = ₹8,000)
- **Standard Pagination Envelope:**
  ```json
  {
    "results": [ /* items */ ],
    "total": 2480,
    "page": 1,
    "pageSize": 12,
    "totalPages": 207
  }
  ```
- **Standard Error Envelope:**
  ```json
  {
    "error": { "code": "error_code", "message": "Human readable explanation" },
    "message": "Human readable explanation",
    "code": "error_code"
  }
  ```

---

## 1. Authentication & Session

### `POST /auth/signup`
- **Brand Signup:** `{ name, email, password, companyName }` → `201` `{ token, user: { id, name, email, companyName, role: "brand" } }`
- **Creator Signup:** `{ role: "creator", name, mobile, email?, password, acceptTerms: true, termsVersion }` → `201` `{ userId, otpSent: true, resendInSeconds }`

### `POST /auth/login`
- **Brand Login:** `{ email, password }` → `200` `{ token, user: { id, name, email, companyName, role: "brand" } }`
- **Creator Login:** `{ identifier: "+91...", password }` → `200` `{ accessToken, refreshToken, expiresIn, role, status, next }`

### `GET /auth/me`
- **Headers:** `Authorization: Bearer <token>`
- **Response `200`:** `{ user: { id, name, email, companyName, role: "brand" } }`

### `POST /auth/logout`
- **Headers:** `Authorization: Bearer <token>` (optional body `{ refreshToken }`)
- **Response:** `204 No Content`

### `POST /auth/oauth/google`
- **Request Body:** `{ idToken: string, nonce?: string }`
- **Response `200`:** `{ token, refreshToken, expiresIn, user: { id, name, email, companyName, role: "brand" }, status, next }`
- **Errors:** `401 invalid_token`, `403 wrong_role`

### `POST /auth/oauth/apple`
- **Request Body:** `{ idToken: string }`
- **Response:** `501 Not Implemented` unless `OAUTH_APPLE_ENABLED=true`

### `POST /auth/otp/send`
- **Request Body:** `{ mobile: "+91...", purpose: "signup" | "login" }`
- **Response `200`:** `{ resendInSeconds: 30 }`

### `POST /auth/otp/verify`
- **Request Body:** `{ mobile: "+91...", code: "123456", purpose: "signup" | "login", role?: "brand" | "creator" }`
- **Response `200`:** `{ accessToken, refreshToken, expiresIn, role, status, next }`

### `POST /auth/refresh`
- **Request Body:** `{ refreshToken: string }`
- **Response `200`:** `{ accessToken, refreshToken, expiresIn }`

### `POST /auth/forgot-password` & `POST /auth/reset-password`
- **Forgot Password:** `{ identifier }` → `200` `{ ok: true }`
- **Reset Password:** `{ identifier, code, newPassword }` → `200` `{ ok: true }`

### `POST /auth/change-password`
- **Headers:** `Authorization: Bearer <token>`
- **Request Body:** `{ current: string, next: string }` → `200` `{ ok: true }`

---

## 2. Creator Discovery (Brand Side)

### `GET /creators/suggestions`
- **Auth:** Public
- **Response `200`:** Array of suggestion strings:
  ```json
  ["Skincare Creators", "Tech Reviewers Delhi", "Fitness Coaches under ₹10k", "Micro-influencers Mumbai"]
  ```

### `GET /creators/filters`
- **Auth:** Public
- **Response `200`:** Dropdown configuration:
  ```json
  {
    "platforms": ["Instagram", "YouTube", "TikTok", "LinkedIn"],
    "cities": ["Bengaluru", "Mumbai", "Delhi NCR", "Hyderabad"],
    "categories": ["Beauty, Skincare", "Tech & Gadgets", "Fitness & Wellness"],
    "languages": ["English", "Hindi", "Tamil", "Telugu", "Kannada"],
    "priceBuckets": [
      { "label": "Under ₹10k", "min": 0, "max": 10000 },
      { "label": "₹10k - ₹25k", "min": 10000, "max": 25000 },
      { "label": "₹25k - ₹50k", "min": 25000, "max": 50000 },
      { "label": "₹50k+", "min": 50000, "max": 9999999 }
    ]
  }
  ```

### `GET /creators`
- **Auth:** Public
- **Query Parameters:** `q`, `category`, `platform`, `city`, `language`, `minPrice`, `maxPrice`, `sort` (`recommended`, `price_asc`, `price_desc`, `followers_desc`, `rating_desc`), `page`, `pageSize`
- **Response `200`:**
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
        "reviewCount": 38,
        "priceFrom": 8000,
        "image": "https://images.unsplash.com/photo-1534528741775-53994a69daeb?auto=format&fit=crop&w=600&q=80",
        "verified": true,
        "saved": false
      }
    ],
    "total": 3,
    "page": 1,
    "pageSize": 12,
    "totalPages": 1
  }
  ```

### `GET /creators/:id`
- **Auth:** Brand or Admin token required (401 unauth, 403 creator)
- **Response `200`:**
  ```json
  {
    "id": "ananya-rao",
    "name": "Ananya Rao",
    "handle": "@ananyaskincare",
    "category": "Beauty, Skincare",
    "location": "Bengaluru",
    "followers": "48.2k",
    "platform": "Instagram",
    "rating": 4.9,
    "reviewCount": 38,
    "priceFrom": 8000,
    "image": "https://images.unsplash.com/photo-1534528741775-53994a69daeb?auto=format&fit=crop&w=600&q=80",
    "coverImage": "https://images.unsplash.com/photo-1522337360788-8b13dee7a37e?auto=format&fit=crop&w=1200&q=80",
    "bio": "Dermatology-certified content creator focusing on cruelty-free skincare routines.",
    "verified": true,
    "saved": false,
    "turnaroundDays": 4,
    "badges": ["Top Rated", "Fast Delivery"],
    "gallery": ["https://images.unsplash.com/..."]
  }
  ```

### `GET /creators/:id/packages`
- **Auth:** Brand or Admin token required
- **Response `200`:**
  ```json
  [
    {
      "id": "pkg_1",
      "name": "Single Dedicated Reel",
      "price": 8000,
      "turnaroundDays": 3,
      "deliverables": "1 Instagram Reel (30–45 sec)",
      "features": ["Product placement", "Link in bio for 24h", "Usage rights 30 days"]
    }
  ]
  ```

### `GET /creators/:id/reviews`
- **Auth:** Brand or Admin token required
- **Response `200`:**
  ```json
  {
    "rating": 4.9,
    "totalReviews": 38,
    "reviews": [
      {
        "id": "rev_1",
        "brandName": "PureGlow Organics",
        "rating": 5,
        "comment": "Ananya's video drove over 1,200 store visits in 48 hours. Incredible work!",
        "date": "2026-09-15",
        "verifiedHire": true
      }
    ]
  }
  ```

### `GET /creators/:id/similar`
- **Auth:** Brand or Admin token required
- **Response `200`:** Array of creator summary cards matching category/platform.

### `POST /creators/:id/save` & `DELETE /creators/:id/save`
- **Auth:** Brand or Admin token required
- **Response:** `200` `{ "saved": true }` or `{ "saved": false }`

---

## 3. Cart & Custom Offers

### `GET /cart`
- **Auth:** Brand token required
- **Response `200`:**
  ```json
  {
    "items": [
      {
        "id": "cart_item_uuid",
        "creator": {
          "id": "ananya-rao",
          "name": "Ananya Rao",
          "avatar": "https://..."
        },
        "package": {
          "id": "pkg_1",
          "name": "Single Dedicated Reel",
          "price": 8000,
          "deliverables": "1 Instagram Reel (30–45 sec)"
        },
        "quantity": 1,
        "lineTotal": 8000
      }
    ],
    "subtotal": 8000
  }
  ```

### `POST /cart/items`
- **Auth:** Brand token required
- **Request Body:** `{ "creatorId": "ananya-rao", "packageId": "pkg_1", "quantity": 1 }`
- **Response `200`:** Returns updated cart object.

### `PATCH /cart/items/:itemId`
- **Auth:** Brand token required
- **Request Body:** `{ "quantity": 2 }`
- **Response `200`:** Returns updated cart object. If `quantity <= 0`, item is deleted.

### `DELETE /cart/items/:itemId`
- **Auth:** Brand token required
- **Response `200`:** Returns updated cart object.

### `POST /offers`
- **Auth:** Brand token required
- **Request Body:**
  ```json
  {
    "creatorId": "ananya-rao",
    "deliverable": "2 Dedicated Reels + 1 IG Live Session for Diwali Launch",
    "budget": 25000,
    "message": "We love your skincare content and would like an exclusive festive partnership.",
    "deadline": "2026-11-15"
  }
  ```
- **Response `201`:** Created custom offer object.

---

## 4. Campaigns & Bids

### `POST /campaigns`
- **Auth:** Brand token required
- **Request Body:**
  ```json
  {
    "title": "Winter Hydration Skincare Launch",
    "platform": "Instagram",
    "deliverables": "1 Reel (30–45 sec) + 2 Stories with link sticker",
    "budgetMin": 10000,
    "budgetMax": 25000,
    "applyBy": "2026-11-20",
    "brief": "Looking for beauty creators to highlight our new ceramide moisturizer in a clean morning skincare routine.",
    "status": "open_for_bids"
  }
  ```
- **Validation:** `budgetMax > budgetMin`, `budgetMin >= 0`, `status` optional (`draft` or `open_for_bids`).
- **Response `201`:** Campaign object.

### `GET /campaigns`
- **Auth:** Brand token required
- **Response `200`:** Array of brand's active campaigns with `bidCount` and `proposalAvatars`. Soft-deleted campaigns (`deleted_at is not null`) are excluded.

### `GET /campaigns/:id`
- **Auth:** Brand token required
- **Response `200`:** Full campaign details. Returns `404` if not found or soft-deleted.

### `PATCH /campaigns/:id`
- **Auth:** Brand owner only (404 for others)
- **Status Constraints:** `closed`, `awarded`, and `cancelled` return `409 Conflict`.
- **Field Whitelist:** Only `title`, `platform`, `deliverables`, `budgetMin`, `budgetMax`, `applyBy`, `brief` allowed. Unknown fields return `422`.
- **Locked Fields When Bids Exist:** If bids > 0, modifying `budgetMin`, `budgetMax`, `deliverables`, or `applyBy` returns `409 Conflict`.
- **Validation:** `budgetMin < budgetMax`, `applyBy` cannot be in the past (returns `422`).
- **Response `200`:** Updated campaign object.

### `DELETE /campaigns/:id`
- **Auth:** Brand owner only (404 for others)
- **Delete Rules:** Only drafts, or campaigns with 0 bids and 0 orders can be deleted (otherwise `409 Conflict`). Soft-deletes with `deleted_at = now()`.
- **Response:** `204 No Content`.

### `GET /campaigns/:id/bids`
- **Auth:** Brand token required
- **Response `200`:**
  ```json
  [
    {
      "id": "bid_uuid",
      "creator": {
        "id": "ananya-rao",
        "name": "Ananya Rao",
        "note": "Excited to partner on this launch!",
        "avatar": "https://..."
      },
      "price": 18000,
      "status": "submitted"
    }
  ]
  ```

### `POST /campaigns/:id/bids`
- **Auth:** Creator / Public
- **Request Body:** `{ "creatorId": "ananya-rao", "price": 18000, "note": "..." }`
- **Response `201`:** Submitted bid object.

### `POST /campaigns/:id/bids/:bidId/select`
- **Auth:** Brand owner only
- **Action:** Selects winning bid, creates an order in `in_escrow`, sets campaign status to `awarded`, and marks other bids `rejected`.
- **Response `201`:** Created order object.

---

## 5. Orders & Escrow

### `GET /orders`
- **Auth:** Brand token required
- **Response `200`:** List of brand orders:
  ```json
  [
    {
      "id": "order_uuid",
      "creator": {
        "id": "ananya-rao",
        "name": "Ananya Rao",
        "avatar": "https://..."
      },
      "deliverable": "1 Instagram Reel (30–45 sec)",
      "amount": 8000,
      "status": "in_escrow",
      "createdAt": "2026-10-27T10:00:00Z"
    }
  ]
  ```

### `GET /orders/:id`
- **Auth:** Brand token required
- **Response `200`:** Full order details with escrow status and deliverable metadata.

### `POST /orders`
- **Auth:** Brand token required
- **Request Body:** `{ "creatorId": "ananya-rao", "packageId": "pkg_1", "deliverable": "...", "amount": 8000 }`
- **Response `201`:** Created order object.

### `POST /orders/:id/pay`
- **Auth:** Brand owner only
- **Action:** Funds escrow. Test mode returns client token and payment intent stub (`pi_test_<orderId>`).
- **Response `200`:** `{ "clientToken": "ct_test_...", "paymentIntentId": "pi_test_...", "status": "in_escrow" }`

### `POST /orders/:id/submit-draft`
- **Auth:** Creator / Brand
- **Request Body:** `{ "draftUrl": "https://...", "notes"?: string }`
- **Response `200`:** Order updated to `draft_submitted`.

### `POST /orders/:id/request-changes`
- **Auth:** Brand owner only
- **Request Body:** `{ "notes": "Please adjust background music volume" }`
- **Response `200`:** Order updated to `changes_requested`.

### `POST /orders/:id/approve`
- **Auth:** Brand owner only
- **Action:** "Approve & Pay" releases escrow funds to creator. Updates status to `released` and sets `released_at = now()`. Idempotent on second call.
- **Response `200`:** Order object with status `released`.

### `GET /orders/:id/messages` & `POST /orders/:id/messages`
- **Auth:** Brand owner or creator
- **GET Response `200`:** Array of messages/comments in order audit thread.
- **POST Request Body:** `{ "body": "Looking great!", "attachments"?: [...] }` → `201`.

---

## 6. Brand Dashboard & Content Library

### `GET /dashboard/summary`
- **Auth:** Brand token required
- **Response `200`:**
  ```json
  {
    "greetingName": "Acme Marketing",
    "todos": [
      { "id": "complete-profile", "title": "Complete brand profile", "done": true },
      { "id": "hire-creator", "title": "Hire your first creator", "done": false }
    ],
    "stats": [
      { "label": "Total Creators Hired", "value": "4", "sub": "+1 this week" },
      { "label": "Funds in Escrow", "value": "₹32,000", "sub": "Protected until approval" },
      { "label": "Active Jobs", "value": "2", "sub": "Receiving creator bids" }
    ],
    "topCreators": [ /* creator cards */ ]
  }
  ```

### `PATCH /dashboard/todos/:id`
- **Auth:** Brand token required
- **Request Body:** `{ "done": true }`
- **Response `200`:** Updated todo object.

### Custom Shortlists (`/lists`)
- `GET /lists`: List user's custom shortlists.
- `POST /lists`: `{ "name": "Diwali Campaign" }` → `201`.
- `GET /lists/:id`: Full details with creator cards.
- `POST /lists/:id/creators`: `{ "creatorId": "ananya-rao" }` → `200`.
- `DELETE /lists/:id/creators/:creatorId`: `200`.
- `PATCH /lists/:id`: `{ "name": "New Name" }` → `200`.
- `POST /lists/:id/duplicate`: `201`.
- `DELETE /lists/:id`: `204 No Content`.

### Deliverables Content Library (`/deliverables`)
- `GET /deliverables`: Search & filter deliverables (`?q=&platform=&jobId=`).
- `GET /deliverables/:id`: Asset download links and deliverable metadata.
- `GET /deliverables/export`: Downloads full deliverables log as CSV.

### Analytics & Reporting (`/reporting`)
- `GET /reporting`: Monthly spend, platform breakdown, top creators.
- `GET /reporting/export`: Export monthly reporting data as CSV.

---

## 7. Creator Onboarding & KYC

### `POST /uploads/presign`
- **Auth:** Creator token required
- **Request Body:** `{ "purpose": "kyc-id" | "kyc-pan", "fileName": "id.pdf", "contentType": "application/pdf", "size": 500000 }`
- **Validation:** 10 MB limit (`413`), extension whitelist (`415` on forbidden extensions).
- **Response `200`:** `{ "uploadUrl": "...", "fileKey": "..." }`

### `PUT /creator/onboarding/profile`
- **Auth:** Creator token required
- **Request Body:** `{ "category": "Tech & Gadgets", "languages": ["English", "Hindi"], "city": "Bengaluru", "topics": ["AI", "Code"] }`
- **Response `200`:** Updated profile.

### `GET /creator/social/:platform/connect-url` & Callback
- **Auth:** Creator token required
- Connect URL generates HMAC-SHA256 signed state. Callback handles mock authentication and writes metrics with `stats_source: 'stub'`.

### `POST /creator/kyc/id`
- **Auth:** Creator token required
- **Request Body:** `{ "docType": "passport" | "driving_license" | "voter_id", "fileKey": "..." }`
- **Response `200`:** `{ "ok": true }`

### `POST /creator/kyc/pan`
- **Auth:** Creator token required
- **Request Body:** `{ "pan": "ABCDE1234F", "nameOnPan": "..." }`
- **Security:** PAN is AES-256-GCM encrypted in the database.
- **Response `200`:** `{ "ok": true }`

### `POST /creator/bank`
- **Auth:** Creator token required
- **Request Body:** `{ "accountNumber": "...", "ifsc": "HDFC0001234", "holderName": "..." }`
- **Security:** Account number is AES-256-GCM encrypted.
- **Response `200`:** `{ "ok": true }`

### `POST /creator/onboarding/submit`
- **Auth:** Creator token required
- **Action:** Validates profile, social metrics, KYC documents, and bank details; creates verification request in `pending` status.
- **Response `200`:** `{ "ok": true, "status": "pending_verification" }`

### `GET /{role}/verification-status`
- **Auth:** Creator or Brand token
- **Response `200`:** `{ "status": "pending_verification" | "verified" | "rejected", "rejectionReason"?: string }`
