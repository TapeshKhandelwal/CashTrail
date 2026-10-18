from django_filters.rest_framework import DjangoFilterBackend
from drf_spectacular.utils import extend_schema, extend_schema_view
from rest_framework import generics, mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.filters import OrderingFilter, SearchFilter
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.accounts.permissions import IsAdminOrBranchManager, IsAgent, ReadOnly
from apps.accounts.scoping import ScopedQuerysetMixin, scope_queryset
from apps.core.schema import error_responses
from apps.loans import selectors as loan_selectors
from apps.loans.models import Loan
from apps.loans.serializers import LoanSerializer

from . import selectors, services
from .filters import AgentRouteFilter, CustomerFilter, CustomerSearchFilter
from .models import Customer
from .serializers import (
    CustomerAssignSerializer,
    CustomerCreateSerializer,
    CustomerDetailSerializer,
    CustomerSerializer,
    CustomerUpdateSerializer,
)

SEARCH_FIELDS = ("full_name", "phone", "customer_code")


@extend_schema_view(
    list=extend_schema(summary="List customers in your scope with their dues"),
    retrieve=extend_schema(summary="Customer with dues and a summary of each loan"),
    create=extend_schema(
        summary="Create a customer",
        request=CustomerCreateSerializer,
        responses={201: CustomerDetailSerializer, **error_responses(400, 403, 404, 422)},
    ),
    partial_update=extend_schema(
        summary="Update contact details or (de)activate a customer",
        request=CustomerUpdateSerializer,
        responses={200: CustomerDetailSerializer, **error_responses(400, 403, 404, 422)},
    ),
)
class CustomerViewSet(
    ScopedQuerysetMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """Customers are never deleted; deactivate them instead."""

    queryset = Customer.objects.all()
    permission_classes = [IsAuthenticated & (IsAdminOrBranchManager | ReadOnly)]
    scope_agent_field = "assigned_agent"
    filterset_class = CustomerFilter
    filter_backends = [DjangoFilterBackend, CustomerSearchFilter, OrderingFilter]
    search_fields = SEARCH_FIELDS
    ordering_fields = (
        "full_name",
        "customer_code",
        "created_at",
        "outstanding",
        "overdue_amount",
        "next_due_date",
    )
    ordering = ("full_name", "pk")

    def get_queryset(self):
        queryset = super().get_queryset()
        if self.action == "retrieve":
            return selectors.customer_detail(queryset)
        return selectors.customer_list(queryset)

    def get_serializer_class(self):
        return CustomerDetailSerializer if self.action == "retrieve" else CustomerSerializer

    def create(self, request):
        serializer = CustomerCreateSerializer(
            data=request.data, context=self.get_serializer_context()
        )
        serializer.is_valid(raise_exception=True)
        customer = services.create_customer(request.user, **serializer.validated_data)
        return self._detail_response(customer, status.HTTP_201_CREATED)

    def partial_update(self, request, pk=None):
        customer = self.get_object()
        serializer = CustomerUpdateSerializer(customer, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        customer = services.update_customer(request.user, customer, **serializer.validated_data)
        return self._detail_response(customer)

    @extend_schema(
        summary="Assign the customer to an agent of their branch",
        request=CustomerAssignSerializer,
        responses={200: CustomerDetailSerializer, **error_responses(400, 403, 404, 422)},
    )
    @action(detail=True, methods=["post"])
    def assign(self, request, pk=None):
        customer = self.get_object()
        serializer = CustomerAssignSerializer(
            data=request.data, context=self.get_serializer_context()
        )
        serializer.is_valid(raise_exception=True)
        customer = services.assign_customer(
            request.user, customer, serializer.validated_data["agent"]
        )
        return self._detail_response(customer)

    @extend_schema(
        summary="Loans of the customer, newest first",
        description="Each loan carries the same balances as `GET /api/loans/`.",
        responses={200: LoanSerializer(many=True), **error_responses(404)},
    )
    @action(detail=True, methods=["get"], filter_backends=[])
    def loans(self, request, pk=None):
        customer = self.get_object()
        loans = scope_queryset(
            Loan.objects.filter(customer=customer),
            request.user,
            agent_field="customer__assigned_agent",
        )
        loans = loan_selectors.loans_with_balances(loans).order_by("-disbursed_on", "-pk")
        page = self.paginate_queryset(loans)
        serializer = LoanSerializer(page, many=True, context=self.get_serializer_context())
        return self.get_paginated_response(serializer.data)

    def _detail_response(self, customer: Customer, status_code: int = status.HTTP_200_OK):
        customer = selectors.customer_detail(Customer.objects.filter(pk=customer.pk)).get()
        serializer = CustomerDetailSerializer(customer, context=self.get_serializer_context())
        return Response(serializer.data, status=status_code)


@extend_schema(summary="The signed-in agent's customers: overdue first, then due today")
class AgentCustomerListView(generics.ListAPIView):
    serializer_class = CustomerSerializer
    permission_classes = [IsAgent]
    filter_backends = [DjangoFilterBackend, SearchFilter]
    filterset_class = AgentRouteFilter
    search_fields = SEARCH_FIELDS

    def get_queryset(self):
        if getattr(self, "swagger_fake_view", False):
            return Customer.objects.none()
        return selectors.agent_route(self.request.user)
