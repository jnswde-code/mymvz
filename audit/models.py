import uuid

from django.conf import settings
from django.db import models
from django.utils import timezone


class Action(models.TextChoices):
    VIEW = "view", "angesehen"
    LIST = "list", "Liste angesehen"
    SEARCH = "search", "gesucht"
    CREATE = "create", "angelegt"
    UPDATE = "update", "geändert"
    EXPORT = "export", "exportiert"
    PRINT = "print", "gedruckt"
    DOWNLOAD = "download", "heruntergeladen"
    # The reason stays in `patients.EmergencyAccess`, never here (#39).
    EMERGENCY_ACCESS = "emergency_access", "Notfallzugriff"


class AccessLogEntry(models.Model):
    """Who accessed which record when (#5, #23 section 3.2).

    Type and id only, never names or content: once the record is deleted, the
    entry points at nothing and tells nobody who it was about. Entries are
    written through `audit.log.log_access` and never changed.
    """

    Action = Action

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    at = models.DateTimeField(default=timezone.now, db_index=True, editable=False)
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name="+")
    action = models.CharField(max_length=16, choices=Action)
    # Model label such as "appointments.appointmentrequest".
    object_type = models.CharField(max_length=100)
    # Empty for lists and searches.
    object_id = models.CharField(max_length=64, blank=True)
    # No foreign key: the patient may be deleted after the retention period,
    # the entry stays (#23 section 3.2).
    patient_id = models.UUIDField(null=True, blank=True, db_index=True)
    # Searches: how many hits, never the search term.
    result_count = models.PositiveIntegerField(null=True, blank=True)

    class Meta:
        ordering = ["-at", "-id"]
        verbose_name = "Protokolleintrag"
        verbose_name_plural = "Protokolleinträge"
        constraints = [
            models.CheckConstraint(
                condition=models.Q(action__in=Action.values),
                name="audit_accesslogentry_action_valid",
            ),
        ]

    def __str__(self):
        return f"{self.at:%Y-%m-%d %H:%M} {self.action} {self.object_type} {self.object_id}"

    def save(self, *args, **kwargs):
        if not self._state.adding:
            raise ValueError("Protokolleinträge werden nie geändert.")
        super().save(*args, **kwargs)
