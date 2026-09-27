# mymvz

Terminanfrage des MVZ Grevenbroich statt Doctolib, als eigene Seite neben der
bestehenden Homepage, und im selben Projekt die Praxissoftware (Stufen und
Entscheidungen in #3). Stack: Django 5.2 (LTS) mit PostgreSQL, beides in
Docker Compose, Seiten serverseitig gerendert. `README.md` beschreibt für Menschen, was es
gibt und wie man es startet.

## Wie dieses Wissen abgelegt ist

- **Diese Datei** enthält nur, was für jede Session gilt und sich nicht aus dem
  Code ergibt, dazu die Karte der Module.
- **`.claude/rules/<cluster>.md`** enthält das Warum je Modulgruppe:
  Entscheidungen, Randbedingungen und Fallen. Claude Code lädt eine Regeldatei
  erst, wenn eine Datei aus ihrem `paths:` **mit dem Read-Tool** gelesen wird.
  `cat`, `sed` oder `grep` in der Shell lösen das nicht aus. Eine Datei, die du
  ändern willst, deshalb vorher mit Read öffnen. Braucht eine Aufgabe einen
  Cluster, dessen Dateien sie nicht liest, die Regeldatei direkt lesen (Karte
  unten).
- **Die Geschichte** steht in Issues, PRs und im Git-Log: was vorher galt,
  verworfene Fassungen, Messwerte. In den Regeldateien steht davon nur die
  Issue-Nummer.

**Wohin neues Wissen gehört.** Ohne diese Regel wächst die Datei wieder.
- Das Warum einer Änderung: in die Regeldatei ihres Clusters, in der Gegenwart,
  ein bis drei Sätze, Issue-Nummer als Verweis („(#12)“).
- Wie es dazu kam, was vorher galt, Messwerte: ins Issue oder in den PR.
  Erklärt es eine bestimmte Codezeile, als Kommentar dorthin.
- In diese Datei nur, was für jede Session gilt. Ein neues Modul bekommt hier
  eine Zeile in der Karte und in einer Regeldatei einen `paths:`-Eintrag.
  Eine neue Django-App bekommt in der Regel einen eigenen Cluster.
- Grenzen: diese Datei unter 300 Zeilen, eine Regeldatei unter 250.
  `tests/test_regeln.py` prüft beides, dazu dass jede Quelldatei in einem
  `paths:` steht und jedes Muster eine Datei trifft.

## Regeln für jede Session

Die allgemeine Arbeitsweise (Issue + PR, Code-Review vor dem Merge,
Modellwahl, Secrets, Sessions) steht in `~/.claude/CLAUDE.md`. Die Vorlage
dafür liegt in `claude-arbeitsweise/global/CLAUDE.md`. Hier nur, was in diesem
Projekt dazukommt:

- **Hosting:** GitHub, [jnswde-code/mymvz](https://github.com/jnswde-code/mymvz).
  In Cloud-Sessions gibt es kein `gh`; Issues, PRs und Kommentare laufen über
  die GitHub-Tools der Session.
- **Bezeichner:** Englisch im Code (Namen, Kommentare, Docstrings), weil
  Django und die Bibliotheken englisch sind. Oberfläche, Texte für
  Patienten und Praxis, Fehlermeldungen und Commits deutsch (#3,
  Entscheidung 8). Regeldateien und `CLAUDE.md` bleiben deutsch.
- **Zweige:** `main` ist die Integrationslinie. Einen Veröffentlichungszweig
  gibt es nicht.
- **Modell:** In diesem Projekt gibt es nur Opus, kein Fable. Statt des
  Modells wird der Aufwand gewählt: `xhigh`, wo die Arbeitsweise Fable
  empfiehlt, sonst `high`.
- **Test in derselben Änderung.** Enthält eine Änderung eine Verzweigung, eine
  Regex oder eine Randbedingung, die falsch sein könnte, bekommt sie einen
  Test. Abgeschlossen ist sie erst mit einem grünen Lauf (Befehle unter
  „Tests“). Reine Verdrahtung braucht keinen Test.
- **Secrets** stehen in `.env` und werden von dort gelesen, nie in Ausgaben,
  Commits oder Dateien im Repo. Das Repo ist öffentlich. Jede neue Variable
  kommt ohne echten Wert in `.env.example`.
- **Gesundheitsdaten:** In Tests, Beispielen und Fixtures nur erfundene
  Personen und Daten (DSGVO Art. 9, #3).

## Karte: Module und ihre Regeldatei

**`django-projekt`**: Einstellungen, URLs, gemeinsame Templates
- `config/settings.py`: Django-Einstellungen, alle Werte aus `.env`
- `config/env.py`: Umgebungsvariablen lesen (`env_str`, `env_bool`, `env_list`)
- `config/urls.py`, `config/views.py`: Platzhalter-Startseite
- `config/context_processors.py`: Band „Testsystem“ bei `DATA_MODE=synthetic`
- `config/batch.py`: Läufe über viele Datensätze (`each`, `PartialFailure`),
  Regeldatei `jobs`
- `config/wsgi.py`: Einstieg für gunicorn
- `templates/`: Grundlayout `base.html` und Startseite
- `manage.py`, `tests/test_env.py`, `tests/test_home.py`

**`accounts`**: Konten, Anmeldung mit zweitem Faktor, Rollen
- `accounts/models.py`: `User` (eigenes Modell), `LoginThrottle`
- `accounts/views.py`, `accounts/middleware.py`: Anmeldung in zwei Schritten
- `accounts/second_factor.py`: TOTP und Wiederherstellungscodes (django-otp)
- `accounts/throttle.py`: Sperre nach Fehlversuchen
- `accounts/roles.py`: Rollen als Gruppen; `accounts/testing.py`: Test-Helfer
- `accounts/management/commands/`: Konten anlegen, deaktivieren, 2FA zurücksetzen
- `tests/test_accounts_*.py`

**`audit`**: Zugriffsprotokoll
- `audit/models.py`: `AccessLogEntry`; `audit/log.py`: `log_access`
- `audit/views.py`: Protokoll und Notfallzugriffe für die Verwaltung
- `tests/test_audit.py`

**`practice`**: Praxis als Stammdaten
- `practice/models.py`: `Resource` (Ärztin/Arzt, später Raum, Gerät),
  `OpeningHours` (Öffnungs- und Sprechzeiten)
- `practice/info.py`: Name, Anschrift, Telefon, Links der Homepage
- `tests/test_practice.py`

**`patients`**: Patientenstamm (K1 aus #23)
- `patients/models.py`: `Patient` (mit Sperrvermerk und Konto, #39),
  `PatientIdentifier`, `PatientHistory`, `CareTeamMember`, `ConsentToShare`
  (Freigaben, #38), `EmergencyAccess` (Notfallzugriff, #39)
- `patients/services.py`: alle Änderungen, Dublettenhinweis, Suche,
  `retain_until`
- `patients/views.py`, `patients/forms.py`: Seiten fürs Team unter
  `/patienten/`
- `patients/management/commands/seed_demo.py`: erfundene Patienten

**`records`**: Akte mit unveränderlichen Fassungen (K2.1 aus #27)
- `records/models.py`: Basis `VersionedRecord`, `Encounter`, `ChartEntry`,
  `ChartEntryType`; Trigger in `records/migrations/0002_*`
- `records/services.py`: alle Schreibwege (anlegen, korrigieren, Irrtum)
- `records/access.py`: die eine Rechteprüfung (`visible_to`, `can_view`,
  `can_change`)
- `records/views.py`, `records/forms.py`, `records/diff.py`: Akte-Ansicht
  unter `/patienten/<id>/akte/` mit Verlauf und Unterschieden

**`appointments`**: Terminanfrage für Patienten, Termine, Links, Mails
- `appointments/models.py`: Anfrage, Wunschzeiträume, Termin, Verlauf, Tokens,
  Postausgang `OutgoingMail`
- `appointments/services.py`: alle Zustandsübergänge und Löschfristen
- `appointments/deadlines.py`: Fristen in Europe/Berlin
- `appointments/tokens.py`, `appointments/mail.py`: Links und Mails, Versand
  aus dem Postausgang
- `appointments/captcha.py`, `appointments/spam.py`: Schutz vor Spam
- `appointments/views.py`, `appointments/forms.py`: Formular und Link-Seiten
- `appointments/staff_views.py`, `staff_forms.py`, `staff_urls.py`: Anfragen
  fürs Team unter `/anfragen/`
- `tests/test_appointments_*.py`, `tests/factories.py`, `tests/conftest.py`

**`jobs`**: Worker, Läufe des Systems (#9)
- `jobs/management/commands/run_worker.py`: Dauerprozess im Dienst `worker`;
  `worker_health.py`: Healthcheck
- `jobs/runner.py`: Aufgaben, Takte, `JobRun`; `jobs/alerts.py`: Meldung an
  `OPERATIONS_ALERT_EMAIL`
- `jobs/models.py`: `JobRun`

**`telephony`**: Telefonassistent auf Seite der Website (#14)
- `telephony/api.py`, `telephony/urls.py`: interne API für den Sprachdienst
  unter `/intern/telefon/` (Auskunft, Terminarten, Wunschtag, Anfrage,
  Rückrufbitte, Ende des Anrufs)
- `telephony/models.py`: `CallbackRequest` (Rückrufbitte), `CallRecord`
  (Anruf ohne Nummer und Inhalt)
- `telephony/services.py`: alle Änderungen, Fristen, Zählen der Anrufe;
  `telephony/mail.py`: Hinweis an die Praxis
- `telephony/staff_views.py`: Liste fürs Team unter `/rueckrufe/`

**`reporting`**: Zählerstände ohne Personenbezug
- `reporting/models.py`: `RequestStatistic`, `CallStatistic`;
  `tests/test_reporting.py`

**`betrieb`**: Container, Compose, CI, Werkzeugkonfiguration
- `Dockerfile`: Stufen `base`, `dev`, `prod`
- `docker-compose.yml`: Entwicklung und Tests mit PostgreSQL, Dienst `worker`
- `.github/workflows/ci.yml`: Linter, Migrationsprüfung und Tests bei Push
  auf `main` und bei jedem PR
- `pyproject.toml`: pytest und ruff; Abhängigkeiten in `requirements*.txt`

**`voice`**: Sprachdienst mit LiveKit Agents, eigenes Image (#13)
- `voice/mymvz_voice/agent.py`: Worker, Agent, Weiche im `llm_node`,
  LiveKit-Einstellungen ohne Cloud
- `voice/mymvz_voice/tools.py`, `api_client.py`: Werkzeuge des LLM über die
  interne API von `telephony`
- `voice/mymvz_voice/safety.py`: Wortfilter vor dem LLM;
  `handoff.py`, `texts.py`: Weiterleitung und feste Ansagen
- `voice/mymvz_voice/providers/`: Anbieterwahl per `.env`, Attrappen in `fake.py`
- `voice/mymvz_voice/call_report.py`: Meldung des Anrufs am Ende
- `voice/mymvz_voice/log_privacy.py`, `latency.py`, `config.py`, `join_token.py`
- `voice/Dockerfile`, `voice/requirements*.txt`, `voice/tests/`

**`werkzeug`**: Prüfungen der Projektablage selbst
- `tests/test_regeln.py`: wacht über `CLAUDE.md`, `.claude/rules/` und die
  Zuordnung jeder Quelldatei zu einem Cluster

**`tests`**: Teststrategie für alle Tests (Pflichtfälle, Muster, Werkzeuge)
- `**/tests/**`: jede Testdatei, zusätzlich zur Regeldatei ihres Moduls
- `pyproject.toml`: Coverage-Anzeige

`claude-arbeitsweise/` (Quellpaket), `.claude/skills/` und
`.claude/agents/` gehören zu keinem Cluster.

## Tests

Tests und Werkzeuge laufen im Docker-Container, nicht mit dem Python des
Hosts: Lokal ist `python3` unter Windows nur ein Platzhalter, und der
Container entspricht dem späteren Betrieb. Einmal `.env` aus `.env.example`
anlegen (`cp .env.example .env`); die Beispielwerte reichen für Tests.

    docker compose run --rm web pytest
    docker compose run --rm --no-deps web sh -c "ruff check . && ruff format --check ."

Nach einer Änderung an `requirements*.txt` oder am `Dockerfile` vorher
`docker compose build web`. Formatieren: `ruff format .` im selben Container.
Die CI (`.github/workflows/ci.yml`) baut das Image und führt dieselben
Befehle aus, dazu `python manage.py makemigrations --check --dry-run`.
Der Sprachdienst hat ein eigenes Image (Regeldatei `voice`); ruff oben
prüft ihn mit, die Tests laufen in seinem Container (nach Änderungen an
`voice/requirements*.txt` oder `voice/Dockerfile` vorher
`docker compose --profile voice build voice`):

    docker compose --profile voice run --rm --no-deps voice pytest

`pytest` zeigt Branch-Coverage an, ohne Mindestquote. E2E-Tests
(Playwright) kommen in einem Folge-PR zu #7 nach #13 und bekommen dann
einen eigenen Befehl.

**Pflichtfälle** (Warum und Muster in `.claude/rules/tests.md`, #22):
- jede Verzweigung, Regex oder Randbedingung, die falsch sein könnte,
- jede Berechtigungsprüfung, immer auch der verbotene Fall (fremde Termine
  und Patienten, fehlende Rolle, abgelaufener Link); die Rechtematrix aus
  #23 vollständig als Tabelle,
- Unveränderlichkeit der Akte auch per rohem SQL,
- Löschfristen und Aufbewahrung, am Stichtag und daneben,
- Zeitlogik in `Europe/Berlin`: Zeitumstellung, Mitternacht, Monatswechsel,
- jede Migration, die Daten verändert,
- jeder behobene Fehler: erst der rote Test, dann der Fix.

Tests prüfen Verhalten von außen (Antwort, Datenbank, Mail); Mocks nur an
Systemgrenzen (Mail, SMS, KI-Anbieter, Uhr). Testdaten über Factories
(`factory_boy`), Zeit mit `time-machine`.

## Starten

    docker compose run --rm web python manage.py migrate
    docker compose up

Die Seite läuft dann unter http://localhost:8000, die Terminanfrage unter
`/termin/`. Der Dienst `worker` sendet die Mails und lässt Vorschläge und
Anfragen verfallen. `DJANGO_DEBUG=1` in der `.env` ist dafür nötig, sonst lehnt
Django `localhost` ab. Mails erscheinen in der Konsole des Workers.
