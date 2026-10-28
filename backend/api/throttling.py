from django.conf import settings
from rest_framework.throttling import SimpleRateThrottle
from .services import normalize_mobile

class BaseIpRateThrottle(SimpleRateThrottle):
    """
    Base throttle that checks HTTP_CF_CONNECTING_IP (if behind Cloudflare)
    before falling back to DRF get_ident (which applies NUM_PROXIES on X-Forwarded-For).
    """
    def get_ident(self, request):
        cf_ip = request.META.get('HTTP_CF_CONNECTING_IP')
        if cf_ip:
            return cf_ip.strip()
        return super().get_ident(request)

class LoginRateThrottle(BaseIpRateThrottle):
    scope = 'login'

    def get_cache_key(self, request, view):
        return self.cache_format % {
            'scope': self.scope,
            'ident': self.get_ident(request)
        }

class SignupRateThrottle(BaseIpRateThrottle):
    scope = 'signup'

    def get_cache_key(self, request, view):
        return self.cache_format % {
            'scope': self.scope,
            'ident': self.get_ident(request)
        }

class OtpSendRateThrottle(BaseIpRateThrottle):
    scope = 'otp_send'

    def get_cache_key(self, request, view):
        mobile = None
        if request.data:
            mobile = request.data.get('mobile')
        norm = normalize_mobile(mobile) if mobile else None
        ident = norm if norm else self.get_ident(request)
        return self.cache_format % {
            'scope': self.scope,
            'ident': ident
        }

class EmailOtpRateThrottle(BaseIpRateThrottle):
    scope = 'email_otp_send'

    def allow_request(self, request, view):
        # In DEV_MODE or for test emails, bypass rate throttling
        email = (request.data.get('email') or '').strip().lower() if request.data else ''
        if getattr(settings, 'DEV_MODE', False) or email.endswith('.test'):
            return True
        return super().allow_request(request, view)

    def get_cache_key(self, request, view):
        email = None
        if request.data:
            email = (request.data.get('email') or '').strip().lower()
        ident = email if email else self.get_ident(request)
        return self.cache_format % {
            'scope': self.scope,
            'ident': ident
        }

