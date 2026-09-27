"""Forms for the team. They check formats; rules live in `services`."""

from django import forms
from django.contrib.auth import get_user_model
from django.db.models import Q

from accounts.roles import CARE_TEAM_ROLES
from patients.models import ConsentArea, IdentifierSystem, Patient
from patients.services import CHART_PERMISSION, MASTER_DATA_FIELDS, name_terms


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


class AccountChoiceField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return obj.get_full_name() or obj.get_username()


class CareTeamForm(forms.Form):
    """Offers the professions that see a chart only in the care team (#38)."""

    user = AccountChoiceField(label="Person", queryset=get_user_model().objects.none())

    def __init__(self, *args, patient, **kwargs):
        super().__init__(*args, **kwargs)
        current = patient.care_team.filter(valid_until=None).values("user_id")
        self.fields["user"].queryset = (
            get_user_model()
            .objects.filter(is_active=True, groups__name__in=CARE_TEAM_ROLES)
            .exclude(pk__in=current)
            .distinct()
            .order_by("last_name", "first_name", "username")
        )


class ConsentForm(forms.Form):
    area = forms.ChoiceField(label="Bereich", choices=ConsentArea.choices)
    user = AccountChoiceField(label="Person", queryset=get_user_model().objects.none())
    valid_until = forms.DateField(
        label="bis", required=False, widget=DateInput(), help_text="erster Tag ohne Freigabe"
    )

    def __init__(self, *args, actor, **kwargs):
        super().__init__(*args, **kwargs)
        # Accounts with the chart right; `services.grant_consent` checks again.
        app_label, codename = CHART_PERMISSION.split(".")
        right = {"content_type__app_label": app_label, "codename": codename}
        with_right = Q(**{f"groups__permissions__{k}": v for k, v in right.items()}) | Q(
            **{f"user_permissions__{k}": v for k, v in right.items()}
        )
        self.fields["user"].queryset = (
            get_user_model()
            .objects.filter(with_right, is_active=True)
            .exclude(pk=actor.pk)
            .distinct()
            .order_by("last_name", "first_name", "username")
        )
