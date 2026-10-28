#!/usr/bin/env bash
set -e

BASE_URL="${COLLIVRA_BASE_URL:-http://127.0.0.1:8000/api/v1}"
TEST_PASSWORD="${COLLIVRA_TEST_PASSWORD:-creatorpass123}"
NEW_PASSWORD="${COLLIVRA_NEW_PASSWORD:-brandnewpass456}"
FINAL_PASSWORD="${COLLIVRA_FINAL_PASSWORD:-finalpass789}"
TEST_MOBILE="${COLLIVRA_CREATOR_TEST_MOBILE:-+919999999997}"

echo "=== Collivra Creator Auth Test Suite ==="
echo "Target Base URL: $BASE_URL"
echo "Test Mobile: $TEST_MOBILE"

# Cleanup any previous run for this test number
supabase db query --linked "delete from auth.users where raw_user_meta_data->>'mobile' = '$TEST_MOBILE'; delete from public.profiles where mobile = '$TEST_MOBILE';" >/dev/null 2>&1 || true

echo ""
echo "=== 1. Creator Signup: POST /auth/signup ==="
SIGNUP_RES=$(curl -s -w "\nHTTP_STATUS:%{http_code}" -X POST "$BASE_URL/auth/signup" \
  -H "Content-Type: application/json" \
  -d "{
    \"role\": \"creator\",
    \"name\": \"Automated Creator\",
    \"mobile\": \"$TEST_MOBILE\",
    \"password\": \"$TEST_PASSWORD\",
    \"termsVersion\": \"1.0\",
    \"acceptTerms\": true
  }")
HTTP_STATUS=$(echo "$SIGNUP_RES" | tail -n1 | cut -d: -f2)
BODY=$(echo "$SIGNUP_RES" | sed '$d')
if [ "$HTTP_STATUS" != "201" ]; then
  echo "Creator signup failed (HTTP $HTTP_STATUS): $BODY"
  exit 1
fi
OTP_SENT=$(echo "$BODY" | jq -r '.otpSent')
USER_ID=$(echo "$BODY" | jq -r '.userId')
if [ "$OTP_SENT" != "true" ] || [ -z "$USER_ID" ]; then
  echo "Expected otpSent=true and userId in response, got: $BODY"
  exit 1
fi
echo "Creator signup succeeded (HTTP 201, userId: $USER_ID, otpSent: true)"

echo ""
echo "=== 2. Creator OTP Verification: POST /auth/otp/verify ==="
VERIFY_RES=$(curl -s -w "\nHTTP_STATUS:%{http_code}" -X POST "$BASE_URL/auth/otp/verify" \
  -H "Content-Type: application/json" \
  -d "{
    \"mobile\": \"$TEST_MOBILE\",
    \"code\": \"123456\",
    \"purpose\": \"signup\"
  }")
HTTP_STATUS=$(echo "$VERIFY_RES" | tail -n1 | cut -d: -f2)
BODY=$(echo "$VERIFY_RES" | sed '$d')
if [ "$HTTP_STATUS" != "200" ]; then
  echo "OTP verification failed (HTTP $HTTP_STATUS): $BODY"
  exit 1
fi
ROLE=$(echo "$BODY" | jq -r '.role')
TOKEN=$(echo "$BODY" | jq -r '.accessToken')
REFRESH_TOKEN=$(echo "$BODY" | jq -r '.refreshToken')
if [ "$ROLE" != "creator" ] || [ -z "$TOKEN" ]; then
  echo "Expected role=creator and accessToken, got: $BODY"
  exit 1
fi
echo "OTP verified successfully (HTTP 200, role: $ROLE, mobile verified)"

echo ""
echo "=== 3. Creator Login: POST /auth/login ==="
LOGIN_RES=$(curl -s -w "\nHTTP_STATUS:%{http_code}" -X POST "$BASE_URL/auth/login" \
  -H "Content-Type: application/json" \
  -d "{
    \"identifier\": \"$TEST_MOBILE\",
    \"password\": \"$TEST_PASSWORD\"
  }")
HTTP_STATUS=$(echo "$LOGIN_RES" | tail -n1 | cut -d: -f2)
BODY=$(echo "$LOGIN_RES" | sed '$d')
if [ "$HTTP_STATUS" != "200" ]; then
  echo "Creator login failed (HTTP $HTTP_STATUS): $BODY"
  exit 1
fi
LOGIN_TOKEN=$(echo "$BODY" | jq -r '.accessToken')
if [ -z "$LOGIN_TOKEN" ]; then
  echo "Expected accessToken on login, got: $BODY"
  exit 1
fi
echo "Creator login succeeded (HTTP 200)"

