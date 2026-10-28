import jwt
from jwt import PyJWKClient
from django.conf import settings
from rest_framework import authentication, exceptions
from .models import Profile

_jwks_client = None

def get_jwks_client():
    global _jwks_client
    if _jwks_client is None:
        jwks_url = f"{settings.SUPABASE_URL.rstrip('/')}/auth/v1/.well-known/jwks.json"
        _jwks_client = PyJWKClient(jwks_url, cache_jwk_set=True, lifespan=3600)
    return _jwks_client


class SupabaseUser:
    """Represents an authenticated Supabase user in Django request context."""
    def __init__(self, user_id, email=None, role=None, raw_claims=None):
        self.id = str(user_id)
        self.pk = self.id
        self.email = email
        self.role = role or 'brand'
        self.raw_claims = raw_claims or {}
        self.is_authenticated = True
        self.is_anonymous = False

    def __str__(self):
        return f"SupabaseUser({self.id}, role={self.role})"


class SupabaseAuthentication(authentication.BaseAuthentication):
    """
    DRF Authentication class verifying GoTrue JWTs against Supabase JWKS with
    aud 'authenticated', issuer check, and blocking suspended/banned accounts.
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

        issuer = f"{settings.SUPABASE_URL.rstrip('/')}/auth/v1"
        try:
            client = get_jwks_client()
            signing_key = client.get_signing_key_from_jwt(token)
            user_claims = jwt.decode(
                token,
                signing_key.key,
                algorithms=['ES256', 'RS256'],
                audience='authenticated',
                issuer=issuer,
                options={"verify_aud": True, "verify_iss": True}
            )
        except jwt.ExpiredSignatureError:
            raise exceptions.AuthenticationFailed('Token has expired')
        except Exception as e:
            raise exceptions.AuthenticationFailed(f'Invalid token: {str(e)}')

        if not user_claims or not user_claims.get('sub'):
            raise exceptions.AuthenticationFailed('Invalid token claims')

        user_id = user_claims.get('sub')
        email = user_claims.get('email')

        # Block suspended and banned accounts on every request
        profile = Profile.objects.filter(id=user_id).first()
        if profile and profile.status in ['suspended', 'banned']:
            raise exceptions.PermissionDenied(f"Your account is {profile.status}")

        role = None
        if profile:
            role = profile.role
            if not email:
                email = profile.email

        if not role:
            metadata = user_claims.get('user_metadata') or {}
            role = metadata.get('role', 'brand')

        # Safeguard: strictly bind admin/super_admin privileges to socials@burntstack.com
        if role in ['admin', 'super_admin'] and (email or '').strip().lower() != 'socials@burntstack.com':
            role = 'brand'

        user = SupabaseUser(user_id=user_id, email=email, role=role, raw_claims=user_claims)
        return (user, token)
