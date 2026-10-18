import uuid
from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.collections.models import Collection
from apps.collections.services import void_collection
from apps.core.dates import business_date
from apps.core.testing import factories

pytestmark = pytest.mark.django_db

URL = "/api/collections/"


def detail_url(collection):
    return f"{URL}{collection.pk}/"


def results(response):
    assert response.status_code == 200, response.json()
    return response.json()["results"]


class TestRecord:
    def post(self, client, headers, **data):
        return client.post(URL, data, format="json", **headers)

    def test_records_and_returns_the_receipt(self, agent_client, loan, idempotency_headers):
        response = self.post(
            agent_client, idempotency_headers(), loan_id=loan.pk, amount="10000.00", remarks="Paid"
        )

        assert response.status_code == 201, response.json()
        body = response.json()
        assert body["receipt_number"].startswith("RCT-BLR01-")
        assert body["amount"] == "10000.00"
        assert body["mode"] == "CASH"
        assert body["status"] == "COLLECTED"
        assert body["loan_number"] == loan.loan_number
        assert body["loan_outstanding"] == "96619.00"
        assert body["balance_after"] == "96619.00"
        assert body["remarks"] == "Paid"
        assert [a["amount"] for a in body["allocations"]] == ["8885.00", "1115.00"]
        assert [a["installment_no"] for a in body["allocations"]] == [1, 2]
        assert [(s["status"], s["reached"]) for s in body["timeline"]] == [
            ("COLLECTED", True),
            ("SUBMITTED", False),
            ("BRANCH_RECEIVED", False),
            ("DEPOSITED", False),
            ("SETTLED", False),
        ]
        assert body["timeline"][0]["reference"] == body["receipt_number"]

    def test_retry_with_same_key_replays_the_receipt(self, agent_client, loan, idempotency_headers):
        headers = idempotency_headers()
        first = self.post(agent_client, headers, loan_id=loan.pk, amount="5000.00")
        retry = self.post(agent_client, headers, loan_id=loan.pk, amount="5000.00")

        assert first.status_code == 201
        assert retry.status_code == 200
        assert retry.headers["Idempotent-Replayed"] == "true"
        assert retry.json()["id"] == first.json()["id"]
        assert Collection.objects.count() == 1

    def test_key_reuse_with_another_payload_is_refused(
        self, agent_client, loan, idempotency_headers
    ):
        headers = idempotency_headers()
        self.post(agent_client, headers, loan_id=loan.pk, amount="5000.00")
        response = self.post(agent_client, headers, loan_id=loan.pk, amount="6000.00")

        assert response.status_code == 422
        assert response.json()["error"]["code"] == "IDEMPOTENCY_CONFLICT"

    def test_idempotency_key_is_required(self, agent_client, loan):
        response = agent_client.post(URL, {"loan_id": loan.pk, "amount": "5.00"}, format="json")

        assert response.status_code == 400
        assert response.json()["error"]["code"] == "IDEMPOTENCY_KEY_REQUIRED"

    def test_over_collection_reports_the_outstanding(self, agent_client, loan, idempotency_headers):
        response = self.post(agent_client, idempotency_headers(), loan_id=loan.pk, amount="200000")

        assert response.status_code == 422
        error = response.json()["error"]
        assert error["code"] == "OVER_COLLECTION"
        assert error["details"]["outstanding"] == "106619.00"

    def test_possible_duplicate_needs_confirmation(self, agent_client, loan, idempotency_headers):
        first = self.post(agent_client, idempotency_headers(), loan_id=loan.pk, amount="500.00")
        duplicate = self.post(agent_client, idempotency_headers(), loan_id=loan.pk, amount="500.00")

        assert duplicate.status_code == 409
        error = duplicate.json()["error"]
        assert error["code"] == "POSSIBLE_DUPLICATE"
        assert error["details"]["receipt_number"] == first.json()["receipt_number"]

        confirmed = self.post(
            agent_client,
            idempotency_headers(),
            loan_id=loan.pk,
            amount="500.00",
            confirm_duplicate=True,
        )
        assert confirmed.status_code == 201

    def test_float_amounts_are_rejected(self, agent_client, loan, idempotency_headers):
        response = self.post(agent_client, idempotency_headers(), loan_id=loan.pk, amount=10.5)

        assert response.status_code == 400
        assert "amount" in response.json()["error"]["details"]

    def test_upi_cannot_be_recorded_here(self, agent_client, loan, idempotency_headers):
        response = self.post(
            agent_client, idempotency_headers(), loan_id=loan.pk, amount="5.00", mode="UPI"
        )

        assert response.status_code == 400
        assert "mode" in response.json()["error"]["details"]

    def test_loan_of_another_agent_is_not_found(
        self, agent_client, other_agent_loan, idempotency_headers
    ):
        response = self.post(
            agent_client, idempotency_headers(), loan_id=other_agent_loan.pk, amount="5.00"
        )

        assert response.status_code == 404
        assert response.json()["error"]["code"] == "NOT_FOUND"

    def test_closed_loan_is_refused(self, agent_client, loan, idempotency_headers, agent, collect):
        collect(agent, loan, "106619.00")

        response = self.post(agent_client, idempotency_headers(), loan_id=loan.pk, amount="1.00")
        assert response.status_code == 422
        assert response.json()["error"]["code"] == "LOAN_NOT_ACTIVE"


