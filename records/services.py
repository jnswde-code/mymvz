"""All writes to the record (#23 section 3.1, #37).

Every change is a new version in one transaction: the active version is
locked (`select_for_update`), set to `superseded`, and its successor stored,
together with the access log entry. Two parallel corrections of the same
version therefore wait for each other, and the second one fails because its
base is no longer current. Unlike `patients.services`, these functions check
the rights themselves through `records.access`, so no caller can write past
them.
"""

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.utils import timezone

from audit.log import log_access
from patients.services import record_contact
from records import access
from records.models import (
    ChangeReason,
    ChartEntry,
    ChartEntryType,
    Encounter,
    Sensitivity,
    Status,
    VersionedRecord,
)

# Fields every version of a lineage shares; a wrong patient is an error, not
# a correction.
_KEPT = {
    Encounter: ("patient_id", "sensitivity", "source", "appointment_id"),
    ChartEntry: ("patient_id", "sensitivity", "source", "encounter_lineage_id"),
}
# Content that a correction may change, per model.
_CONTENT = {
    Encounter: ("kind", "occurred_at"),
    ChartEntry: ("entry_type_id", "text", "occurred_at"),
}


def is_late(occurred_at, first_recorded_at) -> bool:
    """A late entry: first stored on a later calendar day in Europe/Berlin (#27, question 3)."""
    return timezone.localdate(first_recorded_at) > timezone.localdate(occurred_at)


def _clinical_time(occurred_at, now):
    """The clinical time to the minute, as the form shows and sends it; not in the future."""
    occurred_at = occurred_at.replace(second=0, microsecond=0)
    if occurred_at > now:
        raise ValidationError({"occurred_at": "Der Zeitpunkt liegt in der Zukunft."})
    return occurred_at


def _check_sensitivity(actor, sensitivity):
    if sensitivity not in access.writable_sensitivities(actor):
        raise ValidationError({"sensitivity": "Diese Schutzstufe ist für Sie nicht wählbar."})


def _check_reason(change_reason, change_reason_text):
    if change_reason not in ChangeReason.values:
        raise ValidationError({"change_reason": "Bitte einen Grund wählen."})
    if change_reason == ChangeReason.OTHER and not change_reason_text.strip():
        raise ValidationError({"change_reason_text": "Bei „Sonstiges“ bitte kurz erläutern."})


def _lock_head(record: VersionedRecord, based_on_version: int | None):
    """Lock the active version of the lineage; it must be the one the user saw."""
    model = type(record)
    head = (
        model.objects.select_for_update()
        .filter(lineage_id=record.lineage_id, status=Status.ACTIVE)
        .first()
    )
    expected = record.version if based_on_version is None else based_on_version
    if head is None or head.version != expected:
        raise ValidationError(
            "Das wurde inzwischen geändert oder als Irrtum markiert. "
            "Bitte die aktuelle Fassung ansehen und neu beginnen."
        )
    return head


def _lock_and_check(actor, record: VersionedRecord, based_on_version: int | None):
    """Lock the head, then check the right on it (a stale `record` says nothing)."""
    if not access.can_write(actor, record.patient):
        raise PermissionDenied
    head = _lock_head(record, based_on_version)
    if not access.can_change(actor, head):
        raise PermissionDenied
    return head


def _successor(head: VersionedRecord, *, actor, now, status, reason, reason_text, content):
    """Store the next version of `head` and supersede `head`."""
    model = type(head)
    successor = model(
        lineage_id=head.lineage_id,
        version=head.version + 1,
        replaces=head,
        status=status,
        recorded_at=now,
        recorded_by=actor,
        change_reason=reason,
        change_reason_text=reason_text.strip(),
        **{field: getattr(head, field) for field in _KEPT[model]},
        **{field: getattr(head, field) for field in _CONTENT[model]},
    )
    for field, value in content.items():
        setattr(successor, field, value)
    successor.is_late_entry = is_late(successor.occurred_at, head.first_version().recorded_at)
    # Supersede first: the database allows only one head per lineage.
    model.objects.filter(pk=head.pk)._supersede()
    successor.full_clean()
    successor.save()
    return successor


# --- Encounters --------------------------------------------------------------


@transaction.atomic
def create_encounter(patient, *, kind, occurred_at, actor, appointment=None) -> Encounter:
    if not access.can_write(actor, patient):
        raise PermissionDenied
    if appointment is not None and appointment.patient_id != patient.pk:
        raise ValidationError({"appointment": "Der Termin gehört zu einem anderen Patienten."})
    now = timezone.now()
    occurred_at = _clinical_time(occurred_at, now)
    encounter = Encounter(
        patient=patient,
        kind=kind,
        occurred_at=occurred_at,
        appointment=appointment,
        recorded_at=now,
        recorded_by=actor,
        is_late_entry=is_late(occurred_at, now),
    )
    encounter.full_clean()
    encounter.save()
    record_contact(patient, occurred_at)
    log_access(actor, "create", encounter, patient_id=patient.pk)
    return encounter


