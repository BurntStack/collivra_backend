import re
import json
import jwt
import secrets
import uuid
from datetime import datetime, timezone, timedelta
from django.conf import settings
from django.http import HttpResponse
from django.utils import timezone as django_tz
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny

from ...models import Profile, OtpSendLog
from ...services import (
    normalize_mobile, send_otp, check_otp, supabase_auth,
    generate_and_store_email_otp, verify_email_otp,
    PHONE_EMAIL_DOMAIN
)
from ...throttling import SignupRateThrottle, EmailOtpRateThrottle
from .common import format_user_payload


class RequestEmailOtpView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [EmailOtpRateThrottle]

    def post(self, request):
        body = request.data or {}
        email = (body.get('email') or '').strip().lower()
        role = (body.get('role') or 'brand').strip().lower()

        if not email or not re.match(r'^[^\s@]+@[^\s@]+\.[^\s@]+$', email):
            return Response({
                'error': {'code': 'validation_error', 'message': 'Invalid email address'},
                'message': 'Invalid email address',
                'code': 'validation_error',
            }, status=status.HTTP_422_UNPROCESSABLE_ENTITY)

        if role not in ['brand', 'creator']:
            return Response({
                'error': {'code': 'validation_error', 'message': 'Role must be brand or creator'},
                'message': 'Role must be brand or creator',
                'code': 'validation_error',
            }, status=status.HTTP_422_UNPROCESSABLE_ENTITY)

        # Prevent requesting OTP if email is already registered
        if Profile.objects.filter(email=email).exists():
            return Response({
                'error': {'code': 'email_taken', 'message': 'This email is already registered'},
                'message': 'This email is already registered',
                'code': 'email_taken',
            }, status=status.HTTP_409_CONFLICT)

        otp_code = generate_and_store_email_otp(email, role)

        resp = {'message': 'OTP sent successfully'}
        if getattr(settings, 'DEBUG', False) or getattr(settings, 'DEV_MODE', False) or email.endswith('.test'):
            resp['devOtp'] = otp_code

        return Response(resp, status=status.HTTP_200_OK)

    def get(self, request):
        return Response({
            'endpoint': 'POST /auth/signup/request-otp',
            'description': 'Generates a secure 6-digit OTP, stores it with 10-minute TTL, and triggers email delivery.',
            'fields': {
                'email': 'string (required)',
                'role': 'brand | creator (default: brand)'
            },
            'example': {
                'email': 'you@example.com',
                'role': 'brand'
            }
        })


