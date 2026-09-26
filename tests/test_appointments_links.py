"""Links in e-mails: valid once, until their deadline, and only while they fit (#7)."""

from datetime import timedelta

import pytest
import time_machine
from django.urls import reverse

from accounts.testing import make_user
from appointments import services
from appointments.models import Appointment, AppointmentRequest, RequestToken
from appointments.tokens import hash_token
from tests.conftest import berlin, token_from
from tests.factories import request_data

pytestmark = pytest.mark.django_db

NOW = berlin(2026, 10, 5, 10, 0)
Status = AppointmentRequest.Status


@pytest.fixture(autouse=True)
def _frozen():
    with time_machine.travel(NOW, tick=False) as traveller:
        yield traveller


@pytest.fixture
def staff():
    return make_user("max.probe")


def url(raw):
    return reverse("appointments:link", args=[raw])


def submitted(commit, mailoutbox):
    with commit():
        request = services.submit_request(request_data())
    return request, token_from(mailoutbox[-1])


def opened(commit, mailoutbox):
    request, raw = submitted(commit, mailoutbox)
    with commit():
        services.verify_email(raw)
    request.refresh_from_db()
    return request


def booked(commit, mailoutbox, staff, start=None):
    request = opened(commit, mailoutbox)
    with commit():
        appointment = services.confirm_request(
            request, start or berlin(2026, 10, 12, 10), actor=staff
        )
    return request, appointment, token_from(mailoutbox[-1])


def proposed(commit, mailoutbox, staff):
    request = opened(commit, mailoutbox)
    with commit():
        appointment = services.propose_appointment(request, berlin(2026, 10, 12, 10), actor=staff)
    return request, appointment, token_from(mailoutbox[-1])


# --- Tokens ----------------------------------------------------------------


def test_only_the_hash_is_stored(commit, mailoutbox):
    request, raw = submitted(commit, mailoutbox)
    token = request.tokens.get()
    assert len(raw) >= 43
    assert token.token_hash == hash_token(raw)
    assert raw not in {getattr(token, f.attname) for f in RequestToken._meta.fields}


def test_every_mail_gets_its_own_token(commit, mailoutbox, staff):
    request = opened(commit, mailoutbox)
    withdraw = token_from(mailoutbox[-2])  # mails: verify, received, practice
    assert "/termin/link/" not in mailoutbox[-1].body  # the practice mail has no link
    request, appointment, cancel = booked(commit, mailoutbox, staff)
    assert withdraw != cancel
    assert request.tokens.count() == 3


# --- Verification ------------------------------------------------------------


def test_get_shows_the_page_and_changes_nothing(client, commit, mailoutbox):
    """Mail scanners open links; only the button acts."""
    request, raw = submitted(commit, mailoutbox)
    response = client.get(url(raw))
    assert response.status_code == 200
    assert request.reference in response.content.decode()
    request.refresh_from_db()
    assert request.status == Status.UNVERIFIED
    assert request.tokens.get().used_at is None


def test_verify_link_works_once(client, commit, mailoutbox):
    request, raw = submitted(commit, mailoutbox)
    with commit():
        response = client.post(url(raw))
    assert response.status_code == 200
    request.refresh_from_db()
    assert request.status == Status.OPEN
    assert client.post(url(raw)).status_code == 410
    assert client.get(url(raw)).status_code == 410


def test_verify_link_expires_after_24_hours(client, commit, mailoutbox, _frozen):
    request, raw = submitted(commit, mailoutbox)
    _frozen.move_to(NOW + timedelta(hours=24) - timedelta(seconds=1))
    assert client.get(url(raw)).status_code == 200
    _frozen.move_to(NOW + timedelta(hours=24))
    response = client.post(url(raw))
    assert response.status_code == 410
    assert "24 Stunden" in response.content.decode()
    request.refresh_from_db()
    assert request.status == Status.UNVERIFIED


def test_unknown_link_is_404(client):
    assert client.get(url("x" * 43)).status_code == 404
    assert client.post(url("x" * 43)).status_code == 404


def test_link_of_one_purpose_does_not_work_for_another(commit, mailoutbox):
    _, raw = submitted(commit, mailoutbox)
    with pytest.raises(services.LinkInvalid):
        services.withdraw_request(raw)
    with pytest.raises(services.LinkInvalid):
        services.cancel_by_patient(raw)


# --- Withdrawing -------------------------------------------------------------


def test_withdraw_until_the_end_of_the_last_wish_day(client, commit, mailoutbox, _frozen):
    request = opened(commit, mailoutbox)
    raw = token_from(mailoutbox[-2])
    last_day = request.time_windows.get().date
    _frozen.move_to(berlin(last_day.year, last_day.month, last_day.day, 23, 59))
    assert client.post(url(raw)).status_code == 200
    request.refresh_from_db()
    assert request.status == Status.WITHDRAWN


def test_withdraw_link_after_the_last_wish_day_is_expired(client, commit, mailoutbox, _frozen):
    request = opened(commit, mailoutbox)
    raw = token_from(mailoutbox[-2])
    last_day = request.time_windows.get().date + timedelta(days=1)
    _frozen.move_to(berlin(last_day.year, last_day.month, last_day.day, 0, 0))
    assert client.post(url(raw)).status_code == 410


def test_withdraw_link_is_outdated_once_scheduled(client, commit, mailoutbox, staff):
    request = opened(commit, mailoutbox)
    raw = token_from(mailoutbox[-2])
    services.confirm_request(request, berlin(2026, 10, 12, 10), actor=staff)
    assert client.post(url(raw)).status_code == 410
    request.refresh_from_db()
    assert request.status == Status.SCHEDULED


