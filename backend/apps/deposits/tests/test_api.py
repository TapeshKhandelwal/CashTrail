from datetime import timedelta

import pytest
from django.utils import timezone

from apps.collections.models import Collection
from apps.core.dates import business_date
from apps.core.testing import factories
from apps.deposits.models import BankAccount, BankDeposit

pytestmark = pytest.mark.django_db

BANK_ACCOUNTS = "/api/bank-accounts/"
DEPOSITS = "/api/deposits/"
PENDING_CASH = "/api/deposits/pending-cash/"
GATEWAY_SETTLEMENTS = "/api/gateway-settlements/"
UNSETTLED_UPI = "/api/gateway-settlements/pending/"


def detail(deposit, action=""):
    return f"{DEPOSITS}{deposit.pk}/{action + '/' if action else ''}"


def deposit_payload(submissions, bank_account, **overrides):
    return {
        "submission_ids": [s.pk for s in submissions],
        "bank_account_id": bank_account.pk,
        "deposited_amount": str(sum(s.received_amount or s.expected_amount for s in submissions)),
        "deposit_date": business_date().isoformat(),
        "reference_number": "slip 0001",
        **overrides,
    }


@pytest.fixture
def post_deposit(manager_client, idempotency_headers, bank_account):
    def post(submissions, client=None, headers=None, **overrides):
        return (client or manager_client).post(
            DEPOSITS,
            deposit_payload(submissions, bank_account, **overrides),
            format="json",
            **(headers or idempotency_headers()),
        )

    return post


@pytest.fixture
def pending_deposit(post_deposit, branch_cash):
    res = post_deposit([branch_cash("3000.00", "2000.00")])
    assert res.status_code == 201, res.data
    return BankDeposit.objects.get(pk=res.data["id"])


def error_code(res):
    return res.data["error"]["code"]


# Bank accounts ----------------------------------------------------------------------------


class TestBankAccountsApi:
    def test_admin_creates_account_and_only_last_four_digits_are_kept(self, admin_client):
        res = admin_client.post(
            BANK_ACCOUNTS,
            {
                "bank_name": "HDFC Bank",
                "account_name": "CashTrail Collections",
                "account_number": "50100012349012",
                "ifsc": "hdfc0000123",
            },
            format="json",
        )

        assert res.status_code == 201, res.data
        assert res.data["masked_account_number"] == "XXXX9012"
        assert res.data["ifsc"] == "HDFC0000123"
        assert "account_number" not in res.data
        account = BankAccount.objects.get(pk=res.data["id"])
        assert account.account_number_last4 == "9012"

    def test_invalid_account_details_are_rejected(self, admin_client):
        res = admin_client.post(
            BANK_ACCOUNTS,
            {"bank_name": "X", "account_name": "Y", "account_number": "12ab", "ifsc": "BAD"},
            format="json",
        )

        assert res.status_code == 400
        assert {"account_number", "ifsc"} <= res.data["error"]["details"].keys()

    @pytest.mark.parametrize(
        ("client_fixture", "status"),
        [
            ("admin_client", 200),
            ("manager_client", 200),
            ("finance_client", 200),
            ("agent_client", 403),
        ],
    )
    def test_read_access_by_role(self, request, bank_account, client_fixture, status):
        client = request.getfixturevalue(client_fixture)

        res = client.get(BANK_ACCOUNTS)

        assert res.status_code == status
        if status == 200:
            assert res.data["results"][0]["masked_account_number"].startswith("XXXX")

    @pytest.mark.parametrize("client_fixture", ["manager_client", "finance_client"])
    def test_only_admin_writes(self, request, bank_account, client_fixture):
        client = request.getfixturevalue(client_fixture)

        assert client.post(BANK_ACCOUNTS, {}, format="json").status_code == 403
        res = client.patch(f"{BANK_ACCOUNTS}{bank_account.pk}/", {"is_active": False})
        assert res.status_code == 403

    def test_admin_deactivates_account(self, admin_client, bank_account):
        res = admin_client.patch(
            f"{BANK_ACCOUNTS}{bank_account.pk}/", {"is_active": False}, format="json"
        )

        assert res.status_code == 200
        assert res.data["is_active"] is False

    def test_used_account_details_are_locked(self, admin_client, bank_account):
        factories.BankDepositFactory(bank_account=bank_account)

        res = admin_client.patch(
            f"{BANK_ACCOUNTS}{bank_account.pk}/", {"account_number": "998877665544"}, format="json"
        )

        assert res.status_code == 409
        assert error_code(res) == "RECORD_LOCKED"

    def test_put_and_delete_are_not_exposed(self, admin_client, bank_account):
        url = f"{BANK_ACCOUNTS}{bank_account.pk}/"

        assert admin_client.put(url, {}, format="json").status_code == 405
        assert admin_client.delete(url).status_code == 405

    def test_filter_active_cash_accounts(self, manager_client, bank_account, gateway_bank_account):
        factories.BankAccountFactory(is_active=False)

        res = manager_client.get(BANK_ACCOUNTS, {"is_active": "true", "is_gateway": "false"})

        assert [row["id"] for row in res.data["results"]] == [bank_account.pk]


