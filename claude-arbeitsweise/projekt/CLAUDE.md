# <Projektname> – <ein Satz, was es ist>

<Zwei bis vier Sätze: was das Projekt tut, welche Teile es gibt, wo es läuft.
`README.md` beschreibt für Menschen, was es gibt und wie man es startet.>

## Wie dieses Wissen abgelegt ist

- **Diese Datei** enthält nur, was für jede Session gilt und sich nicht aus dem
  Code ergibt, dazu die Karte der Module.
- **`.claude/rules/<cluster>.md`** enthält das Warum je Modulgruppe:
  Entscheidungen, Randbedingungen und Fallen. Claude Code lädt eine Regeldatei
  erst, wenn eine Datei aus ihrem `paths:` **mit dem Read-Tool** gelesen wird.
  `cat`, `sed` oder `grep` in der Shell lösen das nicht aus. Eine Datei, die du
  ändern willst, deshalb vorher mit Read öffnen. Braucht eine Aufgabe einen
  Cluster, dessen Dateien sie nicht liest, die Regeldatei direkt lesen (Karte
  unten).
- **Die Geschichte** steht in Issues, PRs/MRs und im Git-Log: was vorher galt,
  verworfene Fassungen, Messwerte. In den Regeldateien steht davon nur die
  Issue-Nummer.

**Wohin neues Wissen gehört.** Ohne diese Regel wächst die Datei wieder.
- Das Warum einer Änderung: in die Regeldatei ihres Clusters, in der Gegenwart,
  ein bis drei Sätze, Issue-Nummer als Verweis („(#12)“).
- Wie es dazu kam, was vorher galt, Messwerte: ins Issue oder in den PR/MR.
  Erklärt es eine bestimmte Codezeile, als Kommentar dorthin.
- In diese Datei nur, was für jede Session gilt. Ein neues Modul bekommt hier
  eine Zeile in der Karte und in einer Regeldatei einen `paths:`-Eintrag.
- Grenzen: diese Datei unter 300 Zeilen, eine Regeldatei unter 250.
  `tests/test_regeln.py` prüft beides, dazu dass jede Quelldatei in einem
  `paths:` steht und jedes Muster eine Datei trifft.

## Regeln für jede Session

Die allgemeine Arbeitsweise (Issue + PR/MR, Code-Review vor dem Merge,
Modellwahl, Secrets, Sessions) steht in `~/.claude/CLAUDE.md`. Hier nur, was
in diesem Projekt dazukommt:

- **Bezeichner:** <deutsch | englisch> durchgehend, nicht mischen.
- **Zweige:** `main` ist die Integrationslinie. <Falls es einen
  Veröffentlichungszweig gibt: `<release>` ist der Veröffentlichungszeiger, ein
  Push dorthin deployt. Der Hook `release_push_bestaetigen.py` fragt vorher
  nach. Sonst diesen Punkt streichen und den Hook aus `.claude/settings.json`
  nehmen.>
- **Test in derselben Änderung.** Enthält eine Änderung eine Verzweigung, eine
  Regex oder eine Randbedingung, die falsch sein könnte, bekommt sie einen
  Test. Abgeschlossen ist sie erst mit einem grünen Lauf (Befehle unter
  „Tests“). Reine Verdrahtung braucht keinen Test.
- **Secrets** stehen in `.env` und werden von dort gelesen, nie in Ausgaben,
  Commits oder Dateien im Repo.

## Wichtige Entscheidungen

<Jede Entscheidung, die über ihren Cluster hinaus gilt, in ein bis zwei
Sätzen mit Verweis auf die Regeldatei. Beispiel:>

- **<Entscheidung>.** <Warum, ein Satz.> → `<cluster>`

## Karte: Module und ihre Regeldatei

<Je Cluster ein Absatz. Der Name in Backticks ist der Dateiname unter
`.claude/rules/`, der Test liest ihn genau so aus.>

**`kern`**: <Was der Cluster umfasst>
- `<pfad/modul>`: <ein Halbsatz>

## Tests

<Wie Linter und Tests laufen, ein Befehl je Zeile in einem Codeblock. Wenn
Befehle im Container laufen müssen, hier den Grund nennen.>

    <testbefehl>

## Starten

<Wie man das Projekt lokal startet, kurz. Einzelheiten in `README.md`.>
