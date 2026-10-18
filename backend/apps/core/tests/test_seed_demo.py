from decimal import Decimal
from io import StringIO

import pytest
from django.core.management import call_command
from django.db.models import Q, Sum
from django.urls import reverse

from apps.accounts.models import User
from apps.collections.models import Allocation, Collection
from apps.core.management.demo.data import DEMO_PASSWORD
from apps.core.management.demo.reset import wipe_data
from apps.core.money import ZERO
from apps.deposits.models import BankDeposit
from apps.loans.models import Installment, Loan
from apps.payments.models import GatewayOrder, WebhookEvent
from apps.reconciliation.models import CashSubmission, Discrepancy

pytestmark = pytest.mark.django_db

SEED = 7
LIFECYCLE_MODELS = (Loan, Installment, Collection, CashSubmission, BankDeposit, Discrepancy)


@pytest.fixture(scope="module", autouse=True)
def demo_data(django_db_setup, django_db_blocker):
    """Seeded once for the module; each test still runs in its own rolled-back transaction."""
    with django_db_blocker.unblock():
        call_command("seed_demo", seed=SEED, stdout=StringIO())
        yield
        wipe_data()


def seed(*args) -> str:
    out = StringIO()
    call_command("seed_demo", *args, f"--seed={SEED}", "--no-input", stdout=out)
    return out.getvalue()


def receipts() -> list[tuple]:
    return list(
        Collection.objects.order_by("receipt_number").values_list(
            "receipt_number", "amount", "mode", "status"
        )
    )


@pytest.mark.parametrize("model", [*LIFECYCLE_MODELS, GatewayOrder], ids=lambda m: m.__name__)
def test_every_lifecycle_state_is_present(model):
    statuses = set(model.objects.values_list("status", flat=True))

    assert statuses == set(model.Status.values)


def test_every_kind_of_difference_and_payment_is_present():
    assert set(Discrepancy.objects.values_list("kind", flat=True)) == set(Discrepancy.Kind.values)
    assert set(Collection.objects.values_list("mode", flat=True)) == set(Collection.Mode.values)
    sources = set(BankDeposit.objects.values_list("source", flat=True))
    assert sources == set(BankDeposit.Source.values)


def test_balances_equal_the_effective_allocations():
    allocated = Sum("allocations__amount", filter=Q(allocations__reversed_at__isnull=True))
    for installment in Installment.objects.annotate(allocated=allocated):
        assert installment.amount_paid == (installment.allocated or ZERO), installment
    for loan in Loan.objects.all():
        allocated = Allocation.objects.filter(
            installment__loan=loan, reversed_at__isnull=True
        ).aggregate(total=Sum("amount"))["total"]
        assert loan.amount_paid == (allocated or ZERO), loan.loan_number
        assert loan.is_closed == (loan.outstanding == ZERO), loan.loan_number


def test_receipts_track_their_hand_over_and_deposit():
    for collection in Collection.objects.select_related("submission", "deposit"):
        if collection.status in (Collection.Status.SUBMITTED, Collection.Status.BRANCH_RECEIVED):
            assert collection.submission is not None
        if collection.status == Collection.Status.DEPOSITED:
            assert collection.deposit.status == BankDeposit.Status.PENDING
        if collection.status == Collection.Status.SETTLED:
            assert collection.deposit.status in BankDeposit.SETTLED_STATUSES


def test_branch_counts_48500_against_50000_handed_over():
    submission = CashSubmission.objects.get(expected_amount=Decimal("50000.00"))

    assert submission.received_amount == Decimal("48500.00")
    shortage = submission.discrepancies.get()
    assert (shortage.kind, shortage.amount, shortage.status) == (
        Discrepancy.Kind.CASH_SHORTAGE,
        Decimal("1500.00"),
        Discrepancy.Status.OPEN,
    )


def test_rejected_receipts_are_resubmitted_and_failed_deposit_is_rebanked():
    rejected = CashSubmission.objects.get(status=CashSubmission.Status.REJECTED)
    resubmitted = CashSubmission.objects.filter(
        agent=rejected.agent, submitted_at__gt=rejected.submitted_at
    ).first()
    assert resubmitted.is_approved

    failed = BankDeposit.objects.get(status=BankDeposit.Status.FAILED)
    assert not failed.collections.exists()
    assert (
        BankDeposit.objects.filter(branch=failed.branch, deposit_date__gt=failed.deposit_date)
        .filter(status__in=BankDeposit.SETTLED_STATUSES)
        .exists()
    )


def test_upi_payments_are_recorded_through_signed_webhooks():
    paid = GatewayOrder.objects.filter(status=GatewayOrder.Status.PAID)

    captured = WebhookEvent.objects.filter(event_type="payment.captured")
    assert paid.count() == Collection.objects.filter(mode="UPI").count()
    assert captured.count() == paid.count() + 1  # one captured after the loan was paid off
    assert not WebhookEvent.objects.filter(processed_at__isnull=True).exists()


def test_a_payment_captured_after_payoff_is_left_for_refund():
    order = GatewayOrder.objects.get(status=GatewayOrder.Status.REFUND_DUE)

    assert order.collection is None
    assert order.provider_payment_id
    assert order.loan.status == Loan.Status.CLOSED


def test_bank_charges_are_classified_as_such():
    charges = Discrepancy.objects.get(reason_code=Discrepancy.ReasonCode.BANK_CHARGES)

    assert charges.kind == Discrepancy.Kind.SETTLEMENT_MISMATCH
    assert charges.amount == Decimal("118.00")


def test_dashboards_have_open_work_to_show():
    assert BankDeposit.objects.delayed().exists()
    assert BankDeposit.objects.pending().exclude(pk__in=BankDeposit.objects.delayed()).exists()
    assert Collection.objects.filter(mode=Collection.Mode.CASH, status="COLLECTED").exists()
    assert Collection.objects.filter(mode=Collection.Mode.UPI, status="COLLECTED").exists()
    assert Installment.objects.filter(status=Installment.Status.PARTIALLY_PAID).exists()
    assert any(installment.is_overdue for installment in Installment.objects.all())


@pytest.mark.parametrize("username", ["admin", "finance", "manager.blr", "agent.blr1"])
def test_each_role_signs_in_and_sees_the_dashboard(api_client, username):
    login = api_client.post(
        reverse("login"), {"username": username, "password": DEMO_PASSWORD}, format="json"
    )
    assert login.status_code == 200
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {login.json()['access']}")

    response = api_client.get(reverse("dashboard-summary"))

    assert response.status_code == 200
    assert response.json()["collected"]["count"] > 0


def test_rerun_without_reset_changes_nothing():
    before = receipts()

    output = seed()

    assert "already loaded" in output
    assert receipts() == before


def test_reset_rebuilds_the_same_data_for_the_same_seed():
    before = receipts()

    output = seed("--reset")

    assert "Demo data loaded" in output
    assert receipts() == before
    assert User.objects.filter(username="admin", is_superuser=True).exists()


def test_wipe_clears_tables_guarded_by_delete_triggers():
    wipe_data()

    assert not Collection.objects.exists()
    assert not User.objects.exists()
