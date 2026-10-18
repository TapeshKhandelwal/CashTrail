import re
from datetime import timedelta
from decimal import Decimal

import pytest

from apps.audit.models import AuditAction, AuditLog
from apps.core.testing import factories
from apps.customers.models import Customer
from apps.customers.services import update_customer

from .helpers import installments, pay

pytestmark = pytest.mark.django_db

URL = "/api/customers/"
ROUTE_URL = "/api/agent/customers/"


def detail_url(customer, action: str = "") -> str:
    return f"{URL}{customer.pk}/{action + '/' if action else ''}"


@pytest.fixture
def new_customer():
    return {
        "full_name": "Lakshmi Rao",
        "phone": "+91 98450-11111",
        "email": "lakshmi@example.com",
        "address": "12 MG Road",
    }


class TestCreate:
    def test_manager_creates_in_own_branch_with_generated_number(
        self, clients, manager, agent, new_customer
    ):
        res = clients["manager"].post(URL, new_customer | {"assigned_agent": agent.pk})

        assert res.status_code == 201
        assert re.fullmatch(r"CUS-\d{6}", res.data["customer_code"])
        assert res.data["branch"] == manager.branch_id
        assert res.data["assigned_agent"] == agent.pk
        assert res.data["phone"] == "+919845011111"
        assert (res.data["outstanding"], res.data["loans"]) == ("0.00", [])
        log = AuditLog.objects.get(action=AuditAction.CUSTOMER_CREATED)
        assert (log.actor, log.entity_id) == (manager, str(res.data["id"]))

    def test_customer_numbers_are_sequential(self, clients, new_customer):
        first = clients["manager"].post(URL, new_customer).data["customer_code"]
        second = clients["manager"].post(URL, new_customer).data["customer_code"]

        assert int(second[4:]) == int(first[4:]) + 1

    def test_admin_must_choose_a_branch(self, clients, new_customer):
        res = clients["admin"].post(URL, new_customer)

        assert res.status_code == 422
        assert res.data["error"]["code"] == "VALIDATION_FAILED"
        assert "branch" in res.data["error"]["details"]

    def test_admin_creates_in_any_branch(self, clients, other_branch, new_customer):
        res = clients["admin"].post(URL, new_customer | {"branch": other_branch.pk})

        assert res.data["branch_code"] == "MUM01"

    def test_manager_cannot_pick_another_branch(self, clients, other_branch, new_customer):
        res = clients["manager"].post(URL, new_customer | {"branch": other_branch.pk})

        assert res.status_code == 400
        assert "branch" in res.data["error"]["details"]

    def test_manager_cannot_pick_agent_of_another_branch(
        self, clients, other_branch_agent, new_customer
    ):
        res = clients["manager"].post(URL, new_customer | {"assigned_agent": other_branch_agent.pk})

        assert res.status_code == 400
        assert "assigned_agent" in res.data["error"]["details"]

    def test_admin_cannot_pair_branch_with_foreign_agent(
        self, clients, branch, other_branch_agent, new_customer
    ):
        payload = new_customer | {"branch": branch.pk, "assigned_agent": other_branch_agent.pk}

        res = clients["admin"].post(URL, payload)

        assert res.status_code == 422
        assert not Customer.objects.exists()

    def test_inactive_branch_is_rejected(self, clients, new_customer):
        closed = factories.BranchFactory(code="OLD01", is_active=False)

        res = clients["admin"].post(URL, new_customer | {"branch": closed.pk})

        assert res.status_code == 422

    @pytest.mark.parametrize(
        ("override", "field"),
        [({"phone": "12ab"}, "phone"), ({"full_name": ""}, "full_name"), ({"email": "x"}, "email")],
    )
    def test_validates_input(self, clients, new_customer, override, field):
        res = clients["manager"].post(URL, new_customer | override)

        assert res.status_code == 400
        assert res.data["error"]["code"] == "VALIDATION_ERROR"
        assert field in res.data["error"]["details"]


