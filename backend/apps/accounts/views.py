from drf_spectacular.utils import OpenApiResponse, extend_schema, extend_schema_view
from rest_framework import mixins, status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import AuthenticationFailed
from rest_framework.generics import RetrieveAPIView
from rest_framework.response import Response
from rest_framework_simplejwt.views import TokenObtainPairView

from apps.core.schema import error_responses

from . import services
from .filters import UserFilter
from .models import User
from .permissions import IsAdmin, IsBranchManager, IsFinance, ReadOnly
from .serializers import (
    CashTrailTokenObtainPairSerializer,
    SetPasswordSerializer,
    UserCreateSerializer,
    UserDetailSerializer,
    UserSerializer,
    UserUpdateSerializer,
)
from .throttles import LoginUsernameThrottle


class LoginView(TokenObtainPairView):
    """Throttled per client address (all attempts) and per username (failed attempts)."""

    serializer_class = CashTrailTokenObtainPairSerializer
    throttle_scope = "login"

    def get_throttles(self):
        self.username_throttle = LoginUsernameThrottle()
        return [*super().get_throttles(), self.username_throttle]

    def post(self, request, *args, **kwargs):
        try:
            return super().post(request, *args, **kwargs)
        except AuthenticationFailed:
            self.username_throttle.record_failure()
            raise


class MeView(RetrieveAPIView):
    serializer_class = UserSerializer

    def get_object(self):
        return User.objects.select_related("branch").get(pk=self.request.user.pk)


@extend_schema_view(
    list=extend_schema(summary="List users (branch managers see their branch's agents)"),
    retrieve=extend_schema(summary="Retrieve a user"),
    create=extend_schema(
        summary="Create a user",
        request=UserCreateSerializer,
        responses={201: UserDetailSerializer, **error_responses(400, 403, 409, 422)},
    ),
    partial_update=extend_schema(
        summary="Update a user's profile, role or branch",
        request=UserUpdateSerializer,
        responses={200: UserDetailSerializer, **error_responses(400, 403, 404, 422)},
    ),
)
class UserViewSet(mixins.ListModelMixin, mixins.RetrieveModelMixin, viewsets.GenericViewSet):
    serializer_class = UserDetailSerializer
    permission_classes = [IsAdmin | ((IsBranchManager | IsFinance) & ReadOnly)]
    filterset_class = UserFilter
    search_fields = ("username", "first_name", "last_name", "email", "phone")
    ordering_fields = ("username", "first_name", "role", "date_joined", "last_login")
    ordering = ("username",)

    def get_queryset(self):
        queryset = User.objects.select_related("branch")
        user = self.request.user
        if user.is_authenticated and user.is_branch_manager:
            return queryset.filter(branch=user.branch_id, role=User.Role.AGENT)
        return queryset

    def create(self, request):
        serializer = UserCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = services.create_user(request.user, **serializer.validated_data)
        return Response(self.get_serializer(user).data, status=status.HTTP_201_CREATED)

    def partial_update(self, request, pk=None):
        user = self.get_object()
        serializer = UserUpdateSerializer(user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        user = services.update_user(request.user, user, **serializer.validated_data)
        return Response(self.get_serializer(user).data)

    @extend_schema(
        summary="Deactivate a user and revoke their sessions",
        request=None,
        responses={200: UserDetailSerializer, **error_responses(403, 404, 422)},
    )
    @action(detail=True, methods=["post"])
    def deactivate(self, request, pk=None):
        user = services.deactivate_user(request.user, self.get_object())
        return Response(self.get_serializer(user).data)

    @extend_schema(
        summary="Reactivate a user",
        request=None,
        responses={200: UserDetailSerializer, **error_responses(403, 404, 422)},
    )
    @action(detail=True, methods=["post"])
    def activate(self, request, pk=None):
        user = services.activate_user(request.user, self.get_object())
        return Response(self.get_serializer(user).data)

    @extend_schema(
        summary="Set a new password and revoke the user's sessions",
        request=SetPasswordSerializer,
        responses={
            204: OpenApiResponse(description="Password changed."),
            **error_responses(400, 403, 404, 422),
        },
    )
    @action(detail=True, methods=["post"], url_path="set-password")
    def set_password(self, request, pk=None):
        user = self.get_object()
        serializer = SetPasswordSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        services.set_password(request.user, user, serializer.validated_data["password"])
        return Response(status=status.HTTP_204_NO_CONTENT)
