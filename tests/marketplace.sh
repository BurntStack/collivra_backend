#!/usr/bin/env bash
set -e

BASE_URL="${COLLIVRA_BASE_URL:-https://eetmsobqxlbsvcoscjnb.supabase.co/functions/v1/api/v1}"
TEST_PASSWORD="${COLLIVRA_TEST_PASSWORD:-password123}"
TEST_CREATOR_PASSWORD="${COLLIVRA_CREATOR_PASSWORD:-changedpass123}"
TEST_MOBILE="${COLLIVRA_CREATOR_MOBILE:-+919999999999}"

echo "=== 1. Public Endpoints (No Token Required) ==="
echo "Test 1.1: GET /creators/suggestions"
SUGG_STATUS=$(curl -s -w "%{http_code}" -o /dev/null "$BASE_URL/creators/suggestions")
if [ "$SUGG_STATUS" != "200" ]; then
  echo "GET /creators/suggestions failed with $SUGG_STATUS"
  exit 1
fi
echo "Suggestions OK (200)"

echo "Test 1.2: GET /creators/filters"
FILTERS_STATUS=$(curl -s -w "%{http_code}" -o /dev/null "$BASE_URL/creators/filters")
if [ "$FILTERS_STATUS" != "200" ]; then
  echo "GET /creators/filters failed with $FILTERS_STATUS"
  exit 1
fi
echo "Filters OK (200)"

echo "Test 1.3: GET /creators"
CREATORS_STATUS=$(curl -s -w "%{http_code}" -o /dev/null "$BASE_URL/creators")
if [ "$CREATORS_STATUS" != "200" ]; then
  echo "GET /creators failed with $CREATORS_STATUS"
  exit 1
fi
echo "Creators listing OK (200)"

echo ""
echo "=== 2. Route Gating (B1 Verification: 401 Without Token) ==="
for ENDPOINT in "/creators/ananya-rao" "/creators/ananya-rao/packages" "/creators/ananya-rao/reviews" "/creators/ananya-rao/similar"; do
  STATUS=$(curl -s -w "%{http_code}" -o /dev/null "$BASE_URL$ENDPOINT")
  if [ "$STATUS" != "401" ]; then
    echo "Expected 401 for unauthenticated $ENDPOINT, got $STATUS"
    exit 1
  fi
  echo "Unauthenticated $ENDPOINT -> 401 OK"
done

STATUS=$(curl -s -w "%{http_code}" -o /dev/null -X POST "$BASE_URL/creators/ananya-rao/save")
if [ "$STATUS" != "401" ]; then
  echo "Expected 401 for unauthenticated POST /save, got $STATUS"
  exit 1
fi
echo "Unauthenticated POST /creators/ananya-rao/save -> 401 OK"

echo ""
echo "=== 3. Route Gating (B1 Verification: 403 With Creator Token) ==="
CREATOR_LOGIN=$(curl -s -X POST "$BASE_URL/auth/login" \
  -H "Content-Type: application/json" \
  -d "{\"identifier\":\"$TEST_MOBILE\",\"password\":\"$TEST_CREATOR_PASSWORD\"}")
CREATOR_TOKEN=$(echo "$CREATOR_LOGIN" | jq -r '.accessToken // empty')

if [ -n "$CREATOR_TOKEN" ]; then
  for ENDPOINT in "/creators/ananya-rao" "/creators/ananya-rao/packages" "/creators/ananya-rao/reviews" "/creators/ananya-rao/similar"; do
    STATUS=$(curl -s -w "%{http_code}" -o /dev/null "$BASE_URL$ENDPOINT" -H "Authorization: Bearer $CREATOR_TOKEN")
    if [ "$STATUS" != "403" ]; then
      echo "Expected 403 for creator token on $ENDPOINT, got $STATUS"
      exit 1
    fi
    echo "Creator token on $ENDPOINT -> 403 OK"
  done
else
  echo "Skipping creator 403 check (creator credentials not provided)"
fi

