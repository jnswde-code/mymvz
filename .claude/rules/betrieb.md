---
paths:
  - "Dockerfile"
  - "docker-compose.yml"
  - ".github/workflows/*.yml"
  - "pyproject.toml"
  - "requirements*.txt"
  - ".dockerignore"
---
# Betrieb: Container, Compose, CI, Werkzeugkonfiguration

## Dockerfile

- Drei Stufen: `base` mit den Laufzeit-Abhängigkeiten, `dev` mit pytest und
  ruff für Entwicklung und Tests, `prod` für den Betrieb (gunicorn, ohne
  root). `.dockerignore` hält `.env` aus dem Image heraus, das Repo ist
  öffentlich.
- Django bleibt auf der LTS-Linie (`~=5.2.0` in `requirements.txt`), weil
  der Betrieb drei Jahre Sicherheitsupdates braucht (#3, Abschnitt 3).

## docker-compose.yml

- Nur Entwicklung und Tests: `runserver`, Code als Volume, Port 8000. Der
  Betrieb mit Caddy, gunicorn und Worker bekommt eine eigene Datei (#10).
- Der Healthcheck fragt Postgres über TCP (`-h 127.0.0.1`): Beim ersten Start
  läuft kurz ein Init-Server nur auf dem Socket, und `web` startete sonst zu
  früh. `db` bekommt nur die `POSTGRES_*`-Variablen, nicht die ganze `.env`.
- Tests laufen gegen PostgreSQL im Compose, nicht gegen SQLite: Später
  zählen Postgres-Eigenheiten (Zeitzonen, Sperren, Constraints).
- `livekit` und `voice` stehen im Profil `voice` und starten nur mit
  `--profile voice` (Regeldatei `voice`, #13).
- `voice` hängt an `web`, weil der Agent die interne API von `telephony`
  über `http://web:8000` erreicht; `web` muss dafür in
  `DJANGO_EXTRA_HOSTS` stehen (#44).

## .github/workflows/ci.yml

- Läuft bei Push auf `main` und bei jedem PR; ein Push auf einen PR-Zweig
  löst so nur einen Lauf aus, nicht zwei.
- CI benutzt dieselben Compose-Befehle wie lokal und nimmt `.env.example` als
  `.env`. Die Werte dort taugen deshalb zum Testen, aber nie für den Betrieb.
- `makemigrations --check` hält fest, dass zu jeder Modelländerung eine
  Migration gehört.
- Der Sprachdienst wird als eigenes Image gebaut und in seinem Container
  getestet; ruff prüft ihn im Schritt „Lint“ mit (#13).

## pyproject.toml

- Einstellungen für pytest und ruff. `claude-arbeitsweise/` ist von ruff
  ausgenommen, es ist Quellpaket, kein Projektcode. `src` nennt `voice`,
  damit ruff `mymvz_voice` als eigenes Paket sortiert.
