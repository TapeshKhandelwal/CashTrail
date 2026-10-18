from django_filters import rest_framework as filters

from apps.core.dates import day_bounds

from .models import Collection


class CollectionFilter(filters.FilterSet):
    """Dates are business (IST) dates matched against `collected_at`; `date_to` is inclusive."""

    date = filters.DateFilter(method="filter_date", help_text="Collected on this date.")
    date_from = filters.DateFilter(method="filter_date_from", help_text="Collected on or after.")
    date_to = filters.DateFilter(method="filter_date_to", help_text="Collected on or before.")
    branch = filters.NumberFilter(field_name="branch_id")
    agent = filters.NumberFilter(field_name="agent_id")
    loan = filters.NumberFilter(field_name="loan_id")
    customer = filters.NumberFilter(field_name="customer_id")
    status = filters.MultipleChoiceFilter(choices=Collection.Status.choices)
    mode = filters.ChoiceFilter(choices=Collection.Mode.choices)

    class Meta:
        model = Collection
        fields = ()

    def filter_date(self, queryset, name, value):
        start, end = day_bounds(value)
        return queryset.filter(collected_at__gte=start, collected_at__lt=end)

    def filter_date_from(self, queryset, name, value):
        return queryset.filter(collected_at__gte=day_bounds(value)[0])

    def filter_date_to(self, queryset, name, value):
        return queryset.filter(collected_at__lt=day_bounds(value)[1])
