from datetime import date
from decimal import Decimal

import pytest

from apps.audit.models import AuditAction
from apps.audit.services import log_event, snapshot, to_jsonable
from apps.core.context import RequestContext, reset_request_context, set_request_context
from apps.core.testing import factories

pytestmark = pytest.mark.django_db


def test_log_event_records_entity_actor_and_branch(loan, manager):
    entry = log_event(
        manager,
        AuditAction.LOAN_CREATED,
        loan,
        after=snapshot(loan, ["principal", "status", "customer", "first_due_date"]),
    )

    entry.refresh_from_db()
    assert entry.actor == manager
    assert entry.action == "LOAN_CREATED"
    assert (entry.entity_type, entry.entity_id) == ("loan", str(loan.pk))
    assert entry.branch_id == loan.branch_id
    assert entry.after == {
        "principal": "100000.00",
        "status": "ACTIVE",
        "customer": loan.customer_id,
        "first_due_date": loan.first_due_date.isoformat(),
    }


def test_log_event_captures_request_context(branch, admin_user):
    token = set_request_context(
        RequestContext(
            request_id="4f6a1f2e-6a77-4a8e-9a4f-1d2c3b4a5e6f",
            ip_address="10.0.0.7",
            user_agent="pytest",
        )
    )
    try:
        entry = log_event(admin_user, AuditAction.BRANCH_UPDATED, branch, before={}, after={})
    finally:
        reset_request_context(token)

    assert str(entry.request_id) == "4f6a1f2e-6a77-4a8e-9a4f-1d2c3b4a5e6f"
    assert entry.ip_address == "10.0.0.7"
    assert entry.user_agent == "pytest"
    assert entry.branch_id == branch.pk


def test_system_events_have_no_actor(loan):
    collection = factories.CollectionFactory(loan=loan, upi=True)

    entry = log_event(None, AuditAction.GATEWAY_PAYMENT_CAPTURED, collection)

    assert entry.actor is None
    assert entry.before is None


def test_to_jsonable_keeps_money_exact():
    assert to_jsonable({"amount": Decimal("0.10"), "on": date(2026, 10, 17), "ids": (1, 2)}) == {
        "amount": "0.10",
        "on": "2026-10-17",
        "ids": [1, 2],
    }


def test_to_jsonable_rejects_floats():
    with pytest.raises(TypeError):
        to_jsonable({"amount": 0.1})
