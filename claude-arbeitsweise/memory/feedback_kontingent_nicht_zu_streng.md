---
name: kontingent-nicht-zu-streng
description: "Keine feste Prozentbremse; nur warnen, wenn die Hochrechnung vor dem Reset 100 % reißt"
metadata:
  type: feedback
---

Keine feste Prozentschwelle für das Claude-Kontingent. Warnen nur, wenn die Hochrechnung bis zum Reset über 100 % geht, und dann entscheidet der Nutzer.

**Why:** Eine 85-%-Bremse hielt am 25.9.2026 Arbeit an, obwohl das Kontingent bis zum Reset gereicht hätte. Knapp wird es erst, wenn alle Sessions stillstehen.

**How to apply:** Neue Sessions starten, sobald Dateien und Merges es erlauben. Bei einer Hochrechnung über 100 % die Wahl vorlegen (warten, weniger parallel, Opus statt Fable) statt selbst anzuhalten. Rechenweg im Skill `wellen-organisation`, Abschnitt 1a.