class TestListAndFilters:
    @pytest.fixture
    def receipts(self, agent, other_agent, loan, other_agent_loan, collect):
        yesterday = timezone.now() - timedelta(days=1)
        return {
            "today": collect(agent, loan, "1000.00"),
            "yesterday": collect(agent, loan, "2000.00", collected_at=yesterday),
            "other_agent": collect(other_agent, other_agent_loan, "3000.00"),
            "upi": collect(
                agent,
                loan,
                "4000.00",
                mode=Collection.Mode.UPI,
                idempotency_key=None,
                gateway_payment_id="pay_LIST",
            ),
        }

    def ids(self, response):
        return {row["id"] for row in results(response)}

    def test_agent_sees_only_own_collections(self, agent_client, receipts):
        assert self.ids(agent_client.get(URL)) == {
            receipts[name].pk for name in ("today", "yesterday", "upi")
        }

    def test_manager_sees_the_branch(self, manager_client, receipts, other_branch_loan, collect):
        collect(other_branch_loan.customer.assigned_agent, other_branch_loan, "100.00")

        assert self.ids(manager_client.get(URL)) == {r.pk for r in receipts.values()}

    def test_finance_sees_every_branch(self, finance_client, receipts, other_branch_loan, collect):
        elsewhere = collect(other_branch_loan.customer.assigned_agent, other_branch_loan, "100.00")

        assert elsewhere.pk in self.ids(finance_client.get(URL))
        assert len(self.ids(finance_client.get(URL))) == len(receipts) + 1

    def test_other_branch_manager_sees_nothing(self, client_for, other_branch_manager, receipts):
        assert self.ids(client_for(other_branch_manager).get(URL)) == set()

    def test_filters(self, manager_client, receipts, agent, other_agent, loan):
        today = business_date()
        yesterday = today - timedelta(days=1)

        def ids(**params):
            return self.ids(manager_client.get(URL, params))

        assert ids(date=today) == {receipts[n].pk for n in ("today", "other_agent", "upi")}
        assert ids(date=yesterday) == {receipts["yesterday"].pk}
        assert ids(date_from=yesterday, date_to=yesterday) == {receipts["yesterday"].pk}
        assert ids(date_from=today) == ids(date=today)
        assert ids(agent=other_agent.pk) == {receipts["other_agent"].pk}
        assert ids(mode="UPI") == {receipts["upi"].pk}
        assert ids(loan=loan.pk) == {receipts[n].pk for n in ("today", "yesterday", "upi")}
        assert ids(customer=loan.customer_id) == ids(loan=loan.pk)
        assert ids(branch=agent.branch_id) == {r.pk for r in receipts.values()}

    def test_status_filter_accepts_several_values(self, agent, manager_client, receipts):
        void_collection(actor=agent, collection=receipts["today"], reason="Mistake.")

        response = manager_client.get(URL, {"status": ["VOIDED", "SETTLED"]})
        assert self.ids(response) == {receipts["today"].pk}

    def test_search_by_receipt_number(self, manager_client, receipts):
        receipt = receipts["yesterday"].receipt_number

        assert self.ids(manager_client.get(URL, {"search": receipt})) == {receipts["yesterday"].pk}

    def test_list_avoids_n_plus_one(self, manager_client, receipts, django_assert_max_num_queries):
        # user, count, page + the request savepoint pair
        with django_assert_max_num_queries(5):
            rows = results(manager_client.get(URL))
        assert len(rows) == len(receipts)
        assert rows[0]["customer_name"]


