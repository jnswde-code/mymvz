# mymvz – Projekt im Aufbau

Das Repo enthält noch keinen Anwendungscode, nur die Arbeitsweise für Claude
(diese Datei, `.claude/`, `tests/test_regeln.py`) und das Quellpaket
`claude-arbeitsweise/`. Zweck und Stack stehen hier, sobald sie feststehen.
`README.md` beschreibt für Menschen, was es gibt und wie man es startet.

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
- **Die Geschichte** steht in Issues, PRs und im Git-Log: was vorher galt,
  verworfene Fassungen, Messwerte. In den Regeldateien steht davon nur die
  Issue-Nummer.

**Wohin neues Wissen gehört.** Ohne diese Regel wächst die Datei wieder.
- Das Warum einer Änderung: in die Regeldatei ihres Clusters, in der Gegenwart,
  ein bis drei Sätze, Issue-Nummer als Verweis („(#12)“).
- Wie es dazu kam, was vorher galt, Messwerte: ins Issue oder in den PR.
  Erklärt es eine bestimmte Codezeile, als Kommentar dorthin.
- In diese Datei nur, was für jede Session gilt. Ein neues Modul bekommt hier
  eine Zeile in der Karte und in einer Regeldatei einen `paths:`-Eintrag.
  Mit dem ersten Anwendungscode entstehen die ersten fachlichen Cluster.
- Grenzen: diese Datei unter 300 Zeilen, eine Regeldatei unter 250.
  `tests/test_regeln.py` prüft beides, dazu dass jede Quelldatei in einem
  `paths:` steht und jedes Muster eine Datei trifft.

## Regeln für jede Session

Die allgemeine Arbeitsweise (Issue + PR, Code-Review vor dem Merge,
Modellwahl, Secrets, Sessions) steht in `~/.claude/CLAUDE.md`. Die Vorlage
dafür liegt in `claude-arbeitsweise/global/CLAUDE.md`. Hier nur, was in diesem
Projekt dazukommt:

- **Hosting:** GitHub, [jnswde-code/mymvz](https://github.com/jnswde-code/mymvz).
  In Cloud-Sessions gibt es kein `gh`; Issues, PRs und Kommentare laufen über
  die GitHub-Tools der Session.
- **Bezeichner:** noch festzulegen, sobald es Code gibt, dann durchgehend.
- **Zweige:** `main` ist die Integrationslinie. Einen Veröffentlichungszweig
  gibt es nicht.
- **Modell:** In diesem Projekt gibt es nur Opus, kein Fable. Statt des
  Modells wird der Aufwand gewählt: `xhigh`, wo die Arbeitsweise Fable
  empfiehlt, sonst `high`.
- **Test in derselben Änderung.** Enthält eine Änderung eine Verzweigung, eine
  Regex oder eine Randbedingung, die falsch sein könnte, bekommt sie einen
  Test. Abgeschlossen ist sie erst mit einem grünen Lauf (Befehle unter
  „Tests“). Reine Verdrahtung braucht keinen Test.
- **Secrets** stehen in `.env` und werden von dort gelesen, nie in Ausgaben,
  Commits oder Dateien im Repo. Das Repo ist öffentlich.

## Karte: Module und ihre Regeldatei

**`werkzeug`**: Prüfungen der Projektablage selbst
- `tests/test_regeln.py`: wacht über `CLAUDE.md`, `.claude/rules/` und die
  Zuordnung jeder Quelldatei zu einem Cluster

`claude-arbeitsweise/` (Quellpaket), `.claude/skills/` und
`.claude/agents/` gehören zu keinem Cluster.

## Tests

Tests und Werkzeuge laufen im Docker-Container, nicht mit dem Python des
Hosts: Lokal ist `python3` unter Windows nur ein Platzhalter, und der
Container entspricht dem späteren Betrieb. `MSYS_NO_PATHCONV=1` hält Git
Bash davon ab, `/w` in einen Windows-Pfad umzuschreiben.

    MSYS_NO_PATHCONV=1 docker run --rm -v "$PWD:/w" -w /w python:3-slim sh -c "pip install -q pytest && python -m pytest tests/"

## Starten

Noch nichts zu starten.
