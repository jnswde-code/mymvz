---
paths:
  - "records/**"
---
# Akte: Kontakte und Karteikarte in Fassungen

Konzept in #23 (Abschnitte 3, 5 und 6), Schnitt und Entscheidungen in #27,
umgesetzt als K2.1 (#37), K2.2 (#38, Behandlungsteam und Schutzstufen) und
K2.3 (#39, Sperrvermerk und Notfallzugriff).

## Zwei Regeln für alles in `records`

- **Keine auswertenden Funktionen.** Die Akte speichert, zeigt und ordnet;
  sie bewertet keine medizinischen Inhalte. Allergie gegen Medikation,
  Wechselwirkungen, Dosisrechner, Warnungen aus Werten, Recall aus Diagnosen
  oder ICD-Vorschläge machten sie zum Medizinprodukt (MDR Regel 11, #23
  Abschnitt 2). Kommt so etwas, dann als zugelassenes Fremdprodukt.
- **Nie am Fassungsmodell vorbei.** Geschrieben wird nur über
  `records/services.py`, gelesen nur über `records/access.py`. Das gilt auch
  für Suche, Export und die Sprachsteuerung (#16).

## records/models.py

- Jeder klinische Datensatz erbt von `VersionedRecord` (#23 3.1). Ändern
  heißt: neue Fassung, alte auf `superseded`. Andere Datensätze verweisen
  auf die `lineage_id`, nicht auf eine Fassung (`ChartEntry.encounter_lineage_id`),
  damit ein korrigierter Kontakt seine Einträge behält.
- Je Linie gibt es genau einen Kopf, die neueste Fassung, `active` oder
  `entered_in_error` (Teil-Unique-Index `…_one_head`). Das ist strenger als
  „höchstens eine aktive“ und schließt auch zwei Irrtums-Fassungen aus.
  `replaces` ist eins zu eins, also hat jede Fassung höchstens einen
  Nachfolger, auch in der Datenbank.
- `change_reason` ist ab Fassung 2 Pflicht, bei „Sonstiges“ mit Text
  (#27, Frage 4); Check-Constraints halten das auch in der Datenbank.
- `is_late_entry`: die erste Fassung der Linie wurde an einem späteren
  Kalendertag in Europe/Berlin gespeichert, als es klinisch war (#27,
  Frage 3). Eine Korrektur macht einen Eintrag nicht zum Nachtrag.
- `Encounter` ist selbst versioniert (#27, Frage 1). `patient`,
  `sensitivity`, `source`, `appointment` und `encounter_lineage_id` bleiben
  über alle Fassungen gleich; ein falscher Patient ist ein Irrtum, keine
  Korrektur.
- `ChartEntryType`: Kürzel aus Migration `0003`, vorläufig bis #19. Werden
  abgeschaltet (`is_active`), nicht gelöscht; Einträge verweisen mit
  `PROTECT`.
- `save()` auf eine bestehende Fassung, `delete()`, `QuerySet.update` und
  `QuerySet.delete` werfen `ImmutableRecordError`. `_supersede()` ist der
  einzige Weg für den Statuswechsel und nur für `services`.

## records/migrations/0002_immutability_triggers.py

- Ein Trigger je Tabelle verweigert jedes `DELETE` und jedes `UPDATE` außer
  `active → superseded` bei sonst gleicher Zeile (Vergleich als `jsonb`, so
  sind Spalten aus K3 bis K5 automatisch geschützt). Neue versionierte
  Tabellen bekommen denselben Trigger in ihrer Migration.
- Ausnahme: Spalten, die als Trigger-Argument genannt sind, dürfen auf
  `NULL` gehen und sonst nichts. Das braucht `SET NULL` von
  `Encounter.appointment`, wenn ein Termin gelöscht wird.
- `active → entered_in_error` erlaubt der Trigger bewusst nicht, anders als
  in #37 skizziert: `mark_entered_in_error` legt eine letzte Fassung mit
  Status `entered_in_error` und Grund an. So stehen wer, wann und warum wie
  bei jeder Änderung in einer Fassung, und rohes SQL kann nichts ohne Grund
  als Irrtum markieren.
- Der Weg für den Aufbewahrungslauf (Sitzungsvariable, #23 3.3) kommt erst
  mit K8 (#27, Frage 8). `TRUNCATE` sperrt der Trigger nicht; die Test-DB
  leert Tabellen damit.

## records/services.py

- Jede Änderung: Kopf mit `select_for_update` sperren, prüfen, dass er die
  Fassung ist, die der Nutzer gesehen hat (`based_on_version`), alten Kopf
  ersetzen, Nachfolger speichern, protokollieren. Zwei gleichzeitige
  Korrekturen ergeben so einen Nachfolger und eine Fehlermeldung.
- Anders als `patients.services` prüfen die Funktionen die Rechte selbst
  (über `access`, auf dem gesperrten Kopf), damit kein Aufrufer an ihnen
  vorbei schreibt.
- Ein Kontakt lässt sich erst als Irrtum markieren, wenn keine aktiven
  Einträge mehr an ihm hängen. `create_entry` sperrt den Kontakt ebenfalls,
  damit dazwischen kein Eintrag hineinrutscht.
- Neue Kontakte rufen `patients.services.record_contact` (Aufbewahrung);
  eine Korrektur auf ein späteres Datum schiebt die Frist, eine frühere
  verkürzt sie nie.
- `create_entry` nimmt nur Schutzstufen, die der Autor schreiben darf
  (`access.writable_sensitivities`); ohne Angabe die erste davon, so
  schreibt Psychologie `psychotherapy` und Suchttherapie `addiction` (#38).
  Die Schutzstufe bleibt über alle Fassungen gleich. `restricted` schreiben
  nur Ärztinnen/Ärzte (`write_restricted`, #39).

## records/access.py

- Die eine Prüfung. `can_view` ist `visible_to` auf eine Zeile, beide können
  nicht auseinanderlaufen. Was hier nicht geregelt ist, bleibt zu.
- Zwei Schichten (#23 5.1, 5.2, #38): welche Patienten, dann welche
  Schutzstufen. Ärztinnen/Ärzte und MFA sehen alle Patienten
  (`view_all_patients`), Psychologie und Suchttherapie nur im
  Behandlungsteam, Ernährung und Verwaltung keine Akte. `addiction` sehen
  Ärztinnen/Ärzte und Suchttherapie; MFA nur als Platzhalter bis K4 (#27,
  Frage 7). `psychotherapy` sieht nur die behandelnde Person, der Autor der
  ersten Fassung der Linie, solange er `write_psychotherapy` hat; auch
  Ärztinnen/Ärzte nicht, sonst wäre die Trennung nach § 203 StGB leer.
- Eine Freigabe (`patients.ConsentToShare`) öffnet einen Bereich eines
  Patienten für eine benannte Person, zusätzlich zu Akte und Team, nie
  statt ihnen.
- Sperrvermerk (#39): Ein Patient mit `is_restricted` ist vor allen anderen
  Prüfungen zu, außer für Personen, denen `patients.models.restriction_open`
  ihn öffnet (Freigabe `restricted` oder eigener laufender Notfallzugriff).
  Einträge mit `restricted` sehen dieselben Personen und ihr Autor. Der
  Notfallzugriff öffnet nie Psychotherapie, sonst wäre die Trennung nach
  § 203 StGB über ihn umgehbar.
- Team und Freigabe gelten an einem Tag in Europe/Berlin
  (`patients.models.valid_on`); `valid_until` ist der erste Tag ohne
  Zugang. Wer heute ausgetragen wird, sieht ab sofort nichts mehr.
- Welche Stufen jemand schreibt, sind eigene Rechte (`write_<stufe>`), weil
  Lesen und Schreiben auseinanderfallen: Psychologie liest `normal`,
  schreibt aber nur `psychotherapy`. Korrigieren und als Irrtum markieren
  dürfen Autor und Ärztinnen/Ärzte (#27, Frage 2), jeweils nur, was sie
  sehen und dessen Stufe sie schreiben; fremde Psychotherapie-Notizen nur
  der Autor, denn eine Freigabe öffnet nur zum Lesen. Kontakte sind der Rahmen für alle
  Stufen und haben selbst immer `normal`.
- Platzhalter (`hidden_entries`): aktive Einträge, die der Nutzer nicht
  lesen darf, nur als Zahl je Kontakt („n Einträge mit
  Zugriffsbeschränkung“, #23 Entscheidung 7), ohne Stufe, Autor oder Kürzel.
- Eine Linie mit Irrtums-Kopf ist mit allen Fassungen ausgeblendet. Nur
  Ärztinnen/Ärzte sehen sie auf Wunsch (`include_errors`); jede gezeigte
  Irrtums-Fassung ist ein eigener Protokolleintrag.

## records/views.py

- Reihenfolge: Recht auf die Akte (403), Patient (404), Sperrvermerk (die
  Akte leitet auf die Sperrseite in `patients`, alle anderen Seiten 403),
  Behandlungsteam (403), dann Datensatz nur aus `visible_to` (404, damit
  Verborgenes nicht auffällt), dann protokollieren.
  Akte öffnen ist `list` auf `records.chartentry` mit `patient_id`.
- Der Verlauf zeigt Wortunterschiede (`records/diff.py`, `difflib`) und
  geänderte Felder je Fassung.
