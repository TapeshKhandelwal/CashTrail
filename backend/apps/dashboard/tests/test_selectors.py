import uuid
from datetime import timedelta
from decimal import Decimal

import pytest
from django.db import connection
from django.test.utils import CaptureQueriesContext

from apps.collections.models import Collection
from apps.core.dates import day_bounds
from apps.core.testing import factories
from apps.dashboard import selectors
from apps.deposits import services as deposits
from apps.reconciliation import selectors as reconciliation

pytestmark = pytest.mark.django_db

EMI = Decimal("8885.00")


def tally(amount: str, count: int) -> dict:
    return {"amount": Decimal(amount), "count": count}


@pytest.fixture
def summary_for(scenario, anchor, make_filters):
    def run(user, **filters):
        return selectors.dashboard_summary(user, make_filters(**filters), now=anchor)

    return run


class TestSummaryForGlobalRoles:
    def test_flow_from_dues_to_settlement(self, summary_for, admin_user):
        summary = summary_for(admin_user)

        assert summary["expected"] == {"amount": EMI * 2, "count": 2}
        assert summary["collected"] == {
            **tally("16500.00", 9),
            "cash": tally("13800.00", 7),
            "upi": tally("2700.00", 2),
        }
        assert summary["voided"] == tally("700.00", 1)
        assert summary["cash_with_agents"] == tally("3299.00", 4)
        assert summary["pending_verification"] == tally("2000.00", 1)
        assert summary["branch_received"] == tally("9000.00", 3)
        assert summary["at_branch"] == tally("2500.00", 1)
        assert summary["pending_deposits"] == tally("2500.00", 1)
        # Receipts at full value: the gateway's fee and tax do not reduce what was settled.
        assert summary["settled"] == tally("5200.00", 2)
        assert summary["delayed_settlements"] == tally("2500.00", 1)

    def test_cash_ageing_buckets_cover_cash_in_hand(self, summary_for, admin_user):
        summary = summary_for(admin_user)
        buckets = {b["bucket"]: (b["amount"], b["count"]) for b in summary["cash_ageing"]}

        assert buckets == {
            "under_1_day": (Decimal("1800.00"), 2),
            "1_to_2_days": (Decimal("500.00"), 1),
            "over_2_days": (Decimal("999.00"), 1),
        }
        assert (
            sum(amount for amount, _ in buckets.values()) == summary["cash_with_agents"]["amount"]
        )

    def test_deposits_by_status(self, summary_for, admin_user):
        deposits = summary_for(admin_user)["deposits"]

        # Branch cash only: the failed deposit shows under its status, gateway batches not at all.
        assert (deposits["amount"], deposits["count"]) == (Decimal("6500.00"), 2)
        assert {d["status"]: (d["amount"], d["count"]) for d in deposits["by_status"]} == {
            "PENDING": (Decimal("2500.00"), 1),
            "SETTLED": (Decimal("4000.00"), 1),
            "SETTLED_WITH_MISMATCH": (Decimal("0.00"), 0),
            "FAILED": (Decimal("900.00"), 1),
        }

    def test_outstanding_and_overdue(self, summary_for, admin_user, scenario):
        loans = scenario.loans
        summary = summary_for(admin_user)

        expected_outstanding = (
            loans["l1"].total_payable
            - Decimal("12000.00")
            + loans["l2"].total_payable
            - Decimal("4000.00")
            + loans["l3"].total_payable
        )
        assert summary["outstanding"] == {"amount": expected_outstanding, "count": 3}
        assert summary["overdue"] == {"amount": EMI * 2 - Decimal("4000.00"), "count": 2}

    def test_discrepancies(self, summary_for, admin_user):
        discrepancies = summary_for(admin_user)["discrepancies"]

        assert discrepancies["open"] == tally("506.40", 2)
        assert discrepancies["resolved"] == tally("100.00", 1)
        assert discrepancies["raised"] == tally("606.40", 3)
        by_kind = {d["kind"]: (d["amount"], d["count"]) for d in discrepancies["open_by_kind"]}
        assert by_kind == {
            "CASH_SHORTAGE": (Decimal("500.00"), 1),
            "CASH_EXCESS": (Decimal("0.00"), 0),
            "DEPOSIT_MISMATCH": (Decimal("0.00"), 0),
            "SETTLEMENT_MISMATCH": (Decimal("0.00"), 0),
            "GATEWAY_MISMATCH": (Decimal("6.40"), 1),
        }

    def test_ratios(self, summary_for, finance_user):
        summary = summary_for(finance_user)

        assert summary["collection_efficiency"] == Decimal("92.85")
        assert summary["deposit_accuracy"] == Decimal("100.00")
        assert summary["avg_settlement_lag_days"] == Decimal("2.0")

    def test_ratios_are_null_without_a_base(self, admin_user, make_filters, today):
        empty = make_filters(date_from=today - timedelta(days=1), date_to=today)

        summary = selectors.dashboard_summary(admin_user, empty)

        assert summary["collection_efficiency"] is None
        assert summary["deposit_accuracy"] is None
        assert summary["avg_settlement_lag_days"] is None
        assert summary["collected"]["amount"] == Decimal("0.00")


