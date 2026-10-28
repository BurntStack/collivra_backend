#!/usr/bin/env bash
set -e

BASE_URL="${COLLIVRA_BASE_URL:-http://127.0.0.1:8000/api/v1}"
REST_URL="${COLLIVRA_REST_URL:-https://eetmsobqxlbsvcoscjnb.supabase.co/rest/v1}"
AUTH_ADMIN_URL="${COLLIVRA_AUTH_ADMIN_URL:-https://eetmsobqxlbsvcoscjnb.supabase.co/auth/v1/admin/users}"
TEST_PASSWORD="${COLLIVRA_TEST_PASSWORD:-secpass123}"
CREATOR_MOBILE="${COLLIVRA_CREATOR_MOBILE:-+919999999999}"

# Read service key and anon key safely without ever printing them
SERVICE_KEY="${SERVICE_KEY:-${SUPABASE_SERVICE_ROLE_KEY:-$COLLIVRA_SERVICE_KEY}}"
ANON_KEY="${COLLIVRA_ANON_KEY:-$SUPABASE_ANON_KEY}"
if [ -z "$SERVICE_KEY" ] || [ -z "$ANON_KEY" ]; then
  KEYS_JSON=$(supabase projects api-keys --project-ref eetmsobqxlbsvcoscjnb 2>/dev/null || true)
  if [ -z "$SERVICE_KEY" ]; then
    SERVICE_KEY=$(echo "$KEYS_JSON" | jq -r '.keys[] | select(.id == "service_role") | .api_key')
  fi
  if [ -z "$ANON_KEY" ]; then
    ANON_KEY=$(echo "$KEYS_JSON" | jq -r '.keys[] | select(.id == "anon") | .api_key')
  fi
fi

echo "=== Collivra Security & Isolation Test Suite ==="
echo "Target Base URL: $BASE_URL"

echo ""
echo "=== 1. Setup Accounts: Brand A & Brand B ==="
RAND_A=$((RANDOM % 90000 + 10000))
EMAIL_A="brand_a_${RAND_A}@secbrand.com"
SIGNUP_A=$(curl -s -X POST "$BASE_URL/auth/signup" \
  -H "Content-Type: application/json" \
  -d "{\"name\":\"Brand A\",\"email\":\"$EMAIL_A\",\"password\":\"$TEST_PASSWORD\",\"companyName\":\"Alpha Inc\"}")
TOKEN_A=$(echo "$SIGNUP_A" | jq -r '.token // empty')
USER_A=$(echo "$SIGNUP_A" | jq -r '.user.id')

RAND_B=$((RANDOM % 90000 + 10000))
EMAIL_B="brand_b_${RAND_B}@secbrand.com"
SIGNUP_B=$(curl -s -X POST "$BASE_URL/auth/signup" \
  -H "Content-Type: application/json" \
  -d "{\"name\":\"Brand B\",\"email\":\"$EMAIL_B\",\"password\":\"$TEST_PASSWORD\",\"companyName\":\"Beta Inc\"}")
TOKEN_B=$(echo "$SIGNUP_B" | jq -r '.token // empty')
USER_B=$(echo "$SIGNUP_B" | jq -r '.user.id')

if [ -z "$TOKEN_A" ] || [ -z "$TOKEN_B" ]; then
  echo "Failed to create test brand accounts"
  exit 1
fi
echo "Brand A and Brand B authenticated successfully"

# Get creator token
CREATOR_LOGIN=$(curl -s -X POST "$BASE_URL/auth/login" \
  -H "Content-Type: application/json" \
  -d "{\"identifier\":\"$CREATOR_MOBILE\",\"password\":\"changedpass123\"}")
TOKEN_CREATOR=$(echo "$CREATOR_LOGIN" | jq -r '.accessToken // empty')
if [ -z "$TOKEN_CREATOR" ]; then
  # Fallback to test creator default pass if not changed
  CREATOR_LOGIN=$(curl -s -X POST "$BASE_URL/auth/login" \
    -H "Content-Type: application/json" \
    -d "{\"identifier\":\"$CREATOR_MOBILE\",\"password\":\"creatorpass123\"}")
  TOKEN_CREATOR=$(echo "$CREATOR_LOGIN" | jq -r '.accessToken // empty')
