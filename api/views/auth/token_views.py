import json
from datetime import datetime, timezone, timedelta
from django.conf import settings
from django.utils import timezone as django_tz
from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny, IsAuthenticated

from ...models import Profile
from ...services import (
    supabase_auth, normalize_mobile, send_otp, check_otp,
    PHONE_EMAIL_DOMAIN, LOCK_MINUTES, MAX_FAILED_LOGINS
)
from ...throttling import LoginRateThrottle
from .common import format_user_payload


class HealthCheckView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        return Response({'ok': True, 'time': django_tz.now().isoformat()})


class LoginView(APIView):
    permission_classes = [AllowAny]
    throttle_classes = [LoginRateThrottle]

    def post(self, request):
        body = request.data or {}
        identifier = (body.get('identifier') or body.get('email') or '').strip()
        password = body.get('password') or ''
        role = body.get('role')

        if not identifier or not password:
            return Response({'message': 'Email/mobile and password are required', 'code': 'validation_error'}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)

        # Find profile
        profile = None
        if '@' in identifier:
            profile = Profile.objects.filter(email__iexact=identifier).first()
            if not profile:
                auth_res = supabase_auth.sign_in_with_password(identifier, password)
                if auth_res.status_code == 200:
                    session_data = auth_res.json()
                    user_data = session_data.get('user') or {}
                    u_id = user_data.get('id')
                    u_role = (user_data.get('app_metadata') or {}).get('role') or (user_data.get('user_metadata') or {}).get('role') or 'brand'
                    u_name = (user_data.get('user_metadata') or {}).get('name') or 'User'
                    profile, _ = Profile.objects.get_or_create(
                        id=u_id,
                        defaults={
                            'email': identifier,
                            'name': u_name,
                            'role': u_role,
                            'status': 'active',
                            'failed_logins': 0,
                            'created_at': django_tz.now(),
                            'updated_at': django_tz.now(),
                        }
                    )
                    if not profile.email or profile.role != u_role:
                        profile.email = identifier
                        profile.role = u_role
                        profile.save()
                    token = session_data.get('access_token')
                    refresh_token = session_data.get('refresh_token')
                    expires_in = session_data.get('expires_in', 3600)
                    return Response({
                        'token': token,
                        'accessToken': token,
                        'refreshToken': refresh_token,
                        'expiresIn': expires_in,
                        'user': {
                            'id': str(profile.id),
                            'name': profile.name,
                            'email': profile.email,
                            'companyName': profile.company_name or '',
                            'role': profile.role,
                        }
                    })
                return Response({'message': 'Wrong mobile/email or password', 'code': 'invalid_credentials'}, status=status.HTTP_401_UNAUTHORIZED)
        else:
            norm_m = normalize_mobile(identifier)
            q = Profile.objects.filter(mobile=norm_m)
            if role:
                q = q.filter(role=role)
            if q.count() > 1:
                return Response({'message': 'Choose brand or creator to continue', 'code': 'role_required'}, status=status.HTTP_409_CONFLICT)
            profile = q.first()

        if not profile:
            return Response({'message': 'Wrong mobile/email or password', 'code': 'invalid_credentials'}, status=status.HTTP_401_UNAUTHORIZED)

        # Check account lockout
        if profile.locked_until and profile.locked_until > django_tz.now():
            return Response({
                'message': f"Too many wrong attempts. Try again in {LOCK_MINUTES} minutes.",
                'code': 'account_locked',
                'lockedUntil': profile.locked_until.isoformat(),
            }, status=status.HTTP_423_LOCKED)

        # Determine Supabase Auth login email
        login_email = profile.email
        if not login_email:
            u_res = supabase_auth.get_user_by_id(str(profile.id))
            if u_res.status_code == 200:
                login_email = u_res.json().get('email')
            if not login_email:
                login_email = f"{profile.mobile[1:]}.{profile.role}@{PHONE_EMAIL_DOMAIN}"

        # Sign in via Supabase Auth
        auth_res = supabase_auth.sign_in_with_password(login_email, password)
        if auth_res.status_code != 200:
            failed = profile.failed_logins + 1
            if failed >= MAX_FAILED_LOGINS:
                until = django_tz.now() + timedelta(minutes=LOCK_MINUTES)
                profile.failed_logins = 0
                profile.locked_until = until
                profile.save()
                return Response({
                    'message': f"Too many wrong attempts. Try again in {LOCK_MINUTES} minutes.",
                    'code': 'account_locked',
                    'lockedUntil': until.isoformat(),
                }, status=status.HTTP_423_LOCKED)
            profile.failed_logins = failed
            profile.save()
            return Response({'message': 'Wrong mobile/email or password', 'code': 'invalid_credentials'}, status=status.HTTP_401_UNAUTHORIZED)

        # Clear failed logins on successful password verification
        profile.failed_logins = 0
        profile.locked_until = None
        profile.save()

        # Check account status
        if profile.status in ['suspended', 'banned']:
            return Response({'message': f"Your account is {profile.status}", 'code': 'account_blocked'}, status=status.HTTP_403_FORBIDDEN)

        session_data = auth_res.json()
        token = session_data.get('access_token')
        refresh_token = session_data.get('refresh_token')
        expires_in = session_data.get('expires_in', 3600)

        user_obj = {
            'id': str(profile.id),
            'name': profile.name,
            'email': profile.email or login_email,
            'companyName': profile.company_name,
            'role': profile.role,
        }

        return Response({
            'token': token,
            'user': user_obj,
            'accessToken': token,
            'refreshToken': refresh_token,
            'expiresIn': expires_in,
            'role': profile.role,
            'status': profile.status,
        })


