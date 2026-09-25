#!/usr/bin/env bash
# Stop-Hook: erinnert einmal je Session daran, dauerhaft Merkenswertes ins
# projektbezogene Memory zu schreiben - das ist der Kanal, ueber den andere
# Sessions desselben Projekts auf Stand bleiben (es wird in jede neue Session
# geladen).
#
# Zwei Bremsen, beide noetig:
#
#   1. "Stop" feuert am Ende JEDES Assistenten-Turns, nicht erst am
#      Sessionende - ein echtes Sessionende-Ereignis, bei dem das Modell noch
#      handeln koennte, gibt es nicht. Ohne Bremse kaeme der Hinweis nach
#      jeder einzelnen Antwort.
#   2. Der Hinweis blockiert das Beenden EINMAL (decision: block), damit das
#      Modell tatsaechlich reagiert statt den Hinweis nur anzuzeigen. Die
#      Marker-Datei verhindert dabei die Endlosschleife: beim zweiten
#      Stop-Versuch existiert sie, der Hook steigt sofort aus.
#
# Ausgeloest wird nur, wenn die Session ueberhaupt etwas abgeschlossen hat -
# Commits, die der Upstream noch nicht kennt. Ein blosser schmutziger
# Arbeitsbaum reicht bewusst nicht: mitten in der Arbeit ist der falsche
# Moment fuer einen Merkposten.

set -u

eingabe="$(cat)"
sitzung="$(printf '%s' "$eingabe" | jq -r '.session_id // empty' 2>/dev/null)"
[ -n "$sitzung" ] || exit 0

marker="${TMPDIR:-/tmp}/claude-memory-hinweis-${sitzung}"
[ -e "$marker" ] && exit 0

# Kein Repo (z.B. Scratch-Workspace) -> nichts zu melden.
git rev-parse --git-dir >/dev/null 2>&1 || exit 0

# Commits, die oben noch fehlen. Gegen den Upstream des aktuellen Branches;
# nur ein frischer Branch ohne Upstream vergleicht ersatzweise mit
# origin/main. Ein gepushter Feature-Branch liegt immer vor origin/main und
# loeste sonst in jeder Session aus.
if git rev-parse --abbrev-ref '@{u}' >/dev/null 2>&1; then
  voraus="$(git log --oneline '@{u}..HEAD' 2>/dev/null)"
else
  voraus="$(git log --oneline origin/main..HEAD 2>/dev/null)"
fi
[ -n "$voraus" ] || exit 0

: > "$marker"

jq -n '{
  decision: "block",
  reason: ("Bevor du diese Session beendest, einmalige Pruefung: Ist in dieser Session etwas aufgekommen, das andere Sessions dieses Projekts wissen muessten? Eine Praeferenz des Nutzers, eine Stolperfalle, ein Projektstand, der sich aus Code und git-Historie nicht ergibt - oder eine bestehende Memory-Datei, die durch diese Aenderungen ueberholt ist. Falls ja: entsprechende Datei im Memory-Verzeichnis anlegen oder korrigieren und MEMORY.md nachziehen. Falls nein: das in einem Satz sagen und normal weitermachen, nicht kuenstlich etwas erfinden. Dieser Hinweis kommt nur einmal je Session."),
  systemMessage: "Memory-Erinnerung (einmalig je Session)",
  suppressOutput: true
}'
