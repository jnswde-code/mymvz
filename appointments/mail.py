"""E-mails around a request (#7).

`queue` records only the kind and the ids; the text and the link tokens are
made in `send`, when the mail goes out. Today that is right after the commit;
#9 moves `send` into the worker without changing the callers.

What a mail may contain: date, time, address, reference and links. Never the
appointment type, the note, the doctor or the patient's name: the address
may be read by others, and e-mail is not end-to-end encrypted (#3 section 2,
#5 section 6). Mails to the practice say only that something happened.
"""

from functools import partial

from django.conf import settings
from django.core.mail import EmailMessage
from django.db import transaction
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone

from appointments import deadlines, tokens
from appointments.models import Appointment, AppointmentRequest, TokenPurpose
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
    """Send after the transaction commits, so no mail goes out for a rollback."""
    if kind not in SUBJECTS:
        raise ValueError(f"Unbekannte Mail: {kind!r}")
    appointment_id = appointment.pk if appointment is not None else None
    transaction.on_commit(partial(send, kind, request.pk, appointment_id))


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
        }
        if appointment is not None and appointment.proposal_expires_at:
            context["proposal_expires_at"] = timezone.localtime(appointment.proposal_expires_at)
        body = render_to_string(f"appointments/mail/{kind}.txt", context)
    EmailMessage(SUBJECTS[kind], body, to=[recipient]).send()
    return True
