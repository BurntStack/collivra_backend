#!/usr/bin/env bash
set -e

BASE_URL="${COLLIVRA_BASE_URL:-https://eetmsobqxlbsvcoscjnb.supabase.co/functions/v1/api/v1}"
TEST_PASSWORD="${COLLIVRA_TEST_PASSWORD:-password123}"

echo "=== 1. Log in or register brand user ==="
RANDOM_INT=$((RANDOM % 90000 + 10000))
TEST_BRAND_EMAIL="brand_${RANDOM_INT}@acmebrand.com"
SIGNUP_RES=$(curl -s -X POST "$BASE_URL/auth/signup" \
  -H "Content-Type: application/json" \
  -d "{\"name\":\"Cart Tester\",\"email\":\"$TEST_BRAND_EMAIL\",\"password\":\"$TEST_PASSWORD\",\"companyName\":\"Acme Co\"}")
TOKEN=$(echo "$SIGNUP_RES" | jq -r '.token // empty')

if [ -z "$TOKEN" ]; then
  echo "Brand authentication failed: $SIGNUP_RES"
  exit 1
fi
echo "Brand token acquired"

echo ""
echo "=== 2. Test GET /cart (Initially Empty) ==="
CART_EMPTY=$(curl -s -w "\nHTTP_STATUS:%{http_code}" -X GET "$BASE_URL/cart" \
  -H "Authorization: Bearer $TOKEN")
STATUS=$(echo "$CART_EMPTY" | tail -n1 | cut -d: -f2)
if [ "$STATUS" != "200" ]; then
  echo "GET /cart failed: $CART_EMPTY"
  exit 1
fi
echo "Cart empty check OK (200)"

echo ""
echo "=== 3. Test POST /cart/items (Add pkg_1 for ananya-rao) ==="
ADD_ITEM_1=$(curl -s -w "\nHTTP_STATUS:%{http_code}" -X POST "$BASE_URL/cart/items" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"creatorId":"ananya-rao","packageId":"pkg_1","quantity":1}')
STATUS=$(echo "$ADD_ITEM_1" | tail -n1 | cut -d: -f2)
if [ "$STATUS" != "200" ]; then
  echo "POST /cart/items failed: $ADD_ITEM_1"
  exit 1
fi
echo "Add item 1 OK (200)"

echo ""
echo "=== 4. Test POST /cart/items (Add pkg_2 for ananya-rao, qty 2) ==="
ADD_ITEM_2=$(curl -s -w "\nHTTP_STATUS:%{http_code}" -X POST "$BASE_URL/cart/items" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"creatorId":"ananya-rao","packageId":"pkg_2","quantity":2}')
STATUS=$(echo "$ADD_ITEM_2" | tail -n1 | cut -d: -f2)
BODY=$(echo "$ADD_ITEM_2" | sed '$d')
if [ "$STATUS" != "200" ]; then
  echo "POST /cart/items (item 2) failed: $ADD_ITEM_2"
  exit 1
fi
ITEM_ID=$(echo "$BODY" | jq -r '.items[-1].id // empty')
echo "Add item 2 OK (200, itemId: $ITEM_ID)"

echo ""
echo "=== 5. Test PATCH /cart/items/:itemId (Change quantity to 3) ==="
PATCH_RES=$(curl -s -w "\nHTTP_STATUS:%{http_code}" -X PATCH "$BASE_URL/cart/items/$ITEM_ID" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"quantity":3}')
STATUS=$(echo "$PATCH_RES" | tail -n1 | cut -d: -f2)
if [ "$STATUS" != "200" ]; then
  echo "PATCH /cart/items/:id failed: $PATCH_RES"
  exit 1
fi
echo "Patch item quantity OK (200)"

echo ""
echo "=== 6. Test DELETE /cart/items/:itemId (Remove item) ==="
DELETE_RES=$(curl -s -w "\nHTTP_STATUS:%{http_code}" -X DELETE "$BASE_URL/cart/items/$ITEM_ID" \
  -H "Authorization: Bearer $TOKEN")
STATUS=$(echo "$DELETE_RES" | tail -n1 | cut -d: -f2)
if [ "$STATUS" != "200" ]; then
  echo "DELETE /cart/items/:id failed: $DELETE_RES"
  exit 1
fi
echo "Delete cart item OK (200)"

echo ""
echo "=== 7. Test POST /offers (Send Custom Offer) ==="
OFFER_RES=$(curl -s -w "\nHTTP_STATUS:%{http_code}" -X POST "$BASE_URL/offers" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "creatorId":"ananya-rao",
    "deliverable":"2 Dedicated Reels + 1 IG Live Session for Diwali Launch",
    "budget":25000,
    "message":"We love your skincare content and would like an exclusive festive partnership.",
    "deadline":"2026-11-15"
  }')
STATUS=$(echo "$OFFER_RES" | tail -n1 | cut -d: -f2)
if [ "$STATUS" != "201" ]; then
  echo "POST /offers failed: $OFFER_RES"
  exit 1
fi
echo "Create custom offer OK (201)"

echo ""
echo "=== ALL CART & OFFERS TESTS PASSED ==="
