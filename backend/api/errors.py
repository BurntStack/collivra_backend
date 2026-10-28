from django.http import JsonResponse
from rest_framework import status
from rest_framework.views import exception_handler
from rest_framework.exceptions import (
    NotAuthenticated, AuthenticationFailed, PermissionDenied,
    NotFound, MethodNotAllowed, ValidationError
)

def custom_exception_handler(exc, context):
    """
    Custom DRF exception handler ensuring standard JSON error responses:
    {
        "message": "<message>",
        "code": "<code>",
        "error": {
            "code": "<code>",
            "message": "<message>"
        }
    }
    """
    response = exception_handler(exc, context)

    if response is not None:
        status_code = response.status_code
        code = 'error'
        msg = 'An error occurred'

        if status_code == 401:
            code = 'unauthorized'
            msg = 'Please sign in again'
        elif status_code == 403:
            code = 'forbidden'
            msg = 'Access denied'
        elif status_code == 404:
            code = 'not_found'
            msg = 'The requested resource was not found'
        elif status_code == 405:
            code = 'method_not_allowed'
            msg = 'Method not allowed'
        elif status_code in (400, 422):
            code = 'validation_error'
            msg = 'Validation error'
        elif status_code == 409:
            code = 'conflict'
            msg = 'Conflict'
        elif status_code == 423:
            code = 'account_locked'
            msg = 'Account is locked'

        # Check if exc has specific detail or code
        if hasattr(exc, 'detail'):
            detail = exc.detail
            if isinstance(detail, str):
                msg = detail
            elif isinstance(detail, list) and detail:
                msg = str(detail[0])
            elif isinstance(detail, dict):
                if 'message' in detail:
                    msg = str(detail['message'])
                elif 'error' in detail and isinstance(detail['error'], dict) and 'message' in detail['error']:
                    msg = str(detail['error']['message'])
                if 'code' in detail:
                    code = str(detail['code'])

        # Check if view already set code / message in response.data
        if isinstance(response.data, dict):
            if 'error' in response.data and isinstance(response.data['error'], dict):
                err = response.data['error']
                code = err.get('code', code)
                msg = err.get('message', msg)
            if 'code' in response.data:
                code = response.data.get('code', code)
            if 'message' in response.data:
                msg = response.data.get('message', msg)

        # Standardize envelope
        response.data = {
            'message': msg,
            'code': code,
            'error': {
                'code': code,
                'message': msg,
            }
        }
        return response

    # Unhandled exceptions (500)
    import traceback
    traceback.print_exc()
    return JsonResponse({
        'message': f'An unexpected server error occurred: {exc}',
        'code': 'server_error',
        'error': {
            'code': 'server_error',
            'message': str(exc),
        }
    }, status=500)


def error_404_handler(request, exception=None):
    return JsonResponse({
        'message': 'The requested resource was not found',
        'code': 'not_found',
        'error': {
            'code': 'not_found',
            'message': 'The requested resource was not found',
        }
    }, status=404)


def error_500_handler(request):
    return JsonResponse({
        'message': 'An unexpected server error occurred',
        'code': 'server_error',
        'error': {
            'code': 'server_error',
            'message': 'An unexpected server error occurred',
        }
    }, status=500)


class JsonErrorMiddleware:
    """Ensures that any 404 or 500 error returned by Django is JSON, never HTML."""
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        content_type = response.get('Content-Type', '')
        if response.status_code == 404 and ('text/html' in content_type or not content_type):
            return error_404_handler(request)
        if response.status_code == 500 and ('text/html' in content_type or not content_type):
            return error_500_handler(request)
        return response
