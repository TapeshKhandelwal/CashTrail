from decimal import Decimal

import pytest

from apps.collections.models import Collection
from apps.core.dates import business_date
from apps.core.testing import factories
from apps.reconciliation import services
from apps.reconciliation.models import CashSubmission, Discrepancy

pytestmark = pytest.mark.django_db

SUBMISSIONS = "/api/submissions/"
DISCREPANCIES = "/api/discrepancies/"
BRANCH_SUMMARY = "/api/reconciliation/branch-summary/"
AGENTS_SUMMARY = "/api/reconciliation/agents-summary/"


def _approve_url(submission):
    return f"{SUBMISSIONS}{submission.pk}/approve/"


def _reject_url(submission):
    return f"{SUBMISSIONS}{submission.pk}/reject/"


def _resolve_url(discrepancy):
    return f"{DISCREPANCIES}{discrepancy.pk}/resolve/"


@pytest.fixture
def shortage(manager, pending_submission):
    submission = services.approve_submission(
        manager,
        pending_submission,
        received_amount=Decimal("48500.00"),
        reason_code=Discrepancy.ReasonCode.AGENT_SHORTAGE,
        remarks="Short by 1500.",
    )
    return submission.discrepancies.get()


class TestCreateSubmissionEndpoint:
    def test_agent_submits_cash(self, agent_client, receive_cash, idempotency_headers):
        collections = receive_cash("30000.00", "20000.00")

        response = agent_client.post(
            SUBMISSIONS,
            {
                "collection_ids": [c.pk for c in collections],
                "declared_amount": "50000.00",
                "denominations": {"500": 100},
            },
            format="json",
            **idempotency_headers(),
        )

        assert response.status_code == 201, response.data
        body = response.json()
        assert body["status"] == "SUBMITTED"
        assert body["expected_amount"] == "50000.00"
        assert body["declared_amount"] == "50000.00"
        assert body["received_amount"] is None
        assert body["difference"] is None
        assert body["denominations"] == {"500": 100}
        assert body["collection_count"] == 2
        assert sorted(c["id"] for c in body["collections"]) == sorted(c.pk for c in collections)
        assert body["collections"][0]["loan_number"]

    def test_retry_with_same_key_replays(self, agent_client, receive_cash, idempotency_headers):
        collection = receive_cash("1000.00")[0]
        headers = idempotency_headers()
        payload = {"collection_ids": [collection.pk], "declared_amount": "1000.00"}

        first = agent_client.post(SUBMISSIONS, payload, format="json", **headers)
        replay = agent_client.post(SUBMISSIONS, payload, format="json", **headers)

        assert first.status_code == 201
        assert replay.status_code == 200
        assert replay.headers["Idempotent-Replayed"] == "true"
        assert replay.json()["id"] == first.json()["id"]

    def test_idempotency_key_is_required(self, agent_client, receive_cash):
        collection = receive_cash("1000.00")[0]

        response = agent_client.post(
            SUBMISSIONS,
            {"collection_ids": [collection.pk], "declared_amount": "1000.00"},
            format="json",
        )

        assert response.status_code == 400
        assert response.json()["error"]["code"] == "IDEMPOTENCY_KEY_REQUIRED"

    @pytest.mark.parametrize(
        ("payload", "field"),
        [
            ({"collection_ids": [], "declared_amount": "1.00"}, "collection_ids"),
            ({"collection_ids": [1, 1], "declared_amount": "1.00"}, "collection_ids"),
            ({"collection_ids": [1], "declared_amount": 1000.5}, "declared_amount"),
            ({"collection_ids": [1], "declared_amount": "-1.00"}, "declared_amount"),
            (
                {"collection_ids": [1], "declared_amount": "1.00", "denominations": {"3": 1}},
                "denominations",
            ),
        ],
    )
    def test_malformed_input(self, agent_client, idempotency_headers, payload, field):
        response = agent_client.post(SUBMISSIONS, payload, format="json", **idempotency_headers())

        assert response.status_code == 400
        error = response.json()["error"]
        assert error["code"] == "VALIDATION_ERROR"
        assert field in error["details"]

    def test_second_pending_submission_conflicts(
        self, agent_client, receive_cash, pending_submission, idempotency_headers
    ):
        collection = receive_cash("100.00")[0]

        response = agent_client.post(
            SUBMISSIONS,
            {"collection_ids": [collection.pk], "declared_amount": "100.00"},
            format="json",
            **idempotency_headers(),
        )

        assert response.status_code == 409
        assert response.json()["error"]["code"] == "PENDING_SUBMISSION_EXISTS"

    def test_someone_elses_receipts_are_not_found(
        self, agent_client, receive_cash, other_agent_loan, idempotency_headers
    ):
        theirs = receive_cash("100.00", loan=other_agent_loan)[0]

        response = agent_client.post(
            SUBMISSIONS,
            {"collection_ids": [theirs.pk], "declared_amount": "100.00"},
            format="json",
            **idempotency_headers(),
        )

        assert response.status_code == 404
        assert Collection.objects.get(pk=theirs.pk).status == Collection.Status.COLLECTED

    @pytest.mark.parametrize("client", ["manager_client", "admin_client", "finance_client"])
    def test_only_agents_submit(self, request, client, idempotency_headers):
        response = request.getfixturevalue(client).post(
            SUBMISSIONS,
            {"collection_ids": [1], "declared_amount": "1.00"},
            format="json",
            **idempotency_headers(),
        )

        assert response.status_code == 403


