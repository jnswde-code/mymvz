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
- Keine eigenen Django-Apps im Gerüst. `website`, `appointments` und später
  `patients` legen ihre Issues an (#6, #7, #5); dann kommen sie hier in
  `INSTALLED_APPS` und in die Karte in `CLAUDE.md`. Die Admin-Oberfläche ist
  nicht eingebunden, das Backoffice ist #8.

## config/views.py, templates/home.html

- Die Startseite ist ein Platzhalter und zeigt, ob die Datenbank erreichbar
  ist, mit 503, wenn nicht. Die Inhaltsseiten (#6) ersetzen sie.
