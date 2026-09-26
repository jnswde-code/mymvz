"""The only place where requests and appointments change status (#5 section 3).

Every transition locks the row, checks the starting status, writes an
`AppointmentEvent`, sets `delete_after` and queues its e-mails. The web form,
the backoffice (#8), the phone assistant (#14) and voice control (#16) all
go through these functions, so checks and deadlines live in one place.

Functions for the team take the acting account and write the access log.
Functions for patients take the raw token from the link.
"""

import secrets
from datetime import UTC

from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import Max
from django.utils import timezone

from appointments import mail, tokens
from appointments.deadlines import add_working_days, days_later, latest_request_date
from appointments.models import (
    PATIENT_CANCELLATION_REASONS,
    Appointment,
    AppointmentEvent,
    AppointmentRequest,
    AppointmentResource,
    AppointmentType,
    Channel,
    PartOfDay,
    Reason,
    RequestedTimeWindow,
    TokenPurpose,
)
from audit.log import log_access
from practice.models import OpeningHours, Resource

ActorKind = AppointmentEvent.ActorKind
Status = AppointmentRequest.Status
AStatus = Appointment.Status

MAX_TIME_WINDOWS = 3
MAX_AGE_YEARS = 130

# Who acts for each channel when a request is created.
_CREATOR = {
    Channel.WEB: ActorKind.PATIENT,
    Channel.PHONE_ASSISTANT: ActorKind.ASSISTANT,
    Channel.STAFF: ActorKind.STAFF,
}


class TransitionNotAllowed(Exception):
    """The record is not in a status that allows this step."""


class LinkInvalid(Exception):
    """Unknown, used, expired or no longer applicable link.

    `problem` is one of `tokens.Problem` or "outdated" (the request or
    appointment has moved on, e.g. the practice cancelled first).
    """

    def __init__(self, problem, token=None):
        super().__init__(problem)
        self.problem = problem
        self.token = token


OUTDATED = "outdated"


# --- Deadlines ---------------------------------------------------------------


def compute_delete_after(request: AppointmentRequest):
    """When the request and its appointments are deleted (#5 section 6).

    unverified: 24 h after creation. declined, withdrawn, expired: 30 days
    after closing. scheduled: 30 days after the end of the booked
    appointment, or after the cancellation if the last one was cancelled.
    open, and scheduled with a pending proposal: none, the request ends via
    `expired` or the proposal via its deadline.
    """
    retention = settings.APPOINTMENTS_RETENTION_DAYS
    if request.status == Status.UNVERIFIED:
        return request.created_at.astimezone(UTC) + settings.APPOINTMENTS_VERIFY_EMAIL_WITHIN
    if request.status in (Status.DECLINED, Status.WITHDRAWN, Status.EXPIRED):
        return days_later(request.closed_at, retention)
    if request.status == Status.SCHEDULED:
        latest = request.appointments.order_by("-created_at").first()
        if latest is None or latest.status == AStatus.PROPOSED:
            return None
        if latest.status == AStatus.BOOKED:
            return days_later(latest.end, retention)
        return days_later(latest.cancelled_at, retention)
    return None


def _set_delete_after(request: AppointmentRequest) -> None:
    request.delete_after = compute_delete_after(request)
    request.save()
    # In stage 1 appointments go together with their request (#5 section 6).
    request.appointments.update(delete_after=request.delete_after)


# --- Checks ------------------------------------------------------------------


def validate_time_window(day, part_of_day, *, today=None) -> None:
    """One preferred day: from tomorrow, at most N weeks ahead, with consultation.

    Shared by the form and the phone assistant (#14, `check_time_window`).
    """
    today = today or timezone.localdate()
    if part_of_day not in PartOfDay.values:
        raise ValidationError("Bitte wählen Sie vormittags, nachmittags oder egal.")
    if day <= today:
        raise ValidationError("Bitte wählen Sie einen Tag ab morgen.")
    if day > latest_request_date(today):
        raise ValidationError(
            f"Anfragen sind höchstens {settings.APPOINTMENTS_MAX_WEEKS_AHEAD} Wochen "
            "im Voraus möglich."
        )
    if not OpeningHours.objects.covers(day, part_of_day):
        if part_of_day == PartOfDay.ANY:
            raise ValidationError("An diesem Tag ist keine Sprechstunde.")
        raise ValidationError(
            f"An diesem Tag ist {PartOfDay(part_of_day).label} keine Sprechstunde."
        )


