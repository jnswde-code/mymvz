"""Creating requests and every status transition goes through services (#5, #7)."""

from datetime import date, timedelta

import pytest
import time_machine
from django.core.exceptions import ValidationError
from django.db import IntegrityError

from accounts.testing import make_user
from appointments import services
from appointments.models import (
    Appointment,
    AppointmentEvent,
    AppointmentRequest,
    AppointmentType,
    Channel,
)
from audit.models import AccessLogEntry
from tests.conftest import berlin, token_from
from tests.factories import DoctorFactory, request_data

pytestmark = pytest.mark.django_db

# Monday. Consultation: Mon 8–13, Tue 14–17.30, Wed 8–12, Thu 14–17.30, Fri 8–12.
NOW = berlin(2026, 10, 5, 10, 0)
TUESDAY = date(2026, 10, 6)
SATURDAY = date(2026, 10, 10)
Status = AppointmentRequest.Status


@pytest.fixture(autouse=True)
def _frozen():
    with time_machine.travel(NOW, tick=False):
        yield


@pytest.fixture
def staff():
    return make_user("max.probe")


def submit(**overrides):
    channel = overrides.pop("channel", Channel.WEB)
    actor = overrides.pop("actor", None)
    return services.submit_request(request_data(**overrides), channel=channel, actor=actor)


def errors(**overrides):
    with pytest.raises(ValidationError) as caught:
        submit(**overrides)
    return caught.value.message_dict


def open_request(commit, mailoutbox, **overrides):
    with commit():
        request = submit(**overrides)
    with commit():
        services.verify_email(token_from(mailoutbox[-1]))
    request.refresh_from_db()
    return request


# --- Creating ------------------------------------------------------------


def test_web_request_starts_unverified_with_windows_and_event():
    request = submit(time_windows=[(TUESDAY, "afternoon"), (date(2026, 10, 7), "morning")])
    assert request.status == Status.UNVERIFIED
    assert request.reference.startswith("A-") and len(request.reference) == 7
    assert [(w.position, w.date, w.part_of_day) for w in request.time_windows.all()] == [
        (1, TUESDAY, "afternoon"),
        (2, date(2026, 10, 7), "morning"),
    ]
    event = request.events.get()
    assert (event.from_status, event.to_status, event.actor_kind) == ("", "unverified", "patient")
    assert request.privacy_notice_version


@pytest.mark.parametrize(
    ("window", "ok"),
    [
        ((date(2026, 10, 5), "any"), False),  # today
        ((TUESDAY, "any"), True),  # tomorrow
        ((date(2026, 11, 30), "any"), True),  # exactly 8 weeks ahead (Monday)
        ((date(2026, 12, 1), "any"), False),  # one day more
        ((SATURDAY, "any"), False),  # no consultation at all
        ((TUESDAY, "morning"), False),  # Tuesday only in the afternoon
        ((TUESDAY, "afternoon"), True),
        ((date(2026, 10, 12), "afternoon"), False),  # Monday only until 13.00
        ((date(2026, 10, 12), "morning"), True),
        ((date(2026, 10, 12), "evening"), False),
    ],
)
def test_time_window_rules(window, ok):
    if ok:
        services.validate_time_window(*window)
    else:
        with pytest.raises(ValidationError):
            services.validate_time_window(*window)


def test_window_errors_name_their_position():
    found = errors(time_windows=[(TUESDAY, "afternoon"), (SATURDAY, "any")])
    assert set(found) == {"window_2"}


@pytest.mark.parametrize("count", [0, 4])
def test_one_to_three_windows(count):
    windows = [(TUESDAY + timedelta(days=i), "any") for i in range(count)]
    assert "time_windows" in errors(time_windows=windows)


def test_same_window_twice_is_rejected():
    assert "window_2" in errors(time_windows=[(TUESDAY, "any"), (TUESDAY, "any")])


def test_type_not_bookable_online_is_rejected_on_web_and_phone_but_not_for_staff(staff):
    substitution = AppointmentType.objects.get(name="Substitution")
    assert "appointment_type" in errors(appointment_type=substitution)
    assert "appointment_type" in errors(
        appointment_type=substitution, channel=Channel.PHONE_ASSISTANT
    )
    request = submit(appointment_type=substitution, channel=Channel.STAFF, actor=staff)
    assert request.status == Status.OPEN


def test_inactive_type_is_rejected_even_for_staff(staff):
    inactive = AppointmentType.objects.get(name="Sprechstunde")
    inactive.is_active = False
    inactive.save()
    assert "appointment_type" in errors(
        appointment_type=inactive, channel=Channel.STAFF, actor=staff
    )


