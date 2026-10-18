from functools import wraps

from django.contrib import admin
from django.http import HttpResponse
from rest_framework.throttling import SimpleRateThrottle

from .models import DocumentSequence


class AdminLoginThrottle(SimpleRateThrottle):
    """Login attempts per client address, shared with the API's login rate."""

    scope = "admin_login"

    def get_cache_key(self, request, view):
        return self.cache_format % {"scope": self.scope, "ident": self.get_ident(request)}


def throttle_login(login_view):
    """Rate-limit credential posts to the admin login, which DRF's throttles do not cover."""

    @wraps(login_view)
    def view(request, *args, **kwargs):
        if request.method == "POST" and not AdminLoginThrottle().allow_request(request, None):
            return HttpResponse("Too many login attempts. Try again later.", status=429)
        return login_view(request, *args, **kwargs)

    return view


class ReadOnlyAdminMixin:
    """Records change only through the services, which enforce the business rules and audit
    every change; the admin is for inspection."""

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(DocumentSequence)
class DocumentSequenceAdmin(ReadOnlyAdminMixin, admin.ModelAdmin):
    list_display = ("prefix", "scope", "period", "last_value", "updated_at")
    list_filter = ("prefix",)
    search_fields = ("scope",)
