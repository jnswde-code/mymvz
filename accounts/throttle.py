"""Lock out password guessing per account name and per client address.

Both steps of the login count: a wrong password and a wrong code. The account
limit is low, the address limit high, because the whole practice shares one
public address.
"""

from datetime import timedelta

from django.db import transaction
from django.db.models import Q
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


def is_locked(keys: list[tuple[str, int]]) -> bool:
    return LoginThrottle.objects.filter(
        key__in=[key for key, _ in keys], locked_until__gt=timezone.now()
    ).exists()


def register_failure(keys: list[tuple[str, int]]) -> None:
    now = timezone.now()
    with transaction.atomic():
        # Forget windows that are over and locks that have run out.
        LoginThrottle.objects.filter(window_start__lt=now - WINDOW).filter(
            Q(locked_until__isnull=True) | Q(locked_until__lte=now)
        ).delete()
        for key, limit in keys:
            entry, _ = LoginThrottle.objects.select_for_update().get_or_create(
                key=key, defaults={"window_start": now}
            )
            if entry.locked_until and entry.locked_until <= now:
                entry.failures, entry.window_start, entry.locked_until = 0, now, None
            entry.failures += 1
            if entry.failures >= limit:
                entry.locked_until = now + LOCK
            entry.save()


def reset_account(username: str) -> None:
    """After a complete login; the address counter keeps running."""
    LoginThrottle.objects.filter(key=account_key(username)).delete()
