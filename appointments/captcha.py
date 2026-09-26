"""Self-hosted proof-of-work captcha in the format of ALTCHA (#7).

No third party sees the visitor. The server hands out a challenge
`sha256(salt + number)` with a random number up to `maxnumber`; the browser
tries numbers until the hash matches (`static/appointments/captcha.js`).
That costs a person a second or two and a bot the same for every request.

The challenge carries its expiry in the salt and an HMAC of the server, so
nothing needs storing until it is used. A solved challenge is remembered in
the cache until it expires and works only once.
"""

import base64
import hashlib
import hmac
import json
import secrets
import time
from urllib.parse import parse_qs

from django.conf import settings
from django.core.cache import cache
from django.utils.crypto import salted_hmac

ALGORITHM = "SHA-256"
# Long enough to fill in the form after the page has loaded.
VALID_SECONDS = 60 * 60


def _signature(challenge: str) -> str:
    return salted_hmac("appointments.captcha", challenge, algorithm="sha256").hexdigest()


def create_challenge(now: float | None = None) -> dict:
    now = time.time() if now is None else now
    max_number = settings.APPOINTMENTS_CAPTCHA_MAX_NUMBER
    salt = f"{secrets.token_hex(12)}?expires={int(now) + VALID_SECONDS}"
    number = secrets.randbelow(max_number + 1)
    challenge = hashlib.sha256(f"{salt}{number}".encode()).hexdigest()
    return {
        "algorithm": ALGORITHM,
        "challenge": challenge,
        "maxnumber": max_number,
        "salt": salt,
        "signature": _signature(challenge),
    }


def _expires(salt: str) -> int | None:
    _, _, query = salt.partition("?")
    try:
        return int(parse_qs(query)["expires"][0])
    except (KeyError, ValueError):
        return None


def verify(payload: str, now: float | None = None) -> bool:
    """Check the base64 JSON the browser sends; True uses the challenge up."""
    now = time.time() if now is None else now
    try:
        data = json.loads(base64.b64decode(payload, validate=True))
        algorithm, challenge = data["algorithm"], data["challenge"]
        salt, signature, number = data["salt"], data["signature"], int(data["number"])
    except (ValueError, TypeError, KeyError):
        return False
    if algorithm != ALGORITHM or not all(isinstance(v, str) for v in (challenge, salt, signature)):
        return False
    expires = _expires(salt)
    if expires is None or expires <= now:
        return False
    if not hmac.compare_digest(signature, _signature(challenge)):
        return False
    if not hmac.compare_digest(hashlib.sha256(f"{salt}{number}".encode()).hexdigest(), challenge):
        return False
    # cache.add is atomic: of two requests with the same solution, one wins.
    return cache.add(f"appointments:captcha:{challenge}", 1, timeout=int(expires - now) + 1)


def solve(challenge: dict) -> str:
    """What the browser does, in Python; for tests."""
    for number in range(challenge["maxnumber"] + 1):
        digest = hashlib.sha256(f"{challenge['salt']}{number}".encode()).hexdigest()
        if digest == challenge["challenge"]:
            payload = {k: challenge[k] for k in ("algorithm", "challenge", "salt", "signature")}
            return base64.b64encode(json.dumps({**payload, "number": number}).encode()).decode()
    raise ValueError("Keine Lösung gefunden.")
