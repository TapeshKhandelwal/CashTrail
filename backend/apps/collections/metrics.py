"""Receipt conditions shared by the reconciliation summaries and the dashboards, so the
same figure means the same thing on every screen."""

from datetime import date, datetime, timedelta

from django.db.models import Q

from .models import Collection

CASH = Q(mode=Collection.Mode.CASH)
UPI = Q(mode=Collection.Mode.UPI)
NOT_VOIDED = ~Q(status=Collection.Status.VOIDED)
# Cash still in the agent's hands: recorded but not yet handed over to the branch.
CASH_IN_HAND = CASH & Q(status=Collection.Status.COLLECTED)
# Cash handed over to the branch and waiting for the manager's count.
CASH_AWAITING_REVIEW = CASH & Q(status=Collection.Status.SUBMITTED)

# (key, label, minimum age in days, maximum age in days) of cash in hand.
CASH_AGEING_BUCKETS = (
    ("under_1_day", "Under 1 day", 0, 1),
    ("1_to_2_days", "1 to 2 days", 1, 2),
    ("over_2_days", "Over 2 days", 2, None),
)


def held_between(now: datetime, min_days: int, max_days: int | None) -> Q:
    """Cash in hand collected at least `min_days` and less than `max_days` ago."""
    aged = CASH_IN_HAND
    if min_days:
        aged &= Q(collected_at__lte=now - timedelta(days=min_days))
    if max_days is not None:
        aged &= Q(collected_at__gt=now - timedelta(days=max_days))
    return aged


def settled_between(date_from: date, date_to: date) -> Q:
    """Receipts whose money reached the company account in the period, by bank credit date.

    Counted at full receipt value; what the bank or gateway deducted is tracked on the
    deposit (fees, tax) or as a discrepancy.
    """
    return Q(status=Collection.Status.SETTLED, deposit__settled_on__range=(date_from, date_to))