class TestSummaryScoping:
    def test_manager_sees_only_their_branch(self, summary_for, manager):
        summary = summary_for(manager)

        assert summary["expected"] == {"amount": EMI, "count": 1}
        assert summary["collected"]["amount"] == Decimal("14500.00")
        assert summary["cash_with_agents"] == tally("2499.00", 3)
        assert (summary["deposits"]["amount"], summary["deposits"]["count"]) == (
            Decimal("6500.00"),
            2,
        )
        assert summary["settled"] == tally("4000.00", 1)
        assert summary["discrepancies"]["open"] == tally("500.00", 1)

    def test_agent_sees_only_their_own_book(self, summary_for, agent, scenario):
        summary = summary_for(agent)

        assert summary["expected"] == {"amount": EMI, "count": 1}
        assert summary["collected"]["amount"] == Decimal("12000.00")
        assert summary["cash_with_agents"] == tally("2499.00", 3)
        assert summary["branch_received"] == tally("6500.00", 2)
        # Only the deposit that carries this agent's receipts.
        assert summary["deposits"]["count"] == 1
        assert summary["settled"] == tally("4000.00", 1)
        assert summary["discrepancies"]["open"] == tally("500.00", 1)
        assert summary["outstanding"] == {
            "amount": scenario.loans["l1"].total_payable - Decimal("12000.00"),
            "count": 1,
        }

    def test_agent_without_activity_sees_zeros(self, summary_for, other_branch):
        newcomer = factories.AgentFactory(branch=other_branch)

        summary = summary_for(newcomer)

        assert summary["collected"]["amount"] == Decimal("0.00")
        assert summary["deposits"]["count"] == 0
        assert summary["outstanding"]["count"] == 0


