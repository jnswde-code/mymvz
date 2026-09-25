# Claude-Arbeitsweise, übertragbar

Extrakt aus dem SiKi-Projekt (Stand 25.9.2026): alles, was an der Arbeitsweise
projektunabhängig ist, ohne SiKi-Bezüge. Der Einstieg ist
`EINRICHTUNGS-PROMPT.md`: Ordner ins private Projekt legen, den Prompt in die
erste Session geben, Claude richtet den Rest ein und passt die Vorlagen an das
Projekt an.

## Was drin ist

| Ordner | Ziel | Inhalt |
|---|---|---|
| `global/` | `~/.claude/` | `CLAUDE.md` mit den Regeln für jede Session (Issue + PR, Code-Review vor dem Merge, Modellwahl, Secrets, Sessions, Memory); Stop-Hook `memory-hinweis.sh`, der einmal je Session ans Memory erinnert; `settings.json` mit dem Hook-Eintrag |
| `projekt/` | Projektwurzel | `CLAUDE.md`-Vorlage (Wissensablage, Karte, Tests); `.claude/rules/kern.md` als Muster einer Regeldatei mit `paths:`; `.claude/settings.json` + Hook `release_push_bestaetigen.py` (fragt vor einem Push auf den Veröffentlichungszweig); Skill `wellen-organisation` für die Organisations-Session; `tests/test_regeln.py`, der die Ablage prüft |
| `memory/` | `~/.claude/projects/<slug>/memory/` | zwölf Feedback-Memories mit dem Warum hinter den Regeln, plus `MEMORY.md` als Index |
| `EINRICHTUNGS-PROMPT.md` | erste Session | der Prompt, der alles einrichtet |

## Die Idee in drei Sätzen

Wissen liegt in drei Schichten: `CLAUDE.md` sagt, was in jeder Session gilt,
`.claude/rules/<cluster>.md` sagt das Warum je Modulgruppe und lädt nur, wenn
eine Datei aus `paths:` mit dem Read-Tool gelesen wird, und die Geschichte
bleibt in Issues und git. Arbeit läuft über Issues, und das Issue selbst ist
der Prompt für die Session, die es umsetzt. Zwischen Sessions redet man über
das Memory, und der Stop-Hook sorgt dafür, dass es gepflegt wird.

## Was bewusst nicht drin ist

- Die SiKi-Hooks für Host-`uv` und Compose-Override, die Fachprüfer
  `patientendaten-review` und `mandanten-trennung`, die Referenzen zu GitLab
  und Deploy. Alles projektgebunden; das Muster (Skill mit `description`,
  Agent mit `tools:` und `model:`) ist in `wellen-organisation` zu sehen.
- Die `project_*`- und `reference_*`-Memories, sie beschreiben SiKi.

## Voraussetzungen

- Claude Code (Desktop-App oder CLI) mit Memory und Hooks.
- `jq` für den Stop-Hook, `python3` für den Push-Hook.
- `gh` oder `glab` angemeldet, sonst greift die Issue-Pflicht ins Leere.
