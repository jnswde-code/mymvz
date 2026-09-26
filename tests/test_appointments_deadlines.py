"""Deletion dates and deadlines, at the boundary and in Europe/Berlin (#5 section 6)."""

from datetime import date, timedelta

import pytest
import time_machine

from accounts.testing import make_user
from appointments import services
from appointments.deadlines import add_working_days, cancellation_deadline
from appointments.models import Appointment, AppointmentRequest, Channel
from tests.conftest import berlin, token_from
from tests.factories import request_data

pytestmark = pytest.mark.django_db

Status = AppointmentRequest.Status
DAYS_30 = timedelta(days=30)


@pytest.fixture
def staff():
    return make_user("max.probe")


def staff_request(staff, windows=None, **overrides):
    """Open right away, without mails in the way."""
    data = request_data(**overrides)
    if windows:
        data["time_windows"] = windows
    return services.submit_request(data, channel=Channel.STAFF, actor=staff)


# --- compute_delete_after, one case per status -----------------------------


def test_unverified_is_deleted_24_hours_after_creation():
    with time_machine.travel(berlin(2026, 10, 5, 10), tick=False):
        request = services.submit_request(request_data())
    assert request.delete_after == berlin(2026, 10, 6, 10)


def test_open_has_no_deletion_date(staff):
    with time_machine.travel(berlin(2026, 10, 5, 10), tick=False):
        assert staff_request(staff).delete_after is None


@pytest.mark.parametrize("step", ["decline", "withdraw"])
def test_closed_requests_go_30_days_after_closing(staff, commit, mailoutbox, step):
    """Expired requests: see test_request_expires_the_day_after_its_last_wish_day."""
    with time_machine.travel(berlin(2026, 10, 5, 10), tick=False), commit():
        request = staff_request(staff)
    # The only wish day is 6 Oct; the withdraw link works until its end.
    with time_machine.travel(berlin(2026, 10, 6, 9), tick=False):
        if step == "decline":
            services.decline_request(request, actor=staff)
        else:
            services.withdraw_request(token_from(mailoutbox[-1]))
    request.refresh_from_db()
    assert request.status in (Status.DECLINED, Status.WITHDRAWN)
    assert request.delete_after == berlin(2026, 11, 5, 9)


def test_booked_goes_30_days_after_the_end_and_so_does_the_appointment(staff):
    with time_machine.travel(berlin(2026, 10, 5, 10), tick=False):
        request = staff_request(staff)
        appointment = services.confirm_request(
            request, berlin(2026, 10, 6, 15), actor=staff, end=berlin(2026, 10, 6, 15, 30)
        )
    request.refresh_from_db()
    appointment.refresh_from_db()
    assert request.delete_after == berlin(2026, 11, 5, 15, 30)
    assert appointment.delete_after == request.delete_after


def test_pending_proposal_has_no_deletion_date(staff):
    with time_machine.travel(berlin(2026, 10, 5, 10), tick=False):
        request = staff_request(staff)
        services.propose_appointment(request, berlin(2026, 10, 6, 15), actor=staff)
    request.refresh_from_db()
    assert request.delete_after is None


def test_cancelled_without_reopening_goes_30_days_after_the_cancellation(staff):
    with time_machine.travel(berlin(2026, 10, 5, 10), tick=False):
        request = staff_request(staff)
        appointment = services.confirm_request(request, berlin(2026, 10, 20, 15), actor=staff)
    with time_machine.travel(berlin(2026, 10, 7, 12), tick=False):
        services.cancel_appointment(appointment, actor=staff)
    request.refresh_from_db()
    appointment.refresh_from_db()
    assert request.status == Status.SCHEDULED
    assert request.delete_after == berlin(2026, 11, 6, 12)
    assert appointment.delete_after == request.delete_after


def test_reopened_request_keeps_its_old_appointments_undated_until_it_ends(staff):
    """Cancelled appointments follow their request, also back to open and on to closed."""
    with time_machine.travel(berlin(2026, 10, 5, 10), tick=False):
        request = staff_request(staff)
        appointment = services.confirm_request(request, berlin(2026, 10, 20, 15), actor=staff)
        services.cancel_appointment(appointment, actor=staff, reopen=True)
        appointment.refresh_from_db()
        assert appointment.delete_after is None
        services.decline_request(request, actor=staff)
    appointment.refresh_from_db()
    assert appointment.delete_after == berlin(2026, 11, 4, 10)


