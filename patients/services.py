"""All changes to patient master data, and the searches (#26).

Every change runs in one transaction with its `PatientHistory` rows and its
access log entry. Views, the backoffice (#8) and later voice control (#16)
call these functions; nothing else writes `Patient`, `PatientIdentifier`,
`CareTeamMember`, `ConsentToShare` or `EmergencyAccess`.
Role checks stay in the views; these functions only require a logged-in
account. The one exception is the emergency access, which only doctors may
open whoever calls (#39).
"""

import re
import unicodedata
from datetime import date, datetime
from difflib import SequenceMatcher

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Prefetch, Q
from django.utils import timezone

from audit.log import log_access
from patients.models import (
    EMERGENCY_ACCESS_DURATION,
    CareTeamMember,
    ConsentArea,
    ConsentToShare,
    EmergencyAccess,
    IdentifierSystem,
    Patient,
    PatientHistory,
    running_at,
)
from patients.models import PatientIdentifier as Identifier

# Master data staff may set and change; each change goes into the history.
MASTER_DATA_FIELDS = (
    "family_name",
    "given_name",
    "birth_name",
    "title",
    "date_of_birth",
    "sex",
    "street",
    "postal_code",
    "city",
    "phone",
    "email",
    "deceased_on",
    "is_active",
)

RETENTION_YEARS = 10
SEARCH_LIMIT = 50
# Share of matching letters from which two names count as similar
# ("Meier"/"Meyer" is 0.8).
SIMILAR_NAME_RATIO = 0.8
# Below this length a name inside another one proves nothing ("Li" in "Müller-Linde").
MIN_CONTAINED_LENGTH = 4

# Letter, nine digits; the last digit is a check digit we do not verify yet.
KVNR_PATTERN = re.compile(r"[A-Z][0-9]{9}")
# Name search splits on spaces and commas ("Muster, Erika").
NAME_SEPARATORS = re.compile(r"[\s,]+")


def name_terms(name: str) -> list[str]:
    return [t for t in NAME_SEPARATORS.split(name) if t]


def _require_staff(actor):
    if not getattr(actor, "is_authenticated", False):
        raise ValueError("Stammdaten ändern nur angemeldete Konten.")


def _as_text(value) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "ja" if value else "nein"
    if isinstance(value, date):
        return value.isoformat()
    return str(value)


def _only_master_data(data: dict) -> dict:
    unknown = set(data) - set(MASTER_DATA_FIELDS)
    if unknown:
        raise ValueError(f"Keine Stammdaten: {sorted(unknown)}")
    return data


# --- Retention ---------------------------------------------------------------


def compute_retain_until(last_contact: date) -> date:
    """End of the year of the last contact plus ten years (§ 630f BGB, #23 3.3)."""
    return date(last_contact.year + RETENTION_YEARS, 12, 31)


@transaction.atomic
def record_contact(patient: Patient, when: date | datetime) -> Patient:
    """Note a contact and move `retain_until` (called by the record, K2).

    An aware datetime counts on its day in Europe/Berlin. An earlier contact
    never shortens the retention period.
    """
    day = timezone.localdate(when) if isinstance(when, datetime) else when
    patient = Patient.objects.select_for_update().get(pk=patient.pk)
    if patient.last_contact_on is None or day > patient.last_contact_on:
        patient.last_contact_on = day
        patient.retain_until = compute_retain_until(day)
        patient.save(update_fields=["last_contact_on", "retain_until", "updated_at"])
    return patient


# --- Master data -------------------------------------------------------------


@transaction.atomic
def create_patient(data: dict, *, actor) -> Patient:
    """Create a patient. Only staff, never from a request (#5, decision 1).

    The duplicate check (`find_duplicates`) runs before, and a human decides.
    """
    _require_staff(actor)
    patient = Patient(**_only_master_data(data))
    patient.full_clean()
    patient.save()
    log_access(actor, "create", patient, patient_id=patient.pk)
    return patient


@transaction.atomic
def update_patient(patient: Patient, data: dict, *, actor) -> list[str]:
    """Change master data; one history row per changed field. Returns the changed fields."""
    _require_staff(actor)
    patient = Patient.objects.select_for_update().get(pk=patient.pk)
    return _change(patient, _only_master_data(data), actor=actor)


def _change(patient: Patient, data: dict, *, actor) -> list[str]:
    """Set fields of a locked patient, with one history row per changed field and a log entry."""
    now = timezone.now()
    changed = []
    for field, new in data.items():
        old = getattr(patient, field)
        if old == new:
            continue
        setattr(patient, field, new)
        changed.append((field, old, new))
    if not changed:
        return []
    patient.full_clean()
    patient.save()
    PatientHistory.objects.bulk_create(
        PatientHistory(
            patient=patient,
            field=field,
            old_value=_as_text(old),
            new_value=_as_text(new),
            changed_by=actor,
            changed_at=now,
        )
        for field, old, new in changed
    )
    log_access(actor, "update", patient, patient_id=patient.pk)
    return [field for field, _, _ in changed]


