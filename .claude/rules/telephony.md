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
  anfragbare Terminarten, Prüfung eines Wunschtags, Anlage einer Anfrage.
  **Kein Endpunkt liest vorhandene Anfragen, Termine oder Patienten**, die
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
