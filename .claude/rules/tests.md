---
paths:
  - "**/tests/**"
  - "pyproject.toml"
---
# Tests: was getestet wird, wie und womit

Ziel ist, dass Tests Fehler finden, nicht Zeilen abdecken. mymvz wächst zur
Praxissoftware; Fehler bei Berechtigung, Datentrennung, Löschfristen oder
Zeitzonen fielen sonst erst im Betrieb auf (#22). Die Pflichtfälle stehen als
Liste in `CLAUDE.md`, „Tests“; hier das Warum dazu.

## Wo und womit

- Alles läuft im Container gegen PostgreSQL, lokal wie in der CI mit
  demselben Befehl; ein roter Lauf blockiert den Merge. SQLite verhält sich bei
  Zeitzonen, Sperren und Constraints anders (#4, `betrieb.md`).
- pytest mit pytest-django. Testdaten kommen aus Factories (`factory_boy`),
  nicht aus Fixture-Dateien: Eine Factory setzt nur, was der Test braucht,
  der Rest ist gültig und erfunden, und ein neues Pflichtfeld bricht eine
  Stelle statt jeder Fixture.
- Zeit wird mit `time-machine` eingefroren, nie mit `sleep` oder mit der
  echten Uhr verglichen. Ein Test, der nur an bestimmten Tagen oder zur
  Umstellung auf Sommerzeit rot wird, ist sonst nicht wiederholbar.
- E2E im Browser (Playwright) nur für die kritischen Wege, zuerst die
  Terminanfrage. Eingerichtet wird das in einem Folge-PR zu #7, sobald #13
  `docker-compose.yml` und die CI nicht mehr ändert; E2E laufen dann
  getrennt von der Suite, in der CI immer.

## Pflichtfälle

- **Verzweigung, Regex, Randbedingung**, die falsch sein könnte: der Fall
  links und rechts der Grenze, nicht nur der glückliche Weg.
- **Berechtigung immer mit dem verbotenen Fall.** Fremder Termin, fremder
  Patient, fehlende Rolle, abgelaufener oder schon benutzter Link (#8). Ein
  Test, der nur zeigt, dass die Ärztin ihren Patienten sieht, findet das Leck
  nicht, dass sie auch fremde sieht. Die Rechtematrix aus #23 wird als
  Tabelle getestet (`pytest.mark.parametrize` über Rolle × Aktion ×
  erwartetes Ergebnis), damit keine Zelle fehlt.
- **Akte unveränderlich**, auch am ORM vorbei: Ein Test versucht `UPDATE`
  und `DELETE` per rohem SQL (`connection.cursor()`) und erwartet den Fehler
  der Datenbank. Eine Sperre nur im Model ließe sich sonst mit
  `QuerySet.update()` oder einer Migration umgehen (#23).
- **Löschfristen und Aufbewahrung** (#9): genau am Stichtag, einen Tag davor,
  einen danach; und dass Aufzubewahrendes nicht mitgelöscht wird.
- **Zeit mit `Europe/Berlin`**: Sommer-/Winterzeitwechsel (die Stunde, die es
  nicht gibt, und die, die es zweimal gibt), Mitternacht, Monats- und
  Jahreswechsel. Gespeichert wird UTC; der Fehler steckt in der Umrechnung.
- **Migration, die Daten verändert**: Zustand vorher anlegen, Migration
  ausführen, Zustand nachher prüfen. Reine Schemamigrationen prüft
  `makemigrations --check` in der CI.
- **Behobener Fehler**: erst ein Test, der ihn zeigt und rot ist, dann der
  Fix. Sonst ist nicht belegt, dass der Test den Fehler überhaupt trifft.

Keinen Test brauchen reine Verdrahtung (URL auf View, Setting durchreichen),
Django-eigenes Verhalten und Templates ohne Logik.

## Wie ein guter Test aussieht

- Er prüft Verhalten von außen: Request → Antwort, Zustand der Datenbank,
  versandte Mail (`mailoutbox`). Nicht, welche interne Funktion wie oft
  aufgerufen wurde.
- Mocks nur an Systemgrenzen: Mailversand, SMS, KI-Anbieter, Uhr. Alles
  darunter läuft echt, auch die Datenbank.
- Wird ein Test nach einem Refactoring ohne Verhaltensänderung rot, ist der
  Test schlecht, nicht das Refactoring.
- Name und Docstring sagen, welches Verhalten gilt, damit ein roter Test
  ohne Lesen des Codes verständlich ist.

Muster (erfundene Namen; der erste echte Test kommt mit #25):

    @pytest.mark.django_db
    def test_fremder_termin_ist_nicht_sichtbar(client):
        eigener = AppointmentFactory()
        fremder = AppointmentFactory()
        client.force_login(eigener.doctor.user)

        antwort = client.get(fremder.get_absolute_url())

        assert antwort.status_code == 404

404 statt 403, damit die Antwort nicht verrät, dass es den Termin gibt.

## Testdaten

- Nur erfundene Personen und Daten, auch keine anonymisierten echten: Das
  Repo ist öffentlich und Gesundheitsdaten fallen unter DSGVO Art. 9 (#3).
  Factories erzeugen Namen und Nummern, die erkennbar ausgedacht sind.

## Tempo

- Die Suite ohne E2E bleibt unter etwa einer Minute, damit sie vor jedem
  Commit läuft. Langsam wird sie durch echte Wartezeiten und unnötig viele
  Datensätze, nicht durch PostgreSQL.

## Abdeckung und Mutationstests

- `pytest` zeigt Branch-Coverage an (`pytest-cov`, Einstellung in
  `pyproject.toml`), erzwingt aber keine Quote: Eine Quote erzeugt
  Alibi-Tests, die Zeilen ausführen, ohne etwas zu prüfen. Die Anzeige dient
  dazu, ungetestete Zweige in Pflichtfällen zu finden.
- Ob Tests Fehler bemerken, zeigen Mutationstests (z. B. `mutmut`) über die
  kritischen Module (Berechtigung, Fristen, Zeit), einmalig oder bei
  Verdacht, nicht in jeder CI. Sie sind deshalb nicht in `requirements-dev.txt`.
- Die Coverage-Datei liegt unter `/tmp` im Container, weil der Code als
  Volume eingebunden ist und sie sonst im Repo landete.

## Vor dem Merge

- `/code-review` prüft ausdrücklich, ob jede neue Verzweigung und jede neue
  Berechtigungsprüfung einen Test hat, bei Berechtigungen mit verbotenem Fall.
