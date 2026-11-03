from django.urls import path
from .views import (
    DashboardSummaryView,
    DashboardTodoView,
    ShortlistListCreateView,
    ShortlistDetailView,
    ShortlistCreatorManageView,
    ShortlistDuplicateView,
    DeliverablesListView,
    DeliverableDetailView,
    DeliverablesExportView,
    ReportingView,
    ReportingExportView,
)

urlpatterns = [
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
]

