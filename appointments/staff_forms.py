"""Forms for the team's request pages (#8). They check formats; rules live in `services`."""

from datetime import datetime

from django import forms
from django.utils import timezone

from appointments import services
from appointments.forms import DateInput
from appointments.models import DECLINE_REASONS

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