class VerifyAndRegisterView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        return Response({
            'endpoint': 'POST /auth/signup/verify-and-register',
            'description': 'Verifies the 6-digit OTP code against the stored record and creates user account in Supabase Auth.',
            'fields': {
                'email': 'string (required)',
                'otp': 'string (6 digits, required)',
                'password': 'string (min 8 chars, required)',
                'name': 'string (min 2 chars, required)',
                'role': 'brand | creator (default: brand)',
                'companyName': 'string (required for brand)'
            },
            'example': {
                'email': 'you@example.com',
                'otp': '123456',
                'password': 'MyStrongPassword123!',
                'name': 'Srikar',
                'role': 'brand',
                'companyName': 'Burntstack'
            }
        })

    def post(self, request):
        body = request.data or {}
        email = (body.get('email') or '').strip().lower()
        otp = str(body.get('otp') or '').strip()
        password = body.get('password') or ''
        name = (body.get('name') or '').strip()
        role = (body.get('role') or 'brand').strip().lower()
        company_name = (body.get('companyName') or '').strip()

        fields = {}
        if not email or not re.match(r'^[^\s@]+@[^\s@]+\.[^\s@]+$', email):
            fields['email'] = 'Invalid email address'
        if not otp:
            fields['otp'] = 'OTP is required'
        if len(name) < 2:
            fields['name'] = 'Name must be at least 2 characters'
        if len(password) < 8:
            fields['password'] = 'Password must be at least 8 characters'
        if role not in ['brand', 'creator']:
            fields['role'] = 'Role must be brand or creator'
        if role == 'brand' and company_name and len(company_name) < 2:
            fields['companyName'] = 'Company name must be at least 2 characters'

        if fields:
            return Response({
                'error': {'code': 'validation_error', 'message': next(iter(fields.values()))},
                'message': next(iter(fields.values())),
                'code': 'validation_error',
                'fields': fields,
            }, status=status.HTTP_422_UNPROCESSABLE_ENTITY)

        # Prevent account creation if email is already registered
        if Profile.objects.filter(email=email).exists():
            return Response({
                'error': {'code': 'email_taken', 'message': 'This email is already registered'},
                'message': 'This email is already registered',
                'code': 'email_taken',
            }, status=status.HTTP_409_CONFLICT)

        # Verify OTP code
        valid, reason = verify_email_otp(email, otp)
        if not valid:
            return Response({
                'error': {'code': 'invalid_otp', 'message': reason or 'Invalid OTP code'},
                'message': reason or 'Invalid OTP code',
                'code': 'invalid_otp',
            }, status=status.HTTP_400_BAD_REQUEST)

        # Create user via Supabase Auth admin API
        user_metadata = {'role': role, 'name': name}
        if company_name:
            user_metadata['company_name'] = company_name

        res = supabase_auth.create_user(
            email=email,
            password=password,
            user_metadata=user_metadata
        )

        if res.status_code not in (200, 201):
            err_data = res.json() if res.content else {}
            msg = err_data.get('msg') or err_data.get('error_description') or err_data.get('message') or 'Signup failed'
            if 'already registered' in msg.lower() or 'already exists' in msg.lower():
                return Response({
                    'error': {'code': 'email_taken', 'message': 'This email is already registered'},
                    'message': 'This email is already registered',
                    'code': 'email_taken',
                }, status=status.HTTP_409_CONFLICT)
            return Response({
                'error': {'code': 'auth_error', 'message': msg},
                'message': msg,
                'code': 'auth_error',
            }, status=status.HTTP_400_BAD_REQUEST)

        user_data = res.json()
        user_id = user_data.get('id')

        # Sign in with password to get real access token
        signin_res = supabase_auth.sign_in_with_password(email, password)
        signin_data = signin_res.json() if signin_res.content else {}
        token = signin_data.get('access_token')

        # Update profile status ('active' for brands, 'unverified' for creators)
        target_status = 'active' if role == 'brand' else 'unverified'
        profile = Profile.objects.filter(id=user_id).first()
        if profile:
            profile.role = role
            profile.status = target_status
            profile.email_verified_at = django_tz.now()
            if company_name and role == 'brand':
                profile.company_name = company_name
            profile.save()

        return Response({
            'token': token,
            'user': {
                'id': user_id,
                'name': name,
                'email': email,
                'companyName': company_name if role == 'brand' else None,
                'role': role,
                'status': target_status,
            }
        }, status=status.HTTP_201_CREATED)


class SignupEmailView(APIView):
    """
    Step 1 of 3-step signup flow:
    POST /api/v1/auth/signup/email
    Request Body: {"email": "..."}
    Response: {"ok": true}
    """
    permission_classes = [AllowAny]
    throttle_classes = [EmailOtpRateThrottle]

    def get(self, request):
        return Response({
            'endpoint': 'POST /api/v1/auth/signup/email',
            'description': 'Step 1: Request 6-digit verification code to email',
            'body': {'email': 'string (required)', 'role': 'brand | creator (default: brand)'},
            'response': {'ok': True}
        })

    def post(self, request):
        body = request.data or {}
        email = (body.get('email') or '').strip().lower()
        role = (body.get('role') or 'brand').strip().lower()

        if not email or not re.match(r'^[^\s@]+@[^\s@]+\.[^\s@]+$', email):
            return Response({
                'error': {'code': 'validation_error', 'message': 'Invalid email address'},
                'message': 'Invalid email address',
                'code': 'validation_error',
            }, status=status.HTTP_422_UNPROCESSABLE_ENTITY)

        if role not in ['brand', 'creator']:
            role = 'brand'

        # Prevent requesting OTP if email is already registered
        if Profile.objects.filter(email=email).exists():
            return Response({
                'error': {'code': 'email_taken', 'message': 'This email is already registered'},
                'message': 'This email is already registered',
                'code': 'email_taken',
            }, status=status.HTTP_409_CONFLICT)

        otp_code = generate_and_store_email_otp(email, role)

        resp = {'ok': True}
        if getattr(settings, 'DEBUG', False) or getattr(settings, 'DEV_MODE', False) or email.endswith('.test'):
            resp['devOtp'] = otp_code

        return Response(resp, status=status.HTTP_200_OK)


