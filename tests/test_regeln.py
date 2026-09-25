"""Waechter fuer die Ablage des Projektwissens.

CLAUDE.md enthaelt nur, was fuer jede Session gilt, und eine Karte der
Module. Das Warum je Modulgruppe steht in .claude/rules/<cluster>.md, und
Claude Code laedt eine solche Datei erst, wenn eine Datei aus ihrem `paths:`
gelesen wird. Beide Fehlerarten fielen sonst niemandem auf: ein neues Modul,
das in keinem `paths:` steht, bekommt sein Warum nie zu sehen, und eine
Regeldatei ohne `paths:` laedt in jeder Session, wie die alte CLAUDE.md.
Dazu die Groessengrenzen aus CLAUDE.md, weil die Wurzel sonst in ein paar
Wochen wieder bei zweitausend Zeilen steht.

Die Dateien kommen aus dem Dateisystem statt aus `git ls-files`: das `.git`
einer Worktree loest im Container nicht auf.
"""

from __future__ import annotations

import os
import re
from functools import cache
from pathlib import Path

import pytest

WURZEL = Path(__file__).resolve().parent.parent
REGELN = WURZEL / ".claude" / "rules"

WURZEL_HOECHSTENS_ZEILEN = 300
REGELDATEI_HOECHSTENS_ZEILEN = 250

# Was als Quelldatei zaehlt: Code, Vorlagen, Stylesheets, Container und CI.
_ENDUNGEN = {".py", ".js", ".html", ".css", ".yml", ".yaml", ".sh", ".conf", ".toml"}
_DATEINAMEN = {"Dockerfile"}

# Nie Quelltext: Abhaengigkeiten, Caches und andere Worktrees, ueberall.
_AUSGENOMMENE_NAMEN = {".git", ".venv", "venv", "node_modules", "__pycache__", ".pytest_cache", ".ruff_cache"}
# Die per .gitignore ausgeschlossenen Ablagen, Skills und Agenten (Werkzeug
# fuer die Sessions selbst, an keinen Cluster gebunden) und das unveraenderte
# Quellpaket der Arbeitsweise (s. CLAUDE.md, Karte).
_AUSGENOMMENE_ORDNER = {
    ".claude/worktrees",
    "claude-arbeitsweise",
    ".claude/skills",
    ".claude/agents",
}


@cache
def _dateien() -> tuple[str, ...]:
    """Alle Dateien im Projekt, relativ zur Wurzel, ohne die Ausnahmen."""
    gefunden = []
    for ordner, unterordner, dateien in os.walk(WURZEL):
        relativ = Path(ordner).relative_to(WURZEL).as_posix()
        praefix = "" if relativ == "." else relativ + "/"
        unterordner[:] = [
            u for u in unterordner
            if u not in _AUSGENOMMENE_NAMEN and praefix + u not in _AUSGENOMMENE_ORDNER
        ]
        gefunden += [praefix + d for d in dateien]
    return tuple(sorted(gefunden))


def _quelldateien() -> list[str]:
    return [
        d for d in _dateien()
        if Path(d).suffix in _ENDUNGEN or Path(d).name in _DATEINAMEN
    ]


def _klammern_aufloesen(muster: str) -> list[str]:
    """`a/{b,c}.py` -> `a/b.py`, `a/c.py`; verschachtelt nicht noetig."""
    treffer = re.search(r"\{([^{}]*)\}", muster)
    if not treffer:
        return [muster]
    ergebnis = []
    for teil in treffer.group(1).split(","):
        ergebnis += _klammern_aufloesen(muster[: treffer.start()] + teil + muster[treffer.end():])
    return ergebnis


def _als_regex(muster: str) -> re.Pattern:
    """Glob wie in Claude Code: `**` ueber Verzeichnisse, `*` nicht ueber `/`."""
    teile = []
    i = 0
    while i < len(muster):
        if muster.startswith("**/", i):
            teile.append("(?:.*/)?")
            i += 3
        elif muster.startswith("**", i):
            teile.append(".*")
            i += 2
        elif muster[i] == "*":
            teile.append("[^/]*")
            i += 1
        elif muster[i] == "?":
            teile.append("[^/]")
            i += 1
        else:
            teile.append(re.escape(muster[i]))
            i += 1
    return re.compile("".join(teile) + r"\Z")


@cache
def _regexe(muster: str) -> tuple[re.Pattern, ...]:
    return tuple(_als_regex(m) for m in _klammern_aufloesen(muster))


def _trifft(muster: str, datei: str) -> bool:
    return any(r.match(datei) for r in _regexe(muster))


