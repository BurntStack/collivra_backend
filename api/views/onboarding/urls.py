from django.urls import path
from .views import (
    PresignUploadView,
    CreatorOnboardingProfileView,
    SocialConnectUrlView,
    SocialCallbackView,
    KycIdView,
    KycPanView,
    BankView,
    CreatorOnboardingSubmitView,
    VerificationStatusView,
)

urlpatterns = [
    path('uploads/presign', PresignUploadView.as_view(), name='uploads-presign'),
    path('creator/onboarding/profile', CreatorOnboardingProfileView.as_view(), name='creator-onboarding-profile'),
    path('creator/social/<str:platform>/connect-url', SocialConnectUrlView.as_view(), name='social-connect-url'),
    path('creator/social/<str:platform>/callback', SocialCallbackView.as_view(), name='social-callback'),
    path('creator/kyc/id', KycIdView.as_view(), name='creator-kyc-id'),
    path('creator/kyc/pan', KycPanView.as_view(), name='creator-kyc-pan'),
    path('creator/bank', BankView.as_view(), name='creator-bank'),
    path('creator/onboarding/submit', CreatorOnboardingSubmitView.as_view(), name='creator-onboarding-submit'),
    path('creator/verification-status', VerificationStatusView.as_view(), {'role': 'creator'}, name='creator-verification-status'),
    path('<str:role>/verification-status', VerificationStatusView.as_view(), name='role-verification-status'),
]

