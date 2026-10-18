from datetime import date, datetime, time, timedelta

from django.utils import timezone

from .exceptions import ValidationFailed


def business_date(moment: datetime | None = None) -> date:
    """Calendar date in the business timezone (Asia/Kolkata), not UTC."""
    return timezone.localdate(moment)


def day_bounds(day: date) -> tuple[datetime, datetime]:
    """Aware [start, end) datetimes covering `day` in the business timezone."""
    try:
        start = timezone.make_aware(datetime.combine(day, time.min))
        return start, start + timedelta(days=1)
    except OverflowError:
        raise ValidationFailed("Date is out of range.", details={"date": day.isoformat()}) from None