class TestSummaryFilters:
    def test_branch_filter(self, summary_for, admin_user, other_branch):
        summary = summary_for(admin_user, branch=other_branch)

        assert summary["collected"]["amount"] == Decimal("2000.00")
        # Gateway settlements belong to no branch.
        assert summary["deposits"]["count"] == 0
        assert summary["discrepancies"]["open"]["count"] == 0

    def test_agent_filter(self, summary_for, admin_user, other_agent):
        summary = summary_for(admin_user, agent=other_agent)

        assert summary["collected"]["amount"] == Decimal("2500.00")
        assert summary["deposits"]["amount"] == Decimal("2500.00")
        assert summary["delayed_settlements"]["count"] == 1
        assert summary["overdue"]["count"] == 2

    def test_status_filter_narrows_every_receipt_figure(self, summary_for, admin_user):
        summary = summary_for(admin_user, status=Collection.Status.SETTLED)

        assert summary["collected"] == {
            **tally("5200.00", 2),
            "cash": tally("4000.00", 1),
            "upi": tally("1200.00", 1),
        }
        assert summary["settled"] == tally("5200.00", 2)
        assert summary["voided"] == tally("0.00", 0)
        assert summary["cash_with_agents"] == tally("0.00", 0)
        assert all(bucket["count"] == 0 for bucket in summary["cash_ageing"])
        assert summary["pending_verification"] == tally("0.00", 0)
        assert summary["at_branch"] == tally("0.00", 0)
        assert summary["pending_deposits"] == tally("0.00", 0)
        assert summary["delayed_settlements"] == tally("0.00", 0)

    def test_status_filter_leaves_figures_that_are_not_receipts(self, summary_for, admin_user):
        summary = summary_for(admin_user, status=Collection.Status.SETTLED)

        assert summary["expected"] == {"amount": EMI * 2, "count": 2}
        assert summary["branch_received"] == tally("9000.00", 3)
        assert summary["discrepancies"]["open"] == tally("506.40", 2)

    @pytest.mark.parametrize(
        ("status", "figure", "expected"),
        [
            (Collection.Status.COLLECTED, "cash_with_agents", tally("3299.00", 4)),
            (Collection.Status.SUBMITTED, "pending_verification", tally("2000.00", 1)),
            (Collection.Status.BRANCH_RECEIVED, "at_branch", tally("2500.00", 1)),
            (Collection.Status.DEPOSITED, "pending_deposits", tally("2500.00", 1)),
        ],
    )
    def test_status_filter_keeps_its_own_stage_whole(
        self, summary_for, admin_user, status, figure, expected
    ):
        summary = summary_for(admin_user, status=status)

        assert summary[figure] == expected
        assert summary["settled"] == tally("0.00", 0)

    def test_pending_deposits_are_live_whatever_the_period(self, summary_for, admin_user, today):
        # The pending deposit is dated five days ago, before this period.
        summary = summary_for(admin_user, date_from=today - timedelta(days=1), date_to=today)

        by_status = {d["status"]: d["count"] for d in summary["deposits"]["by_status"]}
        assert by_status["PENDING"] == 0
        assert summary["pending_deposits"] == tally("2500.00", 1)
        assert summary["delayed_settlements"] == tally("2500.00", 1)

    def test_pending_deposits_follow_the_agent_filter(
        self, summary_for, admin_user, agent, other_agent
    ):
        assert summary_for(admin_user, agent=other_agent)["pending_deposits"] == tally("2500.00", 1)
        assert summary_for(admin_user, agent=agent)["pending_deposits"] == tally("0.00", 0)

    def test_filters_combine_with_scope(self, summary_for, manager, other_agent):
        assert summary_for(manager, agent=other_agent)["collected"]["amount"] == Decimal("2500.00")

    def test_date_range_excludes_older_receipts(self, summary_for, admin_user, today):
        summary = summary_for(admin_user, date_from=today - timedelta(days=21), date_to=today)

        assert summary["collected"] == {
            **tally("17499.00", 10),
            "cash": tally("14799.00", 8),
            "upi": tally("2700.00", 2),
        }


def test_summary_runs_a_fixed_number_of_queries(
    scenario, admin_user, make_filters, django_assert_num_queries
):
    with django_assert_num_queries(7):
        selectors.dashboard_summary(admin_user, make_filters())


