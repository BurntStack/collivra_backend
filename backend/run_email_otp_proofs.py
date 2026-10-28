import os
import sys
import uuid
import json
import time
import requests
from datetime import datetime, timezone, timedelta

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'collivra_backend.settings')
import django
django.setup()

from django.db import connection
from django.conf import settings
from api.models import Profile, EmailVerificationOtp
from api.services import supabase_auth

BASE_URL = os.environ.get('COLLIVRA_BASE_URL', 'http://127.0.0.1:8000')

def get_account_count():
    with connection.cursor() as cur:
        cur.execute("SELECT count(*) FROM public.profiles;")
        return cur.fetchone()[0]

def run():
    print("=" * 80)
    print("COLLIVRA TWO-STEP EMAIL OTP SIGNUP VERIFICATION SUITE")
    print(f"Timestamp: {datetime.now(timezone.utc).isoformat()}")
    print("=" * 80)

    # 1. INITIAL ACCOUNT AUDIT
    initial_count = get_account_count()
    print(f"\n[ACCOUNT AUDIT BEFORE TESTS] Total profiles in database: {initial_count}")

    test_run_id = str(uuid.uuid4())[:8]
    test_brand_email = f"brand_otp_{test_run_id}@collivra.test"
    test_creator_email = f"creator_otp_{test_run_id}@collivra.test"
    test_pwd = f"SecurePass_{test_run_id}_!"
    created_user_ids = []

    try:
        # =====================================================================
        # TEST A: REQUEST OTP FOR NEW BRAND USER
        # =====================================================================
        print("\n--- TEST A: REQUEST OTP FOR NEW BRAND USER ---")
        req_res = requests.post(f"{BASE_URL}/auth/signup/request-otp", json={
            "email": test_brand_email,
            "role": "brand"
        })
        print(f"POST /auth/signup/request-otp -> Status: {req_res.status_code}")
        print(f"Response: {req_res.text}")
        assert req_res.status_code == 200, f"Expected 200, got {req_res.status_code}"
        req_data = req_res.json()
        assert req_data.get("message") == "OTP sent successfully"
        brand_otp = req_data.get("devOtp")
        print(f"Captured Brand OTP: {brand_otp}")
        assert brand_otp and len(brand_otp) == 6, f"Expected 6-digit OTP, got {brand_otp}"

        # Verify OTP record in database
        otp_rec = EmailVerificationOtp.objects.filter(email=test_brand_email, consumed_at__isnull=True).first()
        assert otp_rec is not None, "OTP record not found in database"
        print(f"Database OTP Record: ID={otp_rec.id}, Email={otp_rec.email}, Role={otp_rec.role}, ExpiresAt={otp_rec.expires_at}")
        assert otp_rec.role == "brand"
        assert otp_rec.expires_at > django.utils.timezone.now()

        # =====================================================================
        # TEST B: ATTEMPT REGISTRATION WITH INVALID OTP (ASSERT 400/422)
        # =====================================================================
        print("\n--- TEST B: ATTEMPT REGISTRATION WITH INVALID OTP ---")
        invalid_res = requests.post(f"{BASE_URL}/auth/signup/verify-and-register", json={
            "email": test_brand_email,
            "otp": "000000",
            "password": test_pwd,
            "name": f"Brand Corp {test_run_id}",
            "role": "brand",
            "companyName": f"Acme {test_run_id}"
        })
        print(f"POST /auth/signup/verify-and-register (Invalid OTP) -> Status: {invalid_res.status_code}")
        print(f"Response: {invalid_res.text}")
        assert invalid_res.status_code in [400, 422], f"Expected 400 or 422, got {invalid_res.status_code}"
        assert "invalid_otp" in invalid_res.text or "Invalid" in invalid_res.text

        # =====================================================================
        # TEST C: COMPLETE REGISTRATION WITH CORRECT OTP AND PASSWORD
        # =====================================================================
        print("\n--- TEST C: COMPLETE REGISTRATION WITH CORRECT OTP ---")
        reg_res = requests.post(f"{BASE_URL}/auth/signup/verify-and-register", json={
            "email": test_brand_email,
            "otp": brand_otp,
            "password": test_pwd,
            "name": f"Brand Corp {test_run_id}",
            "role": "brand",
            "companyName": f"Acme {test_run_id}"
        })
        print(f"POST /auth/signup/verify-and-register (Valid OTP) -> Status: {reg_res.status_code}")
        print(f"Response (Token truncated for security): {json.dumps({k: (v[:20] + '...' if k == 'token' else v) for k, v in reg_res.json().items()})}")
        assert reg_res.status_code == 201, f"Expected 201, got {reg_res.status_code}"
        reg_data = reg_res.json()
        brand_token = reg_data.get("token")
        brand_user = reg_data.get("user", {})
        brand_id = brand_user.get("id")
        created_user_ids.append(brand_id)
        assert brand_token is not None, "Missing token in response"
        assert brand_user.get("email") == test_brand_email
        assert brand_user.get("role") == "brand"
        assert brand_user.get("status") == "active"

        # Verify OTP consumed
        otp_rec_after = EmailVerificationOtp.objects.filter(id=otp_rec.id).first()
        print(f"OTP Record consumed_at: {otp_rec_after.consumed_at}")
        assert otp_rec_after.consumed_at is not None, "OTP was not marked as consumed"

        # =====================================================================
        # TEST D: VERIFY USER IN DATABASE (ROLE='brand', STATUS='active')
        # =====================================================================
        print("\n--- TEST D: VERIFY DATABASE RECORD FOR BRAND ---")
        brand_profile = Profile.objects.filter(id=brand_id).first()
        assert brand_profile is not None, "Brand profile does not exist in database"
        print(f"Profile: ID={brand_profile.id}, Email={brand_profile.email}, Role={brand_profile.role}, Status={brand_profile.status}")
        assert brand_profile.role == "brand", f"Expected role 'brand', got {brand_profile.role}"
        assert brand_profile.status == "active", f"Expected status 'active', got {brand_profile.status}"
        assert brand_profile.email_verified_at is not None, "email_verified_at should be set"

        # =====================================================================
        # TEST E: VERIFY IMMEDIATE LOGIN WITH NEWLY CREATED PASSWORD
        # =====================================================================
        print("\n--- TEST E: VERIFY IMMEDIATE LOGIN ---")
        login_res = requests.post(f"{BASE_URL}/auth/login", json={
            "email": test_brand_email,
            "password": test_pwd
        })
        print(f"POST /auth/login -> Status: {login_res.status_code}")
        assert login_res.status_code == 200, f"Expected 200, got {login_res.status_code}"
        login_data = login_res.json()
        assert login_data.get("token") is not None
        assert login_data.get("user", {}).get("email") == test_brand_email
        print(f"Login successful for {test_brand_email}!")

        # Verify authenticated endpoint /auth/me works
        me_res = requests.get(f"{BASE_URL}/auth/me", headers={"Authorization": f"Bearer {login_data.get('token')}"})
        print(f"GET /auth/me -> Status: {me_res.status_code}, User: {me_res.json().get('name')}")
        assert me_res.status_code == 200

        # =====================================================================
        # TEST F: DUPLICATE EMAIL PREVENTION (ASSERT 409 CONFLICT)
        # =====================================================================
        print("\n--- TEST F: PREVENT ALREADY REGISTERED EMAIL ---")
        dup_otp_res = requests.post(f"{BASE_URL}/auth/signup/request-otp", json={
            "email": test_brand_email,
            "role": "brand"
        })
        print(f"POST /auth/signup/request-otp (Existing Email) -> Status: {dup_otp_res.status_code}")
        print(f"Response: {dup_otp_res.text}")
        assert dup_otp_res.status_code == 409, f"Expected 409, got {dup_otp_res.status_code}"

        dup_reg_res = requests.post(f"{BASE_URL}/auth/signup/verify-and-register", json={
            "email": test_brand_email,
            "otp": "123456",
            "password": test_pwd,
            "name": "Duplicate Brand",
            "role": "brand"
        })
        print(f"POST /auth/signup/verify-and-register (Existing Email) -> Status: {dup_reg_res.status_code}")
        print(f"Response: {dup_reg_res.text}")
        assert dup_reg_res.status_code == 409, f"Expected 409, got {dup_reg_res.status_code}"

        # =====================================================================
        # TEST G: TWO-STEP SIGNUP FOR CREATOR (ROLE='creator', STATUS='unverified')
        # =====================================================================
        print("\n--- TEST G: TWO-STEP SIGNUP FOR CREATOR ---")
        c_req = requests.post(f"{BASE_URL}/auth/signup/request-otp", json={
            "email": test_creator_email,
            "role": "creator"
        })
        print(f"Creator OTP Request -> Status: {c_req.status_code}")
        assert c_req.status_code == 200
        creator_otp = c_req.json().get("devOtp")
        print(f"Captured Creator OTP: {creator_otp}")

        c_reg = requests.post(f"{BASE_URL}/auth/signup/verify-and-register", json={
            "email": test_creator_email,
            "otp": creator_otp,
            "password": test_pwd,
            "name": f"Creator User {test_run_id}",
            "role": "creator",
            "category": "Tech & Gadgets"
        })
        print(f"Creator Verify & Register -> Status: {c_reg.status_code}")
        assert c_reg.status_code == 201
        c_data = c_reg.json()
        creator_id = c_data.get("user", {}).get("id")
        created_user_ids.append(creator_id)

        # Verify Creator in DB: role='creator', status='unverified'
        creator_profile = Profile.objects.filter(id=creator_id).first()
        assert creator_profile is not None
        print(f"Creator DB Record: Role={creator_profile.role}, Status={creator_profile.status}")
        assert creator_profile.role == "creator", f"Expected role 'creator', got {creator_profile.role}"
        assert creator_profile.status == "unverified", f"Expected status 'unverified', got {creator_profile.status}"

        # Creator login works immediately
        c_login = requests.post(f"{BASE_URL}/auth/login", json={
            "email": test_creator_email,
            "password": test_pwd
        })
        print(f"Creator Login -> Status: {c_login.status_code}")
        assert c_login.status_code == 200

        print("\nAll Two-Step Email OTP assertions passed successfully!")

    finally:
        # =====================================================================
        # CLEANUP: DELETE ALL TEST ACCOUNTS AND OTPS
        # =====================================================================
        print("\n--- CLEANUP: REMOVING TEST ACCOUNTS ---")
        for uid in created_user_ids:
            if uid:
                try:
                    res = supabase_auth.delete_user(str(uid))
                    print(f"Deleted test user {uid}: status {res.status_code}")
                except Exception as e:
                    print(f"Error deleting user {uid}: {e}")

        # Remove test OTPs
        EmailVerificationOtp.objects.filter(email__in=[test_brand_email, test_creator_email]).delete()

        # AUDIT AFTER TESTS
        final_count = get_account_count()
        print(f"\n[ACCOUNT AUDIT AFTER TESTS] Total profiles in database: {final_count}")
        print(f"Before: {initial_count} | After: {final_count} | Delta: {final_count - initial_count}")
        assert final_count == initial_count, f"Account count mismatch! Started with {initial_count}, ended with {final_count}"
        print("ZERO test accounts left behind. Clean state confirmed!")

if __name__ == '__main__':
    run()
