"""Master data pages for the team (#26).

Every page checks the role first and logs afterwards (`audit.log`): opening a
patient is a `view` with `patient_id`, a search one `search` entry with the
number of hits and never the terms. Unknown patients answer 404.
"""

from django.contrib import messages
from django.contrib.auth.decorators import login_required, permission_required
from django.core.exceptions import ValidationError
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_POST

from audit.log import log_access
from patients import services
from patients.forms import IdentifierForm, NewPatientForm, PatientForm, SearchForm
from patients.models import Patient, PatientIdentifier


def _master_data(form) -> dict:
    return {f: form.cleaned_data[f] for f in form.Meta.fields}


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
    patient = get_object_or_404(Patient, pk=pk)
    log_access(request.user, "view", patient, patient_id=patient.pk)
    return render(
        request,
        "patients/detail.html",
        {
            "patient": patient,
            "identifiers": patient.identifiers.all(),
            "history": patient.history.select_related("changed_by"),
            "care_team": patient.care_team.filter(valid_until=None).select_related("user"),
            "identifier_form": IdentifierForm(),
        },
    )


@login_required
@permission_required("patients.change_patient", raise_exception=True)
@never_cache
def edit_view(request, pk):
    patient = get_object_or_404(Patient, pk=pk)
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
    patient = get_object_or_404(Patient, pk=pk)
    form = IdentifierForm(request.POST)
    if form.is_valid():
        try:
            services.add_identifier(patient, actor=request.user, **form.cleaned_data)
        except ValidationError as error:
            for message in error.messages:
                messages.error(request, message)
        else:
            messages.success(request, "Kennung hinzugefügt.")
    else:
        messages.error(request, "Bitte Art und Nummer angeben.")
    return redirect("patients:detail", pk=patient.pk)


@login_required
@permission_required("patients.change_patient", raise_exception=True)
@require_POST
def end_identifier_view(request, pk, identifier_pk):
    identifier = get_object_or_404(PatientIdentifier, pk=identifier_pk, patient_id=pk)
    try:
        services.end_identifier(identifier, actor=request.user)
    except ValidationError as error:
        for message in error.messages:
            messages.error(request, message)
    else:
        messages.success(request, "Kennung beendet.")
    return redirect("patients:detail", pk=pk)
