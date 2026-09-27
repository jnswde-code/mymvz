from django.core.management.base import BaseCommand, CommandError

from jobs import runner


class Command(BaseCommand):
    help = "Healthcheck: fehlerhaft, wenn der Worker seit 5 Minuten keinen Lauf beendet hat."

    def handle(self, *args, **options):
        if not runner.healthy():
            raise CommandError("Der Worker hat seit 5 Minuten keinen Lauf beendet.")
        self.stdout.write("Worker läuft.")
