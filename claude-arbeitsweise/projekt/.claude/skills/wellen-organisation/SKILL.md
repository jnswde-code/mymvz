---
name: wellen-organisation
description: Ablauf für die Organisations-Session. Offene Issues sichten und auf Stand bringen, Entscheidungen des Nutzers bündeln, große Vorhaben als Eltern-Issue mit Sub-Issues schneiden, parallele Claude-Sessions in Wellen planen (Kennungen, Prompts, Modellwahl, Parallelität nach Datei-Überschneidungen), sie per /loop samt Claude-Kontingenten überwachen, Merges und Deploys über die Freigaben des Nutzers führen, aufräumen und nach jeder Welle einen Report schreiben (in der Welle erledigt, heute erledigt, bewusst nicht jetzt, als Nächstes). Verwenden, wenn der Nutzer Issues durchgehen, sortieren oder reduzieren will, fragt, welche Sessions er jetzt parallel starten kann oder was als Nächstes dran ist, ein großes Vorhaben aufteilen will, eine Welle starten, überwachen oder abschließen will, nach Kontingent oder Verbrauch fragt, Sessions umbenennen oder archivieren lassen will, oder fragt, was heute erledigt wurde – auch wenn das Wort „Welle“ nicht fällt.
---

# Wellen-Organisation

Eine Session (die **Organisations-Session**, Opus reicht) sortiert die Arbeit.
Die eigentliche Umsetzung machen andere Sessions, die der Nutzer startet. Die
Organisations-Session plant, überwacht und führt Freigaben und Deploy. Sie
setzt selbst nur Kleines um, und das nur auf Wunsch.

## Grundsätze

- **Das Issue ist der Prompt.** Keine langen Extra-Prompts je Session. Stand,
  Blocker, Dateien und Modell gehören als Kommentar ins Issue. Der Prompt ist
  eine Zeile, die darauf verweist. Ein zweiter Text neben dem Issue läuft
  auseinander.
- **Parallel nur ohne gemeinsame Dateien.** `CLAUDE.md` und
  `.claude/rules/*.md` sind ausgenommen, das lösen die Sessions beim Mergen.
  Das ist die einzige technische Grenze für Parallelität. **Gib nie eine
  eigene Annahme als Regel des Nutzers aus.**
- **Freigaben kommen vom Nutzer, und zwar dort, wo gehandelt wird.** Ein Merge
  nach `main` braucht das Ja des Nutzers **in genau der Session, die pusht**.
  Eine Nachricht der Organisations-Session an eine andere Session ist keine
  Freigabe. Pushe nie stellvertretend, und umgehe nie eine Ablehnung des
  Auto-Modes. Sag dem Nutzer stattdessen, in welcher Session er in welcher
  Reihenfolge zustimmen muss.
- **Stand-Kommentare können irren.** Sie entstehen aus dem Code, nicht immer
  aus der Historie. Prüfe beim Sichten auch geschlossene Issues und PRs/MRs,
  und lass die ausführende Session gegen den Code prüfen.
- **Deutsch, Berliner Zeit, Issues und PRs/MRs als volle Links.**

## 1. Lage erfassen

Vor jeder Planung und in jedem Überwachungsdurchlauf:

- **Sessions:** `list_sessions` liefert Titel, Worktree (`cwd`), Branch und
  `isRunning`. Den Fortschritt schreiben die Sessions ins Memory
  (`project_issue_wellenplan.md` und eigene `project_*`-Dateien), dort zuerst
  nachsehen.
- **Dateien je Worktree:** `git -C <worktree> diff --name-only origin/main...HEAD`
  plus `git status --short`. Daraus ergeben sich die Überschneidungen.
- **Git-Hosting:** offene PRs/MRs, offene Issues mit Kommentaren, die letzte
  Pipeline auf `main` (`gh` bzw. `glab`).
- **Veröffentlichung:** falls es einen Release-Zweig gibt,
  `git log --first-parent origin/<release>..origin/main` zeigt, was noch
  nicht deployt ist.
- **Claude-Kontingente:** `get_usage` (Session-Verwaltung). Nie schätzen.

