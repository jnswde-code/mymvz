"""The appointment types from the data migration (#3, decision 2)."""

import pytest

from appointments.models import AppointmentType

pytestmark = pytest.mark.django_db


def test_online_list_and_the_types_only_by_phone():
    online = set(
        AppointmentType.objects.filter(bookable_online=True).values_list("name", flat=True)
    )
    offline = set(
        AppointmentType.objects.filter(bookable_online=False).values_list("name", flat=True)
    )
    assert online == {"Sprechstunde", "Check-up", "TPS-Erstgespräch", "Erstvorstellung"}
    assert offline == {"Akut", "Substitution", "Hausbesuch"}
