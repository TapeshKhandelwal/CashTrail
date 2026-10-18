from datetime import timedelta
from decimal import Decimal

import pytest
from django.utils import timezone

from apps.collections.models import Collection
from apps.core.dates import business_date
from apps.core.testing import factories
from apps.loans.models import Loan

from .utils import months_ago, pay

pytestmark = pytest.mark.django_db

LOANS_URL = "/api/loans/"
PREVIEW_URL = "/api/loans/schedule-preview/"


def detail_url(loan: Loan, suffix: str = "") -> str:
    return f"{LOANS_URL}{loan.pk}/{suffix}"


def loan_numbers(response) -> set[str]:
    return {row["loan_number"] for row in response.json()["results"]}


@pytest.fixture
def create_payload(customer):
    return {
        "customer_id": customer.pk,
        "principal": "100000.00",
        "annual_interest_rate": "12.00",
        "tenure_months": 12,
    }


class TestListAndScoping:
    @pytest.fixture(autouse=True)
    def _loans(self, loan, unassigned_loan, other_branch_loan):
        self.loan, self.unassigned_loan, self.other_branch_loan = (
            loan,
            unassigned_loan,
            other_branch_loan,
        )

    @pytest.mark.parametrize("client_fixture", ["admin_client", "finance_client"])
    def test_global_roles_see_every_loan(self, request, client_fixture):
        response = request.getfixturevalue(client_fixture).get(LOANS_URL)

        assert response.status_code == 200
        assert response.json()["count"] == 3

    def test_manager_sees_own_branch(self, manager_client):
        response = manager_client.get(LOANS_URL)

        assert loan_numbers(response) == {
            self.loan.loan_number,
            self.unassigned_loan.loan_number,
        }

    def test_agent_sees_assigned_customers_only(self, agent_client):
        response = agent_client.get(LOANS_URL)

        assert loan_numbers(response) == {self.loan.loan_number}

    def test_anonymous_is_rejected(self, api_client):
        response = api_client.get(LOANS_URL)

        assert response.status_code == 401
        assert response.json()["error"]["code"] == "NOT_AUTHENTICATED"

    @pytest.mark.parametrize(
        ("client_fixture", "loan_attr"),
        [
            ("manager_client", "other_branch_loan"),
            ("agent_client", "unassigned_loan"),
            ("agent_client", "other_branch_loan"),
        ],
    )
    def test_out_of_scope_loans_are_not_found(self, request, client_fixture, loan_attr):
        client = request.getfixturevalue(client_fixture)
        loan = getattr(self, loan_attr)

        for suffix in ("", "schedule/", "repayments/"):
            response = client.get(detail_url(loan, suffix))
            assert response.status_code == 404, suffix
            assert response.json()["error"]["code"] == "NOT_FOUND"

    def test_filters(self, admin_client, other_agent):
        def numbers(**params):
            return loan_numbers(admin_client.get(LOANS_URL, params))

        assert numbers(branch=self.other_branch_loan.branch_id) == {
            self.other_branch_loan.loan_number
        }
        assert numbers(customer=self.loan.customer_id) == {self.loan.loan_number}
        assert numbers(agent=other_agent.pk) == {self.unassigned_loan.loan_number}
        assert numbers(status="CLOSED") == set()

    def test_status_filter_rejects_unknown_values(self, admin_client):
        response = admin_client.get(LOANS_URL, {"status": "WRITTEN_OFF"})

        assert response.status_code == 400
        assert response.json()["error"]["code"] == "VALIDATION_ERROR"

    def test_search_by_customer_name_and_loan_number(self, admin_client):
        by_name = admin_client.get(LOANS_URL, {"search": self.loan.customer.full_name})
        by_number = admin_client.get(LOANS_URL, {"search": self.other_branch_loan.loan_number})

        assert self.loan.loan_number in loan_numbers(by_name)
        assert loan_numbers(by_number) == {self.other_branch_loan.loan_number}

    def test_overdue_filter(self, admin_client, customer):
        overdue = factories.LoanFactory(customer=customer, disbursed_on=months_ago(3))

        assert loan_numbers(admin_client.get(LOANS_URL, {"overdue": "true"})) == {
            overdue.loan_number
        }
        assert overdue.loan_number not in loan_numbers(
            admin_client.get(LOANS_URL, {"overdue": "false"})
        )

    def test_list_query_count_does_not_grow_with_loans(
        self, admin_client, customer, django_assert_max_num_queries
    ):
        factories.LoanFactory.create_batch(5, customer=customer)

        with django_assert_max_num_queries(5):
            response = admin_client.get(LOANS_URL)

        assert response.json()["count"] == 8


