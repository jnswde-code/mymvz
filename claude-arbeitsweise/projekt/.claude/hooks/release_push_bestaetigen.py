#!/usr/bin/env python3
"""PreToolUse-Hook (Bash): fragt vor einem Push nach, der eine Veroeffentlichung ausloest.

Ein Push auf den Veroeffentlichungszweig (RELEASE_ZWEIG) ist keine
Zwischenablage, sondern ein Deploy. "main" ist davon nicht betroffen und wird
hier nicht abgefragt. Den Zweignamen unten anpassen; gibt es keinen solchen
Zweig, den Hook aus .claude/settings.json nehmen.
"""

import json
import re
import subprocess
import sys

RELEASE_ZWEIG = "deployment"

_GIT_PUSH = re.compile(r"(^|[;&|]\s*)git\s.*push")
_UPSTREAM_RELEASE = re.compile(rf"/{re.escape(RELEASE_ZWEIG)}$")

HINWEIS = f"""Dieser Push zielt auf "{RELEASE_ZWEIG}" - den Veroeffentlichungszeiger, keinen Zwischenstand.

Vorher pruefen, was rausginge:

  git log {RELEASE_ZWEIG}..main --oneline

Nur bestaetigen, wenn genau diese Veroeffentlichung gewollt ist. Fertige
Arbeit, die noch nicht live soll, gehoert auf "main"."""


def _git(arbeitsverzeichnis: str, *argumente: str) -> str:
    """Git-Abfrage, die bei jedem Fehler leer zurueckkommt statt zu werfen."""
    try:
        ergebnis = subprocess.run(
            ["git", "-C", arbeitsverzeichnis, *argumente],
            capture_output=True,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return ""
    return ergebnis.stdout.strip() if ergebnis.returncode == 0 else ""


def nachfragen(befehl: str, zweig: str = "", upstream: str = "") -> bool:
    """True, wenn der Befehl auf den Release-Zweig zielt.

    `zweig`/`upstream` decken "git push" ohne Argumente ab - dort steht das Ziel
    nicht im Befehlstext, sondern im Zustand des Arbeitsbaums.
    """
    if not _GIT_PUSH.search(befehl):
        return False
    if RELEASE_ZWEIG in befehl:
        return True
    return zweig == RELEASE_ZWEIG or bool(_UPSTREAM_RELEASE.search(upstream))


def main() -> None:
    eingabe = json.load(sys.stdin)
    befehl = (eingabe.get("tool_input") or {}).get("command") or ""
    arbeitsverzeichnis = eingabe.get("cwd") or "."

    if not _GIT_PUSH.search(befehl):
        return

    zweig = _git(arbeitsverzeichnis, "rev-parse", "--abbrev-ref", "HEAD")
    upstream = _git(arbeitsverzeichnis, "rev-parse", "--abbrev-ref", "@{u}")
    if not nachfragen(befehl, zweig, upstream):
        return

    json.dump(
        {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "ask",
                "permissionDecisionReason": HINWEIS,
            }
        },
        sys.stdout,
    )


if __name__ == "__main__":
    main()
