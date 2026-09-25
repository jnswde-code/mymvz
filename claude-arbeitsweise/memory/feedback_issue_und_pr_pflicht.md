---
name: issue-und-pr-pflicht
description: "Issue + Pull/Merge Request für jede Änderung; gemergt wird bewusst lokal per git"
metadata:
  type: feedback
---

Zu jeder Änderung gehört ein Issue, und der Weg nach `main` führt über einen PR/MR. Gemergt wird lokal per git, nicht über den Knopf der Weboberfläche.

**Why:** Der Projektstand soll vollständig im Git-Hosting ablesbar sein, nicht teilweise in lokalen Branches und Commit-Nachrichten einer Maschine. Der lokale Merge hält den Nutzer in der Session, die den Stand geprüft hat, und die Freigabe passiert dort.

**How to apply:** Vor der Arbeit Issue anlegen oder finden, Branch `claude/issue-<n>-<kurz>`, PR/MR mit Abschnitt „Prüfung“ (Linter, Tests, Code-Review). Merge erst nach dem Ja des Nutzers in dieser Session, dann Branch löschen. Siehe [[code-review-vor-merge]], [[issue-ist-der-prompt]].
