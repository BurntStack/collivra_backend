from django.urls import path
from .views import (
    HealthCheckView, SignupView, RequestEmailOtpView, VerifyAndRegisterView,
    OtpSendView, OtpVerifyView, LoginView,
    MeView, RefreshView, ForgotPasswordView, ResetPasswordView,
    ChangePasswordView, LogoutView, GoogleOAuthView, AppleOAuthView,
    PresignUploadView, CreatorOnboardingProfileView, SocialConnectUrlView,
    SocialCallbackView, KycIdView, KycPanView, BankView,
    CreatorOnboardingSubmitView, VerificationStatusView,
    CreatorSuggestionsView, CreatorFiltersView, CreatorListView,
    CreatorDetailView, CreatorPackagesView, CreatorReviewsView,
    CreatorSimilarView, CreatorSaveView,
    CartView, CartItemCreateView, CartItemDetailView, OffersView,
    CampaignListCreateView, CampaignDetailView, CampaignBidsView,
    CampaignBidSelectView,
    OrderListCreateView, OrderDetailView, OrderPayView,
    OrderConfirmStubView, OrderSubmitDraftView, OrderRequestChangesView,
    OrderApproveView, OrderMessagesView,
    DashboardSummaryView, DashboardTodoView, ShortlistListCreateView,
    ShortlistDetailView, ShortlistCreatorManageView, ShortlistDuplicateView,
    DeliverablesListView, DeliverableDetailView, DeliverablesExportView,
    ReportingView, ReportingExportView,
    AdminVerificationsListView, AdminVerificationDetailView,
    AdminVerificationApproveView, AdminVerificationRejectView,
    AdminVerificationRequestInfoView,
)


urlpatterns = [
    # Health check
    path('health', HealthCheckView.as_view(), name='health'),

    # Auth
    path('auth/signup', SignupView.as_view(), name='auth-signup'),
    path('auth/signup/request-otp', RequestEmailOtpView.as_view(), name='auth-signup-request-otp'),
    path('auth/signup/verify-and-register', VerifyAndRegisterView.as_view(), name='auth-signup-verify-and-register'),
    path('auth/otp/send', OtpSendView.as_view(), name='auth-otp-send'),
    path('auth/otp/verify', OtpVerifyView.as_view(), name='auth-otp-verify'),
    path('auth/login', LoginView.as_view(), name='auth-login'),
    path('auth/me', MeView.as_view(), name='auth-me'),
    path('auth/refresh', RefreshView.as_view(), name='auth-refresh'),
    path('auth/forgot-password', ForgotPasswordView.as_view(), name='auth-forgot-password'),
    path('auth/reset-password', ResetPasswordView.as_view(), name='auth-reset-password'),
    path('auth/change-password', ChangePasswordView.as_view(), name='auth-change-password'),
    path('auth/logout', LogoutView.as_view(), name='auth-logout'),
    path('auth/oauth/google', GoogleOAuthView.as_view(), name='auth-oauth-google'),
    path('auth/oauth/apple', AppleOAuthView.as_view(), name='auth-oauth-apple'),

    # Uploads & KYC
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

    # Marketplace Discovery
    path('creators/suggestions', CreatorSuggestionsView.as_view(), name='creator-suggestions'),
    path('creators/filters', CreatorFiltersView.as_view(), name='creator-filters'),
    path('creators', CreatorListView.as_view(), name='creator-list'),
    path('creators/<str:pk>', CreatorDetailView.as_view(), name='creator-detail'),
    path('creators/<str:pk>/packages', CreatorPackagesView.as_view(), name='creator-packages'),
    path('creators/<str:pk>/reviews', CreatorReviewsView.as_view(), name='creator-reviews'),
    path('creators/<str:pk>/similar', CreatorSimilarView.as_view(), name='creator-similar'),
    path('creators/<str:pk>/save', CreatorSaveView.as_view(), name='creator-save'),

    # Cart & Offers
    path('cart', CartView.as_view(), name='cart'),
    path('cart/items', CartItemCreateView.as_view(), name='cart-items-create'),
    path('cart/items/<str:pk>', CartItemDetailView.as_view(), name='cart-items-detail'),
    path('offers', OffersView.as_view(), name='offers'),

    # Campaigns & Bids
    path('campaigns', CampaignListCreateView.as_view(), name='campaign-list-create'),
    path('campaigns/<str:pk>', CampaignDetailView.as_view(), name='campaign-detail'),
    path('campaigns/<str:pk>/bids', CampaignBidsView.as_view(), name='campaign-bids'),
    path('campaigns/<str:pk>/bids/<str:bid_id>/select', CampaignBidSelectView.as_view(), name='campaign-bid-select'),

    # Orders & Escrow
    path('orders', OrderListCreateView.as_view(), name='order-list-create'),
    path('orders/<str:pk>', OrderDetailView.as_view(), name='order-detail'),
    path('orders/<str:pk>/pay', OrderPayView.as_view(), name='order-pay'),
    path('orders/<str:pk>/confirm-payment-stub', OrderConfirmStubView.as_view(), name='order-confirm-stub'),
    path('orders/<str:pk>/submit-draft', OrderSubmitDraftView.as_view(), name='order-submit-draft'),
    path('orders/<str:pk>/request-changes', OrderRequestChangesView.as_view(), name='order-request-changes'),
    path('orders/<str:pk>/approve', OrderApproveView.as_view(), name='order-approve'),
    path('orders/<str:pk>/messages', OrderMessagesView.as_view(), name='order-messages'),

    # Dashboard & Reporting
    path('dashboard/summary', DashboardSummaryView.as_view(), name='dashboard-summary'),
    path('dashboard/todos/<str:pk>', DashboardTodoView.as_view(), name='dashboard-todo'),
    path('lists', ShortlistListCreateView.as_view(), name='shortlists-list-create'),
    path('lists/<str:pk>', ShortlistDetailView.as_view(), name='shortlist-detail'),
    path('lists/<str:pk>/creators', ShortlistCreatorManageView.as_view(), name='shortlist-add-creator'),
    path('lists/<str:pk>/creators/<str:creator_id>', ShortlistCreatorManageView.as_view(), name='shortlist-remove-creator'),
    path('lists/<str:pk>/duplicate', ShortlistDuplicateView.as_view(), name='shortlist-duplicate'),
    path('deliverables', DeliverablesListView.as_view(), name='deliverables-list'),
    path('deliverables/export', DeliverablesExportView.as_view(), name='deliverables-export'),
    path('deliverables/<str:pk>', DeliverableDetailView.as_view(), name='deliverable-detail'),
    path('reporting', ReportingView.as_view(), name='reporting'),
    path('reporting/export', ReportingExportView.as_view(), name='reporting-export'),

    # Admin Verifications & Approvals
    path('admin/verifications', AdminVerificationsListView.as_view(), name='admin-verifications-list'),
    path('admin/verifications/<str:pk>', AdminVerificationDetailView.as_view(), name='admin-verifications-detail'),
    path('admin/verifications/<str:pk>/approve', AdminVerificationApproveView.as_view(), name='admin-verifications-approve'),
    path('admin/verifications/<str:pk>/reject', AdminVerificationRejectView.as_view(), name='admin-verifications-reject'),
    path('admin/verifications/<str:pk>/request-info', AdminVerificationRequestInfoView.as_view(), name='admin-verifications-request-info'),
]

