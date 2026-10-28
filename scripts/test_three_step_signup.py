import os
import sys
import uuid
import django

# Setup Django environment
ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT_DIR not in sys.path:
    sys.path.insert(0, ROOT_DIR)
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from django.test import Client
from api.models import Profile, EmailVerificationOtp
from api.services import supabase_auth

def run_tests():
    print("=" * 80)
    print("RUNNING 3-STEP SIGNUP VERIFICATION SUITE (/api/v1/auth/signup/...)")
    print("=" * 80)

    client = Client()
    initial_profiles_count = Profile.objects.count()
    print(f"[AUDIT BEFORE] Profiles in database: {initial_profiles_count}")

    test_id = uuid.uuid4().hex[:8]
    brand_email = f"brand_3step_{test_id}@collivra.test"
    creator_email = f"creator_3step_{test_id}@collivra.test"
    created_user_ids = []

    try:
        # -------------------------------------------------------------
        # STEP 1: POST /api/v1/auth/signup/email
        # -------------------------------------------------------------
        print("\n--- STEP 1: POST /api/v1/auth/signup/email (Brand) ---")
        res = client.post('/api/v1/auth/signup/email', {'email': brand_email, 'role': 'brand'}, content_type='application/json')
        print(f"Status: {res.status_code}")
        print(f"Body: {res.json()}")
        assert res.status_code == 200, f"Expected 200, got {res.status_code}"
        assert res.json().get('ok') is True, "Expected ok: True"
        brand_otp = res.json().get('devOtp')
        assert brand_otp, "Expected devOtp in response"
        print(f"Captured devOtp: {brand_otp}")

        # -------------------------------------------------------------
        # STEP 2a: POST /api/v1/auth/signup/verify-email with INVALID code
        # -------------------------------------------------------------
        print("\n--- STEP 2a: POST /api/v1/auth/signup/verify-email (Invalid Code) ---")
        res_invalid = client.post('/api/v1/auth/signup/verify-email', {'email': brand_email, 'code': '000000'}, content_type='application/json')
        print(f"Status: {res_invalid.status_code}")
        print(f"Body: {res_invalid.json()}")
        assert res_invalid.status_code == 400, f"Expected 400, got {res_invalid.status_code}"

        # -------------------------------------------------------------
        # STEP 2b: POST /api/v1/auth/signup/verify-email with VALID code
        # -------------------------------------------------------------
        print("\n--- STEP 2b: POST /api/v1/auth/signup/verify-email (Valid Code) ---")
        res_valid = client.post('/api/v1/auth/signup/verify-email', {'email': brand_email, 'code': brand_otp}, content_type='application/json')
        print(f"Status: {res_valid.status_code}")
        print(f"Body: {res_valid.json()}")
        assert res_valid.status_code == 200, f"Expected 200, got {res_valid.status_code}"
        verification_token = res_valid.json().get('verificationToken')
        assert verification_token, "Expected verificationToken in response"
        print(f"Verification Token acquired: {verification_token[:20]}...")

        # -------------------------------------------------------------
        # STEP 3a: POST /api/v1/auth/signup/complete with INVALID token
        # -------------------------------------------------------------
        print("\n--- STEP 3a: POST /api/v1/auth/signup/complete (Invalid Token) ---")
        res_bad_token = client.post('/api/v1/auth/signup/complete', {
            'email': brand_email,
            'verificationToken': 'invalid.token.here',
            'name': 'Acme Corp',
            'password': 'Password123!',
            'role': 'brand'
        }, content_type='application/json')
        print(f"Status: {res_bad_token.status_code}")
        assert res_bad_token.status_code == 400, f"Expected 400, got {res_bad_token.status_code}"

        # -------------------------------------------------------------
        # STEP 3b: POST /api/v1/auth/signup/complete with VALID token
        # -------------------------------------------------------------
        print("\n--- STEP 3b: POST /api/v1/auth/signup/complete (Valid Brand) ---")
        res_complete = client.post('/api/v1/auth/signup/complete', {
            'email': brand_email,
            'verificationToken': verification_token,
            'name': f'Brand {test_id}',
            'password': 'Password123!',
            'role': 'brand',
            'companyName': f'Acme {test_id}'
        }, content_type='application/json')
        print(f"Status: {res_complete.status_code}")
        print(f"Body: {res_complete.json()}")
        assert res_complete.status_code == 201, f"Expected 201, got {res_complete.status_code}"
        brand_data = res_complete.json()
        assert brand_data.get('token'), "Expected session token"
        assert brand_data.get('user', {}).get('role') == 'brand', "Expected role brand"
        assert brand_data.get('user', {}).get('status') == 'active', "Expected status active"
        brand_user_id = brand_data.get('user', {}).get('id')
        created_user_ids.append(brand_user_id)

        # -------------------------------------------------------------
        # STEP 4: Test Immediate Login for Brand
        # -------------------------------------------------------------
        print("\n--- STEP 4: POST /api/v1/auth/login ---")
        res_login = client.post('/api/v1/auth/login', {
            'email': brand_email,
            'password': 'Password123!'
        }, content_type='application/json')
        print(f"Status: {res_login.status_code}")
        assert res_login.status_code == 200, f"Expected 200, got {res_login.status_code}"

        # -------------------------------------------------------------
        # STEP 5: Duplicate Prevention on Step 1
        # -------------------------------------------------------------
        print("\n--- STEP 5: Duplicate Prevention (Conflict 409) ---")
        res_dup = client.post('/api/v1/auth/signup/email', {'email': brand_email}, content_type='application/json')
        print(f"Status: {res_dup.status_code}")
        assert res_dup.status_code == 409, f"Expected 409, got {res_dup.status_code}"

        # -------------------------------------------------------------
        # STEP 6: Full 3-Step Flow for Creator
        # -------------------------------------------------------------
        print("\n--- STEP 6: 3-Step Flow for Creator ---")
        res_c1 = client.post('/api/v1/auth/signup/email', {'email': creator_email, 'role': 'creator'}, content_type='application/json')
        assert res_c1.status_code == 200
        creator_otp = res_c1.json().get('devOtp')

        res_c2 = client.post('/api/v1/auth/signup/verify-email', {'email': creator_email, 'code': creator_otp}, content_type='application/json')
        assert res_c2.status_code == 200
        creator_token = res_c2.json().get('verificationToken')

        res_c3 = client.post('/api/v1/auth/signup/complete', {
            'email': creator_email,
            'verificationToken': creator_token,
            'name': f'Creator {test_id}',
            'password': 'Password123!',
            'role': 'creator'
        }, content_type='application/json')
        print(f"Status: {res_c3.status_code}")
        print(f"Body: {res_c3.json()}")
        assert res_c3.status_code == 201, f"Expected 201, got {res_c3.status_code}"
        creator_data = res_c3.json()
        assert creator_data.get('user', {}).get('role') == 'creator', "Expected role creator"
        assert creator_data.get('user', {}).get('status') == 'unverified', "Expected status unverified"
        creator_user_id = creator_data.get('user', {}).get('id')
        created_user_ids.append(creator_user_id)

        print("\nAll 3-Step Signup Tests Passed Successfully!")

    finally:
        print("\n--- CLEANUP: REMOVING CREATED TEST ACCOUNTS ---")
        for uid in created_user_ids:
            if uid:
                del_res = supabase_auth.delete_user(uid)
                print(f"Deleted Supabase & Profile test user {uid}: status {del_res.status_code}")
        EmailVerificationOtp.objects.filter(email__in=[brand_email, creator_email]).delete()

        final_profiles_count = Profile.objects.count()
        print(f"[AUDIT AFTER] Profiles in database: {final_profiles_count}")
        print(f"Initial: {initial_profiles_count} | Final: {final_profiles_count} | Delta: {final_profiles_count - initial_profiles_count}")
        assert initial_profiles_count == final_profiles_count, f"Account leak detected! Initial: {initial_profiles_count}, Final: {final_profiles_count}"
        print("ZERO account residue confirmed.")

if __name__ == '__main__':
    run_tests()
