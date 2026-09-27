"""Request and appointment pages for the team under /anfragen/ (#8).

Kept apart from the pages for patients (`views.py`), which need no login:
here every view needs a role, and a forgotten decorator in a shared file
would leave a request open to anyone. Every view checks the role first; only
then does a service read and log (`list`, `view`) or change and log
(`update`). Unknown and unconfirmed requests answer 404. Every step is a
POST; a request that moved on meanwhile (`TransitionNotAllowed`) becomes a
message, not a 500.

Assigning a request to a patient shows patient records, so those parts need
`patients.view_patient` on top of the right on requests.
"""

from datetime import timedelta

from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.core.exceptions import ValidationError
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST

from appointments import services
from appointments.models import (
    Appointment,
    AppointmentRequest,
    AppointmentStatus,
    Reason,
    RequestStatus,
)
from appointments.staff_forms import (
    AppointmentForm,
    AssignPatientForm,
    DeclineForm,
    ListFilterForm,
    ListTabForm,
    MedicalOfficeForm,
    PatientSearchForm,
    PhoneCancelForm,
    PracticeCancelForm,
    StaffNoteForm,
)
from patients import services as patient_services

VIEW = "appointments.view_appointmentrequest"
CHANGE = "appointments.change_appointmentrequest"
VIEW_PATIENT = "patients.view_patient"

MOVED_ON = "Die Anfrage hat sich inzwischen geändert. Bitte den aktuellen Stand prüfen."
APPOINTMENT_MOVED_ON = "Der Termin hat sich inzwischen geändert. Bitte den aktuellen Stand prüfen."
# Cancellations by patients of the last two weeks (#8).
CANCELLED_TAB_DAYS = 14
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


def _patient_context(request, found):
    """Assigned patient, suggestions and search; only with `patients.view_patient`."""
    if not request.user.has_perm(VIEW_PATIENT):
        return {}
    search_form = PatientSearchForm(request.GET if "name" in request.GET else None)
    context = {"patient_search_form": search_form, "search_results": None}
    if found.patient is None:
        context["suggestions"] = services.suggest_patients(found, actor=request.user)
    if search_form.has_terms():
        context["search_results"] = patient_services.search_patients(
            actor=request.user,
            name=search_form.cleaned_data["name"],
            date_of_birth=search_form.cleaned_data["geburtsdatum"],
        )
    return context


def _detail(
    request,
    pk,
    *,
    appointment_form=None,
    decline_form=None,
    note_form=None,
    practice_cancel_form=None,
    phone_cancel_form=None,
):
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
            "appointments": found.appointments.order_by("-created_at").prefetch_related(
                "resources"
            ),
            "practice_cancel_form": practice_cancel_form or PracticeCancelForm(),
            "phone_cancel_form": phone_cancel_form or PhoneCancelForm(),
            **_patient_context(request, found),
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


# --- Appointments: cancel, withdraw, Medical Office ---------------------------


def _appointment_target(pk, appointment_pk):
    """An appointment of a visible request; 404 if it belongs to another one."""
    return get_object_or_404(
        Appointment.objects.filter(request__in=services.staff_visible()),
        pk=appointment_pk,
        request_id=pk,
    )


def _cancel_step(
    request, pk, appointment_pk, form, *, form_key, done, warn_without_email=False, **kwargs
):
    appointment = _appointment_target(pk, appointment_pk)
    if not form.is_valid():
        return _detail(request, pk, **{form_key: form})
    try:
        services.cancel_appointment(
            appointment,
            actor=request.user,
            reason=form.cleaned_data["reason"],
            reopen=form.cleaned_data["reopen"],
            expected_status=AppointmentStatus.BOOKED,
            **kwargs,
        )
    except services.TransitionNotAllowed:
        messages.error(request, APPOINTMENT_MOVED_ON)
    else:
        messages.success(request, done)
        if warn_without_email and not appointment.request.email:
            messages.warning(request, NO_MAIL)
    return redirect("appointments_staff:detail", pk=pk)


@login_required
@permission_required(CHANGE, raise_exception=True)
@never_cache
@require_POST
def cancel_view(request, pk, appointment_pk):
    """The practice cancels a booked appointment; the patient gets a mail if possible."""
    return _cancel_step(
        request,
        pk,
        appointment_pk,
        PracticeCancelForm(request.POST),
        form_key="practice_cancel_form",
        done="Termin abgesagt.",
        warn_without_email=True,
        cancelled_by=Appointment.CancelledBy.PRACTICE,
        channel=Appointment.CancellationChannel.BACKOFFICE,
    )