class SignupVerifyEmailView(APIView):
    """
    Step 2 of 3-step signup flow:
    POST /api/v1/auth/signup/verify-email
    Request Body: {"email": "...", "code": "..."}
    Response: {"verificationToken": "..."}
    """
    permission_classes = [AllowAny]

    def get(self, request):
        return Response({
            'endpoint': 'POST /api/v1/auth/signup/verify-email',
            'description': 'Step 2: Verify OTP code and receive verificationToken',
            'body': {'email': 'string (required)', 'code': 'string (6 digits, required)'},
            'response': {'verificationToken': 'jwt_token_string'}
        })

    def post(self, request):
        body = request.data or {}
        email = (body.get('email') or '').strip().lower()
        code = str(body.get('code') or body.get('otp') or '').strip()

        if not email or not code:
            return Response({
                'error': {'code': 'invalid_otp', 'message': 'Email and code are required'},
                'message': 'Email and code are required',
                'code': 'invalid_otp',
            }, status=status.HTTP_400_BAD_REQUEST)

        valid, reason = verify_email_otp(email, code)
        if not valid:
            return Response({
                'error': {'code': 'invalid_otp', 'message': reason or 'Invalid OTP code'},
                'message': reason or 'Invalid OTP code',
                'code': 'invalid_otp',
            }, status=status.HTTP_400_BAD_REQUEST)

        # Generate short-lived signed verificationToken (15 minutes)
        payload = {
            'email': email,
            'purpose': 'signup_verification',
            'exp': datetime.now(timezone.utc) + timedelta(minutes=15),
            'iat': datetime.now(timezone.utc),
        }
        verification_token = jwt.encode(payload, settings.SECRET_KEY, algorithm='HS256')

        return Response({'verificationToken': verification_token}, status=status.HTTP_200_OK)


