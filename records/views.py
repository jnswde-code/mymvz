"""The record pages for the team (#37, #38, #39).

Every page first checks the right to the chart (403, also for a patient
whose care team the user is not on or whose restriction is closed to them;
the chart itself then sends to the lock page), then looks the record up only among
what `access.visible_to` lets through (404, so a hidden record does not
reveal that it exists), and logs afterwards:
opening the chart is a `list` of chart entries with `patient_id`, a history
or form a `view` of the current version, each shown error a `view` of its own.
"""

from collections import defaultdict

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.cache import never_cache

from audit.log import log_access
from patients.models import EMERGENCY_ACCESS_MINUTES, Patient, emergency_notices
from records import access, services
from records.diff import word_diff
from records.forms import (
    ChartEntryForm,
    ChartEntryRevisionForm,
    EncounterForm,
    EncounterRevisionForm,
    ReasonForm,
)
from records.models import ChartEntry, Encounter, Status

# URL segment → model.
KINDS = {"kontakte": Encounter, "eintraege": ChartEntry}


def _patient(request, pk) -> Patient:
    """The patient, if the user may see this chart.

    No chart role 403, unknown patient 404, not on the care team 403.
    """
    if not access.has_chart_role(request.user):
        raise PermissionDenied
    patient = get_object_or_404(Patient, pk=pk)
    if not access.can_view_chart(request.user, patient):
        raise PermissionDenied
    return patient


def _head(request, patient, model, lineage, *, include_errors=False):
    """The newest visible version of a lineage of this patient, else 404."""
    versions = model.objects.filter(patient=patient, lineage_id=lineage).current()
    head = access.visible_to(request.user, versions, include_errors=include_errors).first()
    if head is None:
        raise Http404
    return head


def _add_errors(form, error: ValidationError):
    if hasattr(error, "error_dict"):
        for field, errors in error.error_dict.items():
            form.add_error(field if field in form.fields else None, errors)
    else:
        form.add_error(None, error)


def _chart_url(patient, **query) -> str:
    url = reverse("records:chart", args=[patient.pk])
    return url + ("?irrtuemer=1" if query.get("errors") else "")


@login_required
@never_cache
def chart_view(request, pk):
    user = request.user
    if not access.has_chart_role(user):
        raise PermissionDenied
    patient = get_object_or_404(Patient, pk=pk)
    if access.is_locked(user, patient):
        # One lock page, with emergency access and release (`patients`).
        return redirect("patients:detail", pk=patient.pk)
    if not access.can_view_chart(user, patient):
        raise PermissionDenied
    include_errors = request.GET.get("irrtuemer") == "1" and access.can_view_errors(user)
    encounters = list(
        access.visible_to(
            user, Encounter.objects.filter(patient=patient).current(), include_errors=include_errors
        ).order_by("-occurred_at", "-recorded_at")
    )
    entries = list(
        access.visible_to(
            user,
            ChartEntry.objects.filter(patient=patient).current(),
            include_errors=include_errors,
        )
        .select_related("entry_type", "recorded_by")
        .order_by("occurred_at", "recorded_at")
    )
    by_encounter = defaultdict(list)
    for entry in entries:
        by_encounter[entry.encounter_lineage_id].append(entry)
    hidden = access.hidden_entries(user, patient)
    # What an emergency access would open; never one's own record (#39).
    hidden_restricted = (
        bool(hidden) and patient.user_id != user.pk and access.hides_restricted(user, patient)
    )
    for encounter in encounters:
        encounter.entries = by_encounter.pop(encounter.lineage_id, [])
        encounter.hidden = hidden.pop(encounter.lineage_id, 0)
    # Only possible for errors shown to doctors; never hide an entry silently.
    without_encounter = [entry for group in by_encounter.values() for entry in group]
    hidden_without_encounter = sum(hidden.values())

    log_access(user, "list", ChartEntry, patient_id=patient.pk)
    for record in [*encounters, *entries]:
        if record.status == Status.ENTERED_IN_ERROR:
            log_access(user, "view", record, patient_id=patient.pk)
    return render(
        request,
        "records/chart.html",
        {
            "patient": patient,
            "encounters": encounters,
            "without_encounter": without_encounter,
            "hidden_without_encounter": hidden_without_encounter,
            "can_write": access.can_write(user, patient),
            "can_view_errors": access.can_view_errors(user),
            "include_errors": include_errors,
            "changeable": access.changeable(user, encounters) | access.changeable(user, entries),
            "emergency_notices": emergency_notices(user, patient),
            "hidden_restricted": hidden_restricted,
            "emergency_minutes": EMERGENCY_ACCESS_MINUTES,
        },
    )


def _form_page(request, patient, form, *, title, submit, record=None, back=None):
    return render(
        request,
        "records/form.html",
        {
            "patient": patient,
            "form": form,
            "title": title,
            "submit": submit,
            "record": record,
            "back": back or _chart_url(patient),
        },
    )


@login_required
@never_cache
def encounter_create_view(request, pk):
    patient = _patient(request, pk)
    if not access.can_write(request.user, patient):
        raise PermissionDenied
    form = EncounterForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        try:
            services.create_encounter(patient, actor=request.user, **form.cleaned_data)
        except ValidationError as error:
            _add_errors(form, error)
        else:
            messages.success(request, "Kontakt angelegt.")
            return redirect(_chart_url(patient))
    return _form_page(request, patient, form, title="Neuer Kontakt", submit="Anlegen")