class TestTrend:
    def test_daily_series(self, scenario, admin_user, make_filters, today):
        points = selectors.collection_trend(admin_user, make_filters())
        by_day = {p["date"]: p for p in points}

        assert [p["date"] for p in points] == [today - timedelta(days=n) for n in range(7, -1, -1)]
        assert by_day[today]["expected"] == EMI * 2
        assert by_day[today]["collected"] == Decimal("1800.00")
        assert by_day[today]["settled"] == Decimal("1200.00")
        # c7 at noon plus c2, collected 36 hours before the anchor: midnight yesterday.
        assert by_day[today - timedelta(days=1)]["collected"] == Decimal("2000.00")
        assert by_day[today - timedelta(days=1)]["settled"] == Decimal("4000.00")
        assert by_day[today - timedelta(days=6)]["collected"] == Decimal("2500.00")
        assert by_day[today - timedelta(days=7)] == {
            "date": today - timedelta(days=7),
            "expected": Decimal("0.00"),
            "collected": Decimal("0.00"),
            "settled": Decimal("0.00"),
        }
        assert sum(p["collected"] for p in points) == Decimal("16500.00")

    def test_days_follow_the_business_timezone(self, admin_user, make_filters, today, loan):
        # 00:30 IST is still the previous day in UTC.
        factories.CollectionFactory(
            loan=loan,
            amount=Decimal("250.00"),
            collected_at=day_bounds(today)[0] + timedelta(minutes=30),
        )

        points = selectors.collection_trend(admin_user, make_filters())

        assert points[-1]["collected"] == Decimal("250.00")
        assert points[-2]["collected"] == Decimal("0.00")

    def test_status_filter_narrows_collected_and_settled(self, scenario, admin_user, make_filters):
        points = selectors.collection_trend(
            admin_user, make_filters(status=Collection.Status.COLLECTED)
        )

        assert sum(p["collected"] for p in points) == Decimal("3800.00")
        assert sum(p["settled"] for p in points) == Decimal("0.00")
        assert sum(p["expected"] for p in points) == EMI * 2

    def test_agent_trend_is_scoped(self, scenario, other_agent, make_filters):
        points = selectors.collection_trend(other_agent, make_filters())

        assert sum(p["collected"] for p in points) == Decimal("2500.00")
        assert sum(p["expected"] for p in points) == Decimal("0.00")


class TestLifecycle:
    def test_funnel_and_status_breakdown(self, scenario, admin_user, make_filters):
        lifecycle = selectors.collection_lifecycle(admin_user, make_filters())

        assert lifecycle["expected"] == {"amount": EMI * 2, "count": 2}
        assert [(s["stage"], s["amount"], s["count"]) for s in lifecycle["stages"]] == [
            ("COLLECTED", Decimal("16500.00"), 9),
            ("BRANCH_RECEIVED", Decimal("10700.00"), 4),
            ("DEPOSITED", Decimal("7700.00"), 3),
            ("SETTLED", Decimal("5200.00"), 2),
        ]
        assert {s["status"]: (s["amount"], s["count"]) for s in lifecycle["by_status"]} == {
            "COLLECTED": (Decimal("3800.00"), 4),
            "SUBMITTED": (Decimal("2000.00"), 1),
            "BRANCH_RECEIVED": (Decimal("3000.00"), 1),
            "DEPOSITED": (Decimal("2500.00"), 1),
            "SETTLED": (Decimal("5200.00"), 2),
            "VOIDED": (Decimal("700.00"), 1),
        }

    def test_status_filter_narrows_the_funnel(self, scenario, admin_user, make_filters):
        lifecycle = selectors.collection_lifecycle(
            admin_user, make_filters(status=Collection.Status.DEPOSITED)
        )

        assert [(s["stage"], s["amount"]) for s in lifecycle["stages"]] == [
            ("COLLECTED", Decimal("2500.00")),
            ("BRANCH_RECEIVED", Decimal("2500.00")),
            ("DEPOSITED", Decimal("2500.00")),
            ("SETTLED", Decimal("0.00")),
        ]

    def test_manager_funnel_is_branch_scoped(self, scenario, manager, make_filters):
        stages = selectors.collection_lifecycle(manager, make_filters())["stages"]

        assert [s["amount"] for s in stages] == [
            Decimal("14500.00"),
            Decimal("9500.00"),
            Decimal("6500.00"),
            Decimal("4000.00"),
        ]


