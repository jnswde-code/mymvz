# mymvz

Neue Website des MVZ Grevenbroich mit eigener Terminanfrage (statt
Doctolib). Später wächst im selben Projekt die Praxissoftware. Konzept und
Entscheidungen stehen in Issue #3.

Stand: Grundgerüst. Django 5.2 (LTS) mit PostgreSQL in Docker Compose und
eine Platzhalter-Startseite, die zeigt, ob Anwendung und Datenbank laufen.
Dazu Konten fürs Praxisteam mit Pflicht zum zweiten Faktor (TOTP-App),
Rollen und ein Zugriffsprotokoll.

## Voraussetzungen

Docker mit Docker Compose. Python auf dem Rechner ist nicht nötig, alles
läuft im Container.

## Starten

    cp .env.example .env
    docker compose run --rm web python manage.py migrate
    docker compose up

Dann http://localhost:8000 öffnen.

**Wer vor dem eigenen Benutzermodell (#25) schon migriert hat**, setzt die
Datenbank einmal zurück, sonst passt das Schema nicht:

    docker compose down -v
    docker compose run --rm web python manage.py migrate

Die `.env` enthält Zugangsdaten und kommt nie ins Repo, das Repo ist
öffentlich. Für den Betrieb `DJANGO_SECRET_KEY` und `POSTGRES_PASSWORD`
durch lange Zufallswerte ersetzen und `DJANGO_DEBUG=0` setzen.

## Konten

Konten legt man auf der Kommandozeile an; das Passwort wird verdeckt
abgefragt (mindestens 12 Zeichen). Rollen: `doctor`, `mfa`,
`administration`, `psychology`, `addiction_therapy`, `nutrition`.

    docker compose run --rm web python manage.py create_account erika.beispiel --role mfa

Anmelden unter http://localhost:8000/anmelden/. Beim ersten Mal richtet man
eine Authenticator-App ein (QR-Code) und bekommt zehn
Wiederherstellungscodes. Weitere Befehle:

    docker compose run --rm web python manage.py deactivate_account erika.beispiel
    docker compose run --rm web python manage.py reset_second_factor erika.beispiel

Konten werden nie gelöscht, nur deaktiviert.

## Tests und Linter

    docker compose run --rm web pytest
    docker compose run --rm --no-deps web sh -c "ruff check . && ruff format --check ."

Dieselben Befehle laufen in GitHub Actions bei Push auf `main` und bei jedem
Pull Request.

## Aufbau

| Pfad | Inhalt |
|---|---|
| `config/` | Django-Einstellungen (Werte aus `.env`), URLs, Startseite |
| `accounts/` | Konten, Anmeldung mit zweitem Faktor, Rollen |
| `audit/` | Zugriffsprotokoll |
| `templates/` | gemeinsame Templates |
| `tests/` | pytest-Tests, darunter `test_regeln.py` für die Projektablage |
| `Dockerfile`, `docker-compose.yml` | Container für Entwicklung, Tests und Betrieb |
| `.github/workflows/` | CI |
| `CLAUDE.md`, `.claude/` | Arbeitsweise für Claude Code |
| `claude-arbeitsweise/` | Quellpaket dieser Arbeitsweise |
