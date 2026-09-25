# Prompt für die erste Session im privaten Projekt

Das Paket `claude-arbeitsweise/` in das private Projekt legen (oder daneben)
und diesen Text als ersten Prompt in eine neue Claude-Code-Session im
Projektordner geben. Opus reicht.

---

Richte meine Arbeitsweise aus dem Ordner `claude-arbeitsweise/` in diesem
Projekt ein. Lies zuerst dessen `README.md`, dann geh in dieser Reihenfolge vor
und halte nach Schritt 1 an, bis ich „weiter“ sage.

1. **Bestandsaufnahme, noch nichts ändern.** Stell fest: Git-Hosting (GitHub
   oder GitLab, welches CLI ist da: `gh` oder `glab`, angemeldet?), Hauptzweig,
   ob es einen Veröffentlichungszweig oder ein Deploy gibt, Sprache und
   Konvention der Bezeichner im Code, wie Linter und Tests laufen (lokal oder
   im Container), ob es schon eine `CLAUDE.md`, `.claude/`-Dateien oder ein
   Memory gibt. Sag mir in einer kurzen Liste, was du vorgefunden hast und was
   du an den Vorlagen deshalb anpassen wirst. Dann anhalten.

2. **Global** (gilt für alle meine Projekte): `global/CLAUDE.md` nach
   `~/.claude/CLAUDE.md`, `global/hooks/memory-hinweis.sh` nach
   `~/.claude/hooks/` (ausführbar, braucht `jq`), und den Stop-Hook aus
   `global/settings.json` in `~/.claude/settings.json` einmischen, ohne
   vorhandene Einstellungen zu überschreiben. Gibt es schon eine globale
   `CLAUDE.md`, beide zusammenführen und mir den Unterschied zeigen.

3. **Projekt:** `projekt/CLAUDE.md` als Vorlage nehmen und aus dem echten
   Code füllen: ein Absatz zum Projekt, die Karte der Module in zwei bis fünf
   Cluster, je Cluster eine Regeldatei unter `.claude/rules/` mit `paths:`,
   die Testbefehle. Regeldateien enthalten nur das Warum, das sich aus dem Code
   nicht ergibt; steht dir nichts Belegbares zur Verfügung, bleibt die Datei
   kurz. `projekt/tests/test_regeln.py` übernehmen (Endungen und Ausnahmen an
   das Projekt anpassen) und grün bekommen. `.claude/settings.json` und den
   Hook `release_push_bestaetigen.py` nur, wenn es einen Veröffentlichungszweig
   gibt, dann dessen Namen im Hook eintragen; sonst beides weglassen. Den
   Skill `wellen-organisation` nach `.claude/skills/` übernehmen und die
   Stellen mit `gh`/`glab` und Release-Zweig an das Projekt anpassen.

4. **Memory:** die Dateien aus `memory/` in das Memory-Verzeichnis dieses
   Projekts legen (`~/.claude/projects/<projekt-slug>/memory/`, der Slug ist
   der absolute Projektpfad mit `-` statt `/`) und `MEMORY.md` dort anlegen
   oder ergänzen. Nichts umschreiben, die Dateien sind fertig.

5. **Issue-Pflicht scharf schalten:** Prüfe, dass `gh` bzw. `glab` angemeldet
   ist und ein Issue anlegen kann. Leg als Probe ein Issue „Arbeitsweise
   eingerichtet“ an, mach für alles aus Schritt 2 bis 4 einen Branch
   `claude/issue-<n>-arbeitsweise` und einen PR/MR mit dem Abschnitt
   „Prüfung“. Lass `/code-review` darüber laufen. Schlag mir dann den Merge
   vor und warte auf mein Ja.

6. **Probelauf:** Nimm dir danach ein echtes offenes Issue dieses Projekts
   vor, schreib den Kommentar „Stand <Datum>“ nach dem Muster im Skill hinein
   und sag mir, mit welchem Prompt und welchem Modell ich die nächste Session
   dafür starte. Nicht selbst umsetzen.

Antworte auf Deutsch. Was du nicht sicher weißt, fragst du in Schritt 1,
nicht später.
