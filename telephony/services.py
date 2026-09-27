"""Every change to callbacks and call records (#45).

The internal API (for the voice agent), the pages for the team and the
worker call these functions; nothing else writes `CallbackRequest` or
`CallRecord`. Steps of the practice take the acting account and write the
access log; the role is checked by the view before.

Deadlines in days are calendar days in Europe/Berlin (`days_later`, #5).
"""

import re
from datetime import datetime, timedelta

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from appointments.deadlines import days_later
from appointments.forms import phone_validator
from appointments.models import AppointmentRequest, Channel
from audit.log import log_access
from config import batch
from practice.models import OpeningHours
from reporting.models import CallStatistic
from telephony import mail
from telephony.models import CallbackCategory, CallbackRequest, CallRecord

# Retention (#14 section 6): an open callback expires after 14 days, a closed
# one is deleted 7 days later, a call record is counted and deleted after 30.
CALLBACK_EXPIRES_AFTER_DAYS = 14
CALLBACK_KEEP_DAYS = 7
CALL_RECORD_KEEP_DAYS = 30

# The assistant hands over after 8 minutes (#14 section 7); anything far
# beyond that is a broken clock, not a call.
MAX_CALL_SECONDS = 2 * 60 * 60
# Clocks of web and voice may differ a little.
CLOCK_SKEW = timedelta(minutes=5)

# Stronger outcomes win: an emergency hint is what the call was, whatever
# else happened in it (#14 section 3.1).
OUTCOME_PRIORITY = [
    CallRecord.Outcome.EMERGENCY_HINT,
    CallRecord.Outcome.HANDED_OFF,
    CallRecord.Outcome.REQUEST_CREATED,
    CallRecord.Outcome.CALLBACK_REQUESTED,
    CallRecord.Outcome.FAILED,
    CallRecord.Outcome.INFO,
    CallRecord.Outcome.ABANDONED,
]

# The reference of a request as `appointments.services` makes it.
REFERENCE = re.compile(r"A-[2-9A-HJKMNP-Z]{5}")

Status = CallbackRequest.Status


class NotOpen(Exception):
    """The callback was ticked off or deleted meanwhile."""


def _require_staff(actor):
    if not getattr(actor, "is_authenticated", False):
        raise ValueError("Schritte der Praxis brauchen ein angemeldetes Konto.")


def _passed(moment: datetime, days: int, now: datetime) -> bool:
    return days_later(moment, days) <= now


def _candidates_before(now: datetime, days: int) -> datetime:
    """Every moment whose deadline of `days` calendar days has passed lies before this.

    A day across the change of summer time has 25 hours, so one hour more
    than `days` × 24; each candidate is checked with `days_later` again.
    """
    return now - timedelta(days=days) + timedelta(hours=1)


# --- Callbacks from the phone ------------------------------------------------


def create_callback(*, name: str, phone: str, category: str, reference: str = ""):
    """A new callback, open, not yet announced to the practice.

    The reference of a request is only taken for "Absage/Verschiebung"; it
    is taken down, not looked up, so the assistant never learns whether it
    exists (#14, decision 6).
    """
    errors = {}
    name = name.strip()
    phone = phone.strip()
    reference = reference.strip().upper()
    if not name:
        errors["name"] = "Fehlt."
    try:
        phone_validator(phone)
    except ValidationError:
        errors["phone"] = "Bitte eine Telefonnummer mit Ziffern."
    if category not in CallbackCategory.values:
        errors["category"] = f"Bitte eins von {', '.join(CallbackCategory.values)}."
    elif reference and category != CallbackCategory.CANCEL_OR_MOVE:
        errors["reference"] = "Eine Kennung nur bei Absage oder Verschiebung."
    if reference and not REFERENCE.fullmatch(reference):
        errors["reference"] = "Eine Kennung sieht aus wie A-7K3F9."
    if errors:
        raise ValidationError(errors)
    return CallbackRequest.objects.create(
        name=name, phone=phone, category=category, reference=reference
    )


# --- For the team ------------------------------------------------------------


def list_callbacks(actor) -> list:
    """Open and expired callbacks, oldest first; one `list` entry in the access log.

    Expired ones stay visible until they are deleted, so nobody wonders
    where they went (#14 section 6).
    """
    _require_staff(actor)
    callbacks = list(
        CallbackRequest.objects.filter(status__in=[Status.OPEN, Status.EXPIRED]).order_by(
            "created_at"
        )
    )
    log_access(actor, "list", CallbackRequest, result_count=len(callbacks))
    return callbacks


@transaction.atomic
def mark_done(pk, *, actor) -> CallbackRequest:
    """The team called back. Also after it expired: late is better than never."""
    _require_staff(actor)
    callback = CallbackRequest.objects.select_for_update().filter(pk=pk).first()
    if callback is None or callback.status == Status.DONE:
        raise NotOpen
    now = timezone.now()
    callback.status = Status.DONE
    callback.closed_at = now
    callback.delete_after = days_later(now, CALLBACK_KEEP_DAYS)
    callback.save(update_fields=["status", "closed_at", "delete_after"])
    log_access(actor, "update", callback)
    return callback


# --- Runs of the system (called by the worker, #9) ---------------------------


