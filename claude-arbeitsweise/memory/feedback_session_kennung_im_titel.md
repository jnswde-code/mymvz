---
name: session-kennung-im-titel
description: "Titel „<Kennung> · #<Issue> <Kurzname>“; Sessions und Issues immer mit Thema nennen"
metadata:
  type: feedback
---

Laufen mehrere Sessions parallel, steht die Kennung aus dem Wellenplan vorn im Session-Titel: `<Kennung> · #<Issues> <Kurzname>`, etwa `F1 · #54 Konzept Anmeldelink`.

**Why:** Der Nutzer springt zwischen Sessions und soll Rückfragen und Freigaben der richtigen Zeile im Plan zuordnen können, ohne die Titel mit der Tabelle abzugleichen.

**How to apply:** Die App vergibt den Titel aus dem ersten Prompt. Deshalb die Kennung vorn in den Prompt schreiben und als Organisations-Session jede neue Session per `set_session_title` umbenennen. In Antworten Sessions und Issues immer mit Thema nennen, nie nur per Kennung.
