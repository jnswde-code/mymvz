import re
from datetime import datetime
from functools import partial
from zoneinfo import ZoneInfo

import pytest
from django.core.cache import cache

BERLIN = ZoneInfo("Europe/Berlin")


def berlin(*args) -> datetime:
    """An aware datetime in local time, e.g. berlin(2026, 10, 5, 10)."""
    return datetime(*args, tzinfo=BERLIN)


@pytest.fixture(autouse=True)
def _empty_cache():
    """Rate limits and used captchas must not leak from one test into the next."""
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def commit(django_capture_on_commit_callbacks):
    """`with commit(): …` runs what waits for the commit (the mails) at the end."""
    return partial(django_capture_on_commit_callbacks, execute=True)


LINK = re.compile(r"/termin/link/([A-Za-z0-9_-]+)/")


def token_from(message) -> str:
    """The raw token in the one link of a mail."""
    found = LINK.findall(message.body)
    assert len(found) == 1, message.body
    return found[0]
