"""Lock out password guessing per account name and per client address.

Both steps of the login count: a wrong password and a wrong code. The account
limit is low, the address limit high, because the whole practice shares one
public address.

An attempt is counted before it is checked (`begin_attempt`) and forgiven if
it succeeds (`attempt_succeeded`). Counting only after the slow password check
would let parallel requests all pass the lock check first.
"""

from datetime import timedelta

from django.db import transaction
from django.db.models import F, Q
from django.db.models.functions import Greatest
from django.utils import timezone
from django.utils.crypto import salted_hmac

from accounts.models import LoginThrottle

ACCOUNT_LIMIT = 5
ADDRESS_LIMIT = 20
WINDOW = timedelta(minutes=15)
LOCK = timedelta(minutes=15)


def _key(kind: str, value: str) -> str:
    return salted_hmac("accounts.throttle", f"{kind}:{value}", algorithm="sha256").hexdigest()


def account_key(username: str) -> str:
    """Also for names without an account, so a lock reveals nothing."""
    return _key("account", username.strip().casefold())


def address_key(address: str) -> str:
    return _key("address", address)


def client_address(request) -> str:
    # Direct connections only. Behind Caddy (#10) this has to read the address
    # Caddy passes on, or every request would share the proxy's address.
    return request.META.get("REMOTE_ADDR", "")


def request_keys(request, username: str) -> list[tuple[str, int]]:
    """The keys an attempt counts against, each with its limit."""
    return [
        (account_key(username), ACCOUNT_LIMIT),
        (address_key(client_address(request)), ADDRESS_LIMIT),
    ]


def purge_expired() -> None:
    """Forget windows that are over and locks that have run out."""
    now = timezone.now()
    LoginThrottle.objects.filter(window_start__lt=now - WINDOW).filter(
        Q(locked_until__isnull=True) | Q(locked_until__lte=now)
    ).delete()


def begin_attempt(keys: list[tuple[str, int]]) -> bool:
    """Count an attempt; False if it must not be checked at all.

    Attempts still in flight count, so at most `limit` run at the same time.
    """
    now = timezone.now()
    limits = dict(keys)
    with transaction.atomic():
        purge_expired()
        LoginThrottle.objects.bulk_create(
            [LoginThrottle(key=key, window_start=now) for key in limits],
            ignore_conflicts=True,
        )
        entries = list(LoginThrottle.objects.select_for_update().filter(key__in=limits))
        for entry in entries:
            if entry.locked_until and entry.locked_until <= now:
                # The lock has run out: start over, whatever WINDOW says.
                entry.failures, entry.window_start, entry.locked_until = 0, now, None
            if entry.locked_until or entry.failures >= limits[entry.key]:
                return False
        for entry in entries:
            entry.failures += 1
            entry.save()
    return True


def attempt_failed(keys: list[tuple[str, int]]) -> None:
    """Start the lock where the attempt reached the limit."""
    for key, limit in keys:
        LoginThrottle.objects.filter(
            key=key, failures__gte=limit, locked_until__isnull=True
        ).update(locked_until=timezone.now() + LOCK)


def attempt_succeeded(keys: list[tuple[str, int]]) -> None:
    LoginThrottle.objects.filter(key__in=[key for key, _ in keys]).update(
        failures=Greatest(F("failures") - 1, 0)
    )


def reset_account(username: str) -> None:
    """After a complete login; the address counter keeps running."""
    LoginThrottle.objects.filter(key=account_key(username)).delete()
