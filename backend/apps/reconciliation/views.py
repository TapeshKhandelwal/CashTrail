from drf_spectacular.utils import OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.models import User
from apps.accounts.permissions import HasRole, IsAdminOrBranchManager, IsAgent
from apps.accounts.scoping import scope_queryset
from apps.core.idempotency import (
    IDEMPOTENCY_KEY_PARAMETER,
    created_or_replayed,
    require_idempotency_key,
)
from apps.core.schema import error_responses

from . import selectors, services
from .filters import CashSubmissionFilter, DiscrepancyFilter
from .serializers import (
    AgentsSummarySerializer,
    BranchSummarySerializer,
    CashSubmissionCreateSerializer,
    CashSubmissionDetailSerializer,
    CashSubmissionSerializer,
    DiscrepancyCreateSerializer,
    DiscrepancyResolveSerializer,
    DiscrepancySerializer,
    SubmissionApproveSerializer,
    SubmissionRejectSerializer,
    SummaryQuerySerializer,
)

CanReviewDiscrepancies = HasRole(User.Role.ADMIN, User.Role.BRANCH_MANAGER, User.Role.FINANCE)


@extend_schema_view(
    list=extend_schema(summary="List cash submissions", responses=CashSubmissionSerializer),
    retrieve=extend_schema(
        summary="Cash submission with its receipts and discrepancies",
        responses={200: CashSubmissionDetailSerializer, **error_responses(404)},
    ),
)
class CashSubmissionViewSet(
    mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet
):
    """Agents hand cash over to their branch; managers count it and approve or reject."""

    filterset_class = CashSubmissionFilter
    search_fields = (
        "submission_number",
        "agent__username",
        "agent__first_name",
        "agent__last_name",
    )
    ordering_fields = ("submitted_at", "reviewed_at", "expected_amount", "received_amount")
    ordering = ("-submitted_at", "-id")

    def get_queryset(self):
        queryset = (
            selectors.cash_submissions()
            if self.action == "list"
            else selectors.cash_submission_details()
        )
        return scope_queryset(queryset, self.request.user, agent_field="agent")

    def get_serializer_class(self):
        return CashSubmissionSerializer if self.action == "list" else CashSubmissionDetailSerializer

    def get_permissions(self):
        if self.action == "create":
            return [IsAgent()]
        if self.action in ("approve", "reject"):
            return [IsAdminOrBranchManager()]
        return [IsAuthenticated()]

    @extend_schema(
        summary="Submit collected cash to the branch",
        parameters=[IDEMPOTENCY_KEY_PARAMETER],
        request=CashSubmissionCreateSerializer,
        responses={
            201: CashSubmissionDetailSerializer,
            200: OpenApiResponse(
                CashSubmissionDetailSerializer, description="Replay of an earlier request."
            ),
            **error_responses(400, 403, 404, 409, 422),
        },
    )
    def create(self, request):
        idempotency_key = require_idempotency_key(request)
        serializer = CashSubmissionCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        submission, created = services.create_submission(
            request.user, idempotency_key=idempotency_key, **serializer.validated_data
        )
        return created_or_replayed(self._detail(submission), created=created)

    @extend_schema(
        summary="Approve after counting the cash",
        description=(
            "Any difference between expected and received cash needs a reason code and remarks "
            "and opens a CASH_SHORTAGE or CASH_EXCESS discrepancy."
        ),
        request=SubmissionApproveSerializer,
        responses={200: CashSubmissionDetailSerializer, **error_responses(400, 403, 404, 409, 422)},
    )
    @action(detail=True, methods=["post"])
    def approve(self, request, pk=None):
        submission = self.get_object()
        serializer = SubmissionApproveSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        submission = services.approve_submission(
            request.user, submission, **serializer.validated_data
        )
        return Response(self._detail(submission))

    @extend_schema(
        summary="Reject and return the receipts to the agent",
        request=SubmissionRejectSerializer,
        responses={200: CashSubmissionDetailSerializer, **error_responses(400, 403, 404, 409, 422)},
    )
    @action(detail=True, methods=["post"])
    def reject(self, request, pk=None):
        submission = self.get_object()
        serializer = SubmissionRejectSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        submission = services.reject_submission(
            request.user, submission, **serializer.validated_data
        )
        return Response(self._detail(submission))

    def _detail(self, submission):
        submission = selectors.cash_submission_details().get(pk=submission.pk)
        context = self.get_serializer_context()
        return CashSubmissionDetailSerializer(submission, context=context).data


