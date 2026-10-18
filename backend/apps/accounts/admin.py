from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from apps.core.admin import ReadOnlyAdminMixin

from .models import User


@admin.register(User)
class CashTrailUserAdmin(ReadOnlyAdminMixin, UserAdmin):
    """Users are managed through the API, which checks workloads, revokes sessions and
    audits every change."""

    list_display = ("username", "get_full_name", "role", "branch", "is_active")
    list_filter = ("role", "branch", "is_active")
    list_select_related = ("branch",)
    fieldsets = (*UserAdmin.fieldsets, ("CashTrail", {"fields": ("role", "branch", "phone")}))