class TestRetrieve:
    def test_receipt_detail_shows_lifecycle(self, manager_client, agent, loan, collect):
        collection = collect(agent, loan, "100.00")

        later = collect(agent, loan, "200.00")

        body = manager_client.get(detail_url(collection)).json()
        assert body["receipt_number"] == collection.receipt_number
        assert body["balance_after"] == "106519.00"
        assert body["loan_outstanding"] == "106319.00"
        assert manager_client.get(detail_url(later)).json()["balance_after"] == "106319.00"
        assert body["agent_name"] == agent.get_full_name()
        assert len(body["allocations"]) == 1
        assert body["timeline"][0]["at"] is not None

    def test_settled_receipt_timeline(self, manager_client, loan):
        agent = loan.customer.assigned_agent
        submission = factories.CashSubmissionFactory(agent=agent, approved=True)
        deposit = factories.BankDepositFactory(branch=loan.branch, settled=True)
        now = timezone.now()
        collection = factories.CollectionFactory(
            loan=loan,
            status=Collection.Status.SETTLED,
            submission=submission,
            deposit=deposit,
            submitted_at=now,
            branch_received_at=now,
            deposited_at=now,
            settled_at=now,
        )

        timeline = manager_client.get(detail_url(collection)).json()["timeline"]
        assert all(step["reached"] for step in timeline)
        assert [step["reference"] for step in timeline[1:]] == [
            submission.submission_number,
            submission.submission_number,
            deposit.deposit_number,
            deposit.deposit_number,
        ]

    def test_out_of_scope_receipt_is_not_found(
        self, client_for, other_agent, other_branch_manager, agent, loan, collect
    ):
        collection = collect(agent, loan, "100.00")

        assert client_for(other_agent).get(detail_url(collection)).status_code == 404
        assert client_for(other_branch_manager).get(detail_url(collection)).status_code == 404

    def test_detail_query_count(
        self, agent_client, agent, loan, collect, django_assert_max_num_queries
    ):
        collection = collect(agent, loan, "20000.00")

        # user, receipt, allocations + the request savepoint pair
        with django_assert_max_num_queries(5):
            response = agent_client.get(detail_url(collection))
        assert len(response.json()["allocations"]) == 3


class TestVoid:
    def void(self, client, collection, reason="Recorded against the wrong loan."):
        return client.post(f"{detail_url(collection)}void/", {"reason": reason}, format="json")

    def test_agent_voids_own_receipt(self, agent_client, agent, loan, collect):
        collection = collect(agent, loan, "100.00")

        response = self.void(agent_client, collection)

        assert response.status_code == 200, response.json()
        body = response.json()
        assert body["status"] == "VOIDED"
        assert body["void_reason"] == "Recorded against the wrong loan."
        assert body["voided_by_name"] == agent.get_full_name()
        assert all(a["reversed_at"] for a in body["allocations"])
        assert [s["status"] for s in body["timeline"]] == ["COLLECTED", "VOIDED"]
        assert body["loan_outstanding"] == "106619.00"
        # The receipt still shows the balance it left when it was recorded.
        assert body["balance_after"] == "106519.00"

    def test_reason_is_required(self, agent_client, agent, loan, collect):
        collection = collect(agent, loan, "100.00")

        assert self.void(agent_client, collection, reason="").status_code == 400

    def test_voiding_twice_conflicts(self, agent_client, agent, loan, collect):
        collection = collect(agent, loan, "100.00")
        self.void(agent_client, collection)

        response = self.void(agent_client, collection)
        assert response.status_code == 409
        assert response.json()["error"]["code"] == "INVALID_STATE_TRANSITION"

    def test_other_agent_cannot_void(self, client_for, other_agent, agent, loan, collect):
        collection = collect(agent, loan, "100.00")

        assert self.void(client_for(other_agent), collection).status_code == 404


