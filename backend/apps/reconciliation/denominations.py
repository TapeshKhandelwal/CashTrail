"""Cash counts are recorded as `{"500": 90, "200": 10}`: rupee value -> number of notes/coins."""

from collections.abc import Mapping
from decimal import Decimal

# Legal-tender notes and coins in circulation, in rupees.
DENOMINATIONS = (2000, 500, 200, 100, 50, 20, 10, 5, 2, 1)
DENOMINATION_KEYS = frozenset(str(value) for value in DENOMINATIONS)


def normalize_denominations(counts: Mapping[str, int]) -> dict[str, int]:
    """Validated copy without zero counts, largest denomination first."""
    unknown = sorted(set(counts) - DENOMINATION_KEYS)
    if unknown:
        raise ValueError(f"Unknown denominations: {', '.join(unknown)}.")
    for key, count in counts.items():
        if isinstance(count, bool) or not isinstance(count, int) or count < 0:
            raise ValueError(f"Count for {key} must be a non-negative whole number.")
    return {str(value): counts[str(value)] for value in DENOMINATIONS if counts.get(str(value))}


def denominations_total(counts: Mapping[str, int]) -> Decimal:
    return sum((Decimal(key) * count for key, count in counts.items()), Decimal("0.00"))
