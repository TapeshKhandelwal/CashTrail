from datetime import date
from decimal import Decimal
from itertools import pairwise

import pytest

from apps.loans.schedule import calculate_emi, generate_schedule


def _rupees(amount: Decimal) -> bool:
    return amount == amount.to_integral_value()


def test_known_emi():
    # The exact EMI is 8884.88; instalments are whole rupees.
    assert calculate_emi(Decimal("100000"), Decimal("12"), 12) == Decimal("8885.00")


def test_schedule_repays_principal_exactly():
    rows = generate_schedule(Decimal("100000"), Decimal("12"), 12, date(2026, 11, 5))

    assert len(rows) == 12
    assert sum(r.principal_component for r in rows) == Decimal("100000.00")
    assert all(r.amount_due == Decimal("8885.00") for r in rows[:-1])
    assert rows[-1].amount_due == Decimal("8884.00")
    assert rows[0].interest_component == Decimal("1000.00")
    assert rows[-1].closing_balance == Decimal("0.00")
    assert all(r.amount_due == r.principal_component + r.interest_component for r in rows)


def test_installments_are_whole_rupees():
    rows = generate_schedule(Decimal("250000"), Decimal("18.5"), 36, date(2026, 11, 1))

    assert all(_rupees(r.amount_due) for r in rows)
    assert {r.amount_due for r in rows[:-1]} == {Decimal("9101.00")}
    # Interest is the exact figure rounded to the paisa; principal takes the remainder.
    assert rows[0].interest_component == Decimal("3854.17")
    assert rows[0].principal_component == Decimal("5246.83")


def test_balances_chain():
    rows = generate_schedule(Decimal("250000"), Decimal("18.5"), 36, date(2026, 11, 1))

    assert rows[0].opening_balance == Decimal("250000.00")
    for previous, current in pairwise(rows):
        assert current.opening_balance == previous.closing_balance
    for row in rows:
        assert row.closing_balance == row.opening_balance - row.principal_component
        assert all(
            value.as_tuple().exponent == -2
            for value in (row.amount_due, row.principal_component, row.interest_component)
        )


@pytest.mark.parametrize(
    ("principal", "rate", "tenure", "emi", "last"),
    [
        (Decimal("100000"), Decimal("48"), 360, Decimal("4000.00"), Decimal("4001.00")),
        (Decimal("100000"), Decimal("36"), 360, Decimal("3000.00"), Decimal("3026.00")),
        (Decimal("1000"), Decimal("24"), 360, Decimal("20.00"), Decimal("26.00")),
        (Decimal("500000"), Decimal("9.5"), 240, Decimal("4661.00"), None),
    ],
)
def test_rounding_does_not_compound_over_long_tenures(principal, rate, tenure, emi, last):
    rows = generate_schedule(principal, rate, tenure, date(2026, 11, 1))

    assert all(r.amount_due == emi for r in rows[:-1])
    assert sum(r.principal_component for r in rows) == principal
    assert all(r.principal_component >= 0 and r.interest_component >= 0 for r in rows)
    assert all(r.closing_balance >= 0 for r in rows)
    # The last instalment only settles rounding: at most half a rupee per instalment.
    assert abs(rows[-1].amount_due - emi) <= Decimal("0.5") * tenure
    if last is not None:
        assert rows[-1].amount_due == last


def test_high_rate_long_tenure_has_no_balloon():
    for rate in (Decimal("48"), Decimal("36")):
        rows = generate_schedule(Decimal("100000"), rate, 360, date(2026, 11, 1))
        emi = rows[0].amount_due

        assert rows[-1].amount_due < emi + Decimal("50")
        assert rows[-1].principal_component < emi
        # The balance falls every month instead of sitting at the full principal.
        assert rows[180].opening_balance < Decimal("100000")


def test_small_loan_over_long_tenure_is_accepted():
    rows = generate_schedule(Decimal("1000"), Decimal("24"), 360, date(2026, 11, 1))

    assert len(rows) == 360
    assert sum(r.principal_component for r in rows) == Decimal("1000.00")
    assert all(_rupees(r.amount_due) for r in rows)


def test_rounds_up_when_rounding_down_cannot_cover_interest():
    # The exact EMI is 400.40 and the first month's interest 400.40: 400 would not cover it.
    rows = generate_schedule(Decimal("10010"), Decimal("48"), 360, date(2026, 11, 1))

    assert rows[0].amount_due == Decimal("401.00")
    assert all(_rupees(r.amount_due) for r in rows)
    assert all(r.principal_component >= 0 for r in rows)
    assert sum(r.principal_component for r in rows) == Decimal("10010.00")
    assert abs(rows[-1].amount_due - rows[0].amount_due) < 360


def test_falls_back_to_paise_when_whole_rupees_cannot_repay():
    # 1.67 a month rounds to 2, which would repay 10 before the sixth month.
    rows = generate_schedule(Decimal("10"), Decimal("0"), 6, date(2026, 11, 1))

    assert [r.amount_due for r in rows] == [Decimal("1.67")] * 5 + [Decimal("1.65")]
    assert sum(r.principal_component for r in rows) == Decimal("10.00")
    assert calculate_emi(Decimal("10"), Decimal("0"), 6) == Decimal("1.67")


def test_zero_rate_splits_principal():
    rows = generate_schedule(Decimal("1000"), Decimal("0"), 3, date(2026, 11, 1))

    assert [r.amount_due for r in rows] == [Decimal("333.00"), Decimal("333.00"), Decimal("334.00")]
    assert all(r.interest_component == 0 for r in rows)


def test_zero_rate_never_charges_interest_for_rounding():
    rows = generate_schedule(Decimal("1000.40"), Decimal("0"), 3, date(2026, 11, 1))

    assert all(r.interest_component == 0 for r in rows)
    assert sum(r.amount_due for r in rows) == Decimal("1000.40")


def test_single_month_loan():
    (row,) = generate_schedule(Decimal("5000"), Decimal("24"), 1, date(2026, 11, 1))

    assert row.principal_component == Decimal("5000.00")
    assert row.interest_component == Decimal("100.00")
    assert row.amount_due == Decimal("5100.00")


def test_single_month_loan_rounds_to_whole_rupees():
    (row,) = generate_schedule(Decimal("1000"), Decimal("13"), 1, date(2026, 11, 1))

    # Exact interest is 10.83.
    assert row.amount_due == Decimal("1011.00")
    assert row.principal_component == Decimal("1000.00")
    assert row.interest_component == Decimal("11.00")


def test_due_dates_clamp_to_month_end():
    rows = generate_schedule(Decimal("12000"), Decimal("10"), 4, date(2027, 1, 31))

    assert [r.due_date for r in rows] == [
        date(2027, 1, 31),
        date(2027, 2, 28),
        date(2027, 3, 31),
        date(2027, 4, 30),
    ]


@pytest.mark.parametrize(
    ("principal", "rate", "tenure", "error"),
    [
        (Decimal("0"), Decimal("12"), 12, ValueError),
        (Decimal("1000"), Decimal("-1"), 12, ValueError),
        (Decimal("1000"), Decimal("12"), 0, ValueError),
        (Decimal("1000"), Decimal("12"), 361, ValueError),
        (Decimal("0.02"), Decimal("0"), 3, ValueError),
        (Decimal("0.05"), Decimal("12"), 12, ValueError),
        (Decimal("1000"), 12.0, 12, TypeError),
        (1000.0, Decimal("12"), 12, TypeError),
    ],
)
def test_invalid_inputs(principal, rate, tenure, error):
    with pytest.raises(error):
        generate_schedule(principal, rate, tenure, date(2026, 11, 1))
