import pytest
from django.contrib.auth.models import AnonymousUser
from django.db import IntegrityError
from rest_framework.test import APIRequestFactory

from apps.accounts.models import User
from apps.accounts.permissions import HasRole, IsAdmin, IsAgent, ReadOnly
from apps.accounts.scoping import scope_queryset
from apps.core.testing import factories
from apps.customers.models import Customer

pytestmark = pytest.mark.django_db


@pytest.fixture
def customers(customer, other_agent, other_branch_agent):
    return {
        "own": customer,
        "colleague": factories.CustomerFactory(branch=customer.branch, assigned_agent=other_agent),
        "other_branch": factories.CustomerFactory(
            branch=other_branch_agent.branch, assigned_agent=other_branch_agent
        ),
    }


def scoped(user):
    return set(
        scope_queryset(Customer.objects.all(), user, agent_field="assigned_agent").values_list(
            "pk", flat=True
        )
    )


def test_global_roles_see_everything(customers, admin_user, finance_user):
    every = {c.pk for c in customers.values()}

    assert scoped(admin_user) == every
    assert scoped(finance_user) == every


def test_manager_sees_own_branch_only(customers, manager):
    assert scoped(manager) == {customers["own"].pk, customers["colleague"].pk}


def test_agent_sees_assigned_rows_only(customers, agent):
    assert scoped(agent) == {customers["own"].pk}


def test_agent_without_agent_field_sees_nothing(customers, agent):
    assert not scope_queryset(Customer.objects.all(), agent).exists()


def test_anonymous_sees_nothing(customers):
    assert not scope_queryset(Customer.objects.all(), AnonymousUser()).exists()


@pytest.mark.parametrize(
    ("permission", "role", "method", "allowed"),
    [
        (IsAdmin, User.Role.ADMIN, "post", True),
        (IsAdmin, User.Role.FINANCE, "post", False),
        (IsAgent, User.Role.AGENT, "post", True),
        (HasRole(User.Role.ADMIN, User.Role.FINANCE), User.Role.FINANCE, "post", True),
        (IsAdmin | (HasRole(User.Role.FINANCE) & ReadOnly), User.Role.FINANCE, "get", True),
        (IsAdmin | (HasRole(User.Role.FINANCE) & ReadOnly), User.Role.FINANCE, "post", False),
    ],
)
def test_role_permissions(permission, role, method, allowed, branch):
    request = getattr(APIRequestFactory(), method)("/")
    request.user = factories.UserFactory(
        role=role, branch=branch if role in User.BRANCH_ROLES else None
    )

    assert permission().has_permission(request, None) is allowed


def test_branch_roles_require_a_branch():
    with pytest.raises(IntegrityError, match="user_branch_required_for_branch_roles"):
        User.objects.create_user(username="orphan", password="x", role=User.Role.AGENT)
