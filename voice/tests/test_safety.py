"""Word filter and safety switch (#14, section 3).

All sentences are made up. Missing an emergency is the failure that counts;
the lists below grow with every case the test collection of #14 finds.
"""

import pytest

from mymvz_voice.safety import Detection, Reason, SafetyGate, detect, normalize

EMERGENCY = Detection(Reason.EMERGENCY_HINT)
CRISIS = Detection(Reason.EMERGENCY_HINT, crisis=True)
HUMAN = Detection(Reason.CALLER_ASKED)
HEALTH = Detection(Reason.HEALTH_TOPIC)


def test_normalize_spells_out_umlauts_and_drops_punctuation():
    assert normalize("Übelkeit, Atemnot!  Straße?") == "uebelkeit atemnot strasse"


@pytest.mark.parametrize(
    "sentence",
    [
        "Mein Mann hat starke Brustschmerzen.",
        "Ich habe so ein Stechen in der Brust.",
        "Die Brust tut so weh.",
        "Meine Mutter bekommt keine Luft mehr.",
        "Er kann nicht mehr richtig atmen.",
        "Sie ist bewusstlos.",
        "Mein Vater ist einfach umgekippt.",
        "Meine Mutter redet so komisch.",
        "Er spricht ganz verwaschen.",
        "Der Mundwinkel hängt auf einer Seite.",
        "Ich glaube, das ist ein Schlaganfall.",
        "Ist das ein Herzinfarkt?",
        "Mein Sohn hatte einen Krampfanfall.",
        "Mein Kind hat seit gestern hohes Fieber.",
        "Das Baby hat Fieber.",
        "Fieber bei meiner Tochter.",
        "Ich habe zu viele Tabletten genommen.",
        "Er hat zu viel Methadon genommen.",
        "Ich glaube, das ist eine Überdosis.",
        "Die Wunde blutet stark.",
        "Es ist ein Notfall.",
        "Brauche ich einen Krankenwagen?",
        "Nach dem Wespenstich ist die Zunge geschwollen.",
        "Er ist ganz verwirrt.",
        "Sie reagiert nicht.",
        "Wir hatten einen Unfall.",
    ],
)
def test_emergency_hints_trigger(sentence):
    assert detect(sentence) == EMERGENCY


@pytest.mark.parametrize(
    "sentence",
    [
        "Ich will nicht mehr leben.",
        "Ich denke an Selbstmord.",
        "Ich möchte mir etwas antun.",
        "Ich will sterben.",
        "Ich bin lebensmüde.",
    ],
)
def test_suicidal_thoughts_trigger_with_crisis_line(sentence):
    assert detect(sentence) == CRISIS


@pytest.mark.parametrize(
    "sentence",
    [
        "Kann ich mit einem Menschen sprechen?",
        "Bitte einen Mitarbeiter.",
        "Verbinden Sie mich bitte.",
        "Ich möchte mit der Praxis sprechen.",
        "Ich will mit dem Arzt sprechen.",
        "Gibt es da auch eine echte Person?",
        "Ich möchte das Praxisteam.",
    ],
)
def test_asking_for_a_person_triggers(sentence):
    assert detect(sentence) == HUMAN


@pytest.mark.parametrize(
    "sentence",
    [
        "Ich habe Rückenschmerzen.",
        "Mir ist seit Tagen übel.",
        "Ich habe Kopfweh.",
        "Ich brauche meine Tabletten.",
        "Es geht um meine Substitution.",
        "Kontrolltermin nach der Chemo.",
        "Ist mein Befund schon da?",
        "Wie sind meine Blutwerte?",
        "Ich bin krank.",
        "Ich habe Husten und Fieber.",
    ],
)
def test_health_topics_trigger(sentence):
    assert detect(sentence) == HEALTH


@pytest.mark.parametrize(
    "sentence",
    [
        "Wann haben Sie geöffnet?",
        "Ich möchte einen Check-up.",
        "Ich möchte einen Termin zur Blutabnahme.",
        "Wo kann ich parken?",
        "Gibt es einen barrierefreien Eingang?",
        "Ich brauche ein Rezept.",
        "Ich brauche eine Krankschreibung.",
        "Wie ist die Adresse?",
        "Ich möchte meinen Termin absagen.",
        "Ist die Praxis am Freitag offen?",
        "Ich hätte gern eine Gesundheitsuntersuchung.",
        "Mein Name ist Erika Beispiel.",
    ],
)
def test_ordinary_requests_pass(sentence):
    assert detect(sentence) is None


def test_most_serious_hit_wins():
    """A sentence with several hits takes the most serious one."""
    assert detect("Ich will einen Menschen, ich habe Brustschmerzen") == EMERGENCY
    assert detect("Mitarbeiter bitte, ich habe Rückenschmerzen") == HUMAN
    assert detect("Brustschmerzen und ich will nicht mehr leben") == CRISIS


def test_gate_passes_ordinary_turns():
    gate = SafetyGate()
    assert gate.check("Wann haben Sie geöffnet?") is None
    assert not gate.emergency_seen


def test_gate_has_no_way_back_after_an_emergency():
    """After an emergency hint every later turn gets the emergency answer."""
    gate = SafetyGate()
    assert gate.check("Er bekommt keine Luft") == EMERGENCY
    assert gate.check("Ach so, dann möchte ich einen Termin") == EMERGENCY
    assert gate.check("Kann ich mit einem Menschen sprechen?") == EMERGENCY
    assert gate.emergency_seen


def test_gate_keeps_the_crisis_line_once_named():
    gate = SafetyGate()
    gate.check("Ich will nicht mehr leben")
    assert gate.check("Er hat Brustschmerzen") == CRISIS
    assert gate.check("Wann haben Sie geöffnet?") == CRISIS


def test_gate_health_topic_does_not_lock():
    gate = SafetyGate()
    assert gate.check("Ich habe Rückenschmerzen") == HEALTH
    assert gate.check("Wann haben Sie geöffnet?") is None


def test_escalate_from_llm_locks_only_for_emergencies():
    gate = SafetyGate()
    assert gate.escalate(Reason.OUT_OF_SCOPE) == Detection(Reason.OUT_OF_SCOPE)
    assert not gate.emergency_seen
    assert gate.escalate(Reason.EMERGENCY_HINT) == EMERGENCY
    assert gate.escalate(Reason.CALLER_ASKED) == EMERGENCY
    assert gate.check("Wann haben Sie geöffnet?") == EMERGENCY
