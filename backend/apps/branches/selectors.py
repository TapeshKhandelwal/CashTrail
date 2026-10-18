from django.db.models import Count, IntegerField, OuterRef, QuerySet, Subquery, Value
from django.db.models.functions import Coalesce

from apps.accounts.models import User
from apps.customers.models import Customer

from .models import Branch


def _count_per_branch(queryset: QuerySet) -> Coalesce:
    counts = (
        queryset.filter(branch=OuterRef("pk"))
        .order_by()
        .values("branch")
        .annotate(total=Count("pk"))
        .values("total")
    )
    return Coalesce(Subquery(counts, output_field=IntegerField()), Value(0))


def with_headcounts(queryset: QuerySet[Branch]) -> QuerySet[Branch]:
    """Active agents and customers per branch, as correlated subqueries (no row fan-out)."""
    return queryset.annotate(
        agent_count=_count_per_branch(User.objects.filter(role=User.Role.AGENT, is_active=True)),
        customer_count=_count_per_branch(Customer.objects.filter(is_active=True)),
    )
