---
paths:
  - "voice/**"
---
# Voice: Sprachdienst mit LiveKit Agents

Prototyp der Sprachplattform (#13), Grundlage für Telefonassistent (#14),
Gesprächsdokumentation (#15), Sprachsteuerung (#16) und Auswertungen (#17).
Anforderungen aus dem Konzept in #14, Abschnitte 3, 6 und 7.

## Aufbau

- Eigenes Verzeichnis mit eigenem Image und eigenen Abhängigkeiten, getrennt
  von der Web-App: LiveKit und die Anbieter-SDKs kommen nie ins Django-Image.
  Im Compose unter dem Profil `voice` (Dienste `livekit` und `voice`), damit
  `docker compose up` weiter nur die Website startet (#13).
- Der Agent hat keine Datenbank-Zugangsdaten. Anfragen anlegen wird er über
  eine interne API der Web-App (#14, Abschnitt 7), die kommt mit T0 in #14.
- ruff läuft von der Wurzel aus über `voice/` mit (`src` in der
  `pyproject.toml` der Wurzel). `voice/pyproject.toml` enthält nur pytest;
  das `pytest` der Wurzel sammelt `voice/tests/` nicht ein.

## Anbieter

- Der Agent kennt nur LiveKits Basisklassen (`stt.STT`, `llm.LLM`,
  `tts.TTS`). Welche Klasse dahinter steckt, entscheidet allein
  `providers/__init__.py` nach `VOICE_*_PROVIDER` aus `.env`. Ein neuer
  Anbieter ist eine Fabrikfunktion, sein Paket in `voice/requirements.txt`
  und ein Eintrag in der Tabelle; der Agent ändert sich nicht (#13).
- Bis zur Anbieterwahl in #18 gibt es nur `fake`, und `fake` ist die
  Voreinstellung: Eine fehlende Variable darf nie Audio an einen echten
  Anbieter schicken. Echte Aufrufe nur mit Testdaten und Zugangsdaten in
  `.env`; Region EU und kein Training einstellen, wo der Anbieter es kann.
- Die Attrappen in `providers/fake.py` reichen für den ganzen Weg im
  Browser: Die STT „hört“ nach jeder Sprechpause denselben Satz, die TTS
  piept so lange, wie der Text dauern würde.

## LiveKit-Voreinstellungen, die Audio in die Cloud schicken

- LiveKit Agents wählt im Dev-Modus für Turn-Erkennung und
  Unterbrechungserkennung Modelle auf LiveKit Cloud
  (`agent-gateway.livekit.cloud`). Das hieße Anruferaudio an einen Dienst
  ohne Auftragsverarbeitung. `LOCAL_TURN_HANDLING` in `agent.py` legt beides
  lokal fest (Satzende von der STT, Unterbrechung per VAD), ein Test hält es
  fest (#13).
- `session.start(record=False)`: keine Aufnahme und kein Sitzungsbericht,
  egal was ein LiveKit-Cloud-Projekt voreinstellt.
- Bei jedem Update von `livekit-agents` im Paket nach `agent-gateway`,
  `is_hosted` und `is_dev_mode` suchen, ob neue Cloud-Voreinstellungen
  dazugekommen sind.

## Sicherheitsweiche (`safety.py`, `handoff.py`)

- Der Wortfilter sitzt in `ReceptionAgent.llm_node`, nicht in
  `on_user_turn_completed`: Jeder Weg zum LLM läuft durch `llm_node`, auch
  Texteingaben; der Turn-Hook läuft nur bei gesprochenen Turns. Ein Treffer
  ersetzt die LLM-Antwort durch feste Sätze, das LLM wird nicht gefragt.
- Reihenfolge der Treffer: Suizidgedanken, Notfall, Wunsch nach einem
  Menschen, Gesundheitsthema. Der Filter stuft nie Dringlichkeit ab, jeder
  Treffer führt nur zu mehr menschlicher Aufmerksamkeit. Das hält den
  Assistenten unter Anhang III Nr. 5 lit. d KI-VO und außerhalb von
  MDR-Regel 11 (#14, Abschnitt 4). Keine Stufen, Punktwerte oder „kann
  warten“ einbauen.
- Fehlalarme sind erlaubt, übersehene Notfälle nicht. Neue Muster kommen
  mit erfundenen Sätzen in `tests/test_safety.py`, auch mit Sätzen, die
  nicht auslösen dürfen (Blutabnahme, Rezept, Krankschreibung sind
  Anliegen, keine Beschwerden).
- Nach einem Notfallhinweis gibt es im Anruf keinen Weg zurück
  (`SafetyGate`): Jeder weitere Turn bekommt wieder die Notrufnummern.
- Das LLM kann die Weiche über das Werkzeug `hand_off` auslösen, aber nie
  aufheben.
- Die Sperre greift auch, wenn im Kontext kein Text der Anrufenden steht
  (Antwort nach dem Werkzeug `hand_off`).
- Der Filter prüft den fertigen Turn, nicht Zwischenergebnisse der STT.
  Ob das für das Kriterium „Weiche innerhalb von 10 Sekunden“ reicht,
  zeigt die Testsammlung in T0 (#14, 3.4).
- Bis SIP angebunden ist, gibt es niemanden zum Weiterleiten (`NoTransfer`);
  jede Weiche endet mit 112 und 116 117 bzw. der Bitte, später anzurufen.
- Taste 0 und 9 unterbrechen mit `force=True`, auch die Begrüßung, die
  sich durch Sprechen nicht unterbrechen lässt (Hinweis auf KI, Art. 50
  KI-VO). Nach einem Notfall tut 9 nichts.
- Die Ansagen in `texts.py` sind Entwürfe; die bzw. der
  Datenschutzbeauftragte stimmt sie noch ab. Zahlen stehen zusätzlich
  ausgeschrieben, damit keine TTS „hundertzwölf“ sagt.

## Protokolle (`log_privacy.py`)

- LiveKit schreibt auf Debug-Ebene jeden Gesprächsbeitrag mit Text und die
  Teilnehmerkennung ins Log (Felder `lk.pii.*`), bei SIP mit Rufnummer. Der
  Filter ersetzt `lk.pii.*` ganz und jede Ziffernfolge ab sechs Stellen,
  auch in Tracebacks und strukturierten Feldern (#14, Abschnitt 6).
- Er hängt an den Handlern der Wurzel im Worker-Prozess, gesetzt beim
  Ereignis `worker_started`, nachdem `cli.run_app` die Handler eingerichtet
  hat. Job-Prozesse leiten ihre Einträge dorthin, und erst dort hängt
  LiveKit Raumnamen an (bei SIP mit Rufnummer); ein Logger-Filter sähe sie
  nicht. Ein fehlerhafter Log-Aufruf darf im Filter keine Ausnahme werfen,
  sonst bricht er den Anruf ab.
- Die Protokolle des LiveKit-Servers und des SIP-Dienstes sind damit nicht
  erfasst; die kommen mit T0 in #14.

## Latenz (`latency.py`)

- Je Antwort schreibt der Agent `e2e_latency` aus `ChatMessage.metrics` ins
  Log, nur Zahlen, und am Gesprächsende Median und Höchstwert. Gemessen
  wird mit einem echten Anbieter nach #18; die Werte gehören ins Issue.

## Entwicklung

- LiveKit-Server im Compose mit `--dev --node-ip 127.0.0.1`, Schlüssel aus
  `LIVEKIT_API_KEY`/`LIVEKIT_API_SECRET`. Der Worker tritt jedem neuen Raum
  bei; ein Raum, der schon vor dem Neustart des Agenten bestand, bekommt
  keinen Agenten mehr, deshalb für jeden Versuch einen neuen Raumnamen.
- Im Browser über `python -m mymvz_voice.join_token` und meet.livekit.io
  (README). Ein eigener Test-Client muss seine Spur als Mikrofon
  veröffentlichen (`TrackSource.SOURCE_MICROPHONE`), sonst hört der Agent
  sie nicht.
- Tests laufen im Textmodus von `AgentSession` mit der LLM-Attrappe, ohne
  LiveKit-Server; `pytest-asyncio` im Modus `auto`.