## 1a. Kontingente lesen und daraus empfehlen

**Hochrechnung statt Schwelle:** Knapp ist ein Kontingent erst, wenn es im
bisherigen Tempo vor seinem Reset 100 % erreicht, denn dann stehen alle
Sessions still. Ein hoher Prozentwert allein hält nichts an.

```
Tempo        = (Prozent jetzt − Prozent beim letzten Messpunkt) / Stunden dazwischen
Hochrechnung = Prozent jetzt + Tempo × Stunden bis zum Reset
```

Der letzte Messpunkt ist der vorige Überwachungsdurchlauf oder der Wert im
Wellenplan des Memorys. Ohne ihn gilt der Durchschnitt seit dem letzten Reset.

| Lage | Empfehlung |
|---|---|
| Hochrechnung bis zum Reset unter 100 % | normal planen, neue Sessions starten, sobald Dateien und Merges es erlauben |
| Hochrechnung über 100 % | nicht selbst anhalten. Dem Nutzer die Wahl vorlegen: warten, weniger Sessions parallel oder Opus statt Fable. Dazu die Uhrzeit, zu der 100 % erreicht wären. |
| eigene Session über 80 % Kontext | an eine frische Organisations-Session übergeben: Stand ins Memory, dort weiter mit diesem Skill |

Die Kontingente stehen in jeder Wellenplanung, in jedem Überwachungsdurchlauf
und im Report, jeweils in einer Zeile mit Prozent, Tempo je Stunde,
Hochrechnung und Reset in Berliner Zeit. Den Messwert mit Uhrzeit in den
Wellenplan im Memory schreiben, damit der nächste Durchlauf ein Tempo hat.

## 2. Issues sichten

Je offenem Issue gegen den aktuellen Code prüfen (grep, `git log`, verwandte
geschlossene Issues) und einordnen:

- **erledigt oder überholt:** Schließen vorschlagen, mit Beleg (Datei:Zeile, PR).
- **zusammenlegen:** wenn ein Issue das andere mit erledigt.
- **neu fassen:** wenn die Annahme nicht mehr stimmt. Die alte Fassung als
  `<details><summary>Ursprüngliche Fassung</summary>` darunter stehen lassen.
- **blockiert:** durch eine Entscheidung, einen Zugang, eine andere Session
  oder ein anderes Issue. Immer benennen, woran genau.
- **zu groß:** passt nicht in einen PR/MR, den `/code-review` vollständig
  prüft. In Sub-Issues schneiden (5).
- **frei:** sofort bearbeitbar.

**Schließen, Zusammenlegen und Neufassen erst nach dem Okay des Nutzers.**
Einen Stapel neuer Issues vorher mit Titeln freigeben lassen.

## 3. Stand-Kommentar je offenem Issue

Kurz, und so, dass eine neue Session ohne weitere Erklärung loslegen kann:

```
**Stand <Datum>**

- **Erledigt:** … (mit Belegen)
- **Hängt an:** Entscheidung (<wer>) / Zugang / Session X / Issue #N – oder „nichts“
- **Umsetzung:** Einstieg Datei:Zeile, Randbedingungen, Tests
- **Achtung:** Stolperfallen, Überschneidungen mit anderen Issues
- **Modell:** Opus | Fable durchgehend | Fable bis zum abgestimmten Konzept, danach Opus – <Halbsatz Grund>
```

Fable bei unklarer Ursache über mehrere Schichten, bei Fehlern, die erst im
Betrieb auffallen (Migration, Autorisierung, Datentrennung), bei Entwürfen
über viele Module. Sonst Opus.

Kommentare einzeln und nachvollziehbar posten, nicht als großes Skript mit
vielen Schreibzugriffen; so ein Skript lehnt der Auto-Mode ab.

## 4. Entscheidungen bündeln

Eine Tabelle mit Issue, Frage, zwei bis drei Möglichkeiten und Empfehlung,
dazu eine eigene Liste mit **Handgriffen, die nur der Nutzer kann** (Rechte,
fremde Konsolen, Verträge). Jede Entscheidung danach **als Kommentar ins
Issue** und ins Memory, damit die ausführende Session sie dort findet.