class TestListSubmissions:
    @pytest.fixture
    def submissions(self, pending_submission, other_agent, other_agent_loan, receive_cash, submit):
        theirs = submit(receive_cash("700.00", loan=other_agent_loan), actor=other_agent)
        return pending_submission, theirs

    @pytest.mark.parametrize(
        ("client", "visible"),
        [
            ("agent_client", {0}),
            ("manager_client", {0, 1}),
            ("finance_client", {0, 1}),
            ("admin_client", {0, 1}),
        ],
    )
    def test_list_is_scoped_by_role(self, request, submissions, client, visible):
        response = request.getfixturevalue(client).get(SUBMISSIONS)

        assert response.status_code == 200
        ids = {row["id"] for row in response.json()["results"]}
        assert ids == {submissions[i].pk for i in visible}

    def test_other_branch_sees_nothing(self, client_for, other_branch_manager, submissions):
        response = client_for(other_branch_manager).get(SUBMISSIONS)

        assert response.json()["count"] == 0

    def test_filters(self, manager_client, manager, submissions, agent):
        services.approve_submission(manager, submissions[1], received_amount=Decimal("700.00"))
        today = business_date().isoformat()

        pending = manager_client.get(SUBMISSIONS, {"status": "SUBMITTED"}).json()
        awaiting = manager_client.get(SUBMISSIONS, {"awaiting_deposit": "true"}).json()
        by_agent = manager_client.get(SUBMISSIONS, {"agent": agent.pk}).json()
        by_date = manager_client.get(SUBMISSIONS, {"date_from": today, "date_to": today}).json()
        before = manager_client.get(SUBMISSIONS, {"date_to": "2020-01-01"}).json()

        assert [row["id"] for row in pending["results"]] == [submissions[0].pk]
        assert [row["id"] for row in awaiting["results"]] == [submissions[1].pk]
        assert [row["id"] for row in by_agent["results"]] == [submissions[0].pk]
        assert by_date["count"] == 2
        assert before["count"] == 0

    def test_list_query_count_is_constant(
        self, manager_client, submissions, django_assert_max_num_queries
    ):
        with django_assert_max_num_queries(6):
            response = manager_client.get(SUBMISSIONS)

        assert response.json()["count"] == 2


class TestSubmissionDetail:
    def test_out_of_scope_is_not_found(self, client_for, other_branch_manager, pending_submission):
        response = client_for(other_branch_manager).get(f"{SUBMISSIONS}{pending_submission.pk}/")

        assert response.status_code == 404
        assert response.json()["error"]["code"] == "NOT_FOUND"

    def test_rejected_submission_still_lists_its_receipts(
        self, agent_client, manager, pending_submission
    ):
        services.reject_submission(manager, pending_submission, reason="Recount.")

        body = agent_client.get(f"{SUBMISSIONS}{pending_submission.pk}/").json()

        assert body["status"] == "REJECTED"
        assert body["rejection_reason"] == "Recount."
        assert body["collection_count"] == 2
        assert len(body["collections"]) == 2
        assert {c["status"] for c in body["collections"]} == {"COLLECTED"}


