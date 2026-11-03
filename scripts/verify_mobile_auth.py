import os
import sys

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

import django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from rest_framework.test import APIClient
from api.models import Profile, MobileVerificationOtp

def run():
    client = APIClient()
    test_mobile = "+919876543210"

    print("--- 1. Testing Request Mobile OTP ---")
    res1 = client.post('/api/v1/auth/mobile/request-otp', {'mobile': test_mobile, 'purpose': 'login'}, format='json')
    print("Status:", res1.status_code)
    print("Response:", res1.json())
    assert res1.status_code == 200
    otp_code = res1.json().get('devOtp')
    print(f"Captured devOtp: {otp_code}")

    print("\n--- 2. Testing Wrong OTP Code ---")
    res_wrong = client.post('/api/v1/auth/mobile/verify-otp', {'mobile': test_mobile, 'code': '000000_wrong', 'purpose': 'login'}, format='json')
    print("Status:", res_wrong.status_code)
    print("Response:", res_wrong.json())
    assert res_wrong.status_code == 400

    print("\n--- 3. Testing Valid OTP Code Verification ---")
    res_correct = client.post('/api/v1/auth/mobile/verify-otp', {'mobile': test_mobile, 'code': otp_code, 'purpose': 'login'}, format='json')
    print("Status:", res_correct.status_code)
    print("Response:", res_correct.json())
    assert res_correct.status_code == 200
    assert res_correct.json().get('ok') is True
    assert 'accessToken' in res_correct.json()

    print("\n--- 4. Testing Legacy / Alias Endpoints (/api/v1/auth/otp/send and /verify) ---")
    alias_mobile = "+919876543211"
    res_send = client.post('/api/v1/auth/otp/send', {'mobile': alias_mobile}, format='json')
    assert res_send.status_code == 200
    otp2 = res_send.json().get('devOtp')
    print(f"Alias OTP send OK: {otp2}")

    res_ver = client.post('/api/v1/auth/otp/verify', {'mobile': alias_mobile, 'code': otp2}, format='json')
    assert res_ver.status_code == 200
    print("Alias OTP verify OK:", res_ver.json().get('ok'))

    # Clean up test records
    Profile.objects.filter(mobile__in=[test_mobile, alias_mobile]).delete()
    MobileVerificationOtp.objects.filter(mobile__in=[test_mobile, alias_mobile]).delete()
    print("\n Cleaned up test records from database.")
    print(" ALL MOBILE AUTH TESTS PASSED PERFECTLY!")

if __name__ == '__main__':
    run()

def test_mobile_signup_complete():
    client = APIClient()
    import random
    rand_suffix = random.randint(1000, 9999)
    test_mobile = f"+91987654{rand_suffix}"
    Profile.objects.filter(mobile=test_mobile).delete()
    MobileVerificationOtp.objects.filter(mobile=test_mobile).delete()

    print("\n--- 5. Testing 3-Step Mobile Signup Flow ---")
    res1 = client.post('/api/v1/auth/mobile/request-otp', {'mobile': test_mobile, 'purpose': 'signup', 'role': 'creator'}, format='json')
    assert res1.status_code == 200
    otp = res1.json().get('devOtp')

    res2 = client.post('/api/v1/auth/mobile/verify-otp', {'mobile': test_mobile, 'code': otp, 'purpose': 'signup'}, format='json')
    assert res2.status_code == 200
    verification_token = res2.json().get('verificationToken')
    assert verification_token is not None
    print(f"Obtained verificationToken for {test_mobile}")

    res3 = client.post('/api/v1/auth/signup/complete', {
        'mobile': test_mobile,
        'verificationToken': verification_token,
        'name': 'Test Mobile Creator',
        'password': 'SecurePassword123!',
        'role': 'creator'
    }, format='json')
    print("Step 3 Status:", res3.status_code)
    print("Step 3 Response:", res3.json())
    assert res3.status_code == 201
    assert res3.json().get('user', {}).get('name') == 'Test Mobile Creator'

    # Cleanup
    Profile.objects.filter(mobile=test_mobile).delete()
    MobileVerificationOtp.objects.filter(mobile=test_mobile).delete()
    print(" 3-Step Mobile Signup Verified Successfully!")

test_mobile_signup_complete()
