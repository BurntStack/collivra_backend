#!/usr/bin/env bash
set -e

BASE_URL="${COLLIVRA_BASE_URL:-https://eetmsobqxlbsvcoscjnb.supabase.co/functions/v1/api/v1}"
TEST_PASSWORD="${COLLIVRA_TEST_PASSWORD:-changedpass123}"
TEST_MOBILE="${COLLIVRA_CREATOR_MOBILE:-+919999999999}"

echo "=== 1. Log in as test creator ==="
LOGIN_RES=$(curl -s -X POST "$BASE_URL/auth/login" \
  -H "Content-Type: application/json" \
  -d "{\"identifier\":\"$TEST_MOBILE\",\"password\":\"$TEST_PASSWORD\"}")

ACCESS_TOKEN=$(echo "$LOGIN_RES" | jq -r '.accessToken // empty')
if [ -z "$ACCESS_TOKEN" ]; then
  echo "Login failed: $LOGIN_RES"
  exit 1
fi
echo "Logged in successfully as creator. Token acquired."

echo ""
echo "=== 2. File Check: Presign Validation ==="
echo "Test 2.1: 11 MB file (should return 413)"
CURL_413=$(curl -s -w "\nHTTP_STATUS:%{http_code}" -X POST "$BASE_URL/uploads/presign" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"purpose":"kyc-id","fileName":"large.pdf","contentType":"application/pdf","size":11534336}')
STATUS_413=$(echo "$CURL_413" | tail -n1 | cut -d: -f2)
if [ "$STATUS_413" != "413" ]; then
  echo "Expected 413 for oversized file, got $STATUS_413"
  exit 1
fi
echo "Presign oversized check passed (413)"

echo ""
echo "Test 2.2: .exe file (should return 415)"
CURL_415=$(curl -s -w "\nHTTP_STATUS:%{http_code}" -X POST "$BASE_URL/uploads/presign" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"purpose":"kyc-id","fileName":"virus.exe","contentType":"application/x-msdownload","size":1024}')
STATUS_415=$(echo "$CURL_415" | tail -n1 | cut -d: -f2)
if [ "$STATUS_415" != "415" ]; then
  echo "Expected 415 for invalid extension, got $STATUS_415"
  exit 1
fi
echo "Presign extension check passed (415)"

echo ""
echo "Test 2.3: Valid file presign (should return 200 with uploadUrl & fileKey)"
PRESIGN_RES=$(curl -s -X POST "$BASE_URL/uploads/presign" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"purpose":"kyc-id","fileName":"my_id.pdf","contentType":"application/pdf","size":500000}')
UPLOAD_URL=$(echo "$PRESIGN_RES" | jq -r '.uploadUrl // empty')
FILE_KEY=$(echo "$PRESIGN_RES" | jq -r '.fileKey // empty')
if [ -z "$UPLOAD_URL" ] || [ -z "$FILE_KEY" ]; then
  echo "Presign failed: $PRESIGN_RES"
  exit 1
fi
echo "Presign succeeded (fileKey: $FILE_KEY)"

echo ""
echo "Test 2.4: Uploading content using uploadUrl via PUT"
DUMMY_FILE="/tmp/collivra_dummy_id.pdf"
echo "Dummy PDF content for testing" > "$DUMMY_FILE"
UPLOAD_STATUS=$(curl -s -w "%{http_code}" -o /dev/null -X PUT "$UPLOAD_URL" \
  -H "Content-Type: application/pdf" \
  --data-binary "@$DUMMY_FILE")
rm -f "$DUMMY_FILE"
if [ "$UPLOAD_STATUS" != "200" ]; then
  echo "Upload to storage failed with status $UPLOAD_STATUS"
  exit 1
fi
echo "Upload PUT succeeded (HTTP $UPLOAD_STATUS)"

echo ""
echo "=== 3. Creator Profile Update ==="
PROFILE_RES=$(curl -s -w "\nHTTP_STATUS:%{http_code}" -X PUT "$BASE_URL/creator/onboarding/profile" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
    "category":"Tech & Gadgets",
    "languages":["English","Hindi"],
    "city":"Bengaluru",
    "topics":["AI","Smartphones","Code"]
  }')
PROF_STATUS=$(echo "$PROFILE_RES" | tail -n1 | cut -d: -f2)
if [ "$PROF_STATUS" != "200" ]; then
  echo "Profile update failed: $PROFILE_RES"
  exit 1
fi
echo "Profile update succeeded (HTTP $PROF_STATUS)"

echo ""
echo "=== 4. Social Account Connect (Stub Mode) ==="
CONNECT_RES=$(curl -s -X GET "$BASE_URL/creator/social/instagram/connect-url" \
  -H "Authorization: Bearer $ACCESS_TOKEN")
CONNECT_URL=$(echo "$CONNECT_RES" | jq -r '.url // empty')
if [ -z "$CONNECT_URL" ]; then
  echo "Social connect failed: $CONNECT_RES"
  exit 1
fi
echo "Connect URL acquired"

CALLBACK_RES=$(curl -s -w "\nHTTP_STATUS:%{http_code}" "$CONNECT_URL")
CB_STATUS=$(echo "$CALLBACK_RES" | tail -n1 | cut -d: -f2)
if [ "$CB_STATUS" != "200" ]; then
  echo "Social callback failed: $CALLBACK_RES"
  exit 1
fi
echo "Social callback succeeded (HTTP $CB_STATUS)"

