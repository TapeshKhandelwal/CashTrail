import re

from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from apps.branches.models import Branch

from .models import User


class PhoneField(serializers.CharField):
    """Accepts common separators ("98765 43210", "+91-98765-43210") and stores digits only."""

    default_error_messages = {"invalid": "Enter a valid phone number (10-14 digits)."}
    PATTERN = re.compile(r"^\+?\d{10,14}$")

    def __init__(self, **kwargs):
        kwargs.setdefault("max_length", 15)
        super().__init__(**kwargs)

    def to_internal_value(self, data):
        value = re.sub(r"[\s()-]", "", super().to_internal_value(data))
        if value and not self.PATTERN.match(value):
            self.fail("invalid")
        return value


class UserSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(source="get_full_name", read_only=True)
    branch_code = serializers.CharField(source="branch.code", read_only=True, default=None)
    branch_name = serializers.CharField(source="branch.name", read_only=True, default=None)

    class Meta:
        model = User
        fields = (
            "id",
            "username",
            "first_name",
            "last_name",
            "full_name",
            "email",
            "role",
            "phone",
            "branch",
            "branch_code",
            "branch_name",
        )
        read_only_fields = fields


class CashTrailTokenObtainPairSerializer(TokenObtainPairSerializer):
    """Adds role and branch claims and returns the user alongside the tokens."""

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        token["role"] = user.role
        token["branch_id"] = user.branch_id
        token["branch_code"] = user.branch.code if user.branch_id else None
        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        data["user"] = UserSerializer(self.user).data
        return data


class UserDetailSerializer(UserSerializer):
    class Meta(UserSerializer.Meta):
        fields = (*UserSerializer.Meta.fields, "is_active", "last_login", "date_joined")
        read_only_fields = fields


class UserCreateSerializer(serializers.ModelSerializer):
    # Uniqueness (case-insensitive) is enforced by the service.
    username = serializers.RegexField(r"^[\w.@+-]+\Z", max_length=150)
    password = serializers.CharField(
        write_only=True, trim_whitespace=False, style={"input_type": "password"}
    )
    phone = PhoneField(required=False, allow_blank=True)
    branch = serializers.PrimaryKeyRelatedField(
        queryset=Branch.objects.all(), required=False, allow_null=True
    )

    class Meta:
        model = User
        fields = (
            "username",
            "password",
            "first_name",
            "last_name",
            "email",
            "phone",
            "role",
            "branch",
        )
        extra_kwargs = {"first_name": {"required": True, "allow_blank": False}}


class UserUpdateSerializer(serializers.ModelSerializer):
    phone = PhoneField(required=False, allow_blank=True)
    branch = serializers.PrimaryKeyRelatedField(
        queryset=Branch.objects.all(), required=False, allow_null=True
    )

    class Meta:
        model = User
        fields = ("first_name", "last_name", "email", "phone", "role", "branch")


class SetPasswordSerializer(serializers.Serializer):
    password = serializers.CharField(
        write_only=True, trim_whitespace=False, style={"input_type": "password"}
    )
