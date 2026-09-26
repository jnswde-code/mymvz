"""Latency from the end of the caller's sentence to the start of the answer.

LiveKit notes per answer in `ChatMessage.metrics` how long the turn took
(`e2e_latency`) and how that splits into LLM and TTS. The log keeps only
these numbers, never text, and sums them up when the call ends.
"""

from __future__ import annotations

import logging
import statistics
from collections.abc import Mapping

logger = logging.getLogger("mymvz_voice.latency")


class LatencyLog:
    def __init__(self) -> None:
        self.values: list[float] = []

    def observe(self, metrics: Mapping[str, object]) -> None:
        """One assistant message; messages without a measured turn are skipped.

        Fixed announcements (greeting, hand-off) have no preceding caller
        turn, and an answer to a key press none either.
        """
        e2e = metrics.get("e2e_latency")
        if not isinstance(e2e, int | float):
            return
        self.values.append(float(e2e))
        logger.info(
            "Latenz Satzende bis Antwort: %.3f s (LLM erstes Token %s, TTS erstes Audio %s)",
            e2e,
            _seconds(metrics.get("llm_node_ttft")),
            _seconds(metrics.get("tts_node_ttfb")),
        )

    def summary(self) -> str | None:
        if not self.values:
            return None
        return (
            f"{len(self.values)} Antworten, Median {statistics.median(self.values):.3f} s, "
            f"höchstens {max(self.values):.3f} s"
        )

    def log_summary(self) -> None:
        if text := self.summary():
            logger.info("Latenz im Gespräch: %s", text)


def _seconds(value: object) -> str:
    return f"{value:.3f} s" if isinstance(value, int | float) else "–"
