"""Forms for the team. They check formats; rules live in `services`."""

from django import forms

from patients.models import IdentifierSystem, Patient
from patients.services import MASTER_DATA_FIELDS, name_terms


class DateInput(forms.DateInput):
    input_type = "date"

    def __init__(self, **kwargs):
        super().__init__(format="%Y-%m-%d", **kwargs)


class PatientForm(forms.ModelForm):
    class Meta:
        model = Patient
        fields = MASTER_DATA_FIELDS
        widgets = {"date_of_birth": DateInput(), "deceased_on": DateInput()}


class NewPatientForm(PatientForm):
    """Creating asks once more when the duplicate check found someone (#26)."""

    not_a_duplicate = forms.BooleanField(
        required=False, label="Ich habe die Treffer geprüft; es ist eine andere Person."
    )
    # Ids of the patients shown as possible duplicates; the confirmation
    # covers only those, not ones that appear after the data was changed.
    duplicates_seen = forms.CharField(required=False, widget=forms.HiddenInput)

    class Meta(PatientForm.Meta):
        fields = tuple(f for f in MASTER_DATA_FIELDS if f not in ("deceased_on", "is_active"))

    def seen_ids(self) -> set[str]:
        return {i for i in self.cleaned_data.get("duplicates_seen", "").split(",") if i}


class SearchForm(forms.Form):
    name = forms.CharField(required=False, max_length=200, label="Name")
    date_of_birth = forms.DateField(required=False, widget=DateInput(), label="Geburtsdatum")
    identifier = forms.CharField(required=False, max_length=64, label="Nummer")

    def clean(self):
        data = super().clean()
        if not (
            name_terms(data.get("name", ""))
            or data.get("date_of_birth")
            or data.get("identifier", "").strip()
        ):
            raise forms.ValidationError("Bitte Name, Geburtsdatum oder Nummer angeben.")
        return data


class IdentifierForm(forms.Form):
    system = forms.ChoiceField(choices=IdentifierSystem.choices, label="Art")
    value = forms.CharField(max_length=64, label="Nummer")
