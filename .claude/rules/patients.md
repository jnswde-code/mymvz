---
paths:
  - "patients/**"
---
# Patientenstamm: Patient, Kennungen, Verlauf, Behandlungsteam, Sperrvermerk

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
- `CareTeamMember`: Psychologie und Suchttherapie sehen die Akte nur bei
  Patienten, in deren Team sie stehen (#38, Prüfung in `records/access.py`
  über `is_on_care_team`); Ernährung kommt dazu, sobald sie etwas liest
  (K4). `valid_on` ist die eine Definition von „gilt heute“ für Team und
  Freigaben; `valid_until` ist der erste Tag ohne Zugang, die Seite zeigt es
  als „ohne Zugang ab“. Mitgliedschaften und Freigaben beginnen am Tag des
  Eintragens, deshalb überlappt jede noch nicht beendete eine neue.
- `ConsentToShare` (#23 5.2, #38): der Patient öffnet Sucht oder
  Psychotherapie für eine benannte Person. `ConsentArea` wiederholt die
  Werte von `records.Sensitivity`, weil `patients` `records` nicht kennt.
  Beendet (mit wer und wann), nie gelöscht.
- Sperrvermerk (`is_restricted`, #39) liegt hier, nicht in `records`
  (#27, Frage 10): Er schließt auch die Stammdaten, und `records` kennt
  `patients`, nicht umgekehrt. Deshalb liegt auch `EmergencyAccess` hier,
  anders als im Schnitt in #27 vorgesehen. `restriction_open` und
  `can_see_patient` sind die eine Definition, wem ein gesperrter Patient
  offen ist; `records/access.py` benutzt sie.
- Die Freigabe für den Sperrvermerk ist `ConsentToShare` mit dem Bereich
  `restricted`. Sie öffnet den Patienten und die Einträge mit `restricted`,
  verlangt nur `view_patient`, nicht die Akte.
- `Patient.user`: Mitarbeitende als Patienten. Das Verknüpfen setzt den
  Sperrvermerk im selben Schritt (#23, Entscheidung 8); Entfernen der
  Verknüpfung lässt ihn stehen.
- `EmergencyAccess` gilt 60 Minuten je Patient und Ärztin/Arzt (#27,
  Frage 5), am Ende schon nicht mehr (`running_at`). Solange einer läuft,
  gibt es keinen zweiten; danach braucht es einen neuen Grund. Der Grund
  steht nur hier, nie im Protokoll. Nie geändert, nur mit dem Patienten
  gelöscht.
- `retain_until` ist Ende des Jahres des letzten Kontakts plus zehn Jahre
  (§ 630f BGB, #23 Abschnitt 3.3), gesetzt über `services.record_contact`.
  Ein Löschlauf fehlt bewusst; er kommt mit K8 und nur nach Freigabe durch
  einen Menschen.
- `Sex` folgt FHIR; „divers“ ist `other`.

## patients/services.py

- Außer `seed_demo` der einzige Ort, der `Patient`, `PatientIdentifier`,
  `CareTeamMember`, `ConsentToShare` und `EmergencyAccess` schreibt;
  Änderung, Verlauf und Protokolleintrag in einer Transaktion. Rollen prüfen
  die Ansichten, die Funktionen verlangen nur ein angemeldetes Konto, damit
  Backoffice (#8) und Sprachsteuerung (#16) sie ebenso nutzen. Ausnahme:
  `open_emergency_access` prüft das Recht selbst, weil ein Notfallzugriff
  ohne Ärztin/Arzt nie entstehen darf.
- Sperrvermerk setzen, aufheben und Konto verknüpfen schreiben je eine
  Zeile `PatientHistory` (`is_restricted`, `user`); so steht, wer ihn wann
  gesetzt oder aufgehoben hat.
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
  Zugang zur Akte (beim Sperrvermerk: zu den Stammdaten). Eine Freigabe
  beginnt am Tag des Eintragens.

## patients/views.py, patients/forms.py

- Erst Rolle prüfen, dann protokollieren: Öffnen ist `view` mit
  `patient_id`, Suchen `search`. Unbekannte Patienten geben 404.
- Wer jemanden behandelt und in welchem geschützten Bereich, ist selbst
  klinisch: Das Behandlungsteam und den Link zur Akte zeigt die
  Stammdatenseite nur Konten, die diese Akte sehen, Freigaben nur
  Ärztinnen/Ärzten. Team und Freigaben
  pflegen Ärztinnen/Ärzte (#38).
- Sperrvermerk (#39): Wer nicht freigegeben ist, bekommt auf jeder Seite
  des Patienten 403; die Stammdatenseite zeigt dann nur Name und
  Geburtsdatum (wie die Suche) mit Notfallzugriff, Freigabe und Aufheben
  für Ärztinnen/Ärzte. So kann eine nicht freigegebene Ärztin eine andere
  Person freigeben, aber nie sich selbst (vier Augen). Setzen, Aufheben
  und Verknüpfen verraten nichts und gehen deshalb auch am gesperrten
  Patienten. Die Suche findet gesperrte Patienten mit Markierung, ohne
  Nummern, damit niemand eine Dublette anlegt.
- Rechte (#27, Frage 6): Ärztinnen/Ärzte setzen, geben frei, heben auf und
  öffnen im Notfall; die Verwaltung setzt nur, verknüpft Konten und liest
  die Liste der Notfallzugriffe.
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