@login_required
@never_cache
def entry_create_view(request, pk, lineage):
    patient = _patient(request, pk)
    if not access.can_write(request.user, patient):
        raise PermissionDenied
    # Without errors, so only an active contact.
    encounter = _head(request, patient, Encounter, lineage)
    form = ChartEntryForm(request.POST or None, user=request.user)
    if request.method == "POST" and form.is_valid():
        try:
            services.create_entry(encounter, actor=request.user, **form.cleaned_data)
        except ValidationError as error:
            _add_errors(form, error)
        else:
            messages.success(request, "Eintrag gespeichert.")
            return redirect(_chart_url(patient))
    log_access(request.user, "view", encounter, patient_id=patient.pk)
    return _form_page(
        request, patient, form, title="Neuer Eintrag", submit="Speichern", record=encounter
    )


def _changes(previous, version) -> list[tuple[str, str, str]]:
    """Changed fields other than the text: (label, old, new)."""
    fields = ["kind", "occurred_at"] if isinstance(version, Encounter) else ["occurred_at"]
    changes = []
    if isinstance(version, ChartEntry) and previous.entry_type_id != version.entry_type_id:
        changes.append(("Kürzel", str(previous.entry_type), str(version.entry_type)))
    for field in fields:
        old, new = getattr(previous, field), getattr(version, field)
        if old != new:
            label = version._meta.get_field(field).verbose_name
            if field == "kind":
                old, new = previous.get_kind_display(), version.get_kind_display()
            changes.append((label, old, new))
    return changes


@login_required
@never_cache
def history_view(request, pk, kind, lineage):
    patient = _patient(request, pk)
    model = KINDS[kind]
    head = _head(request, patient, model, lineage, include_errors=True)
    versions = list(
        access.visible_to(
            request.user,
            model.objects.filter(patient=patient, lineage_id=lineage),
            include_errors=True,
        )
        .select_related("recorded_by", *(["entry_type"] if model is ChartEntry else []))
        .order_by("version")
    )
    previous = None
    for version in versions:
        version.changes = _changes(previous, version) if previous else []
        if model is ChartEntry:
            changed = previous is not None and previous.text != version.text
            version.diff = word_diff(previous.text, version.text) if changed else None
        previous = version
    encounter = None
    if model is ChartEntry:
        encounter = (
            access.visible_to(
                request.user,
                Encounter.objects.filter(lineage_id=head.encounter_lineage_id).current(),
                include_errors=True,
            )
            .order_by("-version")
            .first()
        )
    log_access(request.user, "view", head, patient_id=patient.pk)
    if encounter is not None and encounter.status == Status.ENTERED_IN_ERROR:
        log_access(request.user, "view", encounter, patient_id=patient.pk)
    return render(
        request,
        "records/history.html",
        {
            "patient": patient,
            "kind": kind,
            "head": head,
            "versions": reversed(versions),
            "encounter": encounter,
            "can_change": access.can_change(request.user, head),
            "back": _chart_url(patient, errors=head.status == Status.ENTERED_IN_ERROR),
        },
    )


@login_required
@never_cache
def revise_view(request, pk, kind, lineage):
    patient = _patient(request, pk)
    model = KINDS[kind]
    head = _head(request, patient, model, lineage)
    if not access.can_change(request.user, head):
        raise PermissionDenied
    form_class = EncounterRevisionForm if model is Encounter else ChartEntryRevisionForm
    initial = {"based_on_version": head.version, "occurred_at": head.occurred_at}
    if model is Encounter:
        initial["kind"] = head.kind
    else:
        initial.update(entry_type=head.entry_type_id, text=head.text)
    form = form_class(request.POST or None, initial=initial, current=head)
    if request.method == "POST" and form.is_valid():
        revise = services.revise_encounter if model is Encounter else services.revise_entry
        try:
            revise(head, actor=request.user, **form.cleaned_data)
        except ValidationError as error:
            _add_errors(form, error)
        else:
            messages.success(request, "Korrektur gespeichert; die alte Fassung bleibt im Verlauf.")
            return redirect("records:history", pk=patient.pk, kind=kind, lineage=lineage)
    log_access(request.user, "view", head, patient_id=patient.pk)
    return _form_page(
        request,
        patient,
        form,
        title="Korrigieren",
        submit="Korrektur speichern",
        back=reverse("records:history", args=[patient.pk, kind, lineage]),
    )


@login_required
@never_cache
def error_view(request, pk, kind, lineage):
    patient = _patient(request, pk)
    model = KINDS[kind]
    head = _head(request, patient, model, lineage)
    if not access.can_change(request.user, head):
        raise PermissionDenied
    form = ReasonForm(request.POST or None, initial={"based_on_version": head.version})
    if request.method == "POST" and form.is_valid():
        try:
            services.mark_entered_in_error(head, actor=request.user, **form.cleaned_data)
        except ValidationError as error:
            _add_errors(form, error)
        else:
            messages.success(request, "Als Irrtum markiert; nur Ärztinnen und Ärzte sehen es noch.")
            return redirect(_chart_url(patient))
    log_access(request.user, "view", head, patient_id=patient.pk)
    return _form_page(
        request,
        patient,
        form,
        title="Als Irrtum markieren",
        submit="Als Irrtum markieren",
        record=head,
        back=reverse("records:history", args=[patient.pk, kind, lineage]),
    )
