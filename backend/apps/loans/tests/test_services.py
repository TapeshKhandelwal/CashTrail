from datetime import timedelta
from decimal import Decimal

import pytest
from dateutil.relativedelta import relativedelta
from django.utils import timezone

from apps.audit.models import AuditAction, AuditLog
from apps.collections.models import Collection
from apps.core.dates import business_date
from apps.core.exceptions import RecordLocked, ResourceNotFound, ScopeViolation, ValidationFailed
from apps.core.testing import factories
from apps.loans.models import Installment, Loan
from apps.loans.services import build_schedule, create_loan, update_loan_terms

from .utils import months_ago

pytestmark = pytest.mark.django_db


class TestBuildSchedule:
    def test_defaults_to_disbursal_today_and_first_emi_a_month_later(self, loan_terms):
        schedule = build_schedule(**loan_terms)

        assert schedule.disbursed_on == business_date()
        assert schedule.first_due_date == business_date() + relativedelta(months=1)
        assert schedule.emi_amount == Decimal("8885.00")
        assert len(schedule.rows) == 12
        assert schedule.total_payable == sum(row.amount_due for row in schedule.rows)
        assert schedule.total_interest == schedule.total_payable - Decimal("100000.00")

    def test_zero_rate_splits_principal_evenly(self):
        schedule = build_schedule(
            principal=Decimal("12000.00"), annual_interest_rate=Decimal("0"), tenure_months=12
        )

        assert schedule.emi_amount == Decimal("1000.00")
        assert schedule.total_payable == Decimal("12000.00")
        assert schedule.total_interest == Decimal("0.00")

    def test_rejects_future_disbursal(self, loan_terms):
        tomorrow = business_date() + timedelta(days=1)

        with pytest.raises(ValidationFailed, match="future"):
            build_schedule(**loan_terms, disbursed_on=tomorrow)

    @pytest.mark.parametrize("offset_days", [0, -1])
    def test_first_due_date_must_follow_disbursal(self, loan_terms, offset_days):
        disbursed_on = months_ago(1)

        with pytest.raises(ValidationFailed) as excinfo:
            build_schedule(
                **loan_terms,
                disbursed_on=disbursed_on,
                first_due_date=disbursed_on + timedelta(days=offset_days),
            )

        assert set(excinfo.value.details) == {"disbursed_on", "first_due_date"}

    def test_rejects_rate_above_hundred_percent(self, loan_terms):
        with pytest.raises(ValidationFailed, match="100%"):
            build_schedule(**{**loan_terms, "annual_interest_rate": Decimal("100.01")})

    def test_rejects_principal_too_small_for_tenure(self):
        with pytest.raises(ValidationFailed, match="too small"):
            build_schedule(
                principal=Decimal("0.05"), annual_interest_rate=Decimal("0"), tenure_months=12
            )

    def test_rejects_out_of_range_tenure(self, loan_terms):
        with pytest.raises(ValidationFailed, match="Tenure"):
            build_schedule(**{**loan_terms, "tenure_months": 361})

    def test_rejects_terms_whose_total_does_not_fit_a_money_column(self):
        with pytest.raises(ValidationFailed, match="total repayable"):
            build_schedule(
                principal=Decimal("900000000000.00"),
                annual_interest_rate=Decimal("36.00"),
                tenure_months=360,
            )


class TestCreateLoan:
    def test_creates_loan_with_schedule_and_audit_entry(self, manager, customer, loan_terms):
        loan = create_loan(manager, customer_id=customer.pk, **loan_terms)

        assert loan.loan_number == "LN-BLR01-000001"
        assert loan.branch == customer.branch
        assert loan.status == Loan.Status.ACTIVE
        assert loan.emi_amount == Decimal("8885.00")
        assert loan.amount_paid == Decimal("0.00")
        assert loan.created_by == manager

        installments = list(loan.installments.order_by("installment_no"))
        assert [i.installment_no for i in installments] == list(range(1, 13))
        assert installments[0].due_date == loan.first_due_date
        assert all(i.status == Installment.Status.PENDING for i in installments)
        assert sum(i.amount_due for i in installments) == loan.total_payable
        assert sum(i.principal_component for i in installments) == loan.principal

        entry = AuditLog.objects.get(action=AuditAction.LOAN_CREATED)
        assert entry.actor == manager
        assert entry.entity_id == str(loan.pk)
        assert entry.branch_id == customer.branch_id
        assert entry.after["principal"] == "100000.00"
        assert entry.after["total_payable"] == str(loan.total_payable)

    def test_loan_numbers_are_sequential_per_branch(
        self, admin_user, customer, other_branch_customer, loan_terms
    ):
        numbers = [
            create_loan(admin_user, customer_id=c.pk, **loan_terms).loan_number
            for c in (customer, customer, other_branch_customer)
        ]

        assert numbers == ["LN-BLR01-000001", "LN-BLR01-000002", "LN-MUM01-000001"]

    def test_backdated_loan_keeps_requested_dates(self, admin_user, customer, loan_terms):
        disbursed_on = months_ago(3)
        first_due = disbursed_on + timedelta(days=45)

        loan = create_loan(
            admin_user,
            customer_id=customer.pk,
            disbursed_on=disbursed_on,
            first_due_date=first_due,
            **loan_terms,
        )

        assert (loan.disbursed_on, loan.first_due_date) == (disbursed_on, first_due)

    def test_manager_cannot_lend_to_another_branchs_customer(
        self, manager, other_branch_customer, loan_terms
    ):
        with pytest.raises(ResourceNotFound):
            create_loan(manager, customer_id=other_branch_customer.pk, **loan_terms)

        assert not Loan.objects.exists()

    def test_unknown_customer_is_not_found(self, admin_user, loan_terms):
        with pytest.raises(ResourceNotFound):
            create_loan(admin_user, customer_id=999_999, **loan_terms)

    @pytest.mark.parametrize("role_fixture", ["agent", "finance_user"])
    def test_only_admins_and_managers_create_loans(
        self, request, role_fixture, customer, loan_terms
    ):
        actor = request.getfixturevalue(role_fixture)

        with pytest.raises(ScopeViolation):
            create_loan(actor, customer_id=customer.pk, **loan_terms)

    def test_inactive_customer_is_rejected(self, admin_user, customer, loan_terms):
        customer.is_active = False
        customer.save()

        with pytest.raises(ValidationFailed, match="inactive customer"):
            create_loan(admin_user, customer_id=customer.pk, **loan_terms)

    def test_inactive_branch_is_rejected(self, admin_user, customer, loan_terms):
        customer.branch.is_active = False
        customer.branch.save()

        with pytest.raises(ValidationFailed, match="branch is inactive"):
            create_loan(admin_user, customer_id=customer.pk, **loan_terms)

    def test_invalid_terms_do_not_consume_a_loan_number(self, admin_user, customer, loan_terms):
        with pytest.raises(ValidationFailed):
            create_loan(admin_user, customer_id=customer.pk, **{**loan_terms, "tenure_months": 0})

        loan = create_loan(admin_user, customer_id=customer.pk, **loan_terms)

        assert loan.loan_number == "LN-BLR01-000001"


