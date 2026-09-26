"""Safety switch in front of the LLM (#14, sections 3 and 7).

A fixed word filter looks at every caller utterance before the LLM does.
A hit leaves the normal conversation for a person, or for 112 and 116 117
when nobody can be reached, whatever the LLM would have made of it. The
filter never grades urgency: every hit leads to *more* human attention,
never to "this can wait". That keeps the assistant below annex III no. 5
lit. d of the AI Act and outside MDR rule 11 (#14, section 4).

False alarms are acceptable, missed emergencies are not. When in doubt,
a pattern belongs in the list.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import StrEnum


class Reason(StrEnum):
    """Why a call leaves the assistant (fixed list, #14 section 7)."""

    CALLER_ASKED = "caller_asked"
    HEALTH_TOPIC = "health_topic"
    EMERGENCY_HINT = "emergency_hint"
    NOT_UNDERSTOOD = "not_understood"
    OUT_OF_SCOPE = "out_of_scope"


@dataclass(frozen=True)
class Detection:
    reason: Reason
    # Hint of suicidal thoughts: the crisis line is named as well.
    crisis: bool = False


# Patterns work on normalised text: lower case, umlauts spelled out
# (ä -> ae, ß -> ss), everything but letters and digits as single spaces.
_W = r"(?:\w+ )"  # one word, for "up to n words in between"

_CRISIS = [
    r"suizid",
    r"selbstmord",
    r"umbringen",
    r"\bbringe? mich " + _W + r"{0,2}um\b",
    r"mich " + _W + r"{0,2}(?:toeten|erhaengen|umbringen)",
    r"\btoeten\b",
    r"lebensmuede",
    r"nicht mehr leben",
    r"(?:will|moechte|wollte) " + _W + r"{0,3}(?:nicht mehr leben|sterben)",
    r"(?:mir|mich) (?:etwas|was) an(?:tun|zutun)",
    r"(?:mir|mich) das leben nehmen",
    r"mich (?:selbst )?(?:ritzen|verletzen)",
]

_EMERGENCY = [
    r"notfall",
    r"notarzt",
    r"rettungswagen",
    r"krankenwagen",
    r"lebensgefahr",
    r"brust " + _W + r"{0,3}\w*schmerz",
    r"brust\w*schmerz",
    r"herz\w*schmerz",
    r"schmerz\w* (?:in|an) der brust",
    r"(?:druck|enge|stechen\w*) (?:auf|in) der brust",
    r"brust tut " + _W + r"?weh",
    r"herz ?infarkt",
    r"herzstillstand",
    r"schlaganfall",
    r"atemnot",
    r"(?:keine|kaum|schlecht|schwer) luft",
    r"(?:nicht|kaum|schlecht|schwer) " + _W + r"{0,2}atmen",
    r"atmet (?:nicht|kaum)",
    r"erstick",
    r"bewusstlos",
    r"ohnmacht",
    r"ohnmaechtig",
    r"nicht (?:mehr )?ansprechbar",
    r"(?:er|sie|es|kind|baby) reagiert (?:gar |ueberhaupt )?nicht",
    r"(?:mann|frau|mutter|vater|oma|opa|sohn|tochter) reagiert (?:gar |ueberhaupt )?nicht",
    r"zusammengebrochen",
    r"umgekippt",
    r"kollabiert",
    r"\bkrampf",
    r"\banfall",
    r"epilep",
    r"laehmung",
    r"gelaehmt",
    r"(?:haengt|haengende?r?) (?:\w+ )?(?:mundwinkel|gesicht)",
    r"(?:mundwinkel|gesicht\w*) (?:\w+ )?haengt",
    r"(?:nicht|kaum) (?:mehr )?(?:richtig )?(?:sprechen|reden)\b",
    r"(?:redet|spricht|sprechen|reden) (?:\w+ )?(?:so )?(?:komisch|wirr|verwaschen|undeutlich)",
    r"(?:ist|wirkt|scheint|wird) " + _W + r"{0,2}verwirrt",
    r"blut(?:et|ung|ungen|en)\b",
    r"viel blut",
    r"blut (?:spucken|husten|erbrechen|im stuhl|im urin)",
    r"ueberdosis",
    r"zu ?viel\w* " + _W + r"{0,3}(?:genommen|geschluckt|gespritzt|eingenommen)",
    r"vergift",
    r"\bgift",
    r"(?:alle|viele|ganze|packung|schachtel) "
    + _W
    + r"{0,2}(?:tabletten|pillen|medikamente) "
    + _W
    + r"{0,2}(?:genommen|geschluckt|eingenommen)",
    r"(?:tabletten|pillen|medikamente) " + _W + r"{0,4}zu ?viel",
    r"unfall",
    r"allergisch\w* (?:schock|reaktion)",
    r"anaphyla",
    r"(?:zunge|hals|gesicht|lippen?) (?:\w+ )?(?:an)?geschwollen",
    r"(?:kind|baby|saeugling|sohn|tochter)\w* " + _W + r"{0,5}fieber",
    r"fieber " + _W + r"{0,5}(?:kind|baby|saeugling|sohn|tochter)",
]

_CALLER_ASKED = [
    r"\bmenschen?\b",
    r"\bmitarbeiter",
    r"\bpraxisteam",
    r"\b(?:echte|richtige|lebende)[nr]? person",
    r"\bsprechstundenhilfe",
    r"\barzthelfer",
    r"verbinden sie mich",
    r"(?:mit|zu) (?:der|ihrer) praxis (?:sprechen|verbunden|verbinden|reden)",
    r"(?:mit|zum|zur) (?:dem |der )?(?:arzt|aerztin|doktor|doktorin) (?:sprechen|verbunden|reden)",
    r"(?:mit|zur|zum) (?:der |dem )?(?:rezeption|empfang|anmeldung) (?:sprechen|verbunden|reden)",
]

_HEALTH_TOPIC = [
    r"schmerz",
    r"weh\b",
    r"fieber",
    r"husten",
    r"\buebel",
    r"erbrech",
    r"schwindel",
    r"durchfall",
    r"ausschlag",
    r"entzuend",
    r"infekt",
    r"grippe",
    r"erkaelt",
    r"corona",
    r"allerg",
    r"verletz",
    r"gebrochen",
    r"gestuerzt",
    r"schwanger",
    r"\bkrank\b",
    r"beschwerden",
    r"symptom",
    r"diagnose",
    r"befund",
    r"labor ?(?:wert|ergebnis)",
    r"blut ?(?:wert|druck|zucker)",
    r"medikament",
    r"tablette",
    r"\bpillen?\b",
    r"methadon",
    r"polamidon",
    r"subutex",
    r"substitu",
    r"tumor",
    r"krebs",
    r"chemo",
]


def _compile(patterns: list[str]) -> re.Pattern:
    return re.compile("|".join(f"(?:{p})" for p in patterns))


_CHECKS = [
    (_compile(_CRISIS), Detection(Reason.EMERGENCY_HINT, crisis=True)),
    (_compile(_EMERGENCY), Detection(Reason.EMERGENCY_HINT)),
    (_compile(_CALLER_ASKED), Detection(Reason.CALLER_ASKED)),
    (_compile(_HEALTH_TOPIC), Detection(Reason.HEALTH_TOPIC)),
]

_SPELLED_OUT = str.maketrans({"ä": "ae", "ö": "oe", "ü": "ue"})


def normalize(text: str) -> str:
    folded = text.casefold().translate(_SPELLED_OUT)  # casefold turns ß into ss
    return " ".join(re.findall(r"[a-z0-9]+", folded))


def detect(text: str) -> Detection | None:
    """The most serious hit in one utterance, None if the filter has nothing."""
    normalized = normalize(text)
    for pattern, detection in _CHECKS:
        if pattern.search(normalized):
            return detection
    return None


class SafetyGate:
    """State of the switch for one call.

    After the first emergency hint there is no way back (#14, 3.1 no. 6):
    every later turn gets the emergency answer again, the LLM is not asked
    any more and no appointment request is taken in this call.
    """

    def __init__(self) -> None:
        self._emergency: Detection | None = None

    @property
    def emergency_seen(self) -> bool:
        return self._emergency is not None

    def check(self, text: str) -> Detection | None:
        """Run the word filter over one caller utterance."""
        found = detect(text)
        if found is not None and found.reason is Reason.EMERGENCY_HINT:
            self._note_emergency(found)
        return self._emergency or found

    def escalate(self, reason: Reason) -> Detection:
        """A hand-off from outside the word filter (LLM tool, key press)."""
        if reason is Reason.EMERGENCY_HINT:
            self._note_emergency(Detection(reason))
        return self._emergency or Detection(reason)

    def _note_emergency(self, found: Detection) -> None:
        crisis = found.crisis or (self._emergency is not None and self._emergency.crisis)
        self._emergency = Detection(Reason.EMERGENCY_HINT, crisis=crisis)