@transaction.atomic
def revise_encounter(
    encounter: Encounter,
    *,
    kind,
    occurred_at,
    change_reason,
    change_reason_text="",
    actor,
    based_on_version=None,
) -> Encounter:
    _check_reason(change_reason, change_reason_text)
    head = _lock_and_check(actor, encounter, based_on_version)
    now = timezone.now()
    occurred_at = _clinical_time(occurred_at, now)
    if (kind, occurred_at) == (head.kind, head.occurred_at):
        raise ValidationError("Keine Änderung.")
    successor = _successor(
        head,
        actor=actor,
        now=now,
        status=Status.ACTIVE,
        reason=change_reason,
        reason_text=change_reason_text,
        content={"kind": kind, "occurred_at": occurred_at},
    )
    # A later date moves the retention period; an earlier one never shortens it.
    record_contact(head.patient, occurred_at)
    log_access(actor, "update", successor, patient_id=successor.patient_id)
    return successor


# --- Chart entries -----------------------------------------------------------


@transaction.atomic
def create_entry(
    encounter: Encounter,
    *,
    entry_type: ChartEntryType,
    text,
    actor,
    occurred_at=None,
    sensitivity=None,
) -> ChartEntry:
    """A new entry for a contact; its time defaults to that of the contact.

    Without `sensitivity` it gets the default of the author's role
    (`access.writable_sensitivities`), so psychology writes psychotherapy.
    """
    if not access.can_write(actor, encounter.patient) or not access.can_view(actor, encounter):
        raise PermissionDenied
    if sensitivity is None:
        sensitivity = next(iter(access.writable_sensitivities(actor)), Sensitivity.NORMAL)
    _check_sensitivity(actor, sensitivity)
    # Lock the contact, so it cannot be marked as error in between. If it was
    # corrected meanwhile, the first query finds nothing once the lock is
    # released; the second one sees the new version.
    active = Encounter.objects.select_for_update().filter(
        lineage_id=encounter.lineage_id, status=Status.ACTIVE
    )
    encounter = active.first() or active.first()
    if encounter is None:
        raise ValidationError("Dieser Kontakt ist als Irrtum markiert.")
    if not entry_type.is_active:
        raise ValidationError({"entry_type": "Dieses Kürzel wird nicht mehr verwendet."})
    now = timezone.now()
    occurred_at = occurred_at or encounter.occurred_at
    occurred_at = _clinical_time(occurred_at, now)
    entry = ChartEntry(
        patient_id=encounter.patient_id,
        encounter_lineage_id=encounter.lineage_id,
        entry_type=entry_type,
        text=text,
        occurred_at=occurred_at,
        sensitivity=sensitivity,
        recorded_at=now,
        recorded_by=actor,
        is_late_entry=is_late(occurred_at, now),
    )
    entry.full_clean()
    entry.save()
    log_access(actor, "create", entry, patient_id=entry.patient_id)
    return entry


@transaction.atomic
def revise_entry(
    entry: ChartEntry,
    *,
    entry_type: ChartEntryType,
    text,
    occurred_at,
    change_reason,
    change_reason_text="",
    actor,
    based_on_version=None,
) -> ChartEntry:
    _check_reason(change_reason, change_reason_text)
    head = _lock_and_check(actor, entry, based_on_version)
    now = timezone.now()
    occurred_at = _clinical_time(occurred_at, now)
    if entry_type.pk != head.entry_type_id and not entry_type.is_active:
        raise ValidationError({"entry_type": "Dieses Kürzel wird nicht mehr verwendet."})
    if (entry_type.pk, text, occurred_at) == (head.entry_type_id, head.text, head.occurred_at):
        raise ValidationError("Keine Änderung.")
    successor = _successor(
        head,
        actor=actor,
        now=now,
        status=Status.ACTIVE,
        reason=change_reason,
        reason_text=change_reason_text,
        content={"entry_type_id": entry_type.pk, "text": text, "occurred_at": occurred_at},
    )
    log_access(actor, "update", successor, patient_id=successor.patient_id)
    return successor


# --- Errors ------------------------------------------------------------------


@transaction.atomic
def mark_entered_in_error(
    record: VersionedRecord, *, change_reason, change_reason_text="", actor, based_on_version=None
) -> VersionedRecord:
    """Mark a contact or an entry as error: a last version with the reason.

    The content stays readable for doctors (#23 section 3.1). A contact with
    entries that are not marked as error themselves stays, so no entry loses
    its contact unnoticed.
    """
    _check_reason(change_reason, change_reason_text)
    head = _lock_and_check(actor, record, based_on_version)
    # `create_entry` locks the contact too, so no entry slips in after this check.
    if (
        isinstance(head, Encounter)
        and ChartEntry.objects.filter(
            encounter_lineage_id=head.lineage_id, status=Status.ACTIVE
        ).exists()
    ):
        raise ValidationError("Erst die Einträge dieses Kontakts als Irrtum markieren.")
    successor = _successor(
        head,
        actor=actor,
        now=timezone.now(),
        status=Status.ENTERED_IN_ERROR,
        reason=change_reason,
        reason_text=change_reason_text,
        content={},
    )
    log_access(actor, "update", successor, patient_id=successor.patient_id)
    return successor
