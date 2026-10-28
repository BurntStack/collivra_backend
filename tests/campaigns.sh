#!/usr/bin/env bash
set -e

BASE_URL="${COLLIVRA_BASE_URL:-http://127.0.0.1:8000/api/v1}"
TEST_PASSWORD="${COLLIVRA_TEST_PASSWORD:-password123}"

echo "=== 1. Log in / register brand user ==="
RANDOM_INT=$((RANDOM % 90000 + 10000))
TEST_BRAND_EMAIL="brand_${RANDOM_INT}@acmebrand.com"
SIGNUP_RES=$(curl -s -X POST "$BASE_URL/auth/signup" \
  -H "Content-Type: application/json" \
  -d "{\"name\":\"Campaign Brand\",\"email\":\"$TEST_BRAND_EMAIL\",\"password\":\"$TEST_PASSWORD\",\"companyName\":\"Acme Co\"}")
TOKEN=$(echo "$SIGNUP_RES" | jq -r '.token // empty')

if [ -z "$TOKEN" ]; then
  echo "Brand authentication failed: $SIGNUP_RES"
  exit 1
fi
echo "Brand token acquired"

echo ""
echo "=== 2. Campaign Validation Check (budgetMin >= budgetMax should return 422) ==="
INVALID_CAMP=$(curl -s -w "\nHTTP_STATUS:%{http_code}" -X POST "$BASE_URL/campaigns" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "title":"Invalid Budget Campaign",
    "platform":"Instagram",
    "deliverables":"1 Reel",
    "budgetMin":30000,
    "budgetMax":20000,
    "applyBy":"2026-12-01"
  }')
STATUS=$(echo "$INVALID_CAMP" | tail -n1 | cut -d: -f2)
if [ "$STATUS" != "422" ]; then
  echo "Expected 422 for budgetMin >= budgetMax, got $STATUS"
  exit 1
fi
echo "Budget validation check OK (422)"

echo ""
echo "=== 3. Post Campaign (Open for Bids) ==="
POST_CAMP_RES=$(curl -s -w "\nHTTP_STATUS:%{http_code}" -X POST "$BASE_URL/campaigns" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "title":"Winter Hydration Skincare Launch",
    "platform":"Instagram",
    "deliverables":"1 Reel (30–45 sec) + 2 Stories with link sticker",
    "budgetMin":10000,
    "budgetMax":25000,
    "applyBy":"2026-11-20",
    "brief":"Looking for beauty creators to highlight our new ceramide moisturizer in a clean morning skincare routine."
  }')
STATUS=$(echo "$POST_CAMP_RES" | tail -n1 | cut -d: -f2)
BODY=$(echo "$POST_CAMP_RES" | sed '$d')
if [ "$STATUS" != "201" ]; then
  echo "Campaign creation failed: $POST_CAMP_RES"
  exit 1
fi
CAMP_ID=$(echo "$BODY" | jq -r '.id')
echo "Campaign created successfully (201, id: $CAMP_ID)"

echo ""
echo "=== 4. B2 Campaign Edit Rules Before Bids ==="
echo "Test 4.1: Unknown field should return 422"
UNKNOWN_EDIT=$(curl -s -w "\nHTTP_STATUS:%{http_code}" -X PATCH "$BASE_URL/campaigns/$CAMP_ID" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"unknownField":"hacked"}')
STATUS=$(echo "$UNKNOWN_EDIT" | tail -n1 | cut -d: -f2)
if [ "$STATUS" != "422" ]; then
  echo "Expected 422 for unknown field in PATCH, got $STATUS"
  exit 1
fi
echo "Unknown field rejected OK (422)"

echo "Test 4.2: applyBy in the past should return 422"
PAST_EDIT=$(curl -s -w "\nHTTP_STATUS:%{http_code}" -X PATCH "$BASE_URL/campaigns/$CAMP_ID" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"applyBy":"2020-01-01"}')
STATUS=$(echo "$PAST_EDIT" | tail -n1 | cut -d: -f2)
if [ "$STATUS" != "422" ]; then
  echo "Expected 422 for past applyBy in PATCH, got $STATUS"
  exit 1