class TestRetrieve:
    def test_detail_shows_balances_and_next_due(self, agent_client, overdue_loan):
        first, second = overdue_loan.installments.order_by("installment_no")[:2]
        pay(first, first.amount_due)
        pay(second, "1000.00")

        response = agent_client.get(detail_url(overdue_loan))

        assert response.status_code == 200
        body = response.json()
        assert body["loan_number"] == overdue_loan.loan_number
        assert body["customer_name"] == overdue_loan.customer.full_name
        assert body["branch_code"] == "BLR01"
        assert body["agent"] == overdue_loan.customer.assigned_agent_id
        assert body["emi_amount"] == "8885.00"
        assert body["amount_paid"] == str(first.amount_due + Decimal("1000.00"))
        assert body["outstanding"] == str(
            overdue_loan.total_payable - first.amount_due - Decimal("1000.00")
        )
        assert body["overdue_amount"] == str(second.amount_due - Decimal("1000.00"))
        assert body["paid_installments"] == 1
        assert body["next_due"] == {
            "installment_no": 2,
            "due_date": second.due_date.isoformat(),
            "amount": str(second.amount_due - Decimal("1000.00")),
        }
        assert body["terms_locked"] is False

    def test_money_is_serialized_as_strings(self, admin_client, loan):
        body = admin_client.get(detail_url(loan)).json()

        for field in ("principal", "emi_amount", "total_payable", "outstanding", "overdue_amount"):
            assert isinstance(body[field], str), field


class TestCreate:
    @pytest.mark.parametrize("client_fixture", ["admin_client", "manager_client"])
    def test_admin_and_manager_create_loans(self, request, client_fixture, create_payload):
        response = request.getfixturevalue(client_fixture).post(
            LOANS_URL, create_payload, format="json"
        )

        assert response.status_code == 201
        body = response.json()
        assert body["loan_number"] == "LN-BLR01-000001"
        assert body["emi_amount"] == "8885.00"
        assert body["outstanding"] == body["total_payable"]
        assert body["disbursed_on"] == business_date().isoformat()
        assert body["next_due"]["installment_no"] == 1
        assert Loan.objects.get(pk=body["id"]).installments.count() == 12

    @pytest.mark.parametrize("client_fixture", ["agent_client", "finance_client"])
    def test_other_roles_cannot_create(self, request, client_fixture, create_payload):
        response = request.getfixturevalue(client_fixture).post(
            LOANS_URL, create_payload, format="json"
        )

        assert response.status_code == 403
        assert response.json()["error"]["code"] == "PERMISSION_DENIED"
        assert not Loan.objects.exists()

    def test_manager_gets_not_found_for_other_branch_customer(
        self, manager_client, create_payload, other_branch_customer
    ):
        response = manager_client.post(
            LOANS_URL, {**create_payload, "customer_id": other_branch_customer.pk}, format="json"
        )

        assert response.status_code == 404
        assert response.json()["error"]["code"] == "NOT_FOUND"

    def test_inactive_customer_is_unprocessable(self, admin_client, create_payload, customer):
        customer.is_active = False
        customer.save()

        response = admin_client.post(LOANS_URL, create_payload, format="json")

        assert response.status_code == 422
        assert response.json()["error"]["code"] == "VALIDATION_FAILED"

    def test_float_amounts_are_rejected(self, admin_client, create_payload):
        response = admin_client.post(
            LOANS_URL,
            {**create_payload, "principal": 100000.5, "annual_interest_rate": 12.5},
            format="json",
        )

        assert response.status_code == 400
        details = response.json()["error"]["details"]
        assert set(details) == {"principal", "annual_interest_rate"}

    @pytest.mark.parametrize(
        ("field", "value"),
        [
            ("principal", "0.00"),
            ("principal", "-100.00"),
            ("annual_interest_rate", "-1"),
            ("annual_interest_rate", "100.01"),
            ("tenure_months", 0),
            ("tenure_months", 361),
            ("customer_id", None),
        ],
    )
    def test_field_validation(self, admin_client, create_payload, field, value):
        response = admin_client.post(LOANS_URL, {**create_payload, field: value}, format="json")

        assert response.status_code == 400
        assert field in response.json()["error"]["details"]

    def test_business_rule_violation_is_unprocessable(self, admin_client, create_payload):
        response = admin_client.post(
            LOANS_URL,
            {**create_payload, "disbursed_on": (business_date() + timedelta(days=1)).isoformat()},
            format="json",
        )

        assert response.status_code == 422
        assert response.json()["error"]["code"] == "VALIDATION_FAILED"


