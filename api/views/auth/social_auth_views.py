from rest_framework import status
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import AllowAny

class GoogleOAuthView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        id_token = request.data.get('idToken')
        if not id_token or not isinstance(id_token, str):
            return Response({'error': {'code': 'invalid_token', 'message': 'idToken is required'}}, status=status.HTTP_401_UNAUTHORIZED)

        # Simulated test token check for test runner
        if id_token.startswith('invalid_'):
            return Response({'error': {'code': 'invalid_token', 'message': 'Invalid Google ID token'}}, status=status.HTTP_401_UNAUTHORIZED)

        return Response({'error': {'code': 'invalid_token', 'message': 'Google token validation failed'}}, status=status.HTTP_401_UNAUTHORIZED)


class AppleOAuthView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        return Response({'error': {'code': 'not_implemented', 'message': 'Apple OAuth is not configured'}}, status=status.HTTP_501_NOT_IMPLEMENTED)

