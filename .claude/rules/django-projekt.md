---
paths:
  - "manage.py"
  - "config/**"
  - "templates/**"
  - "tests/test_{env,home}.py"
  - ".env.example"
---
# Django-Projekt: Einstellungen, URLs, gemeinsame Templates

## config/settings.py, config/env.py

- Alles, was sich zwischen Rechnern unterscheidet, kommt aus `.env`, auch der
  öffentliche Hostname `SITE_HOST`: Er ist zuerst `mymvz.jnsw.de`, später
  `mymvz.de` (#10). `.env.example` nennt jede Variable ohne echten Wert.
- `env_bool` bricht bei unbekannten Werten ab, statt still `False` zu nehmen:
  Ein Tippfehler bei `DJANGO_DEBUG` soll nicht unbemerkt die Einstellung
  kippen (#4).
- `localhost` steht nur mit `DJANGO_DEBUG=1` in `ALLOWED_HOSTS`.
- `env_str` behandelt `NAME=` wie eine fehlende Variable, sonst liefe ein
  leerer `SITE_HOST` oder ein leeres Passwort still durch.
- HTTPS-Umleitung, HSTS und `SECURE_PROXY_SSL_HEADER` fehlen bewusst
  (`check --deploy` warnt): Sie kommen mit Caddy im Betrieb (#10). Ohne
  Proxy davor könnte jeder Client `X-Forwarded-Proto` selbst setzen.
- Neue Apps kommen mit ihrem Issue in `INSTALLED_APPS` und in die Karte in
  `CLAUDE.md`. Die Admin-Oberfläche ist nicht eingebunden, das Backoffice ist
  #8.
- `AUTH_USER_MODEL = "accounts.User"` stand vor der ersten eigenen Migration
  (#25). Die Middleware-Reihenfolge Authentication → `OTPMiddleware` →
  `RequireSecondFactorMiddleware` ist nötig (Regeldatei `accounts`).
- Sitzungen enden nach 30 Minuten ohne Anfrage (`SESSION_SAVE_EVERY_REQUEST`)
  und mit dem Browser (#25).

## templates/base.html

- Zeigt angemeldeten Konten Name, Konto-Link und Abmelden (POST).

## config/views.py, templates/home.html

- Die Startseite ist ein Platzhalter und zeigt, ob die Datenbank erreichbar
  ist, mit 503, wenn nicht. Die Inhaltsseiten (#6) ersetzen sie.
