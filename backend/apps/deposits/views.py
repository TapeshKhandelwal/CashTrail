from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.accounts.models import User
from apps.accounts.permissions import (
    HasRole,
    IsAdmin,
    IsAdminOrBranchManager,
    IsAdminOrFinance,
    ReadOnly,
)
from apps.accounts.scoping import scope_queryset
from apps.core.idempotency import (
    IDEMPOTENCY_KEY_PARAMETER,
    created_or_replayed,
    require_idempotency_key,
)
from apps.core.schema import error_responses

from . import selectors, services
from .filters import BankAccountFilter, DepositFilter, GatewaySettlementFilter
from .serializers import (
    MAX_ITEMS_PER_BATCH,
    BankAccountSerializer,
    BankAccountWriteSerializer,
    DepositCreateSerializer,
    DepositDetailSerializer,
    DepositFailSerializer,
    DepositSerializer,
    DepositSettleSerializer,
    GatewaySettlementCreateSerializer,
    PendingCashQuerySerializer,
    PendingCashSerializer,
    UnsettledUpiQuerySerializer,
    UnsettledUpiSerializer,
)

CanViewDeposits = HasRole(User.Role.ADMIN, User.Role.BRANCH_MANAGER, User.Role.FINANCE)


def _detail_data(deposit) -> dict:
    return DepositDetailSerializer(selectors.deposit_details().get(pk=deposit.pk)).data


@extend_schema_view(
    list=extend_schema(summary="List company bank accounts"),
    retrieve=extend_schema(
        summary="Bank account", responses={200: BankAccountSerializer, **error_responses(404)}
    ),
)
class BankAccountViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.CreateModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """Company accounts that cash and gateway settlements land in. Account numbers are masked."""

    permission_classes = [IsAdmin | (CanViewDeposits & ReadOnly)]
    queryset = selectors.bank_accounts()
    serializer_class = BankAccountSerializer
    filterset_class = BankAccountFilter
    search_fields = ("bank_name", "account_name", "ifsc")
    ordering_fields = ("bank_name", "account_name", "created_at")
    http_method_names = ["get", "post", "patch", "head", "options"]

    @extend_schema(
        summary="Add a bank account",
        request=BankAccountWriteSerializer,
        responses={201: BankAccountSerializer, **error_responses(400, 403, 409)},
    )
    def create(self, request, *args, **kwargs):
        serializer = BankAccountWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        account = services.create_bank_account(request.user, **serializer.validated_data)
        return Response(BankAccountSerializer(account).data, status=201)

    @extend_schema(
        summary="Update a bank account",
        request=BankAccountWriteSerializer,
        responses={200: BankAccountSerializer, **error_responses(400, 403, 404, 409)},
    )
    def partial_update(self, request, *args, **kwargs):
        serializer = BankAccountWriteSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        account = services.update_bank_account(
            request.user, self.get_object(), **serializer.validated_data
        )
        return Response(BankAccountSerializer(account).data)


