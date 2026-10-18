from decimal import Decimal

from django.utils import timezone

from apps.loans.models import Installment, Loan


def pay(installment: Installment, amount: Decimal) -> None:
    """Applies a payment the way the collection service does, without the workflow around it."""
    installment.amount_paid += amount
    installment.sync_status(at=timezone.now())
    installment.save()
    loan = Loan.objects.get(pk=installment.loan_id)
    loan.amount_paid += amount
    if loan.amount_paid == loan.total_payable:
        loan.status, loan.closed_at = Loan.Status.CLOSED, timezone.now()
    loan.save()


def installments(loan: Loan) -> list[Installment]:
    return list(loan.installments.order_by("installment_no"))
