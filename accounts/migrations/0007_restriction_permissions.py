"""Restriction, staff as patients and emergency access (#23 section 5.2, #39).

A frozen copy of accounts/roles.py.

Doctors set, release and lift a restriction, write entries with it and open
it in an emergency; the administration may only set it, link staff accounts
and read the list of emergency accesses (#27, question 6).
"""

from django.contrib.auth.management import create_permissions
from django.db import migrations

PERMISSIONS = {
    "Ärztin/Arzt": [
        "records.write_restricted",
        "patients.restrict_patient",
        "patients.lift_restriction",
        "patients.link_account",
        "patients.add_emergencyaccess",
    ],
    "Verwaltung": [
        "patients.restrict_patient",
        "patients.link_account",
        "patients.view_emergencyaccess",
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
        ("accounts", "0006_protection_level_permissions"),
        ("records", "0005_write_restricted"),
        ("patients", "0003_restriction_emergencyaccess"),
    ]

    operations = [migrations.RunPython(grant, revoke)]
