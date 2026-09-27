---
paths:
  - "appointments/**"
  - "tests/test_appointments_*.py"
  - "tests/factories.py"
  - "tests/conftest.py"
---
# Terminanfrage: Anfrage, Termin, Links, Mails

Datenmodell und Zustände nach dem Konzept in #5 (Abschnitte 2, 3 und 6), mit
den Ergänzungen aus #14 (Telefonassistent). Hier nur, was man beim Ändern
wissen muss.

## appointments/models.py

- Name, Geburtsdatum und Kontakt stehen als Momentaufnahme in der Anfrage
  und werden mit ihr gelöscht (#5, Entscheidung 1). Die Spalte `patient` an
  Anfrage und Termin ist optional und wird nur von Mitarbeitenden gesetzt
  (`services.assign_patient`, #26); neue Termine übernehmen sie von der
  Anfrage. `PROTECT`, damit das Löschen eines Patienten (K8) seine Termine
  bedenken muss.
- Die ganze Anfrage gilt als Art.-9-Datensatz, nicht nur Terminart und
  Notiz: Schon „Patient dieses MVZ“ kann bei Suchtmedizin eine
  Gesundheitsangabe sein (#5 Abschnitt 6).
- `email` ist nur für `channel = web` Pflicht (Constraint), der
  Telefonassistent darf ohne anlegen (#14). Ohne Adresse beginnt die Anfrage
  bei `open`.
- `AppointmentEvent` hat kein Freitextfeld und keine Namen; ein Test hält die
  Feldliste fest. `actor` steht genau dann, wenn `actor_kind = staff`.
- Termine hängen mit `SET_NULL` an der Anfrage, weil es ab Stufe 2 Termine
  ohne Anfrage gibt. Der Löschlauf (#9) löscht Termine deshalb über ihr
  eigenes `delete_after`, nicht über die Anfrage.
- Primärschlüssel UUID für alles mit Personenbezug (#5, Entscheidung 10).
- `medical_office_entered_at` und `medical_office_removed_at` am Termin:
  Medical Office bleibt in Stufe 1 der Kalender, angenommene Vorschläge und
  Absagen per Link geschehen ohne das Team (#8, Entscheidung 2). Kein Zustand
  und kein Verlaufseintrag, wer abgehakt hat, steht im Zugriffsprotokoll.

## appointments/services.py

- Der einzige Ort, an dem sich `status` ändert (#5 Abschnitt 3). Jeder
  Übergang sperrt die Zeile, prüft den Ausgangszustand, schreibt einen
  Verlaufseintrag, setzt `delete_after` und stellt seine Mails ein. Formular,
  Backoffice (#8), Telefonassistent (#14) und Sprachsteuerung (#16) rufen
  dieselben Funktionen auf.
- Prüfung der Wunschzeiträume und Anlage der Anfrage stehen hier, nicht im
  Formular, damit der Telefonassistent sie über die interne API nutzt (#14).
  Das Formular prüft nur Formate.
- Schritte der Praxis nehmen das handelnde Konto und schreiben
  `log_access(..., "update")`; ohne angemeldetes Konto brechen sie ab.
- `compute_delete_after` ist die eine Stelle für Löschfristen: unbestätigt
  24 Stunden nach Anlage, abgelehnt/zurückgezogen/verfallen 30 Tage nach
  Abschluss, gebucht 30 Tage nach Terminende, abgesagt 30 Tage nach der
  Absage, offen und mit laufendem Vorschlag keine. Termine bekommen in
  Stufe 1 dasselbe Datum wie ihre Anfrage.
- Lesen fürs Team (`list_requests`, `get_request`) steht ebenfalls hier und
  protokolliert selbst (`list` einmal je Liste, `view` je Anfrage), damit die
  Sprachsteuerung (#16) dieselben Einträge erzeugt. Unbestätigte Anfragen
  sieht das Team nie (`staff_visible`).
- Ein Vorschlag an eine Anfrage ohne E-Mail wird abgewiesen: Niemand könnte
  ihn annehmen, er verfiele still, und die Anfrage spränge zurück (#8,
  Entscheidung 4). Das Team ruft an und bestätigt.
- „für ein Kind“ heißt unter 18 am Tag der Anzeige in Europe/Berlin, nur ein
  Hinweis für die Triage; „offen seit“ zählt Werktage ab der Bestätigung der
  E-Mail bzw. der Anlage (#8, Entscheidungen 5 und 8); die offene Liste ist
  danach sortiert.
- `expire_overdue_requests` und `expire_overdue_proposals` sind die Läufe des
  Systems; der Worker ruft sie auf (#49). Jeder Datensatz in eigener
  Transaktion (`config.batch.each`), einer, der wirft, hält die anderen
  nicht auf.
- Ein abgelehnter, verfallener oder zurückgezogener Vorschlag setzt die
  Anfrage immer auf `open`, eine Absage eines gebuchten Termins nur mit
  `reopen`.
- `cancel_appointment` nimmt `expected_status`, den Zustand, den das Team
  gesehen hat: Hat der Patient den Vorschlag inzwischen angenommen, darf
  „zurückziehen“ nicht zur Absage eines gebuchten Termins mit Mail werden.
- Arbeitslisten für Medical Office (`list_appointments`): „einzutragen“ sind
  gebuchte, noch nicht eingetragene, „auszutragen“ abgesagte, die eingetragen
  waren. Beide nur, solange der Termin nicht vorbei ist; ein vergangener
  Termin blockiert nichts mehr (#8).
- `suggest_patients` zeigt Patienten aus dem Stamm und protokolliert das
  deshalb als `search` mit Trefferzahl. Zuordnen entscheidet immer ein Mensch
  (#5 Abschnitt 4).

## appointments/deadlines.py

- Fristen in Tagen sind Kalendertage in Europe/Berlin (`days_later`),
  Fristen in Stunden echte Stunden (`hours_before` rechnet in UTC). Python
  rechnet innerhalb einer Zeitzone mit der Wanduhr, aus der Datenbank kommt
  UTC; ohne diese Trennung verschiebt die Zeitumstellung Fristen um eine
  Stunde, je nachdem, woher der Wert kommt.
- Werktage für Gegenvorschläge sind Mo–Fr; Feiertage kennt das System noch
  nicht.

## appointments/tokens.py

- Gespeichert wird nur der SHA-256 des Tokens. Jede Mail bekommt ihren
  eigenen Token, jeder gilt einmal und nur, solange sein Zweck zum Zustand
  passt (sonst „outdated“): Hat die Praxis abgesagt, ist der Absagelink tot.

## appointments/views.py

- GET auf einen Link zeigt nur an, erst der Knopf (POST) handelt:
  Mailfilter öffnen Links zum Prüfen und dürfen dabei nichts absagen.
- Unbekannter Link 404, bekannter, aber verbrauchter oder abgelaufener 410.
- Die Seiten haben ein eigenes schlichtes Layout mit Notfallhinweis und
  Links auf das Impressum der bestehenden Homepage und den eigenen
  Datenschutzhinweis; die Homepage wird vorerst nicht neu gebaut (#3).
  Referrer nur `same-origin`, weil die URL den Token enthält;
  `no-referrer` ließe Browser bei Formularen `Origin: null` senden, und die
  CSRF-Prüfung schlüge fehl.
- Der Datenschutzhinweis (`/termin/datenschutz/`, #11) beschreibt nur, was
  der Code tut, und zieht Fristen aus den Einstellungen. Ändert sich, was
  erhoben, gespeichert oder weitergegeben wird, oder eine Frist, den Text
  anpassen und `APPOINTMENTS_PRIVACY_NOTICE_VERSION` auf das neue Datum
  setzen (ISO, die Seite zeigt es als Stand); die Version steht in jeder
  Anfrage. Gelb markierte Platzhalter hängen an Hosting und Mailanbieter (#10).

## appointments/staff_views.py, staff_forms.py, staff_urls.py

- Die Seiten fürs Team unter `/anfragen/` liegen getrennt von denen für
  Patienten: Dort braucht keine Ansicht eine Anmeldung, hier jede eine
  Rolle. In einer gemeinsamen Datei reichte ein vergessener Decorator, und
  eine Anfrage läge offen (#8).
- Anfragen sehen und bearbeiten nur Ärztin/Arzt und MFA (#8,
  Entscheidung 1): `view_appointmentrequest` für Liste und Ansicht,
  `change_appointmentrequest` für jeden Schritt und die Notiz. Erst die
  Rolle, dann liest und protokolliert der Service. Jeder Schritt ist POST;
  `TransitionNotAllowed` (jemand anderes war schneller) wird zur Meldung.
- Meldungen liegen im Cookie (Standard von Django) und tragen deshalb nie
  Namen oder Telefonnummern; die stehen auf der Seite.
- Den Block „Für Medical Office“ ordnet #19 nach der Eingabemaske; bis dahin
  gilt die Reihenfolge der Anfrage.
- Schritte an einem Termin tragen Anfrage und Termin in der URL; ein Termin
  einer anderen Anfrage gibt 404.
- Zuordnung zum Patienten und Patientensuche auf der Anfrage brauchen
  zusätzlich `patients.view_patient`, weil sie den Patientenstamm zeigen.
  Von der Patientenseite führt noch kein Link zu den Anfragen; der kommt nach
  #39, das dieselbe Vorlage ändert (#8, Entscheidung 7).

## appointments/mail.py

- In Mails nur Datum, Uhrzeit, Adresse, Kennung und Links. Nie Terminart,
  Notiz, Ärztin/Arzt oder Namen (#3 Abschnitt 2); ein Test schickt jede Mail
  und sucht danach. Mails an die Praxis sagen nur, dass etwas geschehen ist,
  und verlinken die Liste, nie eine einzelne Anfrage.
- Den Text der Ablehnung wählt nur der feste Grund aus dem Verlauf
  (`DECLINE_REASONS`), nie ein Freitext des Teams (#3 Abschnitt 2).
- `queue` schreibt nur Art und IDs in den Postausgang `OutgoingMail`, in
  der Transaktion des Übergangs; der Worker sendet (`process_outbox`, #49).
  Kein Empfänger und kein Text in der Tabelle, Text und Tokens entstehen
  erst in `send` (#5 Abschnitt 6). Nach einem Rollback gibt es keine Mail,
  nach einem Absturz geht keine verloren. In Tests `with commit():`
  (`tests/conftest.py`), das den Worker einmal spielt.
- Fehlgeschlagene Mails wiederholt der Worker nach 1, 5, 15, 60 Minuten,
  dann stündlich, und gibt sie nach 24 Stunden auf; das meldet der Lauf.
  `last_error` hält nur die Klasse der Ausnahme, SMTP-Fehler nennen die
  Adresse. Stirbt der Worker zwischen Versand und Commit, geht die Mail
  doppelt raus; eine verlorene Bestätigung wöge schwerer (#9 Abschnitt 3).

## appointments/captcha.py, appointments/spam.py

- Captcha selbst gehostet im Format von ALTCHA (Proof of Work, kein Dritter
  sieht die Besucher). Eine Lösung gilt einmal (Cache) und eine Stunde.
  Ohne JavaScript geht das Formular nicht; die Seite nennt dann das Telefon.
- Höchstens 10 Formular-Absendungen je Adresse und Stunde, gezählt im Cache
  über ein HMAC der Adresse; in der Datenbank steht keine IP (#5).
- Cache ist der Prozessspeicher, weil gunicorn mit einem Prozess läuft. Mit
  mehreren Prozessen braucht es einen gemeinsamen Cache (#10), sonst zählt
  jeder für sich.
- Honeypot: ausgefüllt sieht es aus wie Erfolg und speichert nichts.

## appointments/migrations/0002_appointment_types.py

- Die feste Liste aus #3, Entscheidung 2. Dauern sind Platzhalter, bis die
  Praxis eigene nennt. Terminarten werden deaktiviert, nie gelöscht.

## tests/conftest.py, tests/factories.py

- `berlin(...)` für lokale Zeitpunkte, `commit` für Mails, `token_from` holt
  den Token aus einer Mail. Factories erzeugen nur erfundene Personen.
