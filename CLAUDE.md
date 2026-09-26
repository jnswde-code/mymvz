# mymvz

Website des MVZ Grevenbroich mit eigener Terminanfrage statt Doctolib. Im
selben Projekt wächst später die Praxissoftware (Stufen und Entscheidungen in
#3). Stack: Django 5.2 (LTS) mit PostgreSQL, beides in Docker Compose,
Seiten serverseitig gerendert. `README.md` beschreibt für Menschen, was es
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
- `config/wsgi.py`: Einstieg für gunicorn
- `templates/`: Grundlayout `base.html` und Startseite
- `manage.py`, `tests/test_env.py`, `tests/test_home.py`

**`betrieb`**: Container, Compose, CI, Werkzeugkonfiguration
- `Dockerfile`: Stufen `base`, `dev`, `prod`
- `docker-compose.yml`: Entwicklung und Tests mit PostgreSQL
- `.github/workflows/ci.yml`: Linter, Migrationsprüfung und Tests bei Push
  auf `main` und bei jedem PR
- `pyproject.toml`: pytest und ruff; Abhängigkeiten in `requirements*.txt`

**`werkzeug`**: Prüfungen der Projektablage selbst
- `tests/test_regeln.py`: wacht über `CLAUDE.md`, `.claude/rules/` und die
  Zuordnung jeder Quelldatei zu einem Cluster

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

## Starten

    docker compose run --rm web python manage.py migrate
    docker compose up

Die Seite läuft dann unter http://localhost:8000. `DJANGO_DEBUG=1` in der
`.env` ist dafür nötig, sonst lehnt Django `localhost` ab.
