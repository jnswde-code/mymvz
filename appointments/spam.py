"""Limit form submissions per client address (#7).

The address is never stored in the database (#5): the cache holds an HMAC of
it for one hour, then forgets it.
"""

from django.conf import settings
from django.core.cache import cache
from django.utils.crypto import salted_hmac

from accounts.throttle import client_address

WINDOW_SECONDS = 60 * 60

# Name of the hidden field. People do not see it and leave it empty; bots
# that fill in every field give themselves away.
HONEYPOT_FIELD = "website"


def _key(request) -> str:
    digest = salted_hmac("appointments.spam", client_address(request), algorithm="sha256")
    return f"appointments:submissions:{digest.hexdigest()}"


def allow_submission(request) -> bool:
    """Count this submission; False once the address is over the limit."""
    key = _key(request)
    cache.add(key, 0, timeout=WINDOW_SECONDS)
    try:
        count = cache.incr(key)
    except ValueError:
        # Expired between add and incr.
        cache.add(key, 1, timeout=WINDOW_SECONDS)
        count = 1
    return count <= settings.APPOINTMENTS_SUBMISSIONS_PER_HOUR
