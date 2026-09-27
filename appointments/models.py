"""Appointment requests and appointments of stage 1 (#5, #7).

Statuses only change through `appointments.services`; nothing else sets
`status` directly. The whole request counts as special-category data (Art. 9
GDPR): the appointment type and the note never go into e-mails or logs.
"""

import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q


class AppointmentType(models.Model):
    """Fixed list of appointment types (#3, decision 2). Deactivated, never deleted."""

    # Internal name for the team, e.g. "TPS-Erstgespräch".
    name = models.CharField(max_length=100, unique=True)
    # Shown in the request form.
    public_name = models.CharField(max_length=100)
    bookable_online = models.BooleanField(default=False)
    default_duration = models.DurationField()
    is_active = models.BooleanField(default=True)
    sort_order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "name"]
        verbose_name = "Terminart"
        verbose_name_plural = "Terminarten"

    def __str__(self):
        return self.name


class Channel(models.TextChoices):
    WEB = "web", "Website"
    PHONE_ASSISTANT = "phone_assistant", "Telefonassistent"
    STAFF = "staff", "Praxisteam"


class Insurance(models.TextChoices):
    STATUTORY = "statutory", "gesetzlich"
    PRIVATE = "private", "privat"
    SELF_PAY = "self_pay", "Selbstzahler"


class RequestStatus(models.TextChoices):
    UNVERIFIED = "unverified", "E-Mail nicht bestätigt"
    OPEN = "open", "offen"
    SCHEDULED = "scheduled", "Termin vergeben"
    DECLINED = "declined", "abgelehnt"
    WITHDRAWN = "withdrawn", "zurückgezogen"
    EXPIRED = "expired", "verfallen"


