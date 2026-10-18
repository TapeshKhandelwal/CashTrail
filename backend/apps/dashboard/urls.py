from django.urls import path

from . import views

urlpatterns = [
    path("dashboard/summary/", views.DashboardSummaryView.as_view(), name="dashboard-summary"),
    path("dashboard/trend/", views.DashboardTrendView.as_view(), name="dashboard-trend"),
    path(
        "dashboard/lifecycle/",
        views.DashboardLifecycleView.as_view(),
        name="dashboard-lifecycle",
    ),
    path("dashboard/branches/", views.BranchBreakdownView.as_view(), name="dashboard-branches"),
    path("dashboard/agents/", views.AgentBreakdownView.as_view(), name="dashboard-agents"),
    path(
        "reports/collections.csv",
        views.CollectionsReportView.as_view(),
        name="report-collections",
    ),
    path(
        "reports/submissions.csv",
        views.SubmissionsReportView.as_view(),
        name="report-submissions",
    ),
    path("reports/deposits.csv", views.DepositsReportView.as_view(), name="report-deposits"),
    path(
        "reports/discrepancies.csv",
        views.DiscrepanciesReportView.as_view(),
        name="report-discrepancies",
    ),
]