class SignupCompleteView(APIView):
    """
    Step 3 of 3-step signup flow:
    POST /api/v1/auth/signup/complete
    Request Body: {"email": "...", "verificationToken": "...", "password": "...", "name": "...", "role": "..."}
    Response: {"token": "...", "user": { ... }}
    """
    permission_classes = [AllowAny]

    def get(self, request):
        return Response({
            'endpoint': 'POST /api/v1/auth/signup/complete',
            'description': 'Step 3: Complete signup with verified token, password, and profile metadata',
            'body': {
                'email': 'string (optional if mobile)',
                'mobile': 'string (optional if email)',
                'verificationToken': 'string (required)',
                'password': 'string (min 8 chars, required)',
                'name': 'string (min 2 chars, required)',
                'role': 'brand | creator (default: brand)',
                'companyName': 'string (optional for brand)'
            },
            'response': {'token': 'jwt_session_token', 'user': {'id': 'uuid', 'name': '...', 'email': '...', 'role': '...', 'status': 'active | unverified'}}
        })

    def post(self, request):
        body = request.data or {}
        email = (body.get('email') or '').strip().lower()
        raw_mobile = body.get('mobile') or body.get('phone') or ''
        mobile = normalize_mobile(raw_mobile) if raw_mobile else None
        verification_token = body.get('verificationToken') or ''
        password = body.get('password') or ''
        name = (body.get('name') or '').strip()
        role = (body.get('role') or 'brand').strip().lower()
        company_name = (body.get('companyName') or '').strip()

        # Validate verificationToken
        if not verification_token:
            return Response({
                'error': {'code': 'invalid_token', 'message': 'Verification token is required'},
                'message': 'Verification token is required',
                'code': 'invalid_token',
            }, status=status.HTTP_400_BAD_REQUEST)

        try:
            token_payload = jwt.decode(verification_token, settings.SECRET_KEY, algorithms=['HS256'])
            token_email = (token_payload.get('email') or '').strip().lower()
            token_mobile = token_payload.get('mobile')

            is_valid_match = False
            if email and token_email == email:
                is_valid_match = True
            elif mobile and token_mobile == mobile:
                is_valid_match = True

            if not is_valid_match or token_payload.get('purpose') != 'signup_verification':
                return Response({
                    'error': {'code': 'invalid_token', 'message': 'Invalid verification token'},
                    'message': 'Invalid verification token',
                    'code': 'invalid_token',
                }, status=status.HTTP_400_BAD_REQUEST)
        except jwt.ExpiredSignatureError:
            return Response({
                'error': {'code': 'token_expired', 'message': 'Verification token has expired. Please verify again.'},
                'message': 'Verification token has expired. Please verify again.',
                'code': 'token_expired',
            }, status=status.HTTP_400_BAD_REQUEST)
        except Exception:
            return Response({
                'error': {'code': 'invalid_token', 'message': 'Invalid verification token'},
                'message': 'Invalid verification token',
                'code': 'invalid_token',
            }, status=status.HTTP_400_BAD_REQUEST)

        fields = {}
        if not email and not mobile:
            fields['email'] = 'Email or mobile number is required'
        elif email and not re.match(r'^[^\s@]+@[^\s@]+\.[^\s@]+$', email):
            fields['email'] = 'Invalid email address'
        if len(name) < 2:
            fields['name'] = 'Name must be at least 2 characters'
        if len(password) < 8:
            fields['password'] = 'Password must be at least 8 characters'
        if role not in ['brand', 'creator']:
            fields['role'] = 'Role must be brand or creator'
        if role == 'brand' and company_name and len(company_name) < 2:
            fields['companyName'] = 'Company name must be at least 2 characters'

        if fields:
            return Response({
                'error': {'code': 'validation_error', 'message': next(iter(fields.values()))},
                'message': next(iter(fields.values())),
                'code': 'validation_error',
                'fields': fields,
            }, status=status.HTTP_422_UNPROCESSABLE_ENTITY)

        # Check existing profile
        if email and Profile.objects.filter(email=email).exists():
            return Response({
                'error': {'code': 'email_taken', 'message': 'This email is already registered'},
                'message': 'This email is already registered',
                'code': 'email_taken',
            }, status=status.HTTP_409_CONFLICT)
        if mobile and Profile.objects.filter(mobile=mobile).exists():
            return Response({
                'error': {'code': 'mobile_taken', 'message': 'This mobile number is already registered'},
                'message': 'This mobile number is already registered',
                'code': 'mobile_taken',
            }, status=status.HTTP_409_CONFLICT)

        user_metadata = {
            'name': name,
            'role': role,
            'company_name': company_name if role == 'brand' else None,
        }
        if mobile:
            user_metadata['mobile'] = mobile

        auth_email = email or f"{mobile[1:]}.{role}@{PHONE_EMAIL_DOMAIN}"

        # Create user via Supabase Admin API
        res = supabase_auth.create_user(
            email=auth_email,
            password=password,
            user_metadata=user_metadata
        )

        if res.status_code not in (200, 201):
            err_data = res.json() if res.content else {}
            msg = err_data.get('msg') or err_data.get('error_description') or err_data.get('message') or 'Signup failed'
            if 'already registered' in msg.lower() or 'already exists' in msg.lower():
                return Response({
                    'error': {'code': 'email_taken', 'message': 'This email is already registered'},
                    'message': 'This email is already registered',
                    'code': 'email_taken',
                }, status=status.HTTP_409_CONFLICT)
            return Response({
                'error': {'code': 'auth_error', 'message': msg},
                'message': msg,
                'code': 'auth_error',
            }, status=status.HTTP_400_BAD_REQUEST)

        user_data = res.json()
        user_id = user_data.get('id')

        # Sign in with password to get real access token
        signin_res = supabase_auth.sign_in_with_password(auth_email, password)
        signin_data = signin_res.json() if signin_res.content else {}
        token = signin_data.get('access_token')

        # Update profile status ('active' for brands, 'unverified' for creators)
        target_status = 'active' if role == 'brand' else 'unverified'
        profile = Profile.objects.filter(id=user_id).first()
        if profile:
            profile.role = role
            profile.status = target_status
            if email:
                profile.email = email
                profile.email_verified_at = django_tz.now()
            if mobile:
                profile.mobile = mobile
                profile.mobile_verified_at = django_tz.now()
            if company_name and role == 'brand':
                profile.company_name = company_name
            profile.save()

        return Response({
            'token': token,
            'user': {
                'id': user_id,
                'name': name,
                'email': email or auth_email,
                'mobile': mobile,
                'companyName': company_name if role == 'brand' else None,
                'role': role,
                'status': target_status,
            }
        }, status=status.HTTP_201_CREATED)


