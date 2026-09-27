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
- Der Agent hat keine Datenbank-Zugangsdaten. Auskunft und Anfragen laufen
  über die interne API von `telephony` (Regeldatei `telephony`, #44).
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

## Werkzeuge (`tools.py`, `api_client.py`)

- Die Liste ist abschließend (#14, Abschnitt 7): `get_practice_info`,
  `check_time_window`, `create_phone_request`, `create_callback_request`
  hier, `hand_off` und `end_call` am Agenten. Es gibt kein Werkzeug, das
  vorhandene Anfragen, Termine, Rückrufbitten oder Personen liest. Die
  Terminarten sind ein Thema von `get_practice_info`, kein eigenes Werkzeug.
- Rezept, Überweisung, AU, Befund, Rückruf der Ärztin bzw. des Arztes und
  Absage/Verschiebung werden Rückrufbitten mit Kategorie, ohne Grund und
  ohne Freitext (#45); der Assistent führt nichts davon aus. Akutes,
  Substitution und Hausbesuch bleiben `hand_off`. Wie bei Anfragen legt das
  Werkzeug nach einem Ausfall im selben Anruf nichts mehr an, höchstens
  drei je Anruf.
- Fällt die API aus (nicht konfiguriert, nicht erreichbar, 5 Sekunden ohne
  Antwort, 403/404/5xx), sagt der Agent den festen Satz
  `texts.API_UNAVAILABLE` und beendet die Antwort; das LLM rät nie. Im Log
  steht nur der Grund (Status oder Ausnahme). Eine abgewiesene Eingabe (400)
  geht als `ToolError` mit den Meldungen der API an das LLM, damit es
  nachfragt.
- Anlegen ist nicht wiederholbar: Die Mails gehen im selben HTTP-Aufruf
  raus, ein Ausfall kann nach dem Commit kommen. Deshalb 20 Sekunden statt
  5, und nach einem Ausfall legt das Werkzeug im selben Anruf nichts mehr
  an. Höchstens drei Anfragen je Anruf; die Grenze je Nummer und Tag kommt
  mit P3 (#46).
- Die Wunschtage prüft nur die API (eine Stelle, #7). Das heutige Datum in
  Europe/Berlin steht je Anruf in der Anweisung, sonst rechnet das LLM
  „nächsten Dienstag“ falsch.
- `texts.NOTICE_VERSION` wird mit jeder Anfrage als
  `privacy_notice_version` gespeichert; bei jeder Änderung an Begrüßung oder
  Datenschutzansage auf das Datum setzen.
- Bodies und Antworten der API kommen nie ins Log, nur der Status.
- Die Weiche geht jedem Werkzeug vor: Der Wortfilter in `llm_node` läuft,
  bevor das LLM ein Werkzeug wählen kann.

## Anrufprotokoll (`call_report.py`)

- `CallReport` sammelt je Anruf Beginn, Ergebnisse und die erste Kennung
  bzw. Rückrufbitten-ID und meldet sie am Ende über die API
  (`ctx.add_shutdown_callback`), nie Nummer, Name oder Text (#45). Jede
  Weiche zählt, aus Wortfilter, Taste 0 oder `hand_off`; welches Ergebnis
  gewinnt, entscheidet die Web-App (`emergency_hint` immer). Scheitert die
  Meldung, steht nur der Grund im Log, der Anruf ist ohnehin vorbei.

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