@login_required
@permission_required(CHANGE, raise_exception=True)
@never_cache
@require_POST
def phone_cancel_view(request, pk, appointment_pk):
    """A patient called to cancel; no mail."""
    return _cancel_step(
        request,
        pk,
        appointment_pk,
        PhoneCancelForm(request.POST),
        form_key="phone_cancel_form",
        done="Absage am Telefon eingetragen.",
        cancelled_by=Appointment.CancelledBy.PATIENT,
        channel=Appointment.CancellationChannel.PHONE,
    )


@login_required
@permission_required(CHANGE, raise_exception=True)
@never_cache
@require_POST
def withdraw_view(request, pk, appointment_pk):
    """Withdraw an open proposal; the request is open again, no mail."""
    appointment = _appointment_target(pk, appointment_pk)
    try:
        services.cancel_appointment(
            appointment,
            actor=request.user,
            reason=Reason.PROPOSAL_WITHDRAWN,
            expected_status=AppointmentStatus.PROPOSED,
        )
    except services.TransitionNotAllowed:
        messages.error(request, APPOINTMENT_MOVED_ON)
    else:
        messages.success(request, "Vorschlag zurückgezogen, die Anfrage ist wieder offen.")
    return redirect("appointments_staff:detail", pk=pk)


def _medical_office_step(request, pk, appointment_pk, step, done):
    appointment = _appointment_target(pk, appointment_pk)
    form = MedicalOfficeForm(request.POST)
    back = form.cleaned_data["zurueck"] if form.is_valid() else ""
    try:
        step(appointment, actor=request.user)
    except services.TransitionNotAllowed:
        messages.error(request, APPOINTMENT_MOVED_ON)
    else:
        messages.success(request, done)
    if back:
        return redirect(f"{reverse('appointments_staff:appointments')}?zeige={back}")
    return redirect("appointments_staff:detail", pk=pk)


@login_required
@permission_required(CHANGE, raise_exception=True)
@never_cache
@require_POST
def entered_view(request, pk, appointment_pk):
    return _medical_office_step(
        request,
        pk,
        appointment_pk,
        services.mark_entered_in_medical_office,
        "In Medical Office eingetragen.",
    )


@login_required
@permission_required(CHANGE, raise_exception=True)
@never_cache
@require_POST
def removed_view(request, pk, appointment_pk):
    return _medical_office_step(
        request,
        pk,
        appointment_pk,
        services.mark_removed_from_medical_office,
        "Aus Medical Office ausgetragen.",
    )


@login_required
@permission_required(VIEW, raise_exception=True)
@never_cache
@require_GET
def appointment_list_view(request):
    shown = ListTabForm(request.GET).selected()
    filters = {
        ListTabForm.TO_ENTER: {"to_enter": True},
        ListTabForm.TO_REMOVE: {"to_remove": True},
        ListTabForm.UPCOMING: {},
        ListTabForm.CANCELLED: {
            "cancelled_by_patient_since": timezone.now() - timedelta(days=CANCELLED_TAB_DAYS)
        },
    }[shown]
    return render(
        request,
        "appointments/staff/appointments.html",
        {
            "appointments": services.list_appointments(request.user, **filters),
            "shown": shown,
            "choices": ListTabForm.CHOICES,
        },
    )


# --- Assignment to a patient (#5 section 4) ----------------------------------


@login_required
@permission_required([CHANGE, VIEW_PATIENT], raise_exception=True)
@never_cache
@require_POST
def assign_view(request, pk):
    """A human confirms which patient the request belongs to."""
    target = _target(pk)
    form = AssignPatientForm(request.POST)
    if not form.is_valid():
        messages.error(request, "Diesen Patienten gibt es nicht (mehr).")
        return redirect("appointments_staff:detail", pk=pk)
    services.assign_patient(target, form.cleaned_data["patient"], actor=request.user)
    messages.success(request, "Anfrage dem Patienten zugeordnet.")
    return redirect("appointments_staff:detail", pk=pk)


@login_required
@permission_required([CHANGE, VIEW_PATIENT], raise_exception=True)
@never_cache
@require_POST
def unassign_view(request, pk):
    target = _target(pk)
    services.assign_patient(target, None, actor=request.user)
    messages.success(request, "Zuordnung aufgehoben.")
    return redirect("appointments_staff:detail", pk=pk)