class SignupView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [SignupRateThrottle]

    def post(self, request):
        body = request.data or {}

        role = body.get('role')
        if not role:
            role = 'brand' if body.get('companyName') else ('creator' if body.get('mobile') else 'brand')

        # Email-based signup flow (brand or creator)
        if body.get('email') and not body.get('mobile'):
            name = (body.get('name') or '').strip()
            email = (body.get('email') or '').strip().lower()
            password = body.get('password') or ''
            company_name = (body.get('companyName') or '').strip()

            fields = {}
            if len(name) < 2:
                fields['name'] = 'Name must be at least 2 characters'
            if not re.match(r'^[^\s@]+@[^\s@]+\.[^\s@]+$', email):
                fields['email'] = 'Invalid email address'
            if len(password) < 8:
                fields['password'] = 'Password must be at least 8 characters'
            if role == 'brand' and len(company_name) < 2:
                fields['companyName'] = 'Company name must be at least 2 characters'

            if fields:
                return Response({
                    'error': {'code': 'validation_error', 'message': next(iter(fields.values()))},
                    'message': next(iter(fields.values())),
                    'code': 'validation_error',
                    'fields': fields,
                }, status=status.HTTP_422_UNPROCESSABLE_ENTITY)

            # Check existing profile
            if Profile.objects.filter(email=email).exists():
                return Response({
                    'error': {'code': 'email_taken', 'message': 'This email is already registered'},
                    'message': 'This email is already registered',
                    'code': 'email_taken',
                }, status=status.HTTP_409_CONFLICT)

            # Create in Supabase Auth
            user_metadata = {'role': role, 'name': name}
            if company_name:
                user_metadata['company_name'] = company_name

            res = supabase_auth.create_user(
                email=email,
                password=password,
                user_metadata=user_metadata
            )
            if res.status_code != 200 and res.status_code != 201:
                err_data = res.json() if res.content else {}
                if 'already registered' in str(err_data).lower() or err_data.get('code') == 'email_exists':
                    return Response({
                        'error': {'code': 'email_taken', 'message': 'This email is already registered'},
                        'message': 'This email is already registered',
                        'code': 'email_taken',
                    }, status=status.HTTP_409_CONFLICT)
                return Response({'message': 'Registration failed', 'code': 'registration_failed'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            created_user = res.json()
            user_id = created_user.get('id')

            # Sign in to get access token
            signin_res = supabase_auth.sign_in_with_password(email=email, password=password)
            if signin_res.status_code != 200:
                return Response({'message': 'Auto-login failed', 'code': 'auth_error'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

            signin_data = signin_res.json()
            token = signin_data.get('access_token')

            profile = Profile.objects.filter(id=user_id).first()
            if profile and company_name:
                profile.company_name = company_name
                profile.save()

            return Response({
                'token': token,
                'user': {
                    'id': user_id,
                    'name': name,
                    'email': email,
                    'companyName': company_name if role == 'brand' else None,
                    'role': role,
                    'status': profile.status if profile else ('active' if role == 'brand' else 'unverified'),
                }
            }, status=status.HTTP_201_CREATED)

        # Creator / Mobile signup flow
        name = (body.get('name') or '').strip()
        raw_mobile = body.get('mobile') or ''
        mobile = normalize_mobile(raw_mobile)
        password = body.get('password') or ''
        role = body.get('role', 'creator')
        terms_version = body.get('termsVersion', '1.0')
        accept_terms = body.get('acceptTerms')

        fields = {}
        if not mobile:
            fields['mobile'] = 'Please enter a valid Indian mobile number'
        if len(name) < 2:
            fields['name'] = 'Name must be at least 2 characters'
        if len(password) < 8:
            fields['password'] = 'Password must be at least 8 characters'
        if accept_terms is not True:
            fields['acceptTerms'] = 'You must accept the terms to continue'

        if fields:
            return Response({'message': 'Please check the highlighted fields', 'code': 'validation_error', 'fields': fields}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)

        # Check existing profile
        if Profile.objects.filter(mobile=mobile, role=role).exists():
            return Response({'message': 'This mobile number is already registered', 'code': 'mobile_taken'}, status=status.HTTP_409_CONFLICT)

        login_email = f"{mobile[1:]}.{role}@{PHONE_EMAIL_DOMAIN}"
        res = supabase_auth.create_user(
            email=login_email,
            password=password,
            user_metadata={'role': role, 'name': name, 'mobile': mobile, 'terms_version': terms_version}
        )
        if res.status_code not in [200, 201]:
            err_data = res.json() if res.content else {}
            if 'already registered' in str(err_data).lower():
                return Response({'message': 'This mobile number is already registered', 'code': 'mobile_taken'}, status=status.HTTP_409_CONFLICT)
            return Response({'message': 'Registration failed', 'code': 'registration_failed'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        created = res.json()
        user_id = created.get('id')

        # Send OTP
        send_otp(mobile)

        return Response({
            'userId': user_id,
            'otpSent': True,
            'resendInSeconds': 30,
        }, status=status.HTTP_201_CREATED)


class EmailOtpTestUIView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        html = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Collivra - Auth & OTP Verification Interactive Test</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif; }
    body { background: #0b0f19; color: #f1f5f9; padding: 32px 16px; min-height: 100vh; display: flex; flex-direction: column; align-items: center; }
    .container { max-width: 680px; width: 100%; }
    .header { text-align: center; margin-bottom: 24px; }
    .header h1 { font-size: 24px; color: #38bdf8; font-weight: 700; margin-bottom: 6px; }
    .header p { color: #94a3b8; font-size: 14px; }
    .nav-tabs { display: flex; gap: 8px; margin-bottom: 20px; background: #131c2e; padding: 4px; border-radius: 8px; border: 1px solid #1e293b; }
    .tab-btn { flex: 1; padding: 10px 16px; border: none; background: transparent; color: #94a3b8; font-size: 13px; font-weight: 600; border-radius: 6px; cursor: pointer; transition: all 0.2s; }
    .tab-btn.active { background: #0284c7; color: white; }
    .tab-content { display: none; }
    .tab-content.active { display: block; }
    .card { background: #131c2e; border: 1px solid #1e293b; border-radius: 12px; padding: 20px; margin-bottom: 18px; box-shadow: 0 4px 12px rgba(0,0,0,0.3); }
    .card-title { font-size: 16px; font-weight: 600; color: #e2e8f0; margin-bottom: 14px; display: flex; align-items: center; justify-content: space-between; }
    .step-pill { background: #0284c7; color: #fff; font-size: 11px; font-weight: 700; text-transform: uppercase; padding: 2px 8px; border-radius: 9999px; }
    .form-group { margin-bottom: 12px; }
    label { display: block; font-size: 12px; font-weight: 600; color: #94a3b8; margin-bottom: 4px; text-transform: uppercase; letter-spacing: 0.5px; }
    input, select { width: 100%; background: #0b0f19; border: 1px solid #334155; color: #fff; padding: 9px 12px; border-radius: 6px; font-size: 14px; outline: none; transition: border-color 0.15s; }
    input:focus, select:focus { border-color: #38bdf8; }
    .btn { background: #0284c7; color: white; border: none; padding: 10px 16px; border-radius: 6px; font-size: 13px; font-weight: 600; cursor: pointer; transition: background 0.15s; width: 100%; margin-top: 6px; }
    .btn:hover { background: #0369a1; }
    .btn-green { background: #059669; }
    .btn-green:hover { background: #047857; }
    .result { margin-top: 14px; padding: 12px; border-radius: 6px; font-size: 13px; font-family: monospace; white-space: pre-wrap; word-break: break-all; display: none; }
    .success { background: #064e3b; border: 1px solid #059669; color: #a7f3d0; }
    .error { background: #450a0a; border: 1px solid #dc2626; color: #fecaca; }
    .code-box { background: #0f172a; border: 1px dashed #38bdf8; color: #38bdf8; padding: 12px; border-radius: 6px; font-size: 20px; font-weight: 700; letter-spacing: 5px; text-align: center; margin: 12px 0; display: none; }
  </style>
</head>
<body>
  <div class="container">
    <div class="header">
      <h1>Collivra Authentication Portal</h1>
      <p>Test Email OTP & Mobile Phone OTP flows live in your browser</p>
    </div>

    <!-- Navigation Tabs -->
    <div class="nav-tabs">
      <button class="tab-btn active" onclick="switchTab('mobile')">📱 Mobile Phone OTP</button>
      <button class="tab-btn" onclick="switchTab('email')">✉️ Email OTP</button>
    </div>

    <!-- TAB 1: MOBILE OTP -->
    <div id="tab-mobile" class="tab-content active">
      <!-- Step 1: Request Mobile OTP -->
      <div class="card">
        <div class="card-title">
          <span>Step 1: Request Mobile OTP</span>
          <span class="step-pill">POST /api/v1/auth/mobile/request-otp</span>
        </div>
        <div class="form-group">
          <label>Mobile Number (Indian 10-digit or +91)</label>
          <input type="tel" id="mobile-number" placeholder="+919876543210 or 9876543210" value="+91">
        </div>
        <div class="form-group">
          <label>Purpose</label>
          <select id="mobile-purpose">
            <option value="login">Login (Instant Session)</option>
            <option value="signup">Sign Up (Complete Registration)</option>
            <option value="verification">Verification</option>
          </select>
        </div>
        <div class="form-group">
          <label>Role</label>
          <select id="mobile-role">
            <option value="creator">Creator</option>
            <option value="brand">Brand</option>
          </select>
        </div>
        <button class="btn btn-green" onclick="requestMobileOtp()">Send 6-Digit Mobile OTP</button>
        <div id="mobile-otp-display" class="code-box"></div>
        <div id="mobile-req-result" class="result"></div>
      </div>

      <!-- Step 2: Verify Mobile OTP -->
      <div class="card">
        <div class="card-title">
          <span>Step 2: Verify OTP & Sign In</span>
          <span class="step-pill">POST /api/v1/auth/mobile/verify-otp</span>
        </div>
        <div class="form-group">
          <label>Mobile Number</label>
          <input type="tel" id="verify-mobile" placeholder="+919876543210">
        </div>
        <div class="form-group">
          <label>6-Digit OTP Code</label>
          <input type="text" id="verify-code" placeholder="Enter 6-digit OTP code" maxlength="6">
        </div>
        <button class="btn btn-green" onclick="verifyMobileOtp()">Verify OTP & Authenticate</button>
        <div id="mobile-verify-result" class="result"></div>
      </div>
    </div>

    <!-- TAB 2: EMAIL OTP -->
    <div id="tab-email" class="tab-content">
      <!-- Step 1: Request Email OTP -->
      <div class="card">
        <div class="card-title">
          <span>Step 1: Request Email OTP</span>
          <span class="step-pill">POST /auth/signup/request-otp</span>
        </div>
        <div class="form-group">
          <label>Email Address</label>
          <input type="email" id="req-email" placeholder="you@domain.com" value="">
        </div>
        <div class="form-group">
          <label>Account Role</label>
          <select id="req-role">
            <option value="brand">Brand (Active Immediately)</option>
            <option value="creator">Creator (Requires Approval)</option>
          </select>
        </div>
        <button class="btn" onclick="requestOtp()">Send 6-Digit Email OTP</button>
        <div id="otp-display" class="code-box"></div>
        <div id="req-result" class="result"></div>
      </div>

      <!-- Step 2: Verify & Register -->
      <div class="card">
        <div class="card-title">
          <span>Step 2: Verify OTP & Create Account</span>
          <span class="step-pill">POST /auth/signup/verify-and-register</span>
        </div>
        <div class="form-group">
          <label>Email Address</label>
          <input type="email" id="reg-email" placeholder="you@domain.com" value="">
        </div>
        <div class="form-group">
          <label>6-Digit OTP Code</label>
          <input type="text" id="reg-otp" placeholder="e.g. 123456" maxlength="6">
        </div>
        <div class="form-group">
          <label>Full Name</label>
          <input type="text" id="reg-name" placeholder="Your Name" value="Test User">
        </div>
        <div class="form-group">
          <label>Password (Min 8 Characters)</label>
          <input type="password" id="reg-password" placeholder="Password" value="MyStrongPassword123!">
        </div>
        <div class="form-group" id="company-group">
          <label>Company Name (for Brands)</label>
          <input type="text" id="reg-company" placeholder="Company Name" value="Acme Inc">
        </div>
        <button class="btn" onclick="verifyAndRegister()">Verify OTP & Complete Sign-Up</button>
        <div id="reg-result" class="result"></div>
      </div>

      <!-- Step 3: Test Login -->
      <div class="card">
        <div class="card-title">
          <span>Step 3: Test Password Login</span>
          <span class="step-pill">POST /auth/login</span>
        </div>
        <div class="form-group">
          <label>Email or Mobile</label>
          <input type="text" id="login-email" placeholder="you@domain.com or +919876543210">
        </div>
        <div class="form-group">
          <label>Password</label>
          <input type="password" id="login-password" value="MyStrongPassword123!">
        </div>
        <button class="btn" onclick="testLogin()">Log In</button>
        <div id="login-result" class="result"></div>
      </div>
    </div>
  </div>

  <script>
    function switchTab(tab) {
      document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
      document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));
      if (tab === 'mobile') {
        document.querySelectorAll('.tab-btn')[0].classList.add('active');
        document.getElementById('tab-mobile').classList.add('active');
      } else {
        document.querySelectorAll('.tab-btn')[1].classList.add('active');
        document.getElementById('tab-email').classList.add('active');
      }
    }

    async function requestMobileOtp() {
      const mobile = document.getElementById('mobile-number').value.trim();
      const purpose = document.getElementById('mobile-purpose').value;
      const role = document.getElementById('mobile-role').value;
      const resEl = document.getElementById('mobile-req-result');
      const otpBox = document.getElementById('mobile-otp-display');

      if (!mobile || mobile.length < 10) { alert('Please enter a valid Indian mobile number'); return; }

      try {
        const res = await fetch('/api/v1/auth/mobile/request-otp', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ mobile, purpose, role })
        });
        const data = await res.json();
        resEl.style.display = 'block';
        if (res.ok) {
          resEl.className = 'result success';
          resEl.textContent = `Status: ${res.status} OK\n` + JSON.stringify(data, null, 2);
          if (data.devOtp) {
            otpBox.style.display = 'block';
            otpBox.textContent = data.devOtp;
            document.getElementById('verify-code').value = data.devOtp;
          }
          document.getElementById('verify-mobile').value = data.mobile || mobile;
        } else {
          resEl.className = 'result error';
          resEl.textContent = `Status: ${res.status} Error\n` + JSON.stringify(data, null, 2);
        }
      } catch (err) {
        resEl.style.display = 'block';
        resEl.className = 'result error';
        resEl.textContent = 'Request failed: ' + err.message;
      }
    }

    async function verifyMobileOtp() {
      const mobile = document.getElementById('verify-mobile').value.trim();
      const code = document.getElementById('verify-code').value.trim();
      const purpose = document.getElementById('mobile-purpose').value;
      const resEl = document.getElementById('mobile-verify-result');

      if (!mobile || !code) { alert('Please enter both mobile and 6-digit code'); return; }

      try {
        const res = await fetch('/api/v1/auth/mobile/verify-otp', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ mobile, code, purpose })
        });
        const data = await res.json();
        resEl.style.display = 'block';
        if (res.ok) {
          resEl.className = 'result success';
          resEl.textContent = `Status: 200 OK! Authentication Successful!\n` + JSON.stringify(data, null, 2);
        } else {
          resEl.className = 'result error';
          resEl.textContent = `Status: ${res.status} Error\n` + JSON.stringify(data, null, 2);
        }
      } catch (err) {
        resEl.style.display = 'block';
        resEl.className = 'result error';
        resEl.textContent = 'Verification failed: ' + err.message;
      }
    }

    async function requestOtp() {
      const email = document.getElementById('req-email').value.trim();
      const role = document.getElementById('req-role').value;
      const resEl = document.getElementById('req-result');
      const otpBox = document.getElementById('otp-display');

      if (!email) { alert('Please enter an email address'); return; }

      try {
        const res = await fetch('/auth/signup/request-otp', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ email, role })
        });
        const data = await res.json();
        resEl.style.display = 'block';
        if (res.ok) {
          resEl.className = 'result success';
          resEl.textContent = `Status: ${res.status} OK\n` + JSON.stringify(data, null, 2);
          if (data.devOtp) {
            otpBox.style.display = 'block';
            otpBox.textContent = data.devOtp;
            document.getElementById('reg-otp').value = data.devOtp;
          }
          document.getElementById('reg-email').value = email;
          document.getElementById('login-email').value = email;
        } else {
          resEl.className = 'result error';
          resEl.textContent = `Status: ${res.status} Error\n` + JSON.stringify(data, null, 2);
        }
      } catch (err) {
        resEl.style.display = 'block';
        resEl.className = 'result error';
        resEl.textContent = 'Request failed: ' + err.message;
      }
    }

    async function verifyAndRegister() {
      const email = document.getElementById('reg-email').value.trim();
      const otp = document.getElementById('reg-otp').value.trim();
      const name = document.getElementById('reg-name').value.trim();
      const password = document.getElementById('reg-password').value;
      const companyName = document.getElementById('reg-company').value.trim();
      const role = document.getElementById('req-role').value;
      const resEl = document.getElementById('reg-result');

      try {
        const res = await fetch('/auth/signup/verify-and-register', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ email, otp, name, password, role, companyName })
        });
        const data = await res.json();
        resEl.style.display = 'block';
        if (res.ok) {
          resEl.className = 'result success';
          resEl.textContent = `Status: 201 Created!\nAccount active! Token received:\n` + JSON.stringify(data, null, 2);
          document.getElementById('login-email').value = email;
          document.getElementById('login-password').value = password;
        } else {
          resEl.className = 'result error';
          resEl.textContent = `Status: ${res.status} Error\n` + JSON.stringify(data, null, 2);
        }
      } catch (err) {
        resEl.style.display = 'block';
        resEl.className = 'result error';
        resEl.textContent = 'Registration failed: ' + err.message;
      }
    }

    async function testLogin() {
      const email = document.getElementById('login-email').value.trim();
      const password = document.getElementById('login-password').value;
      const resEl = document.getElementById('login-result');

      try {
        const res = await fetch('/auth/login', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ identifier: email, password })
        });
        const data = await res.json();
        resEl.style.display = 'block';
        if (res.ok) {
          resEl.className = 'result success';
          resEl.textContent = `Status: 200 OK (Logged In successfully!)\n` + JSON.stringify(data, null, 2);
        } else {
          resEl.className = 'result error';
          resEl.textContent = `Status: ${res.status} Error\n` + JSON.stringify(data, null, 2);
        }
      } catch (err) {
        resEl.style.display = 'block';
        resEl.className = 'result error';
        resEl.textContent = 'Login failed: ' + err.message;
      }
    }
  </script>
</body>
</html>"""
        return HttpResponse(html, content_type='text/html')