def test_preferred_resource_must_be_an_active_doctor():
    assert submit(preferred_resource=DoctorFactory()).preferred_resource is not None
    assert "preferred_resource" in errors(preferred_resource=DoctorFactory(is_active=False))
    assert "preferred_resource" in errors(preferred_resource=DoctorFactory(kind="room"))


@pytest.mark.parametrize(
    ("born", "ok"),
    [
        (date(2026, 10, 5), True),  # a baby born today
        (date(2026, 10, 6), False),  # tomorrow
        (date(1896, 12, 31), True),  # 130 years back
        (date(1895, 12, 31), False),
    ],
)
def test_date_of_birth(born, ok):
    if ok:
        submit(patient_date_of_birth=born)
    else:
        assert "patient_date_of_birth" in errors(patient_date_of_birth=born)


@pytest.mark.parametrize(
    ("name", "relationship", "ok"),
    [
        ("", "", True),
        ("Max Beispiel", "Vater", True),
        ("Max Beispiel", "", False),
        ("", "Vater", False),
    ],
)
def test_contact_for_another_person_needs_name_and_relationship(name, relationship, ok):
    if ok:
        submit(contact_name=name, contact_relationship=relationship)
    else:
        assert "contact_name" in errors(contact_name=name, contact_relationship=relationship)


def test_web_needs_email_but_phone_assistant_does_not(commit, mailoutbox):
    assert "email" in errors(email="")
    with commit():
        request = submit(email="", channel=Channel.PHONE_ASSISTANT)
    assert request.status == Status.OPEN
    assert request.events.get().actor_kind == "assistant"
    # Only the practice hears of it; there is no address for the patient.
    assert [m.to for m in mailoutbox] == [["praxis@example.invalid"]]


def test_phone_assistant_with_email_verifies_like_the_web():
    assert submit(channel=Channel.PHONE_ASSISTANT).status == Status.UNVERIFIED


def test_phone_assistant_takes_no_note():
    assert "note" in errors(channel=Channel.PHONE_ASSISTANT, note="Probe")


def test_database_rejects_web_request_without_email():
    request = submit()
    with pytest.raises(IntegrityError):
        AppointmentRequest.objects.filter(pk=request.pk).update(email="")


def test_staff_request_starts_open_and_is_logged(staff):
    request = submit(channel=Channel.STAFF, actor=staff)
    assert request.status == Status.OPEN
    assert request.events.get().actor == staff
    assert AccessLogEntry.objects.get().action == "create"


def test_staff_channel_needs_an_account():
    with pytest.raises(ValueError):
        submit(channel=Channel.STAFF)


# --- Transitions ---------------------------------------------------------


def test_verify_opens_the_request(commit, mailoutbox):
    request = open_request(commit, mailoutbox)
    assert request.status == Status.OPEN
    assert request.email_verified_at == NOW
    # Frozen clock: both events have the same time, so compare without order.
    assert set(request.events.values_list("from_status", "to_status")) == {
        ("", "unverified"),
        ("unverified", "open"),
    }


def test_confirm_books_and_logs(commit, mailoutbox, staff):
    request = open_request(commit, mailoutbox)
    doctor = DoctorFactory()
    start = berlin(2026, 10, 6, 15, 0)
    appointment = services.confirm_request(request, start, actor=staff, resources=[doctor])
    request.refresh_from_db()
    assert request.status == Status.SCHEDULED
    assert appointment.status == "booked"
    assert appointment.end == start + timedelta(minutes=15)  # default duration
    assert list(appointment.resources.all()) == [doctor]
    assert AccessLogEntry.objects.filter(action="update", object_id=str(request.pk)).exists()
    assert request.events.filter(appointment=appointment, to_status="booked").exists()


def test_appointment_must_be_in_the_future_and_end_after_it_starts(commit, mailoutbox, staff):
    request = open_request(commit, mailoutbox)
    with pytest.raises(ValidationError):
        services.confirm_request(request, NOW, actor=staff)
    start = berlin(2026, 10, 6, 15)
    with pytest.raises(ValidationError):
        services.confirm_request(request, start, end=start, actor=staff)
    request.refresh_from_db()
    assert request.status == Status.OPEN


@pytest.mark.parametrize("status", ["unverified", "scheduled", "declined", "withdrawn", "expired"])
def test_practice_steps_need_an_open_request(status, staff):
    request = submit()
    AppointmentRequest.objects.filter(pk=request.pk).update(status=status)
    for step in (
        lambda: services.confirm_request(request, berlin(2026, 10, 6, 15), actor=staff),
        lambda: services.propose_appointment(request, berlin(2026, 10, 6, 15), actor=staff),
        lambda: services.decline_request(request, actor=staff),
    ):
        with pytest.raises(services.TransitionNotAllowed):
            step()