def _validate_request(data: dict, channel: str, today) -> None:
    errors = {}
    appointment_type = data["appointment_type"]
    if not appointment_type.is_active or (
        channel != Channel.STAFF and not appointment_type.bookable_online
    ):
        errors["appointment_type"] = "Diese Terminart kann nicht online angefragt werden."

    resource = data.get("preferred_resource")
    if resource is not None and not (resource.is_active and resource.kind == Resource.Kind.DOCTOR):
        errors["preferred_resource"] = "Bitte wählen Sie eine Ärztin oder einen Arzt aus der Liste."

    born = data["patient_date_of_birth"]
    if born > today:
        errors["patient_date_of_birth"] = "Das Geburtsdatum liegt in der Zukunft."
    elif born.year < today.year - MAX_AGE_YEARS:
        errors["patient_date_of_birth"] = "Bitte prüfen Sie das Geburtsdatum."

    if channel == Channel.WEB and not data.get("email"):
        errors["email"] = "Bitte geben Sie Ihre E-Mail-Adresse an."
    if bool(data.get("contact_name")) != bool(data.get("contact_relationship")):
        errors["contact_name"] = (
            "Bitte geben Sie Ihren Namen und Ihre Beziehung zur Patientin bzw. zum Patienten an."
        )
    # No free text on the phone: the assistant would note what it does not
    # understand (#14 section 5).
    if channel == Channel.PHONE_ASSISTANT and data.get("note"):
        errors["note"] = "Am Telefon wird keine Notiz aufgenommen."

    windows = data["time_windows"]
    if not 1 <= len(windows) <= MAX_TIME_WINDOWS:
        errors["time_windows"] = "Bitte geben Sie einen bis drei Wunschtermine an."
    seen = set()
    for position, (day, part) in enumerate(windows[:MAX_TIME_WINDOWS], start=1):
        try:
            validate_time_window(day, part, today=today)
        except ValidationError as error:
            errors[f"window_{position}"] = error.messages
            continue
        if (day, part) in seen:
            errors[f"window_{position}"] = "Diesen Wunschtermin haben Sie schon angegeben."
        seen.add((day, part))
    if errors:
        raise ValidationError(errors)


# --- Helpers -----------------------------------------------------------------


def _lock(request: AppointmentRequest) -> AppointmentRequest:
    return AppointmentRequest.objects.select_for_update().get(pk=request.pk)


def _lock_appointment(appointment: Appointment) -> Appointment:
    return Appointment.objects.select_for_update().get(pk=appointment.pk)


def _require(current, *allowed):
    if current not in allowed:
        raise TransitionNotAllowed(f"Nicht erlaubt im Zustand {current!r}.")


def _event(
    request,
    to_status,
    actor_kind,
    *,
    from_status="",
    appointment=None,
    actor=None,
    reason="",
    now=None,
):
    AppointmentEvent.objects.create(
        request=request,
        appointment=appointment,
        at=now or timezone.now(),
        actor_kind=actor_kind,
        actor=actor if actor_kind == ActorKind.STAFF else None,
        from_status=from_status,
        to_status=to_status,
        reason=reason,
    )


def _move(request, to_status, actor_kind, *, actor=None, reason="", now=None):
    from_status = request.status
    request.status = to_status
    if to_status in (Status.DECLINED, Status.WITHDRAWN, Status.EXPIRED):
        request.closed_at = now or timezone.now()
    _event(
        request, to_status, actor_kind, from_status=from_status, actor=actor, reason=reason, now=now
    )


def _require_staff(actor):
    if not getattr(actor, "is_authenticated", False):
        raise ValueError("Schritte der Praxis brauchen ein angemeldetes Konto.")


def _new_reference() -> str:
    # No 0/O, 1/I/L: read out on the phone (#14).
    alphabet = "23456789ABCDEFGHJKMNPQRSTUVWXYZ"
    while True:
        reference = "A-" + "".join(secrets.choice(alphabet) for _ in range(5))
        if not AppointmentRequest.objects.filter(reference=reference).exists():
            return reference


def _entered_open(request, *, notify_practice=True):
    """Everything that follows once a request is visible to the practice."""
    if request.email:
        mail.queue(mail.RECEIVED, request)
    if notify_practice:
        mail.queue(mail.PRACTICE_NEW_REQUEST, request)


# --- Creating a request ------------------------------------------------------


