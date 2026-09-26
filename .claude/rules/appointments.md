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

- Stufe 1 hat keine Patiententabelle: Name, Geburtsdatum und Kontakt stehen
  als Momentaufnahme in der Anfrage und werden mit ihr gelöscht (#5,
  Entscheidung 1). Die Zuordnung zu `patients.Patient` macht später immer ein
  Mensch.
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
- `expire_overdue_requests` und `expire_overdue_proposals` sind die Läufe des
  Systems; aufrufen soll sie der Worker aus #9.
- Ein abgelehnter, verfallener oder zurückgezogener Vorschlag setzt die
  Anfrage immer auf `open`, eine Absage eines gebuchten Termins nur mit
  `reopen`.

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
  Links auf Impressum und Datenschutz der bestehenden Homepage; die
  Homepage wird vorerst nicht neu gebaut (#3). Referrer nur `same-origin`,
  weil die URL den Token enthält; `no-referrer` ließe Browser bei Formularen
  `Origin: null` senden, und die CSRF-Prüfung schlüge fehl.

## appointments/mail.py

- In Mails nur Datum, Uhrzeit, Adresse, Kennung und Links. Nie Terminart,
  Notiz, Ärztin/Arzt oder Namen (#3 Abschnitt 2); ein Test schickt jede Mail
  und sucht danach. Mails an die Praxis sagen nur, dass etwas geschehen ist.
- `queue` merkt sich nur Art und IDs und sendet nach dem Commit; Text und
  Tokens entstehen erst in `send`. So kann #9 `send` in den Worker verlegen,
  ohne die Aufrufer zu ändern. In Tests deshalb `with commit():`
  (`tests/conftest.py`).

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
