"""Callbacks of the phone assistant (#45): doctors and MFA, as for requests.

A frozen copy of accounts/roles.py.
"""

from django.contrib.auth.management import create_permissions
from django.db import migrations

NAMES = ["telephony.view_callbackrequest", "telephony.change_callbackrequest"]
GROUPS = ["Ärztin/Arzt", "MFA/Anmeldung"]


def _permissions(apps):
    Permission = apps.get_model("auth", "Permission")
    found = []
    for name in NAMES:
        app_label, codename = name.split(".")
        found.append(Permission.objects.get(content_type__app_label=app_label, codename=codename))
    return found


def grant(apps, schema_editor):
    # Permissions normally appear after all migrations (post_migrate).
    app_config = apps.get_app_config("telephony")
    app_config.models_module = True
    create_permissions(app_config, verbosity=0, using=schema_editor.connection.alias, apps=apps)
    app_config.models_module = None

    Group = apps.get_model("auth", "Group")
    for group in GROUPS:
        Group.objects.get(name=group).permissions.add(*_permissions(apps))


def revoke(apps, schema_editor):
    Group = apps.get_model("auth", "Group")
    for group in GROUPS:
        Group.objects.get(name=group).permissions.remove(*_permissions(apps))


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0007_restriction_permissions"),
        ("telephony", "0001_initial"),
    ]

    operations = [migrations.RunPython(grant, revoke)]