fi
echo "Past applyBy rejected OK (422)"

echo "Test 4.3: budgetMin >= budgetMax should return 422"
BAD_BUDGET_EDIT=$(curl -s -w "\nHTTP_STATUS:%{http_code}" -X PATCH "$BASE_URL/campaigns/$CAMP_ID" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"budgetMin":30000}')
STATUS=$(echo "$BAD_BUDGET_EDIT" | tail -n1 | cut -d: -f2)
if [ "$STATUS" != "422" ]; then
  echo "Expected 422 for invalid budget in PATCH, got $STATUS"
  exit 1
fi
echo "Invalid budget rejected OK (422)"

echo "Test 4.4: Valid edit before bids should succeed (200)"
VALID_EDIT=$(curl -s -w "\nHTTP_STATUS:%{http_code}" -X PATCH "$BASE_URL/campaigns/$CAMP_ID" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"title":"Winter Hydration Launch (Early Birds)","budgetMax":28000}')
STATUS=$(echo "$VALID_EDIT" | tail -n1 | cut -d: -f2)
if [ "$STATUS" != "200" ]; then
  echo "Valid edit failed: $VALID_EDIT"
  exit 1
fi
echo "Valid edit before bids OK (200)"

echo ""
echo "=== 5. Submit Bids to Campaign ==="
CREATOR_LOGIN=$(curl -s -X POST "$BASE_URL/auth/login" \
  -H "Content-Type: application/json" \
  -d '{"identifier":"+919999999999","password":"changedpass123"}')
CREATOR_TOKEN=$(echo "$CREATOR_LOGIN" | jq -r '.accessToken // empty')
if [ -z "$CREATOR_TOKEN" ]; then
  CREATOR_LOGIN=$(curl -s -X POST "$BASE_URL/auth/login" \
    -H "Content-Type: application/json" \
    -d '{"identifier":"+919999999998","password":"changedpass123"}')
  CREATOR_TOKEN=$(echo "$CREATOR_LOGIN" | jq -r '.accessToken // empty')
fi

