from django.urls import path
from .views import (
    OrderListCreateView,
    OrderDetailView,
    OrderPayView,
    OrderConfirmStubView,
    OrderSubmitDraftView,
    OrderRequestChangesView,
    OrderApproveView,
    OrderMessagesView,
)

urlpatterns = [
    path('orders', OrderListCreateView.as_view(), name='order-list-create'),
    path('orders/<str:pk>', OrderDetailView.as_view(), name='order-detail'),
    path('orders/<str:pk>/pay', OrderPayView.as_view(), name='order-pay'),
    path('orders/<str:pk>/confirm-payment-stub', OrderConfirmStubView.as_view(), name='order-confirm-stub'),
    path('orders/<str:pk>/submit-draft', OrderSubmitDraftView.as_view(), name='order-submit-draft'),
    path('orders/<str:pk>/request-changes', OrderRequestChangesView.as_view(), name='order-request-changes'),
    path('orders/<str:pk>/approve', OrderApproveView.as_view(), name='order-approve'),
    path('orders/<str:pk>/messages', OrderMessagesView.as_view(), name='order-messages'),
]
