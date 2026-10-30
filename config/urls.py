from django.contrib import admin
from django.urls import path, include
from django.http import JsonResponse

def root_health_view(request):
    return JsonResponse({
        'name': 'Collivra API',
        'status': 'healthy',
        'version': '1.0.0',
        'base_url': '/api/v1/',
        'sample_endpoints': [
            '/api/v1/creators',
            '/api/v1/creators/suggestions',
            '/api/v1/creators/filters',
            '/api/v1/auth/me',
            '/api/v1/cart',
            '/api/v1/orders'
        ]
    })

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', root_health_view, name='root-health'),
    path('api/v1/', include('api.urls')),
    path('', include('api.urls')),
]

handler404 = 'api.errors.error_404_handler'
handler500 = 'api.errors.error_500_handler'