@extend_schema_view(
    list=extend_schema(
        summary="List bank deposits",
        description="Scoped by role: managers see their branch, finance and admins see all.",
    ),
    retrieve=extend_schema(
        summary="Bank deposit with its submissions and reconciliation chain",
        responses={200: DepositDetailSerializer, **error_responses(404)},
    ),
)
class DepositViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    queryset = selectors.deposits()
    filterset_class = DepositFilter
    search_fields = ("deposit_number", "reference_number", "settlement_reference")
    ordering_fields = ("deposit_date", "created_at", "deposited_amount", "settled_on")

    def get_permissions(self):
        if self.action in {"create", "pending_cash"}:
            return [IsAdminOrBranchManager()]
        if self.action in {"settle", "fail"}:
            return [IsAdminOrFinance()]
        return [CanViewDeposits()]

    def get_queryset(self):
        base = selectors.deposit_details() if self.action == "retrieve" else selectors.deposits()
        return scope_queryset(base, self.request.user)

    def get_serializer_class(self):
        return DepositDetailSerializer if self.action == "retrieve" else DepositSerializer

    @extend_schema(
        summary="Deposit approved branch cash",
        parameters=[IDEMPOTENCY_KEY_PARAMETER],
        request=DepositCreateSerializer,
        responses={
            201: DepositDetailSerializer,
            200: DepositDetailSerializer,
            **error_responses(400, 403, 404, 409, 422),
        },
    )
    def create(self, request, *args, **kwargs):
        idempotency_key = require_idempotency_key(request)
        serializer = DepositCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        deposit, created = services.create_deposit(
            request.user, idempotency_key=idempotency_key, **serializer.validated_data
        )
        return created_or_replayed(_detail_data(deposit), created=created)

    @extend_schema(
        summary="Confirm settlement from the bank statement",
        request=DepositSettleSerializer,
        responses={200: DepositDetailSerializer, **error_responses(400, 403, 404, 409, 422)},
    )
    @action(detail=True, methods=["post"])
    def settle(self, request, pk=None):
        serializer = DepositSettleSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        deposit = services.settle_deposit(
            request.user, self.get_object(), **serializer.validated_data
        )
        return Response(_detail_data(deposit))

    @extend_schema(
        summary="Mark a deposit as failed so its cash can be redeposited",
        request=DepositFailSerializer,
        responses={200: DepositDetailSerializer, **error_responses(400, 403, 404, 409, 422)},
    )
    @action(detail=True, methods=["post"])
    def fail(self, request, pk=None):
        serializer = DepositFailSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        deposit = services.fail_deposit(
            request.user, self.get_object(), reason=serializer.validated_data["reason"]
        )
        return Response(_detail_data(deposit))

    @extend_schema(
        summary="Approved cash at the branch awaiting deposit",
        parameters=[PendingCashQuerySerializer],
        responses={200: PendingCashSerializer, **error_responses(400, 403)},
    )
    @action(
        detail=False,
        methods=["get"],
        url_path="pending-cash",
        filter_backends=[],
        pagination_class=None,
    )
    def pending_cash(self, request):
        params = PendingCashQuerySerializer(data=request.query_params)
        params.is_valid(raise_exception=True)
        submissions = selectors.pending_cash_submissions(
            request.user, branch_id=params.validated_data.get("branch")
        )
        totals = selectors.pending_cash_total(submissions)
        listed = list(submissions[:MAX_ITEMS_PER_BATCH])
        data = {
            "count": totals.count,
            "total_amount": totals.total_amount,
            "has_more": totals.count > len(listed),
            "submissions": listed,
        }
        return Response(PendingCashSerializer(data).data)


@extend_schema_view(list=extend_schema(summary="List gateway (UPI) settlements"))
class GatewaySettlementViewSet(mixins.ListModelMixin, viewsets.GenericViewSet):
    """Gateway settlement batches; each settles captured UPI collections net of fee and tax."""

    permission_classes = [IsAdminOrFinance]
    queryset = selectors.gateway_settlements()
    serializer_class = DepositSerializer
    filterset_class = GatewaySettlementFilter
    search_fields = ("deposit_number", "reference_number")
    ordering_fields = ("settled_on", "created_at", "settled_amount")

    @extend_schema(
        summary="Record a gateway settlement",
        parameters=[IDEMPOTENCY_KEY_PARAMETER],
        request=GatewaySettlementCreateSerializer,
        responses={
            201: DepositDetailSerializer,
            200: DepositDetailSerializer,
            **error_responses(400, 403, 404, 409, 422),
        },
    )
    def create(self, request, *args, **kwargs):
        idempotency_key = require_idempotency_key(request)
        serializer = GatewaySettlementCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        settlement, created = services.record_gateway_settlement(
            request.user, idempotency_key=idempotency_key, **serializer.validated_data
        )
        return created_or_replayed(_detail_data(settlement), created=created)

    @extend_schema(
        summary="Captured UPI payments awaiting gateway settlement",
        parameters=[UnsettledUpiQuerySerializer],
        responses={200: UnsettledUpiSerializer, **error_responses(400, 403)},
    )
    @action(detail=False, methods=["get"], filter_backends=[], pagination_class=None)
    def pending(self, request):
        params = UnsettledUpiQuerySerializer(data=request.query_params)
        params.is_valid(raise_exception=True)
        collections = selectors.unsettled_upi_collections(params.validated_data.get("up_to_date"))
        totals = selectors.unsettled_upi_total(collections)
        listed = list(collections[:MAX_ITEMS_PER_BATCH])
        data = {
            "count": totals.count,
            "total_amount": totals.total_amount,
            "has_more": totals.count > len(listed),
            "collections": listed,
        }
        return Response(UnsettledUpiSerializer(data).data)
