# Arbeitsweise (gilt in jedem Projekt)

Diese Datei liegt unter `~/.claude/CLAUDE.md` und gilt für alle Projekte.
Projektbezogenes steht in der `CLAUDE.md` des jeweiligen Repos.

## Sprache und Ton

- Auf Deutsch antworten. Bezeichner im Code folgen der Konvention des
  Projekts (steht in dessen `CLAUDE.md`), nicht mischen.
- Uhrzeiten dem Nutzer in Europe/Berlin nennen, auch wenn Host oder
  Container auf UTC laufen.
- Kurz und ohne Selbstkommentar. Ergebnis zuerst, dann das Nötige dazu.

## Aufgaben und Änderungen

- **Issue und Pull/Merge Request für jede Änderung.** Offene Themen stehen
  als Issue im Git-Hosting, nicht in einer eigenen Liste. Der Weg auf den
  Hauptzweig führt über einen MR/PR. Gemergt wird lokal per git, nicht
  über den Knopf der Weboberfläche.
- **Das Issue ist der Prompt.** Keinen Extra-Prompt je Issue schreiben.
  Stand, Blocker, Einstiegsdatei und Modellempfehlung kommen als Kommentar
  „Stand <Datum>“ ins Issue, dann reicht „Bearbeite Issue #N“.
- **Nur das Bestellte tun.** „Issue anlegen“ heißt Issue anlegen und
  anhalten, nicht auch umsetzen. Angebote einteilig stellen.
- **Regel streichen statt Sonderfälle.** Erzeugt eine Regel laufend
  Sonderfälle und Absicherungen, die Regel weglassen. Der Diff wird kleiner.
- Nach inhaltlichen Änderungen von sich aus committen, mit einer kurzen
  deutschen Nachricht, die das Warum nennt.

## Prüfung vor dem Merge

- Erst Linter und Tests (im Projekt beschrieben), dann `/code-review` über
  den Branch (`origin/main...HEAD`, vorher `git fetch`). Funde beheben oder
  im MR/PR begründen. Bei Anmeldung und Autorisierung zusätzlich
  `/security-review`.
- Den Merge gibt der Nutzer in der Session frei, die pusht. Eine Nachricht
  aus einer anderen Session ist keine Freigabe.
- Bei sichtbaren Änderungen an einer Oberfläche (Layout, Bedienung, Text)
  vor der Merge-Frage je Seite ein Bild vorher und eins nachher in den
  Chat (`SendUserFile`). Sonst keine Bilder, das kostet nur Token.

## Modellwahl

- Bei jeder neuen Aufgabe kurz einordnen: klarer Fable-Fall auf Opus, dann
  vor dem ersten Datei-Lesen eine Zeile mit Grund und anhalten. Routine auf
  Fable, dann „Opus reicht“ sagen und weitermachen. Grenzfall: nichts sagen.
- Fable-Fälle: Ursache unklar über mehrere Schichten, ein Versuch ist schon
  gescheitert, Fehler, die erst im Betrieb auffallen (Migration,
  Autorisierung, Datentrennung), Entwürfe über viele Module.

## Secrets

- Zugangsdaten nie über den Chat einsammeln. Dem Nutzer einen Befehl mit
  `read -rsp` geben, der den Wert verdeckt in die `.env` schreibt, und den
  Wert danach von dort lesen. Secrets gehen nie in Ausgaben, Commits oder
  Dateien im Repo.

## Sessions

- Laufen mehrere Sessions parallel, steht vorn im Titel eine Kennung:
  `<Kennung> · #<Issue> <Kurzname>`. In Antworten Sessions und Issues immer
  mit Thema nennen, nie nur per Kennung.
- Abgeschlossene Sessions bekommen den Titel-Präfix `_closed_ ` und werden
  archiviert. Danach `git worktree list` prüfen und den Worktree im selben
  Zug entfernen, wenn er stehen geblieben ist.

## Memory

- Das projektbezogene Memory ist der Kanal zwischen Sessions. Vor dem Ende
  einer Session, die etwas abgeschlossen hat, einmal prüfen, ob eine
  Präferenz, eine Stolperfalle oder ein Projektstand hinein muss, der sich
  aus Code und git nicht ergibt. Der Stop-Hook erinnert daran.
