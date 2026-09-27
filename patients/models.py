"""Patient master data (#23 sections 4 and 6, K1 in #26).

Patients are created by staff only, never from an appointment request (#5,
decision 1). Master data is changed in place, but every change writes a
`PatientHistory` row, so it stays clear under which name someone was known
when. All changes go through `patients.services`.
"""

import uuid

from django.conf import settings
from django.core.exceptions import FieldDoesNotExist
from django.db import models
from django.db.models import Q
from django.utils import timezone


class Sex(models.TextChoices):
    # FHIR administrative gender; "other" covers "divers" (§ 22 PStG).
    FEMALE = "female", "weiblich"
    MALE = "male", "männlich"
    OTHER = "other", "divers"
    UNKNOWN = "unknown", "ohne Angabe"


class Patient(models.Model):
    """One person treated by the practice. Not documentation in the sense of § 630f BGB."""

    Sex = Sex

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    family_name = models.CharField("Nachname", max_length=100)
    given_name = models.CharField("Vorname", max_length=100)
    birth_name = models.CharField("Geburtsname", max_length=100, blank=True)
    title = models.CharField("Titel", max_length=50, blank=True)
    date_of_birth = models.DateField("Geburtsdatum", db_index=True)
    sex = models.CharField("Geschlecht", max_length=16, choices=Sex, default=Sex.UNKNOWN)
    street = models.CharField("Straße und Hausnummer", max_length=200, blank=True)
    postal_code = models.CharField("PLZ", max_length=10, blank=True)
    city = models.CharField("Ort", max_length=100, blank=True)
    phone = models.CharField("Telefon", max_length=40, blank=True)
    email = models.EmailField("E-Mail", blank=True)
    deceased_on = models.DateField("verstorben am", null=True, blank=True)
    is_active = models.BooleanField("aktiv", default=True)
    # Set by the contacts of the record (K2) through `services.record_contact`.
    last_contact_on = models.DateField(null=True, blank=True, editable=False)
    # End of the year of the last contact + 10 years (§ 630f BGB, #23 3.3).
    # No deletion run yet; that comes with K8 and only after human approval.
    retain_until = models.DateField(null=True, blank=True, editable=False, db_index=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ["family_name", "given_name", "date_of_birth"]
        verbose_name = "Patient"
        verbose_name_plural = "Patienten"
        constraints = [
            models.CheckConstraint(
                condition=Q(sex__in=Sex.values), name="patients_patient_sex_valid"
            ),
        ]

    def __str__(self):
        return f"{self.family_name}, {self.given_name} ({self.date_of_birth:%d.%m.%Y})"

    def current_identifiers(self):
        return self.identifiers.filter(valid_until__isnull=True)


class IdentifierSystem(models.TextChoices):
    MEDICAL_OFFICE = "medical_office", "Patientennummer Medical Office"
    KVNR = "kvnr", "Krankenversichertennummer"


class PatientIdentifier(models.Model):
    """A number another system knows the patient by (#5 section 4).

    Unique per `system`, also once ended, so an old number never points at a
    second person. Ended with `valid_until`, never deleted.
    """

    System = IdentifierSystem

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name="identifiers")
    system = models.CharField("Art", max_length=32, choices=IdentifierSystem)
    value = models.CharField("Nummer", max_length=64)
    valid_from = models.DateField(default=timezone.localdate)
    valid_until = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ["system", "-valid_from"]
        verbose_name = "Kennung"
        verbose_name_plural = "Kennungen"
        constraints = [
            models.CheckConstraint(
                condition=Q(system__in=IdentifierSystem.values),
                name="patients_identifier_system_valid",
            ),
            models.UniqueConstraint(
                fields=["system", "value"], name="patients_identifier_unique_per_system"
            ),
            # One current number per system and patient.
            models.UniqueConstraint(
                fields=["patient", "system"],
                condition=Q(valid_until__isnull=True),
                name="patients_identifier_one_current_per_system",
            ),
            models.CheckConstraint(
                condition=Q(valid_until__isnull=True) | Q(valid_until__gte=models.F("valid_from")),
                name="patients_identifier_until_after_from",
            ),
        ]

    def __str__(self):
        return f"{self.get_system_display()} {self.value}"

    def delete(self, *args, **kwargs):
        raise ValueError("Kennungen werden beendet, nicht gelöscht.")


