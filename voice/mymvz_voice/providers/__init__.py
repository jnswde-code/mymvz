"""Choose the STT, LLM and TTS providers by configuration.

The agent only ever sees LiveKit's base classes (`stt.STT`, `llm.LLM`,
`tts.TTS`); which class sits behind them is decided here and nowhere else.
Adding a provider (after the choice in #18) means one factory function, its
package in `requirements.txt` and an entry in the matching table. The agent
does not change.
"""

from __future__ import annotations

from collections.abc import Callable, Mapping

from livekit.agents import llm, stt, tts

from ..config import ConfigError, Settings
from . import fake

STT_PROVIDERS: Mapping[str, Callable[[Settings], stt.STT]] = {
    "fake": lambda settings: fake.FakeSTT(language=settings.language),
}
LLM_PROVIDERS: Mapping[str, Callable[[Settings], llm.LLM]] = {
    "fake": lambda settings: fake.FakeLLM(),
}
TTS_PROVIDERS: Mapping[str, Callable[[Settings], tts.TTS]] = {
    "fake": lambda settings: fake.FakeTTS(),
}


def _lookup[T](
    kind: str, name: str, table: Mapping[str, Callable[[Settings], T]]
) -> Callable[[Settings], T]:
    try:
        return table[name]
    except KeyError:
        known = ", ".join(sorted(table))
        raise ConfigError(f"Unbekannter Anbieter für {kind}: {name!r} (bekannt: {known})") from None


def validate(settings: Settings) -> None:
    """Raise ConfigError for any provider name that is not in its table."""
    _lookup("Spracherkennung", settings.stt_provider, STT_PROVIDERS)
    _lookup("LLM", settings.llm_provider, LLM_PROVIDERS)
    _lookup("Sprachausgabe", settings.tts_provider, TTS_PROVIDERS)


def build_stt(settings: Settings) -> stt.STT:
    return _lookup("Spracherkennung", settings.stt_provider, STT_PROVIDERS)(settings)


def build_llm(settings: Settings) -> llm.LLM:
    return _lookup("LLM", settings.llm_provider, LLM_PROVIDERS)(settings)


def build_tts(settings: Settings) -> tts.TTS:
    return _lookup("Sprachausgabe", settings.tts_provider, TTS_PROVIDERS)(settings)
