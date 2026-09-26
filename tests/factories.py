"""Factories for invented test data only (#3, DSGVO Art. 9).

Names are obviously made up ("Probe", "Beispiel"); dates of birth and phone
numbers are fictitious.
"""

from datetime import date, timedelta

import factory
from django.utils import timezone

from appointments.models import AppointmentRequest, AppointmentType
from practice.models import Resource


class DoctorFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Resource

    kind = Resource.Kind.DOCTOR
    name = factory.Sequence(lambda n: f"Dr. med. Probe {n}")


def request_data(**overrides) -> dict:
    """Valid input for `services.submit_request`, with windows from tomorrow."""
    tomorrow = timezone.localdate() + timedelta(days=1)
    data = {
        "appointment_type": overrides.pop("appointment_type", None)
        or AppointmentType.objects.get(name="Sprechstunde"),
        "is_existing_patient": False,
        "insurance_type": AppointmentRequest.Insurance.STATUTORY,
        "preferred_resource": None,
        "patient_first_name": "Erika",
        "patient_last_name": "Beispiel",
        "patient_date_of_birth": date(1970, 1, 1),
        "contact_name": "",
        "contact_relationship": "",
        "email": "erika.beispiel@example.org",
        "phone": "0151 00000000",
        "note": "",
        "time_windows": [(next_consultation_day(tomorrow), "any")],
    }
    data.update(overrides)
    return data


def next_consultation_day(start: date) -> date:
    """The first weekday from `start`; the seeded hours have consultation Mon–Fri."""
    day = start
    while day.weekday() >= 5:
        day += timedelta(days=1)
    return day
