"""Forms for the record. They check formats; rules live in `services` and `access`."""

from django import forms

from records.access import OPEN_SENSITIVITIES
from records.models import ChangeReason, ChartEntryType, EncounterKind, Sensitivity


class DateTimeInput(forms.DateTimeInput):
    input_type = "datetime-local"

    def __init__(self, **kwargs):
        super().__init__(format="%Y-%m-%dT%H:%M", **kwargs)


def _occurred_at(**kwargs):
    # Entered in Europe/Berlin; a time that does not exist or exists twice
    # at the clock change is refused by Django.
    return forms.DateTimeField(
        label="Zeitpunkt", widget=DateTimeInput(), input_formats=["%Y-%m-%dT%H:%M"], **kwargs
    )


class EncounterForm(forms.Form):
    kind = forms.ChoiceField(label="Art", choices=EncounterKind.choices)
    occurred_at = _occurred_at()


class ChartEntryForm(forms.Form):
    entry_type = forms.ModelChoiceField(
        label="Kürzel", queryset=ChartEntryType.objects.filter(is_active=True), empty_label=None
    )
    text = forms.CharField(label="Text", widget=forms.Textarea(attrs={"rows": 4}))
    occurred_at = _occurred_at(required=False, help_text="leer: Zeitpunkt des Kontakts")
    sensitivity = forms.ChoiceField(
        label="Schutzstufe",
        choices=[(s.value, s.label) for s in Sensitivity if s in OPEN_SENSITIVITIES],
        initial=Sensitivity.NORMAL,
    )


class ReasonForm(forms.Form):
    """Why something changes; required from version 2 on (#23 section 3.1)."""

    # The version the user saw; a newer one in between fails the change.
    based_on_version = forms.IntegerField(widget=forms.HiddenInput, min_value=1)
    change_reason = forms.ChoiceField(
        label="Grund", choices=[("", "– bitte wählen –"), *ChangeReason.choices]
    )
    change_reason_text = forms.CharField(label="Erläuterung", max_length=200, required=False)

    def clean(self):
        data = super().clean()
        if (
            data.get("change_reason") == ChangeReason.OTHER
            and not data.get("change_reason_text", "").strip()
        ):
            self.add_error("change_reason_text", "Bei „Sonstiges“ bitte kurz erläutern.")
        return data


class EncounterRevisionForm(EncounterForm, ReasonForm):
    pass


class ChartEntryRevisionForm(ReasonForm):
    entry_type = forms.ModelChoiceField(label="Kürzel", queryset=ChartEntryType.objects.all())
    text = forms.CharField(label="Text", widget=forms.Textarea(attrs={"rows": 6}))
    occurred_at = _occurred_at()

    field_order = ["entry_type", "text", "occurred_at", "change_reason", "change_reason_text"]
