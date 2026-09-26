---
paths:
  - "audit/**"
  - "tests/test_audit.py"
---
# Zugriffsprotokoll

## audit/models.py

- `AccessLogEntry` hält Typ und ID, nie Namen oder Inhalte (#5). Nach dem
  Löschen eines Datensatzes zeigt der Eintrag auf nichts mehr. Ein Test
  hält die Feldliste fest; ein neues Feld braucht einen Grund.
- `patient_id` ist eine UUID ohne Fremdschlüssel, damit sich „wer hat die
  Akte von Patient X gesehen“ beantworten lässt, auch nach dem Löschen des
  Patienten (#23 Abschnitt 3.2).
- Einträge werden nie geändert (`save()` auf bestehende wirft). Gelöscht wird
  nur nach Frist: 1 Jahr für Anfragen (#5, Löschlauf in #9), für die Akte
  3 Jahre (#23, Entscheidung 10).
- Suchen: nur die Trefferzahl, nie der Suchbegriff.

## audit/log.py

- `log_access(user, action, target)` ist der eine Weg, Einträge zu schreiben.
  `target` ist ein Datensatz (Detail, Änderung) oder eine Modellklasse (Liste,
  Suche); eine Liste ist ein Eintrag, nicht einer je Zeile (#5).
- Protokolliert wird, nachdem die Rechteprüfung bestanden ist; abgewiesene
  Zugriffe schreiben keinen Eintrag.

## audit/views.py

- Nur die Verwaltung liest das Protokoll (#23 Abschnitt 5.1), und auch das
  wird protokolliert.
