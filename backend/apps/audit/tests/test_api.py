from datetime import timedelta
from decimal import Decimal
from unittest import mock

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.audit.models import AuditAction, AuditLog
from apps.audit.services import log_event, snapshot
from apps.collections.models import Collection
from apps.core.dates import business_date
from apps.core.testing import factories
from apps.deposits.models import BankDeposit
from apps.loans.models import Loan

pytestmark = pytest.mark.django_db

LIST = reverse("audit-log-list")


def detail(entry) -> str:
    return reverse("audit-log-detail", args=[entry.pk])


@pytest.fixture
def trail(loan, agent, manager, other_branch_agent, other_branch_manager, finance_user):
    receipt = factories.CollectionFactory(loan=loan, amount=Decimal("1500.00"))
    other_loan = factories.LoanFactory(
        customer=factories.CustomerFactory(
            branch=other_branch_agent.branch, assigned_agent=other_branch_agent
        )
    )
    settlement = factories.BankDepositFactory(gateway=True)
    with mock.patch("django.utils.timezone.now", return_value=timezone.now() - timedelta(days=10)):
        old = log_event(manager, AuditAction.LOAN_CREATED, loan, after={"status": "ACTIVE"})
    return {
        "old": old,
        "receipt": log_event(
            agent,
            AuditAction.COLLECTION_RECORDED,
            receipt,
            after=snapshot(receipt, ["amount", "status", "loan"]),
        ),
        "other_branch": log_event(other_branch_manager, AuditAction.LOAN_CREATED, other_loan),
        "gateway": log_event(
            finance_user, AuditAction.GATEWAY_SETTLEMENT_RECORDED, settlement, after={}
        ),
    }


def ids(response) -> set[int]:
    return {row["id"] for row in response.json()["results"]}


class TestVisibility:
    @pytest.mark.parametrize("client_name", ["admin_client", "finance_client"])
    def test_global_roles_read_the_whole_trail(self, request, trail, client_name):
        response = request.getfixturevalue(client_name).get(LIST)

        assert response.status_code == 200
        assert ids(response) == {entry.pk for entry in trail.values()}

    def test_manager_reads_entries_of_their_branch(self, trail, manager_client):
        assert ids(manager_client.get(LIST)) == {trail["old"].pk, trail["receipt"].pk}

    def test_manager_cannot_open_other_entries(self, trail, manager_client):
        assert manager_client.get(detail(trail["receipt"])).status_code == 200
        for name in ("other_branch", "gateway"):
            response = manager_client.get(detail(trail[name]))
            assert response.status_code == 404
            assert response.json()["error"]["code"] == "NOT_FOUND"

    def test_agents_have_no_access(self, trail, agent_client):
        response = agent_client.get(LIST)

        assert response.status_code == 403
        assert response.json()["error"]["code"] == "PERMISSION_DENIED"

    def test_anonymous_is_rejected(self, api_client):
        assert api_client.get(LIST).status_code == 401

    @pytest.mark.parametrize("method", ["post", "put", "patch", "delete"])
    def test_trail_is_read_only(self, trail, admin_client, method):
        url = LIST if method == "post" else detail(trail["receipt"])

        assert getattr(admin_client, method)(url, {}, format="json").status_code == 405


def test_entry_shape(trail, admin_client, agent, branch):
    entry = trail["receipt"]

    body = admin_client.get(detail(entry)).json()

    assert body["action"] == "COLLECTION_RECORDED"
    assert body["action_label"] == "Repayment recorded"
    assert (body["entity_type"], body["entity_id"]) == ("collection", entry.entity_id)
    assert (body["actor"], body["actor_username"]) == (agent.pk, agent.username)
    assert (body["branch"], body["branch_code"]) == (branch.pk, "BLR01")
    assert body["after"]["amount"] == "1500.00"
    assert body["before"] is None


def test_system_entries_have_no_actor(admin_client, loan):
    receipt = factories.CollectionFactory(loan=loan, upi=True)
    entry = log_event(None, AuditAction.GATEWAY_PAYMENT_CAPTURED, receipt)

    body = admin_client.get(detail(entry)).json()

    assert (body["actor"], body["actor_username"], body["actor_name"]) == (None, None, None)


