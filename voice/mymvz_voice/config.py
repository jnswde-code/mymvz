"""Settings of the voice agent, read from environment variables (`.env`).

LiveKit reads `LIVEKIT_URL`, `LIVEKIT_API_KEY` and `LIVEKIT_API_SECRET`
itself; here only what the agent decides on its own.
"""

from __future__ import annotations

import os
from collections.abc import Mapping
from dataclasses import dataclass


class ConfigError(Exception):
    """The environment does not describe a runnable agent."""


@dataclass(frozen=True)
class Settings:
    stt_provider: str
    llm_provider: str
    tts_provider: str
    language: str


def _value(environ: Mapping[str, str], name: str, default: str) -> str:
    # An empty or blank value (`NAME=`) counts as missing, as in config/env.py.
    return (environ.get(name) or "").strip() or default


def load_settings(environ: Mapping[str, str] | None = None) -> Settings:
    """Settings from the environment; without a choice, the fake providers.

    Defaulting to `fake` keeps a missing variable from sending audio to a
    real provider by accident: no real provider is chosen before #18.
    """
    environ = os.environ if environ is None else environ
    return Settings(
        stt_provider=_value(environ, "VOICE_STT_PROVIDER", "fake").lower(),
        llm_provider=_value(environ, "VOICE_LLM_PROVIDER", "fake").lower(),
        tts_provider=_value(environ, "VOICE_TTS_PROVIDER", "fake").lower(),
        language=_value(environ, "VOICE_LANGUAGE", "de-DE"),
    )