class TestUpdate:
    def test_updates_contact_details_and_audits(self, clients, customer):
        res = clients["manager"].patch(detail_url(customer), {"phone": "98450 22222"})

        assert res.status_code == 200
        assert res.data["phone"] == "9845022222"
        log = AuditLog.objects.get(action=AuditAction.CUSTOMER_UPDATED)
        assert log.after == {"phone": "9845022222"}

    def test_code_branch_and_agent_are_not_editable(self, clients, customer, other_branch):
        res = clients["admin"].patch(
            detail_url(customer),
            {"customer_code": "CUS-999999", "branch": other_branch.pk, "assigned_agent": None},
            format="json",
        )

        assert res.status_code == 200
        assert res.data["customer_code"] == customer.customer_code
        assert res.data["branch"] == customer.branch_id
        assert res.data["assigned_agent"] == customer.assigned_agent_id

    def test_deactivation_is_a_soft_delete(self, clients, customer):
        res = clients["manager"].patch(detail_url(customer), {"is_active": False}, format="json")

        assert res.status_code == 200
        assert Customer.objects.get(pk=customer.pk).is_active is False
        assert clients["manager"].get(detail_url(customer)).status_code == 200

    def test_customer_with_active_loan_cannot_be_deactivated(self, clients, loan):
        res = clients["admin"].patch(detail_url(loan.customer), {"is_active": False}, format="json")

        assert res.status_code == 422
        assert res.data["error"]["details"] == {"active_loans": 1}

    def test_customer_of_inactive_branch_cannot_be_reactivated(self, clients, customer):
        Customer.objects.filter(pk=customer.pk).update(is_active=False)
        customer.branch.is_active = False
        customer.branch.save()

        res = clients["admin"].patch(detail_url(customer), {"is_active": True}, format="json")

        assert res.status_code == 422
        assert Customer.objects.get(pk=customer.pk).is_active is False


class TestAssign:
    def test_reassigns_and_audits(self, clients, customer, agent, other_agent):
        res = clients["manager"].post(detail_url(customer, "assign"), {"agent_id": other_agent.pk})

        assert res.status_code == 200
        assert res.data["assigned_agent"] == other_agent.pk
        assert res.data["assigned_agent_name"] == other_agent.get_full_name()
        log = AuditLog.objects.get(action=AuditAction.CUSTOMER_ASSIGNED)
        assert (log.before, log.after) == (
            {"assigned_agent": agent.pk},
            {"assigned_agent": other_agent.pk},
        )

    def test_unassign(self, clients, customer):
        res = clients["admin"].post(
            detail_url(customer, "assign"), {"agent_id": None}, format="json"
        )

        assert res.status_code == 200
        assert res.data["assigned_agent"] is None

    def test_agent_id_is_required(self, clients, customer):
        res = clients["admin"].post(detail_url(customer, "assign"), {}, format="json")

        assert res.status_code == 400
        assert "agent_id" in res.data["error"]["details"]

    def test_inactive_agent_is_rejected(self, clients, customer, other_agent):
        other_agent.is_active = False
        other_agent.save()

        res = clients["manager"].post(detail_url(customer, "assign"), {"agent_id": other_agent.pk})

        assert res.status_code == 422
        assert res.data["error"]["details"] == {"agent": other_agent.pk}

    def test_admin_cannot_assign_agent_of_another_branch(
        self, clients, customer, other_branch_agent
    ):
        res = clients["admin"].post(
            detail_url(customer, "assign"), {"agent_id": other_branch_agent.pk}
        )

        assert res.status_code == 422
        assert Customer.objects.get(pk=customer.pk).assigned_agent_id == customer.assigned_agent_id

    @pytest.mark.parametrize("target", ["other_branch_agent", "manager"])
    def test_manager_sees_only_own_agents(self, clients, customer, request, target):
        res = clients["manager"].post(
            detail_url(customer, "assign"), {"agent_id": request.getfixturevalue(target).pk}
        )

        assert res.status_code == 400
        assert "agent_id" in res.data["error"]["details"]

    def test_inactive_customer_cannot_be_assigned(self, clients, customer, other_agent):
        customer.is_active = False
        customer.save()

        res = clients["admin"].post(detail_url(customer, "assign"), {"agent_id": other_agent.pk})

        assert res.status_code == 422