class TestApproveEndpoint:
    def test_brief_example_records_1500_shortage(self, manager_client, pending_submission):
        response = manager_client.post(
            _approve_url(pending_submission),
            {
                "received_amount": "48500.00",
                "denominations": {"500": 90, "200": 15, "100": 5},
                "reason_code": "AGENT_SHORTAGE",
                "remarks": "Agent short by 1500.",
            },
            format="json",
        )

        assert response.status_code == 200, response.data
        body = response.json()
        assert body["status"] == "APPROVED_WITH_DISCREPANCY"
        assert body["expected_amount"] == "50000.00"
        assert body["received_amount"] == "48500.00"
        assert body["difference"] == "1500.00"
        assert body["reviewed_by_name"] is not None
        [discrepancy] = body["discrepancies"]
        assert discrepancy["kind"] == "CASH_SHORTAGE"
        assert discrepancy["direction"] == "SHORT"
        assert discrepancy["amount"] == "1500.00"
        assert discrepancy["status"] == "OPEN"
        assert {c["status"] for c in body["collections"]} == {"BRANCH_RECEIVED"}

    def test_excess_shows_negative_difference(self, manager_client, pending_submission):
        response = manager_client.post(
            _approve_url(pending_submission),
            {"received_amount": "50250.00", "reason_code": "COUNTING_ERROR", "remarks": "Extra."},
            format="json",
        )

        assert response.json()["difference"] == "-250.00"
        assert response.json()["discrepancies"][0]["kind"] == "CASH_EXCESS"

    def test_double_approval_conflicts(self, manager_client, pending_submission):
        payload = {"received_amount": "50000.00"}
        manager_client.post(_approve_url(pending_submission), payload, format="json")

        response = manager_client.post(_approve_url(pending_submission), payload, format="json")

        assert response.status_code == 409
        assert response.json()["error"]["code"] == "INVALID_STATE_TRANSITION"

    def test_denomination_mismatch(self, manager_client, pending_submission):
        response = manager_client.post(
            _approve_url(pending_submission),
            {"received_amount": "50000.00", "denominations": {"500": 99}},
            format="json",
        )

        assert response.status_code == 422
        error = response.json()["error"]
        assert error["code"] == "DENOMINATION_MISMATCH"
        assert error["details"] == {
            "denominations_total": "49500.00",
            "received_amount": "50000.00",
        }

    def test_difference_without_explanation(self, manager_client, pending_submission):
        response = manager_client.post(
            _approve_url(pending_submission), {"received_amount": "48500.00"}, format="json"
        )

        assert response.status_code == 422
        error = response.json()["error"]
        assert error["code"] == "VALIDATION_FAILED"
        assert {"reason_code", "remarks"} <= set(error["details"])
        pending_submission.refresh_from_db()
        assert pending_submission.status == CashSubmission.Status.SUBMITTED

    def test_other_branch_manager_gets_not_found(
        self, client_for, other_branch_manager, pending_submission
    ):
        response = client_for(other_branch_manager).post(
            _approve_url(pending_submission), {"received_amount": "50000.00"}, format="json"
        )

        assert response.status_code == 404

    @pytest.mark.parametrize("client", ["agent_client", "finance_client"])
    def test_agents_and_finance_cannot_approve(self, request, client, pending_submission):
        response = request.getfixturevalue(client).post(
            _approve_url(pending_submission), {"received_amount": "50000.00"}, format="json"
        )

        assert response.status_code == 403
        assert response.json()["error"]["code"] == "PERMISSION_DENIED"

    def test_admin_can_approve(self, admin_client, pending_submission):
        response = admin_client.post(
            _approve_url(pending_submission), {"received_amount": "50000.00"}, format="json"
        )

        assert response.status_code == 200
        assert response.json()["status"] == "APPROVED"


