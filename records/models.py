"""The patient record: contacts and chart entries as immutable versions (#23, K2.1 in #37).

Every clinical record consists of versions (#23 section 3.1). Changing means
a new version and the old one set to `superseded`, both in one transaction in
`records.services`; nothing else writes these tables. A PostgreSQL trigger
(migration 0002) refuses any other UPDATE and every DELETE, also against raw
SQL; `save()` on an existing version and `QuerySet.update/delete` raise here.

The records only store and show documentation. Nothing here evaluates
medical content (MDR, #23 section 2).
"""

import uuid

from django.conf import settings
from django.db import models
from django.db.models import Q
from django.utils import timezone


class ImmutableRecordError(Exception):
    """A version was to be changed or deleted in place."""


class Status(models.TextChoices):
    # FHIR values.
    ACTIVE = "active", "aktuell"
    SUPERSEDED = "superseded", "ersetzt"
    ENTERED_IN_ERROR = "entered_in_error", "Irrtum"


class Sensitivity(models.TextChoices):
    # Protection levels (#23 section 5.2); who reads which: `access`.
    NORMAL = "normal", "normal"
    ADDICTION = "addiction", "Sucht"
    PSYCHOTHERAPY = "psychotherapy", "Psychotherapie"
    RESTRICTED = "restricted", "Sperrvermerk"


class Source(models.TextChoices):
    MANUAL = "manual", "eingegeben"
    IMPORT_MEDICAL_OFFICE = "import_medical_office", "aus Medical Office"
    SPEECH_SUMMARY = "speech_summary", "aus der Gesprächsdokumentation"


class ChangeReason(models.TextChoices):
    # Fixed list (#27, open question 4); "other" needs a text.
    TYPO = "typo", "Tippfehler"
    ADDITION = "addition", "Ergänzung"
    CORRECTION = "correction", "inhaltliche Korrektur"
    WRONG_PATIENT = "wrong_patient", "falscher Patient"
    DUPLICATE = "duplicate", "doppelt erfasst"
    OTHER = "other", "Sonstiges"


class VersionedQuerySet(models.QuerySet):
    """Versions are never changed or deleted in bulk either."""

    def update(self, **kwargs):
        raise ImmutableRecordError("Fassungen werden nie geändert, nur ersetzt.")

    def delete(self):
        raise ImmutableRecordError("Fassungen werden nie gelöscht.")

    def current(self):
        """The newest version of each lineage: active or entered in error."""
        return self.exclude(status=Status.SUPERSEDED)

    def _supersede(self) -> int:
        # The one change the trigger allows. Only `services` calls it.
        return super().update(status=Status.SUPERSEDED)


VersionedManager = models.Manager.from_queryset(VersionedQuerySet)


