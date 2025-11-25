from django.urls import path
from .views import (
    KPIListCreateView,
    KPIDetailView,
    KPIEntryListView,
    KPIEntryDetailView,
    KPIActionListCreateView,
    KPIActionDetailView,
    KPIStatsView,
    KPITrendAnalysisView,
    UserKPIsView,
    KPIAssignmentListCreateView,
    KPIAssignmentDetailView,
    KPIReportListCreateView,
    KPIReportDetailView,
    KPIReportSubmitView,
    KPIReportApproveView,
    KPIApprovalsView,
)

app_name = 'kpis'

urlpatterns = [
    # User KPI endpoints
    path('my-kpis/', UserKPIsView.as_view(), name='user-kpis'),
    
    # KPI endpoints
    path('', KPIListCreateView.as_view(), name='kpi-list-create'),
    path('<uuid:pk>/', KPIDetailView.as_view(), name='kpi-detail'),
    path('<uuid:kpi_id>/stats/', KPIStatsView.as_view(), name='kpi-stats'),
    path('<uuid:kpi_id>/trends/', KPITrendAnalysisView.as_view(), name='kpi-trend-analysis'),
    
    # KPI Entry endpoints
    path('entries/', KPIEntryListView.as_view(), name='kpi-entry-list'),
    path('entries/<uuid:pk>/', KPIEntryDetailView.as_view(), name='kpi-entry-detail'),
    
    # KPI Action endpoints
    path('kpi-actions/', KPIActionListCreateView.as_view(), name='kpi-action-list-create'),
    path('kpi-actions/<uuid:pk>/', KPIActionDetailView.as_view(), name='kpi-action-detail'),
    
    # KPI Assignment endpoints
    path('kpi-assignments/', KPIAssignmentListCreateView.as_view(), name='kpi-assignment-list-create'),
    path('kpi-assignments/<uuid:pk>/', KPIAssignmentDetailView.as_view(), name='kpi-assignment-detail'),
    
    # KPI Report endpoints
    path('kpi-reports/', KPIReportListCreateView.as_view(), name='kpi-report-list-create'),
    path('kpi-reports/<uuid:pk>/', KPIReportDetailView.as_view(), name='kpi-report-detail'),
    path('kpi-reports/<uuid:pk>/submit/', KPIReportSubmitView.as_view(), name='kpi-report-submit'),
    path('kpi-reports/<uuid:pk>/approve/', KPIReportApproveView.as_view(), name='kpi-report-approve'),
    path('kpi-reports/approvals/', KPIApprovalsView.as_view(), name='kpi-report-pending-approvals'),
]

