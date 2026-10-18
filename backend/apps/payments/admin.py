from django.contrib import admin

from apps.core.admin import ReadOnlyAdminMixin

from .models import GatewayOrder, WebhookEvent


@admin.register(GatewayOrder)
class GatewayOrderAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
    list_display = (
        "provider_order_id",
        "provider",
        "loan",
        "agent",
        "amount",
        "status",
        "created_at",
    )
    list_filter = ("status", "provider")
    list_select_related = ("loan", "agent")
    search_fields = ("provider_order_id", "provider_payment_id", "receipt", "loan__loan_number")


@admin.register(WebhookEvent)
class WebhookEventAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
    list_display = ("event_id", "provider", "event_type", "processed_at", "error", "created_at")
    list_filter = ("provider", "event_type")
    search_fields = ("event_id",)
