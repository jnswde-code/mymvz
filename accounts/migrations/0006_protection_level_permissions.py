"""Care team and protection levels (#23 sections 5.1 and 5.2, #38).

A frozen copy of accounts/roles.py.

Doctors and MFA see the chart of every patient, psychology and addiction
therapy only in the care team; each writes its own protection levels.
Doctors keep the care team and record consents.
"""

from django.contrib.auth.management import create_permissions
from django.db import migrations

PERMISSIONS = {
    "Ärztin/Arzt": [
        "records.view_all_patients",
        "records.write_normal",
        "records.view_addiction",
        "records.write_addiction",
        "records.write_psychotherapy",
        "patients.add_careteammember",
        "patients.change_careteammember",
        "patients.view_consenttoshare",
        "patients.add_consenttoshare",
        "patients.change_consenttoshare",
    ],
    "MFA/Anmeldung": ["records.view_all_patients", "records.write_normal"],
    "Psychologie": [
        "records.view_chartentry",
        "records.add_chartentry",
        "records.write_psychotherapy",
    ],
    "Suchttherapie/Sozialpädagogik": [
        "records.view_chartentry",
        "records.add_chartentry",
        "records.view_addiction",
        "records.write_addiction",
    ],
}


def _permissions(apps, names):
    Permission = apps.get_model("auth", "Permission")
    found = []
    for name in names:
        app_label, codename = name.split(".")
        found.append(Permission.objects.get(content_type__app_label=app_label, codename=codename))
    return found


def grant(apps, schema_editor):
    # Permissions normally appear after all migrations (post_migrate).
    for app_label in ("records", "patients"):
        app_config = apps.get_app_config(app_label)
        app_config.models_module = True
        create_permissions(app_config, verbosity=0, using=schema_editor.connection.alias, apps=apps)
        app_config.models_module = None

    Group = apps.get_model("auth", "Group")
    for group, names in PERMISSIONS.items():
        Group.objects.get(name=group).permissions.add(*_permissions(apps, names))


def revoke(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    for group, names in PERMISSIONS.items():
        Group.objects.get(name=group).permissions.remove(*_permissions(apps, names))


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0005_appointment_permissions"),
        ("records", "0004_protection_level_permissions"),
        ("patients", "0002_consenttoshare"),
    ]

    operations = [migrations.RunPython(grant, revoke)]
