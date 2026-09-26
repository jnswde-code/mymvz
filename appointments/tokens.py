"""Links in e-mails: long, random, stored as a hash, valid once (#5, #7).

The raw token only ever exists in the link of one e-mail. Anyone who reads
the database learns nothing that would open a link.
"""

import hashlib
import secrets
from dataclasses import dataclass

from django.utils import timezone

from appointments.models import RequestToken

# 32 bytes of randomness, 43 characters in the URL.
TOKEN_BYTES = 32


def hash_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def issue(request, purpose, expires_at, appointment=None) -> str:
    """Store a new token and return the raw value for the link."""
    raw = secrets.token_urlsafe(TOKEN_BYTES)
    RequestToken.objects.create(
        request=request,
        appointment=appointment,
        purpose=purpose,
        token_hash=hash_token(raw),
        expires_at=expires_at,
    )
    return raw


class Problem:
    UNKNOWN = "unknown"
    USED = "used"
    EXPIRED = "expired"


@dataclass
class Lookup:
    token: RequestToken | None
    problem: str | None

    @property
    def ok(self) -> bool:
        return self.problem is None


def look_up(raw: str, *, lock: bool = False, now=None) -> Lookup:
    """Find the token for a link; with `lock`, inside a transaction, lock its row."""
    now = now or timezone.now()
    tokens = RequestToken.objects.select_related("request", "appointment")
    if lock:
        tokens = tokens.select_for_update(of=("self",))
    token = tokens.filter(token_hash=hash_token(raw)).first()
    if token is None:
        return Lookup(None, Problem.UNKNOWN)
    if token.used_at is not None:
        return Lookup(token, Problem.USED)
    if token.expires_at <= now:
        return Lookup(token, Problem.EXPIRED)
    return Lookup(token, None)


def mark_used(token: RequestToken, now=None) -> None:
    token.used_at = now or timezone.now()
    token.save(update_fields=["used_at"])