class TestFilters:
    def test_by_entity(self, trail, admin_client):
        entry = trail["receipt"]

        response = admin_client.get(
            LIST, {"entity_type": "collection", "entity_id": entry.entity_id}
        )

        assert ids(response) == {entry.pk}

    def test_by_actor_and_action(self, trail, admin_client, manager):
        by_actor = admin_client.get(LIST, {"actor": manager.pk})
        by_action = admin_client.get(LIST, {"action": "LOAN_CREATED"})

        assert ids(by_actor) == {trail["old"].pk}
        assert ids(by_action) == {trail["old"].pk, trail["other_branch"].pk}

    def test_by_branch(self, trail, finance_client, other_branch):
        assert ids(finance_client.get(LIST, {"branch": other_branch.pk})) == {
            trail["other_branch"].pk
        }

    def test_by_date_range(self, trail, admin_client):
        today = business_date()

        recent = admin_client.get(LIST, {"date_from": today.isoformat()})
        older = admin_client.get(LIST, {"date_to": (today - timedelta(days=5)).isoformat()})

        assert trail["old"].pk not in ids(recent)
        assert ids(recent) == {e.pk for k, e in trail.items() if k != "old"}
        assert ids(older) == {trail["old"].pk}

    def test_manager_filters_stay_within_scope(self, trail, manager_client, other_branch):
        assert ids(manager_client.get(LIST, {"branch": other_branch.pk})) == set()

    def test_unknown_action_is_rejected(self, admin_client):
        response = admin_client.get(LIST, {"action": "MONEY_VANISHED"})

        assert response.status_code == 400
        assert "action" in response.json()["error"]["details"]

    def test_newest_first(self, trail, admin_client):
        results = admin_client.get(LIST).json()["results"]

        assert results[-1]["id"] == trail["old"].pk
        assert [r["id"] for r in results[:3]] == [
            trail["gateway"].pk,
            trail["other_branch"].pk,
            trail["receipt"].pk,
        ]


def test_list_query_count_is_constant(trail, admin_client, django_assert_max_num_queries):
    def add_branch_entries():
        for _ in range(5):
            log_event(None, AuditAction.BRANCH_UPDATED, factories.BranchFactory())

    add_branch_entries()
    # Request savepoint pair, auth user, page count, one joined page query, and one
    # reference lookup per record type on the page (loan, receipt, deposit, branch).
    with django_assert_max_num_queries(9):
        assert admin_client.get(LIST).json()["count"] == 9

    add_branch_entries()
    with django_assert_max_num_queries(9):
        assert admin_client.get(LIST).json()["count"] == 14


class TestRecordReference:
    def test_entries_name_the_record_and_its_document_number(self, trail, admin_client):
        rows = {row["id"]: row for row in admin_client.get(LIST).json()["results"]}
        receipt = rows[trail["receipt"].pk]
        loan = rows[trail["old"].pk]
        settlement = rows[trail["gateway"].pk]

        assert receipt["entity_label"] == "Receipt"
        assert receipt["entity_reference"].startswith("RCT-")
        assert (loan["entity_label"], loan["entity_reference"]) == (
            "Loan",
            Loan.objects.get(pk=trail["old"].entity_id).loan_number,
        )
        assert settlement["entity_label"] == "Deposit"
        assert settlement["entity_reference"] == (
            BankDeposit.objects.get(pk=trail["gateway"].entity_id).deposit_number
        )

    def test_detail_carries_the_reference_too(self, trail, admin_client):
        body = admin_client.get(detail(trail["receipt"])).json()

        assert body["entity_label"] == "Receipt"
        assert body["entity_reference"] == (
            Collection.objects.get(pk=trail["receipt"].entity_id).receipt_number
        )

    def test_bank_accounts_show_the_masked_number(self, admin_client):
        account = factories.BankAccountFactory()
        entry = log_event(None, AuditAction.BANK_ACCOUNT_CREATED, account)

        body = admin_client.get(detail(entry)).json()

        assert body["entity_label"] == "Bank account"
        assert body["entity_reference"] == f"XXXX{account.account_number_last4}"

    def test_discrepancy_shows_the_record_it_was_raised_on(self, admin_client):
        discrepancy = factories.DiscrepancyFactory()
        entry = log_event(None, AuditAction.DISCREPANCY_RAISED, discrepancy)

        body = admin_client.get(detail(entry)).json()

        assert (body["entity_label"], body["entity_reference"]) == (
            "Discrepancy",
            discrepancy.submission.submission_number,
        )

    def test_a_missing_record_has_no_reference(self, admin_client):
        entry = AuditLog.objects.create(
            action=AuditAction.LOAN_CREATED, entity_type="loan", entity_id="999999"
        )

        body = admin_client.get(detail(entry)).json()

        assert (body["entity_label"], body["entity_reference"]) == ("Loan", None)
        assert body["request_id"] is None
