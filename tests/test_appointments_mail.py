"""E-mails never carry health data: no type, no note, no doctor, no name (#3, #7)."""

import pytest
import time_machine
from django.core import mail as django_mail
from django.db import transaction

from accounts.testing import make_user
from appointments import mail, services
from appointments.models import AppointmentType, Channel, OutgoingMail
from tests.conftest import berlin, token_from
from tests.factories import DoctorFactory, request_data

pytestmark = pytest.mark.django_db

NOW = berlin(2026, 10, 5, 10, 0)
# Invented values that must not appear in any mail.
NOTE = "Probe-Notiz mit Beschwerden"
STAFF_NOTE = "Interner Probevermerk"


@pytest.fixture(autouse=True)
def _frozen():
    with time_machine.travel(NOW, tick=False):
        yield


def forbidden_words(request):
    kind = request.appointment_type
    words = {
        kind.name,
        kind.public_name,
        NOTE,
        STAFF_NOTE,
        request.patient_first_name,
        request.patient_last_name,
        request.contact_name,
        request.patient_date_of_birth.strftime("%d.%m.%Y"),
        request.phone,
    }
    if request.preferred_resource:
        words.add(request.preferred_resource.name)
    return {w for w in words if w}


def assert_clean(messages, request):
    for message in messages:
        text = f"{message.subject}\n{message.body}"
        for word in forbidden_words(request):
            assert word not in text, (word, message.subject)


def test_no_mail_ever_contains_health_data_or_names(commit, mailoutbox):
    """Walk a request through every mail a patient or the practice can get."""
    staff = make_user("max.probe")
    tps = AppointmentType.objects.get(name="TPS-Erstgespräch")
    data = request_data(
        appointment_type=tps,
        note=NOTE,
        preferred_resource=DoctorFactory(name="Dr. med. Probe Vorzug"),
        contact_name="Max Beispiel",
        contact_relationship="Vater",
    )
    with commit():
        request = services.submit_request(data)
    request.staff_note = STAFF_NOTE
    request.save()
    with commit():
        services.verify_email(token_from(mailoutbox[-1]))
    with commit():
        services.propose_appointment(request, berlin(2026, 10, 12, 10), actor=staff)
    with commit():
        services.decline_proposal(token_from(mailoutbox[-1]))
    with commit():
        appointment = services.confirm_request(request, berlin(2026, 10, 13, 15), actor=staff)
    with commit():
        services.cancel_by_patient(token_from(mailoutbox[-1]))
    # The remaining mails, rendered for the same request.
    mail.send(mail.CANCELLED_BY_PRACTICE, request.pk, appointment.pk)
    mail.send(mail.DECLINED, request.pk)
    mail.send(mail.EXPIRED, request.pk)

    assert {m.subject for m in mailoutbox} == set(mail.SUBJECTS.values())
    assert len(mailoutbox) == len(mail.SUBJECTS)  # one of each kind
    assert_clean(mailoutbox, request)


def test_practice_mails_say_only_that_something_happened(commit, mailoutbox):
    with commit():
        request = services.submit_request(request_data(note=NOTE))
    with commit():
        services.verify_email(token_from(mailoutbox[-1]))
    practice = [m for m in mailoutbox if m.to == ["praxis@example.invalid"]]
    assert [m.subject for m in practice] == ["Neue Terminanfrage"]
    assert request.reference not in practice[0].body
    assert "/termin/" not in practice[0].body


def test_mail_shows_local_time(commit, mailoutbox):
    staff = make_user("max.probe")
    request = services.submit_request(request_data(), channel=Channel.STAFF, actor=staff)
    mailoutbox.clear()
    with commit():
        # 26 Oct is winter time: 09:30 in Berlin is 08:30 UTC.
        services.confirm_request(request, berlin(2026, 10, 26, 9, 30), actor=staff)
    body = mailoutbox[-1].body
    assert "Montag, 26. Oktober 2026, 09:30 Uhr" in body
    assert "bis Sonntag, 25. Oktober 2026, 09:30 Uhr" in body


def test_links_start_with_the_configured_address(commit, mailoutbox, settings):
    settings.SITE_BASE_URL = "https://termine.example.invalid"
    with commit():
        services.submit_request(request_data())
    assert "https://termine.example.invalid/termin/link/" in mailoutbox[-1].body


def test_no_mail_for_a_rolled_back_transaction(mailoutbox):
    with pytest.raises(RuntimeError), transaction.atomic():
        services.submit_request(request_data())
        raise RuntimeError
    mail.process_outbox()
    assert not OutgoingMail.objects.exists()
    assert mailoutbox == []


def test_patient_mail_without_address_is_skipped(mailoutbox):
    request = services.submit_request(request_data(email=""), channel=Channel.PHONE_ASSISTANT)
    assert mail.send(mail.DECLINED, request.pk) is False
    assert mailoutbox == []


def test_deleted_request_sends_nothing(mailoutbox):
    request = services.submit_request(request_data())
    request_id = request.pk
    request.delete()
    assert mail.send(mail.VERIFY_EMAIL, request_id) is False
    assert django_mail.outbox == []


def test_unknown_kind_is_rejected():
    request = services.submit_request(request_data())
    with pytest.raises(ValueError):
        mail.queue("reminder", request)