# --- Restriction and staff as patients (#39) ---------------------------------


@transaction.atomic
def set_restriction(patient: Patient, *, actor) -> Patient:
    """Set the restriction; from now on only released persons see the patient."""
    _require_staff(actor)
    patient = Patient.objects.select_for_update().get(pk=patient.pk)
    if patient.is_restricted:
        raise ValidationError("Der Sperrvermerk ist schon gesetzt.")
    _change(patient, {"is_restricted": True}, actor=actor)
    return patient


@transaction.atomic
def lift_restriction(patient: Patient, *, actor) -> Patient:
    """Lift the restriction (doctors only, checked by the view); history and log keep who."""
    _require_staff(actor)
    patient = Patient.objects.select_for_update().get(pk=patient.pk)
    if not patient.is_restricted:
        raise ValidationError("Es gibt keinen Sperrvermerk.")
    _change(patient, {"is_restricted": False}, actor=actor)
    return patient


@transaction.atomic
def link_account(patient: Patient, user, *, actor) -> Patient:
    """Link a staff account to the patient; this sets the restriction too (#23 decision 8)."""
    _require_staff(actor)
    patient = Patient.objects.select_for_update().get(pk=patient.pk)
    if patient.user_id is not None:
        raise ValidationError("Der Patient ist schon mit einem Konto verknüpft.")
    if Patient.objects.filter(user=user).exists():
        raise ValidationError({"user": "Dieses Konto ist schon mit einem Patienten verknüpft."})
    try:
        # A parallel link of the same account to another patient only the
        # unique constraint sees.
        with transaction.atomic():
            _change(patient, {"user": user, "is_restricted": True}, actor=actor)
    except IntegrityError:
        raise ValidationError(
            {"user": "Dieses Konto ist schon mit einem Patienten verknüpft."}
        ) from None
    return patient


@transaction.atomic
def unlink_account(patient: Patient, *, actor) -> Patient:
    """Remove a wrong link. The restriction stays; lifting it is a decision of its own."""
    _require_staff(actor)
    patient = Patient.objects.select_for_update().get(pk=patient.pk)
    if patient.user_id is None:
        raise ValidationError("Der Patient ist mit keinem Konto verknüpft.")
    _change(patient, {"user": None}, actor=actor)
    return patient


EMERGENCY_PERMISSION = "patients.add_emergencyaccess"


@transaction.atomic
def open_emergency_access(patient: Patient, *, reason: str, actor) -> EmergencyAccess:
    """Open the restriction of this patient to a doctor for 60 minutes (#27 question 5, #39).

    The reason is required and kept only in `EmergencyAccess`; the log gets
    an entry `emergency_access` without it. While one runs, it is not
    opened again, so every hour of access has its own reason.
    """
    _require_staff(actor)
    if not (actor.is_active and actor.has_perm(EMERGENCY_PERMISSION)):
        raise PermissionDenied
    reason = reason.strip()
    if not reason:
        raise ValidationError({"reason": "Bitte den Grund für den Notfallzugriff angeben."})
    # Lock the patient so a double click does not open two accesses.
    patient = Patient.objects.select_for_update().get(pk=patient.pk)
    now = timezone.now()
    running = EmergencyAccess.objects.filter(running_at(now), patient=patient, user=actor).first()
    if running is not None:
        until = timezone.localtime(running.valid_until)
        raise ValidationError(f"Ein Notfallzugriff gilt schon bis {until:%H:%M} Uhr.")
    emergency = EmergencyAccess(
        patient=patient,
        user=actor,
        reason=reason,
        valid_from=now,
        valid_until=now + EMERGENCY_ACCESS_DURATION,
    )
    emergency.full_clean()
    emergency.save()
    log_access(actor, "emergency_access", emergency, patient_id=patient.pk)
    return emergency


# --- Identifiers -------------------------------------------------------------


def normalize_identifier(system: str, value: str) -> str:
    value = value.strip()
    if system == IdentifierSystem.KVNR:
        value = value.replace(" ", "").upper()
        if not KVNR_PATTERN.fullmatch(value):
            raise ValidationError(
                {"value": "Die Krankenversichertennummer hat einen Buchstaben und neun Ziffern."}
            )
    if not value:
        raise ValidationError({"value": "Bitte eine Nummer angeben."})
    return value


