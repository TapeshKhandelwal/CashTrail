import pytest

from apps.audit.models import AuditAction, AuditLog
from apps.branches import services
from apps.branches.models import Branch
from apps.core.exceptions import DomainError, ValidationFailed
from apps.core.testing import factories

pytestmark = pytest.mark.django_db


def test_create_branch_normalizes_code_and_audits(admin_user):
    branch = services.create_branch(admin_user, code=" del01 ", name="Delhi CP", city="Delhi")

    assert branch.code == "DEL01"
    log = AuditLog.objects.get(entity_type="branch", entity_id=str(branch.pk))
    assert log.action == AuditAction.BRANCH_CREATED
    assert log.actor == admin_user
    assert log.branch == branch
    assert log.after["code"] == "DEL01"


@pytest.mark.parametrize("code", ["X", "BLR-01", "TOOLONGCODE1"])
def test_create_branch_rejects_malformed_code(admin_user, code):
    with pytest.raises(ValidationFailed):
        services.create_branch(admin_user, code=code, name="Somewhere", city="Pune")


def test_create_branch_rejects_duplicate_code_case_insensitively(admin_user, branch):
    with pytest.raises(DomainError) as exc:
        services.create_branch(admin_user, code="blr01", name="Duplicate", city="Bengaluru")

    assert exc.value.code == "DUPLICATE_RECORD"
    assert exc.value.status_code == 409


def test_update_branch_records_only_changed_fields(admin_user, branch):
    services.update_branch(admin_user, branch, name="Bengaluru MG Road", city=branch.city)

    branch.refresh_from_db()
    assert branch.name == "Bengaluru MG Road"
    log = AuditLog.objects.get(action=AuditAction.BRANCH_UPDATED)
    assert log.before == {"name": "Bengaluru Central"}
    assert log.after == {"name": "Bengaluru MG Road"}


def test_update_branch_without_changes_writes_no_audit(admin_user, branch):
    services.update_branch(admin_user, branch, name=branch.name)

    assert not AuditLog.objects.filter(action=AuditAction.BRANCH_UPDATED).exists()


def test_branch_code_is_immutable(admin_user, branch):
    with pytest.raises(ValidationFailed) as exc:
        services.update_branch(admin_user, branch, code="BLR02")

    assert exc.value.details == {"fields": ["code"]}


def test_branch_with_active_staff_or_customers_cannot_be_deactivated(admin_user, customer):
    with pytest.raises(ValidationFailed) as exc:
        services.update_branch(admin_user, customer.branch, is_active=False)

    assert exc.value.details == {"active_staff": 1, "active_customers": 1}


def test_empty_branch_can_be_deactivated(admin_user):
    branch = factories.BranchFactory(code="PUN01")
    factories.AgentFactory(branch=branch, is_active=False)

    services.update_branch(admin_user, branch, is_active=False)

    assert Branch.objects.get(pk=branch.pk).is_active is False
