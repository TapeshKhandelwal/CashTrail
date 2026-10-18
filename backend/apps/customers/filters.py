import django_filters
from django.db import models
from rest_framework.filters import SearchFilter

from .models import Customer
from .serializers import hides_contact_details


class CustomerFilter(django_filters.FilterSet):
    branch = django_filters.NumberFilter(field_name="branch")
    agent = django_filters.NumberFilter(field_name="assigned_agent")
    unassigned = django_filters.BooleanFilter(field_name="assigned_agent", lookup_expr="isnull")

    class Meta:
        model = Customer
        fields = ("branch", "agent", "unassigned", "is_active")


class Due(models.TextChoices):
    OVERDUE = "overdue", "Overdue"
    TODAY = "today", "Due today"


class AgentRouteFilter(django_filters.FilterSet):
    """Works on querysets annotated by `selectors.with_dues`."""

    due = django_filters.ChoiceFilter(choices=Due.choices, method="filter_due")

    class Meta:
        model = Customer
        fields = ("due",)

    def filter_due(self, queryset, name, value):
        if value == Due.OVERDUE:
            return queryset.filter(overdue_amount__gt=0)
        return queryset.filter(due_today__gt=0)


class CustomerSearchFilter(SearchFilter):
    """Roles that see customers' phone numbers masked cannot search by them either."""

    def get_search_fields(self, view, request):
        fields = super().get_search_fields(view, request)
        if fields and hides_contact_details(request):
            return [field for field in fields if not field.endswith("phone")]
        return fields
