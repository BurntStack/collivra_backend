from django.urls import path
from .views import (
    AdminVerificationsListView,
    AdminVerificationDetailView,
    AdminVerificationApproveView,
    AdminVerificationRejectView,
    AdminVerificationRequestInfoView,
)
from .kyc_admin_views import (
    CreatorVerificationQueueView,
    CreatorApproveView,
    CreatorRejectView,
)

urlpatterns = [
    # Legacy Document Verification Requests
    path('admin/verifications', AdminVerificationsListView.as_view(), name='admin-verifications-list'),
    path('admin/verifications/<str:pk>', AdminVerificationDetailView.as_view(), name='admin-verifications-detail'),
    path('admin/verifications/<str:pk>/approve', AdminVerificationApproveView.as_view(), name='admin-verifications-approve'),
    path('admin/verifications/<str:pk>/reject', AdminVerificationRejectView.as_view(), name='admin-verifications-reject'),
    path('admin/verifications/<str:pk>/request-info', AdminVerificationRequestInfoView.as_view(), name='admin-verifications-request-info'),

    # Superadmin Creator Onboarding Verification Queue
    path('admin/creators/queue', CreatorVerificationQueueView.as_view(), name='admin-creators-queue'),
    path('admin/creators/<str:pk>/approve', CreatorApproveView.as_view(), name='admin-creator-approve'),
    path('admin/creators/<str:pk>/reject', CreatorRejectView.as_view(), name='admin-creator-reject'),
]