echo ""
echo "=== 4. Creator Lockout: 5 Failed Login Attempts ==="
for i in {1..4}; do
  FAIL_RES=$(curl -s -w "\nHTTP_STATUS:%{http_code}" -X POST "$BASE_URL/auth/login" \
    -H "Content-Type: application/json" \
    -d "{\"identifier\": \"$TEST_MOBILE\", \"password\": \"wrongpassword$i\"}")
  FAIL_STATUS=$(echo "$FAIL_RES" | tail -n1 | cut -d: -f2)
  if [ "$FAIL_STATUS" != "401" ]; then
    echo "Expected 401 on failed attempt $i, got $FAIL_STATUS"
    exit 1
  fi
done
echo "4 consecutive failed logins returned 401 invalid_credentials"

# 5th attempt triggers lockout (423)
LOCK_RES=$(curl -s -w "\nHTTP_STATUS:%{http_code}" -X POST "$BASE_URL/auth/login" \
  -H "Content-Type: application/json" \
  -d "{\"identifier\": \"$TEST_MOBILE\", \"password\": \"wrongpassword5\"}")
LOCK_STATUS=$(echo "$LOCK_RES" | tail -n1 | cut -d: -f2)
LOCK_BODY=$(echo "$LOCK_RES" | sed '$d')
if [ "$LOCK_STATUS" != "423" ]; then
  echo "Expected 423 on 5th failed attempt, got $LOCK_STATUS: $LOCK_BODY"
  exit 1
fi
LOCK_CODE=$(echo "$LOCK_BODY" | jq -r '.code')
if [ "$LOCK_CODE" != "account_locked" ]; then
  echo "Expected code account_locked, got $LOCK_CODE"
  exit 1
fi
echo "5th failed login correctly triggered account lockout (HTTP 423, code: account_locked)"

# Attempting with correct password while locked still returns 423
LOCKED_VALID_RES=$(curl -s -w "\nHTTP_STATUS:%{http_code}" -X POST "$BASE_URL/auth/login" \
  -H "Content-Type: application/json" \
  -d "{\"identifier\": \"$TEST_MOBILE\", \"password\": \"$TEST_PASSWORD\"}")
LOCKED_VALID_STATUS=$(echo "$LOCKED_VALID_RES" | tail -n1 | cut -d: -f2)
if [ "$LOCKED_VALID_STATUS" != "423" ]; then
  echo "Expected 423 when trying to log in while locked, got $LOCKED_VALID_STATUS"
  exit 1
fi
echo "Login with correct password during lockout correctly blocked (HTTP 423)"

echo ""
echo "=== 5. Creator Forgot Password: POST /auth/forgot-password ==="
FORGOT_RES=$(curl -s -w "\nHTTP_STATUS:%{http_code}" -X POST "$BASE_URL/auth/forgot-password" \
  -H "Content-Type: application/json" \
  -d "{\"identifier\": \"$TEST_MOBILE\"}")
FORGOT_STATUS=$(echo "$FORGOT_RES" | tail -n1 | cut -d: -f2)
FORGOT_BODY=$(echo "$FORGOT_RES" | sed '$d')
if [ "$FORGOT_STATUS" != "200" ]; then
  echo "Forgot password failed (HTTP $FORGOT_STATUS): $FORGOT_BODY"
  exit 1
fi
FORGOT_OK=$(echo "$FORGOT_BODY" | jq -r '.ok')
if [ "$FORGOT_OK" != "true" ]; then
  echo "Expected ok=true, got: $FORGOT_BODY"
  exit 1
fi
echo "Forgot password request accepted (HTTP 200, ok: true)"

echo ""
echo "=== 6. Creator Reset Password: POST /auth/reset-password ==="
RESET_RES=$(curl -s -w "\nHTTP_STATUS:%{http_code}" -X POST "$BASE_URL/auth/reset-password" \
  -H "Content-Type: application/json" \
  -d "{
    \"mobile\": \"$TEST_MOBILE\",
    \"code\": \"123456\",
    \"newPassword\": \"$NEW_PASSWORD\"
  }")
RESET_STATUS=$(echo "$RESET_RES" | tail -n1 | cut -d: -f2)
RESET_BODY=$(echo "$RESET_RES" | sed '$d')
if [ "$RESET_STATUS" != "200" ]; then
  echo "Reset password failed (HTTP $RESET_STATUS): $RESET_BODY"
  exit 1
fi
RESET_OK=$(echo "$RESET_BODY" | jq -r '.ok')
if [ "$RESET_OK" != "true" ]; then
  echo "Expected ok=true, got: $RESET_BODY"
  exit 1
fi
echo "Password successfully reset and lockout cleared (HTTP 200, ok: true)"

echo ""
echo "=== 7. Login with New Reset Password ==="
NEW_LOGIN_RES=$(curl -s -w "\nHTTP_STATUS:%{http_code}" -X POST "$BASE_URL/auth/login" \
  -H "Content-Type: application/json" \
  -d "{
    \"identifier\": \"$TEST_MOBILE\",
    \"password\": \"$NEW_PASSWORD\"
  }")
