import uuid

from django.contrib.auth.models import AbstractUser
from django.db import models


class User(AbstractUser):
    """Staff account. Accounts are deactivated, never deleted (#25).

    The access log points at users with PROTECT, so deleting an account would
    either fail or, without that, erase who looked at what.
    """

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)

    class Meta:
        verbose_name = "Konto"
        verbose_name_plural = "Konten"

    def __str__(self):
        return self.username

    def delete(self, *args, **kwargs):
        raise models.ProtectedError(
            "Konten werden deaktiviert, nicht gelöscht (is_active = False).", {self}
        )


class LoginThrottle(models.Model):
    """Failed login attempts per account name or per client address.

    `key` is an HMAC of the name or address, never the value itself, and rows
    disappear once their window is over, so no IP address is kept (#25).
    """

    key = models.CharField(max_length=64, unique=True)
    failures = models.PositiveIntegerField(default=0)
    window_start = models.DateTimeField()
    locked_until = models.DateTimeField(null=True, blank=True)

    class Meta:
        verbose_name = "Anmeldesperre"
        verbose_name_plural = "Anmeldesperren"

    def __str__(self):
        return f"{self.key[:8]}… ({self.failures})"
