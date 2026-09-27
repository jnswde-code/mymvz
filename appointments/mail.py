"""E-mails around a request (#7).

`queue` records only the kind and the ids in the outbox (`OutgoingMail`), in
the transaction of the transition; the text and the link tokens are made in
`send`, when the worker sends the mail (`process_outbox`, #9). A rollback
leaves no mail behind, and a crash after the commit loses none.

What a mail may contain: date, time, address, reference and links. Never the
appointment type, the note, the doctor or the patient's name: the address
may be read by others, and e-mail is not end-to-end encrypted (#3 section 2,
#5 section 6). Mails to the practice say only that something happened.
"""

import logging
from datetime import timedelta

from django.conf import settings
from django.core.mail import EmailMessage
from django.db import transaction
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone

from appointments import deadlines, tokens
from appointments.models import (
    Appointment,
    AppointmentEvent,
    AppointmentRequest,
    OutgoingMail,
    Reason,
    RequestStatus,
    TokenPurpose,
)
from config.batch import PartialFailure
from practice import info

VERIFY_EMAIL = "verify_email"
RECEIVED = "received"
CONFIRMED = "confirmed"
PROPOSAL = "proposal"
DECLINED = "declined"
CANCELLED_BY_PRACTICE = "cancelled_by_practice"
EXPIRED = "expired"
PRACTICE_NEW_REQUEST = "practice_new_request"
PRACTICE_CANCELLED = "practice_cancelled"

logger = logging.getLogger("appointments.mail")

SUBJECTS = {
    VERIFY_EMAIL: "Bitte bestätigen Sie Ihre Terminanfrage",
    RECEIVED: "Ihre Terminanfrage ist eingegangen",
    CONFIRMED: "Ihr Termin ist bestätigt",
    PROPOSAL: "Terminvorschlag der Praxis",
    DECLINED: "Ihre Terminanfrage",
    CANCELLED_BY_PRACTICE: "Absage Ihres Termins",
    EXPIRED: "Ihre Terminanfrage",
    PRACTICE_NEW_REQUEST: "Neue Terminanfrage",
    PRACTICE_CANCELLED: "Ein Termin wurde abgesagt",
}
TO_PRACTICE = {PRACTICE_NEW_REQUEST, PRACTICE_CANCELLED}


def queue(kind: str, request: AppointmentRequest, appointment: Appointment | None = None):
    """Put the mail into the outbox; it commits or rolls back with the caller."""
    if kind not in SUBJECTS:
        raise ValueError(f"Unbekannte Mail: {kind!r}")
    OutgoingMail.objects.create(
        kind=kind, request=request, appointment=appointment, next_attempt_at=timezone.now()
    )


def retry_delay(attempts: int) -> timedelta:
    """Wait after the n-th failed attempt: 1, 5, 15, 60 minutes, then hourly."""
    steps = settings.APPOINTMENTS_MAIL_RETRY_MINUTES
    return timedelta(minutes=steps[min(attempts, len(steps)) - 1])


def process_outbox(now=None) -> int:
    """Send every mail that is due; the worker calls this on every pass (#9).

    Each mail in its own transaction, locked with SKIP LOCKED, so a second
    worker never picks the same one. A failed mail is tried again after
    `retry_delay`; after `APPOINTMENTS_MAIL_GIVE_UP_AFTER` it is given up and
    the run reports it (`PartialFailure`, only the kind). A crash between the
    SMTP send and the commit sends the mail twice; that is accepted, a lost
    confirmation weighs more.
    """
    now = now or timezone.now()
    sent = 0
    given_up = []
    while True:
        with transaction.atomic():
            row = (
                OutgoingMail.objects.select_for_update(skip_locked=True)
                .filter(sent_at__isnull=True, failed_at__isnull=True, next_attempt_at__lte=now)
                .order_by("next_attempt_at")
                .first()
            )
            if row is None:
                break
            try:
                # Savepoint: the tokens of a mail that did not go out are dropped.
                with transaction.atomic():
                    send(row.kind, row.request_id, row.appointment_id)
            except Exception as exc:  # every error is retried
                row.attempts += 1
                row.last_error = type(exc).__name__[:100]
                give_up_at = row.created_at + settings.APPOINTMENTS_MAIL_GIVE_UP_AFTER
                if now >= give_up_at:
                    row.failed_at = now
                    given_up.append(row.kind)
                else:
                    # The last attempt is exactly at the limit.
                    row.next_attempt_at = min(now + retry_delay(row.attempts), give_up_at)
                # Kind and exception class only, never the recipient.
                logger.warning(
                    "Mail %s nicht versandt (Versuch %d): %s",
                    row.kind,
                    row.attempts,
                    row.last_error,
                )
            else:
                # Also when there was nobody to send it to (`send` returned False).
                row.attempts += 1
                row.sent_at = now
                sent += 1
            row.save()
    if given_up:
        kinds = ", ".join(sorted(set(given_up)))
        raise PartialFailure(sent, len(given_up), f"Mail nicht zugestellt: {kinds}")
    return sent


