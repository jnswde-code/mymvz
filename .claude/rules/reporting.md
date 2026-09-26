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