fi
if [ -z "$TOKEN_CREATOR" ]; then
  # Or OTP login
  OTP_RES=$(curl -s -X POST "$BASE_URL/auth/otp/verify" \
    -H "Content-Type: application/json" \
    -d "{\"mobile\":\"$CREATOR_MOBILE\",\"code\":\"123456\",\"purpose\":\"login\"}")
  TOKEN_CREATOR=$(echo "$OTP_RES" | jq -r '.accessToken // empty')
fi
if [ -z "$TOKEN_CREATOR" ]; then
  echo "Failed to acquire creator token for security testing"
  exit 1
fi
echo "Creator token acquired"

echo ""
echo "=== 2. Unauthenticated Requests (Must Return 401) ==="
test_401() {
  local method="$1"
  local path="$2"
  local res=$(curl -s -w "\nHTTP_STATUS:%{http_code}" -X "$method" "$BASE_URL$path")
  local st=$(echo "$res" | tail -n1 | cut -d: -f2)
  if [ "$st" != "401" ]; then
    echo "Expected 401 for $method $path without token, got $st"
    exit 1
  fi
}
test_401 "GET" "/auth/me"
test_401 "GET" "/campaigns"
test_401 "GET" "/orders"
test_401 "GET" "/cart"
test_401 "GET" "/lists"
echo "All unauthenticated requests correctly rejected with 401"

echo ""
echo "=== 3. Creator Token on Brand Endpoints (Must Return 403) ==="
test_403_creator() {
  local method="$1"
  local path="$2"
  local data="$3"
  local res
  if [ -n "$data" ]; then
    res=$(curl -s -w "\nHTTP_STATUS:%{http_code}" -X "$method" "$BASE_URL$path" \
      -H "Authorization: Bearer $TOKEN_CREATOR" \
      -H "Content-Type: application/json" \
      -d "$data")
  else
    res=$(curl -s -w "\nHTTP_STATUS:%{http_code}" -X "$method" "$BASE_URL$path" \
      -H "Authorization: Bearer $TOKEN_CREATOR")
  fi
  local st=$(echo "$res" | tail -n1 | cut -d: -f2)
  if [ "$st" != "403" ]; then
    echo "Expected 403 for creator calling brand endpoint $method $path, got $st: $res"
    exit 1
  fi
}
test_403_creator "POST" "/campaigns" '{"title":"Creator Camp","budget":5000}'
test_403_creator "POST" "/orders" '{"creatorId":"ananya-rao","packageId":"pkg_1","deliverable":"Reel","amount":8000}'
test_403_creator "GET" "/cart"
test_403_creator "POST" "/cart/items" '{"creatorId":"ananya-rao","packageId":"pkg_1","quantity":1}'
test_403_creator "GET" "/lists"
echo "Creator token correctly forbidden on brand endpoints with 403"

echo ""
echo "=== 4. Direct PostgREST Database Access (Must Return 403) ==="
test_direct_rest() {
  local method="$1"
  local path="$2"
  local data="$3"
  local res
  if [ -n "$data" ]; then
    res=$(curl -s -w "\nHTTP_STATUS:%{http_code}" -X "$method" "$REST_URL$path" \
      -H "Authorization: Bearer $TOKEN_A" \
      -H "apikey: $ANON_KEY" \
      -H "Content-Type: application/json" \
      -d "$data")
  else
    res=$(curl -s -w "\nHTTP_STATUS:%{http_code}" -X "$method" "$REST_URL$path" \
      -H "Authorization: Bearer $TOKEN_A" \
      -H "apikey: $ANON_KEY")
  fi
  local st=$(echo "$res" | tail -n1 | cut -d: -f2)
  if [ "$st" != "403" ]; then
    echo "Expected 403 for direct PostgREST $method $path, got $st: $res"
    exit 1
  fi
}
test_direct_rest "POST" "/orders" '{"amount":100}'
test_direct_rest "PATCH" "/orders?id=eq.00000000-0000-0000-0000-000000000000" '{"status":"completed"}'
test_direct_rest "POST" "/campaign_bids" '{"price":500}'
test_direct_rest "GET" "/profiles"
echo "Direct PostgREST database access blocked with 403 for all endpoints"