class TestBreakdowns:
    def test_branch_rows(self, scenario, admin_user, make_filters, anchor):
        filters = make_filters()
        branches = list(selectors.branches_for_breakdown(admin_user, filters))

        rows = selectors.branch_breakdown(admin_user, filters, branches, now=anchor)

        blr, mum = rows
        assert (blr["branch"].code, mum["branch"].code) == ("BLR01", "MUM01")
        assert blr["collected"] == tally("14500.00", 7)
        assert blr["expected"] == {"amount": EMI, "count": 1}
        assert blr["at_branch"] == tally("2500.00", 1)
        assert blr["deposited"] == tally("6500.00", 2)
        assert blr["settled"] == tally("4000.00", 1)
        assert blr["delayed_settlements"] == tally("2500.00", 1)
        assert blr["open_discrepancies"] == tally("500.00", 1)
        assert blr["collection_efficiency"] == Decimal("163.20")
        assert mum["collected"] == tally("2000.00", 2)
        assert mum["cash_with_agents"] == tally("800.00", 1)
        assert mum["deposited"] == tally("0.00", 0)

    def test_branch_rows_follow_the_status_filter(self, scenario, admin_user, make_filters):
        filters = make_filters(status=Collection.Status.SETTLED)
        branches = list(selectors.branches_for_breakdown(admin_user, filters))

        blr, mum = selectors.branch_breakdown(admin_user, filters, branches)

        assert blr["collected"] == tally("4000.00", 1)
        assert blr["settled"] == tally("4000.00", 1)
        assert blr["at_branch"] == tally("0.00", 0)
        assert blr["delayed_settlements"] == tally("0.00", 0)
        assert mum["cash_with_agents"] == tally("0.00", 0)

    def test_manager_lists_only_their_branch(self, scenario, manager, make_filters):
        assert [b.code for b in selectors.branches_for_breakdown(manager, make_filters())] == [
            "BLR01"
        ]

    def test_agent_rows(self, scenario, manager, agent, other_agent, make_filters, anchor):
        filters = make_filters()
        agents = list(selectors.agents_for_breakdown(manager, filters))

        breakdown = selectors.agent_breakdown(manager, filters, agents, now=anchor)
        rows = {row["agent"].username: row for row in breakdown}

        assert set(rows) == {agent.username, other_agent.username}
        mine = rows[agent.username]
        assert mine["collected"] == tally("12000.00", 6)
        assert mine["cash_with_agents"] == tally("2499.00", 3)
        assert mine["pending_verification"] == tally("2000.00", 1)
        assert mine["oldest_cash_held_at"] == anchor - timedelta(days=20)
        assert mine["branch_received"] == tally("6500.00", 2)
        assert mine["rejected_submissions"] == tally("600.00", 1)
        assert mine["open_discrepancies"] == tally("500.00", 1)
        colleague = rows[other_agent.username]
        assert colleague["collected"] == tally("2500.00", 1)
        assert colleague["overdue"]["count"] == 2
        assert colleague["oldest_cash_held_at"] is None
        assert colleague["collection_efficiency"] is None

    def test_breakdown_query_count_does_not_grow_with_rows(
        self, scenario, admin_user, make_filters, django_assert_num_queries
    ):
        for code in ("DEL01", "HYD01", "PUN01"):
            factories.AgentFactory(branch=factories.BranchFactory(code=code))
        filters = make_filters()
        branches = list(selectors.branches_for_breakdown(admin_user, filters))
        agents = list(selectors.agents_for_breakdown(admin_user, filters))
        assert (len(branches), len(agents)) == (5, 6)

        with django_assert_num_queries(7):
            selectors.branch_breakdown(admin_user, filters, branches)
        with django_assert_num_queries(5):
            selectors.agent_breakdown(admin_user, filters, agents)


