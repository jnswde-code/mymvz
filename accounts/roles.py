"""Roles are Django groups (#23, section 5.1).

The data migration `0002_roles` creates the groups with these names and
permissions; it carries its own copy, as migrations must not import app code.
A change here needs a new data migration; `tests/test_accounts_roles.py`
checks that the groups in the database match this module.
"""

DOCTOR = "Ärztin/Arzt"
MFA = "MFA/Anmeldung"
ADMINISTRATION = "Verwaltung"
PSYCHOLOGY = "Psychologie"
ADDICTION_THERAPY = "Suchttherapie/Sozialpädagogik"
NUTRITION = "Ernährung/Fitness"

# Keys for the command line (`create_account --role`), mapped to group names.
ROLES = {
    "doctor": DOCTOR,
    "mfa": MFA,
    "administration": ADMINISTRATION,
    "psychology": PSYCHOLOGY,
    "addiction_therapy": ADDICTION_THERAPY,
    "nutrition": NUTRITION,
}

# Permissions per group, as "app_label.codename". Only what exists today.
# Master data: doctors, MFA and the administration read and change it, the
# other professions only read it (#23 section 5.1, #26). The chart: doctors
# and MFA only until K2.2 (#37); what the permissions mean and the checks per
# record are in `records/access.py`.
_MASTER_DATA_EDIT = ["patients.view_patient", "patients.add_patient", "patients.change_patient"]
_MASTER_DATA_READ = ["patients.view_patient"]
_CHART_MFA = ["records.view_chartentry", "records.add_chartentry"]
_CHART_DOCTOR = [*_CHART_MFA, "records.change_chartentry", "records.view_entered_in_error"]
# Appointment requests: doctors and MFA see and answer them, nobody else
# (#8, decision 1). "change" covers every step and the internal note.
_REQUESTS = ["appointments.view_appointmentrequest", "appointments.change_appointmentrequest"]

ROLE_PERMISSIONS = {
    DOCTOR: [*_MASTER_DATA_EDIT, *_CHART_DOCTOR, *_REQUESTS],
    MFA: [*_MASTER_DATA_EDIT, *_CHART_MFA, *_REQUESTS],
    ADMINISTRATION: ["audit.view_accesslogentry", *_MASTER_DATA_EDIT],
    PSYCHOLOGY: _MASTER_DATA_READ,
    ADDICTION_THERAPY: _MASTER_DATA_READ,
    NUTRITION: _MASTER_DATA_READ,
}
