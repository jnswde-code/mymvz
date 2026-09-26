---
paths:
  - "practice/**"
  - "tests/test_practice.py"
---
# Praxis: Ressourcen, Öffnungszeiten, feste Angaben

## practice/models.py

- `Resource` statt nur Ärztinnen und Ärzte, weil TPS Gerät und Person
  braucht und die Sperre gegen Doppelbuchung in Stufe 2 eine Tabelle braucht
  (#5, Entscheidung 9). In Stufe 1 gibt es nur `doctor`; angelegt werden sie
  mit dem Backoffice (#8), bis dahin ist die Wunsch-Ärztin im Formular
  ausgeblendet.
- `OpeningHours` ist die eine Quelle für angezeigte Öffnungszeiten, die
  Prüfung der Wunschzeiträume und später Sprechzeiten-Blöcke (#5).
  Vormittags heißt ein Sprechzeit-Block, der vor 13 Uhr beginnt, nachmittags
  einer, der nach 13 Uhr endet.

## practice/migrations/0002_opening_hours.py

- Zeiten von der bestehenden Homepage. Deren Sprechzeiten reichen über die
  Öffnungszeiten hinaus (#3, Bestandsaufnahme); die Migration schneidet sie
  auf die Öffnungszeiten zu. Von der Praxis zu bestätigen.

## practice/info.py

- Name, Anschrift, Telefon und Links der bestehenden Homepage, für Layout und
  Mails. Impressum und Datenschutzerklärung bleiben Sache der Praxis (#3).
