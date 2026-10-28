from rest_framework import permissions
from rest_framework.exceptions import PermissionDenied, NotAuthenticated

class IsAuthenticatedUser(permissions.BasePermission):
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            raise NotAuthenticated('Authentication credentials were not provided or are invalid.')
        return True


class IsBrandUser(permissions.BasePermission):
    """
    Brand-only endpoints:
    Returns 401 if unauthenticated.
    Returns 403 if authenticated but not brand or admin.
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            raise NotAuthenticated('Authentication credentials were not provided or are invalid.')
        if getattr(request.user, 'role', None) not in ['brand', 'admin']:
            raise PermissionDenied('Access restricted to brands.')
        return True


class IsCreatorUser(permissions.BasePermission):
    """
    Creator-only endpoints:
    Returns 401 if unauthenticated.
    Returns 403 if not creator or admin.
    """
    def has_permission(self, request, view):
        if not request.user or not request.user.is_authenticated:
            raise NotAuthenticated('Authentication credentials were not provided or are invalid.')
        if getattr(request.user, 'role', None) not in ['creator', 'admin']:
            raise PermissionDenied('Access restricted to creators.')
        return True