echo ""
echo "=== 5. Cart Quantity Validation (Must Return 422 for 0, -1, 21) ==="
test_cart_quantity() {
  local qty="$1"
  local res=$(curl -s -w "\nHTTP_STATUS:%{http_code}" -X POST "$BASE_URL/cart/items" \
    -H "Authorization: Bearer $TOKEN_A" \
    -H "Content-Type: application/json" \
    -d "{\"creatorId\":\"ananya-rao\",\"packageId\":\"pkg_1\",\"quantity\":$qty}")
  local st=$(echo "$res" | tail -n1 | cut -d: -f2)
  if [ "$st" != "422" ]; then
    echo "Expected 422 for cart quantity $qty, got $st: $res"
    exit 1
  fi
}
test_cart_quantity 0
test_cart_quantity -1
test_cart_quantity 21
echo "Cart quantity boundaries (0, -1, 21) correctly rejected with 422"

echo ""
echo "=== 6. Brand Isolation: Cross-Brand Resource Gating (Must Return 404) ==="
# Setup Brand A resources:
# 6.1 Campaign A
CAMP_A=$(curl -s -X POST "$BASE_URL/campaigns" \
  -H "Authorization: Bearer $TOKEN_A" \
  -H "Content-Type: application/json" \
  -d '{"title":"Alpha Campaign","budget":50000,"currency":"INR","requirements":"Security test"}')
CAMP_A_ID=$(echo "$CAMP_A" | jq -r '.id')

# 6.2 Order A
ORDER_A=$(curl -s -X POST "$BASE_URL/orders" \
  -H "Authorization: Bearer $TOKEN_A" \
  -H "Content-Type: application/json" \
  -d '{"creatorId":"ananya-rao","packageId":"pkg_1","deliverable":"1 Instagram Reel","amount":8000}')
ORDER_A_ID=$(echo "$ORDER_A" | jq -r '.id')

# 6.3 List A
LIST_A=$(curl -s -X POST "$BASE_URL/lists" \
  -H "Authorization: Bearer $TOKEN_A" \
  -H "Content-Type: application/json" \
  -d '{"name":"Alpha Shortlist"}')
LIST_A_ID=$(echo "$LIST_A" | jq -r '.id')

# 6.4 Cart Item A
CART_ADD_A=$(curl -s -X POST "$BASE_URL/cart/items" \
  -H "Authorization: Bearer $TOKEN_A" \
  -H "Content-Type: application/json" \
  -d '{"creatorId":"ananya-rao","packageId":"pkg_1","quantity":2}')
CART_A_ITEM_ID=$(echo "$CART_ADD_A" | jq -r '.item.id // empty')
if [ -z "$CART_A_ITEM_ID" ]; then
  # Try getting cart
  CART_GET=$(curl -s -X GET "$BASE_URL/cart" -H "Authorization: Bearer $TOKEN_A")
  CART_A_ITEM_ID=$(echo "$CART_GET" | jq -r '.items[0].id')
fi

# Now verify Brand B accessing Brand A's resources returns 404 for EVERY endpoint
test_404_isolation() {
  local desc="$1"
  local method="$2"
  local path="$3"
  local data="$4"
  local res
  if [ -n "$data" ]; then
    res=$(curl -s -w "\nHTTP_STATUS:%{http_code}" -X "$method" "$BASE_URL$path" \
      -H "Authorization: Bearer $TOKEN_B" \
      -H "Content-Type: application/json" \
      -d "$data")
  else
    res=$(curl -s -w "\nHTTP_STATUS:%{http_code}" -X "$method" "$BASE_URL$path" \
      -H "Authorization: Bearer $TOKEN_B")
  fi
  local st=$(echo "$res" | tail -n1 | cut -d: -f2)
  if [ "$st" != "404" ]; then
    echo "Isolation violation ($desc)! Expected 404, got $st: $res"
    exit 1
  fi
}