class TestList:
    def test_search_by_name_phone_and_code(self, clients, branch):
        lakshmi = factories.CustomerFactory(
            branch=branch, full_name="Lakshmi Rao", phone="9845011111"
        )
        factories.CustomerFactory(branch=branch, full_name="Arjun Das", phone="9845022222")

        for term in ("lakshmi", "11111", lakshmi.customer_code.lower()):
            res = clients["admin"].get(URL, {"search": term})
            assert [row["id"] for row in res.data["results"]] == [lakshmi.pk], term

    def test_filters(self, clients, customers, agent):
        inactive = factories.CustomerFactory(
            branch=agent.branch, assigned_agent=agent, is_active=False
        )
        unassigned = factories.CustomerFactory(branch=agent.branch, assigned_agent=None)

        def ids(**params):
            return {row["id"] for row in clients["admin"].get(URL, params).data["results"]}

        assert ids(branch=customers["foreign"].branch_id) == {customers["foreign"].pk}
        assert ids(agent=agent.pk) == {customers["own"].pk, inactive.pk}
        assert ids(agent=agent.pk, is_active="true") == {customers["own"].pk}
        assert ids(unassigned="true") == {unassigned.pk}

    def test_manager_filtering_other_branch_gets_nothing(self, clients, customers):
        res = clients["manager"].get(URL, {"branch": customers["foreign"].branch_id})

        assert res.data["count"] == 0

    def test_orders_by_overdue_amount(self, clients, customers, make_loan, today, overdue_date):
        make_loan(customers["colleague"], first_due_date=overdue_date)
        make_loan(customers["own"], first_due_date=today)

        res = clients["manager"].get(URL, {"ordering": "-overdue_amount"})

        assert [row["id"] for row in res.data["results"]] == [
            customers["colleague"].pk,
            customers["own"].pk,
        ]

    def test_finance_sees_masked_phone(self, clients, customer):
        masked = clients["finance"].get(detail_url(customer)).data["phone"]
        full = clients["manager"].get(detail_url(customer)).data["phone"]

        assert full == customer.phone
        assert masked == "*" * (len(full) - 4) + full[-4:]

    def test_finance_sees_masked_phone_on_loans_and_in_the_trail(
        self, clients, admin_user, customer, make_loan, today
    ):
        make_loan(customer, first_due_date=today)
        update_customer(admin_user, customer, phone="9123456789")
        finance = clients["finance"]

        loans = finance.get("/api/loans/").data["results"]
        customer_loans = finance.get(detail_url(customer, "loans")).data["results"]
        trail = finance.get("/api/audit-logs/", {"entity_type": "customer"}).data["results"]

        assert {row["customer_phone"] for row in loans + customer_loans} == {"******6789"}
        update = next(entry for entry in trail if entry["action"] == "CUSTOMER_UPDATED")
        assert update["after"]["phone"] == "******6789"
        assert update["before"]["phone"].startswith("*")
        full = clients["admin"].get("/api/loans/").data["results"][0]["customer_phone"]
        assert full == "9123456789"

    def test_finance_cannot_search_customers_by_phone(self, clients, customer, make_loan, today):
        make_loan(customer, first_due_date=today)
        by_phone = {"search": customer.phone}

        assert clients["finance"].get(URL, by_phone).data["count"] == 0
        assert clients["finance"].get("/api/loans/", by_phone).data["count"] == 0
        assert clients["manager"].get(URL, by_phone).data["count"] == 1
        assert clients["finance"].get(URL, {"search": customer.full_name}).data["count"] == 1

    def test_query_count_is_constant(
        self, clients, branch, agent, make_loan, today, django_assert_max_num_queries
    ):
        for customer in factories.CustomerFactory.create_batch(
            12, branch=branch, assigned_agent=agent
        ):
            make_loan(customer, first_due_date=today)

        with django_assert_max_num_queries(5):
            res = clients["admin"].get(URL)

        assert res.data["count"] == 12


