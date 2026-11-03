from django.urls import path
from .views import (
    CampaignListCreateView,
    CampaignDetailView,
    CampaignBidsView,
    CampaignBidSelectView,
)

urlpatterns = [
    path('campaigns', CampaignListCreateView.as_view(), name='campaign-list-create'),
    path('campaigns/<str:pk>', CampaignDetailView.as_view(), name='campaign-detail'),
    path('campaigns/<str:pk>/bids', CampaignBidsView.as_view(), name='campaign-bids'),
    path('campaigns/<str:pk>/bids/<str:bid_id>/select', CampaignBidSelectView.as_view(), name='campaign-bid-select'),
]

