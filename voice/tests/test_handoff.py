"""What the assistant says after the switch fired (#14, 3.2)."""

import pytest

from mymvz_voice import texts
from mymvz_voice.handoff import NoTransfer, respond
from mymvz_voice.safety import Detection, Reason


class FakeTransfer:
    available = True

    def __init__(self, answered: bool) -> None:
        self.answered = answered
        self.reasons: list[Reason] = []

    async def connect(self, reason: Reason) -> bool:
        self.reasons.append(reason)
        return self.answered


async def sentences(detection, transfer):
    return [s async for s in respond(detection, transfer)]


async def test_emergency_without_line_gives_both_numbers():
    said = await sentences(Detection(Reason.EMERGENCY_HINT), NoTransfer())
    assert len(said) == 1
    assert "112" in said[0] and "116 117" in said[0]
    assert said[0].endswith(texts.NUMBERS_UNDERSTOOD)
    assert "Telefonseelsorge" not in said[0]


async def test_emergency_nobody_answers_falls_back_to_numbers():
    transfer = FakeTransfer(answered=False)
    said = await sentences(Detection(Reason.EMERGENCY_HINT), transfer)
    assert said[0].startswith(texts.EMERGENCY_FIRST)
    assert said[0].endswith(texts.EMERGENCY_CONNECTING)
    assert said[1].startswith(texts.EMERGENCY_NOBODY)
    assert transfer.reasons == [Reason.EMERGENCY_HINT]


async def test_emergency_answered_ends_after_connecting():
    said = await sentences(Detection(Reason.EMERGENCY_HINT), FakeTransfer(answered=True))
    assert said == [texts.EMERGENCY_FIRST + texts.EMERGENCY_CONNECTING]


@pytest.mark.parametrize("answered", [True, False])
async def test_crisis_names_the_crisis_line_on_both_paths(answered):
    said = await sentences(Detection(Reason.EMERGENCY_HINT, crisis=True), FakeTransfer(answered))
    assert "Telefonseelsorge" in said[0]
    if not answered:
        assert "Telefonseelsorge" in said[1]


async def test_health_topic_without_line_names_116_117():
    said = await sentences(Detection(Reason.HEALTH_TOPIC), NoTransfer())
    assert said == [texts.HEALTH_NOBODY]


async def test_health_topic_connects():
    said = await sentences(Detection(Reason.HEALTH_TOPIC), FakeTransfer(answered=True))
    assert said == [texts.HEALTH_CONNECTING]


@pytest.mark.parametrize(
    "reason", [Reason.CALLER_ASKED, Reason.NOT_UNDERSTOOD, Reason.OUT_OF_SCOPE]
)
async def test_other_reasons(reason):
    assert await sentences(Detection(reason), FakeTransfer(answered=True)) == [texts.CONNECTING]
    assert await sentences(Detection(reason), NoTransfer()) == [texts.NOBODY]
