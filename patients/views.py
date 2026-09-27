"""Master data pages for the team (#26).

Every page checks the role first and logs afterwards (`audit.log`): opening a
patient is a `view` with `patient_id`, a search one `search` entry with the
number of hits and never the terms. Unknown patients answer 404.

A restriction (#39) closes every page of the patient with 403 for those not
released (`can_see_patient`). The detail page then shows only the lock with
the ways past it: emergency access, and releasing someone else or ending
such a release (doctors). Setting, linking and unlinking an account change
nothing anyone could read, so they work on a closed patient too. Lifting
needs the patient open, so a doctor who is not released first opens an
emergency access with a reason.
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db.models import F
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST

from audit.log import log_access
from patients import services
from patients.forms import (
    CareTeamForm,
    ConsentForm,
    EmergencyAccessForm,
    IdentifierForm,
    LinkAccountForm,
    NewPatientForm,
    PatientForm,
    SearchForm,
)
from patients.models import (
    EMERGENCY_ACCESS_MINUTES,
    CareTeamMember,
    ConsentArea,
    ConsentToShare,
    Patient,
    PatientIdentifier,
    can_see_patient,
    emergency_notices,
    is_on_care_team,
)


def _master_data(form) -> dict:
    return {f: form.cleaned_data[f] for f in form.Meta.fields}


def _open_patient(pk) -> Patient:
    """Unknown 404; returned also when closed by a restriction, for the lock page."""
    return get_object_or_404(Patient, pk=pk)


def _patient(request, pk) -> Patient:
    """The patient, if no restriction closes it for the user (else 403)."""
    patient = _open_patient(pk)
    if not can_see_patient(request.user, patient):
        raise PermissionDenied
    return patient


def _locked(request, patient):
    """The lock page: name and date of birth, as the search shows them, nothing else."""
    user = request.user
    context = {"patient": patient, "emergency_minutes": EMERGENCY_ACCESS_MINUTES}
    if user.has_perm("patients.view_consenttoshare"):
        # Who is released, so a withdrawn release can be ended (#39).
        context["releases"] = patient.consents.filter(
            area=ConsentArea.RESTRICTED, ended_at__isnull=True
        ).select_related("user")
    if user.has_perm("patients.add_consenttoshare"):
        context["consent_form"] = ConsentForm(actor=user, areas=[ConsentArea.RESTRICTED])
    return render(request, "patients/locked.html", context, status=403)


@login_required
@permission_required("patients.view_patient", raise_exception=True)
@never_cache
def search_view(request):
    form = SearchForm(request.GET or None)
    hits = None
    if form.is_bound and form.is_valid():
        hits = services.search_patients(actor=request.user, **form.cleaned_data)
    return render(request, "patients/search.html", {"form": form, "hits": hits})


@login_required
@permission_required("patients.add_patient", raise_exception=True)
@never_cache
def create_view(request):
    form = NewPatientForm(request.POST or None)
    duplicates = []
    if request.method == "POST" and form.is_valid():
        data = _master_data(form)
        duplicates = services.find_duplicates(
            given_name=data["given_name"],
            family_name=data["family_name"],
            birth_name=data["birth_name"],
            date_of_birth=data["date_of_birth"],
        )
        log_access(request.user, "search", Patient, result_count=len(duplicates))
        unseen = {str(p.pk) for p in duplicates} - form.seen_ids()
        if not duplicates or (form.cleaned_data["not_a_duplicate"] and not unseen):
            patient = services.create_patient(data, actor=request.user)
            messages.success(request, "Patient angelegt.")
            return redirect("patients:detail", pk=patient.pk)
        form = NewPatientForm(
            data={
                **request.POST.dict(),
                "not_a_duplicate": "",
                "duplicates_seen": ",".join(str(p.pk) for p in duplicates),
            }
        )
        form.is_valid()
    return render(request, "patients/create.html", {"form": form, "duplicates": duplicates})


@login_required
@permission_required("patients.view_patient", raise_exception=True)
@never_cache
def detail_view(request, pk):
    patient = _open_patient(pk)
    user = request.user
    if not can_see_patient(user, patient):
        return _locked(request, patient)
    context = {
        "patient": patient,
        "identifiers": patient.identifiers.all(),
        "history": patient.history.select_related("changed_by"),
        "identifier_form": IdentifierForm(),
        "emergency_notices": emergency_notices(user, patient),
    }
    if user.has_perm("patients.link_account") and patient.user_id is None:
        context["link_form"] = LinkAccountForm()
    # Who treats a patient, and in which protected area, is itself clinical
    # (#38): the team only for those who see this chart, consents only for
    # those who keep them. Same rule as `records.access.can_view_chart`,
    # which `patients` does not import.
    sees_chart = user.has_perm("records.view_chartentry") and (
        user.has_perm("records.view_all_patients") or is_on_care_team(user, patient)
    )
    context["sees_chart"] = sees_chart
    if sees_chart:
        context["care_team"] = patient.care_team.select_related("user").order_by(
            F("valid_until").asc(nulls_first=True), "-valid_from"
        )
        if user.has_perm("patients.add_careteammember"):
            context["care_team_form"] = CareTeamForm(patient=patient)
    if user.has_perm("patients.view_consenttoshare"):
        context["consents"] = patient.consents.select_related("user", "granted_by", "ended_by")
        if user.has_perm("patients.add_consenttoshare"):
            context["consent_form"] = ConsentForm(actor=user)
    log_access(user, "view", patient, patient_id=patient.pk)
    return render(request, "patients/detail.html", context)


@login_required
@permission_required("patients.change_patient", raise_exception=True)
@never_cache
def edit_view(request, pk):
    patient = _patient(request, pk)
    form = PatientForm(request.POST or None, instance=patient)
    if request.method == "POST" and form.is_valid():
        changed = services.update_patient(patient, _master_data(form), actor=request.user)
        messages.success(request, "Gespeichert." if changed else "Keine Änderung.")
        return redirect("patients:detail", pk=patient.pk)
    log_access(request.user, "view", patient, patient_id=patient.pk)
    return render(request, "patients/edit.html", {"form": form, "patient": patient})


@login_required
@permission_required("patients.change_patient", raise_exception=True)
@require_POST
def add_identifier_view(request, pk):
    patient = _patient(request, pk)
    form = IdentifierForm(request.POST)
    if form.is_valid():
        try:
            services.add_identifier(patient, actor=request.user, **form.cleaned_data)
        except ValidationError as error:
            _show_errors(request, error)
        else:
            messages.success(request, "Kennung hinzugefügt.")
    else:
        messages.error(request, "Bitte Art und Nummer angeben.")
    return redirect("patients:detail", pk=patient.pk)


@login_required
@permission_required("patients.change_patient", raise_exception=True)
@require_POST
def end_identifier_view(request, pk, identifier_pk):
    _patient(request, pk)
    identifier = get_object_or_404(PatientIdentifier, pk=identifier_pk, patient_id=pk)
    try:
        services.end_identifier(identifier, actor=request.user)
    except ValidationError as error:
        _show_errors(request, error)
    else:
        messages.success(request, "Kennung beendet.")
    return redirect("patients:detail", pk=pk)


def _show_errors(request, error: ValidationError):
    for message in error.messages:
        messages.error(request, message)


@login_required
@permission_required("patients.add_careteammember", raise_exception=True)
@require_POST
def add_care_team_view(request, pk):
    patient = _patient(request, pk)
    form = CareTeamForm(request.POST, patient=patient)
    if form.is_valid():
        try:
            services.add_care_team_member(patient, form.cleaned_data["user"], actor=request.user)
        except ValidationError as error:
            _show_errors(request, error)
        else:
            messages.success(request, "Ins Behandlungsteam eingetragen.")
    else:
        messages.error(request, "Bitte eine Person wählen.")
    return redirect("patients:detail", pk=patient.pk)


@login_required
@permission_required("patients.change_careteammember", raise_exception=True)
@require_POST
def end_care_team_view(request, pk, member_pk):
    _patient(request, pk)
    member = get_object_or_404(CareTeamMember, pk=member_pk, patient_id=pk)
    try:
        services.end_care_team_member(member, actor=request.user)
    except ValidationError as error:
        _show_errors(request, error)
    else:
        messages.success(request, "Aus dem Behandlungsteam ausgetragen; ab sofort ohne Zugang.")
    return redirect("patients:detail", pk=pk)


@login_required
@permission_required("patients.add_consenttoshare", raise_exception=True)
@require_POST
def add_consent_view(request, pk):
    patient = _open_patient(pk)
    # On a closed patient a doctor may only release someone else for the
    # restriction (four eyes, #39), without seeing anything.
    locked = not can_see_patient(request.user, patient)
    areas = [ConsentArea.RESTRICTED] if locked else None
    form = ConsentForm(request.POST, actor=request.user, areas=areas)
    if form.is_valid():
        try:
            services.grant_consent(patient, actor=request.user, **form.cleaned_data)
        except ValidationError as error:
            _show_errors(request, error)
        else:
            messages.success(request, "Freigabe eingetragen.")
    else:
        messages.error(request, "Bitte Bereich und Person wählen und das Datum prüfen.")
    return redirect("patients:detail", pk=patient.pk)


@login_required
@permission_required("patients.change_consenttoshare", raise_exception=True)
@require_POST
def end_consent_view(request, pk, consent_pk):
    patient = _open_patient(pk)
    consent = get_object_or_404(ConsentToShare, pk=consent_pk, patient_id=pk)
    # On a closed patient only a release of the restriction, as on the lock page.
    if consent.area != ConsentArea.RESTRICTED and not can_see_patient(request.user, patient):
        raise PermissionDenied
    try:
        services.end_consent(consent, actor=request.user)
    except ValidationError as error:
        _show_errors(request, error)
    else:
        messages.success(request, "Freigabe beendet; ab sofort ohne Wirkung.")
    return redirect("patients:detail", pk=pk)


# --- Restriction, staff as patients, emergency access (#39) ------------------


def _change_restriction(request, pk, change, success, *, needs_open=False):
    patient = _patient(request, pk) if needs_open else _open_patient(pk)
    try:
        change(patient, actor=request.user)
    except ValidationError as error:
        _show_errors(request, error)
    else:
        messages.success(request, success)
    return redirect("patients:detail", pk=pk)


@login_required
@permission_required("patients.restrict_patient", raise_exception=True)
@require_POST
def restrict_view(request, pk):
    return _change_restriction(
        request,
        pk,
        services.set_restriction,
        "Sperrvermerk gesetzt; ab sofort sehen nur freigegebene Personen den Patienten.",
    )


@login_required
@permission_required("patients.lift_restriction", raise_exception=True)
@require_POST
def lift_restriction_view(request, pk):
    # Only with the patient open: released, or after an emergency access
    # with a reason. Otherwise lifting would be a way past it without one.
    return _change_restriction(
        request, pk, services.lift_restriction, "Sperrvermerk aufgehoben.", needs_open=True
    )


@login_required
@permission_required("patients.link_account", raise_exception=True)
@require_POST
def link_account_view(request, pk):
    patient = _open_patient(pk)
    form = LinkAccountForm(request.POST)
    if form.is_valid():
        try:
            services.link_account(patient, form.cleaned_data["user"], actor=request.user)
        except ValidationError as error:
            _show_errors(request, error)
        else:
            messages.success(request, "Mit dem Konto verknüpft; der Sperrvermerk ist gesetzt.")
    else:
        messages.error(request, "Bitte ein Konto wählen.")
    return redirect("patients:detail", pk=pk)


@login_required
@permission_required("patients.link_account", raise_exception=True)
@require_POST
def unlink_account_view(request, pk):
    return _change_restriction(
        request,
        pk,
        services.unlink_account,
        "Verknüpfung mit dem Konto entfernt; der Sperrvermerk bleibt.",
    )


@login_required
@permission_required("patients.add_emergencyaccess", raise_exception=True)
@never_cache
def emergency_view(request, pk):
    """A doctor opens a restriction with a reason, for 60 minutes; then on to the chart."""
    patient = _open_patient(pk)
    form = EmergencyAccessForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            emergency = services.open_emergency_access(
                patient, reason=form.cleaned_data["reason"], actor=request.user
            )
        except ValidationError as error:
            _show_errors(request, error)
        else:
            until = timezone.localtime(emergency.valid_until)
            messages.success(request, f"Notfallzugriff bis {until:%H:%M} Uhr, protokolliert.")
            return redirect("records:chart", pk=patient.pk)
    return render(
        request,
        "patients/emergency.html",
        {"patient": patient, "form": form, "emergency_minutes": EMERGENCY_ACCESS_MINUTES},
    )
