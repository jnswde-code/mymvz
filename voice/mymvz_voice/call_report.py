"""What happened in one call, reported to the web app when it ends (#45).

Only when, how long and which outcomes, plus the reference of the first
request and the id of the first callback; never a number, a name or words.
The web app picks the strongest outcome (`telephony.services.final_outcome`,
an emergency hint always wins) and derives the mode from the opening hours.
"""

from __future__ import annotations

import logging
import time
from datetime import UTC, datetime
from enum import StrEnum

from .api_client import ApiClient, ApiRejected, ApiUnavailable
from .safety import Reason

logger = logging.getLogger("mymvz_voice.call_report")


class Outcome(StrEnum):
    INFO = "info"
    REQUEST_CREATED = "request_created"
    CALLBACK_REQUESTED = "callback_requested"
    HANDED_OFF = "handed_off"
    EMERGENCY_HINT = "emergency_hint"
    FAILED = "failed"


class CallReport:
    def __init__(self, now: datetime | None = None) -> None:
        self.started_at = now or datetime.now(UTC)
        self._began = time.monotonic()
        self.outcomes: set[Outcome] = set()
        self.request_reference = ""
        self.callback_id: str | None = None

    def note(self, outcome: Outcome) -> None:
        self.outcomes.add(outcome)

    def hand_off(self, reason: Reason) -> None:
        """Every hand-off, from the word filter, a key or the LLM."""
        if reason is Reason.EMERGENCY_HINT:
            self.note(Outcome.EMERGENCY_HINT)
        else:
            self.note(Outcome.HANDED_OFF)

    def request_created(self, reference: str) -> None:
        self.note(Outcome.REQUEST_CREATED)
        self.request_reference = self.request_reference or reference

    def callback_created(self, callback_id: str) -> None:
        self.note(Outcome.CALLBACK_REQUESTED)
        self.callback_id = self.callback_id or callback_id

    def payload(self) -> dict:
        data = {
            "started_at": self.started_at.isoformat(),
            "duration_seconds": round(time.monotonic() - self._began),
            "outcomes": sorted(self.outcomes),
        }
        if self.request_reference:
            data["request_reference"] = self.request_reference
        if self.callback_id:
            data["callback_id"] = self.callback_id
        return data

    async def send(self, api: ApiClient) -> None:
        """At the end of the call; a failure is logged, the call is over anyway."""
        try:
            await api.record_call(self.payload())
        except (ApiUnavailable, ApiRejected) as error:
            # Only the reason, never what was sent.
            logger.warning("Anruf nicht gemeldet: %s", type(error).__name__)
