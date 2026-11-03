from django.urls import path
from .views import (
    CartView,
    CartItemCreateView,
    CartItemDetailView,
    OffersView,
)

urlpatterns = [
    path('cart', CartView.as_view(), name='cart'),
    path('cart/items', CartItemCreateView.as_view(), name='cart-items-create'),
    path('cart/items/<str:pk>', CartItemDetailView.as_view(), name='cart-items-detail'),
    path('offers', OffersView.as_view(), name='offers'),
]

