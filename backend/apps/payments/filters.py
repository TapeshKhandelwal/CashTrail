from django_filters import rest_framework as filters

from apps.core.dates import day_bounds

from .models import GatewayOrder, GatewayProvider, WebhookEvent


class GatewayOrderFilter(filters.FilterSet):
    """Dates are business (IST) dates matched against `created_at`; `date_to` is inclusive."""

    status = filters.MultipleChoiceFilter(choices=GatewayOrder.Status.choices)
    provider = filters.ChoiceFilter(choices=GatewayProvider.choices)
    loan = filters.NumberFilter(field_name="loan_id")
    agent = filters.NumberFilter(field_name="agent_id")
    branch = filters.NumberFilter(field_name="loan__branch_id")
    date_from = filters.DateFilter(method="filter_date_from", help_text="Created on or after.")
    date_to = filters.DateFilter(method="filter_date_to", help_text="Created on or before.")

    class Meta:
        model = GatewayOrder
        fields = ()

    def filter_date_from(self, queryset, name, value):
        return queryset.filter(created_at__gte=day_bounds(value)[0])

    def filter_date_to(self, queryset, name, value):
        return queryset.filter(created_at__lt=day_bounds(value)[1])


class WebhookEventFilter(filters.FilterSet):
    processed = filters.BooleanFilter(
        field_name="processed_at",
        lookup_expr="isnull",
        exclude=True,
        help_text="`false` lists events that could not be applied and need follow-up.",
    )
    provider = filters.ChoiceFilter(choices=GatewayProvider.choices)
    event_type = filters.CharFilter()

    class Meta:
        model = WebhookEvent
        fields = ()
