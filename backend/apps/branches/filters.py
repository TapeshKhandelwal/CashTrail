import django_filters

from .models import Branch


class BranchFilter(django_filters.FilterSet):
    city = django_filters.CharFilter(lookup_expr="iexact")

    class Meta:
        model = Branch
        fields = ("is_active", "city")