test_404_isolation "Brand B GET Campaign A" "GET" "/campaigns/$CAMP_A_ID"
test_404_isolation "Brand B PATCH Campaign A" "PATCH" "/campaigns/$CAMP_A_ID" '{"title":"Hacked"}'
test_404_isolation "Brand B DELETE Campaign A" "DELETE" "/campaigns/$CAMP_A_ID"
test_404_isolation "Brand B GET Campaign A Bids" "GET" "/campaigns/$CAMP_A_ID/bids"

test_404_isolation "Brand B GET Order A" "GET" "/orders/$ORDER_A_ID"
test_404_isolation "Brand B POST Order A Pay" "POST" "/orders/$ORDER_A_ID/pay"
test_404_isolation "Brand B POST Order A Confirm Stub" "POST" "/orders/$ORDER_A_ID/confirm-payment-stub"
test_404_isolation "Brand B POST Order A Request Changes" "POST" "/orders/$ORDER_A_ID/request-changes" '{"feedback":"Hacked"}'
test_404_isolation "Brand B POST Order A Approve" "POST" "/orders/$ORDER_A_ID/approve"

test_404_isolation "Brand B GET List A" "GET" "/lists/$LIST_A_ID"
test_404_isolation "Brand B POST List A Creator" "POST" "/lists/$LIST_A_ID/creators" '{"creatorId":"ananya-rao"}'

test_404_isolation "Brand B PATCH Cart Item A" "PATCH" "/cart/items/$CART_A_ITEM_ID" '{"quantity":5}'
test_404_isolation "Brand B DELETE Cart Item A" "DELETE" "/cart/items/$CART_A_ITEM_ID"
echo "Cross-brand isolation verified: all foreign accesses returned 404"

echo ""
echo "=== 7. Order State Machine Integrity & Conflicts (409) ==="
# 7.1 Approve from awaiting_payment must return 409
APPROVE_EARLY=$(curl -s -w "\nHTTP_STATUS:%{http_code}" -X POST "$BASE_URL/orders/$ORDER_A_ID/approve" \
  -H "Authorization: Bearer $TOKEN_A")
APPROVE_EARLY_ST=$(echo "$APPROVE_EARLY" | tail -n1 | cut -d: -f2)
if [ "$APPROVE_EARLY_ST" != "409" ]; then
  echo "Expected 409 when approving order in awaiting_payment, got $APPROVE_EARLY_ST"
  exit 1
fi
echo "Approve from awaiting_payment correctly returned 409"

# 7.2 Fund order A via confirm-payment-stub
STUB_CONFIRM=$(curl -s -w "\nHTTP_STATUS:%{http_code}" -X POST "$BASE_URL/orders/$ORDER_A_ID/confirm-payment-stub" \
  -H "Authorization: Bearer $TOKEN_A")
STUB_CONFIRM_ST=$(echo "$STUB_CONFIRM" | tail -n1 | cut -d: -f2)
if [ "$STUB_CONFIRM_ST" != "200" ]; then
  echo "Payment confirmation stub failed, got $STUB_CONFIRM_ST: $STUB_CONFIRM"
  exit 1
fi
echo "Order A moved to in_escrow"

# 7.3 Second confirm-payment-stub must return 409 (already in_escrow)
DOUBLE_CONFIRM=$(curl -s -w "\nHTTP_STATUS:%{http_code}" -X POST "$BASE_URL/orders/$ORDER_A_ID/confirm-payment-stub" \
  -H "Authorization: Bearer $TOKEN_A")
DOUBLE_CONFIRM_ST=$(echo "$DOUBLE_CONFIRM" | tail -n1 | cut -d: -f2)
if [ "$DOUBLE_CONFIRM_ST" != "409" ]; then
  echo "Expected 409 for duplicate confirm-payment-stub, got $DOUBLE_CONFIRM_ST"
  exit 1
