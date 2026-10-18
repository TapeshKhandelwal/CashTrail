from django.urls import path
from rest_framework.routers import SimpleRouter
from rest_framework_simplejwt.views import TokenBlacklistView, TokenRefreshView

from .views import LoginView, MeView, UserViewSet

router = SimpleRouter(trailing_slash=True)
router.register("users", UserViewSet, basename="user")

urlpatterns = [
    path("auth/login/", LoginView.as_view(), name="login"),
    path("auth/refresh/", TokenRefreshView.as_view(), name="token-refresh"),
    path("auth/logout/", TokenBlacklistView.as_view(), name="logout"),
    path("auth/me/", MeView.as_view(), name="me"),
    *router.urls,
]
