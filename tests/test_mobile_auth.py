from django.test import TestCase
from rest_framework.test import APIClient
from django.db import connection
from api.models import Profile, MobileVerificationOtp

class MobileAuthTestCase(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        with connection.cursor() as cursor:
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS public.mobile_verification_otps (
                    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                    mobile TEXT NOT NULL,
                    otp_hash TEXT NOT NULL,
                    purpose TEXT NOT NULL DEFAULT 'login',
                    role TEXT NOT NULL DEFAULT 'creator',
                    expires_at TIMESTAMPTZ NOT NULL,
                    consumed_at TIMESTAMPTZ,
                    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
                );
            """)

    def test_mobile_otp_flow(self):
        client = APIClient()
        test_mobile = "+919876543210"

        # Step 1: Request Mobile OTP
        res = client.post('/api/v1/auth/mobile/request-otp', {'mobile': test_mobile, 'purpose': 'login'}, format='json')
        self.assertEqual(res.status_code, 200)
        self.assertTrue(res.data.get('ok'))
        otp_code = res.data.get('devOtp')
        self.assertIsNotNone(otp_code)

        # Step 2: Try verifying with wrong code
        wrong_res = client.post('/api/v1/auth/mobile/verify-otp', {'mobile': test_mobile, 'code': '999999', 'purpose': 'login'}, format='json')
        self.assertEqual(wrong_res.status_code, 400)
        self.assertEqual(wrong_res.data.get('code'), 'invalid_otp')

        # Step 3: Verify with correct code
        correct_res = client.post('/api/v1/auth/mobile/verify-otp', {'mobile': test_mobile, 'code': otp_code, 'purpose': 'login'}, format='json')
        self.assertEqual(correct_res.status_code, 200)
        self.assertTrue(correct_res.data.get('ok'))
        self.assertTrue('accessToken' in correct_res.data or 'token' in correct_res.data)

        # Step 4: Test alias routes (/auth/otp/send and /auth/otp/verify)
        res_alias = client.post('/api/v1/auth/otp/send', {'mobile': '+919876543211'}, format='json')
        self.assertEqual(res_alias.status_code, 200)
        otp2 = res_alias.data.get('devOtp')
        self.assertIsNotNone(otp2)

        ver_alias = client.post('/api/v1/auth/otp/verify', {'mobile': '+919876543211', 'code': otp2}, format='json')
        self.assertEqual(ver_alias.status_code, 200)
        self.assertTrue(ver_alias.data.get('ok'))

        # Clean up
        Profile.objects.filter(mobile__in=[test_mobile, '+919876543211']).delete()
        MobileVerificationOtp.objects.filter(mobile__in=[test_mobile, '+919876543211']).delete()
