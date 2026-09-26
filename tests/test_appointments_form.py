"""The request form with honeypot, per-address limit and captcha (#7)."""

import base64
import json
from datetime import date

import pytest
import time_machine
from django.urls import reverse

from appointments import captcha
from appointments.forms import RequestForm
from appointments.models import AppointmentRequest, AppointmentType
from tests.conftest import berlin
from tests.factories import DoctorFactory

pytestmark = pytest.mark.django_db

FORM = reverse("appointments:request")
SENT = reverse("appointments:sent")
NOW = berlin(2026, 10, 5, 10, 0)


@pytest.fixture(autouse=True)
def _frozen(settings):
    settings.APPOINTMENTS_CAPTCHA_MAX_NUMBER = 1000
    with time_machine.travel(NOW, tick=False):
        yield


def form_data(**overrides):
    data = {
        "appointment_type": AppointmentType.objects.get(name="Check-up").pk,
        "is_existing_patient": "0",
        "insurance_type": "private",
        "preferred_resource": "",
        "patient_first_name": "Erika",
        "patient_last_name": "Beispiel",
        "patient_date_of_birth": "1970-01-01",
        "email": "erika.beispiel@example.org",
        "phone": "0151 00000000",
        "note": "",
        "window_1_date": "2026-10-06",
        "window_1_part": "afternoon",
        "window_2_date": "",
        "window_2_part": "any",
        "window_3_date": "",
        "window_3_part": "any",
        "website": "",
        "altcha": captcha.solve(captcha.create_challenge()),
    }
    data.update(overrides)
    return data


def post(client, **overrides):
    return client.post(FORM, form_data(**overrides))


def test_form_page_shows_emergency_numbers_and_only_online_types(client):
    response = client.get(FORM)
    page = response.content.decode()
    assert "112" in page and "116 117" in page
    choices = [label for _, label in response.context["form"].fields["appointment_type"].choices]
    assert choices == [
        "Sprechstunde",
        "Gesundheits-Check-up",
        "Erstgespräch Demenztherapie (TPS)",
        "Erstvorstellung als neue Patientin oder neuer Patient",
    ]
    assert "Gesundheits-Check-up" in page
    assert 'id="captcha-challenge"' in page
    # No doctors yet: no choice to show.
    assert "Wunsch-Ärztin" not in page


def test_doctors_appear_once_there_are_any(client):
    DoctorFactory(name="Dr. med. Probe Eins")
    DoctorFactory(name="Dr. med. Probe Aus", is_active=False)
    page = client.get(FORM).content.decode()
    assert "Dr. med. Probe Eins" in page
    assert "Dr. med. Probe Aus" not in page


def test_valid_request_is_stored_and_redirects(client, commit, mailoutbox):
    with commit():
        response = post(client, note="Bitte Probe beachten", window_2_date="2026-10-07")
    assert response.status_code == 302 and response.url == SENT
    request = AppointmentRequest.objects.get()
    assert request.status == "unverified"
    assert request.insurance_type == "private"
    assert request.is_existing_patient is False
    assert request.note == "Bitte Probe beachten"
    assert [(w.date, w.part_of_day) for w in request.time_windows.all()] == [
        (date(2026, 10, 6), "afternoon"),
        (date(2026, 10, 7), "any"),
    ]
    assert mailoutbox[-1].to == ["erika.beispiel@example.org"]


def test_service_errors_land_on_their_fields(client):
    response = post(client, window_1_part="morning", window_2_date="2026-10-10")
    assert response.status_code == 200
    form = response.context["form"]
    assert "window_1_date" in form.errors and "window_2_date" in form.errors
    assert AppointmentRequest.objects.count() == 0


def test_note_longer_than_500_characters_is_rejected(client):
    response = post(client, note="x" * 501)
    assert "note" in response.context["form"].errors
    assert post(client, note="x" * 500).status_code == 302


def test_request_for_another_person_needs_contact(client):
    response = post(client, for_other_person="on")
    assert set(response.context["form"].errors) == {"contact_name", "contact_relationship"}
    ok = post(
        client, for_other_person="on", contact_name="Max Beispiel", contact_relationship="Vater"
    )
    assert ok.status_code == 302
    assert AppointmentRequest.objects.get().contact_relationship == "Vater"