@transaction.atomic
def submit_request(data: dict, *, channel=Channel.WEB, actor=None) -> AppointmentRequest:
    """Check and store a request from the form, the phone assistant or the team.

    `data` holds the model fields plus `time_windows`, a list of
    `(date, part_of_day)`. Raises `ValidationError` with a dict of field
    errors (`window_1` … `window_3` for the preferred days).

    Web requests start `unverified`; the others too if they have an e-mail
    address, else `open` (#14 section 5). Requests entered by the team
    start `open`.
    """
    if channel not in Channel.values:
        raise ValueError(f"Unbekannter Kanal: {channel!r}")
    if channel == Channel.STAFF:
        _require_staff(actor)
    now = timezone.now()
    _validate_request(data, channel, timezone.localdate(now))

    fields = {k: v for k, v in data.items() if k != "time_windows"}
    fields.setdefault("privacy_notice_version", settings.APPOINTMENTS_PRIVACY_NOTICE_VERSION)
    verify = channel != Channel.STAFF and bool(fields.get("email"))
    request = AppointmentRequest.objects.create(
        reference=_new_reference(),
        channel=channel,
        status=Status.UNVERIFIED if verify else Status.OPEN,
        **fields,
    )
    RequestedTimeWindow.objects.bulk_create(
        RequestedTimeWindow(request=request, position=i, date=day, part_of_day=part)
        for i, (day, part) in enumerate(data["time_windows"], start=1)
    )
    _event(request, request.status, _CREATOR[channel], actor=actor, now=now)
    _set_delete_after(request)
    if channel == Channel.STAFF:
        log_access(actor, "create", request)
    if verify:
        mail.queue(mail.VERIFY_EMAIL, request)
    else:
        _entered_open(request, notify_practice=channel != Channel.STAFF)
    return request


# --- Links for patients ------------------------------------------------------


def _applicable(token) -> bool:
    """Whether what the link does is still possible."""
    request, appointment = token.request, token.appointment
    match token.purpose:
        case TokenPurpose.VERIFY_EMAIL:
            return request.status == Status.UNVERIFIED
        case TokenPurpose.WITHDRAW:
            return request.status == Status.OPEN
        case TokenPurpose.RESPOND_TO_PROPOSAL:
            return appointment.status == AStatus.PROPOSED
        case TokenPurpose.CANCEL:
            return appointment.status == AStatus.BOOKED
    return False


def check_link(raw: str, now=None) -> tokens.Lookup:
    """For showing the page behind a link; changes nothing."""
    found = tokens.look_up(raw, now=now)
    if found.ok and not _applicable(found.token):
        return tokens.Lookup(found.token, OUTDATED)
    return found


def _redeem(raw: str, purpose: str):
    """Lock and use up the token; call inside a transaction."""
    found = tokens.look_up(raw, lock=True)
    if not found.ok:
        raise LinkInvalid(found.problem, found.token)
    if found.token.purpose != purpose:
        raise LinkInvalid(tokens.Problem.UNKNOWN)
    token = found.token
    # Lock the records before checking their status again.
    token.request = _lock(token.request)
    if token.appointment is not None:
        token.appointment = _lock_appointment(token.appointment)
    if not _applicable(token):
        raise LinkInvalid(OUTDATED, token)
    tokens.mark_used(token)
    return token


@transaction.atomic
def verify_email(raw: str) -> AppointmentRequest:
    """unverified → open: only now does the practice see the request."""
    token = _redeem(raw, TokenPurpose.VERIFY_EMAIL)
    request = token.request
    request.email_verified_at = timezone.now()
    _move(request, Status.OPEN, ActorKind.PATIENT)
    _set_delete_after(request)
    _entered_open(request)
    return request


@transaction.atomic
def withdraw_request(raw: str) -> AppointmentRequest:
    """open → withdrawn, by the patient."""
    token = _redeem(raw, TokenPurpose.WITHDRAW)
    request = token.request
    _move(request, Status.WITHDRAWN, ActorKind.PATIENT)
    _set_delete_after(request)
    return request


@transaction.atomic
def accept_proposal(raw: str) -> Appointment:
    """Proposed appointment → booked, by the patient."""
    token = _redeem(raw, TokenPurpose.RESPOND_TO_PROPOSAL)
    appointment = token.appointment
    appointment.status = AStatus.BOOKED
    appointment.proposal_expires_at = None
    appointment.save()
    _event(
        token.request,
        AStatus.BOOKED,
        ActorKind.PATIENT,
        from_status=AStatus.PROPOSED,
        appointment=appointment,
    )
    _set_delete_after(token.request)
    mail.queue(mail.CONFIRMED, token.request, appointment)
    return appointment


