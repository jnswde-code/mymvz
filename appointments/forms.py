"""Forms for patients. They check formats; rules and deadlines live in `services` (#14)."""

from django import forms
from django.core.exceptions import ValidationError
from django.core.validators import RegexValidator

from appointments import services
from appointments.models import (
    PATIENT_CANCELLATION_REASONS,
    Insurance,
    PartOfDay,
    Reason,
)

WINDOW_POSITIONS = (1, 2, 3)

phone_validator = RegexValidator(
    r"^\+?[0-9][0-9 ()/\-]{4,28}[0-9]$",
    "Bitte geben Sie eine Telefonnummer mit Ziffern an, z. B. 02181 123456.",
)


class DateInput(forms.DateInput):
    input_type = "date"

    def __init__(self, **kwargs):
        super().__init__(format="%Y-%m-%d", **kwargs)


class PublicTypeField(forms.ModelChoiceField):
    def label_from_instance(self, obj):
        return obj.public_name


class RequestForm(forms.Form):
    appointment_type = PublicTypeField(
        queryset=services.active_types(),
        widget=forms.RadioSelect,
        empty_label=None,
        label="Terminart",
    )
    is_existing_patient = forms.TypedChoiceField(
        choices=[("1", "Ja, ich war schon in der Praxis"), ("0", "Nein, ich bin neu")],
        coerce=lambda value: value == "1",
        widget=forms.RadioSelect,
        label="Waren Sie schon einmal bei uns?",
    )
    insurance_type = forms.ChoiceField(
        choices=Insurance.choices, widget=forms.RadioSelect, label="Versicherung"
    )
    preferred_resource = forms.ModelChoiceField(
        queryset=services.doctors(),
        required=False,
        empty_label="egal",
        label="Wunsch-Ärztin oder -Arzt",
    )
    patient_first_name = forms.CharField(max_length=100, label="Vorname")
    patient_last_name = forms.CharField(max_length=100, label="Nachname")
    patient_date_of_birth = forms.DateField(widget=DateInput(), label="Geburtsdatum")
    for_other_person = forms.BooleanField(
        required=False, label="Ich frage für eine andere Person an (z. B. mein Kind)"
    )
    contact_name = forms.CharField(max_length=200, required=False, label="Ihr Name")
    contact_relationship = forms.CharField(
        max_length=100, required=False, label="Ihre Beziehung zur Person (z. B. Mutter)"
    )
    email = forms.EmailField(label="E-Mail-Adresse")
    phone = forms.CharField(max_length=40, validators=[phone_validator], label="Telefon")
    note = forms.CharField(
        max_length=500,
        required=False,
        widget=forms.Textarea(attrs={"rows": 3, "maxlength": 500}),
        label="Notiz (optional)",
        help_text="Höchstens 500 Zeichen. Bitte keine Befunde oder Beschwerden.",
    )
    # Honeypot, name in spam.HONEYPOT_FIELD.
    website = forms.CharField(required=False, label="Bitte leer lassen")
    # Solution of the captcha, filled in by the browser.
    altcha = forms.CharField(required=False, widget=forms.HiddenInput)

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for position in WINDOW_POSITIONS:
            required = position == 1
            self.fields[f"window_{position}_date"] = forms.DateField(
                required=required, widget=DateInput(), label=f"{position}. Wunschtag"
            )
            self.fields[f"window_{position}_part"] = forms.ChoiceField(
                choices=PartOfDay.choices,
                initial=PartOfDay.ANY,
                required=required,
                label="Tageszeit",
            )

    def windows(self):
        """Bound fields of the preferred days, for the template."""
        return [(self[f"window_{p}_date"], self[f"window_{p}_part"]) for p in WINDOW_POSITIONS]

    def clean(self):
        data = super().clean()
        if data.get("for_other_person"):
            for name in ("contact_name", "contact_relationship"):
                if not data.get(name):
                    self.add_error(name, "Bitte ausfüllen, wenn Sie für jemand anderen anfragen.")
        else:
            data["contact_name"] = data["contact_relationship"] = ""
        for position in WINDOW_POSITIONS:
            day = data.get(f"window_{position}_date")
            if day and not data.get(f"window_{position}_part"):
                data[f"window_{position}_part"] = PartOfDay.ANY
        return data

    def service_data(self) -> dict:
        data = self.cleaned_data
        return {
            "appointment_type": data["appointment_type"],
            "is_existing_patient": data["is_existing_patient"],
            "insurance_type": data["insurance_type"],
            "preferred_resource": data["preferred_resource"],
            "patient_first_name": data["patient_first_name"].strip(),
            "patient_last_name": data["patient_last_name"].strip(),
            "patient_date_of_birth": data["patient_date_of_birth"],
            "contact_name": data["contact_name"].strip(),
            "contact_relationship": data["contact_relationship"].strip(),
            "email": data["email"],
            "phone": data["phone"].strip(),
            "note": data["note"].strip(),
            "time_windows": [
                (data[f"window_{p}_date"], data[f"window_{p}_part"])
                for p in WINDOW_POSITIONS
                if data.get(f"window_{p}_date")
            ],
        }

    def add_service_errors(self, error: ValidationError) -> None:
        """Put the errors of `services.submit_request` on the matching fields."""
        for field, messages in error.message_dict.items():
            if field.startswith("window_"):
                field = f"{field}_date"
            elif field not in self.fields:
                field = None
            for message in messages:
                self.add_error(field, message)


class CancelForm(forms.Form):
    reason = forms.ChoiceField(
        choices=[("", "keine Angabe")]
        + [(r.value, r.label) for r in Reason if r in PATIENT_CANCELLATION_REASONS],
        required=False,
        label="Grund (optional)",
    )
