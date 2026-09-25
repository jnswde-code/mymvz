---
name: regel-streichen-statt-sonderfaelle
description: "Erzeugt eine Regel laufend Sonderfälle, die Regel weglassen"
metadata:
  type: feedback
---

Erzeugt eine Regel laufend neue Sonderfälle, ist die Regel das Problem.

**Why:** Am 23.9.2026 kamen aus einer einzigen Regel („der Notfall-Login endet, sobald ein Admin existiert“) vier Sicherheitsbefunde in zwei Prüfdurchgängen, und ich baute für jeden eine eigene Abhilfe. Der Nutzer brach ab: „vereinfache das“. Nach dem Streichen der Regel war der Diff kleiner und alle vier Befunde weg.

**How to apply:** Sobald die zweite Absicherung für dieselbe Regel entsteht, anhalten und fragen, ob die Regel selbst nötig ist. Einen Zustand fest machen (immer an oder immer aus) schlägt eine Umschaltlogik mit Ausnahmen.