class TestDetail:
    def test_includes_dues_and_loan_summaries(
        self, clients, customer, make_loan, today, overdue_date
    ):
        late = make_loan(customer, first_due_date=overdue_date)
        current = make_loan(customer, first_due_date=today, principal=Decimal("50000.00"))
        first, second, *_ = installments(late)
        pay(first, Decimal("1000.00"))
        overdue = first.amount_due + second.amount_due - Decimal("1000.00")

        res = clients["agent"].get(detail_url(customer))

        assert res.status_code == 200
        outstanding = late.total_payable + current.total_payable - Decimal("1000.00")
        assert res.data["outstanding"] == str(outstanding)
        assert res.data["overdue_amount"] == str(overdue)
        assert res.data["due_today"] == str(current.emi_amount)
        assert res.data["next_due_date"] == overdue_date.isoformat()
        assert res.data["active_loans"] == 2
        newest, oldest = res.data["loans"]
        assert (newest["loan_number"], oldest["loan_number"]) == (
            current.loan_number,
            late.loan_number,
        )
        assert oldest["overdue_amount"] == str(overdue)
        assert oldest["outstanding"] == str(late.total_payable - Decimal("1000.00"))
        assert newest["next_due_date"] == today.isoformat()

    def test_query_count_does_not_grow_with_loans(
        self, clients, customer, make_loan, today, django_assert_max_num_queries
    ):
        for _ in range(5):
            make_loan(customer, first_due_date=today)

        with django_assert_max_num_queries(5):
            res = clients["manager"].get(detail_url(customer))

        assert len(res.data["loans"]) == 5

    def test_loans_endpoint_is_paginated_newest_first(self, clients, customer, make_loan, today):
        older = make_loan(customer, first_due_date=today - timedelta(days=60))
        newer = make_loan(customer, first_due_date=today)

        res = clients["agent"].get(detail_url(customer, "loans"))

        assert res.data["count"] == 2
        assert [row["id"] for row in res.data["results"]] == [newer.pk, older.pk]

    def test_loans_carry_the_same_balances_as_the_loan_list(
        self, clients, customer, make_loan, today
    ):
        make_loan(customer, first_due_date=today - timedelta(days=60))
        make_loan(customer, first_due_date=today)

        nested = clients["manager"].get(detail_url(customer, "loans")).data["results"]
        listed = clients["manager"].get("/api/loans/", {"customer": customer.pk}).data["results"]

        assert sorted(nested, key=lambda loan: loan["id"]) == sorted(
            listed, key=lambda loan: loan["id"]
        )
        assert nested[1]["next_due"]["installment_no"] == 1
        assert nested[1]["overdue_amount"] != "0.00"


class TestAgentRoute:
    @pytest.fixture
    def route(self, agent, other_agent, branch, make_loan, today, overdue_date):
        def customer_of(owner, name, **extra):
            return factories.CustomerFactory(
                branch=branch, assigned_agent=owner, full_name=name, **extra
            )

        route = {
            "overdue": customer_of(agent, "Zoya Overdue"),
            "today": customer_of(agent, "Yash Today"),
            "upcoming": customer_of(agent, "Xavier Upcoming"),
            "idle": customer_of(agent, "Aarav Idle"),
        }
        make_loan(route["overdue"], first_due_date=overdue_date)
        make_loan(route["today"], first_due_date=today)
        make_loan(route["upcoming"], first_due_date=today + timedelta(days=10))
        make_loan(customer_of(agent, "Inactive", is_active=False), first_due_date=overdue_date)
        make_loan(customer_of(other_agent, "Colleague"), first_due_date=overdue_date)
        return route

    def test_lists_active_assigned_customers_overdue_first(self, clients, route):
        res = clients["agent"].get(ROUTE_URL)

        assert res.status_code == 200
        assert [row["id"] for row in res.data["results"]] == [
            route[name].pk for name in ("overdue", "today", "upcoming", "idle")
        ]

    def test_rows_carry_dues(self, clients, route, today, overdue_date):
        loan = route["overdue"].loans.get()
        first, second, *_ = installments(loan)

        rows = {row["id"]: row for row in clients["agent"].get(ROUTE_URL).data["results"]}

        overdue, due_today = rows[route["overdue"].pk], rows[route["today"].pk]
        assert overdue["overdue_amount"] == str(first.amount_due + second.amount_due)
        assert overdue["outstanding"] == str(loan.total_payable)
        assert overdue["next_due_date"] == overdue_date.isoformat()
        assert due_today["due_today"] == str(route["today"].loans.get().emi_amount)
        assert due_today["overdue_amount"] == "0.00"
        assert rows[route["idle"].pk]["next_due_date"] is None

    @pytest.mark.parametrize(("due", "expected"), [("overdue", "overdue"), ("today", "today")])
    def test_due_filter(self, clients, route, due, expected):
        res = clients["agent"].get(ROUTE_URL, {"due": due})

        assert [row["id"] for row in res.data["results"]] == [route[expected].pk]

    def test_invalid_due_filter_is_rejected(self, clients, route):
        res = clients["agent"].get(ROUTE_URL, {"due": "someday"})

        assert res.status_code == 400
        assert "due" in res.data["error"]["details"]

    def test_search(self, clients, route):
        res = clients["agent"].get(ROUTE_URL, {"search": "xavier"})

        assert [row["id"] for row in res.data["results"]] == [route["upcoming"].pk]

    def test_query_count_is_constant(
        self, clients, route, agent, make_loan, today, django_assert_max_num_queries
    ):
        for customer in factories.CustomerFactory.create_batch(
            10, branch=agent.branch, assigned_agent=agent
        ):
            make_loan(customer, first_due_date=today)

        with django_assert_max_num_queries(5):
            res = clients["agent"].get(ROUTE_URL)

        assert res.data["count"] == 14
