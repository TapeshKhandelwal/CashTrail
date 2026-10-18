from datetime import date
from decimal import Decimal

from dateutil.relativedelta import relativedelta

from apps.core.dates import business_date
from apps.loans.models import Installment, Loan


def months_ago(months: int) -> date:
    return business_date() - relativedelta(months=months)


def pay(installment: Installment, amount: Decimal | str) -> Installment:
    """Mark part of an installment paid and keep the loan balance in step."""
    amount = Decimal(amount)
    installment.amount_paid += amount
    installment.sync_status()
    installment.save()
    Loan.objects.filter(pk=installment.loan_id).update(
        amount_paid=installment.loan.amount_paid + amount
    )
    installment.loan.refresh_from_db()
    return installment