class TestPartialUpdate:
    def test_manager_corrects_terms_before_any_repayment(self, manager_client, loan):
        response = manager_client.patch(
            detail_url(loan),
            {"principal": "50000.00", "annual_interest_rate": "10.00"},
            format="json",
        )

        assert response.status_code == 200
        body = response.json()
        assert body["principal"] == "50000.00"
        assert body["emi_amount"] == "4396.00"
        schedule = manager_client.get(detail_url(loan, "schedule/")).json()
        assert schedule[0]["amount_due"] == "4396.00"

    def test_terms_are_locked_once_collected(self, manager_client, loan):
        factories.CollectionFactory(loan=loan)

        response = manager_client.patch(detail_url(loan), {"principal": "1.00"}, format="json")

        assert response.status_code == 409
        error = response.json()["error"]
        assert error["code"] == "RECORD_LOCKED"
        assert error["details"]["fields"] == ["principal"]

    def test_tenure_change_is_refused(self, manager_client, loan):
        response = manager_client.patch(detail_url(loan), {"tenure_months": 24}, format="json")

        assert response.status_code == 422

    @pytest.mark.parametrize("client_fixture", ["agent_client", "finance_client"])
    def test_read_only_roles_cannot_edit(self, request, client_fixture, loan):
        response = request.getfixturevalue(client_fixture).patch(
            detail_url(loan), {"principal": "1.00"}, format="json"
        )

        assert response.status_code == 403

    def test_other_branch_manager_gets_not_found(self, other_branch_manager, client_for, loan):
        response = client_for(other_branch_manager).patch(
            detail_url(loan), {"principal": "1.00"}, format="json"
        )

        assert response.status_code == 404

    def test_server_owned_fields_are_ignored(self, admin_client, loan):
        response = admin_client.patch(
            detail_url(loan),
            {"amount_paid": "50000.00", "status": "CLOSED", "loan_number": "X"},
            format="json",
        )

        assert response.status_code == 200
        loan.refresh_from_db()
        assert loan.amount_paid == Decimal("0.00")
        assert loan.status == Loan.Status.ACTIVE

    @pytest.mark.parametrize("method", ["put", "delete"])
    def test_replace_and_delete_are_not_allowed(self, admin_client, loan, method):
        response = getattr(admin_client, method)(detail_url(loan))

        assert response.status_code == 405
        assert Loan.objects.filter(pk=loan.pk).exists()


class TestSchedule:
    def test_lists_installments_in_order_with_status(self, agent_client, overdue_loan):
        first = overdue_loan.installments.get(installment_no=1)
        pay(first, "500.00")

        response = agent_client.get(detail_url(overdue_loan, "schedule/"))

        assert response.status_code == 200
        rows = response.json()
        assert [row["installment_no"] for row in rows] == list(range(1, 13))
        assert rows[0]["status"] == "PARTIALLY_PAID"
        assert rows[0]["amount_paid"] == "500.00"
        assert rows[0]["outstanding"] == str(first.amount_due - Decimal("500.00"))
        assert rows[0]["is_overdue"] is True
        assert rows[2]["is_overdue"] is False


