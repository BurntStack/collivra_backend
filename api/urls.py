from django.urls import path, include
from .views.auth import HealthCheckView

urlpatterns = [
    # Health check
    path('health', HealthCheckView.as_view(), name='health'),

    # Modular Domain Routers
    path('auth/', include('api.views.auth.urls')),
    path('', include('api.views.onboarding.urls')),
    path('', include('api.views.marketplace.urls')),
    path('', include('api.views.cart.urls')),
    path('', include('api.views.campaigns.urls')),
    path('', include('api.views.orders.urls')),
    path('', include('api.views.dashboard.urls')),
    path('', include('api.views.admin.urls')),
]