class TestRejectEndpoint:
    def test_reject_returns_receipts(self, manager_client, pending_submission):
        response = manager_client.post(
            _reject_url(pending_submission), {"reason": "Cash bundle missing."}, format="json"
        )

        assert response.status_code == 200
        assert response.json()["status"] == "REJECTED"
        assert not Collection.objects.filter(submission=pending_submission).exists()

    def test_reason_is_required(self, manager_client, pending_submission):
        response = manager_client.post(
            _reject_url(pending_submission), {"reason": " "}, format="json"
        )

        assert response.status_code == 400
        assert "reason" in response.json()["error"]["details"]

    def test_cannot_reject_approved(self, manager_client, manager, pending_submission):
        services.approve_submission(manager, pending_submission, received_amount=Decimal("50000"))

        response = manager_client.post(
            _reject_url(pending_submission), {"reason": "Too late."}, format="json"
        )

        assert response.status_code == 409


class TestDiscrepancyEndpoints:
    @pytest.mark.parametrize(
        "client", ["agent_client", "manager_client", "finance_client", "admin_client"]
    )
    def test_list_visible_to_responsible_agent_branch_and_global_roles(
        self, request, shortage, client
    ):
        response = request.getfixturevalue(client).get(DISCREPANCIES)

        assert response.status_code == 200
        assert [row["id"] for row in response.json()["results"]] == [shortage.pk]

    @pytest.mark.parametrize("user", ["other_agent", "other_branch_manager"])
    def test_list_hidden_from_others(self, client_for, request, shortage, user):
        response = client_for(request.getfixturevalue(user)).get(DISCREPANCIES)

        assert response.json()["count"] == 0

    def test_list_filters(self, manager_client, shortage):
        open_cash = manager_client.get(
            DISCREPANCIES, {"kind": ["CASH_SHORTAGE", "CASH_EXCESS"], "status": "OPEN"}
        ).json()
        resolved = manager_client.get(DISCREPANCIES, {"status": "RESOLVED"}).json()
        deposit_kind = manager_client.get(DISCREPANCIES, {"kind": "DEPOSIT_MISMATCH"}).json()

        assert [row["id"] for row in open_cash["results"]] == [shortage.pk]
        row = open_cash["results"][0]
        assert row["amount"] == "1500.00"
        assert row["submission_number"] == shortage.submission.submission_number
        assert row["branch_code"] == "BLR01"
        assert resolved["count"] == 0
        assert deposit_kind["count"] == 0

    def test_manager_raises_manually(self, manager_client, manager, pending_submission):
        services.approve_submission(manager, pending_submission, received_amount=Decimal("50000"))

        response = manager_client.post(
            DISCREPANCIES,
            {
                "kind": "CASH_SHORTAGE",
                "amount": "500.00",
                "reason_code": "OTHER",
                "notes": "Counterfeit note found.",
                "submission_id": pending_submission.pk,
            },
            format="json",
        )

        assert response.status_code == 201, response.data
        assert response.json()["direction"] == "SHORT"
        assert response.json()["raised_by"] == manager.pk

    def test_agent_cannot_raise(self, agent_client, pending_submission):
        response = agent_client.post(
            DISCREPANCIES,
            {
                "kind": "CASH_SHORTAGE",
                "amount": "1.00",
                "reason_code": "OTHER",
                "notes": "n/a",
                "submission_id": pending_submission.pk,
            },
            format="json",
        )

        assert response.status_code == 403

    def test_manager_resolves_shortage(self, manager_client, shortage):
        response = manager_client.post(
            _resolve_url(shortage),
            {"outcome": "RESOLVED", "resolution_notes": "Agent repaid."},
            format="json",
        )

        assert response.status_code == 200
        body = response.json()
        assert body["status"] == "RESOLVED"
        assert body["resolution_notes"] == "Agent repaid."
        assert body["resolved_by_name"] is not None

    def test_finance_cannot_resolve_cash_discrepancy(self, finance_client, shortage):
        response = finance_client.post(
            _resolve_url(shortage),
            {"outcome": "WRITTEN_OFF", "resolution_notes": "n/a"},
            format="json",
        )

        assert response.status_code == 403
        assert response.json()["error"]["code"] == "SCOPE_VIOLATION"

    def test_resolving_twice_conflicts(self, manager_client, shortage):
        payload = {"outcome": "WRITTEN_OFF", "resolution_notes": "Below threshold."}
        manager_client.post(_resolve_url(shortage), payload, format="json")

        response = manager_client.post(_resolve_url(shortage), payload, format="json")

        assert response.status_code == 409

    def test_resolve_rejects_unknown_outcome(self, manager_client, shortage):
        response = manager_client.post(
            _resolve_url(shortage), {"outcome": "OPEN", "resolution_notes": "x"}, format="json"
        )

        assert response.status_code == 400

    def test_agent_cannot_resolve(self, agent_client, shortage):
        response = agent_client.post(
            _resolve_url(shortage), {"outcome": "RESOLVED", "resolution_notes": "x"}, format="json"
        )

        assert response.status_code == 403


