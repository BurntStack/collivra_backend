#!/usr/bin/env bash
set -e

BASE_URL="${COLLIVRA_BASE_URL:-http://127.0.0.1:8000/api/v1}"
BASE_HOST=$(echo "$BASE_URL" | sed 's|/api/v1||')
TEST_PASSWORD="${COLLIVRA_TEST_PASSWORD:-TestPass123!}"

echo "=== Collivra Public Security, CORS & Bids Test Suite ==="
echo "Target Base URL: $BASE_URL"
echo ""

# ---------------------------------------------------------
# 1. CORS Verification
# ---------------------------------------------------------
echo "=== 1. CORS Preflight Tests ==="
ALLOWED_ORIGIN="https://app.collivra.com"
DISALLOWED_ORIGIN="https://evil.example"

echo "Test 1.1: Preflight from allowed origin ($ALLOWED_ORIGIN)"
RES_ALLOWED=$(curl -s -D - -o /dev/null -X OPTIONS "$BASE_URL/creators" \
  -H "Origin: $ALLOWED_ORIGIN" \
  -H "Access-Control-Request-Method: GET")

ORIGIN_HEADER=$(echo "$RES_ALLOWED" | grep -i 'access-control-allow-origin' || true)
CREDS_HEADER=$(echo "$RES_ALLOWED" | grep -i 'access-control-allow-credentials' || true)

if [ -z "$ORIGIN_HEADER" ]; then
  echo "FAIL: Expected Access-Control-Allow-Origin header for $ALLOWED_ORIGIN, got none"
  exit 1
fi
echo "Allowed origin correctly echoed: $ORIGIN_HEADER"

if [ -n "$CREDS_HEADER" ]; then
  echo "FAIL: Access-Control-Allow-Credentials must not be present or true when CORS_ALLOW_CREDENTIALS=False"
  exit 1
fi
echo "CORS_ALLOW_CREDENTIALS=False correctly verified (no allow-credentials header)"

echo ""
echo "Test 1.2: Preflight from unauthorized origin ($DISALLOWED_ORIGIN)"
RES_DISALLOWED=$(curl -s -D - -o /dev/null -X OPTIONS "$BASE_URL/creators" \
  -H "Origin: $DISALLOWED_ORIGIN" \
  -H "Access-Control-Request-Method: GET")

DISALLOWED_ORIGIN_HEADER=$(echo "$RES_DISALLOWED" | grep -i 'access-control-allow-origin' || true)
if [ -n "$DISALLOWED_ORIGIN_HEADER" ]; then
  echo "FAIL: Unauthorized origin $DISALLOWED_ORIGIN should NOT receive allow-origin header, got: $DISALLOWED_ORIGIN_HEADER"
  exit 1
fi
echo "Unauthorized origin correctly denied (no Access-Control-Allow-Origin header returned)"

# ---------------------------------------------------------
# 2. Django Admin Removal & JSON 404 / 500
# ---------------------------------------------------------
echo ""
echo "=== 2. Django Admin & JSON Error Response Tests ==="

echo "Test 2.1: GET /admin/ must return 404 JSON, never HTML"
ADMIN_RES=$(curl -s -w "\nHTTP_STATUS:%{http_code}\nCONTENT_TYPE:%{content_type}" -X GET "$BASE_HOST/admin/")
ADMIN_STATUS=$(echo "$ADMIN_RES" | grep 'HTTP_STATUS:' | cut -d: -f2)
ADMIN_CT=$(echo "$ADMIN_RES" | grep 'CONTENT_TYPE:' | cut -d: -f2)
ADMIN_BODY=$(echo "$ADMIN_RES" | grep -v 'HTTP_STATUS:' | grep -v 'CONTENT_TYPE:')

if [ "$ADMIN_STATUS" != "404" ]; then
  echo "FAIL: Expected 404 for /admin/, got $ADMIN_STATUS"
  exit 1
fi
if [[ "$ADMIN_CT" != *"application/json"* ]]; then
  echo "FAIL: Expected application/json content type for /admin/, got $ADMIN_CT"
  exit 1
fi
ADMIN_CODE=$(echo "$ADMIN_BODY" | jq -r '.code // empty')
if [ "$ADMIN_CODE" != "not_found" ]; then
  echo "FAIL: Expected code 'not_found' in JSON body, got: $ADMIN_BODY"
  exit 1
fi
echo "/admin/ route correctly returns HTTP 404 application/json (code: $ADMIN_CODE)"

