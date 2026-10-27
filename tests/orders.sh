#!/usr/bin/env bash
set -e

BASE_URL="${COLLIVRA_BASE_URL:-https://eetmsobqxlbsvcoscjnb.supabase.co/functions/v1/api/v1}"
TEST_PASSWORD="${COLLIVRA_TEST_PASSWORD:-password123}"

echo "=== 1. Log in / register brand user ==="
RANDOM_INT=$((RANDOM % 90000 + 10000))
TEST_BRAND_EMAIL="brand_${RANDOM_INT}@acmebrand.com"
SIGNUP_RES=$(curl -s -X POST "$BASE_URL/auth/signup" \
  -H "Content-Type: application/json" \
  -d "{\"name\":\"Order Brand\",\"email\":\"$TEST_BRAND_EMAIL\",\"password\":\"$TEST_PASSWORD\",\"companyName\":\"Acme Co\"}")
TOKEN=$(echo "$SIGNUP_RES" | jq -r '.token // empty')

if [ -z "$TOKEN" ]; then
  echo "Brand authentication failed: $SIGNUP_RES"
  exit 1
fi
echo "Brand token acquired"

echo ""
echo "=== 2. Create Order (POST /orders) ==="
CREATE_RES=$(curl -s -w "\nHTTP_STATUS:%{http_code}" -X POST "$BASE_URL/orders" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "creatorId": "ananya-rao",
    "packageId": "pkg_1",
    "deliverable": "1 Instagram Reel (30–45 sec)",
    "amount": 8000
  }')
STATUS=$(echo "$CREATE_RES" | tail -n1 | cut -d: -f2)
BODY=$(echo "$CREATE_RES" | sed '$d')
if [ "$STATUS" != "201" ]; then
  echo "Order creation failed: $CREATE_RES"
  exit 1
fi
ORDER_ID=$(echo "$BODY" | jq -r '.id')
ORDER_STATUS=$(echo "$BODY" | jq -r '.status')
echo "Order created OK (201, id: $ORDER_ID, status: $ORDER_STATUS)"

echo ""
echo "=== 3. List Orders (GET /orders) ==="
LIST_RES=$(curl -s -w "\nHTTP_STATUS:%{http_code}" -X GET "$BASE_URL/orders" \
  -H "Authorization: Bearer $TOKEN")
STATUS=$(echo "$LIST_RES" | tail -n1 | cut -d: -f2)
BODY=$(echo "$LIST_RES" | sed '$d')
if [ "$STATUS" != "200" ]; then
  echo "Orders listing failed: $LIST_RES"
  exit 1
fi
COUNT=$(echo "$BODY" | jq 'length')
echo "Orders list OK (200, count: $COUNT)"

echo ""
echo "=== 4. Order Details (GET /orders/:id) ==="
DETAIL_RES=$(curl -s -w "\nHTTP_STATUS:%{http_code}" -X GET "$BASE_URL/orders/$ORDER_ID" \
  -H "Authorization: Bearer $TOKEN")
STATUS=$(echo "$DETAIL_RES" | tail -n1 | cut -d: -f2)
BODY=$(echo "$DETAIL_RES" | sed '$d')
if [ "$STATUS" != "200" ]; then
  echo "Order detail failed: $DETAIL_RES"
  exit 1
fi
echo "Order detail OK (200, creator: $(echo "$BODY" | jq -r '.creator.name'))"

echo ""
echo "=== 5. Fund Escrow (POST /orders/:id/pay) ==="
PAY_RES=$(curl -s -w "\nHTTP_STATUS:%{http_code}" -X POST "$BASE_URL/orders/$ORDER_ID/pay" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json")
STATUS=$(echo "$PAY_RES" | tail -n1 | cut -d: -f2)
BODY=$(echo "$PAY_RES" | sed '$d')
if [ "$STATUS" != "200" ]; then
  echo "Escrow funding failed: $PAY_RES"
  exit 1
fi
CLIENT_TOKEN=$(echo "$BODY" | jq -r '.clientToken')
echo "Escrow funded OK (200, stub clientToken: $CLIENT_TOKEN)"

echo ""
echo "=== 6. Request Changes (POST /orders/:id/request-changes) ==="
CHANGES_RES=$(curl -s -w "\nHTTP_STATUS:%{http_code}" -X POST "$BASE_URL/orders/$ORDER_ID/request-changes" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"notes":"Please increase audio volume on the voiceover"}')
STATUS=$(echo "$CHANGES_RES" | tail -n1 | cut -d: -f2)
BODY=$(echo "$CHANGES_RES" | sed '$d')
if [ "$STATUS" != "200" ]; then
  echo "Request changes failed: $CHANGES_RES"
  exit 1
fi
echo "Request changes OK (200, status: $(echo "$BODY" | jq -r '.status'))"

echo ""
echo "=== 7. Approve Deliverables (POST /orders/:id/approve) ==="
APPROVE_RES=$(curl -s -w "\nHTTP_STATUS:%{http_code}" -X POST "$BASE_URL/orders/$ORDER_ID/approve" \
  -H "Authorization: Bearer $TOKEN")
STATUS=$(echo "$APPROVE_RES" | tail -n1 | cut -d: -f2)
BODY=$(echo "$APPROVE_RES" | sed '$d')
if [ "$STATUS" != "200" ]; then
  echo "Order approve failed: $APPROVE_RES"
  exit 1
fi
echo "Order approved and released OK (200, status: $(echo "$BODY" | jq -r '.status'))"

echo ""
echo "=== 8. Test Idempotency on Second Approve Call ==="
APPROVE_AGAIN=$(curl -s -w "\nHTTP_STATUS:%{http_code}" -X POST "$BASE_URL/orders/$ORDER_ID/approve" \
  -H "Authorization: Bearer $TOKEN")
STATUS=$(echo "$APPROVE_AGAIN" | tail -n1 | cut -d: -f2)
BODY=$(echo "$APPROVE_AGAIN" | sed '$d')
if [ "$STATUS" != "200" ]; then
  echo "Second approve failed: $APPROVE_AGAIN"
  exit 1
fi
echo "Idempotent approve OK (200, status: $(echo "$BODY" | jq -r '.status'))"

echo ""
echo "=== ALL ORDERS & ESCROW TESTS PASSED ==="
