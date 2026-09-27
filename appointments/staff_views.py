"""Request pages for the team under /anfragen/ (#8).

Kept apart from the pages for patients (`views.py`), which need no login:
here every view needs a role, and a forgotten decorator in a shared file
would leave a request open to anyone. Every view checks the role first; only
then does a service read and log (`list`, `view`) or change and log
(`update`). Unknown and unconfirmed requests answer 404. Every step is a
POST; a request that moved on meanwhile (`TransitionNotAllowed`) becomes a
message, not a 500.
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.core.exceptions import ValidationError
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST

from appointments import services
from appointments.models import AppointmentRequest, AppointmentStatus, RequestStatus
from appointments.staff_forms import AppointmentForm, DeclineForm, ListFilterForm, StaffNoteForm

VIEW = "appointments.view_appointmentrequest"
CHANGE = "appointments.change_appointmentrequest"

MOVED_ON = "Die Anfrage hat sich inzwischen geändert. Bitte den aktuellen Stand prüfen."
NO_MAIL = "Kein Versand, die Anfrage hat keine E-Mail-Adresse: bitte anrufen."


# Events hold the raw values of both status lists.
STATUS_LABELS = {**dict(RequestStatus.choices), **dict(AppointmentStatus.choices)}


def _annotate(request, today):
    request.flags = services.request_flags(request, today)
    if request.status == RequestStatus.OPEN:
        request.open_working_days = services.open_working_days(request, today)
    return request


@login_required
@permission_required(VIEW, raise_exception=True)
@never_cache
@require_GET
def list_view(request):
    shown = ListFilterForm(request.GET).selected()
    if shown == ListFilterForm.ALL:
        requests = services.list_requests(request.user, status=None)
    else:
        requests = services.list_requests(
            request.user, needs_callback=shown == ListFilterForm.CALLBACK
        )
    today = timezone.localdate()
    return render(
        request,
        "appointments/staff/list.html",
        {
            "requests": [_annotate(r, today) for r in requests],
            "shown": shown,
            "choices": ListFilterForm.CHOICES,
        },
    )


def _detail(request, pk, *, appointment_form=None, decline_form=None, note_form=None):
    try:
        found = services.get_request(pk, request.user)
    except AppointmentRequest.DoesNotExist:
        raise Http404 from None
    first_window = found.time_windows.first()
    events = list(found.events.select_related("actor"))
    for event in events:
        event.from_label = STATUS_LABELS.get(event.from_status, "neu")
        event.to_label = STATUS_LABELS.get(event.to_status, event.to_status)
    return render(
        request,
        "appointments/staff/detail.html",
        {
            "req": _annotate(found, timezone.localdate()),
            "time_windows": found.time_windows.all(),
            "events": events,
            "active_appointment": found.active_appointment,
            "appointment_form": appointment_form
            or AppointmentForm(
                initial={
                    "day": first_window.date if first_window else None,
                    "doctor": found.preferred_resource,
                }
            ),
            "decline_form": decline_form or DeclineForm(),
            "note_form": note_form or StaffNoteForm(initial={"staff_note": found.staff_note}),
        },
    )


@login_required
@permission_required(VIEW, raise_exception=True)
@never_cache
@require_GET
def detail_view(request, pk):
    return _detail(request, pk)


def _target(pk):
    """The request for a step, without a `view` entry: the service logs `update`."""
    return get_object_or_404(services.staff_visible(), pk=pk)


def _add_errors(form, error: ValidationError):
    if hasattr(error, "error_dict"):
        for field, errors in error.error_dict.items():
            form.add_error(field if field in form.fields else None, errors)
    else:
        form.add_error(None, error)


def _schedule_step(request, pk, step, done):
    target = _target(pk)
    form = AppointmentForm(request.POST)
    if form.is_valid():
        try:
            step(target, form.start(), actor=request.user, resources=form.resources())
        except services.TransitionNotAllowed:
            messages.error(request, MOVED_ON)
            return redirect("appointments_staff:detail", pk=pk)
        except ValidationError as error:
            _add_errors(form, error)
        else:
            messages.success(request, done)
            if not target.email:
                messages.warning(request, NO_MAIL)
            return redirect("appointments_staff:detail", pk=pk)
    return _detail(request, pk, appointment_form=form)


@login_required
@permission_required(CHANGE, raise_exception=True)
@never_cache
@require_POST
def confirm_view(request, pk):
    return _schedule_step(request, pk, services.confirm_request, "Termin bestätigt.")


@login_required
@permission_required(CHANGE, raise_exception=True)
@never_cache
@require_POST
def propose_view(request, pk):
    return _schedule_step(request, pk, services.propose_appointment, "Termin vorgeschlagen.")


@login_required
@permission_required(CHANGE, raise_exception=True)
@never_cache
@require_POST
def decline_view(request, pk):
    target = _target(pk)
    form = DeclineForm(request.POST)
    if not form.is_valid():
        return _detail(request, pk, decline_form=form)
    try:
        services.decline_request(target, actor=request.user, reason=form.cleaned_data["reason"])
    except services.TransitionNotAllowed:
        messages.error(request, MOVED_ON)
    else:
        messages.success(request, "Anfrage abgelehnt.")
        if not target.email:
            messages.warning(request, NO_MAIL)
    return redirect("appointments_staff:detail", pk=pk)


@login_required
@permission_required(CHANGE, raise_exception=True)
@never_cache
@require_POST
def note_view(request, pk):
    target = _target(pk)
    form = StaffNoteForm(request.POST)
    if not form.is_valid():
        return _detail(request, pk, note_form=form)
    services.set_staff_note(target, form.cleaned_data["staff_note"], actor=request.user)
    messages.success(request, "Notiz gespeichert.")
    return redirect("appointments_staff:detail", pk=pk)
