---
paths:
  - "jobs/**"
  - "config/batch.py"
---
# Worker: Läufe des Systems

Konzept und Entscheidungen in #9 (Kommentar „Konzept und Schnitt #9 in
Sub-Issues“, Abschnitte 2 bis 4 und 8), umgesetzt in Teilen: #49 Worker und
Postausgang, #50 Löschlauf, #51 Erinnerung.

## jobs/management/commands/run_worker.py

- Ein eigener Dauerprozess im Compose-Dienst `worker`, kein Cron auf dem
  Host und keine Warteschlange (#9, Entscheidung 1): Ein Cron außerhalb von
  Compose fiele beim Ausfall niemandem auf, Celery oder Redis wären ein
  Dienst mehr für eine Handvoll fester Aufgaben.
- Nur ein Worker zugleich über `pg_try_advisory_lock`; ein zweiter (etwa
  beim Deploy, #10) wartet, statt Mails doppelt zu senden. Die Sperre hängt
  an der Datenbankverbindung und wird deshalb in jedem Durchgang geprüft.
- `SIGTERM` lässt den laufenden Durchgang zu Ende laufen.

## jobs/runner.py

- Fällig ist eine Aufgabe, wenn ihr letzter `JobRun` mindestens einen Takt
  alt ist. So startet ein Neustart keinen Tageslauf doppelt, und ein
  verpasster Lauf holt sich beim nächsten Durchgang nach.
- Die Apps liefern nur Funktionen, `jobs` kennt sie, nicht umgekehrt. Neue
  Aufgaben kommen in `JOBS`.
- Log und `JobRun` enthalten Aufgabe, Zahlen und die Klasse der Ausnahme,
  nie deren Text oder einen Traceback: Darin stünden Adressen und Werte aus
  Datensätzen.
- `worker_health` (Healthcheck in Compose) schlägt fehl, wenn seit 5 Minuten
  kein Lauf endete; der Postausgang läuft in jedem Durchgang und hält das
  frisch. Die Überwachung von außen gehört zu #10.
- `clean_up` löscht Läufe und gesendete Mails nach 30 Tagen; sie enthalten
  nur Arten und IDs.
- Für den Telefonassistenten (#45) laufen aus `telephony.services`: Hinweis
  auf neue Rückrufbitten jede Minute, Verfall und Löschen der Rückrufbitten
  und Zählen der Anrufe stündlich (Regeldatei `telephony`).

## jobs/alerts.py

- Scheitert ein Lauf, geht eine Mail ohne Inhalt an
  `OPERATIONS_ALERT_EMAIL` (#9, Entscheidung 3), höchstens einmal je Aufgabe
  und Tag in Europe/Berlin. Eine Adresse statt aller Konten der Verwaltung,
  weil sich die still mit Personalwechseln ändern.

## config/batch.py

- `each` behandelt jeden Datensatz in eigener Transaktion; einer, der
  wirft, hält die anderen nicht auf. Am Ende meldet `PartialFailure` die
  Zahlen, der Lauf gilt als fehlgeschlagen. Liegt in `config`, weil die Apps
  es brauchen und nicht von `jobs` abhängen sollen.