echo ""
echo "Test 2.2: GET /does-not-exist must return 404 JSON, never HTML"
DNE_RES=$(curl -s -w "\nHTTP_STATUS:%{http_code}\nCONTENT_TYPE:%{content_type}" -X GET "$BASE_HOST/does-not-exist")
DNE_STATUS=$(echo "$DNE_RES" | grep 'HTTP_STATUS:' | cut -d: -f2)
DNE_CT=$(echo "$DNE_RES" | grep 'CONTENT_TYPE:' | cut -d: -f2)
DNE_BODY=$(echo "$DNE_RES" | grep -v 'HTTP_STATUS:' | grep -v 'CONTENT_TYPE:')

if [ "$DNE_STATUS" != "404" ]; then
  echo "FAIL: Expected 404 for /does-not-exist, got $DNE_STATUS"
  exit 1
fi
if [[ "$DNE_CT" != *"application/json"* ]]; then
  echo "FAIL: Expected application/json content type for /does-not-exist, got $DNE_CT"
  exit 1
fi
DNE_CODE=$(echo "$DNE_BODY" | jq -r '.error.code // empty')
if [ "$DNE_CODE" != "not_found" ]; then
  echo "FAIL: Expected error.code 'not_found', got: $DNE_BODY"
  exit 1
fi
echo "/does-not-exist correctly returns HTTP 404 application/json (error.code: $DNE_CODE)"

# ---------------------------------------------------------
# 3. Default Permission IsAuthenticated & Error Structure
# ---------------------------------------------------------
echo ""
echo "=== 3. DRF Default Permission (IsAuthenticated) & Error Format ==="

echo "Test 3.1: GET /orders without auth header (must return 401 JSON)"
ORDERS_RES=$(curl -s -w "\nHTTP_STATUS:%{http_code}" -X GET "$BASE_URL/orders")
ORDERS_STATUS=$(echo "$ORDERS_RES" | tail -n1 | cut -d: -f2)
ORDERS_BODY=$(echo "$ORDERS_RES" | sed '$d')
if [ "$ORDERS_STATUS" != "401" ]; then
  echo "FAIL: Expected 401 for unauthenticated GET /orders, got $ORDERS_STATUS"
  exit 1
fi
ORDERS_CODE=$(echo "$ORDERS_BODY" | jq -r '.error.code // empty')
if [ "$ORDERS_CODE" != "unauthorized" ]; then
  echo "FAIL: Expected error.code 'unauthorized', got: $ORDERS_BODY"
  exit 1
fi
echo "GET /orders returned HTTP 401 with standard error format: $ORDERS_BODY"

echo ""
echo "Test 3.2: GET /auth/me without auth header (must return 401 JSON)"
ME_RES=$(curl -s -w "\nHTTP_STATUS:%{http_code}" -X GET "$BASE_URL/auth/me")
ME_STATUS=$(echo "$ME_RES" | tail -n1 | cut -d: -f2)
ME_BODY=$(echo "$ME_RES" | sed '$d')
if [ "$ME_STATUS" != "401" ]; then
  echo "FAIL: Expected 401 for unauthenticated GET /auth/me, got $ME_STATUS"
  exit 1
fi
ME_CODE=$(echo "$ME_BODY" | jq -r '.error.code // empty')
if [ "$ME_CODE" != "unauthorized" ]; then
  echo "FAIL: Expected error.code 'unauthorized', got: $ME_BODY"
  exit 1
fi
echo "GET /auth/me returned HTTP 401 with standard error format: $ME_BODY"

echo ""
echo "Test 3.3: POST /uploads/presign without auth header (must return 401 JSON)"
PRE_RES=$(curl -s -w "\nHTTP_STATUS:%{http_code}" -X POST "$BASE_URL/uploads/presign" \
  -H "Content-Type: application/json" \
  -d '{"purpose":"kyc-id","fileName":"doc.pdf","contentType":"application/pdf","size":1000}')
PRE_STATUS=$(echo "$PRE_RES" | tail -n1 | cut -d: -f2)
PRE_BODY=$(echo "$PRE_RES" | sed '$d')
if [ "$PRE_STATUS" != "401" ]; then
  echo "FAIL: Expected 401 for unauthenticated POST /uploads/presign, got $PRE_STATUS"
  exit 1
fi
PRE_CODE=$(echo "$PRE_BODY" | jq -r '.error.code // empty')
if [ "$PRE_CODE" != "unauthorized" ]; then
  echo "FAIL: Expected error.code 'unauthorized', got: $PRE_BODY"
  exit 1
fi
echo "POST /uploads/presign returned HTTP 401 with standard error format: $PRE_BODY"

# ---------------------------------------------------------
# 4. Campaign Bids Permissions & Scoping Verification
# ---------------------------------------------------------
echo ""
echo "=== 4. Campaign Bids Gating & Ownership Verification ==="

