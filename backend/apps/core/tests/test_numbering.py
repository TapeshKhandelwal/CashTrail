from concurrent.futures import ThreadPoolExecutor
from datetime import date

import pytest
from django.db import connection, transaction

from apps.core import numbering
from apps.core.models import DocumentSequence

DAY = date(2026, 10, 17)


@pytest.mark.django_db
def test_formats():
    assert numbering.receipt_number("BLR01", DAY) == "RCT-BLR01-20261017-00001"
    assert numbering.submission_number("BLR01", DAY) == "SUB-BLR01-20261017-001"
    assert numbering.deposit_number("GATEWAY", DAY) == "DEP-GATEWAY-20261017-001"
    assert numbering.loan_number("BLR01") == "LN-BLR01-000001"
    assert numbering.customer_number() == "CUS-000001"


@pytest.mark.django_db
def test_sequences_are_independent_per_prefix_scope_and_day():
    assert numbering.receipt_number("BLR01", DAY).endswith("-00001")
    assert numbering.receipt_number("BLR01", DAY).endswith("-00002")
    assert numbering.receipt_number("MUM01", DAY).endswith("-00001")
    assert numbering.receipt_number("BLR01", date(2026, 10, 18)).endswith("-00001")
    assert numbering.submission_number("BLR01", DAY).endswith("-001")


@pytest.mark.django_db
def test_rolled_back_numbers_are_reused():
    """The counter commits with the document, so an aborted document leaves no gap."""
    with pytest.raises(RuntimeError), transaction.atomic():
        numbering.receipt_number("BLR01", DAY)
        raise RuntimeError

    assert numbering.receipt_number("BLR01", DAY) == "RCT-BLR01-20261017-00001"


@pytest.mark.django_db
def test_undated_sequences_share_one_counter():
    numbering.customer_number()
    numbering.customer_number()

    assert DocumentSequence.objects.get(prefix="CUS").last_value == 2


@pytest.mark.django_db(transaction=True)
def test_concurrent_requests_get_unique_gap_free_numbers():
    def issue(_):
        try:
            with transaction.atomic():
                return numbering.receipt_number("BLR01", DAY)
        finally:
            connection.close()

    with ThreadPoolExecutor(max_workers=8) as pool:
        numbers = list(pool.map(issue, range(40)))

    assert len(set(numbers)) == 40
    assert sorted(numbers) == [f"RCT-BLR01-20261017-{n:05d}" for n in range(1, 41)]