@extend_schema_view(
    list=extend_schema(summary="List discrepancies"),
    retrieve=extend_schema(responses={200: DiscrepancySerializer, **error_responses(404)}),
)
class DiscrepancyViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    """Differences found at the branch count, bank deposit or settlement, and their resolution."""

    serializer_class = DiscrepancySerializer
    filterset_class = DiscrepancyFilter
    ordering_fields = ("created_at", "amount", "resolved_at")
    ordering = ("-created_at", "-id")

    def get_queryset(self):
        return scope_queryset(selectors.discrepancies(), self.request.user, agent_field="agent")

    def get_permissions(self):
        if self.action in ("create", "resolve"):
            return [CanReviewDiscrepancies()]
        return [IsAuthenticated()]

    @extend_schema(
        summary="Record a discrepancy manually",
        description=(
            "Cash shortage/excess against an approved submission (branch manager, admin); "
            "deposit, settlement or gateway mismatches against a bank deposit (finance, admin; "
            "branch managers may raise deposit mismatches for their branch)."
        ),
        request=DiscrepancyCreateSerializer,
        responses={201: DiscrepancySerializer, **error_responses(400, 403, 404, 422)},
    )
    def create(self, request):
        serializer = DiscrepancyCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        discrepancy = services.raise_discrepancy(request.user, **serializer.validated_data)
        return Response(self._detail(discrepancy), status=201)

    @extend_schema(
        summary="Resolve or write off",
        description=(
            "Cash discrepancies are closed by the branch manager or an admin; deposit, settlement "
            "and gateway mismatches by finance or an admin."
        ),
        request=DiscrepancyResolveSerializer,
        responses={200: DiscrepancySerializer, **error_responses(400, 403, 404, 409, 422)},
    )
    @action(detail=True, methods=["post"])
    def resolve(self, request, pk=None):
        discrepancy = self.get_object()
        serializer = DiscrepancyResolveSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        discrepancy = services.resolve_discrepancy(
            request.user, discrepancy, **serializer.validated_data
        )
        return Response(self._detail(discrepancy))

    def _detail(self, discrepancy):
        discrepancy = selectors.discrepancies().get(pk=discrepancy.pk)
        return DiscrepancySerializer(discrepancy, context=self.get_serializer_context()).data


class BranchSummaryView(APIView):
    permission_classes = [HasRole(User.Role.ADMIN, User.Role.BRANCH_MANAGER, User.Role.FINANCE)]

    @extend_schema(
        summary="Branch reconciliation summary",
        description=(
            "Flows (expected, collected, received, deposited, settled) cover the date range; "
            "positions (held by agents, pending verification, at branch, pending settlement, "
            "open discrepancies) are as of now. Branch managers see their own branch."
        ),
        parameters=[SummaryQuerySerializer],
        responses={200: BranchSummarySerializer, **error_responses(400, 403)},
    )
    def get(self, request):
        params = _summary_params(request)
        summary = selectors.branch_summary(
            request.user,
            date_from=params["date_from"],
            date_to=params["date_to"],
            branch_id=params.get("branch"),
        )
        return Response(BranchSummarySerializer(summary).data)


class AgentsSummaryView(APIView):
    @extend_schema(
        summary="Per-agent collections, hand-overs and cash-in-hand ageing",
        description=(
            "Collections and hand-overs cover the date range; cash in hand and its ageing are as "
            "of now. Branch managers see their branch's agents and agents see themselves."
        ),
        parameters=[SummaryQuerySerializer],
        responses={200: AgentsSummarySerializer, **error_responses(400)},
    )
    def get(self, request):
        params = _summary_params(request)
        summary = selectors.agents_summary(
            request.user,
            date_from=params["date_from"],
            date_to=params["date_to"],
            branch_id=params.get("branch"),
        )
        return Response(AgentsSummarySerializer(summary).data)


def _summary_params(request) -> dict:
    serializer = SummaryQuerySerializer(data=request.query_params)
    serializer.is_valid(raise_exception=True)
    return serializer.validated_data
