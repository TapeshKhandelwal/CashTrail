import django_filters

from .models import User


class UserFilter(django_filters.FilterSet):
    branch = django_filters.NumberFilter(field_name="branch")

    class Meta:
        model = User
        fields = ("role", "branch", "is_active")
