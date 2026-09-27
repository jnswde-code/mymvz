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

# Roles whose members see the chart only for patients whose care team they
# are on (#23 section 5.1); the patient page offers them for the team.
# Nutrition joins once it reads something (allergies, K4).
CARE_TEAM_ROLES = [PSYCHOLOGY, ADDICTION_THERAPY]

# Permissions per group, as "app_label.codename". Only what exists today.
# Master data: doctors, MFA and the administration read and change it, the
# other professions only read it (#23 section 5.1, #26). The chart and its
# protection levels (#37, #38): what the permissions mean and the checks per
# record are in `records/access.py`. Doctors keep the care team and record
# consents (#38). Restriction (#39, #27 question 6): doctors set, release
# and lift it and open it in an emergency; the administration may only set
# it, link staff accounts and read the list of emergency accesses. Only the
# administration links: the list of accounts to choose from leaves out those
# already linked, and so shows who of the staff is a patient.
_MASTER_DATA_EDIT = ["patients.view_patient", "patients.add_patient", "patients.change_patient"]
_MASTER_DATA_READ = ["patients.view_patient"]
_CHART = ["records.view_chartentry", "records.add_chartentry"]
_CHART_MFA = [*_CHART, "records.view_all_patients", "records.write_normal"]
_CHART_DOCTOR = [
    *_CHART_MFA,
    "records.change_chartentry",
    "records.view_entered_in_error",
    "records.view_addiction",
    "records.write_addiction",
    "records.write_psychotherapy",
    "records.write_restricted",
]
_CHART_PSYCHOLOGY = [*_CHART, "records.write_psychotherapy"]
_CHART_ADDICTION_THERAPY = [*_CHART, "records.view_addiction", "records.write_addiction"]
_CARE_TEAM = [
    "patients.add_careteammember",
    "patients.change_careteammember",
    "patients.view_consenttoshare",
    "patients.add_consenttoshare",
    "patients.change_consenttoshare",
]
_RESTRICTION_DOCTOR = [
    "patients.restrict_patient",
    "patients.lift_restriction",
    "patients.add_emergencyaccess",
]
_RESTRICTION_ADMINISTRATION = [
    "patients.restrict_patient",
    "patients.link_account",
    "patients.view_emergencyaccess",
]
# Appointment requests: doctors and MFA see and answer them, nobody else
# (#8, decision 1). "change" covers every step and the internal note.
_REQUESTS = ["appointments.view_appointmentrequest", "appointments.change_appointmentrequest"]

ROLE_PERMISSIONS = {
    DOCTOR: [*_MASTER_DATA_EDIT, *_CHART_DOCTOR, *_CARE_TEAM, *_RESTRICTION_DOCTOR, *_REQUESTS],
    MFA: [*_MASTER_DATA_EDIT, *_CHART_MFA, *_REQUESTS],
    ADMINISTRATION: [
        "audit.view_accesslogentry",
        *_MASTER_DATA_EDIT,
        *_RESTRICTION_ADMINISTRATION,
    ],
    PSYCHOLOGY: [*_MASTER_DATA_READ, *_CHART_PSYCHOLOGY],
    ADDICTION_THERAPY: [*_MASTER_DATA_READ, *_CHART_ADDICTION_THERAPY],
    NUTRITION: _MASTER_DATA_READ,
}