class VersionedRecord(models.Model):
    """Base of every clinical record (#23 section 3.1); K3 to K5 inherit from it.

    `lineage_id` is the same for all versions of one record, and other records
    point at it, not at a version. Each lineage has exactly one head (the
    newest version, `active` or `entered_in_error`); all older ones are
    `superseded`.
    """

    Status = Status
    Sensitivity = Sensitivity
    Source = Source
    ChangeReason = ChangeReason

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    lineage_id = models.UUIDField(default=uuid.uuid4, editable=False, db_index=True)
    version = models.PositiveIntegerField(default=1, editable=False)
    # One-to-one: a version has at most one successor, also in the database.
    replaces = models.OneToOneField(
        "self",
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        editable=False,
        related_name="replaced_by",
    )
    patient = models.ForeignKey(
        "patients.Patient", on_delete=models.PROTECT, related_name="%(class)s_versions"
    )
    status = models.CharField(max_length=16, choices=Status, default=Status.ACTIVE)
    # When and by whom it was stored; set by the system, never changed.
    recorded_at = models.DateTimeField(default=timezone.now, editable=False)
    recorded_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+", editable=False
    )
    # When it happened clinically.
    occurred_at = models.DateTimeField("Zeitpunkt")
    change_reason = models.CharField("Grund", max_length=16, choices=ChangeReason, blank=True)
    change_reason_text = models.CharField("Erläuterung", max_length=200, blank=True)
    # First stored on a later calendar day (Europe/Berlin) than it happened
    # (#27, open question 3).
    is_late_entry = models.BooleanField("Nachtrag", default=False, editable=False)
    sensitivity = models.CharField(
        "Schutzstufe", max_length=16, choices=Sensitivity, default=Sensitivity.NORMAL
    )
    source = models.CharField(max_length=32, choices=Source, default=Source.MANUAL)

    objects = VersionedManager()

    class Meta:
        abstract = True
        ordering = ["lineage_id", "version"]
        constraints = [
            models.UniqueConstraint(
                fields=["lineage_id", "version"], name="%(app_label)s_%(class)s_version_unique"
            ),
            # At most one head per lineage, so at most one active version.
            models.UniqueConstraint(
                fields=["lineage_id"],
                condition=~Q(status="superseded"),
                name="%(app_label)s_%(class)s_one_head",
            ),
            models.CheckConstraint(
                condition=Q(status__in=Status.values), name="%(app_label)s_%(class)s_status_valid"
            ),
            models.CheckConstraint(
                condition=Q(sensitivity__in=Sensitivity.values),
                name="%(app_label)s_%(class)s_sensitivity_valid",
            ),
            models.CheckConstraint(
                condition=Q(source__in=Source.values), name="%(app_label)s_%(class)s_source_valid"
            ),
            models.CheckConstraint(
                condition=Q(version=1, replaces__isnull=True, change_reason="")
                | Q(
                    version__gt=1,
                    replaces__isnull=False,
                    change_reason__in=ChangeReason.values,
                ),
                name="%(app_label)s_%(class)s_reason_from_version_2",
            ),
            models.CheckConstraint(
                condition=~Q(change_reason=ChangeReason.OTHER) | ~Q(change_reason_text=""),
                name="%(app_label)s_%(class)s_other_needs_text",
            ),
        ]

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ImmutableRecordError("Fassungen werden nie geändert, nur ersetzt.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ImmutableRecordError("Fassungen werden nie gelöscht.")

    @property
    def is_current(self) -> bool:
        return self.status != Status.SUPERSEDED

    def versions(self):
        return type(self).objects.filter(lineage_id=self.lineage_id).order_by("version")

    def first_version(self):
        if self.version == 1:
            return self
        return type(self).objects.get(lineage_id=self.lineage_id, version=1)


class EncounterKind(models.TextChoices):
    VISIT = "visit", "Besuch in der Praxis"
    PHONE = "phone", "Telefonat"
    HOME_VISIT = "home_visit", "Hausbesuch"
    VIDEO = "video", "Videosprechstunde"


class Encounter(VersionedRecord):
    """One contact: visit, call, home visit, video consultation (#23 section 1).

    Versioned like the entries (#27, open question 1): a wrong date or kind is
    an ordinary correction.
    """

    Kind = EncounterKind

    kind = models.CharField("Art", max_length=16, choices=EncounterKind)
    # `records` knows `appointments`, not the other way round (#23 section 4).
    # The trigger lets exactly this column go to NULL, for SET NULL.
    appointment = models.ForeignKey(
        "appointments.Appointment",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="+",
    )

    class Meta(VersionedRecord.Meta):
        verbose_name = "Kontakt"
        verbose_name_plural = "Kontakte"
        constraints = [
            *VersionedRecord.Meta.constraints,
            models.CheckConstraint(
                condition=Q(kind__in=EncounterKind.values), name="records_encounter_kind_valid"
            ),
        ]

    def __str__(self):
        return f"{self.get_kind_display()} {self.occurred_at:%Y-%m-%d} v{self.version}"


class ChartEntryType(models.Model):
    """A configurable abbreviation of the chart (#23 section 1, decision 5).

    The codes from migration 0003 are provisional until #19 names the ones
    the practice uses in Medical Office. Types are switched off, not deleted.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    code = models.CharField("Kürzel", max_length=8, unique=True)
    label = models.CharField("Bezeichnung", max_length=100)
    position = models.PositiveSmallIntegerField(default=0)
    is_active = models.BooleanField(default=True)

    class Meta:
        ordering = ["position", "code"]
        verbose_name = "Kürzel"
        verbose_name_plural = "Kürzel"

    def __str__(self):
        return f"{self.code} – {self.label}"


class ChartEntry(VersionedRecord):
    """One entry of the chart, belonging to a contact."""

    # The lineage of the contact, not one of its versions: a corrected
    # contact keeps its entries. `services` checks that it exists and belongs
    # to the same patient.
    encounter_lineage_id = models.UUIDField(db_index=True)
    entry_type = models.ForeignKey(
        ChartEntryType, on_delete=models.PROTECT, related_name="+", verbose_name="Kürzel"
    )
    text = models.TextField("Text")

    class Meta(VersionedRecord.Meta):
        verbose_name = "Eintrag"
        verbose_name_plural = "Einträge"
        # What they mean and the checks per record: `records/access.py`.
        permissions = [
            ("view_entered_in_error", "Als Irrtum markierte Kontakte und Einträge sehen"),
            ("view_all_patients", "Akte aller Patienten sehen, ohne Behandlungsteam"),
            ("view_addiction", "Einträge der Schutzstufe Sucht sehen"),
            ("write_normal", "Einträge der Schutzstufe normal schreiben"),
            ("write_addiction", "Einträge der Schutzstufe Sucht schreiben"),
            ("write_psychotherapy", "Einträge der Schutzstufe Psychotherapie schreiben"),
            ("write_restricted", "Einträge mit Sperrvermerk schreiben"),
        ]

    def __str__(self):
        return f"{self.entry_type_id} {self.occurred_at:%Y-%m-%d} v{self.version}"
