"""Money helpers. Amounts are always `Decimal` rupees with two places; never floats."""

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

from django.db.models import DecimalField, Q, Sum, Value
from django.db.models.functions import Coalesce
from rest_framework import serializers

PAISE = Decimal("0.01")
ZERO = Decimal("0.00")
MAX_DIGITS = 14
DECIMAL_PLACES = 2
# Largest amount a NUMERIC(14, 2) money column can hold.
MAX_AMOUNT = Decimal(10 ** (MAX_DIGITS - DECIMAL_PLACES)) - PAISE


def to_money(value: Decimal | int | str) -> Decimal:
    """Convert to a two-place Decimal, rounding half-up. Floats are rejected outright."""
    if isinstance(value, float):
        raise TypeError("Money must not be a float; pass a Decimal, int or string.")
    if isinstance(value, bool):
        raise TypeError("Money must not be a boolean.")
    try:
        amount = value if isinstance(value, Decimal) else Decimal(str(value).strip())
    except InvalidOperation as exc:
        raise ValueError(f"Invalid money amount: {value!r}") from exc
    if not amount.is_finite():
        raise ValueError(f"Invalid money amount: {value!r}")
    return amount.quantize(PAISE, rounding=ROUND_HALF_UP)


def paise_to_money(paise: int) -> Decimal:
    """Gateways report amounts in paise (integer minor units)."""
    if isinstance(paise, bool) or not isinstance(paise, int):
        raise TypeError("Paise must be an integer.")
    return (Decimal(paise) / 100).quantize(PAISE)


def money_to_paise(amount: Decimal | int | str) -> int:
    return int(to_money(amount) * 100)


def money_sum(expression, condition: Q | None = None) -> Coalesce:
    """SUM of a money expression, optionally conditional; zero rather than NULL for no rows."""
    output = DecimalField(max_digits=MAX_DIGITS, decimal_places=DECIMAL_PLACES)
    return Coalesce(
        Sum(expression, filter=condition, output_field=output), Value(ZERO), output_field=output
    )


class MoneyField(serializers.DecimalField):
    """Two-place decimal serialized as a string. Positive by default; JSON floats are rejected."""

    default_error_messages = {
        "float": 'Send amounts as strings (e.g. "1500.00"), not floating-point numbers.',
    }

    def __init__(self, **kwargs):
        kwargs.setdefault("max_digits", MAX_DIGITS)
        kwargs.setdefault("decimal_places", DECIMAL_PLACES)
        kwargs.setdefault("min_value", PAISE)
        super().__init__(**kwargs)

    def to_internal_value(self, data):
        if isinstance(data, float):
            self.fail("float")
        return super().to_internal_value(data)
