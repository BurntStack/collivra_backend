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
