import re

from django.db import transaction

from apps.audit.models import AuditAction
from apps.audit.services import log_event, snapshot
from apps.core.exceptions import DomainError, ValidationFailed

from .models import Branch

AUDIT_FIELDS = ("code", "name", "city", "address", "is_active")
EDITABLE_FIELDS = frozenset({"name", "city", "address", "is_active"})
CODE_PATTERN = re.compile(r"^[A-Z0-9]{2,10}$")


def normalize_branch_code(code: str) -> str:
    return code.strip().upper()


def create_branch(actor, *, code: str, name: str, city: str, address: str = "") -> Branch:
    code = normalize_branch_code(code)
    if not CODE_PATTERN.match(code):
        raise ValidationFailed(
            "Branch code must be 2-10 letters or digits.", details={"code": code}
        )
    with transaction.atomic():
        if Branch.objects.filter(code=code).exists():
            raise DomainError(
                "A branch with this code already exists.",
                code="DUPLICATE_RECORD",
                status_code=409,
                details={"code": code},
            )
        branch = Branch.objects.create(code=code, name=name, city=city, address=address)
        log_event(actor, AuditAction.BRANCH_CREATED, branch, after=snapshot(branch, AUDIT_FIELDS))
    return branch


def update_branch(actor, branch: Branch, **changes) -> Branch:
    """Edit descriptive fields or (de)activate. The code is immutable: it is baked into
    every document number issued for the branch."""
    unknown = changes.keys() - EDITABLE_FIELDS
    if unknown:
        raise ValidationFailed(
            "These fields cannot be changed.", details={"fields": sorted(unknown)}
        )

    with transaction.atomic():
        branch = Branch.objects.select_for_update().get(pk=branch.pk)
        changed = [field for field, value in changes.items() if getattr(branch, field) != value]
        if not changed:
            return branch
        if changes.get("is_active") is False:
            _ensure_branch_can_close(branch)

        before = snapshot(branch, changed)
        for field in changed:
            setattr(branch, field, changes[field])
        branch.save(update_fields=[*changed, "updated_at"])
        log_event(
            actor,
            AuditAction.BRANCH_UPDATED,
            branch,
            before=before,
            after=snapshot(branch, changed),
        )
    return branch


def _ensure_branch_can_close(branch: Branch) -> None:
    active_staff = branch.users.filter(is_active=True).count()
    active_customers = branch.customers.filter(is_active=True).count()
    if active_staff or active_customers:
        raise ValidationFailed(
            "Move or deactivate the branch's staff and customers before deactivating it.",
            details={"active_staff": active_staff, "active_customers": active_customers},
        )
