from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter
from rest_framework.response import Response

from apps.accounts.permissions import (
    IsAdminOrBranchManager,
    IsAgent,
    IsFinance,
    ReadOnly,
)
from apps.accounts.scoping import ScopedQuerysetMixin
from apps.core.schema import error_responses
from apps.customers.filters import CustomerSearchFilter

from . import selectors, services
from .filters import LoanFilter
from .models import Loan
from .serializers import (
    InstallmentSerializer,
    LoanCreateSerializer,
    LoanSerializer,
    LoanTermsSerializer,
    RepaymentSerializer,
    SchedulePreviewSerializer,
)


class LoanViewSet(
    ScopedQuerysetMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """Loans are never deleted; terms are editable only until the first repayment."""

    queryset = Loan.objects.all()
    serializer_class = LoanSerializer
    permission_classes = [IsAdminOrBranchManager | ((IsAgent | IsFinance) & ReadOnly)]
    scope_agent_field = "customer__assigned_agent"
    filterset_class = LoanFilter
    filter_backends = [DjangoFilterBackend, CustomerSearchFilter, OrderingFilter]
    search_fields = (
        "loan_number",
        "customer__full_name",
        "customer__customer_code",
        "customer__phone",
    )
    ordering_fields = (
        "created_at",
        "disbursed_on",
        "principal",
        "loan_number",
        "overdue_amount",
        "next_due_date",
    )
    ordering = ("-created_at", "-pk")

    def get_queryset(self):
        return selectors.loans_with_balances(super().get_queryset())

    @extend_schema(
        request=LoanCreateSerializer,
        responses={201: LoanSerializer, **error_responses(400, 403, 404, 422)},
    )
    def create(self, request):
        serializer = LoanCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        loan = services.create_loan(request.user, **serializer.validated_data)
        return Response(
            self.get_serializer(selectors.get_loan(loan.pk)).data, status=status.HTTP_201_CREATED
        )

    @extend_schema(
        request=LoanTermsSerializer,
        responses={200: LoanSerializer, **error_responses(400, 403, 404, 409, 422)},
        description="Correct loan terms before any repayment exists. The tenure is fixed.",
    )
    def partial_update(self, request, pk=None):
        loan = self.get_object()
        serializer = LoanTermsSerializer(data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        services.update_loan_terms(request.user, loan, **serializer.validated_data)
        return Response(self.get_serializer(selectors.get_loan(loan.pk)).data)

    @extend_schema(
        parameters=[LoanTermsSerializer],
        responses={200: SchedulePreviewSerializer, **error_responses(400, 403, 422)},
        description="EMI and installment schedule for the given terms; nothing is saved.",
    )
    @action(
        detail=False,
        url_path="schedule-preview",
        permission_classes=[IsAdminOrBranchManager],
        filter_backends=[],
        pagination_class=None,
    )
    def schedule_preview(self, request):
        serializer = LoanTermsSerializer(data=request.query_params)
        serializer.is_valid(raise_exception=True)
        schedule = services.build_schedule(**serializer.validated_data)
        return Response(SchedulePreviewSerializer(schedule).data)

    @extend_schema(responses={200: InstallmentSerializer(many=True), **error_responses(404)})
    @action(detail=True, filter_backends=[], pagination_class=None)
    def schedule(self, request, pk=None):
        installments = selectors.loan_schedule(self.get_object())
        return Response(InstallmentSerializer(installments, many=True).data)

    @extend_schema(responses={200: RepaymentSerializer(many=True), **error_responses(404)})
    @action(detail=True, filter_backends=[])
    def repayments(self, request, pk=None):
        page = self.paginate_queryset(selectors.loan_repayments(self.get_object()))
        return self.get_paginated_response(RepaymentSerializer(page, many=True).data)