echo ""
echo "Test 4.2: Callback failure simulation (simulate_error=too_small)"
CALLBACK_ERR=$(curl -s -w "\nHTTP_STATUS:%{http_code}" "$CONNECT_URL&simulate_error=too_small")
CB_ERR_STATUS=$(echo "$CALLBACK_ERR" | tail -n1 | cut -d: -f2)
if [ "$CB_ERR_STATUS" != "422" ]; then
  echo "Expected 422 for simulate_error=too_small, got $CB_ERR_STATUS"
  exit 1
fi
echo "Social callback error simulation succeeded (HTTP 422)"

echo ""
echo "=== 5. KYC ID Submission ==="
echo "Test 5.1: Non-existent / unauthorized fileKey (should return 404)"
ID_FAKE_RES=$(curl -s -w "\nHTTP_STATUS:%{http_code}" -X POST "$BASE_URL/creator/kyc/id" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"docType":"passport","fileKey":"non-existent-key"}')
ID_FAKE_STATUS=$(echo "$ID_FAKE_RES" | tail -n1 | cut -d: -f2)
if [ "$ID_FAKE_STATUS" != "404" ]; then
  echo "Expected 404 for missing fileKey, got $ID_FAKE_STATUS"
  exit 1
fi
echo "Missing fileKey check passed (HTTP 404)"

echo ""
echo "Test 5.2: Valid fileKey attached"
ID_RES=$(curl -s -w "\nHTTP_STATUS:%{http_code}" -X POST "$BASE_URL/creator/kyc/id" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d "{\"docType\":\"passport\",\"fileKey\":\"$FILE_KEY\"}")
ID_STATUS=$(echo "$ID_RES" | tail -n1 | cut -d: -f2)
if [ "$ID_STATUS" != "200" ]; then
  echo "KYC ID submission failed: $ID_RES"
  exit 1
fi
echo "KYC ID submission succeeded (HTTP $ID_STATUS)"

echo ""
echo "=== 6. KYC PAN Submission ==="
echo "Test 6.1: Invalid PAN format (should return 422)"
PAN_INV_RES=$(curl -s -w "\nHTTP_STATUS:%{http_code}" -X POST "$BASE_URL/creator/kyc/pan" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"pan":"INVALID123","nameOnPan":"Test Creator"}')
PAN_INV_STATUS=$(echo "$PAN_INV_RES" | tail -n1 | cut -d: -f2)
if [ "$PAN_INV_STATUS" != "422" ]; then
  echo "Expected 422 for invalid PAN, got $PAN_INV_STATUS"
  exit 1
fi
echo "Invalid PAN check passed (HTTP 422)"

echo ""
echo "Test 6.2: Valid PAN format"
PAN_RES=$(curl -s -w "\nHTTP_STATUS:%{http_code}" -X POST "$BASE_URL/creator/kyc/pan" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"pan":"ABCDE1234F","nameOnPan":"Test Creator"}')
PAN_STATUS=$(echo "$PAN_RES" | tail -n1 | cut -d: -f2)
if [ "$PAN_STATUS" != "200" ]; then
  echo "Valid PAN submission failed: $PAN_RES"
  exit 1
fi
echo "Valid PAN submission succeeded (HTTP $PAN_STATUS)"

echo ""
echo "=== 7. Bank Account Submission ==="
echo "Test 7.1: Invalid IFSC (should return 422)"
BANK_INV_RES=$(curl -s -w "\nHTTP_STATUS:%{http_code}" -X POST "$BASE_URL/creator/bank" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"accountNumber":"123456789012","ifsc":"HDFC123","holderName":"Test Creator"}')
BANK_INV_STATUS=$(echo "$BANK_INV_RES" | tail -n1 | cut -d: -f2)
if [ "$BANK_INV_STATUS" != "422" ]; then
  echo "Expected 422 for invalid IFSC, got $BANK_INV_STATUS"
  exit 1
fi
echo "Invalid IFSC check passed (HTTP 422)"

echo ""
echo "Test 7.2: Valid Bank Details"
BANK_RES=$(curl -s -w "\nHTTP_STATUS:%{http_code}" -X POST "$BASE_URL/creator/bank" \
  -H "Authorization: Bearer $ACCESS_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"accountNumber":"123456789012","ifsc":"HDFC0001234","holderName":"Test Creator"}')
BANK_STATUS=$(echo "$BANK_RES" | tail -n1 | cut -d: -f2)
if [ "$BANK_STATUS" != "200" ]; then
  echo "Bank submission failed: $BANK_RES"
  exit 1
fi
echo "Bank submission succeeded (HTTP $BANK_STATUS)"

echo ""
echo "=== 8. Submit Onboarding ==="
SUBMIT_RES=$(curl -s -w "\nHTTP_STATUS:%{http_code}" -X POST "$BASE_URL/creator/onboarding/submit" \
  -H "Authorization: Bearer $ACCESS_TOKEN")
SUBMIT_STATUS=$(echo "$SUBMIT_RES" | tail -n1 | cut -d: -f2)
if [ "$SUBMIT_STATUS" != "200" ]; then
  echo "Submit onboarding failed: $SUBMIT_RES"
  exit 1
fi
echo "Submit onboarding succeeded (HTTP $SUBMIT_STATUS)"

echo ""
echo "=== 9. Verification Status Check ==="
STATUS_RES=$(curl -s -w "\nHTTP_STATUS:%{http_code}" -X GET "$BASE_URL/creator/verification-status" \
  -H "Authorization: Bearer $ACCESS_TOKEN")
V_STATUS=$(echo "$STATUS_RES" | tail -n1 | cut -d: -f2)
if [ "$V_STATUS" != "200" ]; then
  echo "Verification status check failed: $STATUS_RES"
  exit 1
fi
echo "Verification status check succeeded (HTTP $V_STATUS)"

echo ""
echo "=== ALL ONBOARDING TESTS PASSED ==="
