from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework.viewsets import ReadOnlyModelViewSet

from apps.accounts.permissions import IsAdminOrFinance, IsBranchManager
from apps.accounts.scoping import ScopedQuerysetMixin
from apps.core.schema import error_responses

from . import selectors
from .filters import AuditLogFilter
from .models import AuditLog
from .serializers import AuditLogSerializer


@extend_schema_view(
    list=extend_schema(responses={200: AuditLogSerializer(many=True), **error_responses(400)}),
    retrieve=extend_schema(responses={200: AuditLogSerializer, **error_responses(404)}),
)
class AuditLogViewSet(ScopedQuerysetMixin, ReadOnlyModelViewSet):
    """The append-only audit trail.

    Admin and finance read every entry. A branch manager reads entries whose record
    belongs to their branch (customers, loans, receipts, submissions, discrepancies,
    cash deposits and branch staff); entries without a branch, such as gateway
    settlements or bank accounts, stay with admin and finance. Agents have no access.
    """

    queryset = AuditLog.objects.select_related("actor", "branch")
    serializer_class = AuditLogSerializer
    permission_classes = [IsAdminOrFinance | IsBranchManager]
    filterset_class = AuditLogFilter
    search_fields = ("entity_id", "actor__username")
    ordering_fields = ("created_at", "id")
    ordering = ("-created_at", "-id")

    def paginate_queryset(self, queryset):
        page = super().paginate_queryset(queryset)
        # Look up the references for the whole page at once rather than row by row.
        self.entity_references = selectors.entity_references(page if page is not None else queryset)
        return page

    def get_serializer_context(self):
        context = super().get_serializer_context()
        if hasattr(self, "entity_references"):
            context["entity_references"] = self.entity_references
        return context
