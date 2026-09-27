"""Rights on the chart (#23 section 5.1, #37). A frozen copy of accounts/roles.py.

Doctors and MFA only; the other roles get nothing until K2.2.
"""

from django.contrib.auth.management import create_permissions
from django.db import migrations

MFA = ["view_chartentry", "add_chartentry"]
DOCTOR = [*MFA, "change_chartentry", "view_entered_in_error"]

RECORD_PERMISSIONS = {
    "Ärztin/Arzt": DOCTOR,
    "MFA/Anmeldung": MFA,
}


def grant(apps, schema_editor):
    # Permissions normally appear after all migrations (post_migrate).
    app_config = apps.get_app_config("records")
    app_config.models_module = True
    create_permissions(app_config, verbosity=0, using=schema_editor.connection.alias, apps=apps)
    app_config.models_module = None

    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")
    for name, codenames in RECORD_PERMISSIONS.items():
        permissions = Permission.objects.filter(
            content_type__app_label="records", codename__in=codenames
        )
        assert permissions.count() == len(codenames), codenames
        Group.objects.get(name=name).permissions.add(*permissions)


def revoke(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")
    record_permissions = Permission.objects.filter(content_type__app_label="records")
    for group in Group.objects.filter(name__in=RECORD_PERMISSIONS):
        group.permissions.remove(*record_permissions)


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0003_patient_permissions"),
        ("records", "0001_initial"),
    ]

    operations = [migrations.RunPython(grant, revoke)]
