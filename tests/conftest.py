import re
from contextlib import contextmanager
from datetime import datetime
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
def commit():
    """`with commit(): …` sends the mails of the block at its end.

    Mails wait in the outbox until the worker sends them (#9); this plays the
    worker once, in the time of the block. Mails of steps outside a block are
    dropped, as they were when mails went out on commit, which tests never
    reached without this helper.
    """
    from appointments.mail import process_outbox
    from appointments.models import OutgoingMail

    @contextmanager
    def run():
        OutgoingMail.objects.filter(sent_at__isnull=True).delete()
        yield
        process_outbox()

    return run


LINK = re.compile(r"/termin/link/([A-Za-z0-9_-]+)/")


def token_from(message) -> str:
    """The raw token in the one link of a mail."""
    found = LINK.findall(message.body)
    assert len(found) == 1, message.body
    return found[0]
