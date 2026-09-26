from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = "Deaktiviert ein Konto. Konten werden nie gelöscht (Zugriffsprotokoll)."

    def add_arguments(self, parser):
        parser.add_argument("username")

    def handle(self, *args, username, **options):
        updated = get_user_model().objects.filter(username=username).update(is_active=False)
        if not updated:
            raise CommandError(f"Kein Konto {username}.")
        # Open sessions end at their next request: Django does not load
        # inactive users.
        self.stdout.write(f"Konto {username} deaktiviert.")
