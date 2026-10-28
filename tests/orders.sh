#!/usr/bin/env bash
set -e

BASE_URL="${COLLIVRA_BASE_URL:-http://127.0.0.1:8000/api/v1}"
AUTH_ADMIN_URL="${COLLIVRA_AUTH_ADMIN_URL:-https://eetmsobqxlbsvcoscjnb.supabase.co/auth/v1/admin/users}"
TEST_PASSWORD="${COLLIVRA_TEST_PASSWORD:-password123}"

# Read service key from environment or project api-keys without ever printing it
SERVICE_KEY="${SUPABASE_SERVICE_ROLE_KEY:-$COLLIVRA_SERVICE_KEY}"
if [ -z "$SERVICE_KEY" ]; then
  SERVICE_KEY=$(supabase projects api-keys --project-ref eetmsobqxlbsvcoscjnb | jq -r '.keys[] | select(.id == "service_role") | .api_key')
fi

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
echo "=== 2. Create Order (POST /orders) -> starts in awaiting_payment ==="
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
if [ "$ORDER_STATUS" != "awaiting_payment" ]; then
  echo "Expected status awaiting_payment, got $ORDER_STATUS"
  exit 1
fi
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
echo "=== 5. Fund Escrow (POST /orders/:id/pay) -> status remains awaiting_payment ==="
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
echo "Escrow funding intent OK (200, stub clientToken: $CLIENT_TOKEN)"

echo ""
echo "=== 6. Confirm Stub Payment (POST /orders/:id/confirm-payment-stub) -> transitions to in_escrow ==="
CONFIRM_RES=$(curl -s -w "\nHTTP_STATUS:%{http_code}" -X POST "$BASE_URL/orders/$ORDER_ID/confirm-payment-stub" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json")
STATUS=$(echo "$CONFIRM_RES" | tail -n1 | cut -d: -f2)
BODY=$(echo "$CONFIRM_RES" | sed '$d')
if [ "$STATUS" != "200" ]; then
  echo "Stub payment confirmation failed: $CONFIRM_RES"
  exit 1
fi
STATUS_AFTER_CONFIRM=$(echo "$BODY" | jq -r '.status')
if [ "$STATUS_AFTER_CONFIRM" != "in_escrow" ]; then
  echo "Expected status in_escrow, got $STATUS_AFTER_CONFIRM"
  exit 1
fi
echo "Payment confirmed OK (200, status: $STATUS_AFTER_CONFIRM)"

echo ""
echo "=== 7. Create Admin and Submit Draft (POST /orders/:id/submit-draft) -> transitions to draft_submitted ==="
ADMIN_EMAIL="admin_order_${RANDOM_INT}@collivra.internal"
ADMIN_PASSWORD="AdminSecretPass123!"

# Provision admin through Auth Admin API
curl -s -X POST "$AUTH_ADMIN_URL" \
  -H "apikey: $SERVICE_KEY" \
  -H "Authorization: Bearer $SERVICE_KEY" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"$ADMIN_EMAIL\",\"password\":\"$ADMIN_PASSWORD\",\"email_confirm\":true,\"app_metadata\":{\"role\":\"admin\"},\"user_metadata\":{\"name\":\"Admin Order Tester\"}}" > /dev/null

ADMIN_LOGIN=$(curl -s -X POST "$BASE_URL/auth/login" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"$ADMIN_EMAIL\",\"password\":\"$ADMIN_PASSWORD\"}")
ADMIN_TOKEN=$(echo "$ADMIN_LOGIN" | jq -r '.token // empty')

if [ -z "$ADMIN_TOKEN" ]; then
  echo "Admin login failed: $ADMIN_LOGIN"
  exit 1
fi
echo "Admin token acquired"

SUBMIT_RES=$(curl -s -w "\nHTTP_STATUS:%{http_code}" -X POST "$BASE_URL/orders/$ORDER_ID/submit-draft" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"draftUrl":"https://assets.collivra.com/drafts/demo.mp4","note":"Review first cut"}')
STATUS=$(echo "$SUBMIT_RES" | tail -n1 | cut -d: -f2)
BODY=$(echo "$SUBMIT_RES" | sed '$d')
if [ "$STATUS" != "200" ]; then
  echo "Submit draft failed: $SUBMIT_RES"
  exit 1
fi
STATUS_AFTER_DRAFT=$(echo "$BODY" | jq -r '.status')
if [ "$STATUS_AFTER_DRAFT" != "draft_submitted" ]; then
  echo "Expected status draft_submitted, got $STATUS_AFTER_DRAFT"
  exit 1
fi
echo "Draft submitted OK (200, status: $STATUS_AFTER_DRAFT)"

echo ""
echo "=== 8. Request Changes (POST /orders/:id/request-changes) -> transitions to changes_requested ==="
CHANGES_RES=$(curl -s -w "\nHTTP_STATUS:%{http_code}" -X POST "$BASE_URL/orders/$ORDER_ID/request-changes" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"note":"Please increase audio volume on the voiceover"}')
STATUS=$(echo "$CHANGES_RES" | tail -n1 | cut -d: -f2)
BODY=$(echo "$CHANGES_RES" | sed '$d')
if [ "$STATUS" != "200" ]; then
  echo "Request changes failed: $CHANGES_RES"
  exit 1
fi
REV_COUNT=$(echo "$BODY" | jq -r '.revisionCount')
echo "Request changes OK (200, status: $(echo "$BODY" | jq -r '.status'), revisionCount: $REV_COUNT)"

echo ""
echo "=== 9. Re-submit Draft by Admin -> transitions back to draft_submitted ==="
RESUBMIT_RES=$(curl -s -w "\nHTTP_STATUS:%{http_code}" -X POST "$BASE_URL/orders/$ORDER_ID/submit-draft" \
  -H "Authorization: Bearer $ADMIN_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"draftUrl":"https://assets.collivra.com/drafts/demo_v2.mp4","note":"Updated audio volume"}')
STATUS=$(echo "$RESUBMIT_RES" | tail -n1 | cut -d: -f2)
BODY=$(echo "$RESUBMIT_RES" | sed '$d')
if [ "$STATUS" != "200" ]; then
  echo "Re-submit draft failed: $RESUBMIT_RES"
  exit 1
fi
echo "Draft re-submitted OK (200, status: $(echo "$BODY" | jq -r '.status'))"

echo ""
echo "=== 10. Approve Deliverables (POST /orders/:id/approve) -> transitions to released ==="
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
echo "=== 11. Test Idempotency on Second Approve Call ==="
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
