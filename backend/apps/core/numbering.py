"""Readable, unique document numbers.

Financial documents are gap-free: the counter row is locked until the caller's
transaction ends, so a number is only consumed when its document is committed.
"""

from datetime import date

from django.db import connection, transaction

from .dates import business_date
from .models import DocumentSequence


def next_number(
    prefix: str,
    scope_code: str = "",
    period: date | None = None,
    *,
    width: int = 5,
) -> str:
    """`next_number("RCT", "BLR01", date(2026, 10, 17))` -> `RCT-BLR01-20261017-00012`."""
    with transaction.atomic():
        sequence, _ = DocumentSequence.objects.select_for_update().get_or_create(
            prefix=prefix, scope=scope_code, period=period
        )
        sequence.last_value += 1
        sequence.save(update_fields=["last_value", "updated_at"])

    parts = [
        prefix,
        scope_code,
        period.strftime("%Y%m%d") if period else "",
        f"{sequence.last_value:0{width}d}",
    ]
    return "-".join(part for part in parts if part)


def receipt_number(branch_code: str, on: date | None = None) -> str:
    return next_number("RCT", branch_code, on or business_date(), width=5)


def submission_number(branch_code: str, on: date | None = None) -> str:
    return next_number("SUB", branch_code, on or business_date(), width=3)


def deposit_number(scope_code: str, on: date | None = None) -> str:
    """Scope is the branch code for cash deposits and `GATEWAY` for gateway settlements."""
    return next_number("DEP", scope_code, on or business_date(), width=3)


ORDER_RECEIPT_SEQUENCE = "payments_order_receipt_seq"


def gateway_order_receipt(branch_code: str, on: date | None = None) -> str:
    """Gateway order references only need to be unique, so they come from a database
    sequence: no counter row stays locked while the gateway is being called."""
    with connection.cursor() as cursor:
        cursor.execute("SELECT nextval(%s)", [ORDER_RECEIPT_SEQUENCE])
        (value,) = cursor.fetchone()
    return f"ORD-{branch_code}-{(on or business_date()):%Y%m%d}-{value:06d}"


def loan_number(branch_code: str) -> str:
    return next_number("LN", branch_code, width=6)


def customer_number() -> str:
    return next_number("CUS", width=6)
