"""Forms for the team's request pages (#8). They check formats; rules live in `services`."""

from datetime import datetime

from django import forms
from django.utils import timezone

from appointments import services
from appointments.forms import DateInput
from appointments.models import (
    DECLINE_REASONS,
    PATIENT_CANCELLATION_REASONS,
    PRACTICE_CANCELLATION_REASONS,
)
from patients.models import Patient

STAFF_NOTE_MAX_LENGTH = 2000


class ListFilterForm(forms.Form):
    """`?zeige=` on the list; anything unknown falls back to the open requests."""

    OPEN, CALLBACK, ALL = "offen", "rueckruf", "alle"
    CHOICES = [(OPEN, "offen"), (CALLBACK, "Rückruf nötig"), (ALL, "alle")]

    zeige = forms.ChoiceField(choices=CHOICES, required=False)

    def selected(self) -> str:
        if self.is_valid() and self.cleaned_data["zeige"]:
            return self.cleaned_data["zeige"]
        return self.OPEN


class DoctorField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return obj.name


class AppointmentForm(forms.Form):
    """Day and time in Europe/Berlin; the end follows from the appointment type."""

    day = forms.DateField(widget=DateInput(), label="Tag")
    time = forms.TimeField(widget=forms.TimeInput(attrs={"type": "time"}), label="Uhrzeit")
    doctor = DoctorField(
        queryset=services.doctors(), required=False, empty_label="keine Angabe", label="Ärztin/Arzt"
    )

    def start(self) -> datetime:
        return timezone.make_aware(
            datetime.combine(self.cleaned_data["day"], self.cleaned_data["time"])
        )

    def resources(self) -> list:
        doctor = self.cleaned_data["doctor"]
        return [doctor] if doctor else []


class DeclineForm(forms.Form):
    reason = forms.ChoiceField(
        choices=[(r.value, r.label) for r in DECLINE_REASONS],
        widget=forms.RadioSelect,
        label="Grund (bestimmt den Text der E-Mail)",
    )


class StaffNoteForm(forms.Form):
    staff_note = forms.CharField(
        widget=forms.Textarea(attrs={"rows": 4}),
        max_length=STAFF_NOTE_MAX_LENGTH,
        required=False,
        label="Interne Notiz (nie in E-Mails)",
    )


def _reason_choices(reasons):
    return [(r.value, r.label) for r in reasons]


class PracticeCancelForm(forms.Form):
    """The practice cancels a booked appointment; the patient gets a mail."""

    reason = forms.ChoiceField(
        choices=_reason_choices(PRACTICE_CANCELLATION_REASONS),
        widget=forms.RadioSelect,
        label="Grund",
    )
    reopen = forms.BooleanField(
        required=False, label="Neuen Termin anbieten (Anfrage wieder offen)"
    )


class PhoneCancelForm(forms.Form):
    """A patient called to cancel; no mail goes out."""

    reason = forms.ChoiceField(
        choices=_reason_choices(PATIENT_CANCELLATION_REASONS),
        widget=forms.RadioSelect,
        label="Grund laut Anruf",
    )
    reopen = forms.BooleanField(
        required=False, label="Möchte einen neuen Termin (Anfrage wieder offen)"
    )


class ListTabForm(forms.Form):
    """`?zeige=` on the appointment list; anything unknown falls back to "einzutragen"."""

    TO_ENTER, TO_REMOVE, UPCOMING, CANCELLED = "einzutragen", "auszutragen", "kommende", "absagen"
    CHOICES = [
        (TO_ENTER, "in Medical Office eintragen"),
        (TO_REMOVE, "aus Medical Office austragen"),
        (UPCOMING, "kommende"),
        (CANCELLED, "Absagen durch Patienten (14 Tage)"),
    ]

    zeige = forms.ChoiceField(choices=CHOICES, required=False)

    def selected(self) -> str:
        if self.is_valid() and self.cleaned_data["zeige"]:
            return self.cleaned_data["zeige"]
        return self.TO_ENTER


class MedicalOfficeForm(forms.Form):
    """The tick; `zurueck` only chooses which tab of the list to return to."""

    zurueck = forms.ChoiceField(choices=ListTabForm.CHOICES, required=False)


class PatientSearchForm(forms.Form):
    """Search in the patient records from a request; prefilled from the snapshot."""

    name = forms.CharField(max_length=200, required=False, label="Name")
    geburtsdatum = forms.DateField(widget=DateInput(), required=False, label="Geburtsdatum")

    def has_terms(self) -> bool:
        return self.is_valid() and bool(
            self.cleaned_data["name"].strip() or self.cleaned_data["geburtsdatum"]
        )


class AssignPatientForm(forms.Form):
    patient = forms.ModelChoiceField(queryset=Patient.objects.all(), widget=forms.HiddenInput)
