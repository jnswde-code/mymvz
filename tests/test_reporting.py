"""Counts without personal reference (#5 section 6)."""

from reporting.models import RequestStatistic


def test_statistic_has_no_room_for_personal_data():
    """A new field here needs a reason: no name, no birth date, no id of a request."""
    assert {f.name for f in RequestStatistic._meta.get_fields()} == {
        "id",
        "week",
        "appointment_type",
        "channel",
        "outcome",
        "lead_time",
        "count",
    }