def test_contact_fields_are_dropped_without_the_checkbox(client):
    post(client, contact_name="Max Beispiel", contact_relationship="Vater")
    assert AppointmentRequest.objects.get().contact_name == ""


@pytest.mark.parametrize(
    ("phone", "ok"),
    [
        ("0151 00000000", True),
        ("+49 2181 000000", True),
        ("02181/000-000", True),
        ("(02181) 000000", False),  # must start with + or a digit
        ("0151", False),
        ("keine Angabe", False),
        ("0151 0000000-", False),
    ],
)
def test_phone_number_format(phone, ok):
    form = RequestForm(data=form_data(phone=phone))
    assert form.is_valid() is ok, form.errors


# --- Spam protection -----------------------------------------------------------


def test_honeypot_looks_like_success_but_stores_nothing(client, mailoutbox):
    response = post(client, website="https://example.invalid")
    assert response.status_code == 302 and response.url == SENT
    assert AppointmentRequest.objects.count() == 0
    assert mailoutbox == []


def test_missing_captcha_is_rejected(client):
    response = post(client, altcha="")
    assert response.status_code == 200
    assert response.context["form"].non_field_errors()
    assert AppointmentRequest.objects.count() == 0


def test_captcha_solution_works_only_once(client):
    solution = captcha.solve(captcha.create_challenge())
    assert post(client, altcha=solution).status_code == 302
    response = post(client, altcha=solution)
    assert response.status_code == 200
    assert AppointmentRequest.objects.count() == 1


def test_eleventh_post_from_one_address_within_an_hour_is_refused(client, settings):
    for _ in range(settings.APPOINTMENTS_SUBMISSIONS_PER_HOUR):
        assert post(client, altcha="").status_code == 200
    response = post(client)
    assert response.status_code == 429
    assert AppointmentRequest.objects.count() == 0


def test_limit_is_per_address(client, settings):
    settings.APPOINTMENTS_SUBMISSIONS_PER_HOUR = 1
    assert post(client, altcha="", REMOTE_ADDR="192.0.2.1").status_code == 200
    assert post(client, altcha="", REMOTE_ADDR="192.0.2.1").status_code == 429
    response = client.post(FORM, form_data(), REMOTE_ADDR="192.0.2.2")
    assert response.status_code == 302


def test_limit_resets_after_an_hour(client, settings):
    settings.APPOINTMENTS_SUBMISSIONS_PER_HOUR = 1
    with time_machine.travel(NOW, tick=False) as traveller:
        post(client, altcha="")
        assert post(client, altcha="").status_code == 429
        traveller.shift(60 * 60 + 1)
        assert post(client).status_code == 302


# --- Captcha on its own --------------------------------------------------------


def _tamper(payload, **changes):
    data = json.loads(base64.b64decode(payload))
    data.update(changes)
    return base64.b64encode(json.dumps(data).encode()).decode()


def test_captcha_accepts_the_right_number():
    assert captcha.verify(captcha.solve(captcha.create_challenge()))


@pytest.mark.parametrize(
    "broken",
    [
        lambda p: _tamper(p, number=json.loads(base64.b64decode(p))["number"] + 1),
        lambda p: _tamper(p, signature="0" * 64),
        lambda p: _tamper(p, algorithm="SHA-1"),
        lambda p: _tamper(p, salt="anders?expires=9999999999"),
        lambda p: _tamper(p, number="viele"),
        lambda p: "kein base64!",
        lambda p: base64.b64encode(b"[]").decode(),
    ],
)
def test_captcha_rejects_tampering(broken):
    assert not captcha.verify(broken(captcha.solve(captcha.create_challenge())))


def test_captcha_expires_after_an_hour():
    issued = NOW.timestamp()
    payload = captcha.solve(captcha.create_challenge(now=issued))
    assert not captcha.verify(payload, now=issued + captcha.VALID_SECONDS)
    assert captcha.verify(payload, now=issued + captcha.VALID_SECONDS - 1)
