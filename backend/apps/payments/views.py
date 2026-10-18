from drf_spectacular.types import OpenApiTypes
from drf_spectacular.utils import OpenApiParameter, extend_schema, extend_schema_view
from rest_framework import mixins, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.accounts.permissions import IsAdminOrFinance, IsAgent
from apps.accounts.scoping import ScopedQuerysetMixin
from apps.collections import selectors as collection_selectors
from apps.core.idempotency import (
    IDEMPOTENCY_KEY_PARAMETER,
    created_or_replayed,
    require_idempotency_key,
)
from apps.core.schema import error_responses

from . import selectors, services
from .exceptions import InvalidSignature
from .filters import GatewayOrderFilter, WebhookEventFilter
from .models import GatewayOrder, GatewayProvider, WebhookEvent
from .providers import get_provider
from .serializers import (
    GatewayConfigSerializer,
    GatewayOrderSerializer,
    MockPaySerializer,
    OrderCreatedSerializer,
    OrderCreateSerializer,
    PaymentResultSerializer,
    VerifyPaymentSerializer,
    WebhookAckSerializer,
    WebhookEventSerializer,
)

SIGNATURE_HEADER = "X-Razorpay-Signature"
EVENT_ID_HEADER = "X-Razorpay-Event-Id"
CASHFREE_SIGNATURE_HEADER = "x-webhook-signature"
CASHFREE_TIMESTAMP_HEADER = "x-webhook-timestamp"


def _payment_result(order: GatewayOrder, *, payment_in_progress: bool = False) -> dict:
    receipt = None
    if order.collection_id:
        receipt = collection_selectors.with_receipt_details(
            collection_selectors.collection_list_queryset()
        ).get(pk=order.collection_id)
    return PaymentResultSerializer(
        {"order": order, "receipt": receipt, "payment_in_progress": payment_in_progress}
    ).data


