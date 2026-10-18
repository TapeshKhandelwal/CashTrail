from datetime import timedelta

import pytest
from django.urls import reverse

from apps.core.testing import factories

pytestmark = pytest.mark.django_db

SUMMARY = reverse("dashboard-summary")
TREND = reverse("dashboard-trend")
LIFECYCLE = reverse("dashboard-lifecycle")
BRANCHES = reverse("dashboard-branches")
AGENTS = reverse("dashboard-agents")


class TestSummaryEndpoint:
    def test_money_is_serialized_as_strings(self, scenario, admin_client, period):
        response = admin_client.get(SUMMARY, period)

        assert response.status_code == 200
        body = response.json()
        assert body["date_from"] == period["date_from"]
        assert body["expected"] == {"amount": "17770.00", "count": 2}
        assert body["collected"]["amount"] == "16500.00"
        assert body["collected"]["upi"] == {"amount": "2700.00", "count": 2}
        assert body["deposits"]["by_status"][0] == {
            "status": "PENDING",
            "amount": "2500.00",
            "count": 1,
        }
        assert body["collection_efficiency"] == "92.85"
        assert body["deposit_accuracy"] == "100.00"
        assert body["avg_settlement_lag_days"] == "2.0"
        assert body["discrepancies"]["open"] == {"amount": "506.40", "count": 2}
        assert body["pending_deposits"] == {"amount": "2500.00", "count": 1}

    def test_defaults_to_month_to_date(self, admin_client, today):
        body = admin_client.get(SUMMARY).json()

        assert body["date_from"] == today.replace(day=1).isoformat()
        assert body["date_to"] == today.isoformat()
        assert body["collection_efficiency"] is None

    def test_scope_is_applied_per_role(self, scenario, manager_client, agent_client, period):
        manager_view = manager_client.get(SUMMARY, period).json()
        agent_view = agent_client.get(SUMMARY, period).json()

        assert manager_view["collected"]["amount"] == "14500.00"
        assert agent_view["collected"]["amount"] == "12000.00"

    def test_filters_narrow_global_view(self, scenario, finance_client, period, other_branch):
        body = finance_client.get(
            SUMMARY, {**period, "branch": other_branch.pk, "status": "SETTLED"}
        ).json()

        assert body["collected"] == {
            "amount": "1200.00",
            "count": 1,
            "cash": {"amount": "0.00", "count": 0},
            "upi": {"amount": "1200.00", "count": 1},
        }

    def test_query_count_is_constant(
        self, scenario, admin_client, period, branch, agent, django_assert_max_num_queries
    ):
        # Request savepoint pair, auth user, branch and agent lookups, then one aggregate
        # per source table.
        with django_assert_max_num_queries(12):
            response = admin_client.get(SUMMARY, {**period, "branch": branch.pk, "agent": agent.pk})
        assert response.status_code == 200


class TestFilterValidation:
    @pytest.mark.parametrize(
        ("params", "field"),
        [
            ({"date_from": "2026-02-30"}, "date_from"),
            ({"date_from": "2026-10-10", "date_to": "2026-10-01"}, "date_from"),
            ({"status": "LOST"}, "status"),
            # Voided receipts are counted on their own, never narrowed to.
            ({"status": "VOIDED"}, "status"),
            ({"branch": "abc"}, "branch"),
            ({"agent": 999999}, "agent"),
        ],
    )
    def test_invalid_parameters_are_rejected(self, admin_client, params, field):
        response = admin_client.get(SUMMARY, params)

        assert response.status_code == 400
        error = response.json()["error"]
        assert error["code"] == "VALIDATION_ERROR"
        assert field in error["details"]

    def test_manager_cannot_widen_scope_to_another_branch(
        self, manager_client, other_branch, other_branch_agent
    ):
        by_branch = manager_client.get(SUMMARY, {"branch": other_branch.pk})
        by_agent = manager_client.get(SUMMARY, {"agent": other_branch_agent.pk})

        assert by_branch.status_code == 400
        assert "branch" in by_branch.json()["error"]["details"]
        assert by_agent.status_code == 400

    def test_agent_may_only_filter_on_themselves(self, agent_client, agent, other_agent, branch):
        assert agent_client.get(SUMMARY, {"agent": agent.pk}).status_code == 200
        assert agent_client.get(SUMMARY, {"branch": branch.pk}).status_code == 200
        assert agent_client.get(SUMMARY, {"agent": other_agent.pk}).status_code == 400

    def test_out_of_scope_and_missing_ids_look_the_same(self, manager_client, other_branch):
        out_of_scope = manager_client.get(SUMMARY, {"branch": other_branch.pk}).json()
        missing = manager_client.get(SUMMARY, {"branch": 987654}).json()

        assert out_of_scope["error"]["details"]["branch"][0] == (
            f'Invalid pk "{other_branch.pk}" - object does not exist.'
        )
        assert missing["error"]["details"]["branch"][0] == (
            'Invalid pk "987654" - object does not exist.'
        )

    def test_trend_range_is_capped(self, admin_client, today):
        response = admin_client.get(
            TREND,
            {"date_from": (today - timedelta(days=366)).isoformat(), "date_to": today.isoformat()},
        )

        assert response.status_code == 400
        assert "date_to" in response.json()["error"]["details"]


