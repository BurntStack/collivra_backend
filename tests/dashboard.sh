#!/usr/bin/env bash
set -e

BASE_URL="${COLLIVRA_BASE_URL:-https://eetmsobqxlbsvcoscjnb.supabase.co/functions/v1/api/v1}"
TEST_PASSWORD="${COLLIVRA_TEST_PASSWORD:-password123}"

echo "=== 1. Log in / register brand user ==="
RANDOM_INT=$((RANDOM % 90000 + 10000))
TEST_BRAND_EMAIL="brand_${RANDOM_INT}@acmebrand.com"
SIGNUP_RES=$(curl -s -X POST "$BASE_URL/auth/signup" \
  -H "Content-Type: application/json" \
  -d "{\"name\":\"Dashboard Brand\",\"email\":\"$TEST_BRAND_EMAIL\",\"password\":\"$TEST_PASSWORD\",\"companyName\":\"Acme Co\"}")
TOKEN=$(echo "$SIGNUP_RES" | jq -r '.token // empty')

if [ -z "$TOKEN" ]; then
  echo "Brand authentication failed: $SIGNUP_RES"
  exit 1
fi
echo "Brand token acquired"

echo ""
echo "=== 2. GET /dashboard/summary ==="
SUMMARY_RES=$(curl -s -w "\nHTTP_STATUS:%{http_code}" -X GET "$BASE_URL/dashboard/summary" \
  -H "Authorization: Bearer $TOKEN")
STATUS=$(echo "$SUMMARY_RES" | tail -n1 | cut -d: -f2)
BODY=$(echo "$SUMMARY_RES" | sed '$d')
if [ "$STATUS" != "200" ]; then
  echo "GET /dashboard/summary failed: $SUMMARY_RES"
  exit 1
fi
GREETING=$(echo "$BODY" | jq -r '.greetingName')
echo "Summary OK (200, greeting: $GREETING)"

echo ""
echo "=== 3. PATCH /dashboard/todos/:id ==="
TODO_RES=$(curl -s -w "\nHTTP_STATUS:%{http_code}" -X PATCH "$BASE_URL/dashboard/todos/hire-creator" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"done": true}')
STATUS=$(echo "$TODO_RES" | tail -n1 | cut -d: -f2)
BODY=$(echo "$TODO_RES" | sed '$d')
if [ "$STATUS" != "200" ] || [ "$(echo "$BODY" | jq -r '.done')" != "true" ]; then
  echo "PATCH todo failed: $TODO_RES"
  exit 1
fi
echo "Todo check OK (200)"

echo ""
echo "=== 4. Custom Lists: POST /lists ==="
LIST_RES=$(curl -s -w "\nHTTP_STATUS:%{http_code}" -X POST "$BASE_URL/lists" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"name": "Diwali Beauty Campaign"}')
STATUS=$(echo "$LIST_RES" | tail -n1 | cut -d: -f2)
BODY=$(echo "$LIST_RES" | sed '$d')
if [ "$STATUS" != "201" ]; then
  echo "POST /lists failed: $LIST_RES"
  exit 1
fi
LIST_ID=$(echo "$BODY" | jq -r '.id')
echo "Create list OK (201, id: $LIST_ID)"

echo ""
echo "=== 5. Custom Lists: GET /lists ==="
GET_LISTS=$(curl -s -w "\nHTTP_STATUS:%{http_code}" -X GET "$BASE_URL/lists" \
  -H "Authorization: Bearer $TOKEN")
STATUS=$(echo "$GET_LISTS" | tail -n1 | cut -d: -f2)
if [ "$STATUS" != "200" ]; then
  echo "GET /lists failed: $GET_LISTS"
  exit 1
fi
echo "Get lists OK (200)"

echo ""
echo "=== 6. Custom Lists: Add Creator (POST /lists/:id/creators) ==="
ADD_CREATOR=$(curl -s -w "\nHTTP_STATUS:%{http_code}" -X POST "$BASE_URL/lists/$LIST_ID/creators" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"creatorId": "ananya-rao"}')
STATUS=$(echo "$ADD_CREATOR" | tail -n1 | cut -d: -f2)
if [ "$STATUS" != "201" ] && [ "$STATUS" != "200" ]; then
  echo "Add creator to list failed: $ADD_CREATOR"
  exit 1
fi
echo "Add creator to list OK ($STATUS)"

echo ""
echo "=== 7. Custom Lists: Remove Creator (DELETE /lists/:id/creators/:creatorId) ==="
DEL_CREATOR=$(curl -s -w "\nHTTP_STATUS:%{http_code}" -X DELETE "$BASE_URL/lists/$LIST_ID/creators/ananya-rao" \
  -H "Authorization: Bearer $TOKEN")
STATUS=$(echo "$DEL_CREATOR" | tail -n1 | cut -d: -f2)
if [ "$STATUS" != "204" ] && [ "$STATUS" != "200" ]; then
  echo "Remove creator from list failed: $DEL_CREATOR"
  exit 1
fi
echo "Remove creator from list OK ($STATUS)"

echo ""
echo "=== 8. Deliverables / Content Library: GET /deliverables ==="
DELIV_RES=$(curl -s -w "\nHTTP_STATUS:%{http_code}" -X GET "$BASE_URL/deliverables" \
  -H "Authorization: Bearer $TOKEN")
STATUS=$(echo "$DELIV_RES" | tail -n1 | cut -d: -f2)
BODY=$(echo "$DELIV_RES" | sed '$d')
if [ "$STATUS" != "200" ]; then
  echo "GET /deliverables failed: $DELIV_RES"
  exit 1
fi
COUNT=$(echo "$BODY" | jq 'length')
echo "GET /deliverables OK (200, count: $COUNT)"

echo ""
echo "=== ALL DASHBOARD & CONTENT LIBRARY TESTS PASSED ==="
