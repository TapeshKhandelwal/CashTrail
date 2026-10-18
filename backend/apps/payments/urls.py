from django.urls import path
from rest_framework.routers import SimpleRouter

from .views import (
    CashfreeWebhookView,
    GatewayConfigView,
    GatewayOrderViewSet,
    MockPayView,
    RazorpayWebhookView,
    VerifyPaymentView,
    WebhookEventViewSet,
)

router = SimpleRouter(trailing_slash=True)
router.register("payments/orders", GatewayOrderViewSet, basename="gateway-order")
router.register("payments/webhook-events", WebhookEventViewSet, basename="webhook-event")

urlpatterns = [
    path("payments/config/", GatewayConfigView.as_view(), name="payment-config"),
    path("payments/verify/", VerifyPaymentView.as_view(), name="payment-verify"),
    path("payments/mock/<int:pk>/pay/", MockPayView.as_view(), name="payment-mock-pay"),
    path("payments/webhooks/razorpay/", RazorpayWebhookView.as_view(), name="payment-webhook"),
    path(
        "payments/webhooks/cashfree/",
        CashfreeWebhookView.as_view(),
        name="payment-webhook-cashfree",
    ),
    *router.urls,
]