class TestUpdateLoanTerms:
    def test_recomputes_schedule_in_place(self, manager, loan):
        installment_ids = list(loan.installments.values_list("pk", flat=True))

        updated = update_loan_terms(
            manager, loan, principal=Decimal("50000.00"), annual_interest_rate=Decimal("10.00")
        )

        assert updated.principal == Decimal("50000.00")
        assert updated.emi_amount == Decimal("4396.00")
        installments = list(updated.installments.order_by("installment_no"))
        assert [i.pk for i in installments] == installment_ids
        assert sum(i.principal_component for i in installments) == Decimal("50000.00")
        assert sum(i.amount_due for i in installments) == updated.total_payable

    def test_moving_dates_shifts_due_dates(self, admin_user, loan):
        first_due = loan.first_due_date + timedelta(days=5)

        update_loan_terms(admin_user, loan, first_due_date=first_due)

        schedule = loan.installments.order_by("installment_no")
        due_dates = list(schedule.values_list("due_date", flat=True))
        assert due_dates[0] == first_due
        assert due_dates[1] == first_due + relativedelta(months=1)

    def test_writes_before_and_after_to_audit_log(self, manager, loan):
        update_loan_terms(manager, loan, principal=Decimal("90000.00"))

        entry = AuditLog.objects.get(action=AuditAction.LOAN_UPDATED)
        assert entry.before["principal"] == "100000.00"
        assert entry.after["principal"] == "90000.00"
        assert entry.before["emi_amount"] == "8885.00"
        assert entry.after["emi_amount"] != entry.before["emi_amount"]

    def test_unchanged_values_are_a_no_op(self, manager, loan):
        update_loan_terms(manager, loan, principal=loan.principal, tenure_months=12)

        assert not AuditLog.objects.filter(action=AuditAction.LOAN_UPDATED).exists()

    def test_locked_after_a_collection(self, manager, loan):
        factories.CollectionFactory(loan=loan)

        with pytest.raises(RecordLocked) as excinfo:
            update_loan_terms(manager, loan, principal=Decimal("90000.00"))

        assert excinfo.value.details == {"loan_number": loan.loan_number, "fields": ["principal"]}
        loan.refresh_from_db()
        assert loan.principal == Decimal("100000.00")

    def test_voided_collection_still_locks_terms(self, manager, loan):
        factories.CollectionFactory(
            loan=loan, status=Collection.Status.VOIDED, voided_at=timezone.now()
        )

        with pytest.raises(RecordLocked):
            update_loan_terms(manager, loan, annual_interest_rate=Decimal("11.00"))

    def test_locked_after_a_upi_order(self, manager, loan):
        factories.GatewayOrderFactory(loan=loan)

        with pytest.raises(RecordLocked):
            update_loan_terms(manager, loan, principal=Decimal("90000.00"))

    def test_tenure_is_fixed(self, manager, loan):
        with pytest.raises(ValidationFailed, match="tenure"):
            update_loan_terms(manager, loan, tenure_months=24)

    def test_new_terms_are_validated(self, manager, loan):
        with pytest.raises(ValidationFailed):
            update_loan_terms(manager, loan, first_due_date=loan.disbursed_on)

    def test_other_branch_manager_is_refused(self, other_branch_manager, loan):
        with pytest.raises(ScopeViolation):
            update_loan_terms(other_branch_manager, loan, principal=Decimal("90000.00"))

    def test_agent_is_refused(self, agent, loan):
        with pytest.raises(ScopeViolation):
            update_loan_terms(agent, loan, principal=Decimal("90000.00"))

    def test_rejects_fields_that_are_not_terms(self, manager, loan):
        with pytest.raises(TypeError):
            update_loan_terms(manager, loan, amount_paid=Decimal("1.00"))
