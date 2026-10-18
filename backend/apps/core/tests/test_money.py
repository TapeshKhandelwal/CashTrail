from decimal import Decimal

import pytest
from rest_framework import serializers

from apps.core.money import MoneyField, money_to_paise, paise_to_money, to_money


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (Decimal("10"), Decimal("10.00")),
        ("48500", Decimal("48500.00")),
        (" 1.005 ", Decimal("1.01")),
        ("1.004", Decimal("1.00")),
        (Decimal("-2.345"), Decimal("-2.35")),
        (7, Decimal("7.00")),
    ],
)
def test_to_money_quantizes_half_up(value, expected):
    result = to_money(value)

    assert result == expected
    assert result.as_tuple().exponent == -2


@pytest.mark.parametrize("value", [0.1, 10.0, True])
def test_to_money_rejects_floats_and_bools(value):
    with pytest.raises(TypeError):
        to_money(value)


@pytest.mark.parametrize("value", ["abc", "", "NaN", "Infinity"])
def test_to_money_rejects_non_numbers(value):
    with pytest.raises(ValueError):
        to_money(value)


def test_paise_round_trip():
    assert paise_to_money(4850050) == Decimal("48500.50")
    assert money_to_paise(Decimal("48500.50")) == 4850050
    assert money_to_paise("0.01") == 1


def test_paise_must_be_integer():
    with pytest.raises(TypeError):
        paise_to_money(100.0)


class AmountSerializer(serializers.Serializer):
    amount = MoneyField()


@pytest.mark.parametrize("value", ["1500.50", 1500, "0.01"])
def test_money_field_accepts_strings_and_integers(value):
    serializer = AmountSerializer(data={"amount": value})

    assert serializer.is_valid(), serializer.errors
    assert isinstance(serializer.validated_data["amount"], Decimal)


@pytest.mark.parametrize("value", [1500.5, "0", "-1", "1.005", "1000000000000.00"])
def test_money_field_rejects_invalid_amounts(value):
    assert not AmountSerializer(data={"amount": value}).is_valid()


def test_money_field_serializes_as_string():
    assert AmountSerializer({"amount": Decimal("48500")}).data["amount"] == "48500.00"