# Creating deposits --------------------------------------------------------------------------


class TestCreateDepositApi:
    def test_manager_deposits_approved_cash(self, post_deposit, branch_cash):
        submission = branch_cash("3000.00", "2000.00")

        res = post_deposit([submission])

        assert res.status_code == 201, res.data
        assert res.data["status"] == "PENDING"
        assert res.data["reference_number"] == "SLIP0001"
        assert res.data["expected_amount"] == "5000.00"
        assert res.data["collections_count"] == 2
        assert [s["id"] for s in res.data["submissions"]] == [submission.pk]
        assert res.data["bank_account"]["masked_account_number"].startswith("XXXX")

    def test_retry_with_same_key_replays(self, post_deposit, branch_cash, idempotency_headers):
        submission = branch_cash()
        headers = idempotency_headers()

        first = post_deposit([submission], headers=headers)
        retry = post_deposit([submission], headers=headers)

        assert (first.status_code, retry.status_code) == (201, 200)
        assert retry["Idempotent-Replayed"] == "true"
        assert retry.data["id"] == first.data["id"]

    def test_idempotency_key_is_required(self, manager_client, bank_account, branch_cash):
        res = manager_client.post(
            DEPOSITS, deposit_payload([branch_cash()], bank_account), format="json"
        )

        assert res.status_code == 400
        assert error_code(res) == "IDEMPOTENCY_KEY_REQUIRED"

    def test_duplicate_reference_returns_409(self, post_deposit, branch_cash):
        assert post_deposit([branch_cash()], reference_number="SLIP0001").status_code == 201

        res = post_deposit([branch_cash()], reference_number="  Slip 0001 ")

        assert res.status_code == 409
        assert error_code(res) == "DUPLICATE_BANK_REFERENCE"

    def test_mismatch_without_remarks_returns_422(self, post_deposit, branch_cash):
        res = post_deposit([branch_cash("3000.00", "2000.00")], deposited_amount="4500.00")

        assert res.status_code == 422
        assert error_code(res) == "VALIDATION_FAILED"
        assert res.data["error"]["details"]["difference"] == "500.00"

    def test_mismatch_with_remarks_shows_discrepancy(self, post_deposit, branch_cash):
        res = post_deposit(
            [branch_cash("3000.00", "2000.00")],
            deposited_amount="4500.00",
            remarks="₹500 note found counterfeit at the bank.",
        )

        assert res.status_code == 201
        assert res.data["discrepancies"][0]["kind"] == "DEPOSIT_MISMATCH"
        assert res.data["discrepancies"][0]["amount"] == "500.00"
        assert res.data["reconciliation"]["deposit_difference"] == "500.00"

    def test_pending_submission_is_rejected(self, post_deposit, agent):
        submission = factories.CashSubmissionFactory(agent=agent)

        res = post_deposit([submission])

        assert res.status_code == 422
        assert res.data["error"]["details"] == {"submission_ids": [submission.pk]}

    def test_other_branch_cash_is_not_found(
        self, post_deposit, client_for, other_branch_manager, branch_cash
    ):
        res = post_deposit([branch_cash()], client=client_for(other_branch_manager))

        assert res.status_code == 404

    def test_float_amounts_are_rejected(self, post_deposit, branch_cash):
        res = post_deposit([branch_cash()], deposited_amount=5000.0)

        assert res.status_code == 400
        assert "deposited_amount" in res.data["error"]["details"]

    def test_duplicate_submission_ids_are_rejected(self, post_deposit, branch_cash):
        submission = branch_cash()

        res = post_deposit([submission], submission_ids=[submission.pk, submission.pk])

        assert res.status_code == 400

    @pytest.mark.parametrize("client_fixture", ["agent_client", "finance_client"])
    def test_only_managers_and_admins_deposit(
        self, request, post_deposit, branch_cash, client_fixture
    ):
        res = post_deposit([branch_cash()], client=request.getfixturevalue(client_fixture))

        assert res.status_code == 403


