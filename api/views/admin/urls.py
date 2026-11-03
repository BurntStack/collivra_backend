from django.urls import path
from .views import (
    AdminVerificationsListView,
    AdminVerificationDetailView,
    AdminVerificationApproveView,
    AdminVerificationRejectView,
    AdminVerificationRequestInfoView,
)

urlpatterns = [
    path('admin/verifications', AdminVerificationsListView.as_view(), name='admin-verifications-list'),
    path('admin/verifications/<str:pk>', AdminVerificationDetailView.as_view(), name='admin-verifications-detail'),
    path('admin/verifications/<str:pk>/approve', AdminVerificationApproveView.as_view(), name='admin-verifications-approve'),
    path('admin/verifications/<str:pk>/reject', AdminVerificationRejectView.as_view(), name='admin-verifications-reject'),
    path('admin/verifications/<str:pk>/request-info', AdminVerificationRequestInfoView.as_view(), name='admin-verifications-request-info'),
]
