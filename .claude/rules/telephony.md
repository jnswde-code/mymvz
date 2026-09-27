---
paths:
  - "telephony/**"
---
# Telefonassistent: Seite der Website

Konzept und Entscheidungen in #14 (Kommentar „Konzept Telefonassistent“,
Abschnitte 5 und 7), Schnitt P1 bis P5 dort. Der Sprachdienst selbst steht
in der Regeldatei `voice`.

## telephony/api.py, telephony/urls.py

- Der Agent hat keine Datenbank-Zugangsdaten und spricht nur mit dieser
  API (#14, Abschnitt 7). Sie liefert abschließend: Auskunft, online
  anfragbare Terminarten, Prüfung eines Wunschtags, Anlage einer Anfrage,
  Anlage einer Rückrufbitte, Ende eines Anrufs. **Kein Endpunkt liest
  vorhandene Anfragen, Termine, Rückrufbitten oder Patienten**, die
  Antwort auf eine neue Anfrage ist nur ihre Kennung: Was der Assistent
  nicht lesen kann, kann niemand aus ihm herausreden (#44).
- Schlüssel `VOICE_API_KEY` aus `.env` als `Authorization: Bearer`,
  Vergleich mit `hmac.compare_digest`. Ohne gesetzten Schlüssel ist die API
  aus (404), nicht offen; ohne oder mit falschem Schlüssel 403. Unter 32
  Zeichen startet Django nicht, weil Port 8000 in der Entwicklung offen
  ist. CSRF ist nur hier aus, weil kein Cookie authentisiert.
- Erreichbar nur im Docker-Netz: Der öffentliche Proxy (Caddy, #10) darf
  `/intern/` nicht weiterleiten. Django selbst kann das nicht prüfen, hinter
  dem Proxy kommen alle Anfragen aus dem Docker-Netz.
- Alle Regeln der Anfrage (Terminart online anfragbar, Wunschtage, E-Mail,
  keine Notiz am Telefon) prüft `appointments/services.py`, auch für das
  Telefon (#7). Diese Datei prüft nur Formate und lässt nur bekannte Felder
  zu; ein unbekanntes Feld wie `note` ist ein Fehler, nicht still verworfen.
  Was die Datenbank ablehnen würde (zu lange E-Mail, NUL im Text), fängt
  sie als 400 ab: Eine 500 hieße für den Agenten „nicht verfügbar“, und er
  könnte nicht nachfragen.
- Ein unpassender Wunschtag ist eine Antwort (`ok: false` mit dem Grund zum
  Vorlesen), kein Fehler; 400 nur bei kaputter Eingabe.
- Auskunft nur aus `OpeningHours` und `practice/info.py`, als fertige Sätze
  je Thema; was dort fehlt, weiß der Assistent nicht (#14, Entscheidung 3
  vom 27.09.).
- Rückrufbitte und Ende eines Anrufs sind die Endpunkte fünf und sechs
  (#45). Die Antwort auf eine Rückrufbitte ist nur ihre ID, damit der Agent
  sie im `CallRecord` nennen kann; lesen lässt sich damit nichts.

## telephony/models.py, telephony/services.py

- `CallbackRequest` hat Name, Rückrufnummer und eine Kategorie aus fester
  Liste, **kein Freitext** (#14, Entscheidung 8): Medikamente und Befunde
  sind Gesundheitsangaben, die der Assistent nicht aufnimmt. Die Kennung
  einer Anfrage nur bei „Absage/Verschiebung“ (Constraint); sie wird
  notiert, nicht nachgeschlagen, der Assistent erfährt also nie, ob es sie
  gibt, und führt nichts aus (#14, Entscheidung 6).
- Alle Änderungen nur über `telephony/services.py`; Schritte der Praxis
  nehmen das Konto und schreiben `log_access`. Wer abgehakt hat, steht nur
  im Zugriffsprotokoll, nicht im Datensatz.
- Fristen (#14 Abschnitt 6) in Kalendertagen Europe/Berlin (`days_later`):
  offen nach 14 Tagen `expired`, erledigt oder verfallen nach 7 weiteren
  Tagen gelöscht. Verfallene bleiben bis dahin in der Liste, mit Hinweis,
  und lassen sich noch abhaken. Die Abfrage holt Kandidaten mit einer
  Stunde Spielraum und prüft jeden mit `days_later` nach, sonst verschöbe
  die Zeitumstellung die Frist um eine Stunde.
- `CallRecord` hat **keine Spalte für Rufnummer oder Inhalt**, nur Beginn,
  Dauer, Betriebsart, Ergebnis und Verweise (`SET_NULL`). Die Betriebsart
  leitet der Server aus `OpeningHours` (Art „geöffnet“) zum Anrufbeginn ab:
  in einem Block Überlauf, sonst außerhalb der Öffnungszeiten. Der Agent
  meldet alle Ergebnisse des Anrufs, `final_outcome` wählt das stärkste;
  `emergency_hint` gewinnt immer, ohne Ergebnis heißt es `abandoned`.
- Nach 30 Tagen zählt `count_and_delete_call_records` jeden `CallRecord`
  in `reporting.CallStatistic` hoch und löscht ihn, beides in einer
  Transaktion je Datensatz: nie doppelt gezählt, nie verloren.
- Die Läufe (`notify_new_callbacks`, `expire_overdue_callbacks`,
  `delete_closed_callbacks`, `count_and_delete_call_records`) ruft der
  Worker aus `jobs` auf (#49); `telephony` kennt `jobs` nicht.

## telephony/mail.py

- Eine Mail an `PRACTICE_NOTIFICATION_EMAIL` je Durchgang für alle noch
  nicht gemeldeten Rückrufbitten, ohne Name, Nummer und Kategorie, nur der
  Link auf die Liste. Eigene Funktion statt Postausgang von `appointments`,
  der an Anfragen hängt; gemerkt wird `notified_at` erst nach dem Versand,
  eine gescheiterte Mail versucht der nächste Durchgang wieder.

## telephony/staff_views.py, telephony/templates/telephony/staff/

- Liste unter `/rueckrufe/`, älteste oben, getrennt von der API in eigener
  Datei wie bei `/anfragen/`. Rechte wie bei Anfragen: nur Ärztin/Arzt und
  MFA (`view_callbackrequest`, `change_callbackrequest`, Migration
  `accounts/0008`), alle anderen 403. Abhaken nur per POST; war jemand
  schneller, wird das eine Meldung, keine 500.