## 5. Welle planen

- **Kennungen:** je Session ein Buchstabe (A, B, … oder F1, F2 für
  zusammengehörige Schritte). Der Session-Titel lautet `<Kennung> · #<Issues>`.
  Die App vergibt den Titel selbst aus dem ersten Satz. Deshalb steht die
  Kennung vorne im Prompt, und die Organisations-Session benennt jede neue
  Session per `set_session_title` um, sobald sie auftaucht.
- **Tabelle** mit Kennung, Issue, Modell, Prompt, Parallel, Startbedingung und
  der Spalte „wo sie ohne den Nutzer anhält“.
- **Prompt-Muster:**
  - Umsetzung: `<K> · Bearbeite Issue #N. Der Kommentar „Stand <Datum>“ enthält den Stand.`
  - Konzept: `<K> · Erarbeite das Konzept für #N, wie im Issue beschrieben. Schreib es als Kommentar ins Issue und halte dann an. Noch nichts umsetzen.`
- **Konzept und Umsetzung in getrennten Sessions.** Ein Modellwechsel mitten
  in der Session liest den ganzen Kontext ungecacht neu ein.
- **Große Vorhaben schneiden.** Passt ein Vorhaben nicht in einen PR/MR, den
  `/code-review` vollständig prüft und den eine Session ohne Zusammenfassung
  ihres Kontexts schafft, wird sein Issue zum Eltern-Issue. Das Konzept endet
  dann mit dem Schnitt: Sub-Issues mit Titel, Reihenfolge und Abhängigkeiten.
  Nach der Freigabe der Titel (2) legt die Konzept-Session sie an (GitHub:
  `gh issue create --parent <N>`, bestehende mit
  `gh issue edit <N> --add-sub-issue <n>,<m>`; GitLab: Tasks als Child Items
  am Issue oder Issues unter einem Epic).
  - **Vertikal:** Jedes Sub-Issue liefert fertiges Verhalten, das sich von
    außen testen lässt. Nicht erst Datenmodell, dann Oberfläche, dann
    Schnittstellen; solche Teile liegen halb fertig in `main`.
  - **Nicht zu klein:** Jedes Sub-Issue kostet einen PR/MR, ein Review, eine
    Merge-Freigabe des Nutzers und die Startkosten einer Session.
  - **Eine Quelle:** Konzept und Entscheidungen stehen nur im Eltern-Issue.
    Das Sub-Issue beginnt mit „Teil von #N“ und beschreibt nur seinen Teil.
    Die ausführende Session liest das Eltern-Issue mit.
  - **Reihenfolge:** Sub-Issues eines Vorhabens bekommen Kennungen F1, F2, ….
    Teilen sie Dateien, ist der Merge des Vorgängers die Startbedingung.
    Parallel laufen dann Sub-Issues verschiedener Vorhaben.
- **Nicht in eine Welle:** große Umbauten, die fast jede Datei berühren, und
  alles, was eine Entscheidung des Nutzers braucht.
- **Kapazität:** Läuft alles auf einem kleinen Server, je Session etwa 300 MB
  rechnen und eine Reserve lassen. Dazu die Kontingente nach 1a.

## 6. Überwachen

Der Nutzer startet `/loop 15m Überwache Welle <n> (<Kennungen>) nach dem Wellenplan.`
Jeder Durchlauf:

1. Neue Sessions umbenennen (s. 5). Doppelte Sessions für dasselbe Issue
   melden.
2. Je Session: läuft sie, wartet sie auf den Nutzer (Frage, Rechteabfrage,
   Merge-Freigabe) oder ist sie fertig?
3. Überschneidungen der Branches, offene PRs/MRs, Pipeline auf `main`.
4. Claude-Kontingente (1a).
5. Kurz berichten, was der Nutzer tun muss, in welcher Session und in welcher
   Reihenfolge. `PushNotification` nur, wenn der Nutzer weg sein könnte und
   etwas auf ihn wartet.

Ist die Welle durch, den Cron-Job beenden, statt leere Durchläufe zu fahren.

