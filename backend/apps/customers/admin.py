from django.contrib import admin

from apps.core.admin import ReadOnlyAdminMixin

from .models import Customer


@admin.register(Customer)
class CustomerAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
    list_display = ("customer_code", "full_name", "phone", "branch", "assigned_agent", "is_active")
    list_filter = ("branch", "is_active")
    list_select_related = ("branch", "assigned_agent")
    search_fields = ("customer_code", "full_name", "phone")
