import csv
import io
from decimal import Decimal

import pytest
from django.urls import reverse
from django.utils import timezone

from apps.core.testing import factories
from apps.dashboard.reports import COLLECTIONS
from apps.reconciliation.models import CashSubmission

pytestmark = pytest.mark.django_db

COLLECTIONS_CSV = reverse("report-collections")
SUBMISSIONS_CSV = reverse("report-submissions")
DEPOSITS_CSV = reverse("report-deposits")
DISCREPANCIES_CSV = reverse("report-discrepancies")


def read_csv(response) -> list[dict[str, str]]:
    body = b"".join(response.streaming_content).decode()
    return list(csv.DictReader(io.StringIO(body)))


def keyed(response, column: str) -> dict[str, dict[str, str]]:
    return {row[column]: row for row in read_csv(response)}


class TestCollectionsReport:
    def test_streams_an_attachment(self, scenario, admin_client, period):
        response = admin_client.get(COLLECTIONS_CSV, period)

        assert response.status_code == 200
        assert response.streaming
        assert response["Content-Type"] == "text/csv; charset=utf-8"
        assert response["Content-Disposition"] == (
            f'attachment; filename="collections_{period["date_from"]}_{period["date_to"]}.csv"'
        )
        rows = read_csv(response)
        assert len(rows) == 10
        assert list(rows[0]) == [column.header for column in COLLECTIONS.columns]

    def test_rows_carry_the_reconciliation_chain(self, scenario, admin_client, period):
        rows = keyed(admin_client.get(COLLECTIONS_CSV, period), "Receipt number")

        settled = rows[scenario.receipts["c5"].receipt_number]
        assert settled["Amount"] == "4000.00"
        assert settled["Status"] == "SETTLED"
        assert settled["Branch"] == "BLR01"
        assert settled["Submission number"] == scenario.submissions["ok"].submission_number
        assert settled["Deposit number"] == scenario.deposits["settled"].deposit_number
        assert settled["Collected at"].endswith("+05:30")
        assert rows[scenario.receipts["c1"].receipt_number]["Deposit number"] == ""

    def test_scope_and_filters_apply(self, scenario, manager_client, agent_client, period):
        manager_rows = read_csv(manager_client.get(COLLECTIONS_CSV, period))
        agent_rows = read_csv(agent_client.get(COLLECTIONS_CSV, {**period, "status": "VOIDED"}))

        assert {row["Branch"] for row in manager_rows} == {"BLR01"}
        assert len(manager_rows) == 8
        assert [row["Receipt number"] for row in agent_rows] == [
            scenario.receipts["c6"].receipt_number
        ]

    def test_query_count_is_constant(
        self, scenario, admin_client, period, django_assert_max_num_queries
    ):
        # Request savepoint pair, auth user, and the single joined export query.
        with django_assert_max_num_queries(4):
            rows = read_csv(admin_client.get(COLLECTIONS_CSV, period))
        assert len(rows) == 10


def test_submissions_report(scenario, manager_client, period):
    rows = keyed(manager_client.get(SUBMISSIONS_CSV, period), "Submission number")

    short = rows[scenario.submissions["short"].submission_number]
    assert (short["Expected amount"], short["Received amount"], short["Difference"]) == (
        "3000.00",
        "2500.00",
        "500.00",
    )
    assert short["Status"] == "APPROVED_WITH_DISCREPANCY"
    assert rows[scenario.submissions["pending"].submission_number]["Received amount"] == ""


def test_deposits_report_with_status_filter(scenario, finance_client, period):
    rows = read_csv(finance_client.get(DEPOSITS_CSV, {**period, "status": "PENDING"}))

    assert len(rows) == 1
    assert rows[0]["Deposit number"] == scenario.deposits["pending"].deposit_number
    assert rows[0]["Delayed"] == "yes"
    assert rows[0]["Days pending"] == "5"


def test_gateway_deposit_has_no_branch(scenario, admin_client, period):
    rows = read_csv(admin_client.get(DEPOSITS_CSV, {**period, "status": "SETTLED_WITH_MISMATCH"}))

    assert rows[0]["Source"] == "GATEWAY"
    assert rows[0]["Branch"] == ""
    assert (rows[0]["Fee"], rows[0]["Tax"], rows[0]["Settled amount"]) == (
        "20.00",
        "3.60",
        "1170.00",
    )


def test_discrepancies_report_is_scoped(scenario, manager_client, admin_client, period):
    manager_rows = read_csv(manager_client.get(DISCREPANCIES_CSV, period))
    admin_rows = read_csv(admin_client.get(DISCREPANCIES_CSV, {**period, "status": "OPEN"}))

    assert {row["Kind"] for row in manager_rows} == {"CASH_SHORTAGE", "DEPOSIT_MISMATCH"}
    assert {row["Kind"] for row in admin_rows} == {"CASH_SHORTAGE", "GATEWAY_MISMATCH"}


class TestErrorsAndPermissions:
    @pytest.mark.parametrize(
        "url", [COLLECTIONS_CSV, SUBMISSIONS_CSV, DEPOSITS_CSV, DISCREPANCIES_CSV]
    )
    def test_requires_a_bearer_token(self, api_client, url):
        response = api_client.get(url, HTTP_ACCEPT="text/csv")

        assert response.status_code == 401
        assert response["Content-Type"] == "application/json"
        assert response.json()["error"]["code"] == "NOT_AUTHENTICATED"

    def test_invalid_filter_is_a_json_error_even_when_csv_is_accepted(self, admin_client):
        response = admin_client.get(SUBMISSIONS_CSV, {"status": "SETTLED"}, HTTP_ACCEPT="text/csv")

        assert response.status_code == 400
        assert response.json()["error"]["details"]["status"]

    def test_agent_cannot_export_deposits(self, agent_client):
        response = agent_client.get(DEPOSITS_CSV)

        assert response.status_code == 403
        assert response.json()["error"]["code"] == "PERMISSION_DENIED"

    @pytest.mark.parametrize("url", [COLLECTIONS_CSV, SUBMISSIONS_CSV, DISCREPANCIES_CSV])
    def test_agent_can_export_their_own_records(self, agent_client, url):
        assert agent_client.get(url).status_code == 200

    def test_manager_cannot_export_another_branch(self, manager_client, other_branch):
        response = manager_client.get(COLLECTIONS_CSV, {"branch": other_branch.pk})

        assert response.status_code == 400


def test_spreadsheet_formulas_are_neutralised(loan, admin_client):
    loan.customer.full_name = '=HYPERLINK("http://evil.test","Pay")'
    loan.customer.save(update_fields=["full_name"])
    factories.CollectionFactory(loan=loan, amount=Decimal("100.00"), remarks="-5 from agent")

    row = read_csv(admin_client.get(COLLECTIONS_CSV))[0]

    assert row["Customer name"] == '\'=HYPERLINK("http://evil.test","Pay")'
    assert row["Remarks"] == "'-5 from agent"
    assert row["Amount"] == "100.00"


def test_negative_differences_stay_numeric(admin_client, agent, manager):
    factories.CashSubmissionFactory(
        agent=agent,
        expected_amount=Decimal("5000.00"),
        status=CashSubmission.Status.APPROVED_WITH_DISCREPANCY,
        received_amount=Decimal("5500.00"),
        reviewed_at=timezone.now(),
        reviewed_by=manager,
    )

    row = read_csv(admin_client.get(SUBMISSIONS_CSV))[0]

    assert row["Difference"] == "-500.00"