RAND_SUFFIX=$RANDOM
# Register Brand A (Campaign Owner)
BRAND_A_EMAIL="branda_${RAND_SUFFIX}@example.com"
curl -s -X POST "$BASE_URL/auth/signup" -H "Content-Type: application/json" \
  -d "{\"name\":\"Brand A\",\"email\":\"$BRAND_A_EMAIL\",\"password\":\"$TEST_PASSWORD\",\"companyName\":\"Alpha Brands\"}" > /dev/null
LOGIN_A=$(curl -s -X POST "$BASE_URL/auth/login" -H "Content-Type: application/json" \
  -d "{\"identifier\":\"$BRAND_A_EMAIL\",\"password\":\"$TEST_PASSWORD\"}")
TOKEN_BRAND_A=$(echo "$LOGIN_A" | jq -r .token)

# Register Brand B (Foreign Brand)
BRAND_B_EMAIL="brandb_${RAND_SUFFIX}@example.com"
curl -s -X POST "$BASE_URL/auth/signup" -H "Content-Type: application/json" \
  -d "{\"name\":\"Brand B\",\"email\":\"$BRAND_B_EMAIL\",\"password\":\"$TEST_PASSWORD\",\"companyName\":\"Beta Brands\"}" > /dev/null
LOGIN_B=$(curl -s -X POST "$BASE_URL/auth/login" -H "Content-Type: application/json" \
  -d "{\"identifier\":\"$BRAND_B_EMAIL\",\"password\":\"$TEST_PASSWORD\"}")
TOKEN_BRAND_B=$(echo "$LOGIN_B" | jq -r .token)

# Creator Token
CREATOR_LOGIN=$(curl -s -X POST "$BASE_URL/auth/login" -H "Content-Type: application/json" \
  -d '{"identifier":"+919999999999","password":"changedpass123"}')
TOKEN_CREATOR=$(echo "$CREATOR_LOGIN" | jq -r '.accessToken // empty')
if [ -z "$TOKEN_CREATOR" ]; then
  CREATOR_LOGIN=$(curl -s -X POST "$BASE_URL/auth/login" -H "Content-Type: application/json" \
    -d '{"identifier":"+919999999998","password":"changedpass123"}')
  TOKEN_CREATOR=$(echo "$CREATOR_LOGIN" | jq -r '.accessToken // empty')
fi

# Brand A creates open campaign
CAMP_CREATE=$(curl -s -X POST "$BASE_URL/campaigns" \
  -H "Authorization: Bearer $TOKEN_BRAND_A" \
  -H "Content-Type: application/json" \
  -d '{"title":"Diwali Glow Fest","platform":"Instagram","deliverables":"2 Reels","budgetMin":10000,"budgetMax":25000,"applyBy":"2026-11-15T18:00:00Z"}')
CAMP_ID=$(echo "$CAMP_CREATE" | jq -r .id)
echo "Created open campaign: $CAMP_ID"

echo ""
echo "Test 4.1: Anonymous POST to /campaigns/$CAMP_ID/bids (must return 401)"
ANON_BID=$(curl -s -w "\nHTTP_STATUS:%{http_code}" -X POST "$BASE_URL/campaigns/$CAMP_ID/bids" \
  -H "Content-Type: application/json" \
  -d '{"price":15000}')
ANON_BID_STATUS=$(echo "$ANON_BID" | tail -n1 | cut -d: -f2)
if [ "$ANON_BID_STATUS" != "401" ]; then
  echo "FAIL: Expected 401 for anonymous bid post, got $ANON_BID_STATUS"
  exit 1
fi
echo "Anonymous POST rejected with 401 OK"

echo ""
echo "Test 4.2: Brand token on POST to /campaigns/$CAMP_ID/bids (must return 403)"
BRAND_BID=$(curl -s -w "\nHTTP_STATUS:%{http_code}" -X POST "$BASE_URL/campaigns/$CAMP_ID/bids" \
  -H "Authorization: Bearer $TOKEN_BRAND_A" \
  -H "Content-Type: application/json" \
  -d '{"price":15000}')
BRAND_BID_STATUS=$(echo "$BRAND_BID" | tail -n1 | cut -d: -f2)
if [ "$BRAND_BID_STATUS" != "403" ]; then
  echo "FAIL: Expected 403 for brand token on bid post, got $BRAND_BID_STATUS"
  exit 1
fi
echo "Brand token on POST correctly forbidden with 403 OK"

