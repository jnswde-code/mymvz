"""Provisional abbreviations of the chart (#23 decision 5, #37).

Until #19 names the ones the practice uses in Medical Office. A later list
comes as a new migration that switches old codes off instead of deleting
them, because entries point at them.
"""

from django.db import migrations

TYPES = [
    ("A", "Anamnese"),
    ("B", "Befund"),
    ("TH", "Therapie"),
    ("N", "Notiz"),
    ("TEL", "Telefonnotiz"),
    ("MW", "Messwerte"),
]


def create_types(apps, schema_editor):
    ChartEntryType = apps.get_model("records", "ChartEntryType")
    for position, (code, label) in enumerate(TYPES, start=1):
        ChartEntryType.objects.update_or_create(
            code=code, defaults={"label": label, "position": position}
        )


def remove_types(apps, schema_editor):
    codes = [code for code, _ in TYPES]
    apps.get_model("records", "ChartEntryType").objects.filter(code__in=codes).delete()


class Migration(migrations.Migration):
    dependencies = [("records", "0002_immutability_triggers")]

    operations = [migrations.RunPython(create_types, remove_types)]