@transaction.atomic
def decline_proposal(raw: str) -> Appointment:
    """Proposed appointment → cancelled, request back to open."""
    token = _redeem(raw, TokenPurpose.RESPOND_TO_PROPOSAL)
    _cancel(
        token.appointment,
        token.request,
        cancelled_by=Appointment.CancelledBy.PATIENT,
        channel=Appointment.CancellationChannel.LINK,
        actor_kind=ActorKind.PATIENT,
        reason=Reason.PROPOSAL_DECLINED,
        reopen=True,
    )
    return token.appointment


@transaction.atomic
def cancel_by_patient(raw: str, reason: str = "") -> Appointment:
    """Booked appointment → cancelled by link, until the cancellation deadline."""
    if reason and reason not in PATIENT_CANCELLATION_REASONS:
        raise ValidationError({"reason": "Bitte wählen Sie einen Grund aus der Liste."})
    token = _redeem(raw, TokenPurpose.CANCEL)
    _cancel(
        token.appointment,
        token.request,
        cancelled_by=Appointment.CancelledBy.PATIENT,
        channel=Appointment.CancellationChannel.LINK,
        actor_kind=ActorKind.PATIENT,
        reason=reason,
    )
    mail.queue(mail.PRACTICE_CANCELLED, token.request)
    return token.appointment


# --- Steps of the practice (views in #8) ------------------------------------


def _new_appointment(request, start, end, resources, status, now):
    if start <= now:
        raise ValidationError({"start": "Der Termin muss in der Zukunft liegen."})
    end = end or start + request.appointment_type.default_duration
    if end <= start:
        raise ValidationError({"end": "Das Ende muss nach dem Beginn liegen."})
    appointment = Appointment.objects.create(
        request=request,
        patient=request.patient,
        appointment_type=request.appointment_type,
        start=start,
        end=end,
        status=status,
        proposal_expires_at=(
            min(add_working_days(now, settings.APPOINTMENTS_PROPOSAL_WORKING_DAYS), start)
            if status == AStatus.PROPOSED
            else None
        ),
    )
    AppointmentResource.objects.bulk_create(
        AppointmentResource(appointment=appointment, resource=r) for r in resources
    )
    return appointment


def _schedule(request, start, *, actor, end, resources, status):
    _require_staff(actor)
    now = timezone.now()
    request = _lock(request)
    _require(request.status, Status.OPEN)
    appointment = _new_appointment(request, start, end, resources, status, now)
    _move(request, Status.SCHEDULED, ActorKind.STAFF, actor=actor, now=now)
    _event(request, status, ActorKind.STAFF, appointment=appointment, actor=actor, now=now)
    _set_delete_after(request)
    log_access(actor, "update", request)
    return request, appointment


@transaction.atomic
def confirm_request(request, start, *, actor, end=None, resources=()) -> Appointment:
    """open → scheduled with a booked appointment (the preferred time fits)."""
    request, appointment = _schedule(
        request, start, actor=actor, end=end, resources=resources, status=AStatus.BOOKED
    )
    mail.queue(mail.CONFIRMED, request, appointment)
    return appointment


@transaction.atomic
def propose_appointment(request, start, *, actor, end=None, resources=()) -> Appointment:
    """open → scheduled with a proposal the patient has to accept (#5, decision 4)."""
    request, appointment = _schedule(
        request, start, actor=actor, end=end, resources=resources, status=AStatus.PROPOSED
    )
    mail.queue(mail.PROPOSAL, request, appointment)
    return appointment


@transaction.atomic
def decline_request(request, *, actor, reason=Reason.PLEASE_CALL) -> AppointmentRequest:
    """open → declined, with the text "please call us"."""
    _require_staff(actor)
    if reason not in (Reason.PLEASE_CALL, Reason.NOT_BOOKABLE_ONLINE, Reason.OTHER):
        raise ValidationError({"reason": "Unbekannter Grund."})
    request = _lock(request)
    _require(request.status, Status.OPEN)
    _move(request, Status.DECLINED, ActorKind.STAFF, actor=actor, reason=reason)
    _set_delete_after(request)
    log_access(actor, "update", request)
    mail.queue(mail.DECLINED, request)
    return request


def _cancel(
    appointment,
    request,
    *,
    cancelled_by,
    channel,
    actor_kind,
    actor=None,
    reason="",
    reopen=False,
    now=None,
):
    """Cancel an active appointment; a cancelled proposal always reopens the request."""
    now = now or timezone.now()
    from_status = appointment.status
    _require(from_status, *Appointment.ACTIVE)
    appointment.status = AStatus.CANCELLED
    appointment.cancelled_at = now
    appointment.cancelled_by = cancelled_by
    appointment.cancellation_channel = channel
    appointment.cancellation_reason = reason
    appointment.save()
    _event(
        request,
        AStatus.CANCELLED,
        actor_kind,
        from_status=from_status,
        appointment=appointment,
        actor=actor,
        reason=reason,
        now=now,
    )
    if (reopen or from_status == AStatus.PROPOSED) and request.status == Status.SCHEDULED:
        _move(request, Status.OPEN, actor_kind, actor=actor, reason=reason, now=now)
    _set_delete_after(request)


