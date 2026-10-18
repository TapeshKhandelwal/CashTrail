from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import mixins, status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.permissions import IsAdmin, ReadOnly
from apps.accounts.scoping import ScopedQuerysetMixin
from apps.core.schema import error_responses

from . import services
from .filters import BranchFilter
from .models import Branch
from .selectors import with_headcounts
from .serializers import BranchCreateSerializer, BranchSerializer, BranchUpdateSerializer


@extend_schema_view(
    list=extend_schema(summary="List branches (agents and managers see their own branch)"),
    retrieve=extend_schema(summary="Retrieve a branch with its headcounts"),
    create=extend_schema(
        summary="Create a branch",
        request=BranchCreateSerializer,
        responses={201: BranchSerializer, **error_responses(400, 403, 409, 422)},
    ),
    partial_update=extend_schema(
        summary="Update or (de)activate a branch",
        request=BranchUpdateSerializer,
        responses={200: BranchSerializer, **error_responses(400, 403, 404, 422)},
    ),
)
class BranchViewSet(
    ScopedQuerysetMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    queryset = Branch.objects.all()
    serializer_class = BranchSerializer
    permission_classes = [IsAuthenticated & (IsAdmin | ReadOnly)]
    scope_branch_field = "pk"
    scope_agent_field = "users"
    filterset_class = BranchFilter
    search_fields = ("code", "name", "city")
    ordering_fields = ("code", "name", "city", "created_at")
    ordering = ("code",)

    def get_queryset(self):
        return with_headcounts(super().get_queryset())

    def create(self, request):
        serializer = BranchCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        branch = services.create_branch(request.user, **serializer.validated_data)
        return self._respond(branch, status.HTTP_201_CREATED)

    def partial_update(self, request, pk=None):
        branch = self.get_object()
        serializer = BranchUpdateSerializer(branch, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        branch = services.update_branch(request.user, branch, **serializer.validated_data)
        return self._respond(branch, status.HTTP_200_OK)

    def _respond(self, branch: Branch, status_code: int) -> Response:
        branch = with_headcounts(Branch.objects.filter(pk=branch.pk)).get()
        return Response(self.get_serializer(branch).data, status=status_code)