class TestDailySummary:
    SUMMARY_URL = f"{URL}daily-summary/"

    @pytest.fixture
    def activity(self, agent, other_agent, loan, other_agent_loan, collect):
        yesterday = timezone.now() - timedelta(days=1)
        collect(agent, loan, "1000.00")
        collect(agent, loan, "500.00")
        collect(agent, loan, "250.00", collected_at=yesterday)
        voided = collect(agent, loan, "70.00")
        void_collection(actor=agent, collection=voided, reason="Mistake.")
        collect(
            agent,
            loan,
            "4000.00",
            mode=Collection.Mode.UPI,
            idempotency_key=None,
            gateway_payment_id="pay_SUMMARY",
        )
        collect(other_agent, other_agent_loan, "300.00")

    def test_agent_sees_own_day(self, agent_client, activity):
        response = agent_client.get(self.SUMMARY_URL)

        assert response.status_code == 200
        assert response.json() == {
            "date": business_date().isoformat(),
            "count": 3,
            "total_amount": "5500.00",
            "cash_count": 2,
            "cash_amount": "1500.00",
            "upi_count": 1,
            "upi_amount": "4000.00",
            "voided_count": 1,
            "unsubmitted_count": 3,
            "unsubmitted_cash": "1750.00",
        }

    def test_agent_cannot_widen_scope(self, agent_client, other_agent, activity):
        body = agent_client.get(self.SUMMARY_URL, {"agent": other_agent.pk}).json()

        assert body["count"] == 0
        assert body["unsubmitted_cash"] == "0.00"

    def test_manager_sees_branch_and_can_pick_an_agent(self, manager_client, other_agent, activity):
        branch = manager_client.get(self.SUMMARY_URL).json()
        one_agent = manager_client.get(self.SUMMARY_URL, {"agent": other_agent.pk}).json()

        assert (branch["count"], branch["cash_amount"]) == (4, "1800.00")
        assert branch["unsubmitted_cash"] == "2050.00"
        assert (one_agent["count"], one_agent["total_amount"]) == (1, "300.00")

    def test_past_date(self, agent_client, activity):
        yesterday = business_date() - timedelta(days=1)

        body = agent_client.get(self.SUMMARY_URL, {"date": yesterday.isoformat()}).json()
        assert (body["date"], body["count"], body["cash_amount"]) == (
            yesterday.isoformat(),
            1,
            "250.00",
        )

    def test_other_branch_manager_sees_nothing(self, client_for, other_branch_manager, activity):
        body = client_for(other_branch_manager).get(self.SUMMARY_URL).json()

        assert body["count"] == 0
        assert body["total_amount"] == "0.00"

    def test_invalid_date_is_rejected(self, agent_client):
        response = agent_client.get(self.SUMMARY_URL, {"date": "yesterday"})

        assert response.status_code == 400


def test_idempotency_key_is_stored_on_the_collection(agent_client, loan):
    key = str(uuid.uuid4())
    response = agent_client.post(
        URL, {"loan_id": loan.pk, "amount": "5.00"}, format="json", HTTP_IDEMPOTENCY_KEY=key
    )

    assert response.status_code == 201
    assert Collection.objects.get().idempotency_key == uuid.UUID(key)
    assert Collection.objects.get().amount == Decimal("5.00")
