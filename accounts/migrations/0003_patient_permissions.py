"""Rights on patient master data (#23 section 5.1, #26). A frozen copy of accounts/roles.py."""

from django.contrib.auth.management import create_permissions
from django.db import migrations

EDIT = ["view_patient", "add_patient", "change_patient"]
READ = ["view_patient"]

PATIENT_PERMISSIONS = {
    "Ärztin/Arzt": EDIT,
    "MFA/Anmeldung": EDIT,
    "Verwaltung": EDIT,
    "Psychologie": READ,
    "Suchttherapie/Sozialpädagogik": READ,
    "Ernährung/Fitness": READ,
}


def grant(apps, schema_editor):
    # Permissions normally appear after all migrations (post_migrate).
    app_config = apps.get_app_config("patients")
    app_config.models_module = True
    create_permissions(app_config, verbosity=0, using=schema_editor.connection.alias, apps=apps)
    app_config.models_module = None

    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")
    for name, codenames in PATIENT_PERMISSIONS.items():
        Group.objects.get(name=name).permissions.add(
            *Permission.objects.filter(content_type__app_label="patients", codename__in=codenames)
        )


def revoke(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")
    patient_permissions = Permission.objects.filter(content_type__app_label="patients")
    for group in Group.objects.filter(name__in=PATIENT_PERMISSIONS):
        group.permissions.remove(*patient_permissions)


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0002_roles"),
        ("patients", "0001_initial"),
    ]

    operations = [migrations.RunPython(grant, revoke)]
