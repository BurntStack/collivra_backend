#!/usr/bin/env bash
set -e

BASE_URL="${COLLIVRA_BASE_URL:-https://eetmsobqxlbsvcoscjnb.supabase.co/functions/v1/api/v1}"
TEST_PASSWORD="${COLLIVRA_TEST_PASSWORD:-password123}"

echo "=== 1. Brand Signup: POST /auth/signup ==="
RANDOM_INT=$((RANDOM % 90000 + 10000))
TEST_BRAND_EMAIL="brand_${RANDOM_INT}@acmebrand.com"
SIGNUP_RES=$(curl -s -w "\nHTTP_STATUS:%{http_code}" -X POST "$BASE_URL/auth/signup" \
  -H "Content-Type: application/json" \
  -d "{\"name\":\"Acme Tester\",\"email\":\"$TEST_BRAND_EMAIL\",\"password\":\"$TEST_PASSWORD\",\"companyName\":\"Acme Corp\"}")
HTTP_STATUS=$(echo "$SIGNUP_RES" | tail -n1 | cut -d: -f2)
BODY=$(echo "$SIGNUP_RES" | sed '$d')
if [ "$HTTP_STATUS" != "201" ]; then
  echo "Brand signup failed (HTTP $HTTP_STATUS): $BODY"
  exit 1
fi
echo "Brand signup succeeded (HTTP $HTTP_STATUS)"

TOKEN=$(echo "$BODY" | jq -r '.token // empty')
if [ -z "$TOKEN" ]; then
  echo "No token returned in signup response"
  exit 1
fi

echo ""
echo "=== 2. Brand Login: POST /auth/login ==="
LOGIN_RES=$(curl -s -w "\nHTTP_STATUS:%{http_code}" -X POST "$BASE_URL/auth/login" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"$TEST_BRAND_EMAIL\",\"password\":\"$TEST_PASSWORD\"}")
HTTP_STATUS=$(echo "$LOGIN_RES" | tail -n1 | cut -d: -f2)
BODY=$(echo "$LOGIN_RES" | sed '$d')
if [ "$HTTP_STATUS" != "200" ]; then
  echo "Brand login failed (HTTP $HTTP_STATUS): $BODY"
  exit 1
fi
LOGIN_TOKEN=$(echo "$BODY" | jq -r '.token // empty')
echo "Brand login succeeded (HTTP $HTTP_STATUS)"

echo ""
echo "=== 3. Current User: GET /auth/me ==="
ME_RES=$(curl -s -w "\nHTTP_STATUS:%{http_code}" -X GET "$BASE_URL/auth/me" \
  -H "Authorization: Bearer $LOGIN_TOKEN")
HTTP_STATUS=$(echo "$ME_RES" | tail -n1 | cut -d: -f2)
BODY=$(echo "$ME_RES" | sed '$d')
ROLE=$(echo "$BODY" | jq -r '.user.role // empty')
COMPANY=$(echo "$BODY" | jq -r '.user.companyName // empty')
if [ "$HTTP_STATUS" != "200" ] || [ "$ROLE" != "brand" ]; then
  echo "GET /auth/me failed (HTTP $HTTP_STATUS, role=$ROLE): $BODY"
  exit 1
fi
echo "GET /auth/me succeeded: user role=$ROLE, companyName=$COMPANY"

echo ""
echo "=== 4. Google OAuth: POST /auth/oauth/google (Invalid token test) ==="
OAUTH_GOOGLE_RES=$(curl -s -w "\nHTTP_STATUS:%{http_code}" -X POST "$BASE_URL/auth/oauth/google" \
  -H "Content-Type: application/json" \
  -d '{"idToken":"invalid_mock_token_12345"}')
HTTP_STATUS=$(echo "$OAUTH_GOOGLE_RES" | tail -n1 | cut -d: -f2)
BODY=$(echo "$OAUTH_GOOGLE_RES" | sed '$d')
if [ "$HTTP_STATUS" != "401" ]; then
  echo "Expected 401 for invalid Google idToken, got $HTTP_STATUS: $BODY"
  exit 1
fi
echo "Google OAuth returned expected 401 invalid_token for fake idToken"

echo ""
echo "=== 5. Apple OAuth: POST /auth/oauth/apple (Disabled 501 test) ==="
OAUTH_APPLE_RES=$(curl -s -w "\nHTTP_STATUS:%{http_code}" -X POST "$BASE_URL/auth/oauth/apple" \
  -H "Content-Type: application/json" \
  -d '{"idToken":"mock_apple_token"}')
HTTP_STATUS=$(echo "$OAUTH_APPLE_RES" | tail -n1 | cut -d: -f2)
BODY=$(echo "$OAUTH_APPLE_RES" | sed '$d')
if [ "$HTTP_STATUS" != "501" ]; then
  echo "Expected 501 for Apple OAuth when not enabled, got $HTTP_STATUS: $BODY"
  exit 1
fi
echo "Apple OAuth returned expected 501 not_implemented"

echo ""
echo "=== 6. Invalidate Session: POST /auth/logout ==="
LOGOUT_RES=$(curl -s -w "\nHTTP_STATUS:%{http_code}" -X POST "$BASE_URL/auth/logout" \
  -H "Authorization: Bearer $LOGIN_TOKEN")
HTTP_STATUS=$(echo "$LOGOUT_RES" | tail -n1 | cut -d: -f2)
if [ "$HTTP_STATUS" != "204" ]; then
  echo "Logout failed (HTTP $HTTP_STATUS)"
  exit 1
fi
echo "Logout succeeded (HTTP 204)"

echo ""
echo "=== ALL AUTH TESTS PASSED ==="
