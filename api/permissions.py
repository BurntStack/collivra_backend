from django.conf import settings
from rest_framework import permissions
from rest_framework.exceptions import PermissionDenied, NotAuthenticated
from .models import Profile

ADMIN_EMAIL = 'socials@burntstack.com'

def is_valid_admin(user):
    """
    Verifies that the user has admin role AND their email is strictly socials@burntstack.com
    (or test_admin_ in DEBUG mode).
    """
    if not user or not user.is_authenticated:
        return False
    role = getattr(user, 'role', None)
    email = (getattr(user, 'email', '') or '').strip().lower()
    if role not in ['admin', 'super_admin']:
        return False
    if email == ADMIN_EMAIL:
        return True
    if getattr(settings, 'DEBUG', False) and email.startswith('test_admin_') and email.endswith('@collivra.test'):
        return True
    return False



class IsAuthenticatedUser(permissions.BasePermission):
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            raise NotAuthenticated('Authentication credentials were not provided or are invalid.')
        return True


class IsAdminUser(permissions.BasePermission):
    """
    Admin-only endpoints:
    Restricted strictly to authenticated users with role in ('admin', 'super_admin') and email='socials@burntstack.com',
    server-checked directly from the public.profiles database table on every request.
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            raise NotAuthenticated('Authentication credentials were not provided or are invalid.')
        profile = Profile.objects.filter(id=request.user.id).first()
        if not profile or profile.role not in ['admin', 'super_admin'] or profile.status != 'active':
            raise PermissionDenied('Access restricted to verified administrator (socials@burntstack.com).')
        email = (profile.email or '').strip().lower()
        is_allowed = email == ADMIN_EMAIL or (settings.DEBUG and email.startswith('test_admin_') and email.endswith('@collivra.test'))
        if not is_allowed:
            raise PermissionDenied('Access restricted to verified administrator (socials@burntstack.com).')
        return True



IsSuperAdminUser = IsAdminUser


class IsBrandUser(permissions.BasePermission):
    """
    Brand-only endpoints:
    Requires authenticated user with role='brand' and status='active' (or verified admin).
    Returns 401 if unauthenticated.
    Returns 403 if not active brand.
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            raise NotAuthenticated('Authentication credentials were not provided or are invalid.')
        if is_valid_admin(request.user):
            return True
        role = getattr(request.user, 'role', None)
        status_val = getattr(request.user, 'status', None)
        if role == 'brand' and status_val == 'active':
            return True
        raise PermissionDenied('Access restricted to active brands.')


class IsActiveCreator(permissions.BasePermission):
    """
    Marketplace creator endpoints (bids, packages, offers, orders, drafts, messages):
    Requires authenticated user with role='creator' and status='active' (or verified admin).
    Returns 401 if unauthenticated.
    Returns 403 { code: creator_not_approved } if creator is not active.
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            raise NotAuthenticated('Authentication credentials were not provided or are invalid.')
        if is_valid_admin(request.user):
            return True
        role = getattr(request.user, 'role', None)
        status_val = getattr(request.user, 'status', None)
        if role == 'creator':
            if status_val == 'active':
                return True
            raise PermissionDenied(detail={'code': 'creator_not_approved', 'message': 'Creator account is not approved'})
        raise PermissionDenied(detail={'code': 'creator_not_approved', 'message': 'Access restricted to active creators.'})


# Legacy / general alias
IsCreatorUser = IsActiveCreator


class IsCreatorOnboarding(permissions.BasePermission):
    """
    Creator onboarding endpoints (profile, KYC, bank, upload, verification-status):
    Allows creators in 'unverified', 'pending', 'needs_info', or 'active' (or verified admin).
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            raise NotAuthenticated('Authentication credentials were not provided or are invalid.')
        if is_valid_admin(request.user):
            return True
        role = getattr(request.user, 'role', None)
        status_val = getattr(request.user, 'status', None)
        if role == 'creator' and status_val in ['unverified', 'pending', 'needs_info', 'active']:
            return True
        raise PermissionDenied('Access restricted to creator onboarding.')


class IsMarketplaceParticipant(permissions.BasePermission):
    """
    Shared endpoints between active brands and active creators (orders, order messages).
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            raise NotAuthenticated('Authentication credentials were not provided or are invalid.')
        if is_valid_admin(request.user):
            return True
        role = getattr(request.user, 'role', None)
        status_val = getattr(request.user, 'status', None)
        if role == 'brand' and status_val == 'active':
            return True
        if role == 'creator':
            if status_val == 'active':
                return True
            raise PermissionDenied(detail={'code': 'creator_not_approved', 'message': 'Creator account is not approved'})
        raise PermissionDenied('Access restricted to active marketplace participants.')