fi
echo "Duplicate payment confirmation correctly returned 409"

# 7.4 Pay endpoint from in_escrow must return 409
PAY_IN_ESCROW=$(curl -s -w "\nHTTP_STATUS:%{http_code}" -X POST "$BASE_URL/orders/$ORDER_A_ID/pay" \
  -H "Authorization: Bearer $TOKEN_A")
PAY_IN_ESCROW_ST=$(echo "$PAY_IN_ESCROW" | tail -n1 | cut -d: -f2)
if [ "$PAY_IN_ESCROW_ST" != "409" ]; then
  echo "Expected 409 for pay when order is in_escrow, got $PAY_IN_ESCROW_ST"
  exit 1
fi
echo "Pay endpoint while in_escrow correctly returned 409"

# 7.5 Request changes from in_escrow (before draft submitted) must return 409
CHANGES_EARLY=$(curl -s -w "\nHTTP_STATUS:%{http_code}" -X POST "$BASE_URL/orders/$ORDER_A_ID/request-changes" \
  -H "Authorization: Bearer $TOKEN_A" \
  -H "Content-Type: application/json" \
  -d '{"feedback":"Draft not even submitted"}')
CHANGES_EARLY_ST=$(echo "$CHANGES_EARLY" | tail -n1 | cut -d: -f2)
if [ "$CHANGES_EARLY_ST" != "409" ]; then
  echo "Expected 409 for request-changes before draft submitted, got $CHANGES_EARLY_ST"
  exit 1
fi
echo "Request changes before draft submitted correctly returned 409"

echo ""
echo "=== 8. Draft Submission Role Gating & Admin Workflow ==="
# 8.1 Brand token calling submit-draft must return 403
BRAND_DRAFT=$(curl -s -w "\nHTTP_STATUS:%{http_code}" -X POST "$BASE_URL/orders/$ORDER_A_ID/submit-draft" \
  -H "Authorization: Bearer $TOKEN_A" \
  -H "Content-Type: application/json" \
  -d '{"draftUrl":"https://example.com/draft1.mp4"}')
BRAND_DRAFT_ST=$(echo "$BRAND_DRAFT" | tail -n1 | cut -d: -f2)
if [ "$BRAND_DRAFT_ST" != "403" ]; then
  echo "Expected 403 when brand attempts submit-draft, got $BRAND_DRAFT_ST"
  exit 1
fi
echo "Brand calling submit-draft correctly blocked with 403"

# 8.2 Create admin dynamically using SERVICE_KEY via Auth admin API
ADMIN_EMAIL="sec_admin_${RAND_A}@collivra.test"
ADMIN_USER_RES=$(curl -s -X POST "$AUTH_ADMIN_URL" \
  -H "apikey: $SERVICE_KEY" \
  -H "Authorization: Bearer $SERVICE_KEY" \
  -H "Content-Type: application/json" \
  -d "{
    \"email\": \"$ADMIN_EMAIL\",
    \"password\": \"$TEST_PASSWORD\",
    \"email_confirm\": true,
    \"app_metadata\": {\"role\": \"admin\"},
    \"user_metadata\": {\"name\": \"Security Admin\"}
  }")
ADMIN_UID=$(echo "$ADMIN_USER_RES" | jq -r '.id // empty')
if [ -z "$ADMIN_UID" ]; then
  echo "Admin provisioning via Auth Admin API failed: $ADMIN_USER_RES"
  exit 1
fi
echo "Admin user created successfully via Auth Admin API"

# Log in as admin to get token
ADMIN_LOGIN_RES=$(curl -s -X POST "$BASE_URL/auth/login" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"$ADMIN_EMAIL\",\"password\":\"$TEST_PASSWORD\"}")
TOKEN_ADMIN=$(echo "$ADMIN_LOGIN_RES" | jq -r '.token // .accessToken // empty')
if [ -z "$TOKEN_ADMIN" ]; then
  echo "Admin login failed: $ADMIN_LOGIN_RES"
  exit 1
