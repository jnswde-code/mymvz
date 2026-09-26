"""The one way views write the access log (#25).

log_access(request.user, "view", appointment_request)
log_access(request.user, "list", AppointmentRequest)
log_access(request.user, "search", Patient, result_count=len(hits))
log_access(request.user, "view", chart_entry, patient_id=chart_entry.patient_id)
"""

from django.db import models

from audit.models import AccessLogEntry


def log_access(user, action, target, *, patient_id=None, result_count=None) -> AccessLogEntry:
    """Record that `user` did `action` on `target` (an instance or a model class).

    Only type and id are stored. `patient_id` is for records that belong to a
    patient, so the practice can answer who has seen a patient's file.
    """
    if not getattr(user, "is_authenticated", False):
        raise ValueError("Zugriffe werden nur für angemeldete Konten protokolliert.")
    if isinstance(target, type) and issubclass(target, models.Model):
        model, object_id = target, ""
    elif isinstance(target, models.Model):
        if target.pk is None:
            raise ValueError("Ungespeicherte Datensätze haben keine ID fürs Protokoll.")
        model, object_id = type(target), str(target.pk)
    else:
        raise TypeError(f"Kein Modell und keine Modellklasse: {target!r}")
    return AccessLogEntry.objects.create(
        user=user,
        action=AccessLogEntry.Action(action),
        object_type=model._meta.label_lower,
        object_id=object_id,
        patient_id=patient_id,
        result_count=result_count,
    )
