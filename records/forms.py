"""Forms for the record. They check formats; rules live in `services` and `access`."""

from django import forms
from django.utils import timezone

from records.access import writable_sensitivities
from records.models import ChangeReason, ChartEntryType, EncounterKind, Sensitivity


class DateTimeInput(forms.DateTimeInput):
    input_type = "datetime-local"

    def __init__(self, **kwargs):
        super().__init__(format=FORMAT, **kwargs)


FORMAT = "%Y-%m-%dT%H:%M"


class OccurredAtField(forms.DateTimeField):
    """Entered in Europe/Berlin, to the minute.

    Django refuses a time that does not exist or exists twice at the clock
    change. `keep` is the stored time of the version being corrected: sent
    back unchanged, it stays exactly that time, also in the repeated hour in
    October.
    """

    def __init__(self, **kwargs):
        self.keep = None
        super().__init__(
            label="Zeitpunkt", widget=DateTimeInput(), input_formats=[FORMAT], **kwargs
        )

    def to_python(self, value):
        if self.keep is not None and value == timezone.localtime(self.keep).strftime(FORMAT):
            return self.keep
        return super().to_python(value)


def _occurred_at(**kwargs):
    return OccurredAtField(**kwargs)


class EncounterForm(forms.Form):
    kind = forms.ChoiceField(label="Art", choices=EncounterKind.choices)
    occurred_at = _occurred_at()


class ChartEntryForm(forms.Form):
    entry_type = forms.ModelChoiceField(
        label="Kürzel", queryset=ChartEntryType.objects.filter(is_active=True), empty_label=None
    )
    text = forms.CharField(label="Text", widget=forms.Textarea(attrs={"rows": 4}))
    occurred_at = _occurred_at(required=False, help_text="leer: Zeitpunkt des Kontakts")
    sensitivity = forms.ChoiceField(label="Schutzstufe")

    def __init__(self, *args, user, **kwargs):
        super().__init__(*args, **kwargs)
        # Only the levels the user may write; the first is the default of
        # the role (#38). `services` checks it again.
        levels = writable_sensitivities(user)
        field = self.fields["sensitivity"]
        field.choices = [(level.value, Sensitivity(level).label) for level in levels]
        field.initial = levels[0] if levels else None


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


class RevisionMixin:
    """Keeps the stored time when it comes back unchanged (`OccurredAtField.keep`)."""

    def __init__(self, *args, current=None, **kwargs):
        super().__init__(*args, **kwargs)
        if current is not None:
            self.fields["occurred_at"].keep = current.occurred_at


class EncounterRevisionForm(RevisionMixin, EncounterForm, ReasonForm):
    field_order = ["kind", "occurred_at", "change_reason", "change_reason_text"]


class ChartEntryRevisionForm(RevisionMixin, ReasonForm):
    entry_type = forms.ModelChoiceField(label="Kürzel", queryset=ChartEntryType.objects.all())
    text = forms.CharField(label="Text", widget=forms.Textarea(attrs={"rows": 6}))
    occurred_at = _occurred_at()

    field_order = ["entry_type", "text", "occurred_at", "change_reason", "change_reason_text"]