@extend_schema_view(
    list=extend_schema(summary="List UPI payment orders in your scope"),
    retrieve=extend_schema(
        summary="UPI payment order",
        responses={200: GatewayOrderSerializer, **error_responses(404)},
    ),
)
class GatewayOrderViewSet(
    ScopedQuerysetMixin,
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    queryset = selectors.gateway_orders()
    serializer_class = GatewayOrderSerializer
    scope_branch_field = "loan__branch"
    scope_agent_field = "agent"
    filterset_class = GatewayOrderFilter
    search_fields = (
        "provider_order_id",
        "provider_payment_id",
        "receipt",
        "loan__loan_number",
        "loan__customer__full_name",
    )
    ordering_fields = ("created_at", "amount")
    ordering = ("-created_at", "-id")

    def get_permissions(self):
        if self.action == "create":
            return [IsAgent()]
        return [IsAuthenticated()]

    @extend_schema(
        summary="Raise a UPI payment order for a loan",
        description=(
            "Returns the order and the options for opening the gateway's checkout. The amount "
            "is reserved until the checkout window closes; asking again for the same amount "
            "on the same loan while an order is open returns that order with `200`."
        ),
        parameters=[IDEMPOTENCY_KEY_PARAMETER],
        request=OrderCreateSerializer,
        responses={
            201: OrderCreatedSerializer,
            200: OrderCreatedSerializer,
            **error_responses(400, 403, 404, 409, 422, 502),
        },
    )
    def create(self, request):
        idempotency_key = require_idempotency_key(request)
        params = OrderCreateSerializer(data=request.data)
        params.is_valid(raise_exception=True)
        data = params.validated_data

        order, created = services.create_order(
            request.user,
            loan=collection_selectors.get_collectable_loan(request.user, data["loan_id"]),
            amount=data["amount"],
            idempotency_key=idempotency_key,
        )
        order = self.get_queryset().get(pk=order.pk)
        body = OrderCreatedSerializer(
            {"order": order, "checkout": selectors.checkout_options(order, get_provider())}
        ).data
        return created_or_replayed(body, created=created)

    @extend_schema(
        summary="Check the order's payment with the gateway",
        description=(
            "Asks the gateway for the order's payment attempts and records the outcome: a "
            "captured payment issues the receipt (also when its webhook never arrived), and "
            "an order whose every attempt failed becomes `FAILED`. While the customer is "
            "still paying, the order is returned unchanged. This is how a Cashfree checkout "
            "is confirmed. Safe to repeat."
        ),
        request=None,
        responses={200: PaymentResultSerializer, **error_responses(404, 409, 422, 502)},
    )
    @action(detail=True, methods=["post"])
    def refresh(self, request, pk=None):
        order, in_progress = services.refresh_order(request.user, self.get_object())
        return Response(_payment_result(order, payment_in_progress=in_progress))


class VerifyPaymentView(APIView):
    permission_classes = [IsAgent]

    @extend_schema(
        summary="Confirm a checkout payment and issue the receipt",
        description=(
            "Send the ids and signature returned by the gateway's checkout. The signature is "
            "checked against the stored order; a payment already recorded (for example by "
            "the webhook) returns its receipt with `200` and `Idempotent-Replayed: true`. "
            "If the loan was paid off while the customer was paying, the order becomes "
            "`REFUND_DUE` and `receipt` is null."
        ),
        request=VerifyPaymentSerializer,
        responses={
            201: PaymentResultSerializer,
            200: PaymentResultSerializer,
            **error_responses(400, 403, 404, 409, 422),
        },
    )
    def post(self, request):
        params = VerifyPaymentSerializer(data=request.data)
        params.is_valid(raise_exception=True)
        data = params.validated_data

        order, replayed = services.verify_payment(
            request.user,
            provider_order_id=data["order_id"],
            payment_id=data["payment_id"],
            signature=data["signature"],
        )
        order = selectors.gateway_orders().get(pk=order.pk)
        return created_or_replayed(_payment_result(order), created=not replayed)


class MockPayView(APIView):
    permission_classes = [IsAgent]

    @extend_schema(
        summary="Complete checkout on the mock gateway",
        description="Available only when the mock gateway is active; otherwise `404`.",
        request=MockPaySerializer,
        responses={200: PaymentResultSerializer, **error_responses(400, 404, 409, 422)},
    )
    def post(self, request, pk: int):
        params = MockPaySerializer(data=request.data)
        params.is_valid(raise_exception=True)
        order = services.mock_pay(
            request.user, order_id=pk, outcome=params.validated_data["outcome"]
        )
        return Response(_payment_result(order))


class RazorpayWebhookView(APIView):
    """Signed by the gateway, so it needs no user authentication or CSRF token."""

    authentication_classes = []
    permission_classes = [AllowAny]

    @extend_schema(
        summary="Gateway webhook (payment.captured, order.paid, payment.failed)",
        description=(
            f"The `{SIGNATURE_HEADER}` header must be the HMAC-SHA256 of the raw body. "
            "Redeliveries of an event are acknowledged without being applied again."
        ),
        auth=[],
        parameters=[
            OpenApiParameter(SIGNATURE_HEADER, location=OpenApiParameter.HEADER, required=True),
            OpenApiParameter(EVENT_ID_HEADER, location=OpenApiParameter.HEADER),
        ],
        request=OpenApiTypes.OBJECT,
        responses={200: WebhookAckSerializer, **error_responses(400, 422)},
    )
    def post(self, request):
        # The signature covers the exact bytes received, so read them before any parsing.
        raw_body = request.body
        event, duplicate = services.handle_webhook(
            raw_body=raw_body,
            signature=request.headers.get(SIGNATURE_HEADER, ""),
            event_id=request.headers.get(EVENT_ID_HEADER, ""),
        )
        return _webhook_ack(event, duplicate)


class CashfreeWebhookView(APIView):
    """Signed by Cashfree, so it needs no user authentication or CSRF token."""

    authentication_classes = []
    permission_classes = [AllowAny]

    @extend_schema(
        summary="Cashfree webhook (PAYMENT_SUCCESS, PAYMENT_FAILED, PAYMENT_USER_DROPPED)",
        description=(
            f"`{CASHFREE_SIGNATURE_HEADER}` must be the base64 HMAC-SHA256 of "
            f"`{CASHFREE_TIMESTAMP_HEADER}` followed by the raw body, keyed with the Cashfree "
            "secret key. Accepted only while Cashfree is the active gateway. Redeliveries of "
            "an event are acknowledged without being applied again."
        ),
        auth=[],
        parameters=[
            OpenApiParameter(
                CASHFREE_SIGNATURE_HEADER, location=OpenApiParameter.HEADER, required=True
            ),
            OpenApiParameter(
                CASHFREE_TIMESTAMP_HEADER, location=OpenApiParameter.HEADER, required=True
            ),
        ],
        request=OpenApiTypes.OBJECT,
        responses={200: WebhookAckSerializer, **error_responses(400, 422)},
    )
    def post(self, request):
        raw_body = request.body
        if get_provider().code != GatewayProvider.CASHFREE:
            raise InvalidSignature("Cashfree is not the active payment gateway.")
        event, duplicate = services.handle_webhook(
            raw_body=raw_body,
            signature=request.headers.get(CASHFREE_SIGNATURE_HEADER, ""),
            timestamp=request.headers.get(CASHFREE_TIMESTAMP_HEADER, ""),
        )
        return _webhook_ack(event, duplicate)


def _webhook_ack(event: WebhookEvent, duplicate: bool) -> Response:
    if duplicate:
        return Response({"event_id": event.event_id, "status": "duplicate"})
    status = "processed" if event.processed_at else "failed"
    return Response({"event_id": event.event_id, "status": status})


@extend_schema_view(
    list=extend_schema(summary="Gateway webhooks received, newest first"),
    retrieve=extend_schema(
        summary="Gateway webhook", responses={200: WebhookEventSerializer, **error_responses(404)}
    ),
)
class WebhookEventViewSet(viewsets.ReadOnlyModelViewSet):
    """The webhook inbox.

    An event that could not be applied keeps its error for follow-up, e.g. one for an order
    we do not know or with an amount that does not match the order.
    """

    queryset = selectors.webhook_events()
    serializer_class = WebhookEventSerializer
    permission_classes = [IsAdminOrFinance]
    filterset_class = WebhookEventFilter
    search_fields = ("event_id", "order_id", "payment_id")
    ordering_fields = ("created_at",)
    ordering = ("-created_at", "-id")

    @extend_schema(
        summary="Apply a failed webhook again once its cause is fixed",
        description=(
            "Returns the event: `processed_at` is set when it applied, otherwise `error` holds "
            "the new reason."
        ),
        request=None,
        responses={200: WebhookEventSerializer, **error_responses(404, 409, 422)},
    )
    @action(detail=True, methods=["post"])
    def retry(self, request, pk=None):
        event = services.retry_webhook_event(request.user, self.get_object())
        return Response(self.get_serializer(self.get_queryset().get(pk=event.pk)).data)


class GatewayConfigView(APIView):
    @extend_schema(
        summary="Active payment gateway and its public checkout key",
        responses={200: GatewayConfigSerializer},
    )
    def get(self, request):
        return Response(GatewayConfigSerializer(selectors.gateway_config(get_provider())).data)
