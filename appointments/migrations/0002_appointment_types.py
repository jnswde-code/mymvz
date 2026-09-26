"""The fixed list of appointment types (#3, decision 2).

Online: consultation, check-up, TPS first consultation, first visit. Not
online, but needed by the team (#8): acute, substitution, home visit. The
durations are placeholders until the practice names its own.
"""

from datetime import timedelta

from django.db import migrations

# (name, public name, bookable online, minutes)
TYPES = [
    ("Sprechstunde", "Sprechstunde", True, 15),
    ("Check-up", "Gesundheits-Check-up", True, 30),
    ("TPS-Erstgespräch", "Erstgespräch Demenztherapie (TPS)", True, 30),
    ("Erstvorstellung", "Erstvorstellung als neue Patientin oder neuer Patient", True, 30),
    ("Akut", "Akute Beschwerden", False, 15),
    ("Substitution", "Substitution", False, 15),
    ("Hausbesuch", "Hausbesuch", False, 60),
]


def create(apps, schema_editor):
    AppointmentType = apps.get_model("appointments", "AppointmentType")
    AppointmentType.objects.bulk_create(
        AppointmentType(
            name=name,
            public_name=public_name,
            bookable_online=online,
            default_duration=timedelta(minutes=minutes),
            sort_order=position,
        )
        for position, (name, public_name, online, minutes) in enumerate(TYPES)
    )


def remove(apps, schema_editor):
    names = [name for name, *_ in TYPES]
    apps.get_model("appointments", "AppointmentType").objects.filter(name__in=names).delete()


class Migration(migrations.Migration):
    dependencies = [("appointments", "0001_initial")]

    operations = [migrations.RunPython(create, remove)]