@transaction.atomic
def cancel_appointment(
    appointment,
    *,
    actor,
    reason=Reason.PRACTICE_UNAVAILABLE,
    cancelled_by=Appointment.CancelledBy.PRACTICE,
    channel=Appointment.CancellationChannel.BACKOFFICE,
    reopen=False,
) -> Appointment:
    """The team cancels: for the practice, or for a patient who called (#5 section 3).

    `reopen` puts the request back to open to offer another date right away.
    Withdrawing a proposal always reopens it. The patient gets an e-mail
    when the practice cancels a booked appointment.
    """
    _require_staff(actor)
    if cancelled_by == Appointment.CancelledBy.SYSTEM:
        raise ValueError("Absagen durch das System laufen über expire_overdue_proposals.")
    appointment = _lock_appointment(appointment)
    request = _lock(appointment.request)
    from_status = appointment.status
    if from_status == AStatus.PROPOSED and not reason:
        reason = Reason.PROPOSAL_WITHDRAWN
    _cancel(
        appointment,
        request,
        cancelled_by=cancelled_by,
        channel=channel,
        actor_kind=ActorKind.STAFF,
        actor=actor,
        reason=reason,
        reopen=reopen,
    )
    log_access(actor, "update", request)
    if cancelled_by == Appointment.CancelledBy.PRACTICE and from_status == AStatus.BOOKED:
        mail.queue(mail.CANCELLED_BY_PRACTICE, request, appointment)
    return appointment


# --- Runs of the system (called by the worker, #9) ---------------------------


def expire_overdue_proposals(now=None) -> int:
    """Proposals past their deadline are cancelled; the request is open again."""
    now = now or timezone.now()
    count = 0
    due = Appointment.objects.filter(status=AStatus.PROPOSED, proposal_expires_at__lte=now)
    for appointment_id in due.values_list("pk", flat=True):
        with transaction.atomic():
            appointment = Appointment.objects.select_for_update().get(pk=appointment_id)
            if appointment.status != AStatus.PROPOSED or appointment.proposal_expires_at > now:
                continue
            request = _lock(appointment.request)
            _cancel(
                appointment,
                request,
                cancelled_by=Appointment.CancelledBy.SYSTEM,
                channel="",
                actor_kind=ActorKind.SYSTEM,
                reason=Reason.PROPOSAL_EXPIRED,
                now=now,
            )
            count += 1
    return count


def expire_overdue_requests(now=None) -> int:
    """Open requests whose preferred days are all over expire (#5, decision 5)."""
    now = now or timezone.now()
    today = timezone.localdate(now)
    due = (
        AppointmentRequest.objects.filter(status=Status.OPEN)
        .annotate(last_day=Max("time_windows__date"))
        .filter(last_day__lt=today)
    )
    count = 0
    for request_id in due.values_list("pk", flat=True):
        with transaction.atomic():
            request = AppointmentRequest.objects.select_for_update().get(pk=request_id)
            if request.status != Status.OPEN:
                continue
            _move(request, Status.EXPIRED, ActorKind.SYSTEM, now=now)
            _set_delete_after(request)
            mail.queue(mail.EXPIRED, request)
            count += 1
    return count


# --- Patients --------------------------------------------------------------


@transaction.atomic
def assign_patient(request, patient, *, actor) -> AppointmentRequest:
    """Link a request and its appointments to a patient, or unlink with None.

    Always a decision of a human (#5 section 4): no function matches requests
    to patients on its own. The snapshot in the request stays and is deleted
    on its own schedule.
    """
    _require_staff(actor)
    request = _lock(request)
    previous = request.patient_id
    request.patient = patient
    request.save(update_fields=["patient", "updated_at"])
    request.appointments.update(patient=patient, updated_at=timezone.now())
    patient_id = patient.pk if patient is not None else previous
    log_access(actor, "update", request, patient_id=patient_id)
    return request


def active_types():
    """Appointment types patients may request online, in form order."""
    return AppointmentType.objects.filter(is_active=True, bookable_online=True)


def doctors():
    return Resource.objects.filter(is_active=True, kind=Resource.Kind.DOCTOR)