NEW_LOGIN_STATUS=$(echo "$NEW_LOGIN_RES" | tail -n1 | cut -d: -f2)
NEW_LOGIN_BODY=$(echo "$NEW_LOGIN_RES" | sed '$d')
if [ "$NEW_LOGIN_STATUS" != "200" ]; then
  echo "Login with new password failed (HTTP $NEW_LOGIN_STATUS): $NEW_LOGIN_BODY"
  exit 1
fi
ACTIVE_TOKEN=$(echo "$NEW_LOGIN_BODY" | jq -r '.accessToken')
ACTIVE_REFRESH=$(echo "$NEW_LOGIN_BODY" | jq -r '.refreshToken')
echo "Login with new password succeeded (HTTP 200, session acquired)"

echo ""
echo "=== 8. Creator Change Password: POST /auth/change-password ==="
CHANGE_RES=$(curl -s -w "\nHTTP_STATUS:%{http_code}" -X POST "$BASE_URL/auth/change-password" \
  -H "Authorization: Bearer $ACTIVE_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{
    \"current\": \"$NEW_PASSWORD\",
    \"next\": \"$FINAL_PASSWORD\"
  }")
CHANGE_STATUS=$(echo "$CHANGE_RES" | tail -n1 | cut -d: -f2)
CHANGE_BODY=$(echo "$CHANGE_RES" | sed '$d')
if [ "$CHANGE_STATUS" != "200" ]; then
  echo "Change password failed (HTTP $CHANGE_STATUS): $CHANGE_BODY"
  exit 1
fi
CHANGE_OK=$(echo "$CHANGE_BODY" | jq -r '.ok')
if [ "$CHANGE_OK" != "true" ]; then
  echo "Expected ok=true, got: $CHANGE_BODY"
  exit 1
fi
echo "Password changed successfully (HTTP 200, ok: true)"

# Verify old password no longer works
OLD_TRY_RES=$(curl -s -w "\nHTTP_STATUS:%{http_code}" -X POST "$BASE_URL/auth/login" \
  -H "Content-Type: application/json" \
  -d "{
    \"identifier\": \"$TEST_MOBILE\",
    \"password\": \"$NEW_PASSWORD\"
  }")
OLD_TRY_STATUS=$(echo "$OLD_TRY_RES" | tail -n1 | cut -d: -f2)
if [ "$OLD_TRY_STATUS" != "401" ]; then
  echo "Expected 401 when using superseded password, got $OLD_TRY_STATUS"
  exit 1
fi
echo "Superseded password rejected (HTTP 401)"

# Verify final password works
FINAL_LOGIN_RES=$(curl -s -w "\nHTTP_STATUS:%{http_code}" -X POST "$BASE_URL/auth/login" \
  -H "Content-Type: application/json" \
  -d "{
    \"identifier\": \"$TEST_MOBILE\",
    \"password\": \"$FINAL_PASSWORD\"
  }")
FINAL_LOGIN_STATUS=$(echo "$FINAL_LOGIN_RES" | tail -n1 | cut -d: -f2)
FINAL_LOGIN_BODY=$(echo "$FINAL_LOGIN_RES" | sed '$d')
if [ "$FINAL_LOGIN_STATUS" != "200" ]; then
  echo "Login with final password failed (HTTP $FINAL_LOGIN_STATUS): $FINAL_LOGIN_BODY"
  exit 1
fi
FINAL_REFRESH=$(echo "$FINAL_LOGIN_BODY" | jq -r '.refreshToken')
echo "Login with final password succeeded (HTTP 200)"

echo ""
echo "=== 9. Creator Logout: POST /auth/logout ==="
LOGOUT_RES=$(curl -s -w "\nHTTP_STATUS:%{http_code}" -X POST "$BASE_URL/auth/logout" \
  -H "Content-Type: application/json" \
  -d "{\"refreshToken\": \"$FINAL_REFRESH\"}")
LOGOUT_STATUS=$(echo "$LOGOUT_RES" | tail -n1 | cut -d: -f2)
if [ "$LOGOUT_STATUS" != "204" ]; then
  echo "Logout failed (HTTP $LOGOUT_STATUS)"
  exit 1
fi
echo "Creator logout succeeded (HTTP 204)"

echo ""
echo "=== 10. Teardown / Cleanup ==="
supabase db query --linked "delete from auth.users where raw_user_meta_data->>'mobile' = '$TEST_MOBILE'; delete from public.profiles where mobile = '$TEST_MOBILE';" >/dev/null 2>&1 || true
echo "Test creator cleaned up successfully"

echo ""
echo "ALL CREATOR AUTH TESTS PASSED."