def link(raw_token: str) -> str:
    return settings.SITE_BASE_URL + reverse("appointments:link", args=[raw_token])


def _links(kind, request, appointment, now) -> dict:
    """Issue the tokens this mail needs; each mail gets its own."""
    if kind == VERIFY_EMAIL:
        expires = request.created_at + settings.APPOINTMENTS_VERIFY_EMAIL_WITHIN
        return {"verify_url": link(tokens.issue(request, TokenPurpose.VERIFY_EMAIL, expires))}
    if kind == RECEIVED:
        expires = deadlines.end_of_last_wish_day(request)
        return {"withdraw_url": link(tokens.issue(request, TokenPurpose.WITHDRAW, expires))}
    if kind == PROPOSAL:
        raw = tokens.issue(
            request, TokenPurpose.RESPOND_TO_PROPOSAL, appointment.proposal_expires_at, appointment
        )
        return {"respond_url": link(raw)}
    if kind == CONFIRMED:
        deadline = deadlines.cancellation_deadline(appointment)
        if deadline <= now:
            return {"cancel_url": None, "deadline": deadline}
        raw = tokens.issue(request, TokenPurpose.CANCEL, deadline, appointment)
        return {"cancel_url": link(raw), "deadline": deadline}
    return {}


def _extra(kind, request) -> dict:
    """What a mail needs besides links: the decline reason, the team's list."""
    if kind == DECLINED:
        event = (
            AppointmentEvent.objects.filter(request=request, to_status=RequestStatus.DECLINED)
            .order_by("-at")
            .first()
        )
        # Only the fixed reason picks the text; nothing the team typed (#3 section 2).
        return {"reason": event.reason if event else Reason.OTHER}
    if kind in TO_PRACTICE:
        # Only the address of the list, never one of a request (#8).
        return {"backoffice_url": settings.SITE_BASE_URL + reverse("appointments_staff:list")}
    return {}


def send(kind: str, request_id, appointment_id=None) -> bool:
    """Render and send one mail; False if there is nobody to send it to."""
    request = AppointmentRequest.objects.filter(pk=request_id).first()
    if request is None:
        # Deleted in the meantime.
        return False
    if kind in TO_PRACTICE:
        recipient = settings.PRACTICE_NOTIFICATION_EMAIL
    elif request.email:
        recipient = request.email
    else:
        # Requests from the phone without an address: the team calls (#14).
        return False
    appointment = Appointment.objects.filter(pk=appointment_id).first() if appointment_id else None
    now = timezone.now()
    with transaction.atomic():
        context = {
            "reference": request.reference,
            "appointment_start": timezone.localtime(appointment.start) if appointment else None,
            "practice": info.practice_info(None)["practice"],
            "privacy_url": settings.SITE_BASE_URL + reverse("appointments:privacy"),
            "cancellation_notice_hours": int(
                settings.APPOINTMENTS_CANCELLATION_NOTICE.total_seconds() // 3600
            ),
            **_links(kind, request, appointment, now),
            **_extra(kind, request),
        }
        if appointment is not None and appointment.proposal_expires_at:
            context["proposal_expires_at"] = timezone.localtime(appointment.proposal_expires_at)
        body = render_to_string(f"appointments/mail/{kind}.txt", context)
    EmailMessage(SUBJECTS[kind], body, to=[recipient]).send()
    return True
