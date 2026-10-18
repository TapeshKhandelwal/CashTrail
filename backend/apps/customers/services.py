from django.db import transaction

from apps.accounts.models import User
from apps.audit.models import AuditAction
from apps.audit.services import log_event, snapshot
from apps.branches.models import Branch
from apps.core.exceptions import ResourceNotFound, ScopeViolation, ValidationFailed
from apps.core.numbering import customer_number
from apps.loans.models import Loan

from .models import Customer

AUDIT_FIELDS = (
    "customer_code",
    "full_name",
    "phone",
    "email",
    "address",
    "branch",
    "assigned_agent",
    "is_active",
)
EDITABLE_FIELDS = frozenset({"full_name", "phone", "email", "address", "is_active"})


def create_customer(
    actor,
    *,
    full_name: str,
    phone: str,
    branch: Branch | None = None,
    email: str = "",
    address: str = "",
    assigned_agent: User | None = None,
) -> Customer:
    """Branch managers create customers in their own branch; admins pick the branch."""
    branch = _branch_for_new_customer(actor, branch)

    with transaction.atomic():
        if assigned_agent is not None:
            assigned_agent = _lock_assignable_agent(assigned_agent, branch.pk)
        customer = Customer.objects.create(
            customer_code=customer_number(),
            full_name=full_name,
            phone=phone,
            email=email,
            address=address,
            branch=branch,
            assigned_agent=assigned_agent,
        )
        log_event(
            actor, AuditAction.CUSTOMER_CREATED, customer, after=snapshot(customer, AUDIT_FIELDS)
        )
    return customer


def update_customer(actor, customer: Customer, **changes) -> Customer:
    """Edit contact details or (de)activate. Customers are never deleted; the branch is fixed
    because loans and receipts are numbered and reported under it."""
    unknown = changes.keys() - EDITABLE_FIELDS
    if unknown:
        raise ValidationFailed(
            "These fields cannot be changed.", details={"fields": sorted(unknown)}
        )

    with transaction.atomic():
        customer = Customer.objects.select_for_update().get(pk=customer.pk)
        _ensure_can_manage(actor, customer)
        changed = [field for field, value in changes.items() if getattr(customer, field) != value]
        if not changed:
            return customer
        if "is_active" in changed:
            _ensure_activation_allowed(customer, active=changes["is_active"])

        before = snapshot(customer, changed)
        for field in changed:
            setattr(customer, field, changes[field])
        customer.save(update_fields=[*changed, "updated_at"])
        log_event(
            actor,
            AuditAction.CUSTOMER_UPDATED,
            customer,
            before=before,
            after=snapshot(customer, changed),
        )
    return customer


def assign_customer(actor, customer: Customer, agent: User | None) -> Customer:
    """Hand the customer to an active agent of their branch, or unassign with `None`."""
    with transaction.atomic():
        customer = Customer.objects.select_for_update().get(pk=customer.pk)
        _ensure_can_manage(actor, customer)
        if agent is not None:
            if not customer.is_active:
                raise ValidationFailed("Reactivate the customer before assigning an agent.")
            agent = _lock_assignable_agent(agent, customer.branch_id)
        if customer.assigned_agent_id == (agent.pk if agent else None):
            return customer

        before = snapshot(customer, ["assigned_agent"])
        customer.assigned_agent = agent
        customer.save(update_fields=["assigned_agent", "updated_at"])
        log_event(
            actor,
            AuditAction.CUSTOMER_ASSIGNED,
            customer,
            before=before,
            after=snapshot(customer, ["assigned_agent"]),
        )
    return customer


def _branch_for_new_customer(actor, branch: Branch | None) -> Branch:
    if actor.is_branch_manager:
        if branch is not None and branch.pk != actor.branch_id:
            raise ResourceNotFound("Branch not found.", details={"branch": branch.pk})
        branch = actor.branch
    elif not actor.is_admin:
        raise ScopeViolation("Only admins and branch managers can create customers.")
    if branch is None:
        raise ValidationFailed(
            "Select the customer's branch.", details={"branch": ["This field is required."]}
        )
    if not branch.is_active:
        raise ValidationFailed(
            "Customers cannot be added to an inactive branch.", details={"branch": branch.pk}
        )
    return branch


def _ensure_can_manage(actor, customer: Customer) -> None:
    if actor.is_admin:
        return
    if actor.is_branch_manager:
        if customer.branch_id != actor.branch_id:
            raise ResourceNotFound("Customer not found.")
        return
    raise ScopeViolation("Only admins and branch managers can manage customers.")


def _ensure_activation_allowed(customer: Customer, *, active: bool) -> None:
    if active:
        if not customer.branch.is_active:
            raise ValidationFailed(
                "Customers of an inactive branch cannot be reactivated.",
                details={"branch": customer.branch_id},
            )
        return
    # Inactive customers are refused new collections, so an open loan would be stranded.
    active_loans = customer.loans.filter(status=Loan.Status.ACTIVE).count()
    if active_loans:
        raise ValidationFailed(
            "Close the customer's loans before deactivating them.",
            details={"active_loans": active_loans},
        )


def _lock_assignable_agent(agent: User, branch_id: int) -> User:
    """Locks the agent so a concurrent deactivation or transfer cannot slip past the check."""
    agent = User.objects.select_for_update().get(pk=agent.pk)
    if not agent.is_agent or not agent.is_active:
        raise ValidationFailed(
            "Customers can only be assigned to an active collection agent.",
            details={"agent": agent.pk},
        )
    if agent.branch_id != branch_id:
        raise ValidationFailed(
            "The agent must belong to the customer's branch.",
            details={"agent": agent.pk, "branch": branch_id},
        )
    return agent
