---
paths:
  - "reporting/**"
  - "tests/test_reporting.py"
---
# Auswertungen: Zählerstände ohne Personenbezug

## reporting/models.py

- Statt Pseudonymisierung zählt der Löschlauf (#9) jede Anfrage vor dem
  Löschen in `RequestStatistic` hoch (#5 Abschnitt 6, Entscheidung 6).
  Pseudonyme Gesundheitsdaten blieben personenbezogen; Zählerstände nach
  Woche, Terminart, Kanal und Ergebnis sind anonym und dürfen bleiben.
- Kein Geburtsdatum, keine Altersgruppe, kein Name, keine ID; ein Test hält
  die Feldliste fest. Geschrieben wird hier noch nichts, das kommt mit #9.
- `CallStatistic` zählt Anrufe des Telefonassistenten nach Woche,
  Betriebsart und Ergebnis, eine eigene Tabelle neben `RequestStatistic`,
  weil Anrufe keine Anfragen sind (#14, Entscheidung 4 vom 27.09.).
  Geschrieben wird sie nur von `telephony.services`, wenn ein `CallRecord`
  nach 30 Tagen gelöscht wird (#45). Betriebsart und Ergebnis als Text ohne
  `choices`, damit alte Zählerstände eine Änderung der Listen überstehen.