class TestRepayments:
    def test_history_includes_allocations_and_lifecycle(self, finance_client, loan):
        installment = loan.installments.get(installment_no=1)
        now = timezone.now()
        voided = factories.CollectionFactory(
            loan=loan,
            amount=Decimal("500.00"),
            collected_at=now - timedelta(hours=1),
            status=Collection.Status.VOIDED,
            voided_at=now,
            void_reason="Entered twice.",
        )
        factories.AllocationFactory(collection=voided, reversed_at=now)
        submission = factories.CashSubmissionFactory(agent=loan.customer.assigned_agent)
        kept = factories.CollectionFactory(
            loan=loan,
            amount=Decimal("1000.00"),
            collected_at=now,
            status=Collection.Status.SUBMITTED,
            submitted_at=now,
            submission=submission,
        )
        factories.AllocationFactory(collection=kept)

        response = finance_client.get(detail_url(loan, "repayments/"))

        assert response.status_code == 200
        results = response.json()["results"]
        assert [row["receipt_number"] for row in results] == [
            kept.receipt_number,
            voided.receipt_number,
        ]
        latest, struck = results
        assert latest["status"] == "SUBMITTED"
        assert latest["submission_number"] == submission.submission_number
        assert latest["deposit_number"] is None
        assert latest["allocations"] == [
            {
                "installment": installment.pk,
                "installment_no": 1,
                "due_date": installment.due_date.isoformat(),
                "amount": "1000.00",
                "reversed_at": None,
            }
        ]
        assert struck["status"] == "VOIDED"
        assert struck["void_reason"] == "Entered twice."
        assert struck["allocations"][0]["reversed_at"] is not None

    def test_query_count_is_constant(self, admin_client, loan, django_assert_max_num_queries):
        for _ in range(3):
            factories.AllocationFactory(collection=factories.CollectionFactory(loan=loan))

        with django_assert_max_num_queries(7):
            response = admin_client.get(detail_url(loan, "repayments/"))

        assert response.json()["count"] == 3


class TestSchedulePreview:
    @pytest.mark.parametrize("client_fixture", ["admin_client", "manager_client"])
    def test_preview_returns_schedule_without_saving(self, request, client_fixture):
        response = request.getfixturevalue(client_fixture).get(
            PREVIEW_URL,
            {"principal": "100000", "annual_interest_rate": "12", "tenure_months": 12},
        )

        assert response.status_code == 200
        body = response.json()
        assert body["emi_amount"] == "8885.00"
        assert body["principal"] == "100000.00"
        assert len(body["installments"]) == 12
        assert body["installments"][0]["opening_balance"] == "100000.00"
        assert body["installments"][-1]["closing_balance"] == "0.00"
        assert Decimal(body["total_interest"]) == Decimal(body["total_payable"]) - Decimal(
            "100000.00"
        )
        assert not Loan.objects.exists()

    @pytest.mark.parametrize("client_fixture", ["agent_client", "finance_client"])
    def test_only_lenders_can_preview(self, request, client_fixture):
        response = request.getfixturevalue(client_fixture).get(
            PREVIEW_URL, {"principal": "1000", "annual_interest_rate": "12", "tenure_months": 3}
        )

        assert response.status_code == 403

    def test_missing_parameters(self, admin_client):
        response = admin_client.get(PREVIEW_URL, {"principal": "1000"})

        assert response.status_code == 400
        assert set(response.json()["error"]["details"]) == {
            "annual_interest_rate",
            "tenure_months",
        }

    def test_principal_too_small_for_tenure(self, admin_client):
        response = admin_client.get(
            PREVIEW_URL, {"principal": "0.05", "annual_interest_rate": "0", "tenure_months": 12}
        )

        assert response.status_code == 422
        assert response.json()["error"]["code"] == "VALIDATION_FAILED"
