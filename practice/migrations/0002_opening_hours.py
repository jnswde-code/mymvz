"""Opening and consultation hours from the existing homepage (#3).

The homepage contradicts itself: consultation until 18.00 on Tuesday and
Thursday, but the practice closes at 17.30, and until 13.00 on Wednesday and
Friday, but it closes at 12.00. Consultation is cut to the opening hours
here. To be confirmed by the practice; changes go in a new migration or,
once it exists, the backoffice (#8).
"""

from datetime import time

from django.db import migrations

# (weekday, opens, closes); Monday is 0.
OPENING = [
    (0, time(8), time(16)),
    (1, time(8), time(13)),
    (1, time(14), time(17, 30)),
    (2, time(8), time(12)),
    (3, time(8), time(13)),
    (3, time(14), time(17, 30)),
    (4, time(8), time(12)),
]
CONSULTATION = [
    (0, time(8), time(13)),
    (1, time(14), time(17, 30)),
    (2, time(8), time(12)),
    (3, time(14), time(17, 30)),
    (4, time(8), time(12)),
]


def create(apps, schema_editor):
    OpeningHours = apps.get_model("practice", "OpeningHours")
    OpeningHours.objects.bulk_create(
        [OpeningHours(kind="opening", weekday=d, opens=o, closes=c) for d, o, c in OPENING]
        + [
            OpeningHours(kind="consultation", weekday=d, opens=o, closes=c)
            for d, o, c in CONSULTATION
        ]
    )


def remove(apps, schema_editor):
    apps.get_model("practice", "OpeningHours").objects.all().delete()


class Migration(migrations.Migration):
    dependencies = [("practice", "0001_initial")]

    operations = [migrations.RunPython(create, remove)]
