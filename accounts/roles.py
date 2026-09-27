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

# Permissions per group, as "app_label.codename". Only what exists today;
# record-level checks come with K2 (#23). Master data: doctors, MFA and the
# administration read and change it, the other professions only read it
# (#23 section 5.1, #26).
_MASTER_DATA_EDIT = ["patients.view_patient", "patients.add_patient", "patients.change_patient"]
_MASTER_DATA_READ = ["patients.view_patient"]

ROLE_PERMISSIONS = {
    DOCTOR: _MASTER_DATA_EDIT,
    MFA: _MASTER_DATA_EDIT,
    ADMINISTRATION: ["audit.view_accesslogentry", *_MASTER_DATA_EDIT],
    PSYCHOLOGY: _MASTER_DATA_READ,
    ADDICTION_THERAPY: _MASTER_DATA_READ,
    NUTRITION: _MASTER_DATA_READ,
}