class MeView(APIView):
    def get(self, request):
        if not request.user or not request.user.is_authenticated:
            return Response({'message': 'Please sign in again', 'code': 'unauthorized', 'error': {'code': 'unauthorized', 'message': 'Please sign in again'}}, status=status.HTTP_401_UNAUTHORIZED)

        profile = Profile.objects.filter(id=request.user.id).first()
        if not profile:
            return Response({'message': 'Profile not found', 'code': 'not_found'}, status=status.HTTP_404_NOT_FOUND)

        if profile.status in ['suspended', 'banned']:
            return Response({'message': f"Your account is {profile.status}", 'code': 'account_blocked'}, status=status.HTTP_403_FORBIDDEN)

        return Response({
            'user': {
                'id': str(profile.id),
                'name': profile.name,
                'email': profile.email or request.user.email,
                'companyName': profile.company_name,
                'role': profile.role,
            },
            'id': str(profile.id),
            'role': profile.role,
            'status': profile.status,
            'name': profile.name,
            'mobile': profile.mobile,
        })

    def patch(self, request):
        if not request.user or not request.user.is_authenticated:
            return Response({'message': 'Please sign in again', 'code': 'unauthorized'}, status=status.HTTP_401_UNAUTHORIZED)

        body = request.data or {}
        if 'role' in body or 'status' in body:
            return Response({
                'message': 'Role and status cannot be modified via this endpoint',
                'code': 'validation_error',
                'error': {
                    'code': 'validation_error',
                    'message': 'Role and status cannot be modified via this endpoint',
                }
            }, status=status.HTTP_422_UNPROCESSABLE_ENTITY)

        profile = Profile.objects.filter(id=request.user.id).first()
        if not profile:
            return Response({'message': 'Profile not found', 'code': 'not_found'}, status=status.HTTP_404_NOT_FOUND)

        if 'name' in body:
            profile.name = body['name']
        if 'companyName' in body and profile.role == 'brand':
            profile.company_name = body['companyName']
        profile.save()

        return Response({
            'user': {
                'id': str(profile.id),
                'name': profile.name,
                'email': profile.email or request.user.email,
                'companyName': profile.company_name,
                'role': profile.role,
            },
            'id': str(profile.id),
            'role': profile.role,
            'status': profile.status,
            'name': profile.name,
            'mobile': profile.mobile,
        })


class RefreshView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        refresh_token = request.data.get('refreshToken')
        if not refresh_token:
            return Response({'message': 'refreshToken required', 'code': 'validation_error'}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)

        res = supabase_auth.refresh_session(refresh_token)
        if res.status_code != 200:
            return Response({'message': 'Please sign in again', 'code': 'unauthorized'}, status=status.HTTP_401_UNAUTHORIZED)

        data = res.json()
        return Response({
            'accessToken': data.get('access_token'),
            'refreshToken': data.get('refresh_token'),
            'expiresIn': data.get('expires_in', 3600),
        })


class ForgotPasswordView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        identifier = (request.data.get('identifier') or '').strip()
        if not identifier:
            return Response({'message': 'Identifier required', 'code': 'validation_error'}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)

        mobile = normalize_mobile(identifier)
        if mobile:
            send_otp(mobile)

        return Response({'ok': True})


class ResetPasswordView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        mobile = normalize_mobile(request.data.get('mobile'))
        code = request.data.get('code')
        new_password = request.data.get('newPassword')

        if not mobile or not code or not new_password or len(new_password) < 8:
            return Response({'message': 'Invalid reset parameters', 'code': 'validation_error'}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)

        if not check_otp(mobile, code):
            return Response({'message': 'Wrong or expired code', 'code': 'invalid_otp'}, status=status.HTTP_400_BAD_REQUEST)

        profile = Profile.objects.filter(mobile=mobile).first()
        if not profile:
            return Response({'message': 'User not found', 'code': 'not_found'}, status=status.HTTP_404_NOT_FOUND)

        # Update password in Supabase Auth
        supabase_auth.update_user_password(str(profile.id), new_password)

        profile.failed_logins = 0
        profile.locked_until = None
        profile.mobile_verified_at = django_tz.now()
        profile.save()

        return Response({'ok': True})


class ChangePasswordView(APIView):
    def post(self, request):
        if not request.user or not request.user.is_authenticated:
            return Response({'message': 'Please sign in again', 'code': 'unauthorized'}, status=status.HTTP_401_UNAUTHORIZED)

        current = request.data.get('current')
        next_pwd = request.data.get('next')

        if not current or not next_pwd or len(next_pwd) < 8:
            return Response({'message': 'Invalid password parameters', 'code': 'validation_error'}, status=status.HTTP_422_UNPROCESSABLE_ENTITY)

        profile = Profile.objects.filter(id=request.user.id).first()
        if not profile:
            return Response({'message': 'User not found', 'code': 'not_found'}, status=status.HTTP_404_NOT_FOUND)

        login_email = profile.email
        if not login_email:
            login_email = f"{profile.mobile[1:]}.{profile.role}@{PHONE_EMAIL_DOMAIN}"

        # Verify current password
        auth_res = supabase_auth.sign_in_with_password(login_email, current)
        if auth_res.status_code != 200:
            return Response({'message': 'Current password incorrect', 'code': 'invalid_credentials'}, status=status.HTTP_401_UNAUTHORIZED)

        # Update password
        supabase_auth.update_user_password(str(profile.id), next_pwd)
        return Response({'ok': True})


class LogoutView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        auth_header = request.headers.get('Authorization', '')
        if auth_header.startswith('Bearer '):
            token = auth_header[7:].strip()
            supabase_auth.sign_out(token)
        return Response(status=status.HTTP_204_NO_CONTENT)