echo ""
echo "=== 4. Authenticated Brand Access ==="
RANDOM_INT=$((RANDOM % 90000 + 10000))
TEST_BRAND_EMAIL="brand_${RANDOM_INT}@acmebrand.com"
SIGNUP_RES=$(curl -s -X POST "$BASE_URL/auth/signup" \
  -H "Content-Type: application/json" \
  -d "{\"name\":\"Brand Tester\",\"email\":\"$TEST_BRAND_EMAIL\",\"password\":\"$TEST_PASSWORD\",\"companyName\":\"Acme Co\"}")
BRAND_TOKEN=$(echo "$SIGNUP_RES" | jq -r '.token // empty')

if [ -z "$BRAND_TOKEN" ]; then
  echo "Could not obtain brand token"
  exit 1
fi

echo "Test 4.1: GET /creators/ananya-rao with Brand Token"
PROFILE_STATUS=$(curl -s -w "%{http_code}" -o /dev/null "$BASE_URL/creators/ananya-rao" \
  -H "Authorization: Bearer $BRAND_TOKEN")
if [ "$PROFILE_STATUS" != "200" ]; then
  echo "Failed to get creator profile: $PROFILE_STATUS"
  exit 1
fi
echo "Creator profile OK (200)"

echo "Test 4.2: GET /creators/ananya-rao/packages with Brand Token"
PACKAGES_STATUS=$(curl -s -w "%{http_code}" -o /dev/null "$BASE_URL/creators/ananya-rao/packages" \
  -H "Authorization: Bearer $BRAND_TOKEN")
if [ "$PACKAGES_STATUS" != "200" ]; then
  echo "Failed to get creator packages: $PACKAGES_STATUS"
  exit 1
fi
echo "Creator packages OK (200)"

echo "Test 4.3: GET /creators/ananya-rao/reviews with Brand Token"
REVIEWS_STATUS=$(curl -s -w "%{http_code}" -o /dev/null "$BASE_URL/creators/ananya-rao/reviews" \
  -H "Authorization: Bearer $BRAND_TOKEN")
if [ "$REVIEWS_STATUS" != "200" ]; then
  echo "Failed to get creator reviews: $REVIEWS_STATUS"
  exit 1
fi
echo "Creator reviews OK (200)"

echo "Test 4.4: GET /creators/ananya-rao/similar with Brand Token"
SIMILAR_STATUS=$(curl -s -w "%{http_code}" -o /dev/null "$BASE_URL/creators/ananya-rao/similar" \
  -H "Authorization: Bearer $BRAND_TOKEN")
if [ "$SIMILAR_STATUS" != "200" ]; then
  echo "Failed to get similar creators: $SIMILAR_STATUS"
  exit 1
fi
echo "Similar creators OK (200)"

echo "Test 4.5: POST /creators/ananya-rao/save (Shortlist)"
SAVE_RES=$(curl -s -w "\nHTTP_STATUS:%{http_code}" -X POST "$BASE_URL/creators/ananya-rao/save" \
  -H "Authorization: Bearer $BRAND_TOKEN")
SAVE_STATUS=$(echo "$SAVE_RES" | tail -n1 | cut -d: -f2)
if [ "$SAVE_STATUS" != "204" ]; then
  echo "Failed to save creator: $SAVE_RES"
  exit 1
fi
echo "Shortlist save OK (204)"

echo "Test 4.6: DELETE /creators/ananya-rao/save (Remove Shortlist)"
UNSAVE_RES=$(curl -s -w "\nHTTP_STATUS:%{http_code}" -X DELETE "$BASE_URL/creators/ananya-rao/save" \
  -H "Authorization: Bearer $BRAND_TOKEN")
UNSAVE_STATUS=$(echo "$UNSAVE_RES" | tail -n1 | cut -d: -f2)
if [ "$UNSAVE_STATUS" != "204" ]; then
  echo "Failed to unsave creator: $UNSAVE_RES"
  exit 1
fi
echo "Shortlist remove OK (204)"

echo ""
echo "=== ALL MARKETPLACE & ROUTE GATING TESTS PASSED ==="
