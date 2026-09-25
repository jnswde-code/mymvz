---
name: issue-ist-der-prompt
description: "Keinen Extra-Prompt je Issue; Stand ins Issue, dann reicht „Bearbeite Issue #N“"
metadata:
  type: feedback
---

Fragt der Nutzer, ob er sich für jedes Issue einen Prompt schreiben lassen soll: nein, das Issue ist der Prompt. Der Stand (erledigt, woran es hängt, Einstieg, empfohlenes Modell) kommt als Kommentar ins Issue.

**Why:** Ein zweiter Text neben dem Issue läuft auseinander, und die ausführende Session liest Issue und Code ohnehin selbst. Ein Prompt, der ohne Blick in den Code eine Lösung vorschreibt, lässt Vermutungen umsetzen statt des Codes.

**How to apply:** Einen eigenen Prompt nur, wenn es noch kein Issue gibt. Dann Ziel, Grenzen und einen Haltepunkt nach dem Vorschlag hineinschreiben, keine Lösung. Blockierte Issues, die auf Entscheidungen warten, gebündelt als Liste mit Optionen und Empfehlung vorlegen. Siehe [[nur-das-bestellte-tun]].