@transaction.atomic
def add_identifier(patient: Patient, system: str, value: str, *, actor) -> Identifier:
    """Add a number. A current number of the same system must be ended first."""
    _require_staff(actor)
    if system not in IdentifierSystem.values:
        raise ValidationError({"system": "Unbekannte Art der Kennung."})
    value = normalize_identifier(system, value)
    patient = Patient.objects.select_for_update().get(pk=patient.pk)
    if patient.current_identifiers().filter(system=system).exists():
        raise ValidationError({"system": "Es gibt schon eine gültige Nummer dieser Art."})
    if Identifier.objects.filter(system=system, value=value).exists():
        raise ValidationError({"value": "Diese Nummer ist schon vergeben."})
    try:
        # The checks above cannot see a parallel insert for another patient;
        # the constraints can.
        with transaction.atomic():
            identifier = Identifier.objects.create(patient=patient, system=system, value=value)
    except IntegrityError:
        raise ValidationError({"value": "Diese Nummer ist schon vergeben."}) from None
    PatientHistory.objects.create(
        patient=patient, field=f"identifier:{system}", new_value=value, changed_by=actor
    )
    log_access(actor, "update", patient, patient_id=patient.pk)
    return identifier


@transaction.atomic
def end_identifier(identifier: Identifier, *, actor, on: date | None = None) -> Identifier:
    """End a number with `valid_until` (default today). It stays on record."""
    _require_staff(actor)
    identifier = Identifier.objects.select_for_update().get(pk=identifier.pk)
    if identifier.valid_until is not None:
        raise ValidationError("Diese Kennung ist schon beendet.")
    on = on or timezone.localdate()
    if on < identifier.valid_from:
        raise ValidationError("Das Ende liegt vor dem Beginn.")
    identifier.valid_until = on
    identifier.save(update_fields=["valid_until"])
    PatientHistory.objects.create(
        patient_id=identifier.patient_id,
        field=f"identifier:{identifier.system}",
        old_value=identifier.value,
        changed_by=actor,
    )
    log_access(actor, "update", identifier.patient, patient_id=identifier.patient_id)
    return identifier


# --- Care team ---------------------------------------------------------------


@transaction.atomic
def add_care_team_member(patient: Patient, user, *, actor) -> CareTeamMember:
    _require_staff(actor)
    if not user.is_active:
        raise ValidationError("Deaktivierte Konten gehören zu keinem Behandlungsteam.")
    # Lock the patient so two parallel adds of the same account wait for each other.
    patient = Patient.objects.select_for_update().get(pk=patient.pk)
    today = timezone.localdate()
    # Memberships start the day they are added, so any not ended yet overlaps.
    if CareTeamMember.objects.filter(
        Q(valid_until__isnull=True) | Q(valid_until__gt=today), patient=patient, user=user
    ).exists():
        raise ValidationError("Das Konto gehört schon zum Behandlungsteam.")
    member = CareTeamMember.objects.create(patient=patient, user=user)
    log_access(actor, "update", patient, patient_id=patient.pk)
    return member


@transaction.atomic
def end_care_team_member(member: CareTeamMember, *, actor, on: date | None = None):
    """End a membership; `on` is the first day without access (default today)."""
    _require_staff(actor)
    member = CareTeamMember.objects.select_for_update().get(pk=member.pk)
    if not member.is_in_force:
        raise ValidationError("Die Mitgliedschaft ist schon beendet.")
    on = on or timezone.localdate()
    if on < member.valid_from:
        raise ValidationError("Das Ende liegt vor dem Beginn.")
    member.valid_until = on
    member.save(update_fields=["valid_until"])
    log_access(actor, "update", member.patient, patient_id=member.patient_id)
    return member


# --- Consents ----------------------------------------------------------------

# The one right a named person needs besides the consent; `records/access.py`
# checks it, and the care team, again on every read.
CHART_PERMISSION = "records.view_chartentry"
# A release of the restriction opens the master data first; the chart only
# for those who have it anyway (#39).
PATIENT_PERMISSION = "patients.view_patient"


def consent_permission(area: str) -> str:
    return PATIENT_PERMISSION if area == ConsentArea.RESTRICTED else CHART_PERMISSION