def test_deletion_date_across_the_change_to_winter_time(staff):
    """30 days are 30 calendar days in Berlin, not 30 × 24 hours in UTC."""
    with time_machine.travel(berlin(2026, 10, 5, 10), tick=False):
        request = staff_request(staff)
    with time_machine.travel(berlin(2026, 10, 20, 9), tick=False):
        services.decline_request(request, actor=staff)
    request.refresh_from_db()
    # 20 Oct is summer time (UTC+2), 19 Nov winter time (UTC+1).
    assert request.delete_after == berlin(2026, 11, 19, 9)


# --- Working days and the cancellation deadline ------------------------------


@pytest.mark.parametrize(
    ("start", "expected"),
    [
        (berlin(2026, 10, 5, 10), berlin(2026, 10, 7, 10)),  # Mon → Wed
        (berlin(2026, 10, 8, 10), berlin(2026, 10, 12, 10)),  # Thu → Mon
        (berlin(2026, 10, 9, 10), berlin(2026, 10, 13, 10)),  # Fri → Tue
        (berlin(2026, 10, 10, 10), berlin(2026, 10, 13, 10)),  # Sat → Tue
        (berlin(2026, 10, 23, 15), berlin(2026, 10, 27, 15)),  # Fri → Tue over winter time
        (berlin(2026, 3, 27, 2, 30), berlin(2026, 3, 31, 2, 30)),  # over summer time
        (berlin(2026, 12, 30, 23, 30), berlin(2027, 1, 1, 23, 30)),  # year end, midnight
    ],
)
def test_add_two_working_days_keeps_the_local_clock(start, expected):
    assert add_working_days(start, 2) == expected


def test_proposal_deadline_is_two_working_days_but_never_after_the_appointment(staff):
    with time_machine.travel(berlin(2026, 10, 9, 16), tick=False):  # Friday
        late = services.propose_appointment(
            staff_request(staff), berlin(2026, 10, 20, 15), actor=staff
        )
        early = services.propose_appointment(
            staff_request(staff), berlin(2026, 10, 12, 9), actor=staff
        )
    assert late.proposal_expires_at == berlin(2026, 10, 13, 16)
    assert early.proposal_expires_at == berlin(2026, 10, 12, 9)


def test_cancellation_deadline_is_24_hours_across_the_time_change():
    appointment = Appointment(start=berlin(2026, 10, 25, 10))
    # 25 Oct has 25 hours; 24 hours before is 11:00 the day before.
    assert cancellation_deadline(appointment) == berlin(2026, 10, 24, 11)


# --- Runs of the system --------------------------------------------------------


def test_request_expires_the_day_after_its_last_wish_day(staff, commit, mailoutbox):
    with time_machine.travel(berlin(2026, 10, 5, 10), tick=False):
        request = staff_request(
            staff, windows=[(date(2026, 10, 6), "afternoon"), (date(2026, 10, 7), "morning")]
        )
    # Last wish day, one minute before midnight: still open.
    with time_machine.travel(berlin(2026, 10, 7, 23, 59), tick=False):
        assert services.expire_overdue_requests() == 0
    # Midnight in Berlin is 22:00 UTC; the date must be the local one.
    with time_machine.travel(berlin(2026, 10, 8, 0, 0), tick=False), commit():
        assert services.expire_overdue_requests() == 1
    request.refresh_from_db()
    assert request.status == Status.EXPIRED
    assert request.delete_after == berlin(2026, 11, 7, 0, 0)
    assert request.events.get(to_status="expired").actor_kind == "system"
    assert mailoutbox[-1].to == [request.email]


def test_only_open_requests_expire(staff):
    with time_machine.travel(berlin(2026, 10, 5, 10), tick=False):
        request = staff_request(staff)
        services.confirm_request(request, berlin(2026, 10, 30, 10), actor=staff)
    with time_machine.travel(berlin(2026, 10, 20, 10), tick=False):
        assert services.expire_overdue_requests() == 0
    request.refresh_from_db()
    assert request.status == Status.SCHEDULED


def test_proposal_expires_at_its_deadline_and_reopens_the_request(staff):
    with time_machine.travel(berlin(2026, 10, 5, 10), tick=False):
        request = staff_request(staff)
        proposal = services.propose_appointment(request, berlin(2026, 10, 20, 15), actor=staff)
    with time_machine.travel(berlin(2026, 10, 7, 9, 59), tick=False):
        assert services.expire_overdue_proposals() == 0
    with time_machine.travel(berlin(2026, 10, 7, 10, 0), tick=False):
        assert services.expire_overdue_proposals() == 1
    proposal.refresh_from_db()
    request.refresh_from_db()
    assert (proposal.status, proposal.cancelled_by) == ("cancelled", "system")
    assert proposal.cancellation_reason == "proposal_expired"
    assert request.status == Status.OPEN
