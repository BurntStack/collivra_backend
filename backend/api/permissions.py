from rest_framework import permissions
from rest_framework.exceptions import PermissionDenied, NotAuthenticated

ADMIN_EMAIL = 'socials@burntstack.com'

def is_valid_admin(user):
    """
    Verifies that the user has admin role AND their email is strictly socials@burntstack.com.
    """
    if not user or not user.is_authenticated:
        return False
    role = getattr(user, 'role', None)
    email = (getattr(user, 'email', '') or '').strip().lower()
    return role in ['admin', 'super_admin'] and email == ADMIN_EMAIL


class IsAuthenticatedUser(permissions.BasePermission):
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            raise NotAuthenticated('Authentication credentials were not provided or are invalid.')
        return True


class IsAdminUser(permissions.BasePermission):
    """
    Admin-only endpoints:
    Restricted strictly to authenticated users with role='admin' and email='socials@burntstack.com'.
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            raise NotAuthenticated('Authentication credentials were not provided or are invalid.')
        if not is_valid_admin(request.user):
            raise PermissionDenied('Access restricted to verified administrator (socials@burntstack.com).')
        return True


IsSuperAdminUser = IsAdminUser



class IsBrandUser(permissions.BasePermission):
    """
    Brand-only endpoints:
    Returns 401 if unauthenticated.
    Returns 403 if authenticated but not brand or verified admin.
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            raise NotAuthenticated('Authentication credentials were not provided or are invalid.')
        if getattr(request.user, 'role', None) == 'brand' or is_valid_admin(request.user):
            return True
        raise PermissionDenied('Access restricted to brands.')


class IsCreatorUser(permissions.BasePermission):
    """
    Creator-only endpoints:
    Returns 401 if unauthenticated.
    Returns 403 if not creator or verified admin.
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            raise NotAuthenticated('Authentication credentials were not provided or are invalid.')
        if getattr(request.user, 'role', None) == 'creator' or is_valid_admin(request.user):
            return True
        raise PermissionDenied('Access restricted to creators.')