def notify_new_callbacks(now=None) -> int:
    """One mail to the practice for all callbacks not yet announced.

    Called by the worker. If the mail fails, nothing is marked and the next
    pass tries again.
    """
    now = now or timezone.now()
    with transaction.atomic():
        pending = list(
            CallbackRequest.objects.select_for_update(skip_locked=True)
            .filter(status=Status.OPEN, notified_at__isnull=True)
            .values_list("pk", flat=True)
        )
        if not pending:
            return 0
        mail.send_new_callbacks()
        CallbackRequest.objects.filter(pk__in=pending).update(notified_at=now)
    return len(pending)


def expire_overdue_callbacks(now=None) -> int:
    """Open callbacks older than 14 days expire and stay in the list for 7 more."""
    now = now or timezone.now()
    due = CallbackRequest.objects.filter(
        status=Status.OPEN,
        created_at__lte=_candidates_before(now, CALLBACK_EXPIRES_AFTER_DAYS),
    )

    @transaction.atomic
    def expire(pk) -> bool:
        callback = CallbackRequest.objects.select_for_update().filter(pk=pk).first()
        if callback is None or callback.status != Status.OPEN:
            return False
        if not _passed(callback.created_at, CALLBACK_EXPIRES_AFTER_DAYS, now):
            return False
        callback.status = Status.EXPIRED
        callback.closed_at = now
        callback.delete_after = days_later(now, CALLBACK_KEEP_DAYS)
        callback.save(update_fields=["status", "closed_at", "delete_after"])
        return True

    return batch.each(list(due.values_list("pk", flat=True)), expire)


def delete_closed_callbacks(now=None) -> int:
    """Done or expired callbacks whose `delete_after` has come."""
    now = now or timezone.now()
    deleted, _ = CallbackRequest.objects.filter(delete_after__lte=now).delete()
    return deleted


# --- Call records ------------------------------------------------------------


def call_mode(started_at: datetime) -> str:
    """Outside the opening hours or overflow, from `OpeningHours` at the start of the call."""
    local = timezone.localtime(started_at)
    open_now = OpeningHours.objects.filter(
        kind=OpeningHours.Kind.OPENING,
        weekday=local.weekday(),
        opens__lte=local.time(),
        closes__gt=local.time(),
    ).exists()
    return CallRecord.Mode.OVERFLOW if open_now else CallRecord.Mode.OUTSIDE_HOURS


def final_outcome(outcomes) -> str:
    """The strongest of what happened in a call; nothing at all is `abandoned`."""
    for outcome in OUTCOME_PRIORITY:
        if outcome in outcomes:
            return outcome
    return CallRecord.Outcome.ABANDONED


def record_call(
    *,
    started_at: datetime,
    duration_seconds: int,
    outcomes,
    request_reference: str = "",
    callback_id=None,
    now=None,
) -> CallRecord:
    """Store one call as the agent reports it at its end (#45)."""
    now = now or timezone.now()
    errors = {}
    if timezone.is_naive(started_at):
        errors["started_at"] = "Bitte mit Zeitzone."
    elif not now - timedelta(days=1) <= started_at <= now + CLOCK_SKEW:
        errors["started_at"] = "Der Anruf muss in den letzten 24 Stunden begonnen haben."
    if not 0 <= duration_seconds <= MAX_CALL_SECONDS:
        errors["duration_seconds"] = f"Bitte 0 bis {MAX_CALL_SECONDS} Sekunden."
    unknown = set(outcomes) - set(CallRecord.Outcome.values)
    if unknown:
        errors["outcomes"] = f"Unbekannt: {', '.join(sorted(unknown))}."
    request = None
    if request_reference:
        # Only requests of the assistant; the agent knows no other references.
        request = AppointmentRequest.objects.filter(
            reference=request_reference, channel=Channel.PHONE_ASSISTANT
        ).first()
        if request is None:
            errors["request_reference"] = "Keine Anfrage vom Telefon mit dieser Kennung."
    callback = None
    if callback_id is not None:
        callback = CallbackRequest.objects.filter(pk=callback_id).first()
        if callback is None:
            errors["callback_id"] = "Keine Rückrufbitte mit dieser ID."
    if errors:
        raise ValidationError(errors)
    return CallRecord.objects.create(
        started_at=started_at,
        duration_seconds=duration_seconds,
        mode=call_mode(started_at),
        outcome=final_outcome(outcomes),
        request=request,
        callback=callback,
    )


def week_of(moment: datetime):
    """Monday of the calendar week in Europe/Berlin."""
    day = timezone.localdate(moment)
    return day - timedelta(days=day.weekday())


def count_and_delete_call_records(now=None) -> int:
    """Call records older than 30 days go into `CallStatistic` and are deleted.

    Counting and deleting happen in one transaction per record, so a call is
    never counted twice or lost.
    """
    now = now or timezone.now()
    due = CallRecord.objects.filter(started_at__lte=_candidates_before(now, CALL_RECORD_KEEP_DAYS))

    @transaction.atomic
    def count(pk) -> bool:
        record = CallRecord.objects.select_for_update().filter(pk=pk).first()
        if record is None or not _passed(record.started_at, CALL_RECORD_KEEP_DAYS, now):
            return False
        row, _ = CallStatistic.objects.get_or_create(
            week=week_of(record.started_at), mode=record.mode, outcome=record.outcome
        )
        CallStatistic.objects.filter(pk=row.pk).update(count=F("count") + 1)
        record.delete()
        return True

    return batch.each(list(due.values_list("pk", flat=True)), count)
