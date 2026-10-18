import django_filters

from apps.core.dates import day_bounds

from .models import AuditAction, AuditLog


class AuditLogFilter(django_filters.FilterSet):
    entity_type = django_filters.CharFilter(help_text="Model name, e.g. `collection`.")
    entity_id = django_filters.CharFilter()
    # Plain ids rather than model choices, so probing a user or branch id reveals nothing.
    actor = django_filters.NumberFilter(field_name="actor_id")
    branch = django_filters.NumberFilter(field_name="branch_id")
    action = django_filters.ChoiceFilter(choices=AuditAction.choices)
    date_from = django_filters.DateFilter(method="filter_date_from", help_text="IST date.")
    date_to = django_filters.DateFilter(method="filter_date_to", help_text="IST date.")

    class Meta:
        model = AuditLog
        fields = ("entity_type", "entity_id", "actor", "branch", "action")

    def filter_date_from(self, queryset, name, value):
        return queryset.filter(created_at__gte=day_bounds(value)[0])

    def filter_date_to(self, queryset, name, value):
        return queryset.filter(created_at__lt=day_bounds(value)[1])
