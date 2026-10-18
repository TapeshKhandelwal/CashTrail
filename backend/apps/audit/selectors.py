from collections import defaultdict
from collections.abc import Iterable

from django.apps import apps

from .models import AuditLog

# What each audited record is called on screen.
ENTITY_LABELS = {
    "collection": "Receipt",
    "cashsubmission": "Hand-over",
    "bankdeposit": "Deposit",
    "discrepancy": "Discrepancy",
    "gatewayorder": "UPI order",
    "loan": "Loan",
    "customer": "Customer",
    "user": "User",
    "bankaccount": "Bank account",
    "branch": "Branch",
}

# The business reference of each record type; the first non-empty field wins.
_REFERENCE_FIELDS = {
    "collection": ("collections.Collection", ("receipt_number",)),
    "cashsubmission": ("reconciliation.CashSubmission", ("submission_number",)),
    "bankdeposit": ("deposits.BankDeposit", ("deposit_number",)),
    "discrepancy": (
        "reconciliation.Discrepancy",
        ("submission__submission_number", "deposit__deposit_number"),
    ),
    "gatewayorder": ("payments.GatewayOrder", ("provider_order_id",)),
    "loan": ("loans.Loan", ("loan_number",)),
    "customer": ("customers.Customer", ("customer_code",)),
    "user": ("accounts.User", ("username",)),
    "bankaccount": ("deposits.BankAccount", ("account_number_last4",)),
    "branch": ("branches.Branch", ("code",)),
}


def entity_label(entity_type: str) -> str:
    return ENTITY_LABELS.get(entity_type, entity_type.capitalize())


def entity_references(entries: Iterable[AuditLog]) -> dict[tuple[str, str], str]:
    """`{(entity_type, entity_id): reference}` for a page of entries, one query per record type.

    Records that have no reference, or no longer exist, are left out.
    """
    wanted: dict[str, set[int]] = defaultdict(set)
    for entry in entries:
        if entry.entity_type in _REFERENCE_FIELDS and entry.entity_id.isdigit():
            wanted[entry.entity_type].add(int(entry.entity_id))

    references = {}
    for entity_type, pks in wanted.items():
        label, fields = _REFERENCE_FIELDS[entity_type]
        rows = apps.get_model(label).objects.filter(pk__in=pks).values_list("pk", *fields)
        for pk, *values in rows:
            reference = next((value for value in values if value), None)
            if reference:
                references[(entity_type, str(pk))] = _format(entity_type, reference)
    return references


def _format(entity_type: str, reference: str) -> str:
    # Only the last four digits of an account are stored; show them the way the app does.
    return f"XXXX{reference}" if entity_type == "bankaccount" else reference
