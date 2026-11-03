from django.urls import path
from .views import (
    CreatorSuggestionsView,
    CreatorFiltersView,
    CreatorListView,
    CreatorDetailView,
    CreatorPackagesView,
    CreatorReviewsView,
    CreatorSimilarView,
    CreatorSaveView,
)

urlpatterns = [
    path('creators/suggestions', CreatorSuggestionsView.as_view(), name='creator-suggestions'),
    path('creators/filters', CreatorFiltersView.as_view(), name='creator-filters'),
    path('creators', CreatorListView.as_view(), name='creator-list'),
    path('creators/<str:pk>', CreatorDetailView.as_view(), name='creator-detail'),
    path('creators/<str:pk>/packages', CreatorPackagesView.as_view(), name='creator-packages'),
    path('creators/<str:pk>/reviews', CreatorReviewsView.as_view(), name='creator-reviews'),
    path('creators/<str:pk>/similar', CreatorSimilarView.as_view(), name='creator-similar'),
    path('creators/<str:pk>/save', CreatorSaveView.as_view(), name='creator-save'),
]

