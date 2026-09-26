"""Read configuration from environment variables (filled from `.env`)."""

from __future__ import annotations

import os

from django.core.exceptions import ImproperlyConfigured

_TRUE = {"1", "true", "yes", "on"}
_FALSE = {"0", "false", "no", "off", ""}


def env_str(name: str, default: str | None = None) -> str:
    """Return the variable, or `default`; without either the setup is broken.

    An empty value (`NAME=` in .env) counts as missing, so it neither passes
    silently nor hides the default.
    """
    value = os.environ.get(name) or default
    if not value:
        raise ImproperlyConfigured(f"Umgebungsvariable {name} fehlt (s. .env.example)")
    return value


def env_bool(name: str, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    normalized = value.strip().lower()
    if normalized in _TRUE:
        return True
    if normalized in _FALSE:
        return False
    # A typo like DEBUG=ture must not silently fall back to one side.
    raise ImproperlyConfigured(f"{name}={value!r} ist kein Wahrheitswert (1/0, true/false)")


def env_list(name: str, default: str = "") -> list[str]:
    """Comma-separated list, blanks and empty entries dropped."""
    return [item.strip() for item in os.environ.get(name, default).split(",") if item.strip()]


def allowed_hosts(site_host: str, extra: list[str], debug: bool) -> list[str]:
    """The public host name, extra hosts, and in development the local ones."""
    hosts = [site_host, *extra]
    if debug:
        hosts += ["localhost", "127.0.0.1", "[::1]"]
    return list(dict.fromkeys(hosts))
