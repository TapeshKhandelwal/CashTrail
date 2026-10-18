from django.contrib import admin

from apps.core.admin import ReadOnlyAdminMixin

from .models import Branch


@admin.register(Branch)
class BranchAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
    list_display = ("code", "name", "city", "is_active")
    list_filter = ("is_active", "city")
    search_fields = ("code", "name", "city")
