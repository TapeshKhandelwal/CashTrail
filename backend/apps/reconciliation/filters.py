from django.db.models import Q
from django_filters import rest_framework as filters

from apps.core.dates import day_bounds

from .models import CashSubmission, Discrepancy


class BusinessDateRangeFilterSet(filters.FilterSet):
    """`date_from` / `date_to` (inclusive, business dates) on the timestamp in `date_field`.

    Filters on day boundaries rather than `__date` so the timestamp index stays usable.
    """

    date_field: str

    date_from = filters.DateFilter(method="filter_date_from")
    date_to = filters.DateFilter(method="filter_date_to")

    def filter_date_from(self, queryset, name, value):
        return queryset.filter(**{f"{self.date_field}__gte": day_bounds(value)[0]})

    def filter_date_to(self, queryset, name, value):
        return queryset.filter(**{f"{self.date_field}__lt": day_bounds(value)[1]})


class CashSubmissionFilter(BusinessDateRangeFilterSet):
    date_field = "submitted_at"

    status = filters.MultipleChoiceFilter(choices=CashSubmission.Status.choices)
    agent = filters.NumberFilter(field_name="agent_id")
    branch = filters.NumberFilter(field_name="branch_id")
    awaiting_deposit = filters.BooleanFilter(
        method="filter_awaiting_deposit",
        label="Approved cash that has not been deposited yet.",
    )

    class Meta:
        model = CashSubmission
        fields = ("status", "agent", "branch", "date_from", "date_to", "awaiting_deposit")

    def filter_awaiting_deposit(self, queryset, name, value):
        awaiting = Q(status__in=CashSubmission.APPROVED_STATUSES, deposit__isnull=True)
        return queryset.filter(awaiting) if value else queryset.exclude(awaiting)


class DiscrepancyFilter(BusinessDateRangeFilterSet):
    date_field = "created_at"

    kind = filters.MultipleChoiceFilter(choices=Discrepancy.Kind.choices)
    status = filters.MultipleChoiceFilter(choices=Discrepancy.Status.choices)
    direction = filters.ChoiceFilter(choices=Discrepancy.Direction.choices)
    reason_code = filters.ChoiceFilter(choices=Discrepancy.ReasonCode.choices)
    branch = filters.NumberFilter(field_name="branch_id")
    agent = filters.NumberFilter(field_name="agent_id")
    submission = filters.NumberFilter(field_name="submission_id")
    deposit = filters.NumberFilter(field_name="deposit_id")

    class Meta:
        model = Discrepancy
        fields = (
            "kind",
            "status",
            "direction",
            "reason_code",
            "branch",
            "agent",
            "submission",
            "deposit",
            "date_from",
            "date_to",
        )
