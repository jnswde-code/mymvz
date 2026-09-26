from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError

from accounts.second_factor import remove_all_devices


class Command(BaseCommand):
    help = (
        "Entfernt App und Wiederherstellungscodes eines Kontos, etwa nach Verlust "
        "des Telefons. Beim nächsten Anmelden wird der zweite Faktor neu eingerichtet."
    )

    def add_arguments(self, parser):
        parser.add_argument("username")

    def handle(self, *args, username, **options):
        user = get_user_model().objects.filter(username=username).first()
        if user is None:
            raise CommandError(f"Kein Konto {username}.")
        remove_all_devices(user)
        self.stdout.write(
            f"Zweiter Faktor von {username} entfernt; offene Sitzungen enden damit. "
            "Bitte vor der nächsten Anmeldung das Passwort neu setzen "
            "(manage.py changepassword), falls es mit dem Telefon verloren sein könnte."
        )
