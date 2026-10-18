from datetime import timedelta
from decimal import Decimal

import pytest
from django.db.models import Sum
from django.utils import timezone

from apps.collections.models import Collection
from apps.core.dates import business_date
from apps.core.testing import factories
from apps.loans.models import Installment
from apps.reconciliation import selectors, services
from apps.reconciliation.models import Discrepancy

pytestmark = pytest.mark.django_db


@pytest.fixture
def now():
    return timezone.now()


@pytest.fixture
def ledger(
    now,
    manager,
    agent,
    other_agent,
    other_agent_loan,
    other_branch_loan,
    branch,
    receive_cash,
    submit,
    gateway_bank_account,
):
    """One branch day: cash in hand, a pending and an approved hand-over, UPI, deposits."""
    receive_cash("1000.00")
    receive_cash("1500.00", collected_at=now - timedelta(days=3))
    receive_cash("400.00", status=Collection.Status.VOIDED, voided_at=now)
    submit(receive_cash("2000.00"))

    approved = submit(receive_cash("3000.00", loan=other_agent_loan), actor=other_agent)
    services.approve_submission(
        manager,
        approved,
        received_amount=Decimal("2900.00"),
        reason_code=Discrepancy.ReasonCode.AGENT_SHORTAGE,
        remarks="Short by 100.",
    )

    receive_cash("700.00", upi=True)
    gateway = factories.BankDepositFactory(gateway=True, settled=True)
    receive_cash(
        "300.00", upi=True, status=Collection.Status.SETTLED, deposit=gateway, settled_at=now
    )

    today = business_date()
    banked = factories.BankDepositFactory(
        branch=branch, expected_amount=Decimal("5000.00"), settled=True
    )
    earlier = now - timedelta(days=3)
    receive_cash(
        "5000.00",
        collected_at=earlier,
        status=Collection.Status.SETTLED,
        submission=factories.CashSubmissionFactory(
            agent=agent,
            approved=True,
            expected_amount=Decimal("5000.00"),
            submitted_at=earlier,
            reviewed_at=earlier,
            deposit=banked,
        ),
        deposit=banked,
        settled_at=now,
    )
    factories.BankDepositFactory(
        branch=branch, expected_amount=Decimal("1200.00"), deposit_date=today - timedelta(days=5)
    )
    factories.BankDepositFactory(branch=branch, expected_amount=Decimal("800.00"), failed=True)

    receive_cash("999.00", loan=other_branch_loan)


def _expected_due(branch, day):
    return Installment.objects.filter(loan__branch=branch, due_date=day).aggregate(
        total=Sum("amount_due")
    )["total"] or Decimal("0.00")


class TestBranchSummary:
    def test_reconciles_one_branch_day(self, ledger, manager, branch, django_assert_num_queries):
        today = business_date()

        with django_assert_num_queries(7):
            summary = selectors.branch_summary(manager, date_from=today, date_to=today)

        assert [row["branch_code"] for row in summary["branches"]] == ["BLR01"]
        row = summary["branches"][0]
        assert row == {
            "branch_id": branch.pk,
            "branch_code": "BLR01",
            "branch_name": "Bengaluru Central",
            "expected_due": _expected_due(branch, today),
            "collected_cash": Decimal("6000.00"),
            "collected_upi": Decimal("1000.00"),
            "collected_total": Decimal("7000.00"),
            "held_by_agents": Decimal("2500.00"),
            "pending_verification": Decimal("2000.00"),
            "pending_submissions": 1,
            "received_at_branch": Decimal("2900.00"),
            "at_branch_not_deposited": Decimal("2900.00"),
            "deposited": Decimal("5000.00"),
            "pending_settlement": Decimal("1200.00"),
            "delayed_deposits": 1,
            "settled_cash": Decimal("5000.00"),
            "settled_upi": Decimal("300.00"),
            "settled_total": Decimal("5300.00"),
            "open_discrepancies": 1,
            "open_shortage": Decimal("100.00"),
            "open_excess": Decimal("0.00"),
        }
        assert summary["totals"]["collected_total"] == Decimal("7000.00")

    def test_flows_follow_the_period_and_positions_do_not(self, ledger, manager):
        yesterday = business_date() - timedelta(days=1)

        row = selectors.branch_summary(manager, date_from=yesterday, date_to=yesterday)["branches"][
            0
        ]

        assert row["collected_cash"] == Decimal("0.00")
        assert row["received_at_branch"] == Decimal("0.00")
        assert row["held_by_agents"] == Decimal("2500.00")
        assert row["at_branch_not_deposited"] == Decimal("2900.00")

    def test_global_roles_see_every_branch_and_can_narrow(self, ledger, finance_user, other_branch):
        today = business_date()

        summary = selectors.branch_summary(finance_user, date_from=today, date_to=today)
        narrowed = selectors.branch_summary(
            finance_user, date_from=today, date_to=today, branch_id=other_branch.pk
        )

        codes = {row["branch_code"] for row in summary["branches"]}
        assert {"BLR01", "MUM01"} <= codes
        assert summary["totals"]["collected_cash"] == Decimal("6999.00")
        assert [row["branch_code"] for row in narrowed["branches"]] == ["MUM01"]
        assert narrowed["totals"]["held_by_agents"] == Decimal("999.00")

    def test_manager_cannot_widen_scope(self, ledger, manager, other_branch):
        today = business_date()

        summary = selectors.branch_summary(
            manager, date_from=today, date_to=today, branch_id=other_branch.pk
        )

        assert summary["branches"] == []
        assert summary["totals"]["collected_cash"] == Decimal("0.00")

    def test_agents_have_no_branch_view(self, ledger, agent):
        today = business_date()

        assert selectors.branch_summary(agent, date_from=today, date_to=today)["branches"] == []