## 7. Mergen

Normalfall: Die Session mergt selbst, nachdem der Nutzer in ihr zugestimmt
hat. Sie mischt `main` ein, testet, pusht und löscht den Branch. Zwei
Sessions, die dieselbe Datei ändern, nacheinander.

Vor jedem Merge-Vorschlag läuft `/code-review` (Ziel `origin/main...HEAD`).
Bilder gehören nur zu einem Merge, der Layout, Bedienung oder Text einer
Oberfläche sichtbar ändert: je Seite eins vorher, eins nachher, im Chat.

## 8. Deployen

Gesammelt am Ende einer Welle. Einzeln nur, wenn ein Fehler live ist. Vorher
dem Nutzer den Umfang zeigen (`<release>..main`), dann erst auf „deployen“
hin handeln.

## 9. Gegenprobe

Nach dem Deploy prüfen, ob die Änderung im Betrieb ankommt, mit dem Weg, den
das Projekt dafür hat (Smoke-Test, Health-Endpunkt, ein echter Aufruf). Das
Ergebnis in einem Satz ins Issue.

## 10. Aufräumen und festhalten

- **Fertige Sessions:** Worktree sauber, `HEAD` in `main`, Issue geschlossen,
  dann Titel `_closed_ <Titel>` und `archive_session`. Nur Sessions, denen der
  Nutzer zugestimmt hat. Danach mit `git worktree list` prüfen, ob der
  Worktree noch da ist, und ihn entfernen (`git worktree remove`, dann
  `git worktree prune`). Nie den Worktree einer laufenden Session anfassen.
- **Memory:** den Wellenplan (`project_issue_wellenplan.md`) mit Fortschritt,
  Entscheidungen und nächster Welle nachziehen, neue Stolperfallen in die
  passende Datei, dazu die Zeile in `MEMORY.md`.

## 11. Wellen-Report

**Nach jeder Welle** schreibt die Organisations-Session einen Report in den
Chat. Quellen, damit nichts aus dem Gedächtnis kommt: `git log --first-parent
--since="<heute> 00:00" origin/main`, heute geschlossene Issues, Deploys,
der Wellenplan im Memory.

```
## Wellen-Report – Welle <n>, <Datum>, <Uhrzeit> Uhr

### In dieser Welle erledigt
| Kennung | Issue | Ergebnis | Live seit | Gegenprobe |
|---|---|---|---|---|

### Heute insgesamt erledigt
- **Geschlossen:** #…, #… (je ein Halbsatz, was es bringt)
- **Vorhaben:** #N <Kurzname>: x von y Sub-Issues erledigt (nur, was heute vorankam)
- **Deploys:** …
- **Außerdem:** Handgriffe und Aufräumarbeiten
- **Kontingente:** Woche <x> % (<t> Punkte je Stunde, hochgerechnet <h> % am Reset), Reset <Tag Uhrzeit>

### Bewusst nicht jetzt
| Issue | Warum nicht jetzt | Woran es hängt bzw. wann |
|---|---|---|

### Wartet auf dich
- Entscheidungen, Freigaben (Merge in Session X), Handgriffe, jeweils mit Issue

### Als Nächstes
| Kennung | Issue | Modell | Prompt | Parallel | Startbedingung |
|---|---|---|---|---|---|
```

„Als Nächstes“ ist ein Vorschlag, keine Festlegung: Die Tabelle muss aber
ohne Rückfrage startbar sein. Sicherheit vor Komfort, Live-Fehler vor Neuem,
und Sessions, die ohne den Nutzer bis zu einem Haltepunkt kommen, zuerst.
„Bewusst nicht jetzt“ ist keine Resteliste, dort steht nur, was mit Absicht
zurückgestellt ist, mit Grund.

## Stolperfallen

Ergänze die Liste, wenn dir etwas Neues passiert.

- **Zeiten:** Container und Server laufen oft auf UTC. Dem Nutzer immer
  Berliner Zeit nennen.
- **`ps -eo` zeigt alle Benutzer.** Einen Prozess erst jemandem zuschreiben,
  wenn die Spalte `user` geprüft ist.