# Listing and detail -----------------------------------------------------------------------


class TestDepositQueries:
    def test_scoped_by_role(
        self, pending_deposit, other_branch, manager_client, finance_client, agent_client
    ):
        foreign = factories.BankDepositFactory(branch=other_branch)
        gateway = factories.BankDepositFactory(gateway=True)

        def ids(client):
            return {row["id"] for row in client.get(DEPOSITS).data["results"]}

        assert ids(manager_client) == {pending_deposit.pk}
        assert ids(finance_client) == {pending_deposit.pk, foreign.pk, gateway.pk}
        assert agent_client.get(DEPOSITS).status_code == 403

    def test_filters(self, finance_client, branch, other_branch):
        today = business_date()
        delayed = factories.BankDepositFactory(branch=branch, deposit_date=today - timedelta(5))
        fresh = factories.BankDepositFactory(branch=branch)
        settled = factories.BankDepositFactory(
            branch=other_branch, deposit_date=today - timedelta(9), settled=True
        )
        gateway = factories.BankDepositFactory(gateway=True)

        def ids(**params):
            res = finance_client.get(DEPOSITS, params)
            assert res.status_code == 200, res.data
            return {row["id"] for row in res.data["results"]}

        assert ids(delayed="true") == {delayed.pk}
        assert ids(delayed="false") == {fresh.pk, settled.pk, gateway.pk}
        assert ids(status="SETTLED") == {settled.pk}
        assert ids(status=["PENDING", "SETTLED"]) == {delayed.pk, fresh.pk, settled.pk, gateway.pk}
        assert ids(source="GATEWAY") == {gateway.pk}
        assert ids(branch=other_branch.pk) == {settled.pk}
        assert ids(date_from=today - timedelta(6), date_to=today - timedelta(1)) == {delayed.pk}
        assert ids(search=delayed.reference_number.lower()) == {delayed.pk}

    def test_list_flags_delayed_settlements(self, finance_client, branch):
        factories.BankDepositFactory(branch=branch, deposit_date=business_date() - timedelta(4))

        row = finance_client.get(DEPOSITS).data["results"][0]

        assert row["is_delayed"] is True
        assert row["days_pending"] == 4

    def test_list_query_count_does_not_grow(
        self, finance_client, branch, django_assert_max_num_queries
    ):
        factories.BankDepositFactory.create_batch(5, branch=branch)

        with django_assert_max_num_queries(5):
            res = finance_client.get(DEPOSITS)

        assert res.data["count"] == 5

    def test_detail_shows_reconciliation_chain(self, finance_client, pending_deposit):
        res = finance_client.get(detail(pending_deposit))

        assert res.status_code == 200
        assert res.data["collections_count"] == 2
        assert res.data["submissions"][0]["received_amount"] == "5000.00"
        assert res.json()["submissions"][0]["difference"] == "0.00"
        assert res.data["reconciliation"] == {
            "reconciled_amount": "5000.00",
            "deposited_amount": "5000.00",
            "fee_amount": "0.00",
            "tax_amount": "0.00",
            "expected_settlement_amount": "5000.00",
            "settled_amount": None,
            "deposit_difference": "0.00",
            "settlement_difference": None,
            "total_difference": None,
        }

    def test_detail_of_other_branch_is_not_found(
        self, client_for, other_branch_manager, pending_deposit
    ):
        res = client_for(other_branch_manager).get(detail(pending_deposit))

        assert res.status_code == 404
        assert error_code(res) == "NOT_FOUND"