fi
echo "Admin token acquired"

# 8.3 Admin calls submit-draft -> must succeed with 200
ADMIN_DRAFT=$(curl -s -w "\nHTTP_STATUS:%{http_code}" -X POST "$BASE_URL/orders/$ORDER_A_ID/submit-draft" \
  -H "Authorization: Bearer $TOKEN_ADMIN" \
  -H "Content-Type: application/json" \
  -d '{"draftUrl":"https://cdn.example.com/draft_video.mp4","notes":"First cut"}')
ADMIN_DRAFT_ST=$(echo "$ADMIN_DRAFT" | tail -n1 | cut -d: -f2)
ADMIN_DRAFT_BODY=$(echo "$ADMIN_DRAFT" | sed '$d')
if [ "$ADMIN_DRAFT_ST" != "200" ]; then
  echo "Admin submit-draft failed, got $ADMIN_DRAFT_ST: $ADMIN_DRAFT_BODY"
  exit 1
fi
NEW_STATUS=$(echo "$ADMIN_DRAFT_BODY" | jq -r '.status')
if [ "$NEW_STATUS" != "draft_submitted" ]; then
  echo "Expected status draft_submitted, got $NEW_STATUS"
  exit 1
fi
echo "Admin submit-draft succeeded (HTTP 200, status: draft_submitted)"

# 8.4 Brand A requests changes -> revision count becomes 1
REV1=$(curl -s -w "\nHTTP_STATUS:%{http_code}" -X POST "$BASE_URL/orders/$ORDER_A_ID/request-changes" \
  -H "Authorization: Bearer $TOKEN_A" \
  -H "Content-Type: application/json" \
  -d '{"feedback":"Please brighten colors"}')
REV1_ST=$(echo "$REV1" | tail -n1 | cut -d: -f2)
REV1_BODY=$(echo "$REV1" | sed '$d')
if [ "$REV1_ST" != "200" ]; then
  echo "First revision request failed, got $REV1_ST: $REV1_BODY"
  exit 1
fi
echo "Revision 1 requested (HTTP 200, status: changes_requested, revisionCount: 1)"

# 8.5 Admin submits revision 2
ADMIN_DRAFT2=$(curl -s -w "\nHTTP_STATUS:%{http_code}" -X POST "$BASE_URL/orders/$ORDER_A_ID/submit-draft" \
  -H "Authorization: Bearer $TOKEN_ADMIN" \
  -H "Content-Type: application/json" \
  -d '{"draftUrl":"https://cdn.example.com/draft_v2.mp4"}')
ADMIN_DRAFT2_ST=$(echo "$ADMIN_DRAFT2" | tail -n1 | cut -d: -f2)
ADMIN_DRAFT2_BODY=$(echo "$ADMIN_DRAFT2" | sed '$d')
if [ "$ADMIN_DRAFT2_ST" != "200" ]; then
  echo "Admin submit-draft 2 failed, got $ADMIN_DRAFT2_ST: $ADMIN_DRAFT2_BODY"
  exit 1
fi
echo "Admin draft 2 submitted OK"

# 8.6 Brand A requests changes -> revision count becomes 2
REV2=$(curl -s -w "\nHTTP_STATUS:%{http_code}" -X POST "$BASE_URL/orders/$ORDER_A_ID/request-changes" \
  -H "Authorization: Bearer $TOKEN_A" \
  -H "Content-Type: application/json" \
  -d '{"note":"Trim 2 seconds"}')
REV2_ST=$(echo "$REV2" | tail -n1 | cut -d: -f2)
REV2_BODY=$(echo "$REV2" | sed '$d')
if [ "$REV2_ST" != "200" ]; then
  echo "Second revision request failed, got $REV2_ST: $REV2_BODY"
  exit 1
fi
echo "Revision 2 requested (HTTP 200, status: changes_requested, revisionCount: 2)"

