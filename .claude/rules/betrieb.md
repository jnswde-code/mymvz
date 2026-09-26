---
paths:
  - "Dockerfile"
  - "docker-compose.yml"
  - ".github/workflows/*.yml"
  - "pyproject.toml"
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
- Tests laufen gegen PostgreSQL im Compose, nicht gegen SQLite: Später
  zählen Postgres-Eigenheiten (Zeitzonen, Sperren, Constraints).

## .github/workflows/ci.yml

- CI benutzt dieselben Compose-Befehle wie lokal und nimmt `.env.example` als
  `.env`. Die Werte dort taugen deshalb zum Testen, aber nie für den Betrieb.
- `makemigrations --check` hält fest, dass zu jeder Modelländerung eine
  Migration gehört.

## pyproject.toml

- Einstellungen für pytest und ruff. `claude-arbeitsweise/` ist von ruff
  ausgenommen, es ist Quellpaket, kein Projektcode.
