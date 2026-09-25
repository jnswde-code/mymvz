---
name: session-hygiene
description: "Abgeschlossene Sessions: Präfix _closed_ + archivieren; danach git worktree list prüfen"
metadata:
  type: feedback
---

Abgeschlossene Sessions bekommen beides: den Titel-Präfix `_closed_ ` und danach `archive_session`.

**Why:** So vom Nutzer entschieden, als 12 aktive Sessions ohne Markierung aufgelaufen waren. Der Präfix bleibt im Archiv und beim Zurückholen sichtbar, das Archivieren nimmt die Session aus der aktiven Liste. Das Archivieren entfernt den Worktree nicht verlässlich; am 25.9.2026 lagen 52 Worktrees archivierter Sessions herum.

**How to apply:** Nur Sessions archivieren, denen der Nutzer zugestimmt hat. Danach `git worktree list`, und den Worktree im selben Zug mit `git worktree remove` und `git worktree prune` entfernen. Vorher sicherstellen, dass keine Session darin läuft (`list_sessions` mit `include_archived`, `readlink /proc/<pid>/cwd`).