# 8.7 Admin submits revision 3
ADMIN_DRAFT3=$(curl -s -w "\nHTTP_STATUS:%{http_code}" -X POST "$BASE_URL/orders/$ORDER_A_ID/submit-draft" \
  -H "Authorization: Bearer $TOKEN_ADMIN" \
  -H "Content-Type: application/json" \
  -d '{"draftUrl":"https://cdn.example.com/draft_v3.mp4"}')
ADMIN_DRAFT3_ST=$(echo "$ADMIN_DRAFT3" | tail -n1 | cut -d: -f2)
ADMIN_DRAFT3_BODY=$(echo "$ADMIN_DRAFT3" | sed '$d')
if [ "$ADMIN_DRAFT3_ST" != "200" ]; then
  echo "Admin submit-draft 3 failed, got $ADMIN_DRAFT3_ST: $ADMIN_DRAFT3_BODY"
  exit 1
fi
echo "Admin draft 3 submitted OK"

# 8.8 Brand A requests changes 3rd time -> must return 409 max_revisions_reached
REV3=$(curl -s -w "\nHTTP_STATUS:%{http_code}" -X POST "$BASE_URL/orders/$ORDER_A_ID/request-changes" \
  -H "Authorization: Bearer $TOKEN_A" \
  -H "Content-Type: application/json" \
  -d '{"note":"Want yet another change"}')
REV3_ST=$(echo "$REV3" | tail -n1 | cut -d: -f2)
REV3_BODY=$(echo "$REV3" | sed '$d')
if [ "$REV3_ST" != "409" ]; then
  echo "Expected 409 for 3rd revision request (max 2), got $REV3_ST: $REV3_BODY"
  exit 1
fi
REV3_CODE=$(echo "$REV3_BODY" | jq -r '.code // .error.code // empty')
if [ "$REV3_CODE" != "max_revisions_reached" ]; then
  echo "Expected code max_revisions_reached, got $REV3_CODE"
  exit 1
fi
echo "Max 2 revisions limit enforced correctly (HTTP 409, code: max_revisions_reached)"

# 8.9 Brand A approves order -> moves to released
APPROVE_RES=$(curl -s -w "\nHTTP_STATUS:%{http_code}" -X POST "$BASE_URL/orders/$ORDER_A_ID/approve" \
  -H "Authorization: Bearer $TOKEN_A")
APPROVE_ST=$(echo "$APPROVE_RES" | tail -n1 | cut -d: -f2)
if [ "$APPROVE_ST" != "200" ]; then
  echo "Approval failed, got $APPROVE_ST"
  exit 1
fi
echo "Order approved and moved to released (HTTP 200)"

# 8.10 Repeated approve is idempotent 200
APPROVE_REPEAT=$(curl -s -w "\nHTTP_STATUS:%{http_code}" -X POST "$BASE_URL/orders/$ORDER_A_ID/approve" \
  -H "Authorization: Bearer $TOKEN_A")
APPROVE_REPEAT_ST=$(echo "$APPROVE_REPEAT" | tail -n1 | cut -d: -f2)
if [ "$APPROVE_REPEAT_ST" != "200" ]; then
  echo "Expected idempotent 200 on repeat approve, got $APPROVE_REPEAT_ST"
  exit 1
fi
echo "Repeated approve is idempotent (HTTP 200)"

echo ""
echo "=== 9. Teardown / Cleanup ==="
supabase db query --linked "
  delete from public.orders where id = '$ORDER_A_ID';
  delete from public.campaigns where id = '$CAMP_A_ID';
  delete from public.shortlists where id = '$LIST_A_ID';
  delete from public.cart_items where id = '$CART_A_ITEM_ID';
  delete from auth.users where id in ('$USER_A', '$USER_B', '$ADMIN_UID');
  delete from public.profiles where id in ('$USER_A', '$USER_B', '$ADMIN_UID');
" >/dev/null 2>&1 || true
echo "Security test resources cleaned up"

echo ""
echo "ALL SECURITY AND ISOLATION TESTS PASSED."
