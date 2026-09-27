# mymvz

Eigene Terminanfrage des MVZ Grevenbroich (statt Doctolib), als Seite neben
der bestehenden Homepage. Im selben Projekt wächst die Praxissoftware.
Konzept und Entscheidungen stehen in Issue #3.

Stand: Django 5.2 (LTS) mit PostgreSQL in Docker Compose. Konten fürs
Praxisteam mit Pflicht zum zweiten Faktor (TOTP-App), Rollen und ein
Zugriffsprotokoll. Die Terminanfrage für Patienten unter `/termin/`: Formular
mit Spam-Schutz, Bestätigung der E-Mail-Adresse, Links zum Zurückziehen,
Annehmen eines Vorschlags und Absagen. Ein Patientenstamm fürs Team unter
`/patienten/` (Suche, Anlegen mit Dublettenhinweis, Kennungen, Verlauf der
Stammdaten) und dazu die Akte mit Kontakten und Karteikarteneinträgen:
Korrekturen legen neue Fassungen an, der Verlauf zeigt die Unterschiede,
und die Datenbank verweigert Überschreiben und Löschen. Offene Terminanfragen
sieht das Team unter `/anfragen/` (Ärztin/Arzt und MFA): mit Hinweisen wie
„Telefon“ oder „ohne E-Mail – Rückruf nötig“, bestätigen, anderen Termin
vorschlagen oder ablehnen, interne Notiz. Unter `/anfragen/termine/` stehen
die Termine, die noch in Medical Office ein- oder dort auszutragen sind, die
kommenden und die Absagen der letzten 14 Tage. Auf der Anfrage sagt das Team
Termine ab (für die Praxis oder nach einem Anruf), zieht Vorschläge zurück und
ordnet die Anfrage nach einem Namensvergleich einem Patienten zu. Der
Löschlauf folgt mit #9.

## Voraussetzungen

Docker mit Docker Compose. Python auf dem Rechner ist nicht nötig, alles
läuft im Container.

## Starten

    cp .env.example .env
    docker compose run --rm web python manage.py migrate
    docker compose up

Dann http://localhost:8000/termin/ öffnen. Mails erscheinen in der Konsole
(`docker compose up` zeigt sie). Damit die Links darin auf den eigenen
Rechner zeigen, in der `.env` `SITE_BASE_URL=http://localhost:8000` setzen.

**Wer eine `.env` von vor #7 hat**, ergänzt die neuen Variablen aus
`.env.example` (`DEFAULT_FROM_EMAIL`, `PRACTICE_NOTIFICATION_EMAIL` und die
`EMAIL_*`-Werte), sonst startet Django nicht.

**Wer eine `.env` von vor #26 hat**, kann `DATA_MODE=synthetic` ergänzen;
ohne den Eintrag gilt dieselbe Vorgabe.

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

## Testdaten

Das System läuft mit `DATA_MODE=synthetic` (Vorgabe) und zeigt dann auf
jeder Seite das Band „Testsystem – nur erfundene Daten“. Echte
Patientendaten gehören nicht hinein. Erfundene Patienten legt an:

    docker compose run --rm web python manage.py seed_demo --count 20

Mit `--author <konto>` bekommen die Patienten auch erfundene Kontakte und
Einträge in der Akte; das Konto braucht die Rolle Ärztin/Arzt oder MFA.

## Sprachdienst (Prototyp)

Ein Sprachagent mit [LiveKit Agents](https://docs.livekit.io/agents/)
(#13), Grundlage für den Telefonassistenten (#14). Er läuft als eigener
Dienst neben der Website, mit einem LiveKit-Server im Container:

    docker compose --profile voice up

Spracherkennung, LLM und Sprachausgabe wählt man in der `.env`
(`VOICE_STT_PROVIDER`, `VOICE_LLM_PROVIDER`, `VOICE_TTS_PROVIDER`). Bis
die Anbieter gewählt sind (#18), gibt es nur `fake`: Die Attrappe „hört“
nach jeder Sprechpause denselben Satz und antwortet mit einem Piepton.
Nur erfundene Daten, keine echten Patientendaten.

Im Browser sprechen: einen Zugang erzeugen,

    docker compose --profile voice run --rm voice python -m mymvz_voice.join_token --room test-1

dann https://meet.livekit.io öffnen, Reiter „Custom“, Server
`ws://localhost:7880` und den Zugang eintragen. Der Agent tritt dem Raum
von selbst bei; für jeden Versuch einen neuen Raumnamen nehmen. Die Latenz
vom Satzende bis zur Antwort steht je Antwort im Log des Dienstes `voice`.

## Tests und Linter

    docker compose run --rm web pytest
    docker compose run --rm --no-deps web sh -c "ruff check . && ruff format --check ."
    docker compose --profile voice run --rm --no-deps voice pytest

Dieselben Befehle laufen in GitHub Actions bei Push auf `main` und bei jedem
Pull Request.

## Aufbau

| Pfad | Inhalt |
|---|---|
| `config/` | Django-Einstellungen (Werte aus `.env`), URLs, Startseite |
| `accounts/` | Konten, Anmeldung mit zweitem Faktor, Rollen |
| `audit/` | Zugriffsprotokoll |
| `practice/` | Ärztinnen/Ärzte als Ressourcen, Öffnungs- und Sprechzeiten |
| `patients/` | Patientenstamm: Stammdaten, Kennungen, Verlauf, Behandlungsteam |
| `records/` | Akte: Kontakte und Karteikarte in unveränderlichen Fassungen |
| `appointments/` | Terminanfrage, Termine, Links in Mails, Spam-Schutz |
| `reporting/` | Zählerstände ohne Personenbezug für Auswertungen |
| `templates/` | gemeinsame Templates |
| `voice/` | Sprachdienst mit eigenem Image |
| `tests/` | pytest-Tests, darunter `test_regeln.py` für die Projektablage |
| `Dockerfile`, `docker-compose.yml` | Container für Entwicklung, Tests und Betrieb |
| `.github/workflows/` | CI |
| `CLAUDE.md`, `.claude/` | Arbeitsweise für Claude Code |
| `claude-arbeitsweise/` | Quellpaket dieser Arbeitsweise |
