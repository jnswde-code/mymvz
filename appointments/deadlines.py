"""Deadlines in Europe/Berlin (#5). Stored in UTC; the risk is the conversion."""

from datetime import UTC, datetime, timedelta

from django.conf import settings
from django.db.models import Max
from django.utils import timezone


def add_working_days(moment: datetime, days: int) -> datetime:
    """Same local clock time `days` working days (Mon–Fri) later.

    Public holidays are not known yet and count as working days.
    """
    local = timezone.localtime(moment)
    day = local.date()
    added = 0
    while added < days:
        day += timedelta(days=1)
        if day.weekday() < 5:
            added += 1
    return timezone.make_aware(datetime.combine(day, local.time().replace(tzinfo=None)))


def working_days_between(first, last) -> int:
    """Working days (Mon–Fri) after `first` up to and including `last`; 0 if none.

    A request from Friday counts 1 on Monday, one from Saturday also 1.
    """
    count = 0
    day = first
    while day < last:
        day += timedelta(days=1)
        if day.weekday() < 5:
            count += 1
    return count


def days_later(moment: datetime, days: int) -> datetime:
    """Same local clock time `days` calendar days later (retention periods).

    Across the change to or from summer time that is 23 or 25 hours more
    than `days` × 24.
    """
    local = timezone.localtime(moment)
    later = local.date() + timedelta(days=days)
    return timezone.make_aware(datetime.combine(later, local.time().replace(tzinfo=None)))


def hours_before(moment: datetime, delta: timedelta) -> datetime:
    """Real elapsed time. Python subtracts wall-clock time within one time zone,
    so the arithmetic runs in UTC."""
    return moment.astimezone(UTC) - delta


def cancellation_deadline(appointment) -> datetime:
    """Until then patients may cancel by link; afterwards by phone (#3 section 2)."""
    return hours_before(appointment.start, settings.APPOINTMENTS_CANCELLATION_NOTICE)


def end_of_last_wish_day(request) -> datetime:
    """Midnight after the last preferred day, local time."""
    last = request.time_windows.aggregate(last=Max("date"))["last"]
    return timezone.make_aware(datetime.combine(last + timedelta(days=1), datetime.min.time()))


def latest_request_date(today):
    return today + timedelta(weeks=settings.APPOINTMENTS_MAX_WEEKS_AHEAD)
