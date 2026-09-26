"""Opening hours as the one source for checking preferred days (#5, #7)."""

from datetime import date, time

import pytest
from django.db import IntegrityError

from practice.models import OpeningHours

pytestmark = pytest.mark.django_db

MONDAY = date(2026, 10, 5)


def only(*blocks):
    OpeningHours.objects.all().delete()
    for opens, closes in blocks:
        OpeningHours.objects.create(kind="consultation", weekday=0, opens=opens, closes=closes)


@pytest.mark.parametrize(
    ("opens", "closes", "morning", "afternoon"),
    [
        (time(8), time(13), True, False),  # ends exactly at midday
        (time(8), time(13, 1), True, True),
        (time(12, 59), time(16), True, True),
        (time(13), time(18), False, True),  # starts exactly at midday
    ],
)
def test_part_of_day_splits_at_13(opens, closes, morning, afternoon):
    only((opens, closes))
    assert OpeningHours.objects.covers(MONDAY, "morning") is morning
    assert OpeningHours.objects.covers(MONDAY, "afternoon") is afternoon
    assert OpeningHours.objects.covers(MONDAY, "any") is True


def test_opening_hours_alone_are_no_consultation():
    OpeningHours.objects.all().delete()
    OpeningHours.objects.create(kind="opening", weekday=0, opens=time(8), closes=time(16))
    assert OpeningHours.objects.covers(MONDAY, "any") is False


def test_unknown_part_of_day_is_an_error():
    with pytest.raises(ValueError):
        OpeningHours.objects.covers(MONDAY, "evening")


def test_database_rejects_block_ending_before_it_starts():
    with pytest.raises(IntegrityError):
        OpeningHours.objects.create(kind="opening", weekday=0, opens=time(12), closes=time(8))


def test_seeded_hours_keep_consultation_within_opening_hours():
    """The data migration cut the homepage's contradictions (#3)."""
    consultation = OpeningHours.objects.filter(kind="consultation")
    assert sorted(consultation.values_list("weekday", flat=True)) == [0, 1, 2, 3, 4]
    for block in consultation:
        assert OpeningHours.objects.filter(
            kind="opening", weekday=block.weekday, opens__lte=block.opens, closes__gte=block.closes
        ).exists(), block
