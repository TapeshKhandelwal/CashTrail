"""Reducing-balance EMI schedule. Pure functions: no database access.

Instalments are whole rupees, because cash is counted in notes and coins. The exact
schedule is worked out at high precision first and each row is rounded from it, so the
rounding never feeds back into later interest: the last instalment settles the drift,
which stays within half a rupee per instalment (under a rupee when the EMI is rounded up).
"""

from dataclasses import dataclass
from datetime import date
from decimal import ROUND_CEILING, ROUND_HALF_UP, Decimal, localcontext

from dateutil.relativedelta import relativedelta

from apps.core.money import PAISE, to_money

MAX_TENURE_MONTHS = 360
RUPEE = Decimal("1")
_PRECISION = 40


@dataclass(frozen=True, slots=True)
class ScheduleRow:
    installment_no: int
    due_date: date
    opening_balance: Decimal
    principal_component: Decimal
    interest_component: Decimal
    amount_due: Decimal
    closing_balance: Decimal


@dataclass(frozen=True, slots=True)
class _Line:
    opening_balance: Decimal
    principal_component: Decimal
    interest_component: Decimal
    amount_due: Decimal
    closing_balance: Decimal


def _to_rate(annual_rate: Decimal | int | str) -> Decimal:
    if isinstance(annual_rate, float):
        raise TypeError("Interest rate must not be a float; pass a Decimal or string.")
    return Decimal(str(annual_rate))


def _monthly_rate(annual_rate: Decimal) -> Decimal:
    return annual_rate / Decimal(1200)


def calculate_emi(principal: Decimal, annual_rate: Decimal, tenure_months: int) -> Decimal:
    """The instalment the schedule charges every month but the last.

    `P·r·(1+r)^n / ((1+r)^n - 1)` with `r` the monthly rate (`P / n` when the rate is
    zero), rounded to whole rupees, or to the paisa when whole rupees cannot fit the terms.
    """
    return _amortize(principal, annual_rate, tenure_months)[0].amount_due


def generate_schedule(
    principal: Decimal,
    annual_rate: Decimal,
    tenure_months: int,
    first_due_date: date,
) -> list[ScheduleRow]:
    """Monthly installments; the last one settles the rounding so principal repaid is exact.

    Due dates step from `first_due_date` by calendar month, clamped to month end
    (a 31 Jan start falls due on 28/29 Feb, then 31 Mar).
    """
    return [
        ScheduleRow(
            installment_no=number,
            due_date=first_due_date + relativedelta(months=number - 1),
            opening_balance=line.opening_balance,
            principal_component=line.principal_component,
            interest_component=line.interest_component,
            amount_due=line.amount_due,
            closing_balance=line.closing_balance,
        )
        for number, line in enumerate(_amortize(principal, annual_rate, tenure_months), start=1)
    ]


def _amortize(
    principal: Decimal | int | str, annual_rate: Decimal | int | str, tenure_months: int
) -> list[_Line]:
    principal = to_money(principal)
    annual_rate = _to_rate(annual_rate)
    if principal <= 0:
        raise ValueError("Principal must be positive.")
    if annual_rate < 0:
        raise ValueError("Interest rate cannot be negative.")
    if not 1 <= tenure_months <= MAX_TENURE_MONTHS:
        raise ValueError(f"Tenure must be between 1 and {MAX_TENURE_MONTHS} months.")

    with localcontext() as ctx:
        ctx.prec = _PRECISION
        emi, interests = _exact(principal, _monthly_rate(annual_rate), tenure_months)
        # Nearest rupee; rounded up when rounding down would leave the first month's
        # interest unpaid; to the paisa only when whole rupees cannot repay a tiny loan.
        for unit, rounding in (
            (RUPEE, ROUND_HALF_UP),
            (RUPEE, ROUND_CEILING),
            (PAISE, ROUND_HALF_UP),
        ):
            lines = _rounded(principal, emi, interests, unit, rounding)
            if lines is not None:
                return lines
    raise ValueError("The principal is too small to repay over this many months.")


def _exact(principal: Decimal, rate: Decimal, tenure_months: int) -> tuple[Decimal, list[Decimal]]:
    """The unrounded EMI and each month's interest on the unrounded balance."""
    if rate == 0:
        return principal / tenure_months, [Decimal(0)] * tenure_months
    growth = (1 + rate) ** tenure_months
    emi = principal * rate * growth / (growth - 1)
    interests, balance = [], Decimal(principal)
    for _ in range(tenure_months):
        interest = balance * rate
        interests.append(interest)
        balance -= emi - interest
    return emi, interests


def _rounded(
    principal: Decimal, emi: Decimal, interests: list[Decimal], unit: Decimal, rounding: str
) -> list[_Line] | None:
    """Round the exact schedule to `unit` instalments; `None` when the result is not a valid loan.

    Each interest is the exact one rounded to the paisa, so rounding never compounds.
    """
    installment = emi.quantize(unit, rounding=rounding).quantize(PAISE)
    lines, balance = [], principal
    for number, exact_interest in enumerate(interests, start=1):
        if number < len(interests):
            amount_due = installment
            interest = exact_interest.quantize(PAISE, rounding=ROUND_HALF_UP)
            principal_part = amount_due - interest
        else:
            principal_part = balance
            # Rounded to the nearest unit, but never below the principal it repays.
            amount_due = max(
                (balance + exact_interest).quantize(unit, rounding=ROUND_HALF_UP),
                balance.quantize(unit, rounding=ROUND_CEILING),
            ).quantize(PAISE)
            interest = amount_due - principal_part
        closing = balance - principal_part
        # An interest-free loan never picks up interest from rounding.
        if exact_interest == 0 and interest != 0:
            return None
        if amount_due <= 0 or principal_part < 0 or interest < 0 or closing < 0:
            return None
        lines.append(_Line(balance, principal_part, interest, amount_due, closing))
        balance = closing
    return lines