echo ""
echo "Test 4.3: Creator token on POST to /campaigns/$CAMP_ID/bids (must return 201)"
CREATOR_BID=$(curl -s -w "\nHTTP_STATUS:%{http_code}" -X POST "$BASE_URL/campaigns/$CAMP_ID/bids" \
  -H "Authorization: Bearer $TOKEN_CREATOR" \
  -H "Content-Type: application/json" \
  -d '{"price":14000,"note":"Passionate about beauty content"}')
CREATOR_BID_STATUS=$(echo "$CREATOR_BID" | tail -n1 | cut -d: -f2)
CREATOR_BID_BODY=$(echo "$CREATOR_BID" | sed '$d')
if [ "$CREATOR_BID_STATUS" != "201" ]; then
  echo "FAIL: Expected 201 for creator token on bid post, got $CREATOR_BID_STATUS: $CREATOR_BID_BODY"
  exit 1
fi
BID_ID=$(echo "$CREATOR_BID_BODY" | jq -r .id)
echo "Creator token on POST succeeded with 201 OK (Bid ID: $BID_ID)"

echo ""
echo "Test 4.4: Anonymous GET /campaigns/$CAMP_ID/bids (must return 401)"
ANON_GET_BIDS=$(curl -s -w "\nHTTP_STATUS:%{http_code}" -X GET "$BASE_URL/campaigns/$CAMP_ID/bids")
ANON_GET_BIDS_STATUS=$(echo "$ANON_GET_BIDS" | tail -n1 | cut -d: -f2)
if [ "$ANON_GET_BIDS_STATUS" != "401" ]; then
  echo "FAIL: Expected 401 for anonymous GET bids, got $ANON_GET_BIDS_STATUS"
  exit 1
fi
echo "Anonymous GET bids rejected with 401 OK"

echo ""
echo "Test 4.5: Foreign Brand B token on GET /campaigns/$CAMP_ID/bids (must return 404)"
BRAND_B_GET_BIDS=$(curl -s -w "\nHTTP_STATUS:%{http_code}" -X GET "$BASE_URL/campaigns/$CAMP_ID/bids" \
  -H "Authorization: Bearer $TOKEN_BRAND_B")
BRAND_B_GET_BIDS_STATUS=$(echo "$BRAND_B_GET_BIDS" | tail -n1 | cut -d: -f2)
if [ "$BRAND_B_GET_BIDS_STATUS" != "404" ]; then
  echo "FAIL: Expected 404 for foreign brand on GET bids, got $BRAND_B_GET_BIDS_STATUS"
  exit 1
fi
echo "Foreign brand on GET bids isolated with 404 OK"

echo ""
echo "Test 4.6: Owner Brand A token on GET /campaigns/$CAMP_ID/bids (must return 200 with bid)"
BRAND_A_GET_BIDS=$(curl -s -w "\nHTTP_STATUS:%{http_code}" -X GET "$BASE_URL/campaigns/$CAMP_ID/bids" \
  -H "Authorization: Bearer $TOKEN_BRAND_A")
BRAND_A_GET_BIDS_STATUS=$(echo "$BRAND_A_GET_BIDS" | tail -n1 | cut -d: -f2)
BRAND_A_GET_BIDS_BODY=$(echo "$BRAND_A_GET_BIDS" | sed '$d')
if [ "$BRAND_A_GET_BIDS_STATUS" != "200" ]; then
  echo "FAIL: Expected 200 for owner brand on GET bids, got $BRAND_A_GET_BIDS_STATUS"
  exit 1
fi
BIDS_COUNT=$(echo "$BRAND_A_GET_BIDS_BODY" | jq '. | length')
if [ "$BIDS_COUNT" -lt 1 ]; then
  echo "FAIL: Expected at least 1 bid, got $BIDS_COUNT"
  exit 1
fi
echo "Owner brand successfully retrieved bids (HTTP 200, count: $BIDS_COUNT)"

# ---------------------------------------------------------
# 5. SHOW_SEED_DATA Default False Verification
# ---------------------------------------------------------
echo ""
echo "=== 5. SHOW_SEED_DATA Default False Verification ==="
CREATORS_RES=$(curl -s "$BASE_URL/creators")
TOTAL_CREATORS=$(echo "$CREATORS_RES" | jq -r '.total // empty')
SEED_NAMES=$(echo "$CREATORS_RES" | jq -r '.results[] | select(.id=="ananya-rao" or .id=="rohan-verma" or .id=="neha-sharma") | .name')

if [ -n "$SEED_NAMES" ]; then
  echo "FAIL: Seed creators found in response when SHOW_SEED_DATA is false: $SEED_NAMES"
  exit 1
fi
echo "Public GET /creators returned only real creators (total: $TOTAL_CREATORS, 0 seed creators found)"

echo ""
echo "=== ALL PUBLIC SECURITY, CORS & BIDS TESTS PASSED ==="