# Settlement -----------------------------------------------------------------------------------


class TestSettleAndFailApi:
    def settle_payload(self, **overrides):
        return {
            "settled_amount": "5000.00",
            "settled_on": business_date().isoformat(),
            "settlement_reference": "STMT-7781",
            **overrides,
        }

    def test_finance_settles_with_mismatch(self, finance_client, pending_deposit):
        res = finance_client.post(
            detail(pending_deposit, "settle"),
            self.settle_payload(settled_amount="4975.00", remarks="Cash handling fee."),
            format="json",
        )

        assert res.status_code == 200, res.data
        assert res.data["status"] == "SETTLED_WITH_MISMATCH"
        assert res.data["reconciliation"]["settlement_difference"] == "25.00"
        assert res.data["reconciliation"]["total_difference"] == "25.00"
        assert res.data["discrepancies"][0]["kind"] == "SETTLEMENT_MISMATCH"
        assert res.data["discrepancies"][0]["reason_code"] == "BANK_ERROR"

    def test_settlement_mismatch_takes_a_reason_code(self, finance_client, pending_deposit):
        res = finance_client.post(
            detail(pending_deposit, "settle"),
            self.settle_payload(
                settled_amount="4882.00", remarks="Cash handling fee.", reason_code="BANK_CHARGES"
            ),
            format="json",
        )

        assert res.status_code == 200, res.data
        assert res.data["discrepancies"][0]["reason_code"] == "BANK_CHARGES"

    def test_mismatch_without_remarks_is_rejected(self, finance_client, pending_deposit):
        res = finance_client.post(
            detail(pending_deposit, "settle"),
            self.settle_payload(settled_amount="4975.00"),
            format="json",
        )

        assert res.status_code == 422

    def test_second_settlement_conflicts(self, finance_client, pending_deposit):
        url = detail(pending_deposit, "settle")
        assert finance_client.post(url, self.settle_payload(), format="json").status_code == 200

        res = finance_client.post(url, self.settle_payload(), format="json")

        assert res.status_code == 409
        assert error_code(res) == "INVALID_STATE_TRANSITION"

    @pytest.mark.parametrize("action", ["settle", "fail"])
    @pytest.mark.parametrize("client_fixture", ["manager_client", "agent_client"])
    def test_only_finance_and_admin_confirm(self, request, pending_deposit, action, client_fixture):
        client = request.getfixturevalue(client_fixture)
        payload = self.settle_payload() if action == "settle" else {"reason": "x"}

        res = client.post(detail(pending_deposit, action), payload, format="json")

        assert res.status_code == 403

    def test_failed_deposit_cash_returns_to_queue_and_redeposits(
        self, finance_client, manager_client, pending_deposit, post_deposit
    ):
        res = finance_client.post(
            detail(pending_deposit, "fail"), {"reason": "Bank rejected the slip."}, format="json"
        )
        assert res.status_code == 200
        assert res.data["status"] == "FAILED"

        queue = manager_client.get(PENDING_CASH).data
        assert queue["total_amount"] == "5000.00"
        submission_ids = [s["id"] for s in queue["submissions"]]
        # The failed slip still shows the hand-overs it returned to the branch.
        assert [s["id"] for s in res.data["submissions"]] == submission_ids
        assert res.data["collections_count"] == 2

        res = post_deposit(
            [], submission_ids=submission_ids, deposited_amount="5000.00", reference_number="S2"
        )
        assert res.status_code == 201, res.data
        assert set(
            Collection.objects.filter(submission_id__in=submission_ids).values_list(
                "status", flat=True
            )
        ) == {"DEPOSITED"}

    def test_failed_deposit_keeps_listing_what_it_carried_after_a_redeposit(
        self, finance_client, manager_client, pending_deposit, post_deposit
    ):
        carried = list(pending_deposit.submissions.values_list("pk", flat=True))
        finance_client.post(
            detail(pending_deposit, "fail"), {"reason": "Bank rejected the slip."}, format="json"
        )
        res = post_deposit(
            [], submission_ids=carried, deposited_amount="5000.00", reference_number="S2"
        )
        assert res.status_code == 201, res.data

        failed = manager_client.get(detail(pending_deposit)).data
        redeposit = manager_client.get(detail(BankDeposit.objects.get(pk=res.data["id"]))).data

        assert [s["id"] for s in failed["submissions"]] == carried
        assert failed["collections_count"] == 2
        assert failed["reconciliation"]["settled_amount"] is None
        assert [s["id"] for s in redeposit["submissions"]] == carried
        assert redeposit["collections_count"] == 2

    def test_fail_requires_reason(self, finance_client, pending_deposit):
        res = finance_client.post(detail(pending_deposit, "fail"), {}, format="json")

        assert res.status_code == 400
        assert "reason" in res.data["error"]["details"]


