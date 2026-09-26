# mymvz

Neue Website des MVZ Grevenbroich mit eigener Terminanfrage (statt
Doctolib). Später wächst im selben Projekt die Praxissoftware. Konzept und
Entscheidungen stehen in Issue #3.

Stand: Grundgerüst. Django 5.2 (LTS) mit PostgreSQL in Docker Compose und
eine Platzhalter-Startseite, die zeigt, ob Anwendung und Datenbank laufen.

## Voraussetzungen

Docker mit Docker Compose. Python auf dem Rechner ist nicht nötig, alles
läuft im Container.

## Starten

    cp .env.example .env
    docker compose run --rm web python manage.py migrate
    docker compose up

Dann http://localhost:8000 öffnen.

Die `.env` enthält Zugangsdaten und kommt nie ins Repo, das Repo ist
öffentlich. Für den Betrieb `DJANGO_SECRET_KEY` und `POSTGRES_PASSWORD`
durch lange Zufallswerte ersetzen und `DJANGO_DEBUG=0` setzen.

## Tests und Linter

    docker compose run --rm web pytest
    docker compose run --rm --no-deps web sh -c "ruff check . && ruff format --check ."

Dieselben Befehle laufen in GitHub Actions bei Push auf `main` und bei jedem
Pull Request.

## Aufbau

| Pfad | Inhalt |
|---|---|
| `config/` | Django-Einstellungen (Werte aus `.env`), URLs, Startseite |
| `templates/` | gemeinsame Templates |
| `tests/` | pytest-Tests, darunter `test_regeln.py` für die Projektablage |
| `Dockerfile`, `docker-compose.yml` | Container für Entwicklung, Tests und Betrieb |
| `.github/workflows/` | CI |
| `CLAUDE.md`, `.claude/` | Arbeitsweise für Claude Code |
| `claude-arbeitsweise/` | Quellpaket dieser Arbeitsweise |