def _pfade_lesen(text: str) -> list[str] | None:
    """Die Liste unter `paths:` im Frontmatter, None ohne Frontmatter.

    Claude Code liest YAML; hier gilt bewusst nur eine Schreibweise
    (`  - "muster"`), damit kein Eintrag still aus der Pruefung faellt. Jede
    andere Listenzeile ist ein Fehler mit Meldung statt eines Abbruchs.
    """
    kopf = re.match(r"---\n(.*?)\n---\n", text.replace("\r\n", "\n"), re.S)
    if not kopf:
        return None
    zeilen = kopf.group(1).splitlines()
    if "paths:" not in zeilen:
        return None
    pfade = []
    for zeile in zeilen[zeilen.index("paths:") + 1:]:
        if not re.match(r"\s+-", zeile):
            break
        eintrag = re.fullmatch(r'\s+-\s+"([^"]+)"', zeile)
        if not eintrag:
            raise ValueError(f'paths:-Eintrag bitte als  - "muster" schreiben: {zeile!r}')
        pfade.append(eintrag.group(1))
    return pfade


def _regeldateien() -> list[Path]:
    return sorted(REGELN.glob("*.md"))


@cache
def _alle_pfade() -> dict[str, list[str]]:
    return {d.stem: _pfade_lesen(d.read_text(encoding="utf-8")) or [] for d in _regeldateien()}


def _karte_cluster() -> set[str]:
    """Die Cluster, die CLAUDE.md in der Karte nennt (`**\\`name\\`**:`)."""
    wurzel = (WURZEL / "CLAUDE.md").read_text(encoding="utf-8")
    assert "\n## Karte" in wurzel, "CLAUDE.md: Abschnitt „## Karte“ fehlt"
    karte = wurzel.split("\n## Karte", 1)[1].split("\n## ", 1)[0]
    return set(re.findall(r"^\*\*`([a-z-]+)`\*\*", karte, re.M))


def test_muster_hilfen():
    """Gegenprobe zur Musterlogik, sonst waere jeder weitere Test wertlos."""
    assert _klammern_aufloesen("a/{b,c}.py") == ["a/b.py", "a/c.py"]
    assert _trifft("templates/**/*.html", "templates/index.html")
    assert _trifft("templates/**/*.html", "templates/x/y.html")
    assert _trifft("src/**", "src/test/a.test.js")
    assert _trifft("docker-compose*.yml", "docker-compose.test.yml")
    assert not _trifft("src/*.html", "src/sub/x.html")
    assert not _trifft("src/{a,b}.py", "src/a_alt.py")
    assert _pfade_lesen('---\npaths:\n  - "a.py"\n  - "b/**"\n---\n# x\n') == ["a.py", "b/**"]
    assert _pfade_lesen("# ohne Frontmatter\n") is None
    with pytest.raises(ValueError):
        _pfade_lesen('---\npaths:\n  - "a.py"\n  - b.py\n---\n')


def test_es_gibt_regeldateien():
    assert _regeldateien(), "keine Regeldatei unter .claude/rules/"


@pytest.mark.parametrize("regeldatei", _regeldateien(), ids=lambda d: d.name)
def test_jede_regeldatei_hat_paths(regeldatei):
    """Ohne `paths:` laedt eine Regeldatei beim Start jeder Session."""
    assert _pfade_lesen(regeldatei.read_text(encoding="utf-8")), (
        f"{regeldatei.name}: kein `paths:` im Frontmatter"
    )


def test_jedes_muster_trifft_eine_datei():
    """Ein Muster ohne Treffer ist ein Tippfehler oder ein umbenanntes Modul."""
    dateien = _dateien()
    leer = [
        f"{cluster}: {teilmuster}"
        for cluster, muster in _alle_pfade().items()
        for m in muster
        for teilmuster in _klammern_aufloesen(m)
        if not any(_trifft(teilmuster, d) for d in dateien)
    ]
    assert not leer, "Muster ohne Treffer:\n" + "\n".join(leer)


def test_jede_quelldatei_gehoert_zu_einer_regeldatei():
    """Ein neues Modul braucht einen `paths:`-Eintrag (CLAUDE.md, „Wohin neues Wissen gehört“)."""
    muster = [m for liste in _alle_pfade().values() for m in liste]
    ohne = [d for d in _quelldateien() if not any(_trifft(m, d) for m in muster)]
    assert not ohne, "Ohne Regeldatei:\n" + "\n".join(ohne)


def test_karte_und_regeldateien_decken_sich():
    assert _karte_cluster() == set(_alle_pfade())


def test_wurzel_bleibt_klein():
    zeilen = (WURZEL / "CLAUDE.md").read_text(encoding="utf-8").count("\n")
    assert zeilen < WURZEL_HOECHSTENS_ZEILEN, (
        f"CLAUDE.md hat {zeilen} Zeilen; was nicht fuer jede Session gilt, "
        "gehoert in eine Regeldatei"
    )


@pytest.mark.parametrize("regeldatei", _regeldateien(), ids=lambda d: d.name)
def test_regeldatei_bleibt_teilbar(regeldatei):
    zeilen = regeldatei.read_text(encoding="utf-8").count("\n")
    assert zeilen <= REGELDATEI_HOECHSTENS_ZEILEN, (
        f"{regeldatei.name} hat {zeilen} Zeilen; ab {REGELDATEI_HOECHSTENS_ZEILEN} teilen"
    )