# Pending cash queue -----------------------------------------------------------------------


class TestPendingCashApi:
    def test_lists_approved_undeposited_cash_of_own_branch(
        self, manager_client, branch_cash, other_branch_loan, post_deposit, agent
    ):
        waiting = branch_cash("3000.00", "2000.00")
        short = branch_cash("1000.00", short=True)
        post_deposit([branch_cash("800.00")])
        branch_cash("700.00", target_loan=other_branch_loan)
        factories.CashSubmissionFactory(agent=agent, rejected=True)

        res = manager_client.get(PENDING_CASH)

        assert res.status_code == 200
        assert res.data["count"] == 2
        assert res.data["total_amount"] == "5500.00"
        assert [s["id"] for s in res.data["submissions"]] == [waiting.pk, short.pk]
        assert res.data["submissions"][0]["branch_code"] == "BLR01"
        assert res.data["has_more"] is False

    def test_lists_at_most_one_batch_and_totals_all(self, manager_client, branch_cash, monkeypatch):
        monkeypatch.setattr("apps.deposits.views.MAX_ITEMS_PER_BATCH", 1)
        oldest = branch_cash("3000.00")
        branch_cash("2000.00")

        res = manager_client.get(PENDING_CASH)

        assert (res.data["count"], res.data["total_amount"]) == (2, "5000.00")
        assert [s["id"] for s in res.data["submissions"]] == [oldest.pk]
        assert res.data["has_more"] is True

    def test_admin_can_narrow_to_a_branch(self, admin_client, branch_cash, other_branch_loan):
        branch_cash("3000.00")
        remote = branch_cash("700.00", target_loan=other_branch_loan)

        res = admin_client.get(PENDING_CASH, {"branch": other_branch_loan.branch_id})

        assert [s["id"] for s in res.data["submissions"]] == [remote.pk]
        assert admin_client.get(PENDING_CASH).data["count"] == 2

    @pytest.mark.parametrize("client_fixture", ["finance_client", "agent_client"])
    def test_hidden_from_other_roles(self, request, client_fixture):
        assert request.getfixturevalue(client_fixture).get(PENDING_CASH).status_code == 403


# Gateway settlements --------------------------------------------------------------------------


