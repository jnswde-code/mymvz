---
name: code-review-vor-merge
description: "Vor jedem Merge-Vorschlag /code-review über origin/main...HEAD, Funde beheben, Ergebnis in den PR/MR"
metadata:
  type: feedback
---

Bevor eine Session dem Nutzer einen Merge vorschlägt, läuft `/code-review` über den Branch. Funde werden behoben, oder es steht im PR/MR, warum nicht.

**Why:** Bis dahin prüfte nur die Session, die den Code geschrieben hatte, und Fehler zeigten sich erst nach dem Deploy. Ein zweiter Prüfer fand Nebenbefunde, die die schreibende Session übersehen hatte.

**How to apply:** Reihenfolge: umsetzen, Linter und Tests, `/code-review`, Funde beheben, erneut testen, dann den PR/MR vorlegen. Gilt für jede Änderung mit Code, nicht für reine Doku. Ziel als `origin/main...HEAD` angeben, vorher `git fetch`: der lokale `main`-Ref, den sich alle Worktrees teilen, hängt oft hinterher, und dann enthält der Diff fremde, längst gemergte Änderungen. Bei Anmeldung und Autorisierung zusätzlich `/security-review`.