class TestOtherEndpoints:
    def test_trend(self, scenario, agent_client, period, today):
        points = agent_client.get(TREND, period).json()

        assert len(points) == 8
        assert points[-1] == {
            "date": today.isoformat(),
            "expected": "8885.00",
            "collected": "1000.00",
            "settled": "0.00",
        }

    def test_lifecycle(self, scenario, manager_client, period):
        body = manager_client.get(LIFECYCLE, period).json()

        assert [stage["stage"] for stage in body["stages"]] == [
            "COLLECTED",
            "BRANCH_RECEIVED",
            "DEPOSITED",
            "SETTLED",
        ]
        assert body["stages"][-1] == {
            "stage": "SETTLED",
            "label": "Settled",
            "amount": "4000.00",
            "count": 1,
        }
        assert body["by_status"][-1]["status"] == "VOIDED"

    def test_branch_table_is_paginated(self, scenario, admin_client, period):
        body = admin_client.get(BRANCHES, {**period, "page_size": 1}).json()

        assert body["count"] == 2
        assert body["next"] is not None
        row = body["results"][0]
        assert row["branch"]["code"] == "BLR01"
        assert row["collected"] == {"amount": "14500.00", "count": 7}
        assert row["collection_efficiency"] == "163.20"

    def test_agent_table_for_manager(self, scenario, manager_client, period, agent):
        body = manager_client.get(AGENTS, period).json()

        assert body["count"] == 2
        mine = next(r for r in body["results"] if r["agent"]["id"] == agent.pk)
        assert mine["agent"]["branch_code"] == "BLR01"
        assert mine["cash_with_agents"] == {"amount": "2499.00", "count": 3}
        assert mine["rejected_submissions"] == {"amount": "600.00", "count": 1}

    def test_agent_table_filtered_to_one_agent(self, scenario, admin_client, period, other_agent):
        body = admin_client.get(AGENTS, {**period, "agent": other_agent.pk}).json()

        assert [r["agent"]["username"] for r in body["results"]] == [other_agent.username]

    def test_tables_query_count_does_not_grow_with_rows(
        self, scenario, admin_client, period, django_assert_max_num_queries
    ):
        for code in ("DEL01", "HYD01", "PUN01", "CHN01"):
            factories.AgentFactory(branch=factories.BranchFactory(code=code))

        # Request savepoint pair, auth user, page count and rows, then one grouped query per
        # source table.
        with django_assert_max_num_queries(12):
            assert admin_client.get(BRANCHES, period).json()["count"] == 6
        with django_assert_max_num_queries(10):
            assert admin_client.get(AGENTS, period).json()["count"] == 7


class TestPermissions:
    @pytest.mark.parametrize("url", [SUMMARY, TREND, LIFECYCLE, BRANCHES, AGENTS])
    def test_anonymous_is_rejected(self, api_client, url):
        response = api_client.get(url)

        assert response.status_code == 401
        assert response.json()["error"]["code"] == "NOT_AUTHENTICATED"

    @pytest.mark.parametrize(
        ("url", "expected"),
        [(SUMMARY, 200), (TREND, 200), (LIFECYCLE, 200), (BRANCHES, 403), (AGENTS, 403)],
    )
    def test_agent_gets_own_stats_only(self, agent_client, url, expected):
        assert agent_client.get(url).status_code == expected

    @pytest.mark.parametrize("client_name", ["admin_client", "finance_client", "manager_client"])
    @pytest.mark.parametrize("url", [SUMMARY, TREND, LIFECYCLE, BRANCHES, AGENTS])
    def test_supervisors_see_every_dashboard(self, request, client_name, url):
        assert request.getfixturevalue(client_name).get(url).status_code == 200

    @pytest.mark.parametrize("url", [SUMMARY, BRANCHES])
    def test_dashboards_are_read_only(self, admin_client, url):
        assert admin_client.post(url, {}, format="json").status_code == 405
