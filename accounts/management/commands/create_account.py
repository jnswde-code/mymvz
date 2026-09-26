from getpass import getpass

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from accounts.roles import ROLES


class Command(BaseCommand):
    help = "Legt ein Konto an. Das Passwort wird verdeckt abgefragt."

    def add_arguments(self, parser):
        parser.add_argument("username")
        parser.add_argument(
            "--role",
            action="append",
            choices=sorted(ROLES),
            required=True,
            dest="roles",
            help="Rolle, mehrfach möglich",
        )
        parser.add_argument("--first-name", default="")
        parser.add_argument("--last-name", default="")
        parser.add_argument("--email", default="")

    def handle(self, *args, username, roles, first_name, last_name, email, **options):
        User = get_user_model()
        if User.objects.filter(username=username).exists():
            raise CommandError(f"Das Konto {username} gibt es schon.")
        user = User(username=username, first_name=first_name, last_name=last_name, email=email)
        password = getpass("Passwort: ")
        if password != getpass("Passwort wiederholen: "):
            raise CommandError("Die Passwörter stimmen nicht überein.")
        try:
            validate_password(password, user)
        except ValidationError as error:
            raise CommandError(" ".join(error.messages)) from error
        user.set_password(password)
        with transaction.atomic():
            user.save()
            user.groups.set(Group.objects.filter(name__in=[ROLES[r] for r in roles]))
        self.stdout.write(
            f"Konto {username} angelegt. Beim ersten Anmelden wird der zweite Faktor eingerichtet."
        )
