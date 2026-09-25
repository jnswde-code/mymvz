---
name: bilder-vor-merge-im-chat
description: "Bei sichtbaren Oberflächenänderungen je Seite 1 Bild vorher + 1 nachher in den Chat, vor der Merge-Frage"
metadata:
  type: feedback
---

Ändert eine Session Layout, Bedienung oder Text einer Oberfläche, schickt sie vor der Frage nach der Merge-Freigabe je Seite ein Bild vorher und eins nachher per `SendUserFile` in den Chat, mit einer Zeile, was sich geändert hat.

**Why:** Der Nutzer gibt den Merge in der Session frei und will dort sehen, was sich ändert, ohne den PR/MR im Browser zu öffnen. Bilder nur in der PR-Beschreibung reichten nicht.

**How to apply:** Kein Pflichtschritt bei jeder Änderung, nur bei sichtbaren oder auf Nachfrage, weil jede Vorschau Token kostet. Sparsam: 15 Bilder waren zu viel. Seiten mit personenbezogenen Daten aus einer leeren Vorschau aufnehmen.
