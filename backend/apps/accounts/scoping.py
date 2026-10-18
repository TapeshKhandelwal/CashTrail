"""Row-level visibility by role, applied to querysets before any user-supplied filter.

ADMIN and FINANCE see everything, a BRANCH_MANAGER sees rows of their branch, and
an AGENT sees only rows tied to them. Anything else sees nothing.
"""

from django.db.models import QuerySet

from .models import User


def scope_queryset(
    queryset: QuerySet,
    user,
    *,
    branch_field: str | None = "branch",
    agent_field: str | None = None,
) -> QuerySet:
    """`scope_queryset(Loan.objects.all(), user, agent_field="customer__assigned_agent")`.

    A `None` field means that role has no access to the model at all.
    """
    role = getattr(user, "role", None)
    if not getattr(user, "is_authenticated", False) or role is None:
        return queryset.none()
    if role in User.GLOBAL_ROLES:
        return queryset
    if role == User.Role.BRANCH_MANAGER and branch_field:
        return queryset.filter(**{branch_field: user.branch_id})
    if role == User.Role.AGENT and agent_field:
        return queryset.filter(**{agent_field: user})
    return queryset.none()


class ScopedQuerysetMixin:
    """For generic views/viewsets: set `scope_branch_field` / `scope_agent_field`."""

    scope_branch_field: str | None = "branch"
    scope_agent_field: str | None = None

    def get_queryset(self):
        return scope_queryset(
            super().get_queryset(),
            self.request.user,
            branch_field=self.scope_branch_field,
            agent_field=self.scope_agent_field,
        )
