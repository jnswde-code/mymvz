"""Invented patients for the test system (#23 section 8, #26).

Family names come from a fixed list of words that are obviously not real
surnames, addresses from invented streets with postal code 00000 (no German
postal code starts with 00), e-mail addresses from example.org. So no
realistic combination of name, date of birth and address can come out.
Runs only with DATA_MODE=synthetic.

With `--author` it also writes contacts and chart entries with short,
invented texts (#37), through `records.services` like any user, so the
author needs a role that may write the chart. They lie in the past and therefore count as
late entries.
"""

import random
from datetime import date, timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from patients.models import IdentifierSystem, Patient, PatientIdentifier, Sex
from records import access, services
from records.models import ChangeReason, ChartEntryType, EncounterKind

FAMILY_NAMES = (
    "Beispiel",
    "Muster",
    "Probe",
    "Testfall",
    "Erfunden",
    "Platzhalter",
    "Fiktiv",
    "Exempel",
    "Attrappe",
    "Mustermann",
    "Demo",
    "Vorlage",
)
GIVEN_NAMES = {
    Sex.FEMALE: ("Erika", "Anna", "Lea", "Marie", "Sofia", "Hanna"),
    Sex.MALE: ("Max", "Paul", "Jonas", "Felix", "Lukas", "Emil"),
    Sex.OTHER: ("Kim", "Alex", "Robin"),
}
STREETS = ("Musterweg", "Beispielstraße", "Probegasse", "Testallee")
CITY = "Beispielstadt"
POSTAL_CODE = "00000"
EMAIL_DOMAIN = "example.org"
# Bundesnetzagentur range reserved for film and fiction, never assigned.
PHONE_PREFIX = "030 23125"
# Medical Office numbers of demo patients start here, far from real ones.
DEMO_NUMBER_START = 900_000
# Invented chart texts per abbreviation; nothing that looks like a real case.
ENTRY_TEXTS = {
    "A": ("Kommt zur Kontrolle, keine neuen Beschwerden.", "Seit drei Tagen Husten, kein Fieber."),
    "B": ("Herz und Lunge unauffällig.", "Rachen leicht gerötet, sonst unauffällig."),
    "TH": ("Weiter wie bisher, Kontrolle in drei Monaten.", "Inhalieren, viel trinken."),
    "MW": ("RR 125/80 mmHg, Puls 72/min.", "Gewicht 74 kg."),
    "N": ("Befund an Hausarzt geschickt.",),
}


class Command(BaseCommand):
    help = "Legt erfundene Patienten für das Testsystem an (nur mit DATA_MODE=synthetic)."

    def add_arguments(self, parser):
        parser.add_argument("--count", type=int, default=20, help="Anzahl (Vorgabe 20)")
        parser.add_argument("--seed", type=int, default=None, help="Startwert für den Zufall")
        parser.add_argument(
            "--author",
            default=None,
            help="Konto, das in die Akte schreibt; dann auch Kontakte und Einträge anlegen",
        )

    @transaction.atomic
    def handle(self, *args, count, seed, author, **options):
        if settings.DATA_MODE != "synthetic":
            raise CommandError("seed_demo läuft nur mit DATA_MODE=synthetic.")
        if count < 1:
            raise CommandError("--count muss mindestens 1 sein.")
        author = self._author(author)
        rng = random.Random(seed)
        next_number = self._next_number()
        for i in range(count):
            sex = rng.choice([Sex.FEMALE, Sex.MALE, Sex.OTHER])
            given = rng.choice(GIVEN_NAMES[sex])
            family = rng.choice(FAMILY_NAMES)
            patient = Patient.objects.create(
                family_name=family,
                given_name=given,
                sex=sex,
                date_of_birth=date(1940, 1, 1) + timedelta(days=rng.randrange(80 * 365)),
                street=f"{rng.choice(STREETS)} {rng.randint(1, 99)}",
                postal_code=POSTAL_CODE,
                city=CITY,
                phone=f"{PHONE_PREFIX}{rng.randrange(1_000):03d}",
                email=f"{given}.{family}.{next_number + i}@{EMAIL_DOMAIN}".lower(),
            )
            PatientIdentifier.objects.create(
                patient=patient,
                system=IdentifierSystem.MEDICAL_OFFICE,
                value=str(next_number + i),
            )
            if author is not None:
                self._chart(patient, author, rng)
        self.stdout.write(f"{count} erfundene Patienten angelegt.")

    @staticmethod
    def _author(username):
        if username is None:
            return None
        author = get_user_model().objects.filter(username=username).first()
        if author is None or not access.can_write(author, None):
            raise CommandError(
                "--author braucht ein aktives Konto, das in die Akte schreiben darf."
            )
        return author

    @staticmethod
    def _chart(patient, author, rng):
        """One to three past contacts with entries, now and then corrected."""
        types = {
            t.code: t for t in ChartEntryType.objects.filter(code__in=ENTRY_TEXTS, is_active=True)
        }
        now = timezone.now()
        for _ in range(rng.randint(1, 3)):
            occurred_at = now - timedelta(days=rng.randint(1, 400), minutes=rng.randrange(600))
            encounter = services.create_encounter(
                patient,
                kind=rng.choice(EncounterKind.values),
                occurred_at=occurred_at,
                actor=author,
            )
            for code in rng.sample(sorted(types), min(len(types), rng.randint(1, 3))):
                entry = services.create_entry(
                    encounter,
                    entry_type=types[code],
                    text=rng.choice(ENTRY_TEXTS[code]),
                    actor=author,
                )
                if rng.random() < 0.2:
                    services.revise_entry(
                        entry,
                        entry_type=entry.entry_type,
                        text=entry.text + " Rückruf vereinbart.",
                        occurred_at=entry.occurred_at,
                        change_reason=ChangeReason.ADDITION,
                        actor=author,
                    )

    @staticmethod
    def _next_number() -> int:
        """Continue after earlier runs, so numbers stay unique."""
        numbers = PatientIdentifier.objects.filter(
            system=IdentifierSystem.MEDICAL_OFFICE, value__regex=r"^9[0-9]{5,}$"
        ).values_list("value", flat=True)
        return max((int(n) + 1 for n in numbers), default=DEMO_NUMBER_START)