BID1_RES=$(curl -s -w "\nHTTP_STATUS:%{http_code}" -X POST "$BASE_URL/campaigns/$CAMP_ID/bids" \
  -H "Authorization: Bearer $CREATOR_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"price":18000,"note":"Excited to partner on this launch!"}')
STATUS=$(echo "$BID1_RES" | tail -n1 | cut -d: -f2)
BODY=$(echo "$BID1_RES" | sed '$d')
if [ "$STATUS" != "201" ]; then
  echo "Bid submission failed: $BID1_RES"
  exit 1
fi
BID1_ID=$(echo "$BODY" | jq -r '.id')
echo "Bid 1 submitted OK (201, id: $BID1_ID)"

echo ""
echo "=== 6. B2 Campaign Edit Rules After Bids Exist ==="
echo "Test 6.1: Editing locked field (budgetMax) when bids exist should return 409"
LOCKED_EDIT=$(curl -s -w "\nHTTP_STATUS:%{http_code}" -X PATCH "$BASE_URL/campaigns/$CAMP_ID" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"budgetMax":35000}')
STATUS=$(echo "$LOCKED_EDIT" | tail -n1 | cut -d: -f2)
if [ "$STATUS" != "409" ]; then
  echo "Expected 409 for editing budget when bids exist, got $STATUS"
  exit 1
fi
echo "Locked field correctly rejected with 409"

echo "Test 6.2: Editing non-locked field (title, brief) when bids exist should succeed (200)"
ALLOWED_EDIT=$(curl -s -w "\nHTTP_STATUS:%{http_code}" -X PATCH "$BASE_URL/campaigns/$CAMP_ID" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"title":"Winter Hydration Skincare Campaign (Final)"}')
STATUS=$(echo "$ALLOWED_EDIT" | tail -n1 | cut -d: -f2)
if [ "$STATUS" != "200" ]; then
  echo "Expected 200 for editing allowed field, got $STATUS: $ALLOWED_EDIT"
  exit 1
fi
echo "Allowed field edit after bids OK (200)"

echo ""
echo "=== 7. B2 Campaign Delete Rules ==="
echo "Test 7.1: Deleting open campaign with bids should return 409"
DELETE_WITH_BIDS=$(curl -s -w "\nHTTP_STATUS:%{http_code}" -X DELETE "$BASE_URL/campaigns/$CAMP_ID" \
  -H "Authorization: Bearer $TOKEN")
STATUS=$(echo "$DELETE_WITH_BIDS" | tail -n1 | cut -d: -f2)
if [ "$STATUS" != "409" ]; then
  echo "Expected 409 for deleting campaign with bids, got $STATUS"
  exit 1
fi
echo "Delete with bids rejected OK (409)"

echo "Test 7.2: Create and delete draft campaign (should return 204 soft delete)"
DRAFT_RES=$(curl -s -X POST "$BASE_URL/campaigns" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"title":"Draft Campaign To Delete","platform":"YouTube","deliverables":"1 Short","budgetMin":5000,"budgetMax":8000,"applyBy":"2026-12-01","status":"draft"}')
DRAFT_ID=$(echo "$DRAFT_RES" | jq -r '.id')

DELETE_DRAFT=$(curl -s -w "\nHTTP_STATUS:%{http_code}" -X DELETE "$BASE_URL/campaigns/$DRAFT_ID" \
  -H "Authorization: Bearer $TOKEN")
STATUS=$(echo "$DELETE_DRAFT" | tail -n1 | cut -d: -f2)
if [ "$STATUS" != "204" ]; then
  echo "Expected 204 for deleting draft campaign, got $STATUS"
  exit 1
fi
echo "Draft campaign soft deleted OK (204)"

echo "Test 7.3: Soft-deleted campaign should return 404 on GET /campaigns/:id"
GET_DELETED=$(curl -s -w "\nHTTP_STATUS:%{http_code}" -X GET "$BASE_URL/campaigns/$DRAFT_ID" \
  -H "Authorization: Bearer $TOKEN")
STATUS=$(echo "$GET_DELETED" | tail -n1 | cut -d: -f2)
if [ "$STATUS" != "404" ]; then
  echo "Expected 404 for soft deleted campaign, got $STATUS"
  exit 1
fi
echo "Soft-deleted campaign excluded from queries OK (404)"

echo ""
echo "=== 8. Select Bid -> Creates Escrow Order & Awards Campaign ==="
SELECT_RES=$(curl -s -w "\nHTTP_STATUS:%{http_code}" -X POST "$BASE_URL/campaigns/$CAMP_ID/bids/$BID1_ID/select" \
  -H "Authorization: Bearer $TOKEN")
STATUS=$(echo "$SELECT_RES" | tail -n1 | cut -d: -f2)
if [ "$STATUS" != "201" ]; then
  echo "Bid selection failed: $SELECT_RES"
  exit 1
fi
echo "Bid selection OK (201)"

echo "Test 8.2: Awarded campaign cannot be edited (should return 409)"
EDIT_AWARDED=$(curl -s -w "\nHTTP_STATUS:%{http_code}" -X PATCH "$BASE_URL/campaigns/$CAMP_ID" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"title":"Trying to edit awarded campaign"}')
STATUS=$(echo "$EDIT_AWARDED" | tail -n1 | cut -d: -f2)
if [ "$STATUS" != "409" ]; then
  echo "Expected 409 for editing awarded campaign, got $STATUS"
  exit 1
fi
echo "Awarded campaign edit rejected OK (409)"

echo ""
echo "=== ALL CAMPAIGN & B2 TESTS PASSED ==="
