from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.permissions import IsAgent
from apps.accounts.scoping import ScopedQuerysetMixin
from apps.core.dates import business_date
from apps.core.idempotency import (
    IDEMPOTENCY_KEY_PARAMETER,
    created_or_replayed,
    require_idempotency_key,
)
from apps.core.schema import error_responses

from . import selectors, services
from .filters import CollectionFilter
from .serializers import (
    CollectionCreateSerializer,
    CollectionDetailSerializer,
    CollectionSerializer,
    DailySummaryQuerySerializer,
    DailySummarySerializer,
    VoidCollectionSerializer,
)


@extend_schema_view(
    list=extend_schema(summary="List repayments in your scope"),
    retrieve=extend_schema(
        summary="Receipt with allocations and lifecycle timeline",
        responses={200: CollectionDetailSerializer, **error_responses(404)},
    ),
)
class CollectionViewSet(
    ScopedQuerysetMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    queryset = selectors.collection_list_queryset()
    scope_agent_field = "agent"
    filterset_class = CollectionFilter
    search_fields = (
        "receipt_number",
        "loan__loan_number",
        "customer__full_name",
        "customer__customer_code",
        "gateway_payment_id",
    )
    ordering_fields = ("collected_at", "amount", "receipt_number")
    ordering = ("-collected_at", "-id")

    def get_queryset(self):
        collections = super().get_queryset()
        if self.action in ("create", "retrieve", "void"):
            collections = selectors.with_receipt_details(collections)
        return collections

    def get_permissions(self):
        if self.action in ("create", "void"):
            return [IsAgent()]
        return [IsAuthenticated()]

    def get_serializer_class(self):
        if self.action == "list":
            return CollectionSerializer
        return CollectionDetailSerializer

    @extend_schema(
        summary="Record a cash repayment",
        description=(
            "Applies the amount to the oldest unpaid installments. Retrying with the same "
            "`Idempotency-Key` returns the original receipt with `200` and "
            "`Idempotent-Replayed: true`. A matching receipt (same loan, amount and agent) "
            "within the duplicate window is refused with `409 POSSIBLE_DUPLICATE` unless "
            "`confirm_duplicate` is true."
        ),
        parameters=[IDEMPOTENCY_KEY_PARAMETER],
        request=CollectionCreateSerializer,
        responses={
            201: CollectionDetailSerializer,
            200: CollectionDetailSerializer,
            **error_responses(400, 403, 404, 409, 422),
        },
    )
    def create(self, request):
        idempotency_key = require_idempotency_key(request)
        params = CollectionCreateSerializer(data=request.data)
        params.is_valid(raise_exception=True)
        data = params.validated_data

        collection, replayed = services.record_collection(
            actor=request.user,
            loan=selectors.get_collectable_loan(request.user, data["loan_id"]),
            amount=data["amount"],
            mode=data["mode"],
            idempotency_key=idempotency_key,
            confirm_duplicate=data["confirm_duplicate"],
            remarks=data["remarks"],
        )
        receipt = self.get_queryset().get(pk=collection.pk)
        return created_or_replayed(CollectionDetailSerializer(receipt).data, created=not replayed)

    @extend_schema(
        summary="Void your own cash receipt before it is submitted",
        request=VoidCollectionSerializer,
        responses={200: CollectionDetailSerializer, **error_responses(400, 403, 404, 409, 422)},
    )
    @action(detail=True, methods=["post"])
    def void(self, request, pk=None):
        params = VoidCollectionSerializer(data=request.data)
        params.is_valid(raise_exception=True)
        collection = services.void_collection(
            actor=request.user,
            collection=self.get_object(),
            reason=params.validated_data["reason"],
        )
        receipt = self.get_queryset().get(pk=collection.pk)
        return Response(CollectionDetailSerializer(receipt).data)

    @extend_schema(
        summary="Collection totals for a day",
        description=(
            "Agents see their own totals, branch managers their branch, and admin and finance "
            "every branch; `branch` and `agent` narrow that scope further. `unsubmitted_cash` "
            "is cash still held by agents, whatever day it was collected."
        ),
        parameters=[
            OpenApiParameter("date", type=OpenApiTypes.DATE, description="Defaults to today."),
            OpenApiParameter("branch", type=int),
            OpenApiParameter("agent", type=int),
        ],
        responses={200: DailySummarySerializer, **error_responses(400)},
    )
    @action(
        detail=False,
        methods=["get"],
        url_path="daily-summary",
        filter_backends=[],
        pagination_class=None,
    )
    def daily_summary(self, request):
        params = DailySummaryQuerySerializer(data=request.query_params)
        params.is_valid(raise_exception=True)
        query = params.validated_data

        collections = self.get_queryset()
        if "branch" in query:
            collections = collections.filter(branch_id=query["branch"])
        if "agent" in query:
            collections = collections.filter(agent_id=query["agent"])
        summary = selectors.daily_summary(collections, query.get("date") or business_date())
        return Response(DailySummarySerializer(summary).data)
