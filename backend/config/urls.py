from django.conf import settings
from django.contrib import admin
from django.urls import include, path
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView

from apps.core.admin import throttle_login
from apps.core.views import health

API_APPS = (
    "accounts",
    "branches",
    "customers",
    "loans",
    "collections",
    "reconciliation",
    "deposits",
    "payments",
    "dashboard",
    "audit",
)

api_patterns = [
    path("health/", health, name="health"),
    path("schema/", SpectacularAPIView.as_view(), name="schema"),
    path("docs/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    *(path("", include(f"apps.{app}.urls")) for app in API_APPS),
]

urlpatterns = [path("api/", include(api_patterns))]

if settings.ADMIN_ENABLED:
    urlpatterns += [
        # Matched before the admin's own login route, which stays the one `reverse` returns.
        path(f"{settings.ADMIN_URL}login/", throttle_login(admin.site.login)),
        path(settings.ADMIN_URL, admin.site.urls),
    ]

handler400 = "apps.core.views.bad_request"
handler403 = "apps.core.views.permission_denied"
handler404 = "apps.core.views.not_found"
handler500 = "apps.core.views.server_error"
