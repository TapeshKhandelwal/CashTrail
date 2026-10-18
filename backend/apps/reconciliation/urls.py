from django.urls import path
from rest_framework.routers import SimpleRouter

from .views import AgentsSummaryView, BranchSummaryView, CashSubmissionViewSet, DiscrepancyViewSet

router = SimpleRouter(trailing_slash=True)
router.register("submissions", CashSubmissionViewSet, basename="submission")
router.register("discrepancies", DiscrepancyViewSet, basename="discrepancy")

urlpatterns = [
    path(
        "reconciliation/branch-summary/",
        BranchSummaryView.as_view(),
        name="reconciliation-branch-summary",
    ),
    path(
        "reconciliation/agents-summary/",
        AgentsSummaryView.as_view(),
        name="reconciliation-agents-summary",
    ),
    *router.urls,
]