class PatientHistory(models.Model):
    """One changed field of the master data: old, new, who, when (#23 section 3.1).

    Written by `services` in the same transaction as the change, never
    changed. Deleted only together with the patient.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name="history")
    # A field name of `Patient`, or "identifier:<system>" for numbers.
    field = models.CharField(max_length=50)
    old_value = models.TextField(blank=True)
    new_value = models.TextField(blank=True)
    changed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+"
    )
    changed_at = models.DateTimeField(default=timezone.now, editable=False)

    class Meta:
        ordering = ["-changed_at", "field"]
        verbose_name = "Verlaufseintrag Stammdaten"
        verbose_name_plural = "Verlauf Stammdaten"

    def __str__(self):
        return f"{self.changed_at:%Y-%m-%d %H:%M} {self.field}"

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValueError("Verlaufseinträge werden nie geändert.")
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        raise ValueError("Verlaufseinträge werden nur mit dem Patienten gelöscht.")

    # German labels for the history table; the stored values stay codes.
    @property
    def field_label(self) -> str:
        system = self.field.removeprefix("identifier:")
        if system != self.field:
            label = IdentifierSystem(system).label if system in IdentifierSystem.values else system
            return f"Kennung: {label}"
        try:
            return Patient._meta.get_field(self.field).verbose_name
        except FieldDoesNotExist:
            return self.field

    def _display(self, value: str) -> str:
        if self.field == "sex" and value in Sex.values:
            return Sex(value).label
        return value

    @property
    def old_display(self) -> str:
        return self._display(self.old_value)

    @property
    def new_display(self) -> str:
        return self._display(self.new_value)


def valid_on(day) -> Q:
    """Care team members and consents that count on `day`.

    `valid_until` is the first day without the right: ended today means no
    access from now on, not at midnight (#38).
    """
    return Q(valid_from__lte=day) & (Q(valid_until__isnull=True) | Q(valid_until__gt=day))


def is_on_care_team(user, patient, day=None) -> bool:
    """The one care-team check, for `records/access.py` and the patient page."""
    day = day or timezone.localdate()
    return CareTeamMember.objects.filter(valid_on(day), user=user, patient=patient).exists()


class _ValidFromUntil:
    @property
    def is_in_force(self) -> bool:
        """Counts today, or will count until its end (for the patient page)."""
        return self.valid_until is None or self.valid_until > timezone.localdate()


class CareTeamMember(_ValidFromUntil, models.Model):
    """Someone on the care team of a patient, from/until (#23 section 5.1).

    The record-level checks (`records/access.py`, #38) use it: psychology,
    addiction therapy and nutrition see clinical content only for patients
    whose team they are on (`valid_on`). Ended, not deleted, so it stays
    clear who was allowed when.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name="care_team")
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    valid_from = models.DateField(default=timezone.localdate)
    valid_until = models.DateField(null=True, blank=True)

    class Meta:
        ordering = ["valid_from"]
        verbose_name = "Mitglied im Behandlungsteam"
        verbose_name_plural = "Behandlungsteam"
        constraints = [
            models.UniqueConstraint(
                fields=["patient", "user"],
                condition=Q(valid_until__isnull=True),
                name="patients_care_team_once_current",
            ),
            models.CheckConstraint(
                condition=Q(valid_until__isnull=True) | Q(valid_until__gte=models.F("valid_from")),
                name="patients_care_team_until_after_from",
            ),
        ]

    def __str__(self):
        return f"{self.user_id} für {self.patient_id}"

    def delete(self, *args, **kwargs):
        raise ValueError("Mitglieder des Behandlungsteams werden beendet, nicht gelöscht.")


class ConsentArea(models.TextChoices):
    # The protection levels of `records.Sensitivity` a consent can open; the
    # same values, as `patients` does not know `records` (#23 section 4).
    ADDICTION = "addiction", "Sucht"
    PSYCHOTHERAPY = "psychotherapy", "Psychotherapie"


class ConsentToShare(_ValidFromUntil, models.Model):
    """The patient allows a named person to see a protected area (#23 section 5.2, #38).

    Opens all entries of `area` of this patient to `user` from/until
    (`valid_on`), on top of the care team and the chart right the person
    needs anyway. Ended, not deleted; granting and ending are logged.
    """

    Area = ConsentArea

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    patient = models.ForeignKey(Patient, on_delete=models.CASCADE, related_name="consents")
    area = models.CharField("Bereich", max_length=16, choices=ConsentArea)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+", verbose_name="Person"
    )
    valid_from = models.DateField(default=timezone.localdate)
    valid_until = models.DateField(null=True, blank=True)
    granted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+"
    )
    granted_at = models.DateTimeField(default=timezone.now, editable=False)
    ended_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.PROTECT, null=True, blank=True, related_name="+"
    )
    ended_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["area", "valid_from"]
        verbose_name = "Freigabe"
        verbose_name_plural = "Freigaben"
        constraints = [
            models.CheckConstraint(
                condition=Q(area__in=ConsentArea.values), name="patients_consent_area_valid"
            ),
            models.UniqueConstraint(
                fields=["patient", "area", "user"],
                condition=Q(valid_until__isnull=True),
                name="patients_consent_once_current",
            ),
            models.CheckConstraint(
                condition=Q(valid_until__isnull=True) | Q(valid_until__gte=models.F("valid_from")),
                name="patients_consent_until_after_from",
            ),
        ]

    def __str__(self):
        return f"{self.area} für {self.user_id} bei {self.patient_id}"

    def delete(self, *args, **kwargs):
        raise ValueError("Freigaben werden beendet, nicht gelöscht.")
