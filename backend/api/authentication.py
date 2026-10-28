import jwt
import requests
from django.conf import settings
from rest_framework import authentication, exceptions
from .models import Profile

class SupabaseUser:
    """Represents an authenticated Supabase user in Django request context."""
    def __init__(self, user_id, email=None, role=None, raw_claims=None):
        self.id = str(user_id)
        self.email = email
        self.role = role or 'brand'
        self.raw_claims = raw_claims or {}
        self.is_authenticated = True
        self.is_anonymous = False

    def __str__(self):
        return f"SupabaseUser({self.id}, role={self.role})"


class SupabaseAuthentication(authentication.BaseAuthentication):
    """
    DRF Authentication class that decodes and validates Supabase JWTs from
    the Authorization: Bearer header.
    """
    def authenticate_header(self, request):
        return 'Bearer'

    def authenticate(self, request):
        auth_header = request.headers.get('Authorization')
        if not auth_header:
            return None

        parts = auth_header.split()
        if len(parts) != 2 or parts[0].lower() != 'bearer':
            return None

        token = parts[1]
        user_claims = None

        # 1. Try decoding with SUPABASE_JWT_SECRET if available
        if settings.SUPABASE_JWT_SECRET:
            try:
                user_claims = jwt.decode(
                    token,
                    settings.SUPABASE_JWT_SECRET,
                    algorithms=['HS256'],
                    options={"verify_aud": False}
                )
            except jwt.ExpiredSignatureError:
                raise exceptions.AuthenticationFailed('Token has expired')
            except jwt.InvalidTokenError:
                user_claims = None

        # 2. Fall back to calling Supabase Auth API /auth/v1/user
        if not user_claims and settings.SUPABASE_URL and settings.SUPABASE_ANON_KEY:
            try:
                res = requests.get(
                    f"{settings.SUPABASE_URL}/auth/v1/user",
                    headers={
                        'Authorization': f"Bearer {token}",
                        'apikey': settings.SUPABASE_ANON_KEY,
                    },
                    timeout=5,
                )
                if res.status_code == 200:
                    data = res.json()
                    user_claims = {
                        'sub': data.get('id'),
                        'email': data.get('email'),
                        'user_metadata': data.get('user_metadata', {}),
                    }
                elif res.status_code == 401:
                    raise exceptions.AuthenticationFailed('Invalid or expired token')
            except requests.RequestException:
                pass

        if not user_claims or not user_claims.get('sub'):
            raise exceptions.AuthenticationFailed('Invalid Supabase token')

        user_id = user_claims.get('sub')
        email = user_claims.get('email')

        # Determine role: check database Profile first, fallback to user_metadata
        role = None
        try:
            profile = Profile.objects.filter(id=user_id).first()
            if profile:
                role = profile.role
                if not email:
                    email = profile.email
        except Exception:
            pass

        if not role:
            metadata = user_claims.get('user_metadata') or {}
            role = metadata.get('role', 'brand')

        user = SupabaseUser(user_id=user_id, email=email, role=role, raw_claims=user_claims)
        return (user, token)