@pytest.mark.usefixtures("gateway_bank_account")
class TestGatewaySettlementApi:
    def payload(self, payments, **overrides):
        return {
            "collection_ids": [p.pk for p in payments],
            "gross_amount": "1500.00",
            "fee_amount": "30.00",
            "tax_amount": "5.40",
            "net_amount": "1464.60",
            "utr": "axisn 2026 1017 0001",
            "settled_on": business_date().isoformat(),
            **overrides,
        }

    def test_finance_records_settlement(self, finance_client, idempotency_headers, upi_payments):
        payments = upi_payments("1000.00", "500.00")

        res = finance_client.post(
            GATEWAY_SETTLEMENTS, self.payload(payments), format="json", **idempotency_headers()
        )

        assert res.status_code == 201, res.data
        assert res.data["source"] == "GATEWAY"
        assert res.data["status"] == "SETTLED"
        assert res.data["reference_number"] == "AXISN202610170001"
        assert res.data["collections_count"] == 2
        assert res.data["reconciliation"]["expected_settlement_amount"] == "1464.60"
        assert res.data["reconciliation"]["total_difference"] == "0.00"

        listing = finance_client.get(GATEWAY_SETTLEMENTS).data
        assert [row["id"] for row in listing["results"]] == [res.data["id"]]

    def test_pending_lists_at_most_one_batch(self, finance_client, upi_payments, monkeypatch):
        monkeypatch.setattr("apps.deposits.views.MAX_ITEMS_PER_BATCH", 2)
        upi_payments("100.00", "200.00", "300.00")

        res = finance_client.get(UNSETTLED_UPI)

        assert (res.data["count"], res.data["total_amount"]) == (3, "600.00")
        assert len(res.data["collections"]) == 2
        assert res.data["has_more"] is True

    def test_list_query_count_does_not_grow_with_rows(
        self, finance_client, upi_payments, django_assert_max_num_queries
    ):
        for _ in range(6):
            factories.BankDepositFactory(gateway=True, settled=True)

        # Request savepoint pair, auth user, page count and rows.
        with django_assert_max_num_queries(6):
            assert finance_client.get(GATEWAY_SETTLEMENTS).data["count"] == 6

    def test_mismatch_is_reported(self, finance_client, idempotency_headers, upi_payments):
        res = finance_client.post(
            GATEWAY_SETTLEMENTS,
            self.payload(
                upi_payments("1000.00", "500.00"),
                gross_amount="1400.00",
                net_amount="1364.60",
                remarks="One payment refunded by the gateway.",
            ),
            format="json",
            **idempotency_headers(),
        )

        assert res.status_code == 201
        assert res.data["status"] == "SETTLED_WITH_MISMATCH"
        assert res.data["discrepancies"][0]["kind"] == "GATEWAY_MISMATCH"
        assert res.data["reconciliation"]["total_difference"] == "100.00"

    def test_requires_exactly_one_selection_mode(
        self, finance_client, idempotency_headers, upi_payments
    ):
        payload = self.payload(upi_payments("1500.00"), up_to_date=business_date().isoformat())

        res = finance_client.post(
            GATEWAY_SETTLEMENTS, payload, format="json", **idempotency_headers()
        )

        assert res.status_code == 400

    def test_settle_everything_up_to_a_date(
        self, finance_client, idempotency_headers, upi_payments
    ):
        upi_payments("1000.00", "500.00")
        payload = self.payload([], up_to_date=business_date().isoformat())
        del payload["collection_ids"]

        res = finance_client.post(
            GATEWAY_SETTLEMENTS, payload, format="json", **idempotency_headers()
        )

        assert res.status_code == 201, res.data
        assert res.data["expected_amount"] == "1500.00"

    @pytest.mark.parametrize("client_fixture", ["manager_client", "agent_client"])
    def test_finance_and_admin_only(self, request, client_fixture, idempotency_headers):
        client = request.getfixturevalue(client_fixture)

        assert client.get(GATEWAY_SETTLEMENTS).status_code == 403
        assert client.get(UNSETTLED_UPI).status_code == 403
        res = client.post(GATEWAY_SETTLEMENTS, {}, format="json", **idempotency_headers())
        assert res.status_code == 403

    def test_unsettled_upi_queue(self, admin_client, upi_payments, loan):
        older = upi_payments("1000.00", collected_at=timezone.now() - timedelta(days=2))
        upi_payments("250.00")
        factories.CollectionFactory(loan=loan)

        everything = admin_client.get(UNSETTLED_UPI).data
        assert (everything["count"], everything["total_amount"]) == (2, "1250.00")

        until_yesterday = admin_client.get(
            UNSETTLED_UPI, {"up_to_date": (business_date() - timedelta(1)).isoformat()}
        ).data
        assert [c["id"] for c in until_yesterday["collections"]] == [older[0].pk]
        assert until_yesterday["collections"][0]["loan_number"] == loan.loan_number
