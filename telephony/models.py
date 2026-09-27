import uuid

from django.db import models
from django.db.models import Q


class CallbackCategory(models.TextChoices):
    """Fixed list of what a callback is about (#14 section 1); there is no free text."""

    PRESCRIPTION = "prescription", "Rezept"
    REFERRAL = "referral", "Überweisung"
    SICK_NOTE = "sick_note", "AU"
    FINDINGS = "findings", "Befund"
    DOCTOR_CALLBACK = "doctor_callback", "Rückruf Ärztin/Arzt"
    CANCEL_OR_MOVE = "cancel_or_move", "Absage/Verschiebung"
    OTHER = "other", "Sonstiges"


class CallbackRequest(models.Model):
    """Someone asked the assistant to be called back (#14 section 5, #45).

    Name, number and a category from the fixed list, nothing the caller said
    beyond that: medication and findings are health data the assistant does
    not take down (#14, decision 8). Only `telephony/services.py` changes it.
    """

    class Status(models.TextChoices):
        OPEN = "open", "offen"
        DONE = "done", "erledigt"
        EXPIRED = "expired", "verfallen"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    created_at = models.DateTimeField(auto_now_add=True)
    name = models.CharField(max_length=200)
    phone = models.CharField(max_length=40)
    category = models.CharField(max_length=20, choices=CallbackCategory)
    # Reference of an appointment request, only for "Absage/Verschiebung";
    # the assistant takes it down and does nothing with it (#14, decision 6).
    reference = models.CharField(max_length=10, blank=True)
    status = models.CharField(max_length=10, choices=Status, default=Status.OPEN)
    # When it was ticked off or expired; who ticked it off is in the access log.
    closed_at = models.DateTimeField(null=True, blank=True)
    delete_after = models.DateTimeField(null=True, blank=True)
    # The practice was told by mail that there is something new (#45).
    notified_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["created_at"]
        verbose_name = "Rückrufbitte"
        verbose_name_plural = "Rückrufbitten"
        constraints = [
            models.CheckConstraint(
                condition=Q(category__in=CallbackCategory.values),
                name="telephony_callback_category_valid",
            ),
            models.CheckConstraint(
                condition=Q(status__in=["open", "done", "expired"]),
                name="telephony_callback_status_valid",
            ),
            models.CheckConstraint(
                condition=Q(reference="") | Q(category="cancel_or_move"),
                name="telephony_callback_reference_only_for_cancel",
            ),
            # Every closed callback has its deletion date, an open one none.
            models.CheckConstraint(
                condition=(
                    Q(status="open", closed_at__isnull=True, delete_after__isnull=True)
                    | Q(
                        status__in=["done", "expired"],
                        closed_at__isnull=False,
                        delete_after__isnull=False,
                    )
                ),
                name="telephony_callback_closed_has_dates",
            ),
        ]

    def __str__(self):
        return f"Rückrufbitte {self.get_category_display()} {self.created_at:%Y-%m-%d %H:%M}"


class CallRecord(models.Model):
    """One call to the assistant, without number and without content (#14 section 6).

    Kept 30 days to see how the assistant works, then counted into
    `reporting.CallStatistic` and deleted. A new field here needs a reason:
    no phone number, no name, no text of the conversation.
    """

    class Mode(models.TextChoices):
        # Derived from `OpeningHours` at the start of the call (#14, decision 1).
        OUTSIDE_HOURS = "outside_hours", "außerhalb der Öffnungszeiten"
        OVERFLOW = "overflow", "Überlauf"

    class Outcome(models.TextChoices):
        INFO = "info", "Auskunft"
        REQUEST_CREATED = "request_created", "Terminanfrage angelegt"
        CALLBACK_REQUESTED = "callback_requested", "Rückrufbitte angelegt"
        HANDED_OFF = "handed_off", "an das Team verwiesen"
        EMERGENCY_HINT = "emergency_hint", "Notfallhinweis"
        ABANDONED = "abandoned", "ohne Anliegen beendet"
        FAILED = "failed", "technischer Fehler"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    started_at = models.DateTimeField()
    duration_seconds = models.PositiveIntegerField()
    mode = models.CharField(max_length=16, choices=Mode)
    outcome = models.CharField(max_length=20, choices=Outcome)
    # Gone with the request or callback; the call stays counted.
    request = models.ForeignKey(
        "appointments.AppointmentRequest",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )
    callback = models.ForeignKey(
        CallbackRequest, on_delete=models.SET_NULL, null=True, blank=True, related_name="+"
    )

    class Meta:
        ordering = ["started_at"]
        verbose_name = "Anruf"
        verbose_name_plural = "Anrufe"
        constraints = [
            models.CheckConstraint(
                condition=Q(mode__in=["outside_hours", "overflow"]),
                name="telephony_callrecord_mode_valid",
            ),
            models.CheckConstraint(
                condition=Q(
                    outcome__in=[
                        "info",
                        "request_created",
                        "callback_requested",
                        "handed_off",
                        "emergency_hint",
                        "abandoned",
                        "failed",
                    ]
                ),
                name="telephony_callrecord_outcome_valid",
            ),
        ]

    def __str__(self):
        return f"Anruf {self.started_at:%Y-%m-%d %H:%M} {self.outcome}"
