"""What the assistant says and does once the safety switch has fired."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Protocol

from . import texts
from .safety import Detection, Reason


class Transfer(Protocol):
    """Warm transfer to the practice team (#14, 2.4).

    `available` says whether there is a line to transfer to at all;
    `connect` stays with the caller until someone answers and returns False
    when nobody did.
    """

    available: bool

    async def connect(self, reason: Reason) -> bool: ...


class NoTransfer:
    """Until SIP is connected (T0 in #14) nobody can be reached."""

    available = False

    async def connect(self, reason: Reason) -> bool:
        return False


def _crisis_line(detection: Detection) -> str:
    return texts.CRISIS_LINE if detection.crisis else ""


def _connecting(detection: Detection) -> str:
    if detection.reason is Reason.EMERGENCY_HINT:
        return texts.EMERGENCY_FIRST + _crisis_line(detection) + texts.EMERGENCY_CONNECTING
    if detection.reason is Reason.HEALTH_TOPIC:
        return texts.HEALTH_CONNECTING
    return texts.CONNECTING


def _nobody(detection: Detection) -> str:
    if detection.reason is Reason.EMERGENCY_HINT:
        return texts.EMERGENCY_NOBODY + _crisis_line(detection) + texts.NUMBERS_UNDERSTOOD
    if detection.reason is Reason.HEALTH_TOPIC:
        return texts.HEALTH_NOBODY
    return texts.NOBODY


async def respond(detection: Detection, transfer: Transfer) -> AsyncIterator[str]:
    """The sentences for one hand-off, in order; tries the transfer between them.

    Emergency hints always end with 112 and 116 117 unless a person took
    the call. The assistant never hangs up here.
    """
    if transfer.available:
        yield _connecting(detection)
        if await transfer.connect(detection.reason):
            return
    yield _nobody(detection)