class TestAgentsSummary:
    def test_per_agent_position_and_ageing(
        self, ledger, now, manager, agent, other_agent, django_assert_num_queries
    ):
        today = business_date()

        with django_assert_num_queries(4):
            summary = selectors.agents_summary(manager, date_from=today, date_to=today, now=now)

        rows = {row["agent_id"]: row for row in summary["agents"]}
        assert set(rows) == {agent.pk, other_agent.pk}
        mine = rows[agent.pk]
        assert mine["collected_cash"] == Decimal("3000.00")
        assert mine["collected_upi"] == Decimal("1000.00")
        assert mine["collection_count"] == 4
        assert mine["submitted"] == Decimal("2000.00")
        assert mine["received"] == Decimal("0.00")
        assert mine["cash_in_hand"] == Decimal("2500.00")
        assert mine["receipts_in_hand"] == 2
        assert mine["pending_verification"] == Decimal("2000.00")
        assert mine["held_under_1d"] == Decimal("1000.00")
        assert mine["held_1_to_2d"] == Decimal("0.00")
        assert mine["held_over_2d"] == Decimal("1500.00")
        assert mine["oldest_held_at"] == now - timedelta(days=3)
        assert mine["oldest_held_hours"] == 72

        theirs = rows[other_agent.pk]
        assert theirs["submitted"] == Decimal("3000.00")
        assert theirs["received"] == Decimal("2900.00")
        assert theirs["open_shortage"] == Decimal("100.00")
        assert theirs["cash_in_hand"] == Decimal("0.00")
        assert theirs["oldest_held_at"] is None
        assert theirs["oldest_held_hours"] is None

        assert summary["totals"]["cash_in_hand"] == Decimal("2500.00")
        assert summary["totals"]["receipts_in_hand"] == 2

    def test_agent_sees_only_themselves(self, ledger, agent):
        today = business_date()

        summary = selectors.agents_summary(agent, date_from=today, date_to=today)

        assert [row["agent_id"] for row in summary["agents"]] == [agent.pk]

    def test_inactive_agents_listed_only_while_holding_cash(
        self, ledger, manager, agent, other_agent
    ):
        today = business_date()
        type(agent).objects.filter(pk__in=[agent.pk, other_agent.pk]).update(is_active=False)

        summary = selectors.agents_summary(manager, date_from=today, date_to=today)

        assert [row["agent_id"] for row in summary["agents"]] == [agent.pk]

    def test_rejected_hand_over_is_not_counted_as_submitted(
        self, manager, agent, receive_cash, submit
    ):
        today = business_date()
        services.reject_submission(manager, submit(receive_cash("500.00")), reason="Recount.")

        row = selectors.agents_summary(manager, date_from=today, date_to=today)["agents"][0]

        assert row["agent_id"] == agent.pk
        assert row["submitted"] == Decimal("0.00")
        assert row["cash_in_hand"] == Decimal("500.00")
