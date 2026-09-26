"""Roles as groups (#23, section 5.1). A frozen copy of accounts/roles.py."""

from django.contrib.auth.management import create_permissions
from django.db import migrations

ROLE_PERMISSIONS = {
    "Ärztin/Arzt": [],
    "MFA/Anmeldung": [],
    "Verwaltung": ["audit.view_accesslogentry"],
    "Psychologie": [],
    "Suchttherapie/Sozialpädagogik": [],
    "Ernährung/Fitness": [],
}


def create_roles(apps, schema_editor):
    # Permissions normally appear after all migrations (post_migrate); the
    # ones assigned here are needed now.
    for app_label in ("audit",):
        app_config = apps.get_app_config(app_label)
        app_config.models_module = True
        create_permissions(app_config, verbosity=0, using=schema_editor.connection.alias, apps=apps)
        app_config.models_module = None

    Group = apps.get_model("auth", "Group")
    Permission = apps.get_model("auth", "Permission")
    for name, permissions in ROLE_PERMISSIONS.items():
        group, _ = Group.objects.get_or_create(name=name)
        for permission in permissions:
            app_label, codename = permission.split(".")
            group.permissions.add(
                Permission.objects.get(content_type__app_label=app_label, codename=codename)
            )


def remove_roles(apps, schema_editor):
    apps.get_model("auth", "Group").objects.filter(name__in=ROLE_PERMISSIONS).delete()


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0001_initial"),
        ("audit", "0001_initial"),
        ("contenttypes", "0002_remove_content_type_name"),
    ]

    operations = [migrations.RunPython(create_roles, remove_roles)]
