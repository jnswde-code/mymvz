"""Rights on appointment requests (#8, decision 1). A frozen copy of accounts/roles.py.

Doctors and MFA see and answer requests; the other roles get nothing.
"""

from django.contrib.auth.management import create_permissions
from django.db import migrations

CODENAMES = ["view_appointmentrequest", "change_appointmentrequest"]
GROUPS = ["Ärztin/Arzt", "MFA/Anmeldung"]


def _permissions(apps):
    Permission = apps.get_model("auth", "Permission")
    return Permission.objects.filter(
        content_type__app_label="appointments",
        content_type__model="appointmentrequest",
        codename__in=CODENAMES,
    )


def grant(apps, schema_editor):
    # Permissions normally appear after all migrations (post_migrate).
    app_config = apps.get_app_config("appointments")
    app_config.models_module = True
    create_permissions(app_config, verbosity=0, using=schema_editor.connection.alias, apps=apps)
    app_config.models_module = None

    Group = apps.get_model("auth", "Group")
    permissions = _permissions(apps)
    assert permissions.count() == len(CODENAMES), CODENAMES
    for name in GROUPS:
        Group.objects.get(name=name).permissions.add(*permissions)


def revoke(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    for group in Group.objects.filter(name__in=GROUPS):
        group.permissions.remove(*_permissions(apps))


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0004_record_permissions"),
        ("appointments", "0003_patient"),
    ]

    operations = [migrations.RunPython(grant, revoke)]
