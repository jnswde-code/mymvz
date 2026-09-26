---
paths:
  - "accounts/**"
  - "tests/test_accounts_*.py"
---
# Konten: Anmeldung, zweiter Faktor, Rollen

## accounts/models.py

- `accounts.User` ist das eigene Benutzermodell und die erste eigene
  Migration; nachträglich umzustellen ist in Django teuer (#5, #25).
  Primärschlüssel UUID wie alle Tabellen mit Personenbezug (#5).
- Konten werden deaktiviert, nie gelöscht: Das Zugriffsprotokoll verweist mit
  `PROTECT` auf sie. `User.delete()` wirft deshalb `ProtectedError`.

## accounts/views.py, accounts/middleware.py

- Django-`login()` läuft erst nach dem Code. Zwischen Passwort und Code steht
  in der Sitzung nur die ID des wartenden Kontos (10 Minuten), `request.user`
  bleibt anonym. Deshalb reicht in Ansichten `login_required`; django-otps
  `otp_required` ist nicht nötig (#25).
- `RequireSecondFactorMiddleware` meldet jede angemeldete, aber nicht per
  zweitem Faktor bestätigte Sitzung ab. Sie steht hinter `OTPMiddleware`. In
  Tests deshalb `accounts.testing.login_with_second_factor` statt
  `client.force_login`.
- Einrichten der App geht nur für Konten ohne bestätigtes Gerät, sonst
  reichte das Passwort, um ein zweites Telefon anzumelden. Wer sein Telefon
  verliert, bekommt es per `reset_second_factor` zurückgesetzt.
- Wiederherstellungscodes erscheinen genau einmal, in der Antwort auf das
  Einrichten, und stehen nie in der Sitzung. django-otp speichert sie im
  Klartext; sie gelten nur zusammen mit dem Passwort.
- Die Admin-Oberfläche von Django ist nicht eingebunden; sie umginge Rollen
  und Zugriffsprotokoll (#8).

## accounts/second_factor.py

- TOTP mit django-otp statt eigener Kryptografie: gepflegt, mit
  Wiederholungsschutz (`last_t`) und Verzögerung je Gerät. Sechs Ziffern
  gehen an die App, alles andere an die Wiederherstellungscodes, sonst
  zählte jeder Fehlversuch an beiden Geräten.

## accounts/throttle.py

- Sperre je Kontoname (5 Fehlversuche) und je Adresse (20) für 15 Minuten.
  Beide Schritte zählen. Die Adressgrenze ist hoch, weil die Praxis eine
  gemeinsame öffentliche Adresse hat.
- Ein Versuch wird vor der Prüfung gezählt und bei Erfolg zurückgenommen.
  Zählte er erst danach, kämen parallele Anfragen alle an der Sperre vorbei,
  solange das Passwort-Hashing läuft.
- Gespeichert wird nur ein HMAC von Name bzw. Adresse (#5, #25).
  `purge_expired` entfernt abgelaufene Zeilen bei jedem Versuch; der
  Löschlauf (#9) soll es zusätzlich regelmäßig aufrufen, damit nach dem
  letzten Fehlversuch nichts liegen bleibt. Mit `SECRET_KEY` ließe sich eine
  IPv4-Adresse aus dem HMAC zurückrechnen.
- Auch unbekannte Namen werden gesperrt, damit die Sperre nicht verrät, ob es
  ein Konto gibt.
- `client_address` liest `REMOTE_ADDR`. Hinter Caddy (#10) muss es die von
  Caddy weitergereichte Adresse lesen, sonst teilen sich alle eine Sperre.

## accounts/roles.py, accounts/migrations/0002_roles.py

- Rollen sind Gruppen nach #23 Abschnitt 5.1, angelegt per Datenmigration.
  Migrationen tragen eine eigene Kopie der Liste, eine Änderung an
  `roles.py` braucht also eine neue Datenmigration. Ein Test prüft, dass die
  Gruppen nach allen Migrationen `roles.py` entsprechen.
- Heute hat nur die Verwaltung ein Recht (Zugriffsprotokoll lesen). Die
  Prüfung je Datensatz und Schutzstufen kommen mit K2 (#23), nicht hier.

## accounts/management/commands/

- Konten entstehen per `create_account` (Passwort verdeckt, mindestens 12
  Zeichen), bis das Backoffice eine Oberfläche bekommt.