class TestSummaryEndpoints:
    def test_branch_summary_for_manager(self, manager_client, pending_submission):
        response = manager_client.get(BRANCH_SUMMARY)

        assert response.status_code == 200
        body = response.json()
        today = business_date().isoformat()
        assert body["date_from"] == body["date_to"] == today
        [row] = body["branches"]
        assert row["branch_code"] == "BLR01"
        assert row["pending_verification"] == "50000.00"
        assert row["pending_submissions"] == 1
        assert body["totals"]["collected_cash"] == "50000.00"

    def test_open_discrepancy_total_includes_gateway_mismatches(
        self, finance_client, finance_user, shortage, branch
    ):
        services.raise_discrepancy(
            finance_user,
            kind=Discrepancy.Kind.GATEWAY_MISMATCH,
            direction=Discrepancy.Direction.SHORT,
            amount=Decimal("10.00"),
            reason_code=Discrepancy.ReasonCode.OTHER,
            notes="Fee higher than agreed.",
            deposit_id=factories.BankDepositFactory(gateway=True, settled=True).pk,
        )

        everything = finance_client.get(BRANCH_SUMMARY).json()
        one_branch = finance_client.get(BRANCH_SUMMARY, {"branch": branch.pk}).json()

        assert everything["totals"]["open_discrepancies"] == 2
        assert everything["totals"]["open_shortage"] == "1510.00"
        assert [row["open_discrepancies"] for row in everything["branches"]] == [1]
        assert one_branch["totals"]["open_discrepancies"] == 1
        assert one_branch["totals"]["open_shortage"] == "1500.00"

    def test_manager_totals_leave_out_gateway_mismatches(
        self, manager_client, finance_user, shortage
    ):
        services.raise_discrepancy(
            finance_user,
            kind=Discrepancy.Kind.GATEWAY_MISMATCH,
            direction=Discrepancy.Direction.SHORT,
            amount=Decimal("10.00"),
            reason_code=Discrepancy.ReasonCode.OTHER,
            notes="Fee higher than agreed.",
            deposit_id=factories.BankDepositFactory(gateway=True, settled=True).pk,
        )

        assert manager_client.get(BRANCH_SUMMARY).json()["totals"]["open_discrepancies"] == 1

    def test_agents_cannot_see_branch_summary(self, agent_client):
        assert agent_client.get(BRANCH_SUMMARY).status_code == 403

    def test_date_range_must_be_ordered(self, manager_client):
        response = manager_client.get(
            BRANCH_SUMMARY, {"date_from": "2026-10-10", "date_to": "2026-10-01"}
        )

        assert response.status_code == 400
        assert "date_from" in response.json()["error"]["details"]

    def test_agents_summary_for_agent_is_their_own(self, agent_client, agent, receive_cash):
        receive_cash("1000.00")

        body = agent_client.get(AGENTS_SUMMARY).json()

        [row] = body["agents"]
        assert row["agent_id"] == agent.pk
        assert row["cash_in_hand"] == "1000.00"
        assert row["held_under_1d"] == "1000.00"
        assert row["oldest_held_hours"] == 0

    def test_agents_summary_for_manager_lists_branch_agents(
        self, manager_client, agent, other_agent, other_branch_agent
    ):
        body = manager_client.get(AGENTS_SUMMARY).json()

        assert {row["agent_id"] for row in body["agents"]} == {agent.pk, other_agent.pk}

    @pytest.mark.parametrize("url", [BRANCH_SUMMARY, AGENTS_SUMMARY, SUBMISSIONS, DISCREPANCIES])
    def test_authentication_required(self, api_client, url):
        response = api_client.get(url)

        assert response.status_code == 401
        assert response.json()["error"]["code"] == "NOT_AUTHENTICATED"