class AppointmentRequest(models.Model):
    """What the patient entered, as a snapshot (#5, decision 1: no patient record)."""

    Status = RequestStatus
    Channel = Channel
    Insurance = Insurance

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    # Short, random, for phone calls ("Ihre Anfrage A-7K3F9").
    reference = models.CharField(max_length=10, unique=True, editable=False)
    status = models.CharField(max_length=16, choices=RequestStatus)
    channel = models.CharField(max_length=20, choices=Channel)
    # Special-category data.
    appointment_type = models.ForeignKey(
        AppointmentType, on_delete=models.PROTECT, related_name="requests"
    )
    is_existing_patient = models.BooleanField()
    insurance_type = models.CharField(max_length=16, choices=Insurance)
    patient_first_name = models.CharField(max_length=100)
    patient_last_name = models.CharField(max_length=100)
    patient_date_of_birth = models.DateField()
    # Required for the web channel only (constraint below, #14 section 5).
    email = models.EmailField(blank=True)
    phone = models.CharField(max_length=40)
    # Only when requesting for someone else (#5, decision 2).
    contact_name = models.CharField(max_length=200, blank=True)
    contact_relationship = models.CharField(max_length=100, blank=True)
    preferred_resource = models.ForeignKey(
        "practice.Resource",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="preferred_by_requests",
    )
    # May contain health data. Never in e-mails.
    note = models.CharField(max_length=500, blank=True)
    # Internal note of the team (#8). May contain health data.
    staff_note = models.TextField(blank=True)
    email_verified_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    privacy_notice_version = models.CharField(max_length=40)
    delete_after = models.DateTimeField(null=True, blank=True, db_index=True)
    # Set only by staff through `services.assign_patient` (#5 section 4, #26).
    # PROTECT: the deletion of a patient (K8) must deal with its appointments.
    patient = models.ForeignKey(
        "patients.Patient",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="appointment_requests",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["created_at"]
        verbose_name = "Terminanfrage"
        verbose_name_plural = "Terminanfragen"
        constraints = [
            models.CheckConstraint(
                condition=Q(status__in=RequestStatus.values),
                name="appointments_request_status_valid",
            ),
            models.CheckConstraint(
                condition=Q(channel__in=Channel.values),
                name="appointments_request_channel_valid",
            ),
            models.CheckConstraint(
                condition=Q(insurance_type__in=Insurance.values),
                name="appointments_request_insurance_valid",
            ),
            # The web form always has an address; the phone assistant and the
            # team may create requests without one (#14 section 5).
            models.CheckConstraint(
                condition=~Q(channel=Channel.WEB) | ~Q(email=""),
                name="appointments_request_web_needs_email",
            ),
            # Without an address there is nothing to verify.
            models.CheckConstraint(
                condition=~Q(status=RequestStatus.UNVERIFIED) | ~Q(email=""),
                name="appointments_request_unverified_needs_email",
            ),
        ]

    def __str__(self):
        return self.reference

    @property
    def active_appointment(self):
        return self.appointments.filter(status__in=Appointment.ACTIVE).first()


class PartOfDay(models.TextChoices):
    MORNING = "morning", "vormittags"
    AFTERNOON = "afternoon", "nachmittags"
    ANY = "any", "egal"


class RequestedTimeWindow(models.Model):
    """One of one to three preferred days (#5). A table, so demand can be counted (#17)."""

    PartOfDay = PartOfDay

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    request = models.ForeignKey(
        AppointmentRequest, on_delete=models.CASCADE, related_name="time_windows"
    )
    position = models.PositiveSmallIntegerField()
    date = models.DateField()
    part_of_day = models.CharField(max_length=16, choices=PartOfDay)

    class Meta:
        ordering = ["position"]
        verbose_name = "Wunschzeitraum"
        verbose_name_plural = "Wunschzeiträume"
        constraints = [
            models.UniqueConstraint(
                fields=["request", "position"], name="appointments_window_unique_position"
            ),
            models.CheckConstraint(
                condition=Q(position__gte=1, position__lte=3),
                name="appointments_window_position_1_to_3",
            ),
            models.CheckConstraint(
                condition=Q(part_of_day__in=PartOfDay.values),
                name="appointments_window_part_of_day_valid",
            ),
        ]

    def __str__(self):
        return f"{self.date} {self.get_part_of_day_display()}"


class AppointmentStatus(models.TextChoices):
    # FHIR values; fulfilled and noshow come with stage 2.
    PROPOSED = "proposed", "vorgeschlagen"
    BOOKED = "booked", "gebucht"
    CANCELLED = "cancelled", "abgesagt"


class CancelledBy(models.TextChoices):
    PATIENT = "patient", "Patient"
    PRACTICE = "practice", "Praxis"
    SYSTEM = "system", "System"


class CancellationChannel(models.TextChoices):
    LINK = "link", "Link in der E-Mail"
    PHONE = "phone", "Telefon"
    BACKOFFICE = "backoffice", "Backoffice"


class Reason(models.TextChoices):
    """Fixed list for cancellations and declines; free text invites health data (#5, dec. 8)."""

    NO_LONGER_FITS = "no_longer_fits", "Termin passt nicht mehr"
    TREATED_ELSEWHERE = "treated_elsewhere", "anderweitig versorgt"
    PROPOSAL_DECLINED = "proposal_declined", "Vorschlag abgelehnt"
    PROPOSAL_EXPIRED = "proposal_expired", "Frist für den Vorschlag abgelaufen"
    PROPOSAL_WITHDRAWN = "proposal_withdrawn", "Vorschlag von der Praxis zurückgezogen"
    PRACTICE_UNAVAILABLE = "practice_unavailable", "Ärztin/Arzt verhindert"
    PLEASE_CALL = "please_call", "bitte telefonisch melden"
    NOT_BOOKABLE_ONLINE = "not_bookable_online", "nicht online vergebbar"
    OTHER = "other", "anderer Grund"


# What a patient may choose when cancelling via the link.
PATIENT_CANCELLATION_REASONS = [Reason.NO_LONGER_FITS, Reason.TREATED_ELSEWHERE, Reason.OTHER]


class Appointment(models.Model):
    """What the practice gives (#5). A request has at most one active appointment."""

    Status = AppointmentStatus
    CancelledBy = CancelledBy
    CancellationChannel = CancellationChannel
    ACTIVE = [AppointmentStatus.PROPOSED, AppointmentStatus.BOOKED]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    # Appointments without a request come with stage 2 (phone, series).
    request = models.ForeignKey(
        AppointmentRequest,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="appointments",
    )
    # Special-category data.
    appointment_type = models.ForeignKey(
        AppointmentType, on_delete=models.PROTECT, related_name="appointments"
    )
    start = models.DateTimeField()
    end = models.DateTimeField()
    status = models.CharField(max_length=16, choices=AppointmentStatus)
    resources = models.ManyToManyField(
        "practice.Resource", through="AppointmentResource", related_name="appointments"
    )
    proposal_expires_at = models.DateTimeField(null=True, blank=True)
    cancelled_at = models.DateTimeField(null=True, blank=True)
    cancelled_by = models.CharField(max_length=16, choices=CancelledBy, blank=True)
    cancellation_channel = models.CharField(max_length=16, choices=CancellationChannel, blank=True)
    cancellation_reason = models.CharField(max_length=32, choices=Reason, blank=True)
    # Own deletion date, so an appointment may outlive its request in stage 4.
    delete_after = models.DateTimeField(null=True, blank=True, db_index=True)
    # Follows the request (`services.assign_patient`, #26).
    patient = models.ForeignKey(
        "patients.Patient",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="appointments",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["start"]
        verbose_name = "Termin"
        verbose_name_plural = "Termine"
        constraints = [
            models.CheckConstraint(
                condition=Q(status__in=AppointmentStatus.values),
                name="appointments_appointment_status_valid",
            ),
            models.CheckConstraint(
                condition=Q(end__gt=models.F("start")),
                name="appointments_appointment_end_after_start",
            ),
            models.UniqueConstraint(
                fields=["request"],
                condition=Q(status__in=["proposed", "booked"]),
                name="appointments_one_active_appointment_per_request",
            ),
            models.CheckConstraint(
                condition=~Q(status="proposed") | Q(proposal_expires_at__isnull=False),
                name="appointments_proposal_has_deadline",
            ),
            models.CheckConstraint(
                condition=Q(status="cancelled", cancelled_at__isnull=False)
                | Q(~Q(status="cancelled"), cancelled_at__isnull=True),
                name="appointments_cancelled_iff_cancelled_at",
            ),
        ]

    def __str__(self):
        return f"{self.start:%Y-%m-%d %H:%M} {self.status}"


class AppointmentResource(models.Model):
    """Link table; stage 2 adds the time range and the double-booking exclusion (#5)."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    appointment = models.ForeignKey(Appointment, on_delete=models.CASCADE)
    resource = models.ForeignKey("practice.Resource", on_delete=models.PROTECT)

    class Meta:
        verbose_name = "Terminressource"
        verbose_name_plural = "Terminressourcen"
        constraints = [
            models.UniqueConstraint(
                fields=["appointment", "resource"], name="appointments_resource_once"
            ),
        ]

    def __str__(self):
        return f"{self.appointment_id} – {self.resource_id}"


class ActorKind(models.TextChoices):
    PATIENT = "patient", "Patient"
    STAFF = "staff", "Praxisteam"
    SYSTEM = "system", "System"
    ASSISTANT = "assistant", "Telefonassistent"


class AppointmentEvent(models.Model):
    """One status transition of a request or appointment. No free text, no names (#5)."""

    ActorKind = ActorKind

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    request = models.ForeignKey(AppointmentRequest, on_delete=models.CASCADE, related_name="events")
    # Set when the transition is one of the appointment.
    appointment = models.ForeignKey(
        Appointment, on_delete=models.CASCADE, null=True, blank=True, related_name="events"
    )
    at = models.DateTimeField()
    actor_kind = models.CharField(max_length=16, choices=ActorKind)
    actor = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name="+",
    )
    # Empty when the request or appointment is created.
    from_status = models.CharField(max_length=16, blank=True)
    to_status = models.CharField(max_length=16)
    reason = models.CharField(max_length=32, choices=Reason, blank=True)

    class Meta:
        ordering = ["at", "id"]
        verbose_name = "Verlaufseintrag"
        verbose_name_plural = "Verlauf"
        constraints = [
            models.CheckConstraint(
                condition=Q(actor_kind__in=ActorKind.values),
                name="appointments_event_actor_kind_valid",
            ),
            # Staff events name the account, all others must not.
            models.CheckConstraint(
                condition=Q(actor_kind="staff", actor__isnull=False)
                | Q(~Q(actor_kind="staff"), actor__isnull=True),
                name="appointments_event_actor_iff_staff",
            ),
        ]

    def __str__(self):
        return f"{self.at:%Y-%m-%d %H:%M} {self.from_status or '–'} → {self.to_status}"


class TokenPurpose(models.TextChoices):
    VERIFY_EMAIL = "verify_email", "E-Mail bestätigen"
    RESPOND_TO_PROPOSAL = "respond_to_proposal", "Vorschlag annehmen oder ablehnen"
    CANCEL = "cancel", "Termin absagen"
    WITHDRAW = "withdraw", "Anfrage zurückziehen"


class RequestToken(models.Model):
    """A link in an e-mail. Only the SHA-256 of the token is stored (#5).

    Every e-mail gets its own token, and every token works once.
    """

    Purpose = TokenPurpose

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    request = models.ForeignKey(AppointmentRequest, on_delete=models.CASCADE, related_name="tokens")
    appointment = models.ForeignKey(
        Appointment, on_delete=models.CASCADE, null=True, blank=True, related_name="tokens"
    )
    purpose = models.CharField(max_length=24, choices=TokenPurpose)
    token_hash = models.CharField(max_length=64, unique=True)
    expires_at = models.DateTimeField()
    used_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name = "Link-Token"
        verbose_name_plural = "Link-Tokens"
        constraints = [
            models.CheckConstraint(
                condition=Q(purpose__in=TokenPurpose.values),
                name="appointments_token_purpose_valid",
            ),
            models.CheckConstraint(
                condition=Q(purpose__in=["verify_email", "withdraw"])
                | Q(appointment__isnull=False),
                name="appointments_token_appointment_for_appointment_purposes",
            ),
        ]

    def __str__(self):
        return f"{self.purpose} bis {self.expires_at:%Y-%m-%d %H:%M}"
