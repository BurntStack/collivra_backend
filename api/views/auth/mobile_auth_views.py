import uuid
import secrets
import jwt
from datetime import datetime, timezone, timedelta
from django.conf import settings
from django.utils import timezone as django_tz
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny

from ...models import Profile, MobileVerificationOtp
from ...services import (
    normalize_mobile, generate_and_store_mobile_otp, verify_mobile_otp,
    is_dev_number, supabase_auth, PHONE_EMAIL_DOMAIN
)
from ...throttling import OtpSendRateThrottle
from .common import format_user_payload


class OtpSendView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [OtpSendRateThrottle]

    def get(self, request):
        return Response({
            'endpoint': 'POST /api/v1/auth/otp/send or POST /api/v1/auth/mobile/request-otp',
            'description': 'Request 6-digit verification code to mobile number',
            'body': {
                'mobile': 'string (required, e.g. +919876543210 or 9876543210)',
                'purpose': 'login | signup | verification (default: login)',
                'role': 'creator | brand (default: creator)'
            },
            'response': {'ok': True, 'resendInSeconds': 30}
        })

    def post(self, request):
        body = request.data or {}
        raw_mobile = body.get('mobile') or body.get('phone') or ''
        mobile = normalize_mobile(raw_mobile)
        if not mobile:
            return Response({
                'message': 'Please enter a valid Indian mobile number',
                'error': {'code': 'validation_error', 'message': 'Please enter a valid Indian mobile number'},
                'code': 'validation_error'
            }, status=status.HTTP_422_UNPROCESSABLE_ENTITY)

        purpose = (body.get('purpose') or 'login').strip().lower()
        role = (body.get('role') or 'creator').strip().lower()
        try:
            otp_code = generate_and_store_mobile_otp(mobile, purpose=purpose, role=role)
        except ValueError as e:
            if str(e).startswith('cooldown:'):
                seconds = str(e).split(':', 1)[1]
                return Response({
                    'ok': False,
                    'error': {'code': 'rate_limited', 'message': f'Please wait {seconds} seconds before requesting a new OTP.'},
                    'message': f'Please wait {seconds} seconds before requesting a new OTP.',
                    'code': 'rate_limited',
                    'resendInSeconds': int(seconds),
                }, status=status.HTTP_429_TOO_MANY_REQUESTS)
            raise

        resp = {
            'ok': True,
            'message': 'OTP sent successfully',
            'mobile': mobile,
            'resendInSeconds': 30
        }
        if getattr(settings, 'DEV_MODE', False) or getattr(settings, 'DEBUG', False) or is_dev_number(mobile):
            resp['devOtp'] = otp_code

        return Response(resp, status=status.HTTP_200_OK)