class TestReports:
    def test_collections_report_is_scoped_and_filtered(self, scenario, manager, make_filters):
        rows = selectors.collections_report(manager, make_filters(status="COLLECTED"))

        assert [c.receipt_number for c in rows] == [
            scenario.receipts["c2"].receipt_number,
            scenario.receipts["c7"].receipt_number,
            scenario.receipts["c1"].receipt_number,
        ]

    def test_deposits_report_for_agent_lists_deposits_with_their_receipts(
        self, scenario, other_agent, make_filters
    ):
        rows = selectors.deposits_report(other_agent, make_filters())

        assert list(rows) == [scenario.deposits["pending"]]


class TestDefinitionsAgreeAcrossScreens:
    def test_redeposited_cash_is_banked_once(
        self, admin_user, manager, finance_user, bank_account, make_filters, today
    ):
        submission = factories.CashSubmissionFactory(
            agent=factories.AgentFactory(branch=manager.branch),
            approved=True,
            reviewed_by=manager,
            expected_amount=Decimal("5000.00"),
        )
        params = {
            "submission_ids": [submission.pk],
            "bank_account_id": bank_account.pk,
            "deposited_amount": Decimal("5000.00"),
            "deposit_date": today,
        }
        first, _ = deposits.create_deposit(
            manager, **params, reference_number="SLIP-1", idempotency_key=uuid.uuid4()
        )
        deposits.fail_deposit(finance_user, first, reason="Slip rejected.")
        deposits.create_deposit(
            manager, **params, reference_number="SLIP-2", idempotency_key=uuid.uuid4()
        )

        summary = selectors.dashboard_summary(admin_user, make_filters())
        (row,) = selectors.branch_breakdown(admin_user, make_filters(), [manager.branch])
        branch_summary = reconciliation.branch_summary(admin_user, date_from=today, date_to=today)

        assert summary["deposits"]["amount"] == Decimal("5000.00")
        assert row["deposited"]["amount"] == Decimal("5000.00")
        assert branch_summary["totals"]["deposited"] == Decimal("5000.00")

    def test_settled_is_receipts_by_bank_date_everywhere(
        self, scenario, admin_user, make_filters, today
    ):
        filters = make_filters()
        summary = selectors.dashboard_summary(admin_user, filters)
        trend = selectors.collection_trend(admin_user, filters)
        branch_summary = reconciliation.branch_summary(
            admin_user, date_from=filters.date_from, date_to=today
        )

        assert summary["settled"]["amount"] == Decimal("5200.00")
        assert sum(point["settled"] for point in trend) == Decimal("5200.00")
        assert branch_summary["totals"]["settled_total"] == Decimal("5200.00")


def test_summary_aggregates_only_rows_some_metric_can_count(
    scenario, admin_user, make_filters, anchor
):
    with CaptureQueriesContext(connection) as queries:
        selectors.dashboard_summary(admin_user, make_filters(), now=anchor)

    assert len(queries) == 7
    assert all(" WHERE " in query["sql"] for query in queries.captured_queries)


class TestBreakdownNarrowing:
    def test_branch_filter_lists_one_branch(self, scenario, admin_user, make_filters, branch):
        filters = make_filters(branch=branch)

        assert [b.code for b in selectors.branches_for_breakdown(admin_user, filters)] == ["BLR01"]

    def test_agent_filter_lists_the_agents_branch(
        self, scenario, admin_user, make_filters, other_branch_agent
    ):
        filters = make_filters(agent=other_branch_agent)

        assert [b.code for b in selectors.branches_for_breakdown(admin_user, filters)] == ["MUM01"]
        assert list(selectors.agents_for_breakdown(admin_user, filters)) == [other_branch_agent]

    def test_branch_filter_lists_that_branchs_agents(
        self, scenario, admin_user, make_filters, other_branch, other_branch_agent
    ):
        filters = make_filters(branch=other_branch)

        assert list(selectors.agents_for_breakdown(admin_user, filters)) == [other_branch_agent]