@transaction.atomic
def grant_consent(
    patient: Patient, user, area: str, *, actor, valid_until: date | None = None
) -> ConsentToShare:
    """Record that the patient opens a protected area to a named person (#38), from today.

    Nobody records a consent for themselves, so a single account cannot open
    a protected area to itself.
    """
    _require_staff(actor)
    if area not in ConsentArea.values:
        raise ValidationError({"area": "Unbekannter Bereich."})
    if user.pk == actor.pk:
        raise ValidationError({"user": "Eine Freigabe für sich selbst ist nicht möglich."})
    if not user.is_active or not user.has_perm(consent_permission(area)):
        raise ValidationError({"user": "Dieses Konto hat keinen Zugang zu diesem Bereich."})
    today = timezone.localdate()
    if valid_until is not None and valid_until <= today:
        raise ValidationError({"valid_until": "Das Ende muss nach heute liegen."})
    # Lock the patient so two parallel grants of the same area wait for each other.
    patient = Patient.objects.select_for_update().get(pk=patient.pk)
    # Every consent starts on the day it is granted, so any that has not
    # ended yet overlaps the new one.
    if ConsentToShare.objects.filter(
        Q(valid_until__isnull=True) | Q(valid_until__gt=today),
        patient=patient,
        area=area,
        user=user,
    ).exists():
        raise ValidationError("Für diese Person und diesen Bereich gilt schon eine Freigabe.")
    consent = ConsentToShare.objects.create(
        patient=patient,
        area=area,
        user=user,
        valid_from=today,
        valid_until=valid_until,
        granted_by=actor,
    )
    log_access(actor, "create", consent, patient_id=patient.pk)
    return consent


@transaction.atomic
def end_consent(consent: ConsentToShare, *, actor) -> ConsentToShare:
    """End a consent today; from now on it opens nothing. It stays on record."""
    _require_staff(actor)
    consent = ConsentToShare.objects.select_for_update().get(pk=consent.pk)
    today = timezone.localdate()
    if consent.ended_at is not None or not consent.is_in_force:
        raise ValidationError("Die Freigabe ist schon beendet.")
    consent.valid_until = max(today, consent.valid_from)
    consent.ended_by = actor
    consent.ended_at = timezone.now()
    consent.save(update_fields=["valid_until", "ended_by", "ended_at"])
    log_access(actor, "update", consent, patient_id=consent.patient_id)
    return consent


# --- Duplicates and search ---------------------------------------------------

_UMLAUTS = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"})


def normalize_name(name: str) -> str:
    """Lower case, umlauts spelled out, accents, spaces and hyphens dropped."""
    # NFC first, so a decomposed "ü" (pasted from macOS) also becomes "ue".
    name = unicodedata.normalize("NFC", name).casefold().translate(_UMLAUTS)
    name = unicodedata.normalize("NFKD", name)
    return "".join(c for c in name if c.isalpha())


def names_similar(a: str, b: str) -> bool:
    a, b = normalize_name(a), normalize_name(b)
    if not a or not b:
        return False
    if a == b:
        return True
    shorter, longer = sorted((a, b), key=len)
    if len(shorter) >= MIN_CONTAINED_LENGTH and shorter in longer:
        return True
    return SequenceMatcher(None, a, b).ratio() >= SIMILAR_NAME_RATIO


def find_duplicates(
    *, given_name: str, family_name: str, date_of_birth: date, birth_name: str = "", exclude=None
) -> list[Patient]:
    """Patients with the same date of birth and a similar name (#23 section 4).

    Only a hint; a human decides. Family and birth names are compared crosswise
    (name after marriage), given names on their own.
    """
    new_family = [n for n in (family_name, birth_name) if n]
    candidates = Patient.objects.filter(date_of_birth=date_of_birth)
    if exclude is not None:
        candidates = candidates.exclude(pk=exclude.pk)
    hits = []
    for patient in candidates:
        old_family = [n for n in (patient.family_name, patient.birth_name) if n]
        if names_similar(given_name, patient.given_name) or any(
            names_similar(a, b) for a in new_family for b in old_family
        ):
            hits.append(patient)
    return hits


def search_patients(
    *, actor, name: str = "", date_of_birth: date | None = None, identifier: str = ""
) -> list[Patient]:
    """Search by name parts, date of birth and number; all given criteria must match.

    Writes one access log entry with the number of hits, never the search terms.
    Ended numbers are found too: a letter may carry an old one.
    """
    _require_staff(actor)
    terms = name_terms(name)
    identifier = identifier.strip()
    if not terms and date_of_birth is None and not identifier:
        raise ValueError("Suche ohne Suchbegriff.")
    patients = Patient.objects.all()
    for term in terms:
        patients = patients.filter(
            Q(family_name__icontains=term)
            | Q(given_name__icontains=term)
            | Q(birth_name__icontains=term)
        )
    if date_of_birth is not None:
        patients = patients.filter(date_of_birth=date_of_birth)
    if identifier:
        compact = identifier.replace(" ", "")
        patients = patients.filter(
            Q(identifiers__value__iexact=identifier) | Q(identifiers__value__iexact=compact)
        ).distinct()
    current = Identifier.objects.filter(valid_until__isnull=True)
    patients = patients.prefetch_related(
        Prefetch("identifiers", queryset=current, to_attr="current_identifier_list")
    )
    hits = list(patients[:SEARCH_LIMIT])
    log_access(actor, "search", Patient, result_count=len(hits))
    return hits
