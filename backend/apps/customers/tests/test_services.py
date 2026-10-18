import re

import pytest

from apps.audit.models import AuditAction, AuditLog
from apps.core.exceptions import ResourceNotFound, ScopeViolation, ValidationFailed
from apps.core.testing import factories
from apps.customers import services

pytestmark = pytest.mark.django_db


def create(actor, **overrides):
    return services.create_customer(
        actor, **({"full_name": "Lakshmi Rao", "phone": "9845011111"} | overrides)
    )


class TestCreateCustomer:
    def test_manager_creates_in_own_branch(self, manager, agent):
        customer = create(manager, assigned_agent=agent)

        assert customer.branch == manager.branch
        assert customer.assigned_agent == agent
        assert re.fullmatch(r"CUS-\d{6}", customer.customer_code)
        log = AuditLog.objects.get(action=AuditAction.CUSTOMER_CREATED)
        assert (log.actor, log.branch, log.entity_id) == (manager, manager.branch, str(customer.pk))
        assert log.after["customer_code"] == customer.customer_code

    def test_customer_numbers_are_sequential(self, manager):
        first, second = create(manager), create(manager)

        assert int(second.customer_code[4:]) == int(first.customer_code[4:]) + 1

    def test_manager_cannot_create_in_another_branch(self, manager, other_branch):
        with pytest.raises(ResourceNotFound):
            create(manager, branch=other_branch)

    def test_admin_must_choose_a_branch(self, admin_user):
        with pytest.raises(ValidationFailed) as exc:
            create(admin_user)

        assert "branch" in exc.value.details

    def test_admin_creates_in_any_branch(self, admin_user, other_branch):
        assert create(admin_user, branch=other_branch).branch == other_branch

    def test_inactive_branch_is_rejected(self, admin_user):
        closed = factories.BranchFactory(code="OLD01", is_active=False)

        with pytest.raises(ValidationFailed):
            create(admin_user, branch=closed)

    @pytest.mark.parametrize("role", ["agent", "finance_user"])
    def test_other_roles_cannot_create(self, request, role):
        with pytest.raises(ScopeViolation):
            create(request.getfixturevalue(role))

    def test_agent_must_belong_to_the_branch(self, admin_user, branch, other_branch_agent):
        with pytest.raises(ValidationFailed):
            create(admin_user, branch=branch, assigned_agent=other_branch_agent)


class TestUpdateCustomer:
    def test_updates_and_audits_changed_fields(self, manager, customer):
        services.update_customer(
            manager, customer, phone="9000000000", full_name=customer.full_name
        )

        customer.refresh_from_db()
        assert customer.phone == "9000000000"
        log = AuditLog.objects.get(action=AuditAction.CUSTOMER_UPDATED)
        assert log.after == {"phone": "9000000000"}
        assert log.before.keys() == {"phone"}

    def test_deactivation(self, admin_user, customer):
        services.update_customer(admin_user, customer, is_active=False)

        customer.refresh_from_db()
        assert customer.is_active is False

    def test_branch_cannot_be_changed(self, admin_user, customer, other_branch):
        with pytest.raises(ValidationFailed):
            services.update_customer(admin_user, customer, branch=other_branch)

    def test_manager_of_other_branch_cannot_update(self, other_branch_manager, customer):
        with pytest.raises(ResourceNotFound):
            services.update_customer(other_branch_manager, customer, full_name="Changed")

    def test_agent_cannot_update(self, agent, customer):
        with pytest.raises(ScopeViolation):
            services.update_customer(agent, customer, full_name="Changed")


class TestAssignCustomer:
    def test_reassigns_and_audits(self, manager, customer, agent, other_agent):
        services.assign_customer(manager, customer, other_agent)

        customer.refresh_from_db()
        assert customer.assigned_agent == other_agent
        log = AuditLog.objects.get(action=AuditAction.CUSTOMER_ASSIGNED)
        assert log.before == {"assigned_agent": agent.pk}
        assert log.after == {"assigned_agent": other_agent.pk}

    def test_same_agent_is_a_no_op(self, manager, customer, agent):
        services.assign_customer(manager, customer, agent)

        assert not AuditLog.objects.exists()

    def test_unassign(self, admin_user, customer):
        services.assign_customer(admin_user, customer, None)

        customer.refresh_from_db()
        assert customer.assigned_agent is None

    def test_agent_from_other_branch_is_rejected(self, admin_user, customer, other_branch_agent):
        with pytest.raises(ValidationFailed):
            services.assign_customer(admin_user, customer, other_branch_agent)

    def test_inactive_agent_is_rejected(self, manager, customer, other_agent):
        other_agent.is_active = False
        other_agent.save()

        with pytest.raises(ValidationFailed):
            services.assign_customer(manager, customer, other_agent)

    def test_non_agent_is_rejected(self, admin_user, customer, manager):
        with pytest.raises(ValidationFailed):
            services.assign_customer(admin_user, customer, manager)

    def test_inactive_customer_cannot_be_assigned(self, manager, customer, other_agent):
        customer.is_active = False
        customer.save()

        with pytest.raises(ValidationFailed):
            services.assign_customer(manager, customer, other_agent)

    def test_manager_of_other_branch_is_refused(self, other_branch_manager, customer):
        with pytest.raises(ResourceNotFound):
            services.assign_customer(other_branch_manager, customer, None)


class TestActivation:
    def test_customer_with_active_loan_cannot_be_deactivated(self, admin_user, loan):
        with pytest.raises(ValidationFailed) as exc:
            services.update_customer(admin_user, loan.customer, is_active=False)

        assert exc.value.details == {"active_loans": 1}

    def test_customer_with_only_closed_loans_can_be_deactivated(self, admin_user, loan):
        loan.amount_paid = loan.total_payable
        loan.status, loan.closed_at = loan.Status.CLOSED, loan.created_at
        loan.save()

        services.update_customer(admin_user, loan.customer, is_active=False)

        loan.customer.refresh_from_db()
        assert loan.customer.is_active is False

    def test_reactivation_requires_active_branch(self, admin_user, customer):
        services.update_customer(admin_user, customer, is_active=False)
        customer.branch.is_active = False
        customer.branch.save()

        with pytest.raises(ValidationFailed):
            services.update_customer(admin_user, customer, is_active=True)

    def test_reactivation_is_audited(self, admin_user, customer):
        services.update_customer(admin_user, customer, is_active=False)

        services.update_customer(admin_user, customer, is_active=True)

        logs = AuditLog.objects.filter(action=AuditAction.CUSTOMER_UPDATED).order_by("pk")
        assert [log.after for log in logs] == [{"is_active": False}, {"is_active": True}]