def test_practice_steps_need_an_account(commit, mailoutbox):
    request = open_request(commit, mailoutbox)
    with pytest.raises(ValueError):
        services.decline_request(request, actor=None)


def test_decline_closes_the_request(commit, mailoutbox, staff):
    request = open_request(commit, mailoutbox)
    services.decline_request(request, actor=staff)
    request.refresh_from_db()
    assert (request.status, request.closed_at) == (Status.DECLINED, NOW)
    assert request.events.get(to_status="declined").reason == "please_call"


def test_decline_rejects_patient_reasons(commit, mailoutbox, staff):
    request = open_request(commit, mailoutbox)
    with pytest.raises(ValidationError):
        services.decline_request(request, actor=staff, reason="treated_elsewhere")


def test_only_one_active_appointment_per_request(commit, mailoutbox, staff):
    request = open_request(commit, mailoutbox)
    appointment = services.confirm_request(request, berlin(2026, 10, 6, 15), actor=staff)
    with pytest.raises(IntegrityError):
        Appointment.objects.create(
            request=request,
            appointment_type=appointment.appointment_type,
            start=appointment.start,
            end=appointment.end,
            status="proposed",
            proposal_expires_at=appointment.start,
        )


def test_practice_cancels_booked_and_may_reopen(commit, mailoutbox, staff):
    request = open_request(commit, mailoutbox)
    appointment = services.confirm_request(request, berlin(2026, 10, 6, 15), actor=staff)
    services.cancel_appointment(appointment, actor=staff)
    request.refresh_from_db()
    appointment.refresh_from_db()
    assert request.status == Status.SCHEDULED
    assert (appointment.status, appointment.cancelled_by) == ("cancelled", "practice")
    assert appointment.cancellation_reason == "practice_unavailable"

    second = open_request(commit, mailoutbox)
    booked = services.confirm_request(second, berlin(2026, 10, 6, 15), actor=staff)
    services.cancel_appointment(booked, actor=staff, reopen=True)
    second.refresh_from_db()
    assert second.status == Status.OPEN


def test_withdrawing_a_proposal_always_reopens(commit, mailoutbox, staff):
    request = open_request(commit, mailoutbox)
    proposal = services.propose_appointment(request, berlin(2026, 10, 6, 15), actor=staff)
    services.cancel_appointment(proposal, actor=staff, reason="")
    request.refresh_from_db()
    proposal.refresh_from_db()
    assert request.status == Status.OPEN
    assert proposal.cancellation_reason == "proposal_withdrawn"


def test_cancelled_appointment_cannot_be_cancelled_again(commit, mailoutbox, staff):
    request = open_request(commit, mailoutbox)
    appointment = services.confirm_request(request, berlin(2026, 10, 6, 15), actor=staff)
    services.cancel_appointment(appointment, actor=staff)
    with pytest.raises(services.TransitionNotAllowed):
        services.cancel_appointment(appointment, actor=staff)


def test_patient_cancellation_by_phone_is_entered_by_staff(commit, mailoutbox, staff):
    request = open_request(commit, mailoutbox)
    appointment = services.confirm_request(request, berlin(2026, 10, 6, 15), actor=staff)
    mailoutbox.clear()
    with commit():
        services.cancel_appointment(
            appointment,
            actor=staff,
            cancelled_by="patient",
            channel="phone",
            reason="no_longer_fits",
        )
    appointment.refresh_from_db()
    assert (appointment.cancelled_by, appointment.cancellation_channel) == ("patient", "phone")
    # The patient called; no mail about their own cancellation from the practice.
    assert mailoutbox == []


def test_system_cancellations_are_not_for_staff(commit, mailoutbox, staff):
    request = open_request(commit, mailoutbox)
    appointment = services.confirm_request(request, berlin(2026, 10, 6, 15), actor=staff)
    with pytest.raises(ValueError):
        services.cancel_appointment(appointment, actor=staff, cancelled_by="system")


def test_events_hold_no_free_text():
    """A new field here needs a reason; names and notes never belong in it."""
    assert {f.name for f in AppointmentEvent._meta.get_fields()} == {
        "id",
        "request",
        "appointment",
        "at",
        "actor_kind",
        "actor",
        "from_status",
        "to_status",
        "reason",
    }


def test_database_rejects_staff_event_without_account():
    request = submit()
    with pytest.raises(IntegrityError):
        AppointmentEvent.objects.create(request=request, at=NOW, actor_kind="staff", to_status="x")