class OtpVerifyView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        return Response({
            'endpoint': 'POST /api/v1/auth/otp/verify or POST /api/v1/auth/mobile/verify-otp',
            'description': 'Verify 6-digit OTP code for mobile authentication',
            'body': {
                'mobile': 'string (required)',
                'code': 'string (6 digits, required)',
                'purpose': 'login | signup | verification (default: login)',
                'role': 'creator | brand (optional, default: creator)'
            },
            'response': {
                'ok': True,
                'token': 'jwt_session_token',
                'accessToken': 'jwt_session_token',
                'user': {'id': 'uuid', 'name': '...', 'mobile': '...'}
            }
        })

    def post(self, request):
        body = request.data or {}
        raw_mobile = body.get('mobile') or body.get('phone') or ''
        mobile = normalize_mobile(raw_mobile)
        code = str(body.get('code') or body.get('otp') or '').strip()
        purpose = (body.get('purpose') or 'login').strip().lower()
        role_pref = (body.get('role') or 'creator').strip().lower()

        if not mobile or not code:
            return Response({
                'message': 'Mobile and code are required',
                'error': {'code': 'validation_error', 'message': 'Mobile and code are required'},
                'code': 'validation_error'
            }, status=status.HTTP_422_UNPROCESSABLE_ENTITY)

        valid, reason = verify_mobile_otp(mobile, code, purpose=purpose)
        if not valid:
            return Response({
                'message': reason or 'Wrong or expired code. Please try again.',
                'error': {'code': 'invalid_otp', 'message': reason or 'Wrong or expired code. Please try again.'},
                'code': 'invalid_otp'
            }, status=status.HTTP_400_BAD_REQUEST)

        # 1. If user is currently authenticated via header: Link mobile to existing profile
        if request.user and request.user.is_authenticated:
            prof = Profile.objects.filter(id=request.user.id).first()
            if prof:
                prof.mobile = mobile
                prof.mobile_verified_at = django_tz.now()
                prof.save()
                return Response({
                    'ok': True,
                    'message': 'Mobile number verified and updated successfully',
                    'user': format_user_payload(prof)
                }, status=status.HTTP_200_OK)

        # 2. Check if a profile with this mobile number exists
        profile = Profile.objects.filter(mobile=mobile).first()
        if profile:
            profile.mobile_verified_at = django_tz.now()
            profile.failed_logins = 0
            profile.locked_until = None
            profile.save()

        # 3. Create signed verification token (15-minute TTL)
        payload = {
            'mobile': mobile,
            'purpose': 'signup_verification',
            'exp': datetime.now(timezone.utc) + timedelta(minutes=15),
            'iat': datetime.now(timezone.utc),
        }
        verification_token = jwt.encode(payload, settings.SECRET_KEY, algorithm='HS256')

        # If explicit signup mode and profile doesn't exist yet, return verificationToken
        if purpose == 'signup' and not profile:
            return Response({
                'ok': True,
                'verified': True,
                'mobile': mobile,
                'verificationToken': verification_token,
                'message': 'Mobile verified. You can now complete registration.'
            }, status=status.HTTP_200_OK)

        # 4. Sign-in or Auto-provision flow
        role = profile.role if profile else role_pref
        login_email = profile.email if (profile and profile.email) else f"{mobile[1:]}.{role}@{PHONE_EMAIL_DOMAIN}"

        if not profile:
            auto_pass = f"phone_auth_{secrets.token_hex(8)}"
            res = supabase_auth.create_user(
                email=login_email,
                password=auto_pass,
                user_metadata={'role': role, 'name': f"User {mobile[-4:]}", 'mobile': mobile}
            )
            u_id = None
            if res.status_code in [200, 201]:
                u_id = res.json().get('id')
            else:
                existing_u = supabase_auth.get_user_by_email(login_email)
                if existing_u:
                    u_id = existing_u.get('id')

            if u_id:
                profile, _ = Profile.objects.get_or_create(
                    id=u_id,
                    defaults={
                        'mobile': mobile,
                        'role': role,
                        'status': 'active',
                        'mobile_verified_at': django_tz.now(),
                        'failed_logins': 0,
                        'name': f"User {mobile[-4:]}",
                        'language': 'en',
                        'created_at': django_tz.now(),
                        'updated_at': django_tz.now(),
                    }
                )

        # Obtain Supabase Auth session token or fall back to signed JWT
        signin_res = supabase_auth.sign_in_with_password(login_email, body.get('password', 'creatorpass123'))
        access_token = verification_token
        refresh_token = verification_token
        if signin_res.status_code == 200:
            s_data = signin_res.json()
            access_token = s_data.get('access_token', access_token)
            refresh_token = s_data.get('refresh_token', refresh_token)

        user_obj = format_user_payload(profile, email=login_email)
        return Response({
            'ok': True,
            'token': access_token,
            'accessToken': access_token,
            'refreshToken': refresh_token,
            'verificationToken': verification_token,
            'user': user_obj,
            'role': profile.role,
            'status': profile.status,
        }, status=status.HTTP_200_OK)

