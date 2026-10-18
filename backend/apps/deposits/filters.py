import django_filters

from .models import BankAccount, BankDeposit, delayed_q


class BankAccountFilter(django_filters.FilterSet):
    class Meta:
        model = BankAccount
        fields = ("is_active", "is_gateway")


class DepositFilter(django_filters.FilterSet):
    status = django_filters.MultipleChoiceFilter(choices=BankDeposit.Status.choices)
    source = django_filters.ChoiceFilter(choices=BankDeposit.Source.choices)
    branch = django_filters.NumberFilter(field_name="branch_id")
    bank_account = django_filters.NumberFilter(field_name="bank_account_id")
    date_from = django_filters.DateFilter(field_name="deposit_date", lookup_expr="gte")
    date_to = django_filters.DateFilter(field_name="deposit_date", lookup_expr="lte")
    delayed = django_filters.BooleanFilter(
        method="filter_delayed",
        label="Pending beyond the settlement SLA.",
    )

    class Meta:
        model = BankDeposit
        fields = ("status", "source", "branch", "bank_account", "date_from", "date_to", "delayed")

    def filter_delayed(self, queryset, name, value):
        return queryset.filter(delayed_q()) if value else queryset.exclude(delayed_q())


class GatewaySettlementFilter(django_filters.FilterSet):
    status = django_filters.MultipleChoiceFilter(choices=BankDeposit.Status.choices)
    date_from = django_filters.DateFilter(field_name="settled_on", lookup_expr="gte")
    date_to = django_filters.DateFilter(field_name="settled_on", lookup_expr="lte")

    class Meta:
        model = BankDeposit
        fields = ("status", "date_from", "date_to")