# --- Proposals ---------------------------------------------------------------


def test_accept_proposal(client, commit, mailoutbox, staff):
    request, appointment, raw = proposed(commit, mailoutbox, staff)
    assert client.get(url(raw)).status_code == 200
    with commit():
        response = client.post(url(raw), {"decision": "accept"})
    assert response.status_code == 200
    appointment.refresh_from_db()
    assert appointment.status == "booked"
    assert appointment.proposal_expires_at is None
    # The confirmation brings a cancel link of its own.
    assert mailoutbox[-1].subject == "Ihr Termin ist bestätigt"
    assert token_from(mailoutbox[-1]) != raw


def test_decline_proposal_reopens_the_request(client, commit, mailoutbox, staff):
    request, appointment, raw = proposed(commit, mailoutbox, staff)
    client.post(url(raw), {"decision": "decline"})
    appointment.refresh_from_db()
    request.refresh_from_db()
    assert (appointment.status, appointment.cancelled_by) == ("cancelled", "patient")
    assert request.status == Status.OPEN
    # Answered once; the other button no longer works.
    assert client.post(url(raw), {"decision": "accept"}).status_code == 410


def test_proposal_without_decision_changes_nothing(client, commit, mailoutbox, staff):
    request, appointment, raw = proposed(commit, mailoutbox, staff)
    assert client.post(url(raw), {"decision": "maybe"}).status_code == 200
    appointment.refresh_from_db()
    assert appointment.status == "proposed"


def test_proposal_link_expires_with_the_proposal(client, commit, mailoutbox, staff, _frozen):
    request, appointment, raw = proposed(commit, mailoutbox, staff)
    _frozen.move_to(appointment.proposal_expires_at)
    assert client.post(url(raw), {"decision": "accept"}).status_code == 410
    appointment.refresh_from_db()
    assert appointment.status == "proposed"


def test_proposal_link_is_outdated_when_the_practice_withdraws(client, commit, mailoutbox, staff):
    request, appointment, raw = proposed(commit, mailoutbox, staff)
    services.cancel_appointment(appointment, actor=staff)
    assert client.post(url(raw), {"decision": "accept"}).status_code == 410


# --- Cancelling --------------------------------------------------------------


def test_patient_cancels_until_24_hours_before(client, commit, mailoutbox, staff, _frozen):
    request, appointment, raw = booked(commit, mailoutbox, staff)
    _frozen.move_to(appointment.start - timedelta(hours=24, seconds=1))
    assert client.get(url(raw)).status_code == 200
    with commit():
        response = client.post(url(raw), {"reason": "treated_elsewhere"})
    assert response.status_code == 200
    appointment.refresh_from_db()
    assert (appointment.status, appointment.cancelled_by) == ("cancelled", "patient")
    assert (appointment.cancellation_channel, appointment.cancellation_reason) == (
        "link",
        "treated_elsewhere",
    )
    # The practice hears of it, without content.
    assert mailoutbox[-1].to == ["praxis@example.invalid"]


def test_cancel_link_expires_24_hours_before(client, commit, mailoutbox, staff, _frozen):
    request, appointment, raw = booked(commit, mailoutbox, staff)
    _frozen.move_to(appointment.start - timedelta(hours=24))
    response = client.post(url(raw))
    assert response.status_code == 410
    assert "telefonisch" in response.content.decode()
    appointment.refresh_from_db()
    assert appointment.status == "booked"


def test_cancel_rejects_reasons_outside_the_list(client, commit, mailoutbox, staff):
    request, appointment, raw = booked(commit, mailoutbox, staff)
    assert client.post(url(raw), {"reason": "practice_unavailable"}).status_code == 200
    appointment.refresh_from_db()
    assert appointment.status == "booked"
    with pytest.raises(services.ValidationError):
        services.cancel_by_patient(raw, "please_call")


def test_cancel_link_is_outdated_once_the_practice_cancelled(client, commit, mailoutbox, staff):
    request, appointment, raw = booked(commit, mailoutbox, staff)
    services.cancel_appointment(appointment, actor=staff)
    assert client.post(url(raw)).status_code == 410
    assert Appointment.objects.get(pk=appointment.pk).cancelled_by == "practice"


def test_short_notice_appointment_gets_no_cancel_link(commit, mailoutbox, staff):
    request = opened(commit, mailoutbox)
    with commit():
        services.confirm_request(request, NOW + timedelta(hours=5), actor=staff)
    assert "/termin/link/" not in mailoutbox[-1].body
    assert "telefonisch ab" in mailoutbox[-1].body


def test_second_use_of_a_link_fails_in_the_service(commit, mailoutbox):
    """Two clicks at once: both pass the page's check, only one gets the lock."""
    request, raw = submitted(commit, mailoutbox)
    services.verify_email(raw)
    with pytest.raises(services.LinkInvalid) as caught:
        services.verify_email(raw)
    assert caught.value.problem == "used"


def test_service_rechecks_the_status_under_the_lock(commit, mailoutbox, staff):
    request = opened(commit, mailoutbox)
    raw = token_from(mailoutbox[-2])
    services.confirm_request(request, berlin(2026, 10, 12, 10), actor=staff)
    with pytest.raises(services.LinkInvalid) as caught:
        services.withdraw_request(raw)
    assert caught.value.problem == "outdated"
    assert request.tokens.get(purpose="withdraw").used_at is None
