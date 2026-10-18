from django_filters import rest_framework as filters

from .models import Loan


class LoanFilter(filters.FilterSet):
    branch = filters.NumberFilter(field_name="branch_id")
    customer = filters.NumberFilter(field_name="customer_id")
    agent = filters.NumberFilter(
        field_name="customer__assigned_agent_id", help_text="Assigned collection agent."
    )
    status = filters.ChoiceFilter(choices=Loan.Status.choices)
    disbursed_from = filters.DateFilter(field_name="disbursed_on", lookup_expr="gte")
    disbursed_to = filters.DateFilter(field_name="disbursed_on", lookup_expr="lte")
    overdue = filters.BooleanFilter(
        method="filter_overdue", help_text="Has an installment past due and not fully paid."
    )

    class Meta:
        model = Loan
        fields = ()

    def filter_overdue(self, queryset, name, value):
        return queryset.filter(overdue_amount__gt=0) if value else queryset.filter(overdue_amount=0)
