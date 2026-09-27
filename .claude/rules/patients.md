---
paths:
  - "patients/**"
---
# Patientenstamm: Patient, Kennungen, Verlauf, Behandlungsteam

Modelle nach #23 Abschnitt 4 und 6, Schnitt K1 (#26). Hier nur, was man
beim Ändern wissen muss.

## patients/models.py

- Patienten legen nur Mitarbeitende an, nie eine Anfrage (#5,
  Entscheidung 1). Die Zuordnung einer Anfrage zu einem Patienten ist immer
  eine Entscheidung eines Menschen (`appointments.services.assign_patient`).
- Stammdaten werden an Ort und Stelle geändert, aber jede Änderung schreibt
  je Feld eine Zeile `PatientHistory` (alt, neu, wer, wann). So bleibt klar,
  unter welchem Namen jemand wann geführt wurde (#23 Abschnitt 3.1).
  Verlaufszeilen werden nie geändert und nur mit dem Patienten gelöscht.
- `PatientIdentifier` ist je `system` eindeutig, auch nach dem Beenden, damit
  eine alte Nummer nie auf eine zweite Person zeigt. Je Patient und System
  gilt höchstens eine Nummer. Kennungen und Mitglieder des Behandlungsteams
  werden beendet (`valid_until`), nie gelöscht.
- `CareTeamMember`: Psychologie, Suchttherapie und Ernährung sehen
  klinische Inhalte nur bei Patienten, in deren Team sie stehen (#38,
  Prüfung in `records/access.py`). `valid_on` ist die eine Definition von
  „gilt heute“ für Team und Freigaben; `valid_until` ist der erste Tag ohne
  Zugang.
- `ConsentToShare` (#23 5.2, #38): der Patient öffnet Sucht oder
  Psychotherapie für eine benannte Person. `ConsentArea` wiederholt die
  Werte von `records.Sensitivity`, weil `patients` `records` nicht kennt.
  Beendet (mit wer und wann), nie gelöscht.
- `retain_until` ist Ende des Jahres des letzten Kontakts plus zehn Jahre
  (§ 630f BGB, #23 Abschnitt 3.3), gesetzt über `services.record_contact`.
  Ein Löschlauf fehlt bewusst; er kommt mit K8 und nur nach Freigabe durch
  einen Menschen.
- `Sex` folgt FHIR; „divers“ ist `other`.

## patients/services.py

- Außer `seed_demo` der einzige Ort, der `Patient`, `PatientIdentifier`,
  `CareTeamMember` und `ConsentToShare` schreibt; Änderung, Verlauf und
  Protokolleintrag in einer Transaktion. Rollen prüfen die Ansichten, die
  Funktionen verlangen nur ein angemeldetes Konto, damit Backoffice (#8) und
  Sprachsteuerung (#16) sie ebenso nutzen.
- Dublettenhinweis: gleiches Geburtsdatum und ähnlicher Name. Nachname und
  Geburtsname werden über Kreuz verglichen (Name nach Heirat), Vornamen für
  sich. Ähnlich heißt gleich nach Normalisierung (Umlaute ausgeschrieben,
  Akzente, Bindestriche und Leerzeichen weg), enthalten ab vier Buchstaben
  oder `SequenceMatcher` ab 0,8 („Meier“/„Meyer“). Es ist nur ein Hinweis;
  ein Mensch entscheidet.
- Die Suche verknüpft alle Angaben mit „und“, findet auch beendete Nummern
  (ein Brief kann eine alte tragen) und liefert höchstens 50 Treffer. Sie
  schreibt einen Protokolleintrag mit der Trefferzahl, nie den Suchbegriff.
- Die KVNR wird nur auf Form geprüft (Buchstabe, neun Ziffern), noch nicht
  auf die Prüfziffer.
- Freigaben: niemand trägt eine für sich selbst ein, sonst öffnete ein
  einzelnes Konto sich selbst einen geschützten Bereich. Die Person braucht
  Zugang zur Akte. Eine Freigabe beginnt am Tag des Eintragens.

## patients/views.py, patients/forms.py

- Erst Rolle prüfen, dann protokollieren: Öffnen ist `view` mit
  `patient_id`, Suchen `search`. Unbekannte Patienten geben 404.
- Wer jemanden behandelt und in welchem geschützten Bereich, ist selbst
  klinisch: Das Behandlungsteam zeigt die Stammdatenseite nur Konten mit
  Zugang zur Akte, Freigaben nur Ärztinnen/Ärzten. Team und Freigaben
  pflegen Ärztinnen/Ärzte (#38).
- Beim Anlegen läuft die Dublettenprüfung vor dem Speichern. Die Bestätigung
  „andere Person“ gilt nur für die angezeigten Treffer (`duplicates_seen`);
  kommt nach einer Änderung der Eingabe ein neuer Treffer dazu, fragt die
  Seite noch einmal.

## patients/management/commands/seed_demo.py

- Läuft nur mit `DATA_MODE=synthetic`. Nachnamen sind erkennbar keine echten
  („Beispiel“, „Muster“ …), PLZ `00000`, Mail unter `example.org`,
  Telefon aus dem Bereich `030 23125…`, den die Bundesnetzagentur für
  Filme und Fiktion freihält,
  Medical-Office-Nummern ab 900000. So entsteht keine realistische
  Kombination aus Name, Geburtsdatum und Anschrift (DSGVO Art. 9, #3).
- Mit `--author` schreibt es auch Kontakte und Einträge, über
  `records.services` wie ein Mensch, damit nichts am Fassungsmodell vorbei
  entsteht. Die Texte sind kurz und erfunden; alle Einträge sind Nachträge,
  weil sie in der Vergangenheit liegen (#37).
